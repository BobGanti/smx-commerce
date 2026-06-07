import pytest
from sqlalchemy import select

from smx_commerce import customer_has_active_entitlement, get_customer_active_entitlement
from smx_commerce.catalog.models import ProductPriceRow, ProductRow
from smx_commerce.checkout.objects import BuyerDetails, OrderStatus
from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.models import CustomerEntitlementRow, CustomerRow


@pytest.fixture()
def runtime(tmp_path):
    db_file = tmp_path / "commerce.db"

    runtime = CommerceRuntime.from_mapping(
        {
            "database_url": f"sqlite+pysqlite:///{db_file.as_posix()}",
        }
    )
    runtime.init_schema()

    return runtime


def seed_service_product(session, *, slug="service-product", price_code="standard"):
    session.add(
        ProductRow(
            product_public_id=f"prod_{slug}",
            slug=slug,
            name="Service Product",
            kind="service",
            summary="",
            description="",
            status="active",
            sort_order=0,
            metadata_json={},
        )
    )

    session.add(
        ProductPriceRow(
            product_slug=slug,
            code=price_code,
            label="Standard",
            amount_cents=2000,
            currency="EUR",
            status="active",
            billing_mode="one_time",
            billing_interval=None,
            sort_order=0,
            metadata_json={},
        )
    )

    session.flush()


def create_paid_order(runtime, *, product_slug="service-product", buyer_email="buyer@example.com"):
    with runtime.session_scope() as session:
        seed_service_product(session, slug=product_slug)

        repo = OrderRepository(session)

        order = repo.create_pending(
            product_slug=product_slug,
            price_code="standard",
            buyer=BuyerDetails(
                full_name="Buyer Example",
                email=buyer_email,
            ),
        )

        paid_order = repo.mark_paid(
            order.public_id,
            payment_reference="pay_test_reference",
        )

        customer = session.execute(
            select(CustomerRow).where(CustomerRow.email == buyer_email)
        ).scalar_one()

        return {
            "order_public_id": paid_order.public_id,
            "customer_public_id": customer.public_id,
            "product_slug": product_slug,
        }


def test_paid_order_creates_active_entitlement_and_access_helper_grants_access(runtime):
    created = create_paid_order(runtime)

    active_entitlement = get_customer_active_entitlement(
        customer_public_id=created["customer_public_id"],
        product_slug=created["product_slug"],
        runtime=runtime,
    )

    assert active_entitlement is not None
    assert active_entitlement.order_public_id == created["order_public_id"]
    assert active_entitlement.product_slug == created["product_slug"]
    assert active_entitlement.price_code == "standard"
    assert active_entitlement.status.value == "active"
    assert active_entitlement.entitlement_type.value == "service_access"

    assert customer_has_active_entitlement(
        customer_public_id=created["customer_public_id"],
        product_slug=created["product_slug"],
        price_code="standard",
        runtime=runtime,
    )

    assert not customer_has_active_entitlement(
        customer_public_id=created["customer_public_id"],
        product_slug=created["product_slug"],
        price_code="premium",
        runtime=runtime,
    )


@pytest.mark.parametrize(
    ("target_status", "expected_status"),
    [
        (OrderStatus.CANCELLED, "cancelled"),
        (OrderStatus.FAILED, "failed"),
        (OrderStatus.REFUNDED, "refunded"),
    ],
)
def test_terminal_order_status_cancels_order_entitlement(runtime, target_status, expected_status):
    created = create_paid_order(
        runtime,
        product_slug=f"{expected_status}-service-product",
        buyer_email=f"{expected_status}-buyer@example.com",
    )

    assert customer_has_active_entitlement(
        customer_public_id=created["customer_public_id"],
        product_slug=created["product_slug"],
        price_code="standard",
        runtime=runtime,
    )

    with runtime.session_scope() as session:
        order = OrderRepository(session).update(
            created["order_public_id"],
            status=target_status,
        )

        assert order.status.value == expected_status

    assert not customer_has_active_entitlement(
        customer_public_id=created["customer_public_id"],
        product_slug=created["product_slug"],
        price_code="standard",
        runtime=runtime,
    )

    with runtime.session_scope() as session:
        entitlement_rows = session.execute(
            select(CustomerEntitlementRow).where(
                CustomerEntitlementRow.order_public_id == created["order_public_id"]
            )
        ).scalars().all()

    assert len(entitlement_rows) == 1
    assert entitlement_rows[0].status == "cancelled"

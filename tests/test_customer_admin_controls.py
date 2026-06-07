from flask import Flask
from sqlalchemy import select

from smx_commerce import init_commerce
from smx_commerce.catalog.models import ProductPriceRow, ProductRow
from smx_commerce.checkout.objects import BuyerDetails
from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.models import CustomerRow, CustomerSessionRow
from smx_commerce.customers.repository import CustomerRepository


def create_app_and_runtime(tmp_path):
    db_file = tmp_path / "commerce.db"

    config = {
        "database_url": f"sqlite+pysqlite:///{db_file.as_posix()}",
        "admin_token": "test-admin-token",
        "host_site_title": "SyntaxMatrix",
        "host_home_url": "/",
        "store_title": "smxCommerce",
        "store_home_url": "/commerce",
        "public_base_url": "http://localhost:5055",
        "assets_dir": str(tmp_path / "assets"),
        "products_assets_dir": str(tmp_path / "assets" / "products"),
        "receipts_dir": str(tmp_path / "receipts"),
    }

    app = Flask(__name__)
    app.secret_key = "test-secret"
    init_commerce(app, config=config, init_schema=True)

    return app, CommerceRuntime.from_mapping(config)


def seed_paid_customer_order(
    runtime,
    *,
    product_slug="admin-customer-product",
    buyer_email="admin-customer@example.com",
):
    with runtime.session_scope() as session:
        session.add(
            ProductRow(
                product_public_id=f"prod_{product_slug}",
                slug=product_slug,
                name="Admin Customer Product",
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
                product_slug=product_slug,
                code="standard",
                label="Standard",
                amount_cents=2500,
                currency="EUR",
                status="active",
                billing_mode="one_time",
                billing_interval=None,
                sort_order=0,
                metadata_json={},
            )
        )

        session.flush()

        order = OrderRepository(session).create_pending(
            product_slug=product_slug,
            price_code="standard",
            buyer=BuyerDetails(
                full_name="Admin Customer Buyer",
                email=buyer_email,
            ),
        )

        paid_order = OrderRepository(session).mark_paid(
            order.public_id,
            payment_reference="pay_admin_customer",
        )

        customer = session.execute(
            select(CustomerRow).where(CustomerRow.email == buyer_email)
        ).scalar_one()

        return {
            "customer_public_id": customer.public_id,
            "order_public_id": paid_order.public_id,
            "product_slug": product_slug,
        }


def admin_login(client):
    response = client.post(
        "/commerce/admin/login",
        data={"admin_token": "test-admin-token"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 303}


def test_admin_can_block_and_unblock_customer_and_blocking_revokes_sessions(tmp_path):
    app, runtime = create_app_and_runtime(tmp_path)
    client = app.test_client()
    created = seed_paid_customer_order(runtime)

    with runtime.session_scope() as session:
        issued_session = CustomerRepository(session).create_session(
            customer_public_id=created["customer_public_id"]
        )

    client.set_cookie(
        "smx_commerce_customer_session",
        issued_session.session_token,
        path="/commerce",
    )

    account_before_block = client.get(
        "/commerce/customer/account",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert account_before_block.status_code == 200

    admin_login(client)

    detail_response = client.get(
        f"/commerce/admin/customers/{created['customer_public_id']}",
        headers={"Accept": "text/html"},
    )

    assert detail_response.status_code == 200
    assert "Block customer" in detail_response.get_data(as_text=True)

    block_response = client.post(
        f"/commerce/admin/customers/{created['customer_public_id']}/status",
        data={"status": "blocked"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert block_response.status_code in {302, 303}

    with runtime.session_scope() as session:
        customer = session.execute(
            select(CustomerRow).where(
                CustomerRow.public_id == created["customer_public_id"]
            )
        ).scalar_one()

        sessions = session.execute(
            select(CustomerSessionRow).where(CustomerSessionRow.customer_id == customer.id)
        ).scalars().all()

    assert customer.status == "blocked"
    assert sessions
    assert all(customer_session.revoked_at is not None for customer_session in sessions)

    account_after_block = client.get(
        "/commerce/customer/account",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert account_after_block.status_code in {302, 303}
    assert "/commerce/customer/login" in account_after_block.headers["Location"]

    unblock_response = client.post(
        f"/commerce/admin/customers/{created['customer_public_id']}/status",
        data={"status": "active"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert unblock_response.status_code in {302, 303}

    with runtime.session_scope() as session:
        customer = session.execute(
            select(CustomerRow).where(
                CustomerRow.public_id == created["customer_public_id"]
            )
        ).scalar_one()

    assert customer.status == "active"


def test_admin_can_cancel_and_reactivate_customer_entitlement(tmp_path):
    app, runtime = create_app_and_runtime(tmp_path)
    client = app.test_client()
    created = seed_paid_customer_order(
        runtime,
        product_slug="admin-entitlement-product",
        buyer_email="admin-entitlement@example.com",
    )

    admin_login(client)

    detail_response = client.get(
        f"/commerce/admin/customers/{created['customer_public_id']}",
        headers={"Accept": "text/html"},
    )

    assert detail_response.status_code == 200
    assert "Cancel" in detail_response.get_data(as_text=True)

    detail_json = client.get(
        f"/commerce/admin/customers/{created['customer_public_id']}?format=json",
        headers={"Accept": "application/json"},
    )

    entitlement_public_id = detail_json.get_json()["entitlements"][0]["public_id"]

    cancel_response = client.post(
        f"/commerce/admin/customers/{created['customer_public_id']}/entitlements/{entitlement_public_id}/status",
        data={"status": "cancelled"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert cancel_response.status_code in {302, 303}

    cancelled_json = client.get(
        f"/commerce/admin/customers/{created['customer_public_id']}?format=json",
        headers={"Accept": "application/json"},
    )

    assert cancelled_json.get_json()["entitlements"][0]["status"] == "cancelled"

    reactivate_response = client.post(
        f"/commerce/admin/customers/{created['customer_public_id']}/entitlements/{entitlement_public_id}/status",
        data={"status": "active"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert reactivate_response.status_code in {302, 303}

    active_json = client.get(
        f"/commerce/admin/customers/{created['customer_public_id']}?format=json",
        headers={"Accept": "application/json"},
    )

    assert active_json.get_json()["entitlements"][0]["status"] == "active"

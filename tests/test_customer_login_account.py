from urllib.parse import parse_qs, urlparse

from flask import Flask
from sqlalchemy import select

from smx_commerce import create_commerce_blueprint
from smx_commerce.catalog.models import ProductPriceRow, ProductRow
from smx_commerce.checkout.objects import BuyerDetails
from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.emailer import CustomerLoginEmailService
from smx_commerce.customers.models import CustomerRow
from smx_commerce.notifications import MemoryEmailSender


def create_app_runtime_and_sender(tmp_path):
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

    sender = MemoryEmailSender()
    customer_login_email_service = CustomerLoginEmailService(
        sender,
        from_email="no-reply@example.com",
        store_title="smxCommerce",
    )

    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(
        create_commerce_blueprint(
            config=config,
            init_schema=True,
            customer_login_email_service=customer_login_email_service,
        )
    )

    return app, CommerceRuntime.from_mapping(config), sender


def seed_paid_customer_order(runtime, *, buyer_email="customer-account@example.com"):
    with runtime.session_scope() as session:
        session.add(
            ProductRow(
                product_public_id="prod_customer_account",
                slug="customer-account-product",
                name="Customer Account Product",
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
                product_slug="customer-account-product",
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
            product_slug="customer-account-product",
            price_code="standard",
            buyer=BuyerDetails(
                full_name="Customer Account Buyer",
                email=buyer_email,
            ),
        )

        paid_order = OrderRepository(session).mark_paid(
            order.public_id,
            payment_reference="pay_customer_account",
        )

        customer = session.execute(
            select(CustomerRow).where(CustomerRow.email == buyer_email)
        ).scalar_one()

        return {
            "customer_public_id": customer.public_id,
            "order_public_id": paid_order.public_id,
            "buyer_email": buyer_email,
        }


def extract_verify_path_and_token(sender):
    verify_url = next(
        line.strip()
        for line in sender.messages[-1].body_text.splitlines()
        if "/commerce/customer/verify?" in line
    )

    parsed = urlparse(verify_url)

    return f"{parsed.path}?{parsed.query}", parse_qs(parsed.query)["token"][0]


def test_customer_magic_link_login_account_and_logout(tmp_path):
    app, runtime, sender = create_app_runtime_and_sender(tmp_path)
    client = app.test_client()
    created = seed_paid_customer_order(runtime)

    login_response = client.post(
        "/commerce/customer/login?next=/commerce/customer/account",
        json={
            "email": created["buyer_email"],
            "full_name": "Customer Account Buyer",
        },
        headers={"Accept": "application/json"},
    )

    assert login_response.status_code == 200
    assert login_response.get_json()["status"] == "ok"
    assert len(sender.messages) == 1
    assert created["buyer_email"] == sender.messages[0].to_email
    assert "/commerce/customer/verify?" in sender.messages[0].body_text

    verify_path, token = extract_verify_path_and_token(sender)

    verify_response = client.get(
        verify_path,
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert verify_response.status_code in {302, 303}
    assert verify_response.headers["Location"] == "/commerce/customer/account"
    assert "smx_commerce_customer_session=" in verify_response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in verify_response.headers.get("Set-Cookie", "")

    reused_token_response = client.get(
        f"/commerce/customer/verify?token={token}",
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )

    assert reused_token_response.status_code == 401

    account_response = client.get(
        "/commerce/customer/account",
        headers={"Accept": "text/html"},
    )

    assert account_response.status_code == 200

    html = account_response.get_data(as_text=True)

    assert created["buyer_email"] in html
    assert created["order_public_id"] in html
    assert "customer-account-product" in html
    assert "service_access" in html
    assert "/commerce/customer/logout" in html

    account_json_response = client.get(
        "/commerce/customer/account?format=json",
        headers={"Accept": "application/json"},
    )

    assert account_json_response.status_code == 200
    assert account_json_response.get_json()["customer"]["email"] == created["buyer_email"]
    assert len(account_json_response.get_json()["orders"]) == 1
    assert len(account_json_response.get_json()["entitlements"]) == 1

    logout_response = client.post(
        "/commerce/customer/logout",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert logout_response.status_code in {302, 303}
    assert "smx_commerce_customer_session=;" in logout_response.headers.get("Set-Cookie", "")

    account_after_logout = client.get(
        "/commerce/customer/account",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert account_after_logout.status_code in {302, 303}
    assert "/commerce/customer/login" in account_after_logout.headers["Location"]

from flask import Flask

from smx_commerce import init_commerce


def create_client(tmp_path):
    db_file = tmp_path / "commerce.db"
    app = Flask(__name__)

    init_commerce(
        app,
        config={
            "database_url": f"sqlite+pysqlite:///{db_file.as_posix()}",
            "admin_token": "secret-admin-key",
            "flask_secret_key": "test-flask-secret",
            "payment_provider": "none",
            "email_provider": "none",
            "project_title": "Client Portal",
            "project_home_url": "/client-home",
            "logo_url": "/static/client/logo.png",
            "favicon_url": "/static/client/favicon.ico",
        },
        init_schema=True,
    )

    return app.test_client()


def seed_support_request(client, *, email, subject, order_public_id):
    response = client.post(
        "/commerce/support/submit",
        data={
            "customer_name": "Aoife Murphy",
            "customer_email": email,
            "order_public_id": order_public_id,
            "subject": subject,
            "message": "I paid yesterday and still cannot access the course.",
        },
    )
    assert response.status_code in {200, 302, 303}


def test_admin_support_inbox_search_filters_by_email_subject_and_order(tmp_path):
    client = create_client(tmp_path)

    seed_support_request(
        client,
        email="aoife@example.com",
        subject="Course access problem",
        order_public_id="ord_access_123",
    )
    seed_support_request(
        client,
        email="kwame@example.com",
        subject="Receipt question",
        order_public_id="ord_receipt_456",
    )

    email_response = client.get(
        "/commerce/admin/support?format=json&q=aoife@example.com",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert email_response.status_code == 200
    assert [row["customer_email"] for row in email_response.get_json()] == ["aoife@example.com"]

    subject_response = client.get(
        "/commerce/admin/support?format=json&q=Receipt",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert subject_response.status_code == 200
    assert [row["customer_email"] for row in subject_response.get_json()] == ["kwame@example.com"]

    order_response = client.get(
        "/commerce/admin/support?format=json&q=ord_access_123",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert order_response.status_code == 200
    assert [row["customer_email"] for row in order_response.get_json()] == ["aoife@example.com"]


def test_admin_support_inbox_shows_search_form(tmp_path):
    client = create_client(tmp_path)

    response = client.get(
        "/commerce/admin/support?q=aoife",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Search support" in html
    assert 'name="q"' in html
    assert 'value="aoife"' in html
    assert "Email, order ID, subject, issue type..." in html

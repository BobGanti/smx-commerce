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


def seed_support_request(client):
    response = client.post(
        "/commerce/support/submit",
        data={
            "customer_name": "Aoife Murphy",
            "customer_email": "aoife@example.com",
            "order_public_id": "ord_test_123",
            "subject": "I paid but did not receive access",
            "message": "I paid yesterday and still cannot access the course.",
        },
    )
    assert response.status_code in {200, 302, 303}

    inbox_response = client.get(
        "/commerce/admin/support?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert inbox_response.status_code == 200

    return inbox_response.get_json()[0]["public_id"]


def test_admin_support_save_reply_adds_admin_message_to_conversation(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/reply?format=json",
        data={
            "body": "Hi Aoife, thanks for contacting us. We are checking your order and will help restore access.",
        },
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["sender_type"] == "admin"
    assert data["body"] == "Hi Aoife, thanks for contacting us. We are checking your order and will help restore access."

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert detail_response.status_code == 200

    messages = detail_response.get_json()["messages"]

    assert [message["sender_type"] for message in messages] == ["customer", "admin"]
    assert messages[1]["body"] == "Hi Aoife, thanks for contacting us. We are checking your order and will help restore access."


def test_admin_support_save_reply_rejects_empty_body(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/reply?format=json",
        data={"body": "   "},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "body is required"


def test_admin_support_detail_shows_reviewed_reply_form_when_draft_exists(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    # Store a draft directly through the JSON reply endpoint path used by admins.
    save_response = client.post(
        f"/commerce/admin/support/{thread_public_id}/reply?format=json",
        data={
            "body": "Hi Aoife, we are reviewing your payment and access details.",
        },
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert save_response.status_code == 200

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert detail_response.status_code == 200

    html = detail_response.get_data(as_text=True)

    assert "Hi Aoife, we are reviewing your payment and access details." in html
    assert "admin" in html

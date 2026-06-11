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
            "subject": "Refund request",
            "message": "Please refund my order.",
        },
    )
    assert response.status_code in {200, 302, 303}

    inbox_response = client.get(
        "/commerce/admin/support?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert inbox_response.status_code == 200

    return inbox_response.get_json()[0]["public_id"]


def test_admin_support_save_reply_rejects_unsafe_completed_action_claim(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/reply?format=json",
        data={"body": "Hi Aoife, your refund has been issued."},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 400
    assert "unsafe completed-action claim" in response.get_json()["error"]

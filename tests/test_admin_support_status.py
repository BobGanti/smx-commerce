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


def test_admin_support_status_update_changes_thread_status(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/status?format=json",
        data={"status": "waiting"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["public_id"] == thread_public_id
    assert data["status"] == "waiting"

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert detail_response.status_code == 200
    assert detail_response.get_json()["thread"]["status"] == "waiting"


def test_admin_support_status_update_rejects_invalid_status(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/status?format=json",
        data={"status": "not-a-status"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 400
    assert "not-a-status" in response.get_json()["error"]


def test_admin_support_detail_shows_status_update_form(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.get(
        f"/commerce/admin/support/{thread_public_id}",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert f'action="/commerce/admin/support/{thread_public_id}/status"' in html
    assert 'name="status"' in html
    assert 'value="open"' in html
    assert 'value="waiting"' in html
    assert 'value="resolved"' in html
    assert "Update status" in html

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


def seed_support_request(client, subject):
    response = client.post(
        "/commerce/support/submit",
        data={
            "customer_name": "Aoife Murphy",
            "customer_email": "aoife@example.com",
            "order_public_id": "ord_test_123",
            "subject": subject,
            "message": "I paid yesterday and still cannot access the course.",
        },
    )
    assert response.status_code in {200, 302, 303}

    inbox_response = client.get(
        "/commerce/admin/support?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert inbox_response.status_code == 200

    rows = inbox_response.get_json()
    return next(row["public_id"] for row in rows if row["subject"] == subject)


def test_admin_support_priority_update_changes_thread_priority(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client, "Access issue")

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/priority?format=json",
        data={"priority": "urgent"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["public_id"] == thread_public_id
    assert data["priority"] == "urgent"

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert detail_response.status_code == 200
    assert detail_response.get_json()["thread"]["priority"] == "urgent"


def test_admin_support_priority_update_rejects_invalid_priority(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client, "Access issue")

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/priority?format=json",
        data={"priority": "extreme"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 400
    assert "extreme" in response.get_json()["error"]


def test_admin_support_inbox_filters_by_priority(tmp_path):
    client = create_client(tmp_path)
    urgent_id = seed_support_request(client, "Urgent access issue")
    normal_id = seed_support_request(client, "Normal question")

    priority_response = client.post(
        f"/commerce/admin/support/{urgent_id}/priority?format=json",
        data={"priority": "urgent"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert priority_response.status_code == 200

    response = client.get(
        "/commerce/admin/support?format=json&priority=urgent",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    rows = response.get_json()

    assert [row["public_id"] for row in rows] == [urgent_id]
    assert normal_id not in [row["public_id"] for row in rows]


def test_admin_support_detail_shows_priority_update_form(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client, "Access issue")

    response = client.get(
        f"/commerce/admin/support/{thread_public_id}",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert f'action="/commerce/admin/support/{thread_public_id}/priority"' in html
    assert 'name="priority"' in html
    assert 'value="low"' in html
    assert 'value="normal"' in html
    assert 'value="high"' in html
    assert 'value="urgent"' in html
    assert "Update priority" in html

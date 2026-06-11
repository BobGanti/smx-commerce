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
            "customer_email": f"{subject.lower().replace(' ', '.')}@example.com",
            "order_public_id": "",
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

    return next(row["public_id"] for row in inbox_response.get_json() if row["subject"] == subject)


def test_admin_support_inbox_shows_summary_counts(tmp_path):
    client = create_client(tmp_path)

    urgent_id = seed_support_request(client, "Urgent issue")
    waiting_id = seed_support_request(client, "Waiting issue")
    seed_support_request(client, "Normal issue")

    priority_response = client.post(
        f"/commerce/admin/support/{urgent_id}/priority?format=json",
        data={"priority": "urgent"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert priority_response.status_code == 200

    waiting_response = client.post(
        f"/commerce/admin/support/{waiting_id}/status?format=json",
        data={"status": "waiting"},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert waiting_response.status_code == 200

    response = client.get(
        "/commerce/admin/support",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Support inbox summary" in html
    assert "Open threads" in html
    assert "Waiting" in html
    assert "Urgent" in html
    assert "Resolved" in html
    assert "High" in html

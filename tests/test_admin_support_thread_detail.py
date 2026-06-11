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


def login(client):
    response = client.post(
        "/commerce/admin/login",
        json={"admin_token": "secret-admin-key"},
    )
    assert response.status_code == 200


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


def test_admin_support_thread_detail_shows_customer_conversation(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)
    login(client)

    response = client.get(
        f"/commerce/admin/support/{thread_public_id}",
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Client Portal ? Support Thread" in html
    assert "I paid but did not receive access" in html
    assert "Aoife Murphy" in html
    assert "aoife@example.com" in html
    assert "ord_test_123" in html
    assert "I paid yesterday and still cannot access the course." in html

    assert 'href="/commerce/admin/support"' in html
    assert "Back to support inbox" in html
    assert 'href="/client-home"' in html
    assert 'src="/static/client/logo.png"' in html
    assert 'alt="Client Portal logo"' in html
    assert 'rel="icon" href="/static/client/favicon.ico"' in html
    assert 'action="/commerce/admin/logout"' in html


def test_admin_support_thread_detail_returns_json_for_api_clients(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["thread"]["public_id"] == thread_public_id
    assert data["thread"]["customer_email"] == "aoife@example.com"
    assert data["messages"][0]["sender_type"] == "customer"
    assert data["messages"][0]["body"] == "I paid yesterday and still cannot access the course."

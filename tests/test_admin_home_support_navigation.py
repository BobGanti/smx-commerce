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
            "assets_dir": (tmp_path / "assets").as_posix(),
            "products_assets_dir": (tmp_path / "assets" / "products").as_posix(),
            "receipts_dir": (tmp_path / "assets" / "receipts").as_posix(),
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


def test_admin_home_links_to_support_inbox(tmp_path):
    client = create_client(tmp_path)
    login(client)

    response = client.get(
        "/commerce/admin",
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert 'href="/commerce/admin/support"' in html
    assert "Review support requests" in html
    assert "Triage customer messages and prepare AI-assisted reply drafts." in html

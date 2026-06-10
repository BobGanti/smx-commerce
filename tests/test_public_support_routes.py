from flask import Flask

from smx_commerce import create_commerce_blueprint
from smx_commerce.core import CommerceRuntime
from smx_commerce.support import SupportRepository


def create_client_and_runtime(tmp_path):
    db_file = tmp_path / "commerce.db"

    runtime = CommerceRuntime.from_mapping(
        {
            "database_url": f"sqlite+pysqlite:///{db_file.as_posix()}",
            "admin_token": "secret-admin-token",
            "flask_secret_key": "test-flask-secret",
            "payment_provider": "none",
            "email_provider": "none",
            "project_title": "Client Portal",
            "project_home_url": "/client-home",
            "logo_url": "/static/client/logo.png",
            "favicon_url": "/static/client/favicon.ico",
        }
    )

    app = Flask(__name__)
    app.register_blueprint(
        create_commerce_blueprint(
            runtime=runtime,
            init_schema=True,
        )
    )

    return app.test_client(), runtime


def test_public_support_form_uses_client_branding_and_navigation(tmp_path):
    client, _runtime = create_client_and_runtime(tmp_path)

    response = client.get("/commerce/support", headers={"Accept": "text/html"})

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "Client Portal · Support" in html
    assert "Customer support" in html
    assert 'href="/client-home"' in html
    assert "Back to Client Portal" in html
    assert 'src="/static/client/logo.png"' in html
    assert 'alt="Client Portal logo"' in html
    assert 'rel="icon" href="/static/client/favicon.ico"' in html

    assert 'method="post" action="/commerce/support/submit"' in html
    assert 'name="customer_name"' in html
    assert 'name="customer_email"' in html
    assert 'name="order_public_id"' in html
    assert 'name="subject"' in html
    assert 'name="message"' in html
    assert "Submit support request" in html

    assert 'href="/commerce/admin"' not in html
    assert "Open admin" not in html


def test_public_support_submit_creates_thread_and_customer_message(tmp_path):
    client, runtime = create_client_and_runtime(tmp_path)

    response = client.post(
        "/commerce/support/submit",
        data={
            "customer_name": "Aoife Murphy",
            "customer_email": "Aoife@example.com",
            "order_public_id": "ord_123",
            "subject": "I paid but did not receive access",
            "message": "I paid yesterday and still cannot access the course.",
        },
        content_type="application/x-www-form-urlencoded",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/commerce/support?submitted=1&thread_id=sup_" in response.headers["Location"]

    with runtime.session_scope() as session:
        repository = SupportRepository(session)
        threads = repository.list_threads()

        assert len(threads) == 1
        assert threads[0].customer_email == "aoife@example.com"
        assert threads[0].customer_name == "Aoife Murphy"
        assert threads[0].subject == "I paid but did not receive access"
        assert threads[0].order_public_id == "ord_123"

        detail = repository.get_thread_with_messages(threads[0].public_id)

    assert detail is not None
    assert len(detail.messages) == 1
    assert detail.messages[0].sender_type.value == "customer"
    assert detail.messages[0].body == "I paid yesterday and still cannot access the course."

def test_public_support_submit_error_preserves_branding_and_form_data(tmp_path):
    client, _runtime = create_client_and_runtime(tmp_path)

    response = client.post(
        "/commerce/support/submit",
        data={
            "customer_name": "Aoife Murphy",
            "customer_email": "Aoife@example.com",
            "subject": "Missing message",
            "message": "",
        },
        content_type="application/x-www-form-urlencoded",
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 400

    html = response.get_data(as_text=True)

    assert "Client Portal · Support" in html
    assert "Customer support" in html
    assert "body is required" in html
    assert "Aoife Murphy" in html
    assert "Aoife@example.com" in html
    assert "Missing message" in html
    assert 'href="/client-home"' in html
    assert "Back to Client Portal" in html
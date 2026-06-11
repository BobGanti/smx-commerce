from flask import Flask

from smx_commerce import init_commerce


class FakeAIClient:
    def run_agent_task(self, **kwargs):
        return {
            "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
            "tone": "helpful",
            "needs_human_review": True,
            "next_actions": ["Ask customer for order ID"],
        }


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
        ai_client=FakeAIClient(),
    )

    return app.test_client()


def seed_support_request(client):
    response = client.post(
        "/commerce/support/submit",
        data={
            "customer_name": "Aoife Murphy",
            "customer_email": "aoife@example.com",
            "order_public_id": "",
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


def test_saving_reviewed_reply_consumes_pending_ai_reply_draft(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    compose_response = client.post(
        f"/commerce/admin/support/{thread_public_id}/compose-reply?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert compose_response.status_code == 200

    before_save = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert before_save.status_code == 200
    assert "reply_draft" in before_save.get_json()["thread"]["metadata"]

    save_response = client.post(
        f"/commerce/admin/support/{thread_public_id}/reply?format=json",
        data={"body": "Hi Aoife, we are reviewing your payment and access details."},
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert save_response.status_code == 200

    after_save = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert after_save.status_code == 200

    metadata = after_save.get_json()["thread"]["metadata"]

    assert "reply_draft" not in metadata
    assert metadata["last_saved_reply"]["source"] == "admin_reviewed_reply"
    assert metadata["last_saved_reply"]["message_public_id"] == save_response.get_json()["public_id"]

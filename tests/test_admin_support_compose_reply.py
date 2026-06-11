from flask import Flask

from smx_commerce import init_commerce


class FakeAIClient:
    def __init__(self):
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)

        return {
            "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
            "tone": "helpful",
            "needs_human_review": True,
            "next_actions": ["Ask customer for order ID", "Verify payment before promising access"],
        }


def create_client(tmp_path, ai_client=None):
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
        ai_client=ai_client,
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


def test_admin_support_compose_reply_persists_ai_reply_draft(tmp_path):
    ai_client = FakeAIClient()
    client = create_client(tmp_path, ai_client=ai_client)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/compose-reply?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data == {
        "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
        "tone": "helpful",
        "needs_human_review": True,
        "next_actions": ["Ask customer for order ID", "Verify payment before promising access"],
    }

    assert len(ai_client.calls) == 3
    assert [call["agent_name"] for call in ai_client.calls] == [
        "commerce_support_reply_planner",
        "commerce_support_reply_composer",
        "commerce_support_reply_verifier",
    ]

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert detail_response.status_code == 200

    detail_data = detail_response.get_json()
    reply_draft = detail_data["thread"]["metadata"]["reply_draft"]

    assert reply_draft["tone"] == "helpful"
    assert reply_draft["needs_human_review"] is True
    assert reply_draft["body"].startswith("Hi Aoife")
    assert reply_draft["next_actions"] == [
        "Ask customer for order ID",
        "Verify payment before promising access",
    ]


def test_admin_support_compose_reply_requires_host_ai_client(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/compose-reply?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "ai_client is required to compose support reply drafts"
    }


def test_admin_support_detail_shows_reply_draft_button_and_result(tmp_path):
    ai_client = FakeAIClient()
    client = create_client(tmp_path, ai_client=ai_client)
    thread_public_id = seed_support_request(client)

    compose_response = client.post(
        f"/commerce/admin/support/{thread_public_id}/compose-reply?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert compose_response.status_code == 200

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert detail_response.status_code == 200

    html = detail_response.get_data(as_text=True)

    assert "Compose reply draft" in html
    assert "AI Reply Draft" in html
    assert "Draft only. Review before sending." in html
    assert "helpful" in html
    assert "Required" in html
    assert "Hi Aoife, thanks for reaching out." in html
    assert "Next actions: Ask customer for order ID, Verify payment before promising access" in html

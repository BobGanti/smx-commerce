from flask import Flask

from smx_commerce import init_commerce


class FakeAIClient:
    def __init__(self):
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "issue_type": "account_access_issue",
            "confidence": 0.97,
            "summary": "Customer paid but cannot access purchased content.",
            "should_escalate": False,
            "recommended_priority": "high",
            "missing_information": ["order_public_id"],
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


def test_admin_support_analyze_runs_ai_and_persists_triage(tmp_path):
    ai_client = FakeAIClient()
    client = create_client(tmp_path, ai_client=ai_client)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/analyze?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["issue_type"] == "account_access_issue"
    assert data["confidence"] == 0.97
    assert data["summary"] == "Customer paid but cannot access purchased content."
    assert data["should_escalate"] is False
    assert data["recommended_priority"] == "high"
    assert data["missing_information"] == ["order_public_id"]
    assert "usage_by_agent" in data
    assert "total_usage" in data
    assert data["total_usage"]["total_tokens"] == 0

    assert len(ai_client.calls) == 5
    assert {call["agent_name"] for call in ai_client.calls} == {
        "commerce_support_issue_classifier",
        "commerce_support_summary",
        "commerce_support_missing_information",
        "commerce_support_escalation_assessor",
        "commerce_support_priority_assessor",
    }

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert detail_response.status_code == 200

    detail_data = detail_response.get_json()
    triage = detail_data["thread"]["metadata"]["triage"]

    assert triage["issue_type"] == "account_access_issue"
    assert triage["confidence"] == 0.97
    assert triage["summary"] == "Customer paid but cannot access purchased content."
    assert triage["recommended_priority"] == "high"
    assert triage["missing_information"] == ["order_public_id"]


def test_admin_support_analyze_requires_host_ai_client(tmp_path):
    client = create_client(tmp_path)
    thread_public_id = seed_support_request(client)

    response = client.post(
        f"/commerce/admin/support/{thread_public_id}/analyze?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "ai_client is required to analyze support threads"
    }


def test_admin_support_detail_shows_ai_triage_button_and_result(tmp_path):
    ai_client = FakeAIClient()
    client = create_client(tmp_path, ai_client=ai_client)
    thread_public_id = seed_support_request(client)

    analyze_response = client.post(
        f"/commerce/admin/support/{thread_public_id}/analyze?format=json",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key"},
    )
    assert analyze_response.status_code == 200

    detail_response = client.get(
        f"/commerce/admin/support/{thread_public_id}",
        headers={"X-SMX-Commerce-Admin-Token": "secret-admin-key", "Accept": "text/html"},
    )

    assert detail_response.status_code == 200

    html = detail_response.get_data(as_text=True)

    assert "Run AI triage" in html
    assert "AI Triage" in html
    assert "account_access_issue" in html
    assert "Recommended priority" in html
    assert "high" in html
    assert "0.97" in html
    assert "Customer paid but cannot access purchased content." in html
    assert "Missing: order_public_id" in html

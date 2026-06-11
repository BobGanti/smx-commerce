from smx_commerce.support.composer import SupportReplyComposerService


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_support_reply_composer_service_drafts_admin_reviewable_reply():
    ai_client = FakeAIClient(
        {
            "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
            "tone": "helpful",
            "needs_human_review": True,
            "next_actions": ["Ask customer for order ID", "Verify payment before promising access"],
        }
    )

    service = SupportReplyComposerService(ai_client)

    draft = service.compose_reply(
        customer_name="Aoife Murphy",
        customer_email="aoife@example.com",
        subject="I paid but did not receive access",
        issue_type="account_access_issue",
        triage_summary="Customer paid but cannot access purchased content.",
        missing_information=["order_public_id"],
        customer_message="I paid yesterday and still cannot access the course.",
    )

    assert draft.body.startswith("Hi Aoife")
    assert draft.tone == "helpful"
    assert draft.needs_human_review is True
    assert draft.next_actions == [
        "Ask customer for order ID",
        "Verify payment before promising access",
    ]

    call = ai_client.calls[0]

    assert call["agent_name"] == "commerce_support_composer"
    assert call["context"]["customer_email"] == "aoife@example.com"
    assert call["context"]["issue_type"] == "account_access_issue"
    assert "Draft only. Do not send." in call["context"]["safety_rules"]


def test_support_reply_composer_service_uses_safe_fallback_when_ai_returns_empty_body():
    ai_client = FakeAIClient(
        {
            "body": "",
            "tone": "",
            "needs_human_review": True,
            "next_actions": "not-a-list",
        }
    )

    service = SupportReplyComposerService(ai_client)

    draft = service.compose_reply(
        customer_message="I paid yesterday and still cannot access the course.",
    )

    assert draft.body == "Thank you for contacting us. We are reviewing your request and will get back to you shortly."
    assert draft.tone == "professional"
    assert draft.needs_human_review is True
    assert draft.next_actions == []

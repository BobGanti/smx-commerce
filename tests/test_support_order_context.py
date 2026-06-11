from smx_commerce.support.composer import SupportReplyComposerService
from smx_commerce.support.triage import SupportTriageService


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_support_triage_includes_order_context_in_ai_call():
    ai_client = FakeAIClient(
        {
            "issue_type": "order_status",
            "confidence": 0.88,
            "summary": "Customer asks about an existing paid order.",
            "should_escalate": False,
            "missing_information": [],
        }
    )

    service = SupportTriageService(ai_client)

    service.triage(
        customer_message="What is happening with my order?",
        order_public_id="ord_123",
        order_context={
            "found": True,
            "public_id": "ord_123",
            "status": "paid",
            "product_slug": "ai-bootcamp",
            "amount_cents": 9900,
            "currency": "EUR",
        },
    )

    context = ai_client.calls[0]["context"]

    assert context["order_public_id"] == "ord_123"
    assert context["order_context"]["found"] is True
    assert context["order_context"]["status"] == "paid"
    assert context["order_context"]["currency"] == "EUR"


def test_support_reply_composer_includes_order_context_in_ai_call():
    ai_client = FakeAIClient(
        {
            "body": "Hi Aoife, your paid order is visible and we are checking access.",
            "tone": "helpful",
            "needs_human_review": True,
            "next_actions": ["Verify account access"],
        }
    )

    service = SupportReplyComposerService(ai_client)

    service.compose_reply(
        customer_name="Aoife Murphy",
        customer_email="aoife@example.com",
        customer_message="I paid but cannot access the course.",
        order_context={
            "found": True,
            "public_id": "ord_123",
            "status": "paid",
            "product_slug": "ai-bootcamp",
        },
    )

    context = ai_client.calls[0]["context"]

    assert context["order_context"]["found"] is True
    assert context["order_context"]["public_id"] == "ord_123"
    assert context["order_context"]["status"] == "paid"

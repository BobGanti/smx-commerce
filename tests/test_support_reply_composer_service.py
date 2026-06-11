from smx_commerce.support.composer import SupportReplyComposerService


REPLY_AGENT_NAMES = [
    "commerce_support_reply_planner",
    "commerce_support_reply_composer",
    "commerce_support_reply_verifier",
]


class FakeAIClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses[kwargs["agent_name"]]


def test_support_reply_composer_service_uses_narrow_reply_agents():
    ai_client = FakeAIClient(
        {
            "commerce_support_reply_planner": {
                "reply_strategy": "Ask for the order ID and explain that payment will be verified before access changes.",
                "facts_to_include": ["Customer says they paid yesterday"],
                "questions_to_ask": ["Please send your order ID"],
                "forbidden_claims": ["Do not say access has been restored"],
                "needs_human_review": True,
            },
            "commerce_support_reply_composer": {
                "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
                "tone": "helpful",
                "next_actions": ["Ask customer for order ID", "Verify payment before promising access"],
            },
            "commerce_support_reply_verifier": {
                "is_safe": True,
                "needs_revision": False,
                "concerns": [],
            },
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

    assert [call["agent_name"] for call in ai_client.calls] == REPLY_AGENT_NAMES

    planner_call = ai_client.calls[0]
    composer_call = ai_client.calls[1]
    verifier_call = ai_client.calls[2]

    assert "reply_plan" not in planner_call["context"]
    assert composer_call["context"]["reply_plan"]["questions_to_ask"] == ["Please send your order ID"]
    assert verifier_call["context"]["draft_reply"]["body"].startswith("Hi Aoife")
    assert "Draft only. Do not send." in planner_call["context"]["safety_rules"]


def test_support_reply_composer_service_uses_safe_fallback_when_composer_returns_empty_body():
    ai_client = FakeAIClient(
        {
            "commerce_support_reply_planner": {
                "reply_strategy": "",
                "facts_to_include": [],
                "questions_to_ask": [],
                "forbidden_claims": [],
                "needs_human_review": True,
            },
            "commerce_support_reply_composer": {
                "body": "",
                "tone": "",
                "next_actions": "not-a-list",
            },
            "commerce_support_reply_verifier": {
                "is_safe": True,
                "needs_revision": False,
                "concerns": [],
            },
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


def test_support_reply_composer_service_adds_verifier_concerns_to_next_actions():
    ai_client = FakeAIClient(
        {
            "commerce_support_reply_planner": {
                "reply_strategy": "Reply carefully.",
                "facts_to_include": [],
                "questions_to_ask": [],
                "forbidden_claims": ["Do not claim refund issued"],
                "needs_human_review": False,
            },
            "commerce_support_reply_composer": {
                "body": "Hi Aoife, we are reviewing your refund request.",
                "tone": "careful",
                "next_actions": [],
            },
            "commerce_support_reply_verifier": {
                "is_safe": False,
                "needs_revision": True,
                "concerns": ["Reply needs human review before saving"],
            },
        }
    )

    service = SupportReplyComposerService(ai_client)

    draft = service.compose_reply(
        customer_message="Please refund my order.",
    )

    assert draft.needs_human_review is True
    assert draft.next_actions == ["Verifier concern: Reply needs human review before saving"]

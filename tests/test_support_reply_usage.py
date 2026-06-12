from smx_commerce.ai import CommerceAIResult, CommerceAIUsage
from smx_commerce.support.composer import SupportReplyComposerService


REPLY_AGENT_NAMES = [
    "commerce_support_reply_planner",
    "commerce_support_reply_composer",
    "commerce_support_reply_verifier",
]


def test_support_reply_composer_service_aggregates_usage_by_agent():
    usage_by_name = {
        "commerce_support_reply_planner": CommerceAIUsage(provider="test", model="fake", input_tokens=2, output_tokens=3, total_tokens=5),
        "commerce_support_reply_composer": CommerceAIUsage(provider="test", model="fake", input_tokens=7, output_tokens=11, total_tokens=18),
        "commerce_support_reply_verifier": CommerceAIUsage(provider="test", model="fake", input_tokens=13, output_tokens=17, total_tokens=30),
    }

    data_by_name = {
        "commerce_support_reply_planner": {
            "reply_strategy": "Ask for order ID before promising access.",
            "facts_to_include": ["Customer says they paid yesterday"],
            "questions_to_ask": ["Please send your order ID"],
            "forbidden_claims": ["Do not say access has been restored"],
            "needs_human_review": True,
        },
        "commerce_support_reply_composer": {
            "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment.",
            "tone": "helpful",
            "next_actions": ["Ask customer for order ID"],
        },
        "commerce_support_reply_verifier": {
            "is_safe": True,
            "needs_revision": False,
            "concerns": [],
        },
    }

    class UsageAIClient:
        def run_agent_task(self, **kwargs):
            agent_name = kwargs["agent_name"]
            return CommerceAIResult(
                data=data_by_name[agent_name],
                usage=usage_by_name[agent_name],
            )

    service = SupportReplyComposerService(UsageAIClient())

    draft = service.compose_reply(
        customer_name="Aoife Murphy",
        customer_email="aoife@example.com",
        subject="Paid but no access",
        issue_type="account_access_issue",
        triage_summary="Customer paid but cannot access purchased content.",
        missing_information=["order_public_id"],
        customer_message="I paid yesterday and still cannot access the course.",
    )

    assert set(draft.usage_by_agent) == set(REPLY_AGENT_NAMES)
    assert draft.usage_by_agent["commerce_support_reply_planner"].input_tokens == 2
    assert draft.usage_by_agent["commerce_support_reply_verifier"].output_tokens == 17

    assert draft.total_usage.input_tokens == 22
    assert draft.total_usage.output_tokens == 31
    assert draft.total_usage.total_tokens == 53

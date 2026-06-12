from smx_commerce.ai import CommerceAIResult, CommerceAIUsage
from smx_commerce.support.triage import SupportTriageService


TRIAGE_AGENT_NAMES = [
    "commerce_support_issue_classifier",
    "commerce_support_summary",
    "commerce_support_missing_information",
    "commerce_support_escalation_assessor",
    "commerce_support_priority_assessor",
]


def test_support_triage_service_aggregates_usage_by_agent():
    usage_by_name = {
        "commerce_support_issue_classifier": CommerceAIUsage(provider="test", model="fake", input_tokens=1, output_tokens=2, total_tokens=3),
        "commerce_support_summary": CommerceAIUsage(provider="test", model="fake", input_tokens=4, output_tokens=5, total_tokens=9),
        "commerce_support_missing_information": CommerceAIUsage(provider="test", model="fake", input_tokens=7, output_tokens=8, total_tokens=15),
        "commerce_support_escalation_assessor": CommerceAIUsage(provider="test", model="fake", input_tokens=10, output_tokens=11, total_tokens=21),
        "commerce_support_priority_assessor": CommerceAIUsage(provider="test", model="fake", input_tokens=13, output_tokens=14, total_tokens=27),
    }

    class UsageAIClient:
        def run_agent_task(self, **kwargs):
            agent_name = kwargs["agent_name"]
            return CommerceAIResult(
                data={
                    "issue_type": "payment_problem",
                    "confidence": 0.91,
                    "summary": "Customer paid but cannot access the course.",
                    "should_escalate": False,
                    "recommended_priority": "high",
                    "missing_information": ["order_public_id"],
                },
                usage=usage_by_name[agent_name],
            )

    service = SupportTriageService(UsageAIClient())

    result = service.triage(
        customer_email="aoife@example.com",
        subject="Paid but no access",
        customer_message="I paid yesterday and still cannot access the course.",
    )

    assert set(result.usage_by_agent) == set(TRIAGE_AGENT_NAMES)
    assert result.usage_by_agent["commerce_support_issue_classifier"].input_tokens == 1
    assert result.usage_by_agent["commerce_support_priority_assessor"].output_tokens == 14

    assert result.total_usage.input_tokens == 35
    assert result.total_usage.output_tokens == 40
    assert result.total_usage.total_tokens == 75

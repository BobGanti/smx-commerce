from smx_commerce.support.triage import SupportTriageService


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_support_triage_service_calls_ai_client_with_allowed_taxonomy():
    ai_client = FakeAIClient(
        {
            "issue_type": "payment_problem",
            "confidence": 0.91,
            "summary": "Customer paid but cannot access the course.",
            "should_escalate": False,
            "recommended_priority": "high",
            "missing_information": ["order_public_id"],
        }
    )

    service = SupportTriageService(ai_client)

    result = service.triage(
        customer_email="aoife@example.com",
        order_public_id="",
        subject="I paid but did not receive access",
        customer_message="I paid yesterday and still cannot access the course.",
    )

    assert result.issue_type == "payment_problem"
    assert result.confidence == 0.91
    assert result.summary == "Customer paid but cannot access the course."
    assert result.should_escalate is False
    assert result.recommended_priority == "high"
    assert result.missing_information == ["order_public_id"]

    call = ai_client.calls[0]
    assert call["agent_name"] == "commerce_support_triage"
    assert "allowed_issue_types" in call["context"]
    assert "payment_problem" in call["context"]["allowed_issue_types"]


def test_support_triage_service_falls_back_when_ai_invents_issue_type():
    ai_client = FakeAIClient(
        {
            "issue_type": "access_issue",
            "confidence": 0.95,
            "summary": "Customer cannot access purchased content.",
            "should_escalate": False,
            "missing_information": [],
        }
    )

    service = SupportTriageService(ai_client)

    result = service.triage(
        customer_message="I paid yesterday but I still cannot access the course.",
    )

    assert result.issue_type == "general_question"
    assert result.confidence == 0.95
    assert result.summary == "Customer cannot access purchased content."



def test_support_triage_service_falls_back_to_high_priority_when_escalation_has_no_priority():
    ai_client = FakeAIClient(
        {
            "issue_type": "complaint",
            "confidence": 0.82,
            "summary": "Customer is angry and needs human review.",
            "should_escalate": True,
            "missing_information": [],
        }
    )

    service = SupportTriageService(ai_client)

    result = service.triage(
        customer_message="I have asked three times and nobody has helped me.",
    )

    assert result.issue_type == "complaint"
    assert result.should_escalate is True
    assert result.recommended_priority == "high"

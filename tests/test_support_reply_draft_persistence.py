from smx_commerce.core.db import create_schema, make_engine, make_session_factory
from smx_commerce.support import SupportAnalysisService, SupportRepository


class FakeAIClient:
    def __init__(self):
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)

        if kwargs["agent_name"] == "commerce_support_reply_composer":
            return {
                "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
                "tone": "helpful",
                "needs_human_review": True,
                "next_actions": ["Ask customer for order ID", "Verify payment before promising access"],
            }

        return {
            "issue_type": "account_access_issue",
            "confidence": 0.94,
            "summary": "Customer paid but cannot access purchased content.",
            "should_escalate": False,
            "missing_information": ["order_public_id"],
        }


def _session_factory():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return make_session_factory(engine)


def test_support_analysis_service_composes_and_persists_reply_draft():
    Session = _session_factory()
    ai_client = FakeAIClient()

    with Session() as session:
        repository = SupportRepository(session)
        thread = repository.create_thread(
            customer_email="aoife@example.com",
            customer_name="Aoife Murphy",
            subject="I paid but did not receive access",
        )
        repository.add_customer_message(
            thread.public_id,
            body="I paid yesterday and still cannot access the course.",
        )

        service = SupportAnalysisService(
            session=session,
            ai_client=ai_client,
        )

        service.triage_thread(thread.public_id)
        draft = service.compose_reply_draft(thread.public_id)

        assert draft.body.startswith("Hi Aoife")
        assert draft.tone == "helpful"
        assert draft.needs_human_review is True
        assert draft.next_actions == [
            "Ask customer for order ID",
            "Verify payment before promising access",
        ]

        loaded = repository.get_by_public_id(thread.public_id)

        assert loaded is not None
        assert loaded.metadata["reply_draft"] == {
            "body": "Hi Aoife, thanks for reaching out. Please send your order ID so we can verify the payment and help restore access.",
            "tone": "helpful",
            "needs_human_review": True,
            "next_actions": ["Ask customer for order ID", "Verify payment before promising access"],
        }

        assert [call["agent_name"] for call in ai_client.calls] == [
            "commerce_support_issue_classifier",
            "commerce_support_summary",
            "commerce_support_missing_information",
            "commerce_support_escalation_assessor",
            "commerce_support_priority_assessor",
            "commerce_support_reply_planner",
            "commerce_support_reply_composer",
            "commerce_support_reply_verifier",
        ]

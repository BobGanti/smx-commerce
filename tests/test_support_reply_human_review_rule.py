from smx_commerce.core.db import create_schema, make_engine, make_session_factory
from smx_commerce.support.repository import SupportRepository
from smx_commerce.support.service import SupportAnalysisService


class FakeAIClient:
    def __init__(self):
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        agent_name = kwargs["agent_name"]

        if agent_name == "commerce_support_issue_classifier":
            return {
                "issue_type": "account_access_issue",
                "confidence": 0.93,
            }

        if agent_name == "commerce_support_summary":
            return {
                "summary": "Customer paid but cannot access the course.",
            }

        if agent_name == "commerce_support_missing_information":
            return {
                "missing_information": ["order_public_id"],
            }

        if agent_name == "commerce_support_escalation_assessor":
            return {
                "should_escalate": True,
            }

        if agent_name == "commerce_support_priority_assessor":
            return {
                "recommended_priority": "high",
            }

        if agent_name == "commerce_support_reply_planner":
            return {
                "reply_strategy": "Ask for the order ID.",
                "facts_to_include": ["Customer says they paid yesterday"],
                "questions_to_ask": ["Please send your order ID"],
                "forbidden_claims": ["Do not say access has been restored"],
                "needs_human_review": False,
            }

        if agent_name == "commerce_support_reply_composer":
            return {
                "body": "Hello Aoife, please send your order ID so we can verify your payment.",
                "tone": "supportive",
                "next_actions": ["Ask customer for order ID"],
            }

        if agent_name == "commerce_support_reply_verifier":
            return {
                "is_safe": True,
                "needs_revision": False,
                "concerns": [],
            }

        raise AssertionError(f"Unexpected agent: {agent_name}")


def _session_factory():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return make_session_factory(engine)


def test_high_or_escalated_triage_forces_reply_draft_human_review():
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

        assert draft.needs_human_review is True

        loaded = repository.get_by_public_id(thread.public_id)
        assert loaded is not None
        assert loaded.metadata["reply_draft"]["needs_human_review"] is True

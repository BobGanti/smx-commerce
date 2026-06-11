from smx_commerce.core.db import create_schema, make_engine, make_session_factory
from smx_commerce.support import SupportAnalysisService, SupportRepository


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run_agent_task(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _session_factory():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return make_session_factory(engine)


def test_support_analysis_service_triages_thread_and_persists_result():
    Session = _session_factory()

    ai_client = FakeAIClient(
        {
            "issue_type": "account_access_issue",
            "confidence": 0.93,
            "summary": "Customer paid but cannot access the course.",
            "should_escalate": False,
            "missing_information": ["order_public_id"],
        }
    )

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

        result = service.triage_thread(thread.public_id)

        assert result.issue_type == "account_access_issue"
        assert result.confidence == 0.93
        assert result.summary == "Customer paid but cannot access the course."

        loaded = repository.get_by_public_id(thread.public_id)

        assert loaded is not None
        assert loaded.issue_type == "account_access_issue"
        assert loaded.metadata["triage"]["should_escalate"] is False
        assert loaded.metadata["triage"]["missing_information"] == ["order_public_id"]

        assert len(ai_client.calls) == 1
        assert ai_client.calls[0]["context"]["customer_email"] == "aoife@example.com"
        assert ai_client.calls[0]["context"]["subject"] == "I paid but did not receive access"
        assert ai_client.calls[0]["context"]["customer_message"] == "I paid yesterday and still cannot access the course."


def test_support_analysis_service_requires_existing_thread():
    Session = _session_factory()

    ai_client = FakeAIClient(
        {
            "issue_type": "general_question",
            "confidence": 0.5,
            "summary": "General support question.",
            "should_escalate": False,
            "missing_information": [],
        }
    )

    with Session() as session:
        service = SupportAnalysisService(
            session=session,
            ai_client=ai_client,
        )

        try:
            service.triage_thread("sup_missing")
        except ValueError as exc:
            assert "support thread not found" in str(exc)
        else:
            raise AssertionError("Expected ValueError for missing thread")

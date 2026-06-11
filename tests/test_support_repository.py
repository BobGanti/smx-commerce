from smx_commerce.core.db import create_schema, make_engine, make_session_factory
from smx_commerce.support import SupportRepository, SupportThreadStatus


def _session_factory():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return make_session_factory(engine)


def test_support_repository_creates_thread():
    Session = _session_factory()

    with Session() as session:
        repository = SupportRepository(session)

        thread = repository.create_thread(
            customer_email="Aoife@example.com",
            customer_name="Aoife Murphy",
            subject="I paid but did not receive access",
            order_public_id="ord_123",
            issue_type="payment_problem",
            metadata={"source_page": "/commerce/support"},
        )

        assert thread.public_id.startswith("sup_")
        assert thread.customer_email == "aoife@example.com"
        assert thread.customer_name == "Aoife Murphy"
        assert thread.subject == "I paid but did not receive access"
        assert thread.order_public_id == "ord_123"
        assert thread.issue_type == "payment_problem"
        assert thread.status == SupportThreadStatus.OPEN
        assert thread.metadata == {"source_page": "/commerce/support"}


def test_support_repository_adds_customer_message():
    Session = _session_factory()

    with Session() as session:
        repository = SupportRepository(session)
        thread = repository.create_thread(
            customer_email="customer@example.com",
            customer_name="Customer One",
            subject="Where is my order?",
        )

        message = repository.add_customer_message(
            thread.public_id,
            body="I paid yesterday and need access.",
        )

        assert message.public_id.startswith("supmsg_")
        assert message.thread_public_id == thread.public_id
        assert message.sender_type.value == "customer"
        assert message.sender_name == "Customer One"
        assert message.sender_email == "customer@example.com"
        assert message.body == "I paid yesterday and need access."


def test_support_repository_lists_threads():
    Session = _session_factory()

    with Session() as session:
        repository = SupportRepository(session)
        first = repository.create_thread(
            customer_email="first@example.com",
            subject="First issue",
        )
        second = repository.create_thread(
            customer_email="second@example.com",
            subject="Second issue",
        )

        threads = repository.list_threads()

        assert [thread.public_id for thread in threads] == [second.public_id, first.public_id]


def test_support_repository_gets_thread_with_messages():
    Session = _session_factory()

    with Session() as session:
        repository = SupportRepository(session)
        thread = repository.create_thread(
            customer_email="buyer@example.com",
            subject="Refund request",
        )
        repository.add_customer_message(thread.public_id, body="Please review my refund request.")
        repository.add_customer_message(thread.public_id, body="The order number is ord_123.")

        detail = repository.get_thread_with_messages(thread.public_id)

        assert detail is not None
        assert detail.thread.public_id == thread.public_id
        assert [message.body for message in detail.messages] == [
            "Please review my refund request.",
            "The order number is ord_123.",
        ]



def test_support_repository_records_triage_result():
    Session = _session_factory()

    with Session() as session:
        repository = SupportRepository(session)
        thread = repository.create_thread(
            customer_email="buyer@example.com",
            subject="I paid but did not receive access",
        )

        updated = repository.record_triage_result(
            thread.public_id,
            issue_type="account_access_issue",
            confidence=0.88,
            summary="Customer paid but cannot access purchased content.",
            should_escalate=False,
            missing_information=["order_public_id"],
        )

        assert updated.issue_type == "account_access_issue"
        assert updated.metadata["triage"] == {
            "issue_type": "account_access_issue",
            "confidence": 0.88,
            "summary": "Customer paid but cannot access purchased content.",
            "should_escalate": False,
            "missing_information": ["order_public_id"],
        }

        loaded = repository.get_by_public_id(thread.public_id)

        assert loaded is not None
        assert loaded.issue_type == "account_access_issue"
        assert loaded.metadata["triage"]["summary"] == "Customer paid but cannot access purchased content."

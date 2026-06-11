from __future__ import annotations

from sqlalchemy.orm import Session

from smx_commerce.ai import CommerceAIClient
from smx_commerce.support.repository import SupportRepository
from smx_commerce.support.triage import SupportTriageResult, SupportTriageService


class SupportAnalysisService:
    def __init__(self, *, session: Session, ai_client: CommerceAIClient):
        self.repository = SupportRepository(session)
        self.triage_service = SupportTriageService(ai_client)

    def triage_thread(self, thread_public_id: str) -> SupportTriageResult:
        detail = self.repository.get_thread_with_messages(thread_public_id)

        if detail is None:
            raise ValueError(f"support thread not found: {thread_public_id}")

        customer_messages = [
            message
            for message in detail.messages
            if message.sender_type.value == "customer"
        ]

        if not customer_messages:
            raise ValueError("support thread has no customer message to triage")

        latest_customer_message = customer_messages[-1]

        result = self.triage_service.triage(
            customer_email=detail.thread.customer_email,
            order_public_id=detail.thread.order_public_id,
            subject=detail.thread.subject,
            customer_message=latest_customer_message.body,
        )

        self.repository.record_triage_result(
            detail.thread.public_id,
            issue_type=result.issue_type,
            confidence=result.confidence,
            summary=result.summary,
            should_escalate=result.should_escalate,
            missing_information=result.missing_information,
        )

        return result

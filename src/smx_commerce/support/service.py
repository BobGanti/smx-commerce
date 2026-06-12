from __future__ import annotations

from sqlalchemy.orm import Session

from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.ai import CommerceAIClient
from smx_commerce.support.repository import SupportRepository
from smx_commerce.support.composer import SupportReplyComposerService, SupportReplyDraft
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

        order_context = self._order_context_for_thread(detail.thread.order_public_id)

        result = self.triage_service.triage(
            customer_email=detail.thread.customer_email,
            order_public_id=detail.thread.order_public_id,
            subject=detail.thread.subject,
            customer_message=latest_customer_message.body,
            order_context=order_context,
        )

        self.repository.record_triage_result(
            detail.thread.public_id,
            issue_type=result.issue_type,
            confidence=result.confidence,
            summary=result.summary,
            should_escalate=result.should_escalate,
            missing_information=result.missing_information,
            recommended_priority=result.recommended_priority,
        )

        return result

    def compose_reply_draft(self, thread_public_id: str) -> SupportReplyDraft:
        detail = self.repository.get_thread_with_messages(thread_public_id)

        if detail is None:
            raise ValueError(f"support thread not found: {thread_public_id}")

        customer_messages = [
            message
            for message in detail.messages
            if message.sender_type.value == "customer"
        ]

        if not customer_messages:
            raise ValueError("support thread has no customer message to compose from")

        latest_customer_message = customer_messages[-1]
        triage = detail.thread.metadata.get("triage", {})

        composer = SupportReplyComposerService(self.triage_service.ai_client)
        order_context = self._order_context_for_thread(detail.thread.order_public_id)

        draft = composer.compose_reply(
            customer_email=detail.thread.customer_email,
            customer_name=detail.thread.customer_name,
            subject=detail.thread.subject,
            issue_type=detail.thread.issue_type,
            triage_summary=str(triage.get("summary", "")),
            missing_information=triage.get("missing_information", []),
            customer_message=latest_customer_message.body,
            order_context=order_context,
        )

        needs_human_review = _requires_human_review_from_triage(
            triage=triage,
            thread_priority=detail.thread.priority.value,
            draft_needs_human_review=draft.needs_human_review,
        )

        final_draft = SupportReplyDraft(
            body=draft.body,
            tone=draft.tone,
            needs_human_review=needs_human_review,
            next_actions=draft.next_actions,
        )

        self.repository.record_reply_draft(
            detail.thread.public_id,
            body=final_draft.body,
            tone=final_draft.tone,
            needs_human_review=final_draft.needs_human_review,
            next_actions=final_draft.next_actions,
        )

        return final_draft

    def _order_context_for_thread(self, order_public_id: str) -> dict[str, object]:
        order_id = (order_public_id or "").strip()
        if not order_id:
            return {}

        order = OrderRepository(self.repository.session).get_by_public_id(order_id)
        if order is None:
            return {
                "found": False,
                "public_id": order_id,
            }

        return {
            "found": True,
            "public_id": order.public_id,
            "status": order.status.value,
            "product_slug": order.product_slug,
            "price_code": order.price_code,
            "buyer_email": order.buyer.email,
            "buyer_name": order.buyer.full_name,
            "amount_cents": order.amount.amount_cents,
            "currency": order.amount.currency,
            "payment_provider": order.payment_provider,
            "payment_reference_present": bool(order.payment_reference),
            "notes": order.notes,
        }


def _requires_human_review_from_triage(
    *,
    triage: dict,
    thread_priority: str,
    draft_needs_human_review: bool,
) -> bool:
    if draft_needs_human_review:
        return True

    if bool(triage.get("should_escalate", False)):
        return True

    recommended_priority = str(triage.get("recommended_priority", "")).strip().lower()
    if recommended_priority in {"high", "urgent"}:
        return True

    normalized_thread_priority = str(thread_priority or "").strip().lower()
    if normalized_thread_priority in {"high", "urgent"}:
        return True

    return False


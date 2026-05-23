from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from smx_commerce.checkout.objects import Order
from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.payments.objects import PaymentEvent, PaymentEventStatus
from smx_commerce.payments.repository import PaymentEventRepository


@dataclass(frozen=True)
class PaymentProcessingResult:
    event: PaymentEvent
    order: Order | None
    idempotent: bool = False


class PaymentWebhookService:
    def __init__(self, session: Session):
        self.session = session
        self.events = PaymentEventRepository(session)
        self.orders = OrderRepository(session)

    def process_order_paid(
        self,
        *,
        provider: str,
        provider_event_id: str,
        event_type: str,
        order_public_id: str,
        payment_reference: str,
        payload: dict[str, Any] | None = None,
    ) -> PaymentProcessingResult:
        event = self.events.create_received(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
        )

        if event.status == PaymentEventStatus.PROCESSED:
            order = self.orders.get_by_public_id(event.order_public_id) if event.order_public_id else None
            return PaymentProcessingResult(event=event, order=order, idempotent=True)

        order = self.orders.mark_paid(order_public_id, payment_reference=payment_reference)

        processed_event = self.events.mark_processed(
            provider=provider,
            provider_event_id=provider_event_id,
            order_public_id=order.public_id,
            payment_reference=payment_reference,
        )

        return PaymentProcessingResult(event=processed_event, order=order, idempotent=False)

    def ignore_event(
        self,
        *,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        reason: str = "",
    ) -> PaymentProcessingResult:
        event = self.events.create_received(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
        )

        if event.status in {PaymentEventStatus.PROCESSED, PaymentEventStatus.IGNORED}:
            return PaymentProcessingResult(event=event, order=None, idempotent=True)

        ignored_event = self.events.mark_ignored(
            provider=provider,
            provider_event_id=provider_event_id,
            reason=reason,
        )

        return PaymentProcessingResult(event=ignored_event, order=None, idempotent=False)

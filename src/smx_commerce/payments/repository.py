from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.payments.models import PaymentEventRow, utc_now
from smx_commerce.payments.objects import PaymentEvent, PaymentEventStatus


class PaymentEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_received(
        self,
        *,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> PaymentEvent:
        provider = validate_required_text(provider, "provider").lower()
        provider_event_id = validate_required_text(provider_event_id, "provider_event_id")
        event_type = validate_required_text(event_type, "event_type")

        existing = self.get(provider, provider_event_id)
        if existing is not None:
            return existing

        row = PaymentEventRow(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            status=PaymentEventStatus.RECEIVED.value,
            payload_json=dict(payload or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_domain(row)

    def get(self, provider: str, provider_event_id: str) -> PaymentEvent | None:
        provider = validate_required_text(provider, "provider").lower()
        provider_event_id = validate_required_text(provider_event_id, "provider_event_id")

        row = self.session.execute(
            select(PaymentEventRow).where(
                PaymentEventRow.provider == provider,
                PaymentEventRow.provider_event_id == provider_event_id,
            )
        ).scalar_one_or_none()

        return self._to_domain(row) if row is not None else None

    def list(
        self,
        *,
        provider: str | None = None,
        status: PaymentEventStatus | str | None = None,
    ) -> list[PaymentEvent]:
        statement = select(PaymentEventRow)

        if provider is not None:
            statement = statement.where(PaymentEventRow.provider == provider.lower())

        if status is not None:
            event_status = status if isinstance(status, PaymentEventStatus) else PaymentEventStatus(status)
            statement = statement.where(PaymentEventRow.status == event_status.value)

        statement = statement.order_by(PaymentEventRow.id.desc())

        rows = self.session.execute(statement).scalars().all()

        return [self._to_domain(row) for row in rows]

    def mark_processed(
        self,
        *,
        provider: str,
        provider_event_id: str,
        order_public_id: str,
        payment_reference: str,
    ) -> PaymentEvent:
        row = self._get_row_or_raise(provider, provider_event_id)

        row.status = PaymentEventStatus.PROCESSED.value
        row.order_public_id = validate_required_text(order_public_id, "order_public_id")
        row.payment_reference = validate_required_text(payment_reference, "payment_reference")
        row.error_message = ""
        row.processed_at = utc_now()

        self.session.flush()

        return self._to_domain(row)

    def mark_ignored(
        self,
        *,
        provider: str,
        provider_event_id: str,
        reason: str = "",
    ) -> PaymentEvent:
        row = self._get_row_or_raise(provider, provider_event_id)

        row.status = PaymentEventStatus.IGNORED.value
        row.error_message = reason or ""
        row.processed_at = utc_now()

        self.session.flush()

        return self._to_domain(row)

    def _get_row_or_raise(self, provider: str, provider_event_id: str) -> PaymentEventRow:
        provider = validate_required_text(provider, "provider").lower()
        provider_event_id = validate_required_text(provider_event_id, "provider_event_id")

        row = self.session.execute(
            select(PaymentEventRow).where(
                PaymentEventRow.provider == provider,
                PaymentEventRow.provider_event_id == provider_event_id,
            )
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"payment event not found: {provider}/{provider_event_id}")

        return row

    @staticmethod
    def _to_domain(row: PaymentEventRow) -> PaymentEvent:
        return PaymentEvent(
            provider=row.provider,
            provider_event_id=row.provider_event_id,
            event_type=row.event_type,
            status=PaymentEventStatus(row.status),
            order_public_id=row.order_public_id,
            payment_reference=row.payment_reference,
            payload=dict(row.payload_json or {}),
            error_message=row.error_message or "",
        )

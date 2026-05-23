from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from smx_commerce.core.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentEventRow(Base):
    __tablename__ = "smx_payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_smx_payment_event_provider_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="received")

    order_public_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

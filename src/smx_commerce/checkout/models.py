from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from smx_commerce.core.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderRow(Base):
    __tablename__ = "smx_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)

    product_slug: Mapped[str] = mapped_column(String(140), index=True, nullable=False)
    price_code: Mapped[str] = mapped_column(String(120), nullable=False)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="pending")

    buyer_full_name: Mapped[str] = mapped_column(String(220), nullable=False)
    buyer_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    buyer_phone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    buyer_company: Mapped[str] = mapped_column(String(220), nullable=False, default="")
    buyer_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    payment_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="stripe")
    payment_reference: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

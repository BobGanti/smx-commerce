from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from smx_commerce.core.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SupportThreadRow(Base):
    __tablename__ = "smx_commerce_support_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    customer_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(220), nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    order_public_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False, default="")

    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="normal")
    issue_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False, default="general_question")
    source: Mapped[str] = mapped_column(String(40), index=True, nullable=False, default="public_support")

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class SupportMessageRow(Base):
    __tablename__ = "smx_commerce_support_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    thread_public_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("smx_commerce_support_threads.public_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    sender_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    sender_name: Mapped[str] = mapped_column(String(220), nullable=False, default="")
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

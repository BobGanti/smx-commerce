from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from smx_commerce.core.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CategoryRow(Base):
    __tablename__ = "smx_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="active")

    parent_slug: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ProductRow(Base):
    __tablename__ = "smx_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True, default="generic")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="draft")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ProductCategoryRow(Base):
    __tablename__ = "smx_product_categories"
    __table_args__ = (
        UniqueConstraint("product_slug", "category_slug", name="uq_smx_product_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    product_slug: Mapped[str] = mapped_column(
        String(140),
        ForeignKey("smx_products.slug", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_slug: Mapped[str] = mapped_column(
        String(140),
        ForeignKey("smx_categories.slug", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class ProductPriceRow(Base):
    __tablename__ = "smx_product_prices"
    __table_args__ = (
        UniqueConstraint("product_slug", "code", name="uq_smx_product_price_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    product_slug: Mapped[str] = mapped_column(
        String(140),
        ForeignKey("smx_products.slug", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(180), nullable=False)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="active")
    billing_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="one_time")
    billing_interval: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

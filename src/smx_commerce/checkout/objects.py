from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from smx_commerce.catalog.objects import Money, validate_required_text, validate_slug


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REFUNDED = "refunded"


def validate_email(value: str) -> str:
    email = validate_required_text(value, "email").lower()

    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("email must be valid")

    return email


@dataclass
class BuyerDetails:
    full_name: str
    email: str
    phone: str = ""
    company: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        self.full_name = validate_required_text(self.full_name, "full_name")
        self.email = validate_email(self.email)
        self.phone = (self.phone or "").strip()
        self.company = (self.company or "").strip()
        self.metadata = dict(self.metadata or {})


@dataclass
class Order:
    public_id: str
    product_slug: str
    price_code: str
    buyer: BuyerDetails
    amount: Money
    status: OrderStatus = OrderStatus.PENDING
    payment_provider: str = "stripe"
    payment_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.product_slug = validate_slug(self.product_slug, "product_slug")
        self.price_code = validate_slug(self.price_code, "price_code")

        if not isinstance(self.buyer, BuyerDetails):
            raise TypeError("buyer must be a BuyerDetails instance")

        if not isinstance(self.amount, Money):
            raise TypeError("amount must be a Money instance")

        if not isinstance(self.status, OrderStatus):
            self.status = OrderStatus(self.status)

        self.payment_provider = validate_required_text(self.payment_provider, "payment_provider")
        self.metadata = dict(self.metadata or {})

    @property
    def is_paid(self) -> bool:
        return self.status == OrderStatus.PAID

    @property
    def is_pending(self) -> bool:
        return self.status == OrderStatus.PENDING

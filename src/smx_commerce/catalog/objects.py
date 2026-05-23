from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import re
from typing import Any


_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CategoryStatus(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class PriceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class ProductKind(str, Enum):
    GENERIC = "generic"
    DIGITAL = "digital"
    SERVICE = "service"
    EVENT = "event"
    PHYSICAL = "physical"


class BillingMode(str, Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"


def validate_slug(value: str, field_name: str = "slug") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")

    normalized = value.strip().lower()

    if not _SLUG_PATTERN.match(normalized):
        raise ValueError(
            f"{field_name} must use lowercase letters, numbers, and single hyphens only"
        )

    return normalized


def validate_required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


@dataclass(frozen=True)
class Money:
    amount_cents: int
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if not isinstance(self.amount_cents, int):
            raise TypeError("amount_cents must be an integer")

        if self.amount_cents < 0:
            raise ValueError("amount_cents cannot be negative")

        currency = self.currency.strip().upper()

        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter ISO-style code")

        object.__setattr__(self, "currency", currency)

    @classmethod
    def from_major(cls, amount: str | int | float | Decimal, currency: str = "EUR") -> "Money":
        decimal_amount = Decimal(str(amount))
        cents = int((decimal_amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return cls(amount_cents=cents, currency=currency)

    def major(self) -> Decimal:
        return Decimal(self.amount_cents) / Decimal("100")


@dataclass
class Category:
    slug: str
    name: str
    description: str = ""
    status: CategoryStatus = CategoryStatus.ACTIVE
    parent_slug: str | None = None
    sort_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.slug = validate_slug(self.slug)
        self.name = validate_required_text(self.name, "name")

        if self.parent_slug:
            self.parent_slug = validate_slug(self.parent_slug, "parent_slug")

        if not isinstance(self.status, CategoryStatus):
            self.status = CategoryStatus(self.status)

    @property
    def is_public(self) -> bool:
        return self.status == CategoryStatus.ACTIVE


@dataclass
class ProductPrice:
    code: str
    label: str
    amount: Money
    status: PriceStatus = PriceStatus.ACTIVE
    billing_mode: BillingMode = BillingMode.ONE_TIME
    billing_interval: str | None = None
    sort_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.code = validate_slug(self.code, "code")
        self.label = validate_required_text(self.label, "label")

        if not isinstance(self.amount, Money):
            raise TypeError("amount must be a Money instance")

        if not isinstance(self.status, PriceStatus):
            self.status = PriceStatus(self.status)

        if not isinstance(self.billing_mode, BillingMode):
            self.billing_mode = BillingMode(self.billing_mode)

        if self.billing_mode == BillingMode.RECURRING and not self.billing_interval:
            raise ValueError("billing_interval is required for recurring prices")

        if self.billing_mode == BillingMode.ONE_TIME and self.billing_interval:
            raise ValueError("billing_interval is only valid for recurring prices")

    @property
    def is_active(self) -> bool:
        return self.status == PriceStatus.ACTIVE


@dataclass
class Product:
    slug: str
    name: str
    kind: ProductKind = ProductKind.GENERIC
    summary: str = ""
    description: str = ""
    status: ProductStatus = ProductStatus.DRAFT
    category_slugs: list[str] = field(default_factory=list)
    sort_order: int = 0
    prices: list[ProductPrice] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.slug = validate_slug(self.slug)
        self.name = validate_required_text(self.name, "name")

        if not isinstance(self.kind, ProductKind):
            self.kind = ProductKind(self.kind)

        if not isinstance(self.status, ProductStatus):
            self.status = ProductStatus(self.status)

        self.category_slugs = [
            validate_slug(category_slug, "category_slug")
            for category_slug in self.category_slugs
        ]

        if not isinstance(self.sort_order, int):
            self.sort_order = int(self.sort_order)

        for price in self.prices:
            if not isinstance(price, ProductPrice):
                raise TypeError("prices must contain ProductPrice instances")

    @property
    def is_public(self) -> bool:
        return self.status == ProductStatus.ACTIVE

    @property
    def active_prices(self) -> list[ProductPrice]:
        return sorted(
            [price for price in self.prices if price.is_active],
            key=lambda price: price.sort_order,
        )

    @property
    def is_purchasable(self) -> bool:
        return self.is_public and bool(self.active_prices)

    @property
    def primary_price(self) -> ProductPrice | None:
        active_prices = self.active_prices
        return active_prices[0] if active_prices else None

    def add_price(self, price: ProductPrice) -> None:
        if not isinstance(price, ProductPrice):
            raise TypeError("price must be a ProductPrice instance")
        self.prices.append(price)

    def activate(self) -> None:
        if self.status == ProductStatus.ARCHIVED:
            raise ValueError("archived products cannot be activated")
        self.status = ProductStatus.ACTIVE

    def pause(self) -> None:
        if self.status == ProductStatus.ARCHIVED:
            raise ValueError("archived products cannot be paused")
        self.status = ProductStatus.PAUSED

    def archive(self) -> None:
        self.status = ProductStatus.ARCHIVED

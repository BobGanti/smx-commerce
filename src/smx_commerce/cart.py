from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from smx_commerce.catalog.objects import validate_required_text, validate_slug


CART_SESSION_KEY = "smx_commerce_cart"


def _clean_quantity(value: Any) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise ValueError("quantity must be a whole number") from None

    if quantity < 1:
        raise ValueError("quantity must be at least 1")

    return quantity


@dataclass(frozen=True)
class CartItemSnapshot:
    product_slug: str
    price_code: str
    quantity: int
    product_name: str
    price_label: str
    currency: str
    amount_cents: int
    main_image_url: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_slug", validate_slug(self.product_slug, "product_slug"))
        object.__setattr__(self, "price_code", validate_slug(self.price_code, "price_code"))
        object.__setattr__(self, "quantity", _clean_quantity(self.quantity))
        object.__setattr__(self, "product_name", validate_required_text(self.product_name, "product_name"))
        object.__setattr__(self, "price_label", validate_required_text(self.price_label, "price_label"))

        currency = validate_required_text(self.currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter ISO-style code")
        object.__setattr__(self, "currency", currency)

        if not isinstance(self.amount_cents, int):
            raise TypeError("amount_cents must be an integer")
        if self.amount_cents < 0:
            raise ValueError("amount_cents cannot be negative")

        object.__setattr__(self, "main_image_url", (self.main_image_url or "").strip())

    @property
    def item_key(self) -> str:
        return build_cart_item_key(self.product_slug, self.price_code)

    @property
    def line_total_cents(self) -> int:
        return self.amount_cents * self.quantity

    def to_session_dict(self) -> dict[str, Any]:
        return {
            "product_slug": self.product_slug,
            "price_code": self.price_code,
            "quantity": self.quantity,
            "product_name": self.product_name,
            "price_label": self.price_label,
            "currency": self.currency,
            "amount_cents": self.amount_cents,
            "main_image_url": self.main_image_url,
        }

    @classmethod
    def from_session_dict(cls, data: dict[str, Any]) -> "CartItemSnapshot":
        return cls(
            product_slug=data.get("product_slug", ""),
            price_code=data.get("price_code", ""),
            quantity=data.get("quantity", 1),
            product_name=data.get("product_name", ""),
            price_label=data.get("price_label", ""),
            currency=data.get("currency", ""),
            amount_cents=data.get("amount_cents", 0),
            main_image_url=data.get("main_image_url", ""),
        )


def build_cart_item_key(product_slug: str, price_code: str) -> str:
    return f"{validate_slug(product_slug, 'product_slug')}::{validate_slug(price_code, 'price_code')}"


def list_cart_items(session_data: MutableMapping[str, Any]) -> list[CartItemSnapshot]:
    raw_cart = session_data.get(CART_SESSION_KEY) or {}

    if not isinstance(raw_cart, dict):
        return []

    items: list[CartItemSnapshot] = []

    for raw_item in raw_cart.values():
        if not isinstance(raw_item, dict):
            continue
        items.append(CartItemSnapshot.from_session_dict(raw_item))

    return sorted(items, key=lambda item: (item.product_name.lower(), item.price_label.lower()))


def cart_item_count(session_data: MutableMapping[str, Any]) -> int:
    return sum(item.quantity for item in list_cart_items(session_data))


def add_cart_item(session_data: MutableMapping[str, Any], item: CartItemSnapshot) -> None:
    raw_cart = dict(session_data.get(CART_SESSION_KEY) or {})
    existing = raw_cart.get(item.item_key)

    if isinstance(existing, dict):
        current_quantity = _clean_quantity(existing.get("quantity", 1))
        item = CartItemSnapshot(
            product_slug=item.product_slug,
            price_code=item.price_code,
            quantity=current_quantity + item.quantity,
            product_name=item.product_name,
            price_label=item.price_label,
            currency=item.currency,
            amount_cents=item.amount_cents,
            main_image_url=item.main_image_url,
        )

    raw_cart[item.item_key] = item.to_session_dict()
    session_data[CART_SESSION_KEY] = raw_cart
    _mark_session_modified(session_data)


def update_cart_item_quantity(
    session_data: MutableMapping[str, Any],
    *,
    product_slug: str,
    price_code: str,
    quantity: int,
) -> None:
    raw_cart = dict(session_data.get(CART_SESSION_KEY) or {})
    item_key = build_cart_item_key(product_slug, price_code)

    if item_key not in raw_cart:
        return

    clean_quantity = _clean_quantity(quantity)
    raw_item = dict(raw_cart[item_key])
    raw_item["quantity"] = clean_quantity
    raw_cart[item_key] = raw_item

    session_data[CART_SESSION_KEY] = raw_cart
    _mark_session_modified(session_data)


def remove_cart_item(
    session_data: MutableMapping[str, Any],
    *,
    product_slug: str,
    price_code: str,
) -> None:
    raw_cart = dict(session_data.get(CART_SESSION_KEY) or {})
    raw_cart.pop(build_cart_item_key(product_slug, price_code), None)

    session_data[CART_SESSION_KEY] = raw_cart
    _mark_session_modified(session_data)


def clear_cart(session_data: MutableMapping[str, Any]) -> None:
    session_data.pop(CART_SESSION_KEY, None)
    _mark_session_modified(session_data)


def _mark_session_modified(session_data: MutableMapping[str, Any]) -> None:
    if hasattr(session_data, "modified"):
        session_data.modified = True
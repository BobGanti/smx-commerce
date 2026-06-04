from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from smx_commerce.catalog.objects import Money
from smx_commerce.checkout.objects import BuyerDetails, Order
from smx_commerce.checkout.repository import OrderRepository


@dataclass(frozen=True)
class StartCheckoutRequest:
    product_slug: str
    price_code: str
    buyer_full_name: str
    buyer_email: str
    buyer_phone: str = ""
    buyer_company: str = ""
    buyer_metadata: dict[str, Any] = field(default_factory=dict)
    order_metadata: dict[str, Any] = field(default_factory=dict)
    payment_provider: str = "stripe"


@dataclass(frozen=True)
class StartCartCheckoutRequest:
    amount: Money
    buyer_full_name: str
    buyer_email: str
    buyer_phone: str = ""
    buyer_company: str = ""
    buyer_metadata: dict[str, Any] = field(default_factory=dict)
    order_metadata: dict[str, Any] = field(default_factory=dict)
    payment_provider: str = "stripe"


class CheckoutService:
    def __init__(self, session: Session):
        self.session = session
        self.orders = OrderRepository(session)

    def start_checkout(self, request: StartCheckoutRequest) -> Order:
        buyer = BuyerDetails(
            full_name=request.buyer_full_name,
            email=request.buyer_email,
            phone=request.buyer_phone,
            company=request.buyer_company,
            metadata=request.buyer_metadata,
        )

        return self.orders.create_pending(
            product_slug=request.product_slug,
            price_code=request.price_code,
            buyer=buyer,
            payment_provider=request.payment_provider,
            metadata=request.order_metadata,
        )

    def start_cart_checkout(self, request: StartCartCheckoutRequest) -> Order:
        buyer = BuyerDetails(
            full_name=request.buyer_full_name,
            email=request.buyer_email,
            phone=request.buyer_phone,
            company=request.buyer_company,
            metadata=request.buyer_metadata,
        )

        return self.orders.create_pending_cart(
            amount=request.amount,
            buyer=buyer,
            payment_provider=request.payment_provider,
            metadata=request.order_metadata,
        )
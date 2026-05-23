from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from smx_commerce.checkout.objects import Order


class PaymentCheckoutError(ValueError):
    pass


@dataclass(frozen=True)
class PaymentCheckoutSession:
    provider: str
    session_id: str
    checkout_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PaymentCheckoutProvider(Protocol):
    def create_checkout_session(
        self,
        *,
        order: Order,
        success_url: str,
        cancel_url: str,
    ) -> PaymentCheckoutSession:
        ...

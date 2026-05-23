from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class WebhookVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedPaymentEvent:
    provider: str
    provider_event_id: str
    event_type: str
    order_public_id: str | None = None
    payment_reference: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class PaymentWebhookVerifier(Protocol):
    def verify(
        self,
        *,
        payload: bytes,
        headers: Mapping[str, str],
    ) -> VerifiedPaymentEvent:
        ...

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from smx_commerce.catalog.objects import validate_required_text


class PaymentEventStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


@dataclass
class PaymentEvent:
    provider: str
    provider_event_id: str
    event_type: str
    status: PaymentEventStatus = PaymentEventStatus.RECEIVED
    order_public_id: str | None = None
    payment_reference: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

    def __post_init__(self) -> None:
        self.provider = validate_required_text(self.provider, "provider").lower()
        self.provider_event_id = validate_required_text(self.provider_event_id, "provider_event_id")
        self.event_type = validate_required_text(self.event_type, "event_type")

        if not isinstance(self.status, PaymentEventStatus):
            self.status = PaymentEventStatus(self.status)

        self.payload = dict(self.payload or {})
        self.error_message = self.error_message or ""

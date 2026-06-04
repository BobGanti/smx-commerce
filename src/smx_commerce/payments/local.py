from __future__ import annotations

import json
from collections.abc import Mapping

from smx_commerce.payments.checkout import PaymentCheckoutSession
from smx_commerce.payments.verifiers import VerifiedPaymentEvent, WebhookVerificationError


class LocalCheckoutProvider:
    def __init__(self, checkout_base_url: str = "https://local-payments.invalid/checkout"):
        self.checkout_base_url = checkout_base_url.rstrip("/")

    def create_checkout_session(self, *, order, success_url, cancel_url):
        return PaymentCheckoutSession(
            provider="local",
            session_id=f"local_{order.public_id}",
            checkout_url=f"{self.checkout_base_url}/{order.public_id}",
            metadata={
                "order_public_id": order.public_id,
                "product_slug": order.product_slug,
                "price_code": order.price_code,
                "cart_items": (order.metadata or {}).get("cart_items", []),
                "success_url": success_url,
                "cancel_url": cancel_url,
            },
        )


class StaticSignatureWebhookVerifier:
    def __init__(
        self,
        *,
        expected_signature: str,
        provider: str = "stripe",
        signature_header: str = "Stripe-Signature",
    ):
        if not expected_signature or not expected_signature.strip():
            raise ValueError("expected_signature is required")

        self.expected_signature = expected_signature
        self.provider = provider
        self.signature_header = signature_header

    def verify(self, *, payload: bytes, headers: Mapping[str, str]) -> VerifiedPaymentEvent:
        supplied_signature = headers.get(self.signature_header)

        if supplied_signature != self.expected_signature:
            raise WebhookVerificationError("invalid webhook signature")

        data = json.loads(payload.decode("utf-8"))

        return VerifiedPaymentEvent(
            provider=self.provider,
            provider_event_id=data["id"],
            event_type=data["type"],
            order_public_id=data.get("order_public_id"),
            payment_reference=data.get("payment_reference"),
            payload=data,
        )

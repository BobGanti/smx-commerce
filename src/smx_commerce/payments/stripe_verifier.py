from __future__ import annotations

from typing import Mapping

from smx_commerce.payments.verifiers import (
    VerifiedPaymentEvent,
    WebhookVerificationError,
)


class StripeWebhookVerifier:
    def __init__(self, webhook_secret: str):
        if not webhook_secret or not webhook_secret.strip():
            raise ValueError("webhook_secret is required")

        self.webhook_secret = webhook_secret.strip()

    def verify(
        self,
        *,
        payload: bytes,
        headers: Mapping[str, str],
    ) -> VerifiedPaymentEvent:
        signature = headers.get("Stripe-Signature")

        if not signature:
            raise WebhookVerificationError("missing Stripe-Signature header")

        try:
            import stripe
        except ImportError as exc:
            raise WebhookVerificationError(
                "stripe package is not installed; install smx-commerce[stripe]"
            ) from exc

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=self.webhook_secret,
            )
        except Exception as exc:
            raise WebhookVerificationError("invalid webhook signature") from exc

        event_type = event.get("type", "")
        event_id = event.get("id", "")
        data_object = event.get("data", {}).get("object", {})

        order_public_id = (
            data_object.get("metadata", {}).get("order_public_id")
            or data_object.get("client_reference_id")
        )
        payment_reference = data_object.get("id")

        return VerifiedPaymentEvent(
            provider="stripe",
            provider_event_id=event_id,
            event_type=event_type,
            order_public_id=order_public_id,
            payment_reference=payment_reference,
            payload=dict(event),
        )

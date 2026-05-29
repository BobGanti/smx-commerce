from __future__ import annotations

from typing import Mapping

from smx_commerce.payments.verifiers import (
    VerifiedPaymentEvent,
    WebhookVerificationError,
)


def _stripe_to_plain_dict(value):
    if value is None:
        return None

    if isinstance(value, dict):
        return {
            key: _stripe_to_plain_dict(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_stripe_to_plain_dict(item) for item in value]

    stripe_data = getattr(value, "_data", None)
    if isinstance(stripe_data, dict):
        return {
            key: _stripe_to_plain_dict(item)
            for key, item in stripe_data.items()
        }

    return value


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

        event_payload = _stripe_to_plain_dict(event)

        event_type = event_payload.get("type", "")
        event_id = event_payload.get("id", "")
        data_object = event_payload.get("data", {}).get("object", {})

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
            payload=event_payload,
        )
from __future__ import annotations

from flask import Blueprint, jsonify, request

from smx_commerce.core import CommerceRuntime
from smx_commerce.notifications import OrderConfirmationEmailService
from smx_commerce.payments import PaymentWebhookService
from smx_commerce.payments.verifiers import (
    PaymentWebhookVerifier,
    VerifiedPaymentEvent,
    WebhookVerificationError,
)


def payment_event_response(
    *,
    event_status: str,
    idempotent: bool,
    order_public_id: str | None,
    notification: dict | None = None,
) -> dict:
    return {
        "status": "ok",
        "event_status": event_status,
        "idempotent": idempotent,
        "order_public_id": order_public_id,
        "notification": notification,
    }


def create_payment_webhook_blueprint(
    runtime: CommerceRuntime,
    verifier: PaymentWebhookVerifier | None = None,
    order_confirmation_service: OrderConfirmationEmailService | None = None,
) -> Blueprint:
    bp = Blueprint("smx_commerce_payment_webhooks", __name__)

    @bp.post("/stripe/webhook")
    def stripe_webhook():
        if verifier is None:
            return jsonify({"error": "payment webhook verifier is not configured"}), 503

        try:
            verified_event = verifier.verify(
                payload=request.get_data(),
                headers=request.headers,
            )

            with runtime.session_scope() as session:
                service = PaymentWebhookService(session)
                result = _process_verified_event(service, verified_event)

                notification = None

                if (
                    order_confirmation_service is not None
                    and result.order is not None
                    and result.order.is_paid
                    and result.idempotent is False
                ):
                    notification_result = order_confirmation_service.send_order_paid_confirmation(
                        result.order
                    )
                    notification = {
                        "attempted": True,
                        "sent": notification_result.sent,
                        "error_message": notification_result.error_message,
                    }

            return jsonify(
                payment_event_response(
                    event_status=result.event.status.value,
                    idempotent=result.idempotent,
                    order_public_id=result.order.public_id if result.order else result.event.order_public_id,
                    notification=notification,
                )
            )

        except WebhookVerificationError as exc:
            return jsonify({"error": str(exc)}), 400

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    return bp


def _process_verified_event(
    service: PaymentWebhookService,
    verified_event: VerifiedPaymentEvent,
):
    if verified_event.event_type == "checkout.session.completed":
        if not verified_event.order_public_id:
            raise ValueError("verified payment event is missing order_public_id")

        if not verified_event.payment_reference:
            raise ValueError("verified payment event is missing payment_reference")

        return service.process_order_paid(
            provider=verified_event.provider,
            provider_event_id=verified_event.provider_event_id,
            event_type=verified_event.event_type,
            order_public_id=verified_event.order_public_id,
            payment_reference=verified_event.payment_reference,
            payload=verified_event.payload,
        )

    return service.ignore_event(
        provider=verified_event.provider,
        provider_event_id=verified_event.provider_event_id,
        event_type=verified_event.event_type,
        payload=verified_event.payload,
        reason="unsupported event type",
    )

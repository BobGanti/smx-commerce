from __future__ import annotations
from urllib.parse import urlencode
from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.checkout import CheckoutService, Order, OrderRepository, StartCheckoutRequest
from smx_commerce.core import CommerceRuntime
from smx_commerce.payments import PaymentCheckoutProvider, PaymentCheckoutSession


def order_to_dict(order: Order) -> dict:
    return {
        "public_id": order.public_id,
        "product_slug": order.product_slug,
        "price_code": order.price_code,
        "amount_cents": order.amount.amount_cents,
        "currency": order.amount.currency,
        "status": order.status.value,
        "payment_provider": order.payment_provider,
        "payment_reference": order.payment_reference,
        "buyer": {
            "full_name": order.buyer.full_name,
            "email": order.buyer.email,
            "phone": order.buyer.phone,
            "company": order.buyer.company,
            "metadata": order.buyer.metadata,
        },
        "metadata": order.metadata,
    }


def checkout_session_to_dict(session: PaymentCheckoutSession | None) -> dict | None:
    if session is None:
        return None

    return {
        "provider": session.provider,
        "session_id": session.session_id,
        "checkout_url": session.checkout_url,
        "metadata": session.metadata,
    }


def _is_form_submission() -> bool:
    return request.content_type is not None and "application/x-www-form-urlencoded" in request.content_type


def _checkout_payload() -> dict:
    if _is_form_submission():
        return dict(request.form)

    return request.get_json(silent=True) or {}


def checkout_wants_html() -> bool:
    requested_format = request.args.get("format", "").lower()

    if requested_format == "html":
        return True

    if requested_format == "json":
        return False

    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"



def _absolute_checkout_url(
    runtime: CommerceRuntime,
    path_or_url: str,
    *,
    order_public_id: str,
) -> str:
    value = (path_or_url or "").strip()

    if value.startswith(("http://", "https://")):
        return value

    public_base_url = (runtime.config.public_base_url or "").strip().rstrip("/")

    if not public_base_url:
        return value

    if not value.startswith("/"):
        value = f"/{value}"

    separator = "&" if "?" in value else "?"
    query = urlencode({"order_public_id": order_public_id})

    return f"{public_base_url}{value}{separator}{query}"


def create_checkout_blueprint(
    runtime: CommerceRuntime,
    payment_checkout_provider: PaymentCheckoutProvider | None = None,
) -> Blueprint:
    bp = Blueprint("smx_commerce_checkout", __name__)

    @bp.post("/checkout/start")
    def start_checkout():
        payload = _checkout_payload()

        try:
            checkout_request = StartCheckoutRequest(
                product_slug=payload.get("product_slug", ""),
                price_code=payload.get("price_code", ""),
                buyer_full_name=payload.get("buyer_full_name", ""),
                buyer_email=payload.get("buyer_email", ""),
                buyer_phone=payload.get("buyer_phone", ""),
                buyer_company=payload.get("buyer_company", ""),
                buyer_metadata=payload.get("buyer_metadata") or {},
                order_metadata=payload.get("order_metadata") or {},
                payment_provider=payload.get("payment_provider", "stripe"),
            )

            checkout_session = None

            with runtime.session_scope() as session:
                service = CheckoutService(session)
                order = service.start_checkout(checkout_request)

                if payment_checkout_provider is not None:

                    checkout_session = payment_checkout_provider.create_checkout_session(
                        order=order,
                        success_url=_absolute_checkout_url(
                            runtime,
                            payload.get("success_url", "/checkout/success"),
                            order_public_id=order.public_id,
                        ),
                        cancel_url=_absolute_checkout_url(
                            runtime,
                            payload.get("cancel_url", "/checkout/cancel"),
                            order_public_id=order.public_id,
                        ),
                    )

            if _is_form_submission() and checkout_session is not None:
                return redirect(checkout_session.checkout_url, code=303)

            order_payload = order_to_dict(order)

            response_payload = {
                **order_payload,
                "order": order_payload,
                "checkout_session": checkout_session_to_dict(checkout_session),
            }

            return jsonify(response_payload), 201

        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400


    @bp.get("/checkout/success")
    def checkout_success():
        order_public_id = request.args.get("order_id") or request.args.get("order_public_id")

        order_payload = None

        if order_public_id:
            with runtime.session_scope() as session:
                order = OrderRepository(session).get_by_public_id(order_public_id)

            if order is None:
                return jsonify({"error": f"order not found: {order_public_id}"}), 404

            order_payload = order_to_dict(order)

        payload = {
            "status": "ok",
            "checkout_status": "success_redirect_received",
            "payment_confirmation": "webhook_required",
            "message": "Checkout redirect received. Payment is confirmed only by verified webhook.",
            "order": order_payload,
        }

        if checkout_wants_html():
            return render_template(
                "public/checkout_success.html",
                commerce_config=runtime.config,
                **payload,
            )

        return jsonify(payload)

    @bp.get("/checkout/cancel")
    def checkout_cancel():
        order_public_id = request.args.get("order_id") or request.args.get("order_public_id")

        order_payload = None

        if order_public_id:
            with runtime.session_scope() as session:
                order = OrderRepository(session).get_by_public_id(order_public_id)

            if order is None:
                return jsonify({"error": f"order not found: {order_public_id}"}), 404

            order_payload = order_to_dict(order)

        payload = {
            "status": "ok",
            "checkout_status": "cancel_redirect_received",
            "payment_confirmation": "not_confirmed",
            "message": "Checkout cancel redirect received. No payment has been confirmed by this page.",
            "order": order_payload,
        }

        if checkout_wants_html():
            return render_template(
                "public/checkout_cancel.html",
                commerce_config=runtime.config,
                **payload,
            )

        return jsonify(payload)

    return bp

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.objects import CustomerStatus
from smx_commerce.customers.repository import CustomerRepository


def create_customer_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_customer_admin", __name__)

    @bp.get("/customers")
    def list_customers():
        status = (request.args.get("status") or "").strip().lower() or None

        try:
            with runtime.session_scope() as session:
                customers = CustomerRepository(session).list(
                    status=CustomerStatus(status) if status else None,
                )

            if customer_admin_wants_html():
                return render_template(
                    "admin/customers_list.html",
                    commerce_config=runtime.config,
                    customers=customers,
                    status=status,
                    customer_statuses=[item.value for item in CustomerStatus],
                )

            return jsonify([customer_to_dict(customer) for customer in customers])

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/customers/<customer_public_id>/status")
    def update_customer_status(customer_public_id: str):
        requested_status = (request.form.get("status") or "").strip().lower()

        try:
            status = CustomerStatus(requested_status)

            with runtime.session_scope() as session:
                customer = CustomerRepository(session).set_status(
                    customer_public_id,
                    status,
                )

            if customer_admin_wants_html():
                return redirect(
                    f"/commerce/admin/customers/{customer.public_id}?message=Customer status updated.",
                    code=303,
                )

            return jsonify({
                "status": "ok",
                "customer": customer_to_dict(customer),
            })

        except ValueError as exc:
            if customer_admin_wants_html():
                return redirect(
                    f"/commerce/admin/customers/{customer_public_id}?error={str(exc)}",
                    code=303,
                )

            return jsonify({"error": str(exc)}), 400


    @bp.get("/customers/<customer_public_id>")
    def customer_detail(customer_public_id: str):
        with runtime.session_scope() as session:
            customer_repository = CustomerRepository(session)
            customer = customer_repository.get_by_public_id(customer_public_id)

            if customer is None:
                return jsonify({"error": f"customer not found: {customer_public_id}"}), 404

            orders = OrderRepository(session).list_by_customer_public_id(customer.public_id)
            entitlements = customer_repository.list_entitlements(customer.public_id)
            sessions = customer_repository.list_sessions(customer.public_id)

        if customer_admin_wants_html():
            return render_template(
                "admin/customer_detail.html",
                commerce_config=runtime.config,
                customer=customer,
                orders=orders,
                entitlements=entitlements,
                sessions=sessions,
                message=request.args.get("message"),
                error=request.args.get("error"),
            )

        return jsonify(
            {
                "customer": customer_to_dict(customer),
                "orders": [order_to_dict(order) for order in orders],
                "entitlements": [entitlement_to_dict(entitlement) for entitlement in entitlements],
                "sessions": [session_to_dict(session) for session in sessions],
            }
        )

    return bp


def customer_admin_wants_html() -> bool:
    requested_format = request.args.get("format", "").lower()

    if requested_format == "html":
        return True

    if requested_format == "json":
        return False

    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"


def customer_to_dict(customer) -> dict:
    return {
        "public_id": customer.public_id,
        "email": customer.email,
        "full_name": customer.full_name,
        "phone": customer.phone,
        "company": customer.company,
        "status": customer.status.value,
        "last_login_at": _datetime_to_string(customer.last_login_at),
    }


def order_to_dict(order) -> dict:
    return {
        "public_id": order.public_id,
        "product_slug": order.product_slug,
        "price_code": order.price_code,
        "status": order.status.value,
        "amount_cents": order.amount.amount_cents,
        "currency": order.amount.currency,
        "payment_reference": order.payment_reference,
    }


def entitlement_to_dict(entitlement) -> dict:
    return {
        "public_id": entitlement.public_id,
        "customer_public_id": entitlement.customer_public_id,
        "order_public_id": entitlement.order_public_id,
        "product_slug": entitlement.product_slug,
        "price_code": entitlement.price_code,
        "entitlement_type": entitlement.entitlement_type.value,
        "status": entitlement.status.value,
        "starts_at": _datetime_to_string(entitlement.starts_at),
        "ends_at": _datetime_to_string(entitlement.ends_at),
    }


def session_to_dict(session) -> dict:
    return {
        "public_id": session.public_id,
        "customer_public_id": session.customer_public_id,
        "expires_at": _datetime_to_string(session.expires_at),
        "revoked_at": _datetime_to_string(session.revoked_at),
        "last_seen_at": _datetime_to_string(session.last_seen_at),
    }


def _datetime_to_string(value) -> str | None:
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)

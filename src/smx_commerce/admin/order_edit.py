from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request
from sqlalchemy import select, text

from smx_commerce.checkout import OrderRepository, OrderStatus
from smx_commerce.checkout.models import OrderRow
from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.repository import CustomerRepository


ADMIN_EDITABLE_ORDER_STATUSES = {
    "pending",
    "paid",
    "cancelled",
    "failed",
    "refunded",
}


def create_order_edit_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_order_edit_admin", __name__)

    @bp.get("/orders/<public_id>/edit")
    def edit_order(public_id: str):
        context = _load_order_admin_context(runtime, public_id)

        if context["order"] is None:
            return jsonify({"error": f"order not found: {public_id}"}), 404

        return render_template(
            "admin/order_edit.html",
            commerce_config=runtime.config,
            editable_statuses=sorted(ADMIN_EDITABLE_ORDER_STATUSES),
            **context,
        )

    @bp.post("/orders/<public_id>/update")
    def update_order_from_form(public_id: str):
        requested_status = (request.form.get("status") or "").strip().lower()
        if requested_status == "paid":
            context = _load_order_admin_context(runtime, public_id)
            return render_template(
                "admin/order_edit.html",
                commerce_config=runtime.config,
                editable_statuses=sorted(ADMIN_EDITABLE_ORDER_STATUSES),
                error="Order status can only be changed by a verified payment event.",
                **context,
            ), 400

        payload = request.form
        requested_status = payload.get("status", "pending").strip().lower()

        if requested_status not in ADMIN_EDITABLE_ORDER_STATUSES:
            context = _load_order_admin_context(runtime, public_id)

            if context["order"] is None:
                return jsonify({"error": f"order not found: {public_id}"}), 404

            return render_template(
                "admin/order_edit.html",
                commerce_config=runtime.config,
                editable_statuses=sorted(ADMIN_EDITABLE_ORDER_STATUSES),
                error="status can only be changed to pending, paid, cancelled, failed, or refunded from admin",
                **context,
            ), 400

        with runtime.session_scope() as session:
            order = OrderRepository(session).get_by_public_id(public_id)

            if order is None:
                return jsonify({"error": f"order not found: {public_id}"}), 404

            session.execute(
                text(
                    """
                    UPDATE smx_orders
                    SET buyer_full_name = :buyer_full_name,
                        buyer_email = :buyer_email,
                        buyer_phone = :buyer_phone,
                        buyer_company = :buyer_company,
                        notes = :notes,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE public_id = :public_id
                    """
                ),
                {
                    "public_id": public_id,
                    "buyer_full_name": payload.get("buyer_full_name", ""),
                    "buyer_email": payload.get("buyer_email", ""),
                    "buyer_phone": payload.get("buyer_phone", ""),
                    "buyer_company": payload.get("buyer_company", ""),
                    "notes": payload.get("notes", ""),
                },
            )

            OrderRepository(session).update(
                public_id,
                status=OrderStatus(requested_status),
            )

        return redirect(f"/commerce/admin/orders/{public_id}", code=303)

    return bp



def _load_order_admin_context(runtime: CommerceRuntime, public_id: str) -> dict:
    with runtime.session_scope() as session:
        order_repository = OrderRepository(session)
        customer_repository = CustomerRepository(session)

        order = order_repository.get_by_public_id(public_id)

        if order is None:
            return {
                "order": None,
                "linked_customer": None,
                "order_entitlements": [],
            }

        order_row = session.execute(
            select(OrderRow).where(OrderRow.public_id == public_id)
        ).scalar_one_or_none()

        linked_customer = None

        if order_row is not None and order_row.customer_id is not None:
            linked_customer = customer_repository.get_by_internal_id(order_row.customer_id)

        order_entitlements = customer_repository.list_entitlements_for_order(public_id)

        return {
            "order": order,
            "linked_customer": linked_customer,
            "order_entitlements": order_entitlements,
        }

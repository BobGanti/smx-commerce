from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request
from sqlalchemy import text

from smx_commerce.checkout import OrderRepository
from smx_commerce.core import CommerceRuntime


ADMIN_EDITABLE_ORDER_STATUSES = {
    "pending",
    "cancelled",
    "failed",
    "refunded",
}


def create_order_edit_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_order_edit_admin", __name__)

    @bp.get("/orders/<public_id>/edit")
    def edit_order(public_id: str):
        with runtime.session_scope() as session:
            order = OrderRepository(session).get_by_public_id(public_id)

        if order is None:
            return jsonify({"error": f"order not found: {public_id}"}), 404

        return render_template(
            "admin/order_edit.html",
            order=order,
            editable_statuses=sorted(ADMIN_EDITABLE_ORDER_STATUSES),
        )

    @bp.post("/orders/<public_id>/update")
    def update_order_from_form(public_id: str):
        payload = request.form
        requested_status = payload.get("status", "pending").strip().lower()

        if requested_status not in ADMIN_EDITABLE_ORDER_STATUSES:
            with runtime.session_scope() as session:
                order = OrderRepository(session).get_by_public_id(public_id)

            if order is None:
                return jsonify({"error": f"order not found: {public_id}"}), 404

            return render_template(
                "admin/order_edit.html",
                order=order,
                editable_statuses=sorted(ADMIN_EDITABLE_ORDER_STATUSES),
                error="status can only be changed to pending, cancelled, failed, or refunded from admin",
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
                        status = :status,
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
                    "status": requested_status,
                },
            )

        return redirect(f"/commerce/admin/orders/{public_id}", code=303)

    return bp

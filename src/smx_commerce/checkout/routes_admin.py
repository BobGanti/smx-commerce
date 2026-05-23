from __future__ import annotations

import csv
from io import StringIO

from flask import Blueprint, Response, jsonify, render_template, request

from smx_commerce.checkout import Order, OrderRepository, OrderStatus
from smx_commerce.core import CommerceRuntime


def admin_orders_wants_html() -> bool:
    requested_format = request.args.get("format", "").lower()

    if requested_format == "html":
        return True

    if requested_format == "json":
        return False

    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"


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
        "notes": getattr(order, "notes", ""),
    }


def order_to_csv_row(order: Order) -> dict:
    return {
        "public_id": order.public_id,
        "product_slug": order.product_slug,
        "price_code": order.price_code,
        "amount_cents": order.amount.amount_cents,
        "currency": order.amount.currency,
        "status": order.status.value,
        "payment_provider": order.payment_provider,
        "payment_reference": order.payment_reference or "",
        "buyer_full_name": order.buyer.full_name,
        "buyer_email": order.buyer.email,
        "buyer_phone": order.buyer.phone,
        "buyer_company": order.buyer.company,
    }


def orders_to_csv(orders: list[Order]) -> str:
    fieldnames = [
        "public_id",
        "product_slug",
        "price_code",
        "amount_cents",
        "currency",
        "status",
        "payment_provider",
        "payment_reference",
        "buyer_full_name",
        "buyer_email",
        "buyer_phone",
        "buyer_company",
    ]

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    for order in orders:
        writer.writerow(order_to_csv_row(order))

    return output.getvalue()


def create_order_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_order_admin", __name__)

    @bp.get("/orders")
    def list_orders():
        status = request.args.get("status")
        product_slug = request.args.get("product_slug")

        try:
            with runtime.session_scope() as session:
                orders = OrderRepository(session).list(
                    status=OrderStatus(status) if status else None,
                    product_slug=product_slug,
                )

            if admin_orders_wants_html():
                return render_template(
                    "admin/orders_list.html",
                    orders=orders,
                    status=status,
                    product_slug=product_slug,
                    commerce_config=runtime.config,
                )

            return jsonify([order_to_dict(order) for order in orders])

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.get("/orders.csv")
    def export_orders_csv():
        status = request.args.get("status")
        product_slug = request.args.get("product_slug")

        try:
            with runtime.session_scope() as session:
                orders = OrderRepository(session).list(
                    status=OrderStatus(status) if status else None,
                    product_slug=product_slug,
                )

            csv_text = orders_to_csv(orders)

            return Response(
                csv_text,
                mimetype="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=smx_commerce_orders.csv",
                },
            )

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.get("/orders/<public_id>")
    def get_order(public_id: str):
        with runtime.session_scope() as session:
            order = OrderRepository(session).get_by_public_id(public_id)

        if order is None:
            return jsonify({"error": f"order not found: {public_id}"}), 404

        return jsonify(order_to_dict(order))

    @bp.post("/orders/<public_id>/cancel")
    def cancel_order(public_id: str):
        try:
            with runtime.session_scope() as session:
                order = OrderRepository(session).cancel(public_id)

            return jsonify(order_to_dict(order))

        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    @bp.post("/orders/<public_id>/fail")
    def fail_order(public_id: str):
        try:
            with runtime.session_scope() as session:
                order = OrderRepository(session).fail(public_id)

            return jsonify(order_to_dict(order))

        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    return bp

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, request
from sqlalchemy import text
from urllib.parse import urlencode

from smx_commerce.core import CommerceRuntime


def create_safe_delete_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_safe_delete_admin", __name__)

    @bp.post("/products/<slug>/delete")
    def delete_product(slug: str):
        try:
            with runtime.session_scope() as session:
                order_count = _scalar_int(
                    session,
                    "SELECT COUNT(*) FROM smx_orders WHERE product_slug = :slug",
                    {"slug": slug},
                )

                if order_count > 0:
                    return _delete_blocked(
                        f"product cannot be deleted because {order_count} order(s) reference it",
                        redirect_to=f"/commerce/admin/products/{slug}",
                    )

                product_count = _scalar_int(
                    session,
                    "SELECT COUNT(*) FROM smx_products WHERE slug = :slug",
                    {"slug": slug},
                )

                if product_count == 0:
                    return jsonify({"error": f"product not found: {slug}"}), 404

                session.execute(
                    text("DELETE FROM smx_product_categories WHERE product_slug = :slug"),
                    {"slug": slug},
                )
                session.execute(
                    text("DELETE FROM smx_product_prices WHERE product_slug = :slug"),
                    {"slug": slug},
                )
                session.execute(
                    text("DELETE FROM smx_products WHERE slug = :slug"),
                    {"slug": slug},
                )

            return _delete_ok(
                {"status": "ok", "deleted": True, "object_type": "product", "slug": slug},
                redirect_to="/commerce/admin/products",
            )

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/products/<product_slug>/prices/<code>/delete")
    def delete_price(product_slug: str, code: str):
        try:
            with runtime.session_scope() as session:
                order_count = _scalar_int(
                    session,
                    """
                    SELECT COUNT(*)
                    FROM smx_orders
                    WHERE product_slug = :product_slug
                      AND price_code = :code
                    """,
                    {"product_slug": product_slug, "code": code},
                )

                if order_count > 0:
                    return _delete_blocked(
                        f"price cannot be deleted because {order_count} order(s) reference it",
                        redirect_to=f"/commerce/admin/products/{product_slug}",
                    )

                price_count = _scalar_int(
                    session,
                    """
                    SELECT COUNT(*)
                    FROM smx_product_prices
                    WHERE product_slug = :product_slug
                      AND code = :code
                    """,
                    {"product_slug": product_slug, "code": code},
                )

                if price_count == 0:
                    return jsonify(
                        {"error": f"price not found for product {product_slug}: {code}"}
                    ), 404

                session.execute(
                    text(
                        """
                        DELETE FROM smx_product_prices
                        WHERE product_slug = :product_slug
                          AND code = :code
                        """
                    ),
                    {"product_slug": product_slug, "code": code},
                )

            return _delete_ok(
                {
                    "status": "ok",
                    "deleted": True,
                    "object_type": "price",
                    "product_slug": product_slug,
                    "code": code,
                },
                redirect_to=f"/commerce/admin/products/{product_slug}",
            )

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/categories/<slug>/delete")
    def delete_category(slug: str):
        try:
            with runtime.session_scope() as session:
                product_link_count = _scalar_int(
                    session,
                    "SELECT COUNT(*) FROM smx_product_categories WHERE category_slug = :slug",
                    {"slug": slug},
                )

                if product_link_count > 0:
                    return _delete_blocked(
                        f"category cannot be deleted because {product_link_count} product(s) use it",
                        redirect_to="/commerce/admin/categories",
                    )

                child_count = _scalar_int(
                    session,
                    "SELECT COUNT(*) FROM smx_categories WHERE parent_slug = :slug",
                    {"slug": slug},
                )

                if child_count > 0:
                    return _delete_blocked(
                        f"category cannot be deleted because {child_count} child category/categories use it as parent",
                        redirect_to="/commerce/admin/categories",
                    )

                category_count = _scalar_int(
                    session,
                    "SELECT COUNT(*) FROM smx_categories WHERE slug = :slug",
                    {"slug": slug},
                )

                if category_count == 0:
                    return jsonify({"error": f"category not found: {slug}"}), 404

                session.execute(
                    text("DELETE FROM smx_categories WHERE slug = :slug"),
                    {"slug": slug},
                )

            return _delete_ok(
                {"status": "ok", "deleted": True, "object_type": "category", "slug": slug},
                redirect_to="/commerce/admin/categories",
            )

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400


    @bp.post("/orders/<public_id>/delete")
    def delete_order(public_id: str):
        try:
            with runtime.session_scope() as session:
                row = session.execute(
                    text(
                        """
                        SELECT public_id, status
                        FROM smx_orders
                        WHERE public_id = :public_id
                        """
                    ),
                    {"public_id": public_id},
                ).mappings().first()

                if row is None:
                    return jsonify({"error": f"order not found: {public_id}"}), 404

                status = row["status"]

                if status in {"paid", "refunded"}:
                    return _delete_blocked(
                        f"order cannot be deleted because its status is {status}",
                        redirect_to=f"/commerce/admin/orders/{public_id}/edit",
                    )

                payment_event_count = _scalar_int(
                    session,
                    """
                    SELECT COUNT(*)
                    FROM smx_payment_events
                    WHERE order_public_id = :public_id
                    """,
                    {"public_id": public_id},
                )

                if payment_event_count > 0:
                    return _delete_blocked(
                        f"order cannot be deleted because {payment_event_count} payment event(s) reference it",
                        redirect_to=f"/commerce/admin/orders/{public_id}/edit",
                    )

                session.execute(
                    text("DELETE FROM smx_orders WHERE public_id = :public_id"),
                    {"public_id": public_id},
                )

            return _delete_ok(
                {
                    "status": "ok",
                    "deleted": True,
                    "object_type": "order",
                    "public_id": public_id,
                },
                redirect_to="/commerce/admin/orders",
            )

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400


    return bp


def _scalar_int(session, sql: str, params: dict) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def _is_form_submission() -> bool:
    content_type = request.content_type or ""
    return (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    )


def _delete_ok(payload: dict, *, redirect_to: str):
    if _is_form_submission():
        return redirect(redirect_to, code=303)

    return jsonify(payload)


def _delete_blocked(message: str, *, redirect_to: str):
    if _is_form_submission():
        separator = "&" if "?" in redirect_to else "?"
        return redirect(
            f"{redirect_to}{separator}{urlencode({'error': message})}",
            code=303,
        )

    return jsonify({"error": message}), 409

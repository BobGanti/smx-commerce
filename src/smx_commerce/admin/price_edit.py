from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.admin.amounts import parse_admin_price_amount_from_payload
from smx_commerce.catalog import CatalogService, Money
from smx_commerce.core import CommerceRuntime


def create_price_edit_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_price_edit_admin", __name__)

    @bp.get("/products/<product_slug>/prices/<code>/edit")
    def edit_price(product_slug: str, code: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            product = catalog.get_product(product_slug)
            price = catalog.get_price(product_slug, code)

        if product is None:
            return jsonify({"error": f"product not found: {product_slug}"}), 404

        if price is None:
            return jsonify({"error": f"price not found for product {product_slug}: {code}"}), 404

        return render_template(
            "admin/price_edit.html",
            product=product,
            price=price,
            commerce_config=runtime.config,
        )

    @bp.post("/products/<product_slug>/prices/<code>/update")
    def update_price_from_form(product_slug: str, code: str):
        payload = dict(request.form)

        try:
            amount = Money(
                amount_cents=parse_admin_price_amount_from_payload(
                    payload,
                    is_form=True,
                ),
                currency=payload.get("currency", "EUR"),
            )

            changes = {
                "label": payload.get("label", ""),
                "amount": amount,
                "status": payload.get("status", "active"),
                "billing_mode": payload.get("billing_mode", "one_time"),
                "billing_interval": payload.get("billing_interval") or None,
                "sort_order": int(payload.get("sort_order", 0) or 0),
            }

            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                catalog.update_price(product_slug, code, **changes)

            return redirect(f"/commerce/admin/products/{product_slug}", code=303)

        except (TypeError, ValueError) as exc:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                product = catalog.get_product(product_slug)
                price = catalog.get_price(product_slug, code)

            if product is None:
                return jsonify({"error": f"product not found: {product_slug}"}), 404

            if price is None:
                return jsonify({"error": f"price not found for product {product_slug}: {code}"}), 404

            return render_template(
                "admin/price_edit.html",
                product=product,
                price=price,
                error=str(exc),
                commerce_config=runtime.config,
            ), 400

    return bp

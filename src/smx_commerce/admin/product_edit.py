from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.catalog import CatalogService
from smx_commerce.core import CommerceRuntime


def create_product_edit_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_product_edit_admin", __name__)

    @bp.get("/products/<slug>/edit")
    def edit_product(slug: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            product = catalog.get_product(slug)
            categories = catalog.list_categories(include_archived=False)

        if product is None:
            return jsonify({"error": f"product not found: {slug}"}), 404

        return render_template(
            "admin/product_edit.html",
            product=product,
            categories=categories,
            commerce_config=runtime.config,
        )

    @bp.post("/products/<slug>/update")
    def update_product_from_form(slug: str):
        payload = request.form

        category_slugs = [
            item.strip()
            for value in request.form.getlist("category_slugs")
            for item in str(value).split(",")
            if item.strip()
        ]

        changes = {
            "name": payload.get("name", ""),
            "kind": payload.get("kind", "generic"),
            "summary": payload.get("summary", ""),
            "description": payload.get("description", ""),
            "status": payload.get("status", "draft"),
            "category_slugs": category_slugs,
            "sort_order": int(payload.get("sort_order", 0) or 0),
        }

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                updated = catalog.update_product(slug, **changes)

            return redirect(f"/commerce/admin/products/{updated.slug}", code=303)

        except (TypeError, ValueError) as exc:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                product = catalog.get_product(slug)
                categories = catalog.list_categories(include_archived=False)

            if product is None:
                return jsonify({"error": f"product not found: {slug}"}), 404

            return render_template(
                "admin/product_edit.html",
                product=product,
                categories=categories,
                error=str(exc),
                commerce_config=runtime.config,
            ), 400

    return bp

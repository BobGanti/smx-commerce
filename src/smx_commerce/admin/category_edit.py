from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.catalog import CatalogService
from smx_commerce.core import CommerceRuntime


def create_category_edit_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_category_edit_admin", __name__)

    @bp.get("/categories/<slug>/edit")
    def edit_category(slug: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            category = catalog.get_category(slug)
            categories = catalog.list_categories(include_archived=False)

        if category is None:
            return jsonify({"error": f"category not found: {slug}"}), 404

        parent_options = [
            item for item in categories
            if item.slug != category.slug
        ]

        return render_template(
            "admin/category_edit.html",
            category=category,
            parent_options=parent_options,
            commerce_config=runtime.config,
        )

    @bp.post("/categories/<slug>/update")
    def update_category_from_form(slug: str):
        payload = request.form

        parent_slug = payload.get("parent_slug") or None

        if parent_slug == slug:
            parent_slug = None

        changes = {
            "name": payload.get("name", ""),
            "description": payload.get("description", ""),
            "status": payload.get("status", "active"),
            "parent_slug": parent_slug,
            "sort_order": int(payload.get("sort_order", 0) or 0),
        }

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                updated = catalog.update_category(slug, **changes)

            return redirect("/commerce/admin/categories", code=303)

        except (TypeError, ValueError) as exc:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                category = catalog.get_category(slug)
                categories = catalog.list_categories(include_archived=False)

            if category is None:
                return jsonify({"error": f"category not found: {slug}"}), 404

            parent_options = [
                item for item in categories
                if item.slug != category.slug
            ]

            return render_template(
                "admin/category_edit.html",
                category=category,
                parent_options=parent_options,
                error=str(exc),
                commerce_config=runtime.config,
            ), 400

    return bp

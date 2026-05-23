from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from smx_commerce.catalog import CatalogService, Product, ProductStatus
from smx_commerce.core import CommerceRuntime


def public_price_to_dict(price) -> dict:
    return {
        "code": price.code,
        "label": price.label,
        "amount_cents": price.amount.amount_cents,
        "currency": price.amount.currency,
        "billing_mode": price.billing_mode.value,
        "billing_interval": price.billing_interval,
        "sort_order": price.sort_order,
    }


def public_product_to_dict(product: Product) -> dict:
    return {
        "slug": product.slug,
        "name": product.name,
        "kind": product.kind.value,
        "summary": product.summary,
        "description": product.description,
        "status": product.status.value,
        "category_slugs": product.category_slugs,
        "is_public": product.is_public,
        "is_purchasable": product.is_purchasable,
        "prices": [
            public_price_to_dict(price)
            for price in product.active_prices
        ],
    }


def wants_html() -> bool:
    requested_format = request.args.get("format", "").lower()

    if requested_format == "html":
        return True

    if requested_format == "json":
        return False

    best_match = request.accept_mimetypes.best_match(["text/html", "application/json"])

    return best_match == "text/html"


def create_public_catalog_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint(
        "smx_commerce_public_catalog",
        __name__,
        template_folder="../templates",
    )

    @bp.get("/products")
    def list_public_products():
        category_slug = request.args.get("category_slug")

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                products = catalog.list_products(
                    status=ProductStatus.ACTIVE,
                    category_slug=category_slug,
                )

            if wants_html():
                return render_template(
                    "public/product_list.html",
                    products=products,
                    commerce_config=runtime.config,
                )

            return jsonify([public_product_to_dict(product) for product in products])

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.get("/products/<slug>")
    def get_public_product(slug: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            product = catalog.get_product(slug)

        if product is None or not product.is_public:
            return jsonify({"error": f"product not found: {slug}"}), 404

        if wants_html():
            return render_template(
                "public/product_detail.html",
                product=product,
                commerce_config=runtime.config,
            )

        return jsonify(public_product_to_dict(product))

    return bp

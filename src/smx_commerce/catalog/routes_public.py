from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, session as flask_session
from smx_commerce.catalog import CatalogService, Product, ProductMedia, ProductStatus
from smx_commerce.cart import (
    CartItemSnapshot,
    add_cart_item,
    cart_item_count,
    list_cart_items,
    remove_cart_item,
    update_cart_item_quantity,
)
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


def public_media_to_dict(media: ProductMedia) -> dict:
    return {
        "url": media.url,
        "media_role": media.media_role.value,
        "alt_text": media.alt_text,
        "sort_order": media.sort_order,
    }


def public_product_to_dict(product: Product) -> dict:
    return {
        "product_public_id": product.product_public_id,
        "slug": product.slug,
        "name": product.name,
        "kind": product.kind.value,
        "summary": product.summary,
        "description": product.description,
        "status": product.status.value,
        "category_slugs": product.category_slugs,
        "is_public": product.is_public,
        "is_purchasable": product.is_purchasable,
        "main_image_url": product.main_image_url,
        "gallery_images": [
            public_media_to_dict(media)
            for media in product.gallery_images
        ],
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

    @bp.get("/commerce/cart")
    def view_cart():
        cart_items = list_cart_items(flask_session)
        currencies = {item.currency for item in cart_items}

        return render_template(
            "public/cart.html",
            cart_items=cart_items,
            cart_item_count=cart_item_count(flask_session),
            cart_total_cents=sum(item.line_total_cents for item in cart_items),
            cart_currency=next(iter(currencies)) if len(currencies) == 1 else "",
            commerce_config=runtime.config,
        )

    @bp.post("/commerce/cart/add")
    def add_to_cart():
        product_slug = request.form.get("product_slug", "")
        price_code = request.form.get("price_code", "")
        quantity = request.form.get("quantity", 1)

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                product = catalog.get_product(product_slug)

            if product is None or not product.is_purchasable:
                return jsonify({"error": f"product is not purchasable: {product_slug}"}), 404

            selected_price = next(
                (price for price in product.active_prices if price.code == price_code),
                None,
            )

            if selected_price is None:
                return jsonify({"error": f"price not found for product {product_slug}: {price_code}"}), 404

            add_cart_item(
                flask_session,
                CartItemSnapshot(
                    product_slug=product.slug,
                    price_code=selected_price.code,
                    quantity=quantity,
                    product_name=product.name,
                    price_label=selected_price.label,
                    currency=selected_price.amount.currency,
                    amount_cents=selected_price.amount.amount_cents,
                    main_image_url=product.main_image_url or "",
                ),
            )

            return redirect("/commerce/cart", code=303)

        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
    
    @bp.post("/commerce/cart/remove")
    def remove_from_cart():
        product_slug = request.form.get("product_slug", "")
        price_code = request.form.get("price_code", "")

        try:
            remove_cart_item(
                flask_session,
                product_slug=product_slug,
                price_code=price_code,
            )
            return redirect("/commerce/cart", code=303)

        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        

    @bp.post("/commerce/cart/update")
    def update_cart():
        product_slug = request.form.get("product_slug", "")
        price_code = request.form.get("price_code", "")
        quantity = request.form.get("quantity", 1)

        try:
            update_cart_item_quantity(
                flask_session,
                product_slug=product_slug,
                price_code=price_code,
                quantity=quantity,
            )
            return redirect("/commerce/cart", code=303)

        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        

    @bp.get("/commerce/products")
    def list_public_products():
        category_slug = request.args.get("category_slug")

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                products = catalog.list_products(
                    status=ProductStatus.ACTIVE,
                    category_slug=category_slug,
                )
                categories = catalog.list_categories(include_archived=False)

            if wants_html():
                return render_template(
                    "public/product_list.html",
                    products=products,
                    categories=categories,
                    selected_category_slug=category_slug or "",
                    commerce_config=runtime.config,
                )

            return jsonify([public_product_to_dict(product) for product in products])

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.get("/commerce/products/<slug>")
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

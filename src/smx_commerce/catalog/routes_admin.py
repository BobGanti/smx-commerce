from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.catalog import CatalogService, Category, Money, Product, ProductPrice
from smx_commerce.core import CommerceRuntime
from smx_commerce.admin.amounts import parse_admin_amount_to_cents, parse_admin_price_amount_from_payload


def category_to_dict(category: Category) -> dict:
    return {
        "slug": category.slug,
        "name": category.name,
        "description": category.description,
        "status": category.status.value,
        "parent_slug": category.parent_slug,
        "sort_order": category.sort_order,
        "metadata": category.metadata,
        "is_public": category.is_public,
    }


def price_to_dict(price: ProductPrice) -> dict:
    return {
        "code": price.code,
        "label": price.label,
        "amount_cents": price.amount.amount_cents,
        "currency": price.amount.currency,
        "status": price.status.value,
        "billing_mode": price.billing_mode.value,
        "billing_interval": price.billing_interval,
        "sort_order": price.sort_order,
        "metadata": price.metadata,
        "is_active": price.is_active,
    }


def product_to_dict(product: Product) -> dict:
    return {
        "slug": product.slug,
        "name": product.name,
        "kind": product.kind.value,
        "summary": product.summary,
        "description": product.description,
        "status": product.status.value,
        "category_slugs": product.category_slugs,
        "sort_order": product.sort_order,
        "metadata": product.metadata,
        "is_public": product.is_public,
        "is_purchasable": product.is_purchasable,
        "prices": [price_to_dict(price) for price in product.prices],
    }


def admin_is_form_submission() -> bool:
    content_type = request.content_type or ""
    return (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    )


def admin_payload() -> dict:
    if admin_is_form_submission():
        return dict(request.form)

    return request.get_json(silent=True) or {}


def admin_wants_html() -> bool:
    requested_format = request.args.get("format", "").lower()

    if requested_format == "html":
        return True

    if requested_format == "json":
        return False

    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"




def create_category_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_category_admin", __name__)

    @bp.get("/categories")
    def list_categories():
        include_archived = request.args.get("include_archived") in {"1", "true", "yes"}

        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            categories = catalog.list_categories(include_archived=include_archived)

        if admin_wants_html():
            return render_template(
                "admin/categories_list.html",
                categories=categories,
                commerce_config=runtime.config,
            )

        return jsonify([category_to_dict(category) for category in categories])

    @bp.post("/categories")
    def create_category():
        payload = admin_payload()

        try:
            category = Category(
                slug=payload.get("slug", ""),
                name=payload.get("name", ""),
                description=payload.get("description", ""),
                status=payload.get("status", "active"),
                parent_slug=payload.get("parent_slug") or None,
                sort_order=int(payload.get("sort_order", 0) or 0),
                metadata=payload.get("metadata") or {},
            )

            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                created = catalog.create_category(category)

            if admin_is_form_submission():
                return redirect("/commerce/admin/categories", code=303)

            return jsonify(category_to_dict(created)), 201

        except (TypeError, ValueError) as exc:
            if admin_is_form_submission():
                with runtime.session_scope() as session:
                    catalog = CatalogService(session)
                    categories = catalog.list_categories(include_archived=False)

                return render_template(
                    "admin/categories_list.html",
                    categories=categories,
                    error=str(exc),
                    commerce_config=runtime.config,
                ), 400

            return jsonify({"error": str(exc)}), 400

    @bp.get("/categories/<slug>")
    def get_category(slug: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            category = catalog.get_category(slug)

        if category is None:
            return jsonify({"error": f"category not found: {slug}"}), 404

        return jsonify(category_to_dict(category))

    @bp.patch("/categories/<slug>")
    def update_category(slug: str):
        payload = request.get_json(silent=True) or {}

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                updated = catalog.update_category(slug, **payload)

            return jsonify(category_to_dict(updated))

        except (TypeError, ValueError) as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    @bp.post("/categories/<slug>/archive")
    def archive_category(slug: str):
        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                archived = catalog.archive_category(slug)

            return jsonify(category_to_dict(archived))

        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    return bp



def create_product_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_product_admin", __name__)

    @bp.get("/products")
    def list_products():
        include_archived = request.args.get("include_archived") in {"1", "true", "yes"}
        status = request.args.get("status")
        category_slug = request.args.get("category_slug")

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                products = catalog.list_products(
                    status=status,
                    category_slug=category_slug,
                    include_archived=include_archived,
                )
                categories = catalog.list_categories(include_archived=False)

            if admin_wants_html():
                return render_template(
                    "admin/products_list.html",
                    products=products,
                    categories=categories,
                    error=request.args.get("error"),
                    commerce_config=runtime.config,
                )

            return jsonify([product_to_dict(product) for product in products])

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/products")
    def create_product():
        payload = admin_payload()

        try:
            product = Product(
                slug=payload.get("slug", ""),
                name=payload.get("name", ""),
                kind=payload.get("kind", "generic"),
                summary=payload.get("summary", ""),
                description=payload.get("description", ""),
                status=payload.get("status", "draft"),
                category_slugs=_category_slugs_from_payload(payload),
                sort_order=int(payload.get("sort_order", 0) or 0),
                metadata=payload.get("metadata") or {},
            )

            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                created = catalog.create_product(product)

            if admin_is_form_submission():
                return redirect("/commerce/admin/products", code=303)

            return jsonify(product_to_dict(created)), 201

        except (TypeError, ValueError) as exc:
            if admin_is_form_submission():
                with runtime.session_scope() as session:
                    catalog = CatalogService(session)
                    products = catalog.list_products(include_archived=False)
                    categories = catalog.list_categories(include_archived=False)

                return render_template(
                    "admin/products_list.html",
                    products=products,
                    categories=categories,
                    error=str(exc),
                    commerce_config=runtime.config,
                ), 400

            return jsonify({"error": str(exc)}), 400

    @bp.get("/products/<slug>")
    def get_product(slug: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            product = catalog.get_product(slug)

        if product is None:
            return jsonify({"error": f"product not found: {slug}"}), 404

        if admin_wants_html():
            return render_template(
                "admin/product_detail.html",
                product=product,
                error=request.args.get("error"),
                commerce_config=runtime.config,
            )

        return jsonify(product_to_dict(product))

    @bp.patch("/products/<slug>")
    def update_product(slug: str):
        payload = request.get_json(silent=True) or {}

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                updated = catalog.update_product(slug, **payload)

            return jsonify(product_to_dict(updated))

        except (TypeError, ValueError) as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    @bp.post("/products/<slug>/archive")
    def archive_product(slug: str):
        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                archived = catalog.archive_product(slug)

            return jsonify(product_to_dict(archived))

        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    return bp


def _category_slugs_from_payload(payload: dict) -> list[str]:
    if admin_is_form_submission():
        values = request.form.getlist("category_slugs")
    else:
        values = payload.get("category_slugs") or []

    if isinstance(values, str):
        values = [values]

    cleaned: list[str] = []

    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                cleaned.append(item)

    return cleaned


def create_price_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_price_admin", __name__)

    @bp.get("/products/<product_slug>/prices")
    def list_prices(product_slug: str):
        include_archived = request.args.get("include_archived") in {"1", "true", "yes"}
        status = request.args.get("status")

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                prices = catalog.list_prices(
                    product_slug,
                    status=status,
                    include_archived=include_archived,
                )

            return jsonify([price_to_dict(price) for price in prices])

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/products/<product_slug>/prices")
    def create_price(product_slug: str):
        payload = admin_payload()

        try:
            price = ProductPrice(
                code=payload.get("code", ""),
                label=payload.get("label", ""),
                amount=Money(
                    amount_cents=parse_admin_price_amount_from_payload(
                        payload,
                        is_form=admin_is_form_submission(),
                    ),
                    currency=payload.get("currency", "EUR"),
                ),
                status=payload.get("status", "active"),
                billing_mode=payload.get("billing_mode", "one_time"),
                billing_interval=payload.get("billing_interval") or None,
                sort_order=int(payload.get("sort_order", 0) or 0),
                metadata=payload.get("metadata") or {},
            )

            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                created = catalog.create_price(product_slug, price)

            if admin_is_form_submission():
                return redirect(f"/commerce/admin/products/{product_slug}", code=303)

            return jsonify(price_to_dict(created)), 201

        except (TypeError, ValueError) as exc:
            if admin_is_form_submission():
                with runtime.session_scope() as session:
                    catalog = CatalogService(session)
                    product = catalog.get_product(product_slug)

                if product is None:
                    return jsonify({"error": f"product not found: {product_slug}"}), 404

                return render_template(
                    "admin/product_detail.html",
                    product=product,
                    error=str(exc),
                    commerce_config=runtime.config,
                ), 400

            return jsonify({"error": str(exc)}), 400

    @bp.get("/products/<product_slug>/prices/<code>")
    def get_price(product_slug: str, code: str):
        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                price = catalog.get_price(product_slug, code)

            if price is None:
                return jsonify({"error": f"price not found for product {product_slug}: {code}"}), 404

            return jsonify(price_to_dict(price))

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.patch("/products/<product_slug>/prices/<code>")
    def update_price(product_slug: str, code: str):
        payload = request.get_json(silent=True) or {}

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)

                existing = catalog.get_price(product_slug, code)
                if existing is None:
                    return jsonify({"error": f"price not found for product {product_slug}: {code}"}), 404

                changes = {
                    key: payload[key]
                    for key in (
                        "label",
                        "status",
                        "billing_mode",
                        "billing_interval",
                        "sort_order",
                        "metadata",
                    )
                    if key in payload
                }

                if "amount_cents" in payload or "currency" in payload:
                    changes["amount"] = Money(
                        amount_cents=int(payload.get("amount_cents", existing.amount.amount_cents)),
                        currency=payload.get("currency", existing.amount.currency),
                    )

                updated = catalog.update_price(product_slug, code, **changes)

            return jsonify(price_to_dict(updated))

        except (TypeError, ValueError) as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    @bp.post("/products/<product_slug>/prices/<code>/deactivate")
    def deactivate_price(product_slug: str, code: str):
        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                deactivated = catalog.deactivate_price(product_slug, code)

            return jsonify(price_to_dict(deactivated))

        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    @bp.post("/products/<product_slug>/prices/<code>/archive")
    def archive_price(product_slug: str, code: str):
        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                archived = catalog.archive_price(product_slug, code)

            return jsonify(price_to_dict(archived))

        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 400
            return jsonify({"error": message}), status_code

    return bp

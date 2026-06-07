from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, redirect, render_template, request
from werkzeug.datastructures import FileStorage
from sqlalchemy import select

from smx_commerce.catalog import CategoryRepository, CategoryStatus, ProductRepository, ProductStatus
from smx_commerce.checkout import OrderRepository, OrderStatus
from smx_commerce.checkout.models import OrderRow, utc_now
from smx_commerce.core import CommerceRuntime
from smx_commerce.core.settings_repository import CommerceSettingsRepository
from smx_commerce.customers.models import CustomerEntitlementRow, CustomerRow


ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_FAVICON_EXTENSIONS = {".png", ".ico"}

BRANDING_SETTING_KEYS = (
    "host_site_title",
    "host_home_url",
    "store_title",
    "store_home_url",
    "public_base_url",
    "logo_url",
    "favicon_url",
)


def create_admin_home_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint(
        "smx_commerce_admin_home",
        __name__,
        template_folder="../templates",
    )

    @bp.route("/", methods=["GET"], strict_slashes=False)
    def admin_home():
        dashboard_context = _build_dashboard_context(runtime)

        return render_template(
            "admin/home.html",
            commerce_config=_effective_commerce_config(runtime),
            message=request.args.get("message"),
            error=request.args.get("error") or dashboard_context.get("dashboard_error"),
            **dashboard_context,
        )

    @bp.get("/branding")
    def branding_page():
        effective_config = _effective_commerce_config(runtime)

        return render_template(
            "admin/branding.html",
            commerce_config=effective_config,
            branding_settings=_branding_settings_from_config(effective_config),
            message=request.args.get("message"),
            error=request.args.get("error"),
        )

    @bp.post("/branding/settings")
    def save_branding_settings():
        try:
            values = {
                key: (request.form.get(key) or "").strip()
                for key in BRANDING_SETTING_KEYS
            }

            with runtime.session_scope() as session:
                repository = CommerceSettingsRepository(session)

                for key, value in values.items():
                    if value:
                        repository.set(key, value)
                    else:
                        repository.delete(key)

            return redirect("/commerce/admin?message=Branding settings updated.", code=303)

        except ValueError as exc:
            return redirect(f"/commerce/admin?error={str(exc)}", code=303)

        except Exception as exc:
            return redirect(f"/commerce/admin?error=Branding settings could not be saved: {exc}", code=303)

    @bp.post("/branding/assets")
    def upload_branding_assets():
        try:
            assets_dir = Path(runtime.config.assets_dir).resolve()
            assets_dir.mkdir(parents=True, exist_ok=True)

            logo = request.files.get("logo")
            favicon = request.files.get("favicon")

            uploaded_any = False

            if _has_file(logo):
                _save_asset(
                    file=logo,
                    target=assets_dir / "logo.png",
                    allowed_extensions=ALLOWED_LOGO_EXTENSIONS,
                    label="logo",
                )
                uploaded_any = True

            if _has_file(favicon):
                _save_asset(
                    file=favicon,
                    target=assets_dir / "favicon.png",
                    allowed_extensions=ALLOWED_FAVICON_EXTENSIONS,
                    label="favicon",
                )
                uploaded_any = True

            if not uploaded_any:
                return redirect("/commerce/admin?error=No logo or favicon file was selected.", code=303)

            return redirect("/commerce/admin?message=Branding assets updated.", code=303)

        except ValueError as exc:
            return redirect(f"/commerce/admin?error={str(exc)}", code=303)

    return bp


def _effective_commerce_config(runtime: CommerceRuntime) -> SimpleNamespace:
    values = dict(runtime.config.__dict__)

    try:
        with runtime.session_scope() as session:
            settings = CommerceSettingsRepository(session).get_all().as_dict()

        for key in BRANDING_SETTING_KEYS:
            value = settings.get(key)

            if value:
                values[key] = value

    except Exception:
        # If settings are unavailable, keep the runtime/env defaults.
        pass

    return SimpleNamespace(**values)


def _branding_settings_from_config(config: SimpleNamespace) -> dict[str, str]:
    return {
        key: str(getattr(config, key, "") or "")
        for key in BRANDING_SETTING_KEYS
    }


def _build_dashboard_context(runtime: CommerceRuntime) -> dict:
    try:
        with runtime.session_scope() as session:
            orders = OrderRepository(session).list()
            products = ProductRepository(session).list(include_archived=True)
            categories = CategoryRepository(session).list(include_archived=True)
            order_rows = session.execute(
                select(OrderRow).order_by(OrderRow.created_at.desc())
            ).scalars().all()
            customers = session.execute(select(CustomerRow)).scalars().all()
            entitlements = session.execute(select(CustomerEntitlementRow)).scalars().all()

        paid_orders = [order for order in orders if order.status == OrderStatus.PAID]
        revenue_by_currency: dict[str, int] = {}

        for order in paid_orders:
            currency = order.amount.currency.upper()
            revenue_by_currency[currency] = revenue_by_currency.get(currency, 0) + order.amount.amount_cents

        stats = {
            "total_orders": len(orders),
            "pending_orders": sum(1 for order in orders if order.status == OrderStatus.PENDING),
            "paid_orders": len(paid_orders),
            "total_revenue_display": _format_revenue(revenue_by_currency),
            "active_products": sum(1 for product in products if product.status == ProductStatus.ACTIVE),
            "draft_products": sum(1 for product in products if product.status == ProductStatus.DRAFT),
            "category_count": len(categories),
            "customer_count": len(customers),
            "active_entitlements": sum(1 for entitlement in entitlements if entitlement.status == "active"),
        }

        setup_health = _build_setup_health(runtime, database_connected=True)

        return {
            "dashboard_stats": stats,
            "dashboard_charts": _build_dashboard_charts(
                orders=orders,
                products=products,
                categories=categories,
                order_rows=order_rows,
            ),
            "dashboard_health_summary": _summarize_setup_health(setup_health),
            "dashboard_today_snapshot": _build_today_snapshot(order_rows),
            "dashboard_business_kpis": _build_business_kpis(
                orders=orders,
                products=products,
            ),
            "dashboard_catalog_readiness": _build_catalog_readiness(
                products=products,
                categories=categories,
            ),
            "dashboard_operations_feed": _build_operations_feed(
                recent_orders=orders[:5],
                setup_health=setup_health,
            ),
            "recent_orders": orders[:5],
            "setup_health": setup_health,
            "dashboard_error": "",
        }

    except Exception as exc:
        setup_health = _build_setup_health(runtime, database_connected=False)

        return {
            "dashboard_stats": _empty_dashboard_stats(),
            "dashboard_charts": _empty_dashboard_charts(),
            "dashboard_health_summary": _summarize_setup_health(setup_health),
            "dashboard_today_snapshot": _empty_today_snapshot(),
            "dashboard_business_kpis": _empty_business_kpis(),
            "dashboard_catalog_readiness": _empty_catalog_readiness(),
            "dashboard_operations_feed": _build_operations_feed(
                recent_orders=[],
                setup_health=setup_health,
            ),
            "recent_orders": [],
            "setup_health": setup_health,
            "dashboard_error": f"Dashboard data is not available yet: {exc}",
        }








def _empty_catalog_readiness() -> dict[str, object]:
    return {
        "score_percent": 0,
        "passing": 0,
        "total": 0,
        "attention_count": 0,
        "items": [],
    }


def _build_catalog_readiness(*, products: list, categories: list) -> dict[str, object]:
    total_products = len(products)
    active_products = [
        product for product in products
        if product.status == ProductStatus.ACTIVE
    ]
    draft_products = [
        product for product in products
        if product.status == ProductStatus.DRAFT
    ]
    active_categories = [
        category for category in categories
        if category.status == CategoryStatus.ACTIVE
    ]

    active_without_active_price = [
        product for product in active_products
        if not any(price.is_active for price in product.prices)
    ]

    active_without_main_media = [
        product for product in active_products
        if not any(media.is_main for media in product.media)
    ]

    products_without_category = [
        product for product in products
        if not product.category_slugs
    ]

    active_without_category = [
        product for product in active_products
        if not product.category_slugs
    ]

    items = [
        {
            "label": "Products created",
            "ok": total_products > 0,
            "metric": str(total_products),
            "detail": "At least one product exists." if total_products > 0 else "Create the first product before opening the storefront.",
            "action_url": "/commerce/admin/products/new",
        },
        {
            "label": "Active products available",
            "ok": len(active_products) > 0,
            "metric": str(len(active_products)),
            "detail": "Storefront has active products." if active_products else "Publish at least one product for customers.",
            "action_url": "/commerce/admin/products",
        },
        {
            "label": "Active products priced",
            "ok": len(active_without_active_price) == 0,
            "metric": f"{len(active_without_active_price)} missing",
            "detail": "Every active product has at least one active price." if not active_without_active_price else "Some active products cannot sell because they have no active price.",
            "action_url": "/commerce/admin/products",
        },
        {
            "label": "Active products have main images",
            "ok": len(active_without_main_media) == 0,
            "metric": f"{len(active_without_main_media)} missing",
            "detail": "Every active product has a main image." if not active_without_main_media else "Some active products need a main image for a professional storefront.",
            "action_url": "/commerce/admin/products",
        },
        {
            "label": "Products categorized",
            "ok": len(active_without_category) == 0,
            "metric": f"{len(products_without_category)} uncategorized",
            "detail": "Active products are assigned to categories." if not active_without_category else "Some active products are not assigned to any category.",
            "action_url": "/commerce/admin/categories",
        },
        {
            "label": "Active categories available",
            "ok": len(active_categories) > 0,
            "metric": str(len(active_categories)),
            "detail": "At least one active category exists." if active_categories else "Create or activate a category to organize the storefront.",
            "action_url": "/commerce/admin/categories/new",
        },
        {
            "label": "Draft backlog controlled",
            "ok": len(draft_products) <= len(active_products) + 3,
            "metric": str(len(draft_products)),
            "detail": "Draft backlog is within a reasonable range." if len(draft_products) <= len(active_products) + 3 else "There are many draft products compared with active products.",
            "action_url": "/commerce/admin/products",
        },
    ]

    passing = sum(1 for item in items if bool(item["ok"]))
    total = len(items)
    attention_count = total - passing

    return {
        "score_percent": _plain_percent(passing, total),
        "passing": passing,
        "total": total,
        "attention_count": attention_count,
        "items": items,
    }


def _empty_business_kpis() -> dict[str, object]:
    return {
        "paid_rate_display": "0%",
        "average_order_value_display": "EUR 0.00",
        "cart_checkout_share_display": "0%",
        "product_publish_rate_display": "0%",
        "paid_rate_percent": 0,
        "cart_checkout_share_percent": 0,
        "product_publish_rate_percent": 0,
    }


def _build_business_kpis(*, orders: list, products: list) -> dict[str, object]:
    if not orders and not products:
        return _empty_business_kpis()

    total_orders = len(orders)
    paid_orders = [order for order in orders if order.status == OrderStatus.PAID]

    paid_rate_percent = _plain_percent(len(paid_orders), total_orders)

    paid_revenue_by_currency: dict[str, int] = {}

    for order in paid_orders:
        currency = order.amount.currency.upper()
        paid_revenue_by_currency[currency] = (
            paid_revenue_by_currency.get(currency, 0) + order.amount.amount_cents
        )

    average_order_value_display = _format_average_order_value(
        paid_revenue_by_currency=paid_revenue_by_currency,
        paid_order_count=len(paid_orders),
    )

    cart_orders = 0

    for order in orders:
        cart_items = (order.metadata or {}).get("cart_items")

        if isinstance(cart_items, list) and cart_items:
            cart_orders += 1

    cart_checkout_share_percent = _plain_percent(cart_orders, total_orders)

    active_products = sum(1 for product in products if product.status == ProductStatus.ACTIVE)
    product_publish_rate_percent = _plain_percent(active_products, len(products))

    return {
        "paid_rate_display": f"{paid_rate_percent}%",
        "average_order_value_display": average_order_value_display,
        "cart_checkout_share_display": f"{cart_checkout_share_percent}%",
        "product_publish_rate_display": f"{product_publish_rate_percent}%",
        "paid_rate_percent": paid_rate_percent,
        "cart_checkout_share_percent": cart_checkout_share_percent,
        "product_publish_rate_percent": product_publish_rate_percent,
    }


def _format_average_order_value(
    *,
    paid_revenue_by_currency: dict[str, int],
    paid_order_count: int,
) -> str:
    if paid_order_count <= 0 or not paid_revenue_by_currency:
        return "EUR 0.00"

    parts = []

    for currency, amount_cents in sorted(paid_revenue_by_currency.items()):
        average_cents = amount_cents / paid_order_count
        parts.append(f"{currency} {average_cents / 100:.2f}")

    return " ? ".join(parts)


def _plain_percent(value: int, total: int) -> int:
    if total <= 0:
        return 0

    return int(round((value / total) * 100))


def _empty_today_snapshot() -> dict[str, object]:
    return {
        "total_orders": 0,
        "paid_orders": 0,
        "pending_orders": 0,
        "cancelled_orders": 0,
        "failed_orders": 0,
        "revenue_display": "EUR 0.00",
    }


def _build_today_snapshot(order_rows: list) -> dict[str, object]:
    today = utc_now().date()

    snapshot = _empty_today_snapshot()
    revenue_by_currency: dict[str, int] = {}

    for row in order_rows:
        created_date = _date_from_datetime(getattr(row, "created_at", None))

        if created_date != today:
            continue

        snapshot["total_orders"] = int(snapshot["total_orders"]) + 1

        status = getattr(row, "status", "")

        if status == OrderStatus.PAID.value:
            snapshot["paid_orders"] = int(snapshot["paid_orders"]) + 1

            currency = str(getattr(row, "currency", "") or "EUR").upper()
            amount_cents = int(getattr(row, "amount_cents", 0) or 0)
            revenue_by_currency[currency] = revenue_by_currency.get(currency, 0) + amount_cents

        elif status == OrderStatus.PENDING.value:
            snapshot["pending_orders"] = int(snapshot["pending_orders"]) + 1

        elif status == OrderStatus.CANCELLED.value:
            snapshot["cancelled_orders"] = int(snapshot["cancelled_orders"]) + 1

        elif status == OrderStatus.FAILED.value:
            snapshot["failed_orders"] = int(snapshot["failed_orders"]) + 1

    snapshot["revenue_display"] = _format_revenue(revenue_by_currency)

    return snapshot


def _build_operations_feed(
    *,
    recent_orders: list,
    setup_health: list[dict[str, object]],
) -> list[dict[str, str]]:
    feed: list[dict[str, str]] = []

    for item in setup_health:
        if bool(item.get("ok")):
            continue

        feed.append(
            {
                "kind": "Setup",
                "title": str(item.get("label") or "Setup issue"),
                "detail": str(item.get("detail") or "Needs attention."),
                "tone": "warning",
            }
        )

    for order in recent_orders:
        buyer_name = getattr(order.buyer, "full_name", "") or "Unknown buyer"
        buyer_email = getattr(order.buyer, "email", "") or "No email"
        amount = f"{order.amount.currency} {order.amount.amount_cents / 100:.2f}"

        feed.append(
            {
                "kind": "Order",
                "title": f"{order.public_id} ? {order.status.value}",
                "detail": f"{buyer_name} ({buyer_email}) ? {amount}",
                "tone": "info",
            }
        )

    if not feed:
        feed.append(
            {
                "kind": "System",
                "title": "No active alerts",
                "detail": "No setup warnings or recent order activity to show yet.",
                "tone": "ok",
            }
        )

    return feed[:10]


def _summarize_setup_health(setup_health: list[dict[str, object]]) -> dict[str, object]:
    total = len(setup_health)
    passing = sum(1 for item in setup_health if bool(item.get("ok")))
    attention = max(0, total - passing)
    percent = int(round((passing / total) * 100)) if total else 0

    return {
        "passing": passing,
        "total": total,
        "attention": attention,
        "percent": percent,
        "status": "Ready" if attention == 0 else "Needs attention",
    }


def _empty_dashboard_charts() -> dict:
    return {
        "order_status": [],
        "product_status": [],
        "checkout_mix": [],
        "revenue_by_currency": [],
        "category_load": [],
        "daily_order_volume": [],
    }


def _build_dashboard_charts(
    *,
    orders: list,
    products: list,
    categories: list,
    order_rows: list | None = None,
) -> dict:
    order_status_counts = {
        status.value: 0
        for status in OrderStatus
    }

    for order in orders:
        order_status_counts[order.status.value] = order_status_counts.get(order.status.value, 0) + 1

    product_status_counts = {
        status.value: 0
        for status in ProductStatus
    }

    for product in products:
        product_status_counts[product.status.value] = product_status_counts.get(product.status.value, 0) + 1

    checkout_mix_counts = {
        "cart": 0,
        "single": 0,
    }

    for order in orders:
        cart_items = (order.metadata or {}).get("cart_items")
        checkout_kind = "cart" if isinstance(cart_items, list) and cart_items else "single"
        checkout_mix_counts[checkout_kind] = checkout_mix_counts.get(checkout_kind, 0) + 1

    revenue_by_currency: dict[str, int] = {}

    for order in orders:
        if order.status != OrderStatus.PAID:
            continue

        currency = order.amount.currency.upper()
        revenue_by_currency[currency] = revenue_by_currency.get(currency, 0) + order.amount.amount_cents

    category_label_by_slug = {
        category.slug: category.name
        for category in categories
    }

    category_counts = {
        category.slug: 0
        for category in categories
    }
    uncategorized_count = 0

    for product in products:
        if product.category_slugs:
            for category_slug in product.category_slugs:
                category_counts[category_slug] = category_counts.get(category_slug, 0) + 1
        else:
            uncategorized_count += 1

    if uncategorized_count:
        category_counts["uncategorized"] = uncategorized_count
        category_label_by_slug["uncategorized"] = "Uncategorized"

    return {
        "order_status": _chart_entries_from_counts(
            order_status_counts,
            labels={
                "pending": "Pending",
                "paid": "Paid",
                "cancelled": "Cancelled",
                "failed": "Failed",
                "refunded": "Refunded",
            },
            include_zero=True,
        ),
        "product_status": _chart_entries_from_counts(
            product_status_counts,
            labels={
                "draft": "Draft",
                "active": "Active",
                "paused": "Paused",
                "archived": "Archived",
            },
            include_zero=True,
        ),
        "checkout_mix": _chart_entries_from_counts(
            checkout_mix_counts,
            labels={
                "cart": "Cart checkout",
                "single": "Single product",
            },
            include_zero=True,
        ),
        "revenue_by_currency": _money_chart_entries(revenue_by_currency),
        "category_load": _chart_entries_from_counts(
            category_counts,
            labels=category_label_by_slug,
            include_zero=False,
            limit=8,
        ),
        "daily_order_volume": _build_daily_order_volume(order_rows or []),
    }



def _build_daily_order_volume(order_rows: list, *, days: int = 14) -> list[dict[str, object]]:
    today = utc_now().date()
    ordered_days = [
        today - timedelta(days=offset)
        for offset in range(days - 1, -1, -1)
    ]

    daily_counts = {
        day.isoformat(): {
            "date": day.isoformat(),
            "label": day.strftime("%d %b"),
            "total_orders": 0,
            "paid_orders": 0,
            "pending_orders": 0,
        }
        for day in ordered_days
    }

    earliest_day = ordered_days[0]

    for row in order_rows:
        created_date = _date_from_datetime(getattr(row, "created_at", None))

        if created_date is None or created_date < earliest_day:
            continue

        key = created_date.isoformat()

        if key not in daily_counts:
            continue

        daily_counts[key]["total_orders"] += 1

        if getattr(row, "status", "") == OrderStatus.PAID.value:
            daily_counts[key]["paid_orders"] += 1

        if getattr(row, "status", "") == OrderStatus.PENDING.value:
            daily_counts[key]["pending_orders"] += 1

    max_total = max((int(item["total_orders"]) for item in daily_counts.values()), default=0)

    return [
        {
            **item,
            "percent": _chart_percent(int(item["total_orders"]), max_total),
        }
        for item in daily_counts.values()
    ]


def _date_from_datetime(value) -> object | None:
    if value is None:
        return None

    if hasattr(value, "date"):
        return value.date()

    return None


def _chart_entries_from_counts(
    counts: dict[str, int],
    *,
    labels: dict[str, str] | None = None,
    include_zero: bool = False,
    limit: int | None = None,
) -> list[dict[str, object]]:
    labels = labels or {}

    rows = [
        (key, int(value or 0))
        for key, value in counts.items()
        if include_zero or int(value or 0) > 0
    ]

    rows.sort(key=lambda item: (-item[1], labels.get(item[0], item[0])))

    if limit is not None:
        rows = rows[:limit]

    total = sum(value for _, value in rows)

    return [
        {
            "key": key,
            "label": labels.get(key, key.replace("_", " ").replace("-", " ").title()),
            "value": value,
            "display": str(value),
            "percent": _chart_percent(value, total),
        }
        for key, value in rows
    ]


def _money_chart_entries(revenue_by_currency: dict[str, int]) -> list[dict[str, object]]:
    rows = [
        (currency.upper(), int(amount_cents or 0))
        for currency, amount_cents in revenue_by_currency.items()
        if int(amount_cents or 0) > 0
    ]

    rows.sort(key=lambda item: (-item[1], item[0]))

    total = sum(amount_cents for _, amount_cents in rows)

    return [
        {
            "key": currency,
            "label": currency,
            "value": amount_cents,
            "display": f"{currency} {amount_cents / 100:.2f}",
            "percent": _chart_percent(amount_cents, total),
        }
        for currency, amount_cents in rows
    ]


def _chart_percent(value: int, total: int) -> int:
    if total <= 0:
        return 0

    return max(2, int(round((value / total) * 100)))

def _empty_dashboard_stats() -> dict:
    return {
        "total_orders": 0,
        "pending_orders": 0,
        "paid_orders": 0,
        "total_revenue_display": "EUR 0.00",
        "active_products": 0,
        "draft_products": 0,
        "category_count": 0,
        "customer_count": 0,
        "active_entitlements": 0,
    }


def _format_revenue(revenue_by_currency: dict[str, int]) -> str:
    if not revenue_by_currency:
        return "EUR 0.00"

    parts = []

    for currency, amount_cents in sorted(revenue_by_currency.items()):
        parts.append(f"{currency} {amount_cents / 100:.2f}")

    return " · ".join(parts)


def _build_setup_health(runtime: CommerceRuntime, *, database_connected: bool) -> list[dict[str, object]]:
    payment_provider = (_first_env("SMX_COMMERCE_PAYMENT_PROVIDER") or "none").lower()
    stripe_secret_key = _first_env("SMX_COMMERCE_STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY")
    stripe_webhook_secret = _first_env("SMX_COMMERCE_STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET")

    email_provider = (_first_env("SMX_COMMERCE_EMAIL_PROVIDER") or "none").lower()
    smtp_host = _first_env("SMX_COMMERCE_SMTP_HOST", "SMX_SMTP_HOST")
    smtp_port = _first_env("SMX_COMMERCE_SMTP_PORT", "SMX_SMTP_PORT")
    smtp_username = _first_env("SMX_COMMERCE_SMTP_USERNAME", "SMX_SMTP_USERNAME")
    smtp_password = _first_env("SMX_COMMERCE_SMTP_PASSWORD", "SMX_SMTP_PASSWORD")
    smtp_from = _first_env("SMX_COMMERCE_DEFAULT_FROM_EMAIL", "SMX_SMTP_FROM_EMAIL")

    assets_dir = Path(runtime.config.assets_dir)
    products_assets_dir = Path(runtime.config.products_assets_dir)
    receipts_dir = Path(runtime.config.receipts_dir)

    stripe_checkout_configured = payment_provider == "stripe" and bool(stripe_secret_key)
    stripe_webhook_configured = payment_provider == "stripe" and bool(stripe_webhook_secret)
    smtp_configured = email_provider == "smtp" and bool(smtp_host and smtp_port and smtp_from)

    logo_present = (assets_dir / "logo.png").exists()
    favicon_present = (assets_dir / "favicon.png").exists()

    admin_protected = bool(runtime.config.admin_token)
    public_base_configured = bool(runtime.config.public_base_url)
    host_home_configured = bool(runtime.config.host_home_url)
    store_home_configured = bool(runtime.config.store_home_url)

    return [
        {
            "label": "Database connected",
            "ok": database_connected,
            "detail": "Commerce database is reachable." if database_connected else "Commerce database could not be reached.",
        },
        {
            "label": "Admin protection configured",
            "ok": admin_protected,
            "detail": "Admin token is present." if admin_protected else "Set SMX_COMMERCE_ADMIN_TOKEN before exposing admin routes.",
        },
        {
            "label": "Public base URL configured",
            "ok": public_base_configured,
            "detail": "Public base URL is available for customer links." if public_base_configured else "Set SMX_COMMERCE_PUBLIC_BASE_URL or PUBLIC_BASE_URL for production links.",
        },
        {
            "label": "Host home URL configured",
            "ok": host_home_configured,
            "detail": f"Host home URL is {runtime.config.host_home_url}." if host_home_configured else "Set the host home URL.",
        },
        {
            "label": "Store home URL configured",
            "ok": store_home_configured,
            "detail": f"Store home URL is {runtime.config.store_home_url}." if store_home_configured else "Set the store home URL.",
        },
        {
            "label": "Payment provider selected",
            "ok": payment_provider in {"none", "stripe", "local"},
            "detail": f"Payment provider is {payment_provider}." if payment_provider else "Set SMX_COMMERCE_PAYMENT_PROVIDER.",
        },
        {
            "label": "Stripe checkout configured",
            "ok": stripe_checkout_configured,
            "detail": "Stripe checkout secret is present." if stripe_checkout_configured else "Set SMX_COMMERCE_PAYMENT_PROVIDER=stripe and provide the Stripe secret key before live Stripe checkout.",
        },
        {
            "label": "Stripe webhook configured",
            "ok": stripe_webhook_configured,
            "detail": "Stripe webhook secret is present." if stripe_webhook_configured else "Provide the Stripe webhook secret before live payment use.",
        },
        {
            "label": "Email provider selected",
            "ok": email_provider in {"none", "smtp"},
            "detail": f"Email provider is {email_provider}." if email_provider else "Set SMX_COMMERCE_EMAIL_PROVIDER.",
        },
        {
            "label": "SMTP host configured",
            "ok": email_provider != "smtp" or bool(smtp_host),
            "detail": "SMTP host is present." if smtp_host else "Set SMX_COMMERCE_SMTP_HOST when using SMTP email.",
        },
        {
            "label": "SMTP port configured",
            "ok": email_provider != "smtp" or bool(smtp_port),
            "detail": f"SMTP port is {smtp_port}." if smtp_port else "Set SMX_COMMERCE_SMTP_PORT when using SMTP email.",
        },
        {
            "label": "SMTP sender configured",
            "ok": email_provider != "smtp" or bool(smtp_from),
            "detail": "SMTP sender email is present." if smtp_from else "Set SMX_COMMERCE_DEFAULT_FROM_EMAIL or SMX_SMTP_FROM_EMAIL.",
        },
        {
            "label": "SMTP credentials configured",
            "ok": email_provider != "smtp" or bool(smtp_username or smtp_password),
            "detail": "SMTP username or password is present." if (smtp_username or smtp_password) else "Set SMTP credentials when your SMTP provider requires authentication.",
        },
        {
            "label": "SMTP/email configured",
            "ok": smtp_configured,
            "detail": "SMTP host, port, and sender are present." if smtp_configured else "Set SMTP provider, host, port, and sender email to send order confirmations.",
        },
        {
            "label": "Assets directory writable",
            "ok": _directory_writable(assets_dir),
            "detail": f"Assets directory is writable: {assets_dir}." if _directory_writable(assets_dir) else f"Assets directory is not writable: {assets_dir}.",
        },
        {
            "label": "Product media directory writable",
            "ok": _directory_writable(products_assets_dir),
            "detail": f"Product media directory is writable: {products_assets_dir}." if _directory_writable(products_assets_dir) else f"Product media directory is not writable: {products_assets_dir}.",
        },
        {
            "label": "Receipts directory writable",
            "ok": _directory_writable(receipts_dir),
            "detail": f"Receipts directory is writable: {receipts_dir}." if _directory_writable(receipts_dir) else f"Receipts directory is not writable: {receipts_dir}.",
        },
        {
            "label": "Logo present",
            "ok": logo_present,
            "detail": "Logo file exists in the commerce assets directory." if logo_present else "Upload a logo from Branding & Store Settings.",
        },
        {
            "label": "Favicon present",
            "ok": favicon_present,
            "detail": "Favicon file exists in the commerce assets directory." if favicon_present else "Upload a favicon from Branding & Store Settings.",
        },
    ]


def _directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".smx_commerce_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False

def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _has_file(file: FileStorage | None) -> bool:
    return file is not None and bool(file.filename)


def _save_asset(
    *,
    file: FileStorage,
    target: Path,
    allowed_extensions: set[str],
    label: str,
) -> None:
    original_name = file.filename or ""
    extension = Path(original_name).suffix.lower()

    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"Invalid {label} file type. Allowed: {allowed}")

    target.parent.mkdir(parents=True, exist_ok=True)

    # Always store canonical names. Existing logo/favicon are intentionally replaced
    # only when the admin uploads a new file.
    file.save(target)
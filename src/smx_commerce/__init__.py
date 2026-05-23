from __future__ import annotations

from flask import Blueprint, render_template, send_from_directory

from smx_commerce.admin import apply_admin_api_key_guard, create_admin_auth_blueprint, create_admin_home_blueprint, create_settings_admin_blueprint, create_product_edit_admin_blueprint, create_price_edit_admin_blueprint, create_category_edit_admin_blueprint, create_safe_delete_admin_blueprint, create_order_edit_admin_blueprint, create_product_edit_admin_blueprint
from smx_commerce.catalog.routes_admin import (
    create_category_admin_blueprint,
    create_price_admin_blueprint,
    create_product_admin_blueprint,
)
from smx_commerce.catalog.routes_public import create_public_catalog_blueprint
from smx_commerce.checkout.routes import create_checkout_blueprint
from smx_commerce.checkout.routes_admin import create_order_admin_blueprint
from smx_commerce.core import CommerceRuntime
from smx_commerce.env_config import build_commerce_config_from_env, load_env_file
from smx_commerce.notifications import (
    MemoryEmailSender,
    OrderConfirmationEmailService,
    SMTPEmailSender,
)
from smx_commerce.payments import (
    LocalCheckoutProvider,
    PaymentCheckoutProvider,
    StaticSignatureWebhookVerifier,
    StripeCheckoutProvider,
)
from smx_commerce.payments.routes import create_payment_webhook_blueprint
from smx_commerce.payments.verifiers import PaymentWebhookVerifier
from smx_commerce.scaffold import ensure_smxcommerce_scaffold

def create_commerce_blueprint(
    config=None,
    runtime: CommerceRuntime | None = None,
    init_schema: bool = False,
    payment_webhook_verifier: PaymentWebhookVerifier | None = None,
    payment_checkout_provider: PaymentCheckoutProvider | None = None,
    order_confirmation_service: OrderConfirmationEmailService | None = None,
    admin_api_key: str | None = None,
):
    commerce_runtime = runtime or CommerceRuntime.from_mapping(config)

    if init_schema:
        commerce_runtime.init_schema()

    resolved_admin_api_key = admin_api_key
    if resolved_admin_api_key is None:
        resolved_admin_api_key = commerce_runtime.config.admin_api_key

    bp = Blueprint("smx_commerce", __name__)

    @bp.get("/commerce/health")
    def commerce_health():
        return {
            "status": "ok",
            "package": "smx-commerce",
        }
    
    @bp.get("/commerce/assets/<path:filename>")
    def commerce_asset(filename: str):
        return send_from_directory(
            commerce_runtime.config.assets_dir,
            filename,
        )
    

    @bp.get("/commerce")
    def commerce_home():
        return render_template(
            "public/commerce_home.html",
            commerce_config=commerce_runtime.config,
        )

    bp.register_blueprint(create_public_catalog_blueprint(commerce_runtime))
    bp.register_blueprint(
        create_checkout_blueprint(
            commerce_runtime,
            payment_checkout_provider=payment_checkout_provider,
        )
    )
    bp.register_blueprint(
        create_payment_webhook_blueprint(
            commerce_runtime,
            verifier=payment_webhook_verifier,
            order_confirmation_service=order_confirmation_service,
        )
    )

    admin_bp = Blueprint("smx_commerce_admin", __name__)
    apply_admin_api_key_guard(admin_bp, resolved_admin_api_key)

    admin_bp.register_blueprint(
        create_admin_auth_blueprint(
            resolved_admin_api_key,
            commerce_runtime.config,
        )
    )

    admin_bp.register_blueprint(create_admin_home_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_category_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_category_edit_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_safe_delete_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_product_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_product_edit_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_price_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_price_edit_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_order_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_order_edit_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_settings_admin_blueprint(commerce_runtime))

    bp.register_blueprint(admin_bp, url_prefix="/commerce/admin")

    return bp


def init_commerce(app, *, config=None, init_schema: bool = False):
    resolved_config = config or {}

    if resolved_config.get("flask_secret_key") and not app.secret_key:
        app.config["SECRET_KEY"] = resolved_config["flask_secret_key"]

    app.register_blueprint(
        create_commerce_blueprint(
            config=resolved_config,
            init_schema=init_schema,
            payment_checkout_provider=_build_checkout_provider(resolved_config),
            payment_webhook_verifier=_build_webhook_verifier(resolved_config),
            order_confirmation_service=_build_order_confirmation_service(resolved_config),
        )
    )

    return app


def init_commerce_from_env(
    app,
    *,
    env_file: str = ".env.smx-commerce",
    init_schema: bool = False,
    prefix: str = "SMX_COMMERCE_",
):
    config = build_commerce_config_from_env(
        env_file=env_file,
        prefix=prefix,
    )

    return init_commerce(
        app,
        config=config,
        init_schema=init_schema,
    )


def setup_commerce(
    app,
    *,
    project_root=None,
    init_schema: bool = True,
):
    scaffold = ensure_smxcommerce_scaffold(project_root=project_root)

    return init_commerce_from_env(
        app,
        env_file=scaffold.env_file,
        init_schema=init_schema,
    )


def _build_checkout_provider(config: dict):
    provider = config.get("payment_provider")

    if provider in {None, "", "none"}:
        return None

    if provider == "local":
        return LocalCheckoutProvider(
            checkout_base_url=config.get(
                "local_checkout_base_url",
                "https://local-payments.invalid/checkout",
            )
        )

    if provider == "stripe":
        return StripeCheckoutProvider(
            api_key=config["stripe_secret_key"],
        )

    raise ValueError(f"unsupported payment_provider: {provider}")


def _build_webhook_verifier(config: dict):
    provider = config.get("payment_provider")

    if provider in {None, "", "none"}:
        return None

    if provider == "local":
        return StaticSignatureWebhookVerifier(
            expected_signature=config.get("local_webhook_signature", "local-signature"),
        )

    if provider == "stripe":
        return __import__(
            "smx_commerce.payments",
            fromlist=["StripeWebhookVerifier"],
        ).StripeWebhookVerifier(
            webhook_secret=config["stripe_webhook_secret"],
        )

    raise ValueError(f"unsupported payment_provider: {provider}")


def _build_order_confirmation_service(config: dict):
    email_provider = config.get("email_provider")

    if email_provider in {None, "", "none"}:
        return None

    if email_provider == "memory":
        sender = MemoryEmailSender()
    elif email_provider == "smtp":
        sender = SMTPEmailSender(
            host=config["smtp_host"],
            port=int(config.get("smtp_port", 587)),
            default_from_email=config.get("default_from_email"),
            username=config.get("smtp_username"),
            password=config.get("smtp_password"),
            use_tls=bool(config.get("smtp_use_tls", True)),
            use_ssl=bool(config.get("smtp_use_ssl", False)),
        )
    else:
        raise ValueError(f"unsupported email_provider: {email_provider}")

    return OrderConfirmationEmailService(
        sender,
        from_email=config.get("default_from_email"),
        brand_name=config.get("site_title") or "SyntaxMatrix",
    )


__all__ = [
    "build_commerce_config_from_env",
    "create_commerce_blueprint",
    "init_commerce",
    "init_commerce_from_env",
    "load_env_file",
    "ensure_smxcommerce_scaffold",
    "setup_commerce",
]

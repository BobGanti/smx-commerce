from __future__ import annotations
from pathlib import Path

from flask import Blueprint, redirect, render_template, request, send_from_directory

from smx_commerce.admin.customers import create_customer_admin_blueprint
from smx_commerce.ai import CommerceAIClient, load_gemini_env_client
from smx_commerce.admin import apply_admin_token_guard, create_admin_auth_blueprint, create_admin_home_blueprint, create_settings_admin_blueprint, create_product_edit_admin_blueprint, create_price_edit_admin_blueprint, create_category_edit_admin_blueprint, create_safe_delete_admin_blueprint, create_order_edit_admin_blueprint, create_product_edit_admin_blueprint
from smx_commerce.catalog.routes_admin import (
    create_category_admin_blueprint,
    create_price_admin_blueprint,
    create_product_admin_blueprint,
)
from smx_commerce.catalog.routes_public import create_public_catalog_blueprint
from smx_commerce.checkout.routes import create_checkout_blueprint
from smx_commerce.checkout.routes_admin import create_order_admin_blueprint
from smx_commerce.customers.access import customer_has_active_entitlement, get_customer_active_entitlement
from smx_commerce.customers.emailer import CustomerLoginEmailService
from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.routes import create_customer_auth_blueprint
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
from smx_commerce.smxcp import ensure_commerce_scaffold
from smx_commerce.support import SupportRepository

def create_commerce_blueprint(
    config=None,
    runtime: CommerceRuntime | None = None,
    init_schema: bool = False,
    payment_webhook_verifier: PaymentWebhookVerifier | None = None,
    payment_checkout_provider: PaymentCheckoutProvider | None = None,
    order_confirmation_service: OrderConfirmationEmailService | None = None,
    customer_login_email_service: CustomerLoginEmailService | None = None,
    admin_token: str | None = None,
    ai_client: CommerceAIClient | None = None,
):
    commerce_runtime = runtime or CommerceRuntime.from_mapping(config)

    if init_schema:
        commerce_runtime.init_schema()

    commerce_runtime.ai_client = ai_client or load_gemini_env_client()

    resolved_admin_token = admin_token
    if resolved_admin_token is None:
        resolved_admin_token = commerce_runtime.config.admin_token

    bp = Blueprint("smx_commerce", __name__)
    bp.ai_client = commerce_runtime.ai_client

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
    

    @bp.get("/commerce/static/<path:filename>")
    def commerce_static(filename: str):
        return send_from_directory(
            Path(__file__).resolve().parent / "static",
            filename,
        )


    @bp.get("/commerce")
    def commerce_home():
        return render_template(
            "public/commerce_home.html",
            commerce_config=commerce_runtime.config,
        )

    @bp.get("/commerce/support")
    def commerce_support_form():
        return render_template(
            "public/support.html",
            commerce_config=commerce_runtime.config,
            form_data={},
            error="",
        )
    @bp.post("/commerce/support/submit")
    def commerce_support_submit():
        try:
            with commerce_runtime.session_scope() as session:
                repository = SupportRepository(session)
                thread = repository.create_thread(
                    customer_email=request.form.get("customer_email", ""),
                    customer_name=request.form.get("customer_name", ""),
                    subject=request.form.get("subject", ""),
                    order_public_id=request.form.get("order_public_id", ""),
                    source="public_support",
                    metadata={"entrypoint": "/commerce/support"},
                )
                repository.add_customer_message(
                    thread.public_id,
                    body=request.form.get("message", ""),
                    sender_name=request.form.get("customer_name", ""),
                    sender_email=request.form.get("customer_email", ""),
                    metadata={"entrypoint": "/commerce/support"},
                )
        except (TypeError, ValueError) as exc:
            return render_template(
                "public/support.html",
                commerce_config=commerce_runtime.config,
                form_data=dict(request.form),
                error=str(exc),
            ), 400

        return redirect(
            f"/commerce/support?submitted=1&thread_id={thread.public_id}",
            code=303,
        )
    bp.register_blueprint(create_public_catalog_blueprint(commerce_runtime))
    bp.register_blueprint(
        create_customer_auth_blueprint(
            commerce_runtime,
            customer_login_email_service=customer_login_email_service,
        )
    )
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
    apply_admin_token_guard(admin_bp, resolved_admin_token)

    admin_bp.register_blueprint(
        create_admin_auth_blueprint(
            resolved_admin_token,
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
    admin_bp.register_blueprint(create_customer_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_order_edit_admin_blueprint(commerce_runtime))
    admin_bp.register_blueprint(create_settings_admin_blueprint(commerce_runtime))

    bp.register_blueprint(admin_bp, url_prefix="/commerce/admin")

    return bp


def init_commerce(app, *, config=None, init_schema: bool = False, ai_client: CommerceAIClient | None = None):
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
            customer_login_email_service=_build_customer_login_email_service(resolved_config),
            ai_client=ai_client,
        )
    )

    return app


def init_commerce_from_env(
    app,
    *,
    env_file: str = "commerce/.smx_commerce.env",
    init_schema: bool = False,
    prefix: str = "SMX_COMMERCE_",
    ai_client: CommerceAIClient | None = None,
):
    config = build_commerce_config_from_env(
        env_file=env_file,
        prefix=prefix,
    )

    return init_commerce(
        app,
        config=config,
        init_schema=init_schema,
        ai_client=ai_client,
    )


def setup_commerce(
    app,
    *,
    project_root=None,
    init_schema: bool = True,
    ai_client: CommerceAIClient | None = None,
):
    scaffold = ensure_commerce_scaffold(project_root=project_root)

    return init_commerce_from_env(
        app,
        env_file=scaffold.env_file,
        init_schema=init_schema,
        ai_client=ai_client,
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



def _build_email_sender(config: dict):
    email_provider = config.get("email_provider")

    if email_provider in {None, "", "none"}:
        return None

    if email_provider == "memory":
        return MemoryEmailSender()

    if email_provider == "smtp":
        return SMTPEmailSender(
            host=config["smtp_host"],
            port=int(config.get("smtp_port", 587)),
            default_from_email=config.get("default_from_email"),
            username=config.get("smtp_username"),
            password=config.get("smtp_password"),
            use_tls=bool(config.get("smtp_use_tls", True)),
            use_ssl=bool(config.get("smtp_use_ssl", False)),
        )

    raise ValueError(f"unsupported email_provider: {email_provider}")


def _build_customer_login_email_service(config: dict):
    sender = _build_email_sender(config)

    if sender is None:
        return None

    return CustomerLoginEmailService(
        sender,
        from_email=config.get("default_from_email"),
        store_title=config.get("store_title") or "smxCommerce",
    )


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

    assets_dir = Path(config.get("assets_dir") or "./commerce/assets")
    receipts_dir = config.get("receipts_dir") or str(assets_dir / "receipts")
    logo_path = assets_dir / "logo.png"

    return OrderConfirmationEmailService(
        sender,
        from_email=config.get("default_from_email"),
        brand_name=config.get("site_title") or "SyntaxMatrix",
        receipts_dir=receipts_dir,
        logo_path=str(logo_path),
    )


__all__ = [
    "build_commerce_config_from_env",
    "create_commerce_blueprint",
    "init_commerce",
    "init_commerce_from_env",
    "load_env_file",
    "ensure_commerce_scaffold",
    "setup_commerce",
    "customer_has_active_entitlement",
    "get_customer_active_entitlement",
]

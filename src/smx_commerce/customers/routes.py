from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, jsonify, make_response, redirect, render_template, request

from smx_commerce.core import CommerceRuntime
from smx_commerce.checkout.repository import OrderRepository
from smx_commerce.customers.emailer import CustomerLoginEmailService
from smx_commerce.customers.objects import CustomerAuthTokenPurpose
from smx_commerce.customers.repository import CustomerRepository


CUSTOMER_SESSION_COOKIE = "smx_commerce_customer_session"
CUSTOMER_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def create_customer_auth_blueprint(
    runtime: CommerceRuntime,
    *,
    customer_login_email_service: CustomerLoginEmailService | None = None,
) -> Blueprint:
    bp = Blueprint(
        "smx_commerce_customer_auth",
        __name__,
        template_folder="../templates",
    )

    @bp.get("/commerce/customer/login")
    def login():
        if _wants_html():
            return render_template(
                "public/customer_login.html",
                commerce_config=runtime.config,
            )

        return jsonify({"status": "ok", "message": "customer login is available"})

    @bp.post("/commerce/customer/login")
    def submit_login():
        email = (request.form.get("email") or (request.get_json(silent=True) or {}).get("email") or "").strip()
        full_name = (request.form.get("full_name") or (request.get_json(silent=True) or {}).get("full_name") or "").strip()
        next_url = _safe_next_url(
            request.form.get("next")
            or request.args.get("next")
            or (request.get_json(silent=True) or {}).get("next")
        )

        if not email:
            return _login_error("Email is required", status_code=400)

        if customer_login_email_service is None:
            return _login_error("Customer login email is not configured", status_code=503)

        public_base_url = _public_base_url(runtime)

        with runtime.session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get_or_create_from_identity(
                email=email,
                full_name=full_name,
                metadata={"login_source": "customer_portal"},
            )
            issued = repo.create_auth_token(
                customer_public_id=customer.public_id,
                purpose=CustomerAuthTokenPurpose.LOGIN,
            )

        result = customer_login_email_service.send_login_link(
            to_email=email,
            token=issued.token,
            public_base_url=public_base_url,
            next_url=next_url,
        )

        if not result.sent:
            return _login_error("Could not send login email. Please try again later.", status_code=502)

        payload = {
            "status": "ok",
            "message": "If the email address can receive messages, a secure sign-in link has been sent.",
        }

        if _wants_html():
            return render_template(
                "public/customer_login.html",
                commerce_config=runtime.config,
                success=payload["message"],
            )

        return jsonify(payload)

    @bp.get("/commerce/customer/verify")
    def verify():
        token = (request.args.get("token") or "").strip()
        next_url = _safe_next_url(request.args.get("next")) or "/commerce"

        if not token:
            return _verify_error("Missing login token", status_code=400)

        with runtime.session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.verify_auth_token(
                token=token,
                purpose=CustomerAuthTokenPurpose.LOGIN,
            )

            if customer is None:
                return _verify_error("Invalid or expired login link", status_code=401)

            issued_session = repo.create_session(customer_public_id=customer.public_id)

        if _wants_html():
            response = make_response(redirect(next_url, code=303))
        else:
            response = make_response(jsonify({"status": "ok", "authenticated": True}))

        response.set_cookie(
            CUSTOMER_SESSION_COOKIE,
            issued_session.session_token,
            max_age=CUSTOMER_SESSION_MAX_AGE_SECONDS,
            httponly=True,
            secure=request.is_secure,
            samesite="Lax",
            path="/commerce",
        )

        return response

    @bp.get("/commerce/customer/account")
    def account():
        session_token = request.cookies.get(CUSTOMER_SESSION_COOKIE)

        if not session_token:
            return _customer_auth_required()

        with runtime.session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get_customer_by_session_token(session_token)

            if customer is None:
                return _customer_auth_required(clear_cookie=True)

            orders = OrderRepository(session).list_by_customer_public_id(customer.public_id)
            entitlements = repo.list_entitlements(customer.public_id)

        if _wants_html():
            return render_template(
                "public/customer_account.html",
                commerce_config=runtime.config,
                customer=customer,
                orders=orders,
                entitlements=entitlements,
            )

        return jsonify(
            {
                "status": "ok",
                "customer": {
                    "public_id": customer.public_id,
                    "email": customer.email,
                    "full_name": customer.full_name,
                    "phone": customer.phone,
                    "company": customer.company,
                    "status": customer.status.value,
                },
                "orders": [
                    {
                        "public_id": order.public_id,
                        "product_slug": order.product_slug,
                        "price_code": order.price_code,
                        "status": order.status.value,
                        "amount_cents": order.amount.amount_cents,
                        "currency": order.amount.currency,
                    }
                    for order in orders
                ],
                "entitlements": [
                    {
                        "public_id": entitlement.public_id,
                        "order_public_id": entitlement.order_public_id,
                        "product_slug": entitlement.product_slug,
                        "price_code": entitlement.price_code,
                        "entitlement_type": entitlement.entitlement_type.value,
                        "status": entitlement.status.value,
                    }
                    for entitlement in entitlements
                ],
            }
        )

    @bp.post("/commerce/customer/logout")
    def logout():
        session_token = request.cookies.get(CUSTOMER_SESSION_COOKIE)

        if session_token:
            with runtime.session_scope() as session:
                CustomerRepository(session).revoke_session(session_token)

        if _wants_html():
            response = make_response(redirect("/commerce", code=303))
        else:
            response = make_response(jsonify({"status": "ok", "authenticated": False}))

        response.delete_cookie(
            CUSTOMER_SESSION_COOKIE,
            path="/commerce",
        )

        return response


    return bp



def _customer_auth_required(*, clear_cookie: bool = False):
    if _wants_html():
        response = make_response(
            redirect("/commerce/customer/login?next=/commerce/customer/account", code=303)
        )
    else:
        response = make_response(jsonify({"error": "customer authentication required"}), 401)

    if clear_cookie:
        response.delete_cookie(
            CUSTOMER_SESSION_COOKIE,
            path="/commerce",
        )

    return response


def _public_base_url(runtime: CommerceRuntime) -> str:
    configured = runtime.config.public_base_url
    if configured:
        return configured.rstrip("/")

    return request.url_root.rstrip("/")


def _safe_next_url(value: str | None) -> str | None:
    candidate = (value or "").strip()

    if not candidate:
        return None

    parsed = urlparse(candidate)

    if parsed.scheme or parsed.netloc:
        return None

    if not candidate.startswith("/"):
        return None

    return candidate


def _login_error(message: str, *, status_code: int):
    if _wants_html():
        return render_template(
            "public/customer_login.html",
            commerce_config=None,
            error=message,
        ), status_code

    return jsonify({"error": message}), status_code


def _verify_error(message: str, *, status_code: int):
    if _wants_html():
        return render_template(
            "public/customer_login.html",
            commerce_config=None,
            error=message,
        ), status_code

    return jsonify({"error": message}), status_code


def _wants_html() -> bool:
    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"

from __future__ import annotations

from hmac import compare_digest
from types import SimpleNamespace
from typing import Any

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for


ADMIN_TOKEN_HEADER = "X-SMX-Commerce-Admin-Token"
ADMIN_API_KEY_HEADER = "X-SMX-Commerce-Admin-Key"
ADMIN_SESSION_TOKEN = "smx_commerce_admin_authenticated"


def apply_admin_token_guard(bp: Blueprint, admin_token: str | None) -> None:
    """
    Protect admin routes when admin_token is configured.

    Accepted auth methods:
    1. X-SMX-Commerce-Admin-Token header, useful for API clients/tests.
    2. Session login through /commerce/admin/login, useful for browser admin UX.

    If no token is configured, the guard is inactive.
    """
    if not admin_token:
        return

    expected_token = admin_token.strip()

    @bp.before_request
    def require_admin_auth():
        if _is_auth_route():
            return None

        supplied_token = request.headers.get(ADMIN_TOKEN_HEADER, "") or request.headers.get(ADMIN_API_KEY_HEADER, "")

        if supplied_token and compare_digest(supplied_token, expected_token):
            return None

        if session.get(ADMIN_SESSION_TOKEN) is True:
            return None

        if _wants_html():
            return redirect(url_for("smx_commerce.smx_commerce_admin.smx_commerce_admin_auth.login"))

        return jsonify({"error": "admin authentication required"}), 401

    return None


def create_admin_auth_blueprint(
    admin_token: str | None,
    commerce_config: Any | None = None,
) -> Blueprint:
    bp = Blueprint(
        "smx_commerce_admin_auth",
        __name__,
        template_folder="../templates",
    )

    branding = commerce_config or _default_commerce_config()

    @bp.get("/login")
    def login():
        if not admin_token:
            return jsonify({"status": "ok", "message": "admin authentication is not configured"})

        if request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html":
            return render_template(
                "admin/login.html",
                commerce_config=branding,
            )

        return jsonify({"status": "ok", "message": "admin login is available"})

    @bp.post("/login")
    def submit_login():
        if not admin_token:
            return jsonify({"status": "ok", "message": "admin authentication is not configured"})

        if not current_app.secret_key:
            return jsonify({"error": "Flask secret_key is required for admin session login"}), 500

        payload = request.get_json(silent=True) or {}
        supplied_token = request.form.get("admin_token") or request.form.get("admin_api_key") or payload.get("admin_token") or payload.get("admin_api_key") or ""

        if not compare_digest(supplied_token, admin_token):
            if _wants_html():
                return render_template(
                    "admin/login.html",
                    commerce_config=branding,
                    error="Invalid admin key",
                ), 401

            return jsonify({"error": "invalid admin key"}), 401

        session[ADMIN_SESSION_TOKEN] = True

        if _wants_html():
            return redirect("/commerce/admin/products", code=303)

        return jsonify({"status": "ok", "authenticated": True})

    @bp.post("/logout")
    def logout():
        session.pop(ADMIN_SESSION_TOKEN, None)

        if _wants_html():
            return redirect("/commerce/admin/login", code=303)

        return jsonify({"status": "ok", "authenticated": False})

    return bp


def _default_commerce_config():
    return SimpleNamespace(
        project_title="Commerce",
        project_home_url="/",
        logo_url=None,
        favicon_url=None,
    )


def _is_auth_route() -> bool:
    path = request.path.rstrip("/")
    return path.endswith("/commerce/admin/login") or path.endswith("/commerce/admin/logout")


def _wants_html() -> bool:
    content_type = request.content_type or ""

    if "application/x-www-form-urlencoded" in content_type:
        return True

    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"
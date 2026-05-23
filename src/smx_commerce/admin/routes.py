from __future__ import annotations

from flask import Blueprint, jsonify, request

from smx_commerce.core import CommerceRuntime
from smx_commerce.core.settings_repository import CommerceSettingsRepository


def create_settings_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_settings_admin", __name__)

    @bp.get("/settings")
    def get_settings():
        with runtime.session_scope() as session:
            settings = CommerceSettingsRepository(session).get_all()

        return jsonify(settings.as_dict())

    @bp.patch("/settings")
    def update_settings():
        payload = request.get_json(silent=True) or {}

        try:
            with runtime.session_scope() as session:
                settings = CommerceSettingsRepository(session).set_many(payload)

            return jsonify(settings.as_dict())

        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    return bp

from flask import Flask

from smx_commerce import create_commerce_blueprint, init_commerce


def test_create_commerce_blueprint_accepts_ai_profile():
    provider_client = object()
    ai_profile = {
        "provider": "google",
        "model": "gemini-2.0-flash",
        "api_key": "redacted",
        "client": provider_client,
    }

    blueprint = create_commerce_blueprint(
        config={},
        ai_profile=ai_profile,
    )

    assert blueprint.ai_profile is ai_profile
    assert blueprint.ai_profile["provider"] == "google"
    assert blueprint.ai_profile["client"] is provider_client


def test_init_commerce_forwards_ai_profile_to_registered_blueprint():
    provider_client = object()
    ai_profile = {
        "provider": "google",
        "model": "gemini-2.0-flash",
        "api_key": "redacted",
        "client": provider_client,
    }

    app = Flask(__name__)

    init_commerce(
        app,
        config={},
        init_schema=False,
        ai_profile=ai_profile,
    )

    blueprint = app.blueprints["smx_commerce"]

    assert blueprint.ai_profile is ai_profile
    assert blueprint.ai_profile["provider"] == "google"
    assert blueprint.ai_profile["client"] is provider_client

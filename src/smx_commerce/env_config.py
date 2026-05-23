from __future__ import annotations

from pathlib import Path
import os
from typing import Any


ENV_TO_CONFIG = {
    "DATABASE_URL": "database_url",
    "ECHO_SQL": "echo_sql",
    "ADMIN_API_KEY": "admin_api_key",
    "PAYMENT_PROVIDER": "payment_provider",
    "LOCAL_CHECKOUT_BASE_URL": "local_checkout_base_url",
    "LOCAL_WEBHOOK_SIGNATURE": "local_webhook_signature",
    "STRIPE_SECRET_KEY": "stripe_secret_key",
    "STRIPE_WEBHOOK_SECRET": "stripe_webhook_secret",
    "EMAIL_PROVIDER": "email_provider",
    "SMTP_HOST": "smtp_host",
    "SMTP_PORT": "smtp_port",
    "SMTP_USERNAME": "smtp_username",
    "SMTP_PASSWORD": "smtp_password",
    "SMTP_USE_TLS": "smtp_use_tls",
    "SMTP_USE_SSL": "smtp_use_ssl",
    "DEFAULT_FROM_EMAIL": "default_from_email",
    "PROJECT_HOME_URL": "project_home_url",
    "LOGO_URL": "logo_url",
    "FAVICON_URL": "favicon_url",
    "SITE_TITLE": "site_title",
    "MODULE_TITLE": "module_title",
    "ASSETS_DIR": "assets_dir",
    "FLASK_SECRET_KEY": "flask_secret_key",
}

BOOLEAN_CONFIG_KEYS = {
    "echo_sql",
    "smtp_use_tls",
    "smtp_use_ssl",
}


INTEGER_CONFIG_KEYS = {
    "smtp_port",
}


def load_env_file(env_file: str | os.PathLike[str] | None) -> dict[str, str]:
    if not env_file:
        return {}

    path = Path(env_file)

    if not path.exists():
        return {}

    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export "):].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        values[key] = value

    return values


def build_commerce_config_from_env(
    *,
    env_file: str | os.PathLike[str] | None = ".env.smx-commerce",
    prefix: str = "SMX_COMMERCE_",
) -> dict[str, Any]:
    file_values = load_env_file(env_file)
    config: dict[str, Any] = {}

    for env_suffix, config_key in ENV_TO_CONFIG.items():
        env_key = f"{prefix}{env_suffix}"

        raw_value = os.getenv(env_key)

        if raw_value is None:
            raw_value = file_values.get(env_key)

        if raw_value is None or raw_value == "":
            continue

        config[config_key] = _coerce_config_value(config_key, raw_value)

    return config


def _coerce_config_value(config_key: str, value: str) -> Any:
    if config_key in BOOLEAN_CONFIG_KEYS:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    if config_key in INTEGER_CONFIG_KEYS:
        return int(value)

    return value

from __future__ import annotations

from pathlib import Path
import os
from typing import Any
from urllib.parse import quote


ENV_TO_CONFIG = {
    "DATABASE_URL": "database_url",
    "ECHO_SQL": "echo_sql",
    "ADMIN_TOKEN": "admin_token",
    "ADMIN_API_KEY": "admin_token",

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
    
    "HOST_SITE_TITLE": "host_site_title",
    "HOST_HOME_URL": "host_home_url",
    "STORE_TITLE": "store_title",
    "STORE_HOME_URL": "store_home_url",
    "PUBLIC_BASE_URL": "public_base_url",
    "ASSETS_DIR": "assets_dir",
    "PRODUCTS_ASSETS_DIR": "products_assets_dir",
    "RECEIPTS_DIR": "receipts_dir",
    "LOGO_URL": "logo_url",
    "FAVICON_URL": "favicon_url",
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

    _apply_cloud_run_aliases(config, prefix=prefix)

    return config


def _apply_cloud_run_aliases(config: dict[str, Any], *, prefix: str) -> None:
    """
    Accept production-friendly Cloud Run env names while keeping the original
    SMX_COMMERCE_* names as the public package API.

    Explicit SMX_COMMERCE_* environment variables win.

    Cloud Run production aliases may override values loaded only from the
    client scaffold .smx_commerce.env file, because that file is normally
    local-development SQLite config.
    """
    explicit_database_url = os.getenv(f"{prefix}DATABASE_URL")

    if not explicit_database_url:
        cloud_sql_url = _build_cloud_sql_postgres_url_from_aliases()
        if cloud_sql_url:
            config["database_url"] = cloud_sql_url

    _set_if_missing(config, "public_base_url", _first_env("PUBLIC_BASE_URL"))

    _set_if_missing(config, "stripe_secret_key", _first_env("STRIPE_SECRET_KEY"))
    _set_if_missing(config, "stripe_webhook_secret", _first_env("STRIPE_WEBHOOK_SECRET"))

    if (
        not os.getenv(f"{prefix}PAYMENT_PROVIDER")
        and config.get("stripe_secret_key")
        and config.get("stripe_webhook_secret")
    ):
        config["payment_provider"] = "stripe"

    _apply_email_aliases(config, prefix=prefix)
    _apply_assets_aliases(config, prefix=prefix)


def _build_cloud_sql_postgres_url_from_aliases() -> str | None:
    user = _first_env("SMX_COMMERCE_DB_USER")
    password = _first_env("SMX_COMMERCE_DB_PASSWORD")
    database = _first_env("SMX_COMMERCE_DB_NAME")
    instance_connection_name = _first_env("SMX_COMMERCE_INSTANCE_CONNECTION_NAME")

    if not all([user, password, database, instance_connection_name]):
        return None

    return (
        "postgresql+psycopg2://"
        f"{quote(user, safe='')}:{quote(password, safe='')}"
        f"@/{quote(database, safe='')}"
        f"?host=/cloudsql/{instance_connection_name}"
    )


def _apply_email_aliases(config: dict[str, Any], *, prefix: str) -> None:
    if os.getenv(f"{prefix}EMAIL_PROVIDER"):
        return

    email_enabled = _first_env("SMX_EMAIL_ENABLED")
    smtp_host = _first_env("SMX_SMTP_HOST")

    if email_enabled in {"1", "true", "TRUE", "yes", "YES", "on", "ON"} and smtp_host:
        config["email_provider"] = "smtp"

    _set_if_missing(config, "smtp_host", smtp_host)
    _set_if_missing(config, "smtp_port", _coerce_optional_int(_first_env("SMX_SMTP_PORT")))
    _set_if_missing(config, "smtp_username", _first_env("SMX_SMTP_USERNAME"))
    _set_if_missing(config, "smtp_password", _first_env("SMX_SMTP_PASSWORD"))
    _set_if_missing(config, "default_from_email", _first_env("SMX_SMTP_FROM_EMAIL"))
    _set_if_missing(config, "smtp_use_tls", _coerce_optional_bool(_first_env("SMX_SMTP_USE_TLS")))


def _apply_assets_aliases(config: dict[str, Any], *, prefix: str) -> None:
    explicit_assets_dir = os.getenv(f"{prefix}ASSETS_DIR") or _first_env("COMMERCE_ASSETS_DIR")
    smx_client_dir = _first_env("SMX_CLIENT_DIR")

    if explicit_assets_dir:
        config["assets_dir"] = _resolve_assets_dir(explicit_assets_dir, smx_client_dir)
    elif smx_client_dir:
        config["assets_dir"] = str(Path(smx_client_dir) / "assets")

    raw_logo_url = os.getenv(f"{prefix}LOGO_URL") or _first_env("COMMERCE_LOGO_URL")
    raw_favicon_url = os.getenv(f"{prefix}FAVICON_URL") or _first_env("COMMERCE_FAVICON_URL")

    config["logo_url"] = _public_asset_url(raw_logo_url, default="/commerce/assets/logo.png")
    config["favicon_url"] = _public_asset_url(raw_favicon_url, default="/commerce/assets/favicon.png")


def _resolve_assets_dir(value: str, smx_client_dir: str | None) -> str:
    value = value.strip()

    if smx_client_dir and value.startswith("gs://"):
        parts = value.removeprefix("gs://").split("/", 1)
        suffix = parts[1] if len(parts) == 2 else "assets"
        return str(Path(smx_client_dir) / suffix)

    if smx_client_dir and not value.startswith(("/", "./", "../")):
        suffix = value.split("/", 1)[1] if "/" in value else value
        return str(Path(smx_client_dir) / suffix)

    return value


def _public_asset_url(value: str | None, *, default: str) -> str:
    if not value:
        return default

    value = value.strip()

    if value.startswith(("http://", "https://")):
        return value

    if value.startswith("/") and not value.startswith("/app/"):
        return value

    filename = Path(value).name
    if filename:
        return f"/commerce/assets/{filename}"

    return default


def _set_if_missing(config: dict[str, Any], key: str, value: Any) -> None:
    if key not in config and value not in {None, ""}:
        config[key] = value


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value != "":
            return value
    return None


def _coerce_optional_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _coerce_config_value(config_key: str, value: str) -> Any:
    if config_key in BOOLEAN_CONFIG_KEYS:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    if config_key in INTEGER_CONFIG_KEYS:
        return int(value)

    return value
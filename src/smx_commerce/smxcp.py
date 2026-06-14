from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import shutil


PLUGINS_DIR_NAME = "plugins"
SCAFFOLD_DIR_NAME = "commerce"
SETUP_FILE_NAME = "smx_commerce_setup.py"
ENV_EXAMPLE_FILE_NAME = ".smx_commerce_example.env"
ENV_FILE_NAME = ".smx_commerce.env"
DEPLOY_ENV_EXAMPLE_FILE_NAME = ".smx_commerce.deploy_example.env"
DATA_DIR_NAME = "data"
ASSETS_DIR_NAME = "assets"
PRODUCTS_ASSETS_DIR_NAME = "products"
RECEIPTS_DIR_NAME = "receipts"
DEV_DB_FILE_NAME = "smx_commerce_dev.db"

FALLBACK_PNG_BYTES = (
    b"\\x89PNG\\r\\n\\x1a\\n"
    b"\\x00\\x00\\x00\\rIHDR"
    b"\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01"
    b"\\x08\\x06\\x00\\x00\\x00"
    b"\\x1f\\x15\\xc4\\x89"
    b"\\x00\\x00\\x00\\nIDATx\\x9cc\\x00\\x01\\x00\\x00\\x05\\x00\\x01"
    b"\\r\\n-\\xb4"
    b"\\x00\\x00\\x00\\x00IEND\\xaeB`\\x82"
)


@dataclass(frozen=True)
class SmxCommerceScaffold:
    project_root: Path
    scaffold_dir: Path
    data_dir: Path
    assets_dir: Path
    products_assets_dir: Path
    receipts_dir: Path
    setup_file: Path
    env_example_file: Path
    env_file: Path
    deploy_env_example_file: Path
    db_file: Path
    logo_file: Path
    favicon_file: Path


def ensure_commerce_scaffold(
    *,
    project_root: str | Path | None = None,
) -> SmxCommerceScaffold:
    """
    Ensure a client project has the smx-commerce integration scaffold.

    This creates missing files only. Existing customer files are never overwritten.
    """
    root = Path(project_root or Path.cwd()).resolve()

    plugins_dir = root / PLUGINS_DIR_NAME
    scaffold_dir = plugins_dir / SCAFFOLD_DIR_NAME
    data_dir = scaffold_dir / DATA_DIR_NAME
    assets_dir = scaffold_dir / ASSETS_DIR_NAME
    products_assets_dir = assets_dir / PRODUCTS_ASSETS_DIR_NAME
    receipts_dir = assets_dir / RECEIPTS_DIR_NAME
    db_file = data_dir / DEV_DB_FILE_NAME
    logo_file = assets_dir / "logo.png"
    favicon_file = assets_dir / "favicon.png"

    init_file = scaffold_dir / "__init__.py"
    setup_file = scaffold_dir / SETUP_FILE_NAME
    env_example_file = scaffold_dir / ENV_EXAMPLE_FILE_NAME
    env_file = scaffold_dir / ENV_FILE_NAME
    deploy_env_example_file = scaffold_dir / DEPLOY_ENV_EXAMPLE_FILE_NAME

    scaffold_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    products_assets_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)

    _write_if_missing(init_file, "")

    _write_if_missing(
        setup_file,
        _render_setup_file(),
    )

    _write_if_missing(
        env_example_file,
        _render_env_example_file(),
    )

    _write_if_missing(
        env_file,
        _render_runtime_env_file(
            db_file=db_file,
            assets_dir=assets_dir,
            products_assets_dir=products_assets_dir,
            receipts_dir=receipts_dir,
        ),
    )

    _write_if_missing(
        deploy_env_example_file,
        _render_deploy_env_example_file(),
    )

    _copy_default_asset_if_missing("logo.png", logo_file)
    _copy_default_asset_if_missing("favicon.png", favicon_file)

    return SmxCommerceScaffold(
        project_root=root,
        scaffold_dir=scaffold_dir,
        data_dir=data_dir,
        assets_dir=assets_dir,
        products_assets_dir=products_assets_dir,
        receipts_dir=receipts_dir,
        setup_file=setup_file,
        env_example_file=env_example_file,
        env_file=env_file,
        deploy_env_example_file=deploy_env_example_file,
        db_file=db_file,
        logo_file=logo_file,
        favicon_file=favicon_file,
    )


def _write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return

    path.write_text(content, encoding="utf-8")


def _copy_default_asset_if_missing(asset_name: str, target: Path) -> None:
    if target.exists():
        return

    try:
        asset_resource = resources.files("smx_commerce.default_assets").joinpath(asset_name)
    except ModuleNotFoundError:
        target.write_bytes(FALLBACK_PNG_BYTES)
        return

    if not asset_resource.is_file():
        target.write_bytes(FALLBACK_PNG_BYTES)
        return

    with resources.as_file(asset_resource) as source:
        shutil.copyfile(source, target)


def _sqlite_url_for(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.resolve().as_posix()}"


def _path_value(path: Path) -> str:
    return path.resolve().as_posix()


def _render_setup_file() -> str:
    return '''from __future__ import annotations

from pathlib import Path
from smx_commerce import setup_commerce as _setup_commerce


PROJECT_ROOT = Path(__file__).resolve().parents[2]

def setup_commerce(app, *, init_schema: bool = True, ai_profile=None):
    """
    Initialize smx-commerce for this client project.

    The host project builds and provides ai_profile.
    smx-commerce uses that profile to build its internal AI adapter and agents.

    This file is customer-owned after creation.
    smx-commerce will not overwrite it.
    """
    return _setup_commerce(
        app=app,
        project_root=PROJECT_ROOT,
        init_schema=init_schema,
        ai_profile=ai_profile,
    )
'''


def _render_env_example_file() -> str:
    return '''# smx-commerce client project environment example
#
# Copy this file to:
#
#   plugins/commerce/.smx_commerce.env
#
# Then replace the placeholder values.
#
# Generate strong secrets with:
#
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#
# IMPORTANT:
# - Do not commit plugins/commerce/.smx_commerce.env.
# - The admin key is chosen by the project owner.
# - smx-commerce does not generate a hidden admin token.
# - Public users should not see an Admin button.
# - Admins enter through /commerce/admin and authenticate with the admin key.

SMX_COMMERCE_DATABASE_URL=sqlite+pysqlite:///./plugins/commerce/data/smx_commerce_dev.db
SMX_COMMERCE_ADMIN_TOKEN=replace-with-a-strong-admin-token
SMX_COMMERCE_FLASK_SECRET_KEY=replace-with-a-strong-session-secret

SMX_COMMERCE_PAYMENT_PROVIDER=none
SMX_COMMERCE_EMAIL_PROVIDER=none

SMX_COMMERCE_HOST_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_HOST_HOME_URL=/

SMX_COMMERCE_STORE_TITLE=smxCommerce
SMX_COMMERCE_STORE_HOME_URL=/commerce

SMX_COMMERCE_ASSETS_DIR=./plugins/commerce/assets
SMX_COMMERCE_PRODUCTS_ASSETS_DIR=./plugins/commerce/assets/products
SMX_COMMERCE_RECEIPTS_DIR=./plugins/commerce/assets/receipts
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
'''


def _render_runtime_env_file(
    *,
    db_file: Path,
    assets_dir: Path,
    products_assets_dir: Path,
    receipts_dir: Path,
) -> str:
    return f'''# smx-commerce local runtime environment
#
# This file is customer-owned after creation.
# smx-commerce will not overwrite it.
#
# Replace the dummy values before real use.
#
# Generate strong secrets with:
#
#   python -c "import secrets; print(secrets.token_urlsafe(32))"

SMX_COMMERCE_DATABASE_URL={_sqlite_url_for(db_file)}
SMX_COMMERCE_ADMIN_TOKEN=local-admin-token
SMX_COMMERCE_FLASK_SECRET_KEY=replace-with-a-strong-session-secret

SMX_COMMERCE_PAYMENT_PROVIDER=none
SMX_COMMERCE_EMAIL_PROVIDER=none

SMX_COMMERCE_HOST_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_HOST_HOME_URL=/

SMX_COMMERCE_STORE_TITLE=smxCommerce
SMX_COMMERCE_STORE_HOME_URL=/commerce

SMX_COMMERCE_ASSETS_DIR={_path_value(assets_dir)}
SMX_COMMERCE_PRODUCTS_ASSETS_DIR={_path_value(products_assets_dir)}
SMX_COMMERCE_RECEIPTS_DIR={_path_value(receipts_dir)}
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
'''

def _render_deploy_env_example_file() -> str:
    return '''# smx-commerce production deployment example
#
# Purpose:
# - Copy these variable names into your Cloud Run deployment script.
# - Replace placeholder values with your client/project values.
# - Do not put raw secret values in this file.
#
# Local development runtime config:
#   plugins/commerce/.smx_commerce.env
#
# Production deployment example:
#   plugins/commerce/.smx_commerce.deploy_example.env
#
# smxCP rule:
#   one Secret Manager vault -> one SMX_COMMERCE_* Cloud Run env var


# ---------------------------------------------------------------------
# Required production non-secret env vars
# Use these with: gcloud run deploy/update --set-env-vars
# ---------------------------------------------------------------------

SMX_COMMERCE_PUBLIC_BASE_URL=https://your-domain.com
SMX_COMMERCE_DB_USER=your_commerce_db_user
SMX_COMMERCE_DB_NAME=your_commerce_db_name
SMX_COMMERCE_INSTANCE_CONNECTION_NAME=your-project:your-region:your-cloudsql-instance

SMX_COMMERCE_AUTO_INIT=1
SMX_COMMERCE_PAYMENT_PROVIDER=stripe

SMX_COMMERCE_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/commerce/assets
SMX_COMMERCE_PRODUCTS_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/commerce/assets/products
SMX_COMMERCE_RECEIPTS_DIR=/app/$LOCAL_DATA_SOURCE/plugins/commerce/assets/receipts
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png


# ---------------------------------------------------------------------
# Optional production email env vars
# Use these with: gcloud run deploy/update --set-env-vars
# ---------------------------------------------------------------------

SMX_COMMERCE_EMAIL_PROVIDER=smtp
SMX_COMMERCE_SMTP_HOST=smtp.gmail.com
SMX_COMMERCE_SMTP_PORT=587
SMX_COMMERCE_SMTP_USERNAME=your-smtp-username
SMX_COMMERCE_DEFAULT_FROM_EMAIL=your-from-email
SMX_COMMERCE_SMTP_USE_TLS=1


# ---------------------------------------------------------------------
# Required production secret mappings
# Use these with: gcloud run deploy/update --set-secrets
#
# Format:
#   CLOUD_RUN_ENV_VAR=secret-manager-vault-name:latest
# ---------------------------------------------------------------------

SMX_COMMERCE_DB_PASSWORD=commerce-db-password-secret-vault:latest
SMX_COMMERCE_STRIPE_SECRET_KEY=stripe-secret-key-vault:latest
SMX_COMMERCE_STRIPE_WEBHOOK_SECRET=stripe-webhook-secret-vault:latest
SMX_COMMERCE_ADMIN_TOKEN=commerce-admin-token-vault:latest


# ---------------------------------------------------------------------
# Optional production secret mappings
# Use these with: gcloud run deploy/update --set-secrets
# ---------------------------------------------------------------------

SMX_COMMERCE_SMTP_PASSWORD=smx-smtp-password-vault:latest


# ---------------------------------------------------------------------
# Required Stripe webhook setup
# ---------------------------------------------------------------------

STRIPE_WEBHOOK_ENDPOINT=https://your-domain.com/stripe/webhook
STRIPE_WEBHOOK_EVENT=checkout.session.completed


# ---------------------------------------------------------------------
# Required production migration before deploying v0.2 product media/cart features
# ---------------------------------------------------------------------
#
# Existing production databases must be migrated explicitly.
# create_all() does not alter/backfill existing production tables.

# Run this from a trusted deployment environment with SMX_COMMERCE_DATABASE_URL
# or pass --database-url explicitly:
# smx-commerce migrate-product-public-ids
# smx-commerce migrate-product-media-table

# Then verify:
# smx-commerce check-schema


# ---------------------------------------------------------------------
# Required Cloud Run storage mount
# ---------------------------------------------------------------------

SMX_CLIENT_DIR=/app/$LOCAL_DATA_SOURCE
GCS_MOUNT_PATH=/app/$LOCAL_DATA_SOURCE
COMMERCE_ASSETS_BUCKET_PREFIX=plugins/commerce/assets
COMMERCE_RECEIPTS_BUCKET_PREFIX=plugins/commerce/assets/receipts
'''



from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import shutil


SCAFFOLD_DIR_NAME = "smxcommerce"
SETUP_FILE_NAME = "smx_commerce_setup.py"
ENV_EXAMPLE_FILE_NAME = ".smx_commerce_example.env"
ENV_FILE_NAME = ".smx_commerce.env"
DATA_DIR_NAME = "data"
ASSETS_DIR_NAME = "assets"
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
    setup_file: Path
    env_example_file: Path
    env_file: Path
    db_file: Path
    logo_file: Path
    favicon_file: Path


def ensure_smxcommerce_scaffold(
    *,
    project_root: str | Path | None = None,
) -> SmxCommerceScaffold:
    """
    Ensure a client project has the smx-commerce integration scaffold.

    This creates missing files only. Existing customer files are never overwritten.
    """
    root = Path(project_root or Path.cwd()).resolve()

    scaffold_dir = root / SCAFFOLD_DIR_NAME
    data_dir = scaffold_dir / DATA_DIR_NAME
    assets_dir = scaffold_dir / ASSETS_DIR_NAME
    db_file = data_dir / DEV_DB_FILE_NAME
    logo_file = assets_dir / "logo.png"
    favicon_file = assets_dir / "favicon.png"

    init_file = scaffold_dir / "__init__.py"
    setup_file = scaffold_dir / SETUP_FILE_NAME
    env_example_file = scaffold_dir / ENV_EXAMPLE_FILE_NAME
    env_file = scaffold_dir / ENV_FILE_NAME

    scaffold_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

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
        ),
    )

    _copy_default_asset_if_missing("logo.png", logo_file)
    _copy_default_asset_if_missing("favicon.png", favicon_file)

    return SmxCommerceScaffold(
        project_root=root,
        scaffold_dir=scaffold_dir,
        data_dir=data_dir,
        assets_dir=assets_dir,
        setup_file=setup_file,
        env_example_file=env_example_file,
        env_file=env_file,
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def setup_commerce(app, *, init_schema: bool = True):
    """
    Initialize smx-commerce for this client project.

    This file is customer-owned after creation.
    smx-commerce will not overwrite it.
    """
    return _setup_commerce(
        app,
        project_root=PROJECT_ROOT,
        init_schema=init_schema,
    )
'''


def _render_env_example_file() -> str:
    return '''# smx-commerce client project environment example
#
# Copy this file to:
#
#   smxcommerce/.smx_commerce.env
#
# Then replace the placeholder values.
#
# Generate strong secrets with:
#
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#
# IMPORTANT:
# - Do not commit smxcommerce/.smx_commerce.env.
# - The admin key is chosen by the project owner.
# - smx-commerce does not generate a hidden admin token.
# - Public users should not see an Admin button.
# - Admins enter through /commerce/admin and authenticate with the admin key.

SMX_COMMERCE_DATABASE_URL=sqlite+pysqlite:///./smxcommerce/data/smx_commerce_dev.db
SMX_COMMERCE_ADMIN_API_KEY=replace-with-a-strong-admin-token
SMX_COMMERCE_FLASK_SECRET_KEY=replace-with-a-strong-session-secret

SMX_COMMERCE_PAYMENT_PROVIDER=none
SMX_COMMERCE_EMAIL_PROVIDER=none

SMX_COMMERCE_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_MODULE_TITLE=smxCommerce
SMX_COMMERCE_PROJECT_HOME_URL=/

SMX_COMMERCE_ASSETS_DIR=./smxcommerce/assets
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
'''


def _render_runtime_env_file(*, db_file: Path, assets_dir: Path) -> str:
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
SMX_COMMERCE_ADMIN_API_KEY=local-admin-key
SMX_COMMERCE_FLASK_SECRET_KEY=replace-with-a-strong-session-secret

SMX_COMMERCE_PAYMENT_PROVIDER=none
SMX_COMMERCE_EMAIL_PROVIDER=none

SMX_COMMERCE_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_MODULE_TITLE=smxCommerce
SMX_COMMERCE_PROJECT_HOME_URL=/

SMX_COMMERCE_ASSETS_DIR={_path_value(assets_dir)}
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
'''
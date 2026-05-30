from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class CommerceConfig:
    database_url: str
    echo_sql: bool = False
    admin_token: str | None = None
    site_title: str = "SyntaxMatrix"
    module_title: str = "smxCommerce"

    project_title: str = "SyntaxMatrix"
    project_home_url: str = "/"
    public_base_url: str | None = None

    assets_dir: str = "./smxcommerce/assets"
    products_assets_dir: str = "./smxcommerce/assets/products"
    receipts_dir: str = "./smxcommerce/assets/receipts"
    logo_url: str | None = "/commerce/assets/logo.png"
    favicon_url: str | None = "/commerce/assets/favicon.png"

    @classmethod
    def from_env(cls) -> "CommerceConfig":
        site_title = os.getenv("SMX_COMMERCE_SITE_TITLE") or "SyntaxMatrix"
        module_title = os.getenv("SMX_COMMERCE_MODULE_TITLE") or "smxCommerce"

        return cls(
            database_url=os.getenv(
                "SMX_COMMERCE_DATABASE_URL",
                "sqlite+pysqlite:///./smxcommerce/data/smx_commerce_dev.db",
            ),
            echo_sql=os.getenv("SMX_COMMERCE_ECHO_SQL", "").lower() in {"1", "true", "yes"},
            admin_token=os.getenv("SMX_COMMERCE_ADMIN_TOKEN") or None,
            site_title=site_title,
            module_title=module_title,
            project_title=module_title,
            project_home_url=os.getenv("SMX_COMMERCE_PROJECT_HOME_URL", "/"),
            public_base_url=os.getenv("SMX_COMMERCE_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or None,
            assets_dir=os.getenv("SMX_COMMERCE_ASSETS_DIR", "./smxcommerce/assets"),
            products_assets_dir=os.getenv("SMX_COMMERCE_PRODUCTS_ASSETS_DIR", "./smxcommerce/assets/products"),
            receipts_dir=os.getenv("SMX_COMMERCE_RECEIPTS_DIR", "./smxcommerce/assets/receipts"),
            logo_url=os.getenv("SMX_COMMERCE_LOGO_URL") or "/commerce/assets/logo.png",

            favicon_url=os.getenv("SMX_COMMERCE_FAVICON_URL") or "/commerce/assets/favicon.png",
        )

    @classmethod
    def from_mapping(cls, values: dict | None) -> "CommerceConfig":
        values = values or {}

        site_title = (
            values.get("site_title")
            or os.getenv("SMX_COMMERCE_SITE_TITLE")
            or "SyntaxMatrix"
        )
        module_title = values.get("module_title") or os.getenv("SMX_COMMERCE_MODULE_TITLE") or "smxCommerce"

        return cls(
            database_url=values.get(
                "database_url",
                os.getenv(
                    "SMX_COMMERCE_DATABASE_URL",
                    "sqlite+pysqlite:///./smxcommerce/data/smx_commerce_dev.db",
                ),
            ),
            echo_sql=bool(values.get("echo_sql", False)),
            admin_token=values.get("admin_token") or os.getenv("SMX_COMMERCE_ADMIN_TOKEN") or None,
            site_title=site_title,
            module_title=module_title,
            project_title=module_title,
            project_home_url=values.get("project_home_url") or os.getenv("SMX_COMMERCE_PROJECT_HOME_URL") or "/",
            public_base_url=values.get("public_base_url") or os.getenv("SMX_COMMERCE_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or None,
            assets_dir=values.get("assets_dir") or os.getenv("SMX_COMMERCE_ASSETS_DIR") or "./smxcommerce/assets",
            products_assets_dir=values.get("products_assets_dir") or os.getenv("SMX_COMMERCE_PRODUCTS_ASSETS_DIR") or "./smxcommerce/assets/products",
            receipts_dir=values.get("receipts_dir") or os.getenv("SMX_COMMERCE_RECEIPTS_DIR") or "./smxcommerce/assets/receipts",
            logo_url=values.get("logo_url") or os.getenv("SMX_COMMERCE_LOGO_URL") or "/commerce/assets/logo.png",
            favicon_url=values.get("favicon_url") or os.getenv("SMX_COMMERCE_FAVICON_URL") or "/commerce/assets/favicon.png",
        )
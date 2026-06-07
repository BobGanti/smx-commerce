from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class CommerceConfig:
    database_url: str
    echo_sql: bool = False
    admin_token: str | None = None
    host_site_title: str = "SyntaxMatrix"
    host_home_url: str = "/"

    store_title: str = "smxCommerce"
    store_home_url: str = "/commerce"
    public_base_url: str | None = None

    assets_dir: str = "./smxcommerce/assets"
    products_assets_dir: str = "./smxcommerce/assets/products"
    receipts_dir: str = "./smxcommerce/assets/receipts"
    logo_url: str | None = "/commerce/assets/logo.png"
    favicon_url: str | None = "/commerce/assets/favicon.png"

    @classmethod
    def from_env(cls) -> "CommerceConfig":
        host_site_title = os.getenv("SMX_COMMERCE_HOST_SITE_TITLE") or "SyntaxMatrix"
        store_title = os.getenv("SMX_COMMERCE_STORE_TITLE") or "smxCommerce"

        return cls(
            database_url=os.getenv(
                "SMX_COMMERCE_DATABASE_URL",
                "sqlite+pysqlite:///./smxcommerce/data/smx_commerce_dev.db",
            ),
            echo_sql=os.getenv("SMX_COMMERCE_ECHO_SQL", "").lower() in {"1", "true", "yes"},
            admin_token=os.getenv("SMX_COMMERCE_ADMIN_TOKEN") or os.getenv("SMX_COMMERCE_ADMIN_API_KEY") or None,
            host_site_title=host_site_title,
            store_title=store_title,
            host_home_url=os.getenv("SMX_COMMERCE_HOST_HOME_URL", "/"),
            store_home_url=os.getenv("SMX_COMMERCE_STORE_HOME_URL", "/commerce"),
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

        host_site_title = (
            values.get("host_site_title")
            or os.getenv("SMX_COMMERCE_HOST_SITE_TITLE")
            or "SyntaxMatrix"
        )
        store_title = values.get("store_title") or os.getenv("SMX_COMMERCE_STORE_TITLE") or "smxCommerce"

        return cls(
            database_url=values.get(
                "database_url",
                os.getenv(
                    "SMX_COMMERCE_DATABASE_URL",
                    "sqlite+pysqlite:///./smxcommerce/data/smx_commerce_dev.db",
                ),
            ),
            echo_sql=bool(values.get("echo_sql", False)),
            admin_token=values.get("admin_token") or values.get("admin_api_key") or os.getenv("SMX_COMMERCE_ADMIN_TOKEN") or os.getenv("SMX_COMMERCE_ADMIN_API_KEY") or None,
            host_site_title=host_site_title,
            store_title=store_title,
            host_home_url=values.get("host_home_url") or os.getenv("SMX_COMMERCE_HOST_HOME_URL") or "/",
            store_home_url=values.get("store_home_url") or os.getenv("SMX_COMMERCE_STORE_HOME_URL") or "/commerce",
            public_base_url=values.get("public_base_url") or os.getenv("SMX_COMMERCE_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or None,
            assets_dir=values.get("assets_dir") or os.getenv("SMX_COMMERCE_ASSETS_DIR") or "./smxcommerce/assets",
            products_assets_dir=values.get("products_assets_dir") or os.getenv("SMX_COMMERCE_PRODUCTS_ASSETS_DIR") or "./smxcommerce/assets/products",
            receipts_dir=values.get("receipts_dir") or os.getenv("SMX_COMMERCE_RECEIPTS_DIR") or "./smxcommerce/assets/receipts",
            logo_url=values.get("logo_url") or os.getenv("SMX_COMMERCE_LOGO_URL") or "/commerce/assets/logo.png",
            favicon_url=values.get("favicon_url") or os.getenv("SMX_COMMERCE_FAVICON_URL") or "/commerce/assets/favicon.png",
        )
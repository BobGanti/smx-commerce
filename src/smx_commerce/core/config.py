from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class CommerceConfig:
    database_url: str
    echo_sql: bool = False
    admin_api_key: str | None = None

    site_title: str = "SyntaxMatrix"
    module_title: str = "smxCommerce"

    project_title: str = "SyntaxMatrix"
    project_home_url: str = "/"

    assets_dir: str = "./smxcommerce/assets"
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
            admin_api_key=os.getenv("SMX_COMMERCE_ADMIN_API_KEY") or None,
            site_title=site_title,
            module_title=module_title,
            project_title=module_title,
            project_home_url=os.getenv("SMX_COMMERCE_PROJECT_HOME_URL", "/"),
            assets_dir=os.getenv("SMX_COMMERCE_ASSETS_DIR", "./smxcommerce/assets"),
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
            admin_api_key=values.get("admin_api_key") or os.getenv("SMX_COMMERCE_ADMIN_API_KEY") or None,
            site_title=site_title,
            module_title=module_title,
            project_title=module_title,
            project_home_url=values.get("project_home_url") or os.getenv("SMX_COMMERCE_PROJECT_HOME_URL") or "/",
            assets_dir=values.get("assets_dir") or os.getenv("SMX_COMMERCE_ASSETS_DIR") or "./smxcommerce/assets",
            logo_url=values.get("logo_url") or os.getenv("SMX_COMMERCE_LOGO_URL") or "/commerce/assets/logo.png",
            favicon_url=values.get("favicon_url") or os.getenv("SMX_COMMERCE_FAVICON_URL") or "/commerce/assets/favicon.png",
        )
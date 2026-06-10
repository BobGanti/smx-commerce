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

    assets_dir: str = "./commerce/assets"
    products_assets_dir: str = "./commerce/assets/products"
    receipts_dir: str = "./commerce/assets/receipts"
    logo_url: str | None = "/commerce/assets/logo.png"
    favicon_url: str | None = "/commerce/assets/favicon.png"

    @classmethod
    def from_env(cls) -> "CommerceConfig":
        host_site_title = os.getenv("SMX_COMMERCE_HOST_SITE_TITLE") or "SyntaxMatrix"
        store_title = os.getenv("SMX_COMMERCE_STORE_TITLE") or "smxCommerce"

        return cls(
            database_url=os.getenv(
                "SMX_COMMERCE_DATABASE_URL",
                "sqlite+pysqlite:///./commerce/data/smx_commerce_dev.db",
            ),
            echo_sql=os.getenv("SMX_COMMERCE_ECHO_SQL", "").lower() in {"1", "true", "yes"},
            admin_token=os.getenv("SMX_COMMERCE_ADMIN_TOKEN") or None,
            host_site_title=host_site_title,
            store_title=store_title,
            host_home_url=os.getenv("SMX_COMMERCE_HOST_HOME_URL", "/"),
            store_home_url=os.getenv("SMX_COMMERCE_STORE_HOME_URL", "/commerce"),
            public_base_url=os.getenv("SMX_COMMERCE_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or None,
            assets_dir=os.getenv("SMX_COMMERCE_ASSETS_DIR", "./commerce/assets"),
            products_assets_dir=os.getenv("SMX_COMMERCE_PRODUCTS_ASSETS_DIR", "./commerce/assets/products"),
            receipts_dir=os.getenv("SMX_COMMERCE_RECEIPTS_DIR", "./commerce/assets/receipts"),
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
                    "sqlite+pysqlite:///./commerce/data/smx_commerce_dev.db",
                ),
            ),
            echo_sql=bool(values.get("echo_sql", False)),
            admin_token=values.get("admin_token") or os.getenv("SMX_COMMERCE_ADMIN_TOKEN") or None,
            host_site_title=host_site_title,
            store_title=store_title,
            host_home_url=values.get("host_home_url") or os.getenv("SMX_COMMERCE_HOST_HOME_URL") or "/",
            store_home_url=values.get("store_home_url") or os.getenv("SMX_COMMERCE_STORE_HOME_URL") or "/commerce",
            public_base_url=values.get("public_base_url") or os.getenv("SMX_COMMERCE_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or None,
            assets_dir=values.get("assets_dir") or os.getenv("SMX_COMMERCE_ASSETS_DIR") or "./commerce/assets",
            products_assets_dir=values.get("products_assets_dir") or os.getenv("SMX_COMMERCE_PRODUCTS_ASSETS_DIR") or "./commerce/assets/products",
            receipts_dir=values.get("receipts_dir") or os.getenv("SMX_COMMERCE_RECEIPTS_DIR") or "./commerce/assets/receipts",
            logo_url=values.get("logo_url") or os.getenv("SMX_COMMERCE_LOGO_URL") or "/commerce/assets/logo.png",
            favicon_url=values.get("favicon_url") or os.getenv("SMX_COMMERCE_FAVICON_URL") or "/commerce/assets/favicon.png",
        )

# ---------------------------------------------------------------------
# Backward compatibility aliases.
#
# Older client projects used:
#   site_title        -> host_site_title
#   module_title      -> store_title
#   project_home_url  -> host_home_url
# ---------------------------------------------------------------------

_CommerceConfig_original_from_mapping = CommerceConfig.from_mapping


def _smx_legacy_from_mapping(values: dict | None):
    normalized = dict(values or {})

    has_legacy_site_title = "site_title" in normalized
    has_legacy_module_title = "module_title" in normalized
    has_legacy_project_home_url = "project_home_url" in normalized

    if "host_site_title" not in normalized:
        if has_legacy_site_title:
            normalized["host_site_title"] = normalized["site_title"]
        elif "project_title" in normalized:
            normalized["host_site_title"] = normalized["project_title"]
        elif "brand_name" in normalized:
            normalized["host_site_title"] = normalized["brand_name"]

    if "store_title" not in normalized and has_legacy_module_title:
        normalized["store_title"] = normalized["module_title"]

    if "host_home_url" not in normalized and has_legacy_project_home_url:
        normalized["host_home_url"] = normalized["project_home_url"]

    config = _CommerceConfig_original_from_mapping(normalized)

    if has_legacy_site_title or has_legacy_module_title or has_legacy_project_home_url:
        if has_legacy_project_home_url:
            legacy_main_site_title = config.store_title
        else:
            legacy_main_site_title = config.host_site_title

        object.__setattr__(config, "_smx_legacy_main_site_title", legacy_main_site_title)

    return config


CommerceConfig.from_mapping = staticmethod(_smx_legacy_from_mapping)


def _commerce_config_site_title(self):
    return self.host_site_title


def _commerce_config_module_title(self):
    return self.store_title


def _commerce_config_project_home_url(self):
    return self.host_home_url


def _commerce_config_main_site_title(self):
    return getattr(self, "_smx_legacy_main_site_title", self.store_title)


def _commerce_config_main_site_url(self):
    return self.host_home_url


CommerceConfig.site_title = property(_commerce_config_site_title)
CommerceConfig.module_title = property(_commerce_config_module_title)
CommerceConfig.project_home_url = property(_commerce_config_project_home_url)
CommerceConfig.main_site_title = property(_commerce_config_main_site_title)
CommerceConfig.main_site_url = property(_commerce_config_main_site_url)

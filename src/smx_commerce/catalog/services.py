from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from smx_commerce.catalog.objects import Category, Product, ProductPrice
from smx_commerce.catalog.repository import (
    CategoryRepository,
    ProductPriceRepository,
    ProductRepository,
)


class CatalogService:
    def __init__(self, session: Session):
        self.session = session
        self.categories = CategoryRepository(session)
        self.products = ProductRepository(session)
        self.prices = ProductPriceRepository(session)

    def create_category(self, category: Category) -> Category:
        return self.categories.create(category)

    def get_category(self, slug: str) -> Category | None:
        return self.categories.get_by_slug(slug)

    def list_categories(self, **filters: Any) -> list[Category]:
        return self.categories.list(**filters)

    def update_category(self, slug: str, **changes: Any) -> Category:
        return self.categories.update(slug, **changes)

    def archive_category(self, slug: str) -> Category:
        return self.categories.archive(slug)

    def create_product(self, product: Product) -> Product:
        return self.products.create(product)

    def get_product(self, slug: str) -> Product | None:
        return self.products.get_by_slug(slug)

    def list_products(self, **filters: Any) -> list[Product]:
        return self.products.list(**filters)

    def update_product(self, slug: str, **changes: Any) -> Product:
        return self.products.update(slug, **changes)

    def archive_product(self, slug: str) -> Product:
        return self.products.archive(slug)

    def create_price(self, product_slug: str, price: ProductPrice) -> ProductPrice:
        return self.prices.create(product_slug, price)

    def get_price(self, product_slug: str, code: str) -> ProductPrice | None:
        return self.prices.get_by_code(product_slug, code)

    def list_prices(self, product_slug: str, **filters: Any) -> list[ProductPrice]:
        return self.prices.list(product_slug, **filters)

    def update_price(self, product_slug: str, code: str, **changes: Any) -> ProductPrice:
        return self.prices.update(product_slug, code, **changes)

    def deactivate_price(self, product_slug: str, code: str) -> ProductPrice:
        return self.prices.deactivate(product_slug, code)

    def archive_price(self, product_slug: str, code: str) -> ProductPrice:
        return self.prices.archive(product_slug, code)

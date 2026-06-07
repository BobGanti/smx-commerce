from __future__ import annotations

from smx_commerce.core import CommerceRuntime
from smx_commerce.customers.objects import CustomerEntitlement
from smx_commerce.customers.repository import CustomerRepository


def get_customer_active_entitlement(
    *,
    customer_public_id: str,
    product_slug: str,
    price_code: str | None = None,
    runtime: CommerceRuntime | None = None,
    config: dict | None = None,
) -> CustomerEntitlement | None:
    resolved_runtime = _resolve_runtime(runtime=runtime, config=config)

    with resolved_runtime.session_scope() as session:
        return CustomerRepository(session).get_active_entitlement(
            customer_public_id=customer_public_id,
            product_slug=product_slug,
            price_code=price_code,
        )


def customer_has_active_entitlement(
    *,
    customer_public_id: str,
    product_slug: str,
    price_code: str | None = None,
    runtime: CommerceRuntime | None = None,
    config: dict | None = None,
) -> bool:
    return get_customer_active_entitlement(
        customer_public_id=customer_public_id,
        product_slug=product_slug,
        price_code=price_code,
        runtime=runtime,
        config=config,
    ) is not None


def _resolve_runtime(
    *,
    runtime: CommerceRuntime | None = None,
    config: dict | None = None,
) -> CommerceRuntime:
    if runtime is not None:
        return runtime

    return CommerceRuntime.from_mapping(config or {})

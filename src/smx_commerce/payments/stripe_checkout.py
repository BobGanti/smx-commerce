from __future__ import annotations

from typing import Any, Callable

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.checkout.objects import Order
from smx_commerce.payments.checkout import PaymentCheckoutError, PaymentCheckoutSession


class StripeCheckoutProvider:
    def __init__(
        self,
        api_key: str,
        product_name_resolver: Callable[[Order], str] | None = None,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("api_key is required")

        self.api_key = api_key.strip()
        self.product_name_resolver = product_name_resolver or self._default_product_name

    def create_checkout_session(
        self,
        *,
        order: Order,
        success_url: str,
        cancel_url: str,
    ) -> PaymentCheckoutSession:
        success_url = validate_required_text(success_url, "success_url")
        cancel_url = validate_required_text(cancel_url, "cancel_url")

        try:
            import stripe
        except ImportError as exc:
            raise PaymentCheckoutError(
                "stripe package is not installed; install smx-commerce[stripe]"
            ) from exc

        stripe.api_key = self.api_key

        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=order.buyer.email,
            client_reference_id=order.public_id,
            metadata={
                "order_public_id": order.public_id,
                "product_slug": order.product_slug,
                "price_code": order.price_code,
            },
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": order.amount.currency.lower(),
                        "unit_amount": order.amount.amount_cents,
                        "product_data": {
                            "name": self.product_name_resolver(order),
                            "metadata": {
                                "product_slug": order.product_slug,
                                "price_code": order.price_code,
                            },
                        },
                    },
                }
            ],
        )

        session_id = self._read_field(session, "id")
        checkout_url = self._read_field(session, "url")

        if not session_id:
            raise PaymentCheckoutError("Stripe checkout session response is missing id")

        if not checkout_url:
            raise PaymentCheckoutError("Stripe checkout session response is missing url")

        return PaymentCheckoutSession(
            provider="stripe",
            session_id=session_id,
            checkout_url=checkout_url,
            metadata={
                "order_public_id": order.public_id,
                "product_slug": order.product_slug,
                "price_code": order.price_code,
            },
        )

    @staticmethod
    def _default_product_name(order: Order) -> str:
        return order.product_slug

    @staticmethod
    def _read_field(value: Any, field_name: str) -> Any:
        if isinstance(value, dict):
            return value.get(field_name)

        return getattr(value, field_name, None)

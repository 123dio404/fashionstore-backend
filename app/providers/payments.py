from abc import ABC, abstractmethod
from decimal import Decimal
import hashlib
import hmac
import time

import httpx
from fastapi import HTTPException

from app.core.config import settings


class PaymentProvider(ABC):
    @abstractmethod
    def create_intent(self, amount: Decimal, currency: str, idempotency_key: str, metadata: dict) -> dict: ...

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> dict: ...


class NotConfiguredPaymentProvider(PaymentProvider):
    def create_intent(self, *args, **kwargs):
        raise HTTPException(503, "Payment provider is not configured")

    def verify_webhook(self, *args, **kwargs):
        raise HTTPException(503, "Payment provider is not configured")


class MockPaymentProvider(PaymentProvider):
    def create_intent(self, amount, currency, idempotency_key, metadata):
        return {"id": f"mock_{idempotency_key}", "status": "succeeded", "amount": int(amount * 100), "currency": currency}

    def verify_webhook(self, payload, signature):
        raise HTTPException(400, "Mock provider does not accept webhooks")


# RF18 / CU12: medios de pago de caja. Ninguno pasa por una pasarela de pago, por eso se aceptan
# también en producción (a diferencia de `mock`, que es un simulador sólo de desarrollo).
IN_STORE_PAYMENT_METHODS: dict[str, str] = {
    "efectivo": "efectivo",
    "cash": "efectivo",
    "tarjeta": "tarjeta",
    "card": "tarjeta",
    "tarjeta_credito": "tarjeta",
    "tarjeta_debito": "tarjeta",
    "datafono": "datafono",
    "datáfono": "datafono",
}


class InStorePaymentProvider(PaymentProvider):
    """Cobro en caja (efectivo, tarjeta, datáfono): confirma el comercio, no una pasarela.

    La referencia del pago es el comprobante interno `POS-<id de venta>`, el mismo formato que el
    punto de venta usa para los recibos, y no hay confirmación asíncrona ni webhooks.
    """

    def __init__(self, method: str = "efectivo") -> None:
        self.method = method

    def create_intent(self, amount, currency, idempotency_key, metadata):
        sale_id = metadata.get("sale_id")
        reference = f"POS-{int(sale_id):012d}" if sale_id is not None else f"POS-{idempotency_key}"
        return {
            "id": reference,
            "status": "succeeded",
            "amount": int(Decimal(amount) * 100),
            "currency": currency,
            "payment_method": self.method,
        }

    def verify_webhook(self, payload, signature):
        raise HTTPException(400, "In-store payments do not accept webhooks")


class StripePaymentProvider(PaymentProvider):
    def create_intent(self, amount, currency, idempotency_key, metadata):
        if not settings.stripe_secret_key:
            raise HTTPException(503, "Stripe is enabled but STRIPE_SECRET_KEY is not configured")
        try:
            response = httpx.post(
                f"{settings.stripe_api_base.rstrip('/')}/payment_intents",
                headers={"Authorization": f"Bearer {settings.stripe_secret_key}", "Idempotency-Key": idempotency_key},
                data={"amount": int(amount * 100), "currency": currency, "metadata[sale_id]": str(metadata.get("sale_id", ""))},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Stripe payment intent request failed") from exc

    def verify_webhook(self, payload, signature):
        if not settings.stripe_webhook_secret:
            raise HTTPException(503, "STRIPE_WEBHOOK_SECRET is not configured")
        try:
            timestamp = next(part.split("=", 1)[1] for part in signature.split(",") if part.startswith("t="))
        except (StopIteration, ValueError):
            raise HTTPException(400, "Invalid Stripe signature")
        expected = hmac.new(settings.stripe_webhook_secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        signatures = [p.split("=", 1)[1] for p in signature.split(",") if p.startswith("v1=")]
        if abs(time.time() - int(timestamp)) > 300 or not any(hmac.compare_digest(expected, value) for value in signatures):
            raise HTTPException(400, "Invalid Stripe signature")
        import json
        return json.loads(payload)


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    mode = (name or settings.payment_provider).casefold()
    if mode in IN_STORE_PAYMENT_METHODS:
        return InStorePaymentProvider(IN_STORE_PAYMENT_METHODS[mode])
    if mode == "stripe":
        return StripePaymentProvider()
    if mode == "mock" and settings.environment.casefold() in {"development", "test"}:
        return MockPaymentProvider()
    if mode in {"none", "not_configured", "disabled"}:
        return NotConfiguredPaymentProvider()
    raise HTTPException(500, f"Unsupported payment provider: {mode}")

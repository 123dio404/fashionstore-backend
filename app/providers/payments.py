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
    if mode == "stripe":
        return StripePaymentProvider()
    if mode == "mock" and settings.environment.casefold() in {"development", "test"}:
        return MockPaymentProvider()
    if mode in {"none", "not_configured", "disabled"}:
        return NotConfiguredPaymentProvider()
    raise HTTPException(500, f"Unsupported payment provider: {mode}")

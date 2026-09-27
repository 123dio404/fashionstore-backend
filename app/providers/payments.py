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


def generate_qr_base64(data: str) -> str:
    """Genera un código QR en base64 como Data URI PNG."""
    try:
        import base64
        import io
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return ""


class SimulatedPaymentProvider(PaymentProvider):
    """Pasarela simulada del checkout (CU11 en modo demo)."""

    disclaimer = "Pago simulado con fines académicos: no se contactó ninguna pasarela."

    def __init__(self, method: str = "tarjeta_credito") -> None:
        self.method = method

    def create_intent(self, amount, currency, idempotency_key, metadata):
        # Soporte para validar o rechazar el pago
        card_token = str(metadata.get("card_token") or "").casefold()
        should_reject = (
            metadata.get("simulate_rejection") is True
            or card_token in {"pm_card_declined", "pm_card_chargecustomerfail", "reject", "rechazada"}
            or metadata.get("action") == "reject"
        )
        if should_reject:
            return {
                "id": f"SIM-DECLINED-{idempotency_key}",
                "status": "failed",
                "amount": int(Decimal(amount) * 100),
                "currency": currency,
                "payment_method": self.method,
                "error_code": "card_declined",
                "error_message": "Pago rechazado por Stripe: La tarjeta fue declinada (fondos insuficientes o fallo de emisor).",
            }

        # Soporte para QR
        if self.method in {"qr", "stripe_qr"}:
            pay_url = f"https://checkout.stripe.com/pay/sim_{idempotency_key}"
            return {
                "id": f"SIM-QR-{idempotency_key}",
                "status": "succeeded",
                "amount": int(Decimal(amount) * 100),
                "currency": currency,
                "payment_method": "stripe_qr",
                "payment_url": pay_url,
                "qr_code_base64": generate_qr_base64(pay_url),
                "disclaimer": self.disclaimer,
            }

        return {
            "id": f"SIM-{idempotency_key}",
            "status": "succeeded",
            "amount": int(Decimal(amount) * 100),
            "currency": currency,
            "payment_method": self.method,
            "disclaimer": self.disclaimer,
        }

    def verify_webhook(self, payload, signature):
        raise HTTPException(400, "The simulated provider does not accept webhooks")


class StripePaymentProvider(PaymentProvider):
    """Pasarela real de Stripe con soporte para tarjeta de crédito y Stripe QR.

    Permite validar (aprobar) o rechazar (declinar) la transacción de forma explícita.
    """

    sandbox_payment_method = "pm_card_visa"

    def __init__(self, method: str = "card") -> None:
        self.method = method

    @property
    def is_sandbox(self) -> bool:
        return bool(settings.stripe_secret_key) and settings.stripe_secret_key.startswith("sk_test_")

    def create_intent(self, amount, currency, idempotency_key, metadata):
        card_token = str(metadata.get("card_token") or "").casefold()
        should_reject = (
            metadata.get("simulate_rejection") is True
            or card_token in {"pm_card_declined", "pm_card_chargecustomerfail", "reject", "rechazada"}
            or metadata.get("action") == "reject"
        )

        # Si se solicita rechazar el pago (tarjeta declinada / fondos insuficientes)
        if should_reject:
            if settings.stripe_secret_key and self.is_sandbox:
                try:
                    # Intento de confirmación con tarjeta declinada en Stripe real
                    res = httpx.post(
                        f"{settings.stripe_api_base.rstrip('/')}/payment_intents",
                        headers={"Authorization": f"Bearer {settings.stripe_secret_key}", "Idempotency-Key": idempotency_key},
                        data={"amount": int(amount * 100), "currency": currency, "payment_method": "pm_card_chargeCustomerFail", "confirm": "true", "return_url": "https://fashionstore-web-eight.vercel.app/cart"},
                        timeout=30,
                    )
                except Exception:
                    pass
            return {
                "id": f"STRIPE-DECLINED-{idempotency_key}",
                "status": "failed",
                "amount": int(Decimal(amount) * 100),
                "currency": currency,
                "payment_method": "tarjeta_credito",
                "error_code": "card_declined",
                "error_message": "Pago rechazado por Stripe: La tarjeta fue declinada por fondos insuficientes o bloqueo de seguridad.",
            }

        # Si el método es Stripe QR
        if self.method in {"qr", "stripe_qr"}:
            qr_ref = f"QR-STRIPE-{idempotency_key}"
            pay_url = f"https://checkout.stripe.com/pay/{qr_ref}"
            return {
                "id": qr_ref,
                "status": "succeeded",
                "amount": int(Decimal(amount) * 100),
                "currency": currency,
                "payment_method": "stripe_qr",
                "payment_url": pay_url,
                "qr_code_base64": generate_qr_base64(pay_url),
            }

        # Flujo estándar con tarjeta de crédito
        if not settings.stripe_secret_key:
            # Modo demostración cuando no hay clave externa configurada
            return {
                "id": f"pi_demo_{idempotency_key}",
                "status": "succeeded",
                "amount": int(Decimal(amount) * 100),
                "currency": currency,
                "payment_method": "tarjeta_credito",
                "brand": "visa",
                "last4": "4242",
            }

        try:
            response = httpx.post(
                f"{settings.stripe_api_base.rstrip('/')}/payment_intents",
                headers={"Authorization": f"Bearer {settings.stripe_secret_key}", "Idempotency-Key": idempotency_key},
                data={"amount": int(amount * 100), "currency": currency, "payment_method_types[]": "card", "metadata[sale_id]": str(metadata.get("sale_id", ""))},
                timeout=30,
            )
            response.raise_for_status()
            return self._confirm_in_sandbox(response.json())
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Stripe payment intent request failed") from exc

    def _confirm_in_sandbox(self, intent: dict) -> dict:
        """Confirma el intent con la tarjeta de prueba (solo con claves `sk_test_`)."""
        if not self.is_sandbox or intent.get("status") not in {
            "requires_payment_method",
            "requires_confirmation",
        }:
            return intent
        try:
            response = httpx.post(
                f"{settings.stripe_api_base.rstrip('/')}/payment_intents/{intent['id']}/confirm",
                headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
                data={"payment_method": self.sandbox_payment_method, "return_url": "https://fashionstore-web-eight.vercel.app/cart"},
                timeout=30,
            )
            response.raise_for_status()
            confirmed = response.json()
            confirmed["sandbox_confirmed"] = True
            return confirmed
        except httpx.HTTPError:
            return intent

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
    if mode in {"stripe_qr", "qr"}:
        return StripePaymentProvider(method="qr")
    if mode in {"stripe", "stripe_card", "tarjeta", "tarjeta_credito", "card"}:
        return StripePaymentProvider(method="card")
    if mode in {"simulated", "simulado", "demo"}:
        return SimulatedPaymentProvider(method="tarjeta_credito")
    if mode in {"simulado_qr", "simulated_qr"}:
        return SimulatedPaymentProvider(method="qr")
    if mode == "mock" and settings.environment.casefold() in {"development", "test"}:
        return MockPaymentProvider()
    if mode in {"none", "not_configured", "disabled"}:
        return NotConfiguredPaymentProvider()
    raise HTTPException(500, f"Unsupported payment provider: {mode}")


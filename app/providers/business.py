from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException

from app.core.config import settings


class FiscalProvider(ABC):
    @abstractmethod
    def issue_invoice(self, *args, **kwargs) -> dict: ...


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, *args, **kwargs) -> dict: ...


class NotConfiguredFiscalProvider(FiscalProvider):
    def issue_invoice(self, *args, **kwargs):
        raise HTTPException(503, "Fiscal billing provider is not configured")


class SimulatedFiscalProvider(FiscalProvider):
    """Documento fiscal simulado (módulo Ventas, Facturación y Caja).

    Genera número de factura y desglose de IVA a partir de la venta, sin conectar ninguna entidad
    externa. El precio se interpreta **con IVA incluido** —el mismo criterio del comprobante de
    `GET /commerce/sales/{id}/receipt`—, así que el total del documento coincide con el del
    comprobante. `disclaimer` deja explícito que no tiene validez fiscal.
    """

    disclaimer = "Documento simulado con fines académicos: no tiene validez fiscal."

    def issue_invoice(self, sale=None, *args, **kwargs) -> dict:
        if sale is None:
            raise HTTPException(422, "A sale is required to issue an invoice")
        rate = Decimal(settings.fiscal_tax_rate)
        total = Decimal(sale.total or 0)
        subtotal = (total / (Decimal("1") + rate)).quantize(Decimal("0.01")) if rate > 0 else total
        tax = (total - subtotal).quantize(Decimal("0.01"))
        payment = sale.payments[-1] if sale.payments else None
        return {
            "provider": "simulated",
            "invoice_number": f"FAC-{sale.id:012d}",
            "sale_id": sale.id,
            "issued_at": datetime.now(timezone.utc),
            "issuer_name": settings.fiscal_issuer_name,
            "issuer_tax_id": settings.fiscal_issuer_tax_id,
            "customer_id": sale.client_id,
            "tax_rate": rate,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "payment_status": payment.status if payment is not None else "pendiente",
            "payment_reference": payment.reference if payment is not None else None,
            "disclaimer": self.disclaimer,
        }


class AppNotificationProvider(NotificationProvider):
    """Proveedor de notificaciones de compra y transacciones para clientes."""

    def send(self, event: str = "sale.updated", sale_id: int | None = None, channel: str = "in_app", **kwargs) -> dict:
        now = datetime.now(timezone.utc)
        method = kwargs.get("payment_method") or "digital"
        status = kwargs.get("status") or "aprobado"
        total = kwargs.get("total") or "0.00"
        reference = kwargs.get("reference") or (f"TX-{sale_id}" if sale_id else "TX-DEMO")
        invoice_number = kwargs.get("invoice_number") or (f"FAC-{sale_id:012d}" if sale_id else "N/A")

        if str(status).lower() in {"rechazado", "fallido", "declined", "failed"}:
            title = f"Transacción rechazada · Pedido #{sale_id or 'N/A'}"
            message = (
                f"Tu pago de ${total} no pudo procesarse. La pasarela Stripe rechazó la transacción "
                f"(fondos insuficientes o tarjeta declinada). No se realizó ningún cargo."
            )
        else:
            title = f"¡Compra confirmada! · Pedido #{sale_id}"
            message = (
                f"Tu pago de ${total} mediante {method} fue aprobado exitosamente. "
                f"Transacción: {reference}. Tu factura {invoice_number} ya fue emitida."
            )

        return {
            "id": f"NOTIF-{sale_id or 0}-{int(now.timestamp())}",
            "sale_id": sale_id,
            "channel": channel,
            "event": event,
            "title": title,
            "message": message,
            "amount": str(total),
            "status": status,
            "transaction_reference": reference,
            "invoice_number": invoice_number,
            "created_at": now.isoformat(),
        }


def get_fiscal_provider() -> FiscalProvider:
    """`FISCAL_PROVIDER=simulated` habilita el documento simulado; cualquier otro valor → 503."""
    if settings.fiscal_provider.casefold() in {"simulated", "simulado"}:
        return SimulatedFiscalProvider()
    return NotConfiguredFiscalProvider()


def get_notification_provider() -> NotificationProvider:
    return AppNotificationProvider()

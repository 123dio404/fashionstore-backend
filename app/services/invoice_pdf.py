"""Factura en PDF del CU11 (documento fiscal simulado).

El contenido sale del mismo documento que emite `SimulatedFiscalProvider`, así que el
PDF y la respuesta JSON comparten número, desglose de IVA y descargo de validez.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ACCENT = (0.878, 0.353, 0.278)  # #E05A47
DARK = (0.067, 0.094, 0.153)  # #111827
MUTED = (0.42, 0.447, 0.502)  # #6B7280
LIGHT = (0.957, 0.965, 0.973)  # #F4F6F8
BORDER = (0.898, 0.906, 0.922)  # #E5E7EB

MARGIN = 48.0
ROW = 16.0


def money(value) -> str:
    """`Decimal`/`float`/`str` → `$1,234.56`."""
    return "${:,.2f}".format(Decimal(str(value or 0)))


def short(text: str, font: str, size: float, limit: float, pdf: canvas.Canvas) -> str:
    """Recorta el texto para que no invada la columna siguiente."""
    if pdf.stringWidth(text, font, size) <= limit:
        return text
    while text and pdf.stringWidth(f"{text}…", font, size) > limit:
        text = text[:-1]
    return f"{text}…"


def build_invoice_pdf(invoice: dict, lines: list[dict] | None = None) -> bytes:
    """Devuelve el PDF (bytes) del documento fiscal simulado de una venta."""
    items = lines or []
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    number = str(invoice.get("invoice_number", ""))

    pdf.setTitle(f"Factura {number}")
    pdf.setAuthor(str(invoice.get("issuer_name") or "FashionStore"))

    # -------------------------------------------------------------- encabezado
    pdf.setFillColorRGB(*DARK)
    pdf.rect(0, height - 96, width, 96, stroke=0, fill=1)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawString(MARGIN, height - 52, str(invoice.get("issuer_name") or "FashionStore"))
    pdf.setFont("Helvetica", 9)
    tax_id = invoice.get("issuer_tax_id")
    pdf.drawString(
        MARGIN,
        height - 70,
        f"Documento fiscal simulado · NIT {tax_id}" if tax_id else "Documento fiscal simulado",
    )
    pdf.setFont("Helvetica-Bold", 21)
    pdf.setFillColorRGB(*ACCENT)
    pdf.drawRightString(width - MARGIN, height - 52, "FACTURA")
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(width - MARGIN, height - 72, number)

    # --------------------------------------------------------- datos de la venta
    y = height - 128
    issued = invoice.get("issued_at")
    if not isinstance(issued, datetime):
        issued = datetime.now(timezone.utc)
    reference = invoice.get("payment_reference") or "sin referencia"
    rows = [
        ("Venta", f"#{invoice.get('sale_id')}"),
        ("Fecha", issued.strftime("%d/%m/%Y %H:%M UTC")),
        ("Cliente", f"#{invoice.get('customer_id')}"),
        ("Pago", f"{invoice.get('payment_status')} · {reference}"),
    ]
    half = (width - 2 * MARGIN) / 2
    pdf.setFont("Helvetica-Bold", 9)
    for index, (label, value) in enumerate(rows):
        x = MARGIN + (index % 2) * half
        offset = y - (index // 2) * ROW
        pdf.setFillColorRGB(*MUTED)
        pdf.drawString(x, offset, label.upper())
        pdf.setFont("Helvetica", 9)
        pdf.setFillColorRGB(*DARK)
        pdf.drawString(x + 58, offset, short(str(value), "Helvetica", 9, 150, pdf))
        pdf.setFont("Helvetica-Bold", 9)
    y -= (len(rows) // 2) * ROW + 14

    # ------------------------------------------------------- detalle de prendas
    pdf.setFillColorRGB(*LIGHT)
    pdf.rect(MARGIN, y - 6, width - 2 * MARGIN, 20, stroke=0, fill=1)
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(MARGIN + 6, y, "CANT.")
    pdf.drawString(MARGIN + 46, y, "DESCRIPCIÓN")
    pdf.drawRightString(width - MARGIN - 92, y, "P. UNIT.")
    pdf.drawRightString(width - MARGIN - 6, y, "IMPORTE")
    y -= 20

    if not items:
        pdf.setFillColorRGB(*MUTED)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(MARGIN + 6, y, "Sin detalle registrado para esta venta.")
        y -= ROW
    for item in items:
        variant = " · ".join(str(part) for part in (item.get("size"), item.get("color")) if part)
        name = str(item.get("name") or "Artículo")
        detail = f"{name} ({variant})" if variant else name
        quantity = int(item.get("quantity") or 0)
        unit = Decimal(str(item.get("unit_price") or 0))
        pdf.setFillColorRGB(*DARK)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(MARGIN + 6, y, str(quantity))
        pdf.drawString(MARGIN + 46, y, short(detail, "Helvetica", 9, 250, pdf))
        pdf.drawRightString(width - MARGIN - 92, y, money(unit))
        pdf.drawRightString(width - MARGIN - 6, y, money(unit * quantity))
        y -= 4
        pdf.setStrokeColorRGB(*BORDER)
        pdf.line(MARGIN, y, width - MARGIN, y)
        y -= ROW - 4
    y -= 12

    # --------------------------------------------------------------- totales
    box = 220.0
    x = width - MARGIN - box
    rate = Decimal(str(invoice.get("tax_rate") or 0)) * 100
    for label, value, highlight in (
        ("Subtotal", money(invoice.get("subtotal")), False),
        (f"IVA ({rate.normalize():f}%)", money(invoice.get("tax")), False),
        ("Total", money(invoice.get("total")), True),
    ):
        if highlight:
            pdf.setFillColorRGB(*DARK)
            pdf.rect(x - 8, y - 6, box + 8, 22, stroke=0, fill=1)
            pdf.setFillColorRGB(1, 1, 1)
            pdf.setFont("Helvetica-Bold", 11)
        else:
            pdf.setFillColorRGB(*DARK)
            pdf.setFont("Helvetica", 10)
        pdf.drawString(x, y, label)
        pdf.drawRightString(width - MARGIN, y, value)
        y -= 24 if highlight else 18

    # -------------------------------------------------------------- descargo
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica-Oblique", 8)
    disclaimer = str(invoice.get("disclaimer") or "")
    pdf.drawString(
        MARGIN, MARGIN + 22, short(disclaimer, "Helvetica-Oblique", 8, width - 2 * MARGIN, pdf)
    )
    pdf.drawString(
        MARGIN,
        MARGIN + 10,
        "Generado por FashionStore · " + datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()

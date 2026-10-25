import io
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.commerce import Sale, SaleItem
from app.models.inventory import Stock
from app.models.product import Category, Product, ProductVariant
from app.models.tenant import Tenant
from app.providers import get_ai_provider


# ── REPORTES REALES EN BASE DE DATOS (CON AISLAMIENTO MULTITENANT ESTRICTO) ──

def get_branch_sales_report(db: Session, tenant_id: int, days: int = 30) -> dict[str, Any]:
    """Reporte 1: Ventas agrupadas por sucursal en un período (RF25-1)."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    results = db.execute(
        select(
            Branch.name.label("sucursal"),
            func.count(Sale.id).label("total_transacciones"),
            func.coalesce(func.sum(Sale.total), Decimal("0.00")).label("ingresos_totales"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("unidades_vendidas"),
        )
        .join(Branch, Branch.id == Sale.branch_id)
        .outerjoin(SaleItem, SaleItem.sale_id == Sale.id)
        .where(
            Sale.tenant_id == tenant_id,
            Sale.sale_date >= start_date,
        )
        .group_by(Branch.name)
        .order_by(desc("ingresos_totales"))
    ).all()

    columnas = ["Sucursal", "Transacciones", "Unidades Vendidas", "Ingresos Totales (Bs.)", "Ticket Promedio (Bs.)"]
    filas = []
    labels = []
    data_ingresos = []
    data_unidades = []

    for row in results:
        sucursal = row.sucursal
        transacciones = int(row.total_transacciones)
        ingresos = float(row.ingresos_totales)
        unidades = int(row.unidades_vendidas)
        ticket_prom = round(ingresos / max(transacciones, 1), 2)

        filas.append({
            "Sucursal": sucursal,
            "Transacciones": transacciones,
            "Unidades Vendidas": unidades,
            "Ingresos Totales (Bs.)": round(ingresos, 2),
            "Ticket Promedio (Bs.)": ticket_prom,
        })
        labels.append(sucursal)
        data_ingresos.append(round(ingresos, 2))
        data_unidades.append(unidades)

    return {
        "tipo_reporte": "ventas_sucursal",
        "titulo": f"Ventas Consolidadas por Sucursal (Últimos {days} días)",
        "tipo_grafico": "barras",
        "columnas": columnas,
        "filas": filas,
        "datos_grafico": {
            "labels": labels,
            "datasets": [
                {"label": "Ingresos (Bs.)", "data": data_ingresos, "backgroundColor": "#4F46E5"},
                {"label": "Unidades", "data": data_unidades, "backgroundColor": "#06B6D4"},
            ],
        },
    }


def get_top_products_report(db: Session, tenant_id: int, limit: int = 10) -> dict[str, Any]:
    """Reporte 2: Top productos más vendidos por categoría (RF25-2)."""
    results = db.execute(
        select(
            Product.name.label("producto"),
            Category.name.label("categoria"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("unidades_vendidas"),
            func.coalesce(func.sum(SaleItem.quantity * SaleItem.unit_price), Decimal("0.00")).label("ingresos_totales"),
        )
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(Stock, Stock.variant_id == ProductVariant.id)
        .join(SaleItem, SaleItem.stock_id == Stock.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Category, Category.id == Product.category_id)
        .where(
            Product.tenant_id == tenant_id,
            Sale.tenant_id == tenant_id,
        )
        .group_by(Product.name, Category.name)
        .order_by(desc("unidades_vendidas"))
        .limit(limit)
    ).all()

    columnas = ["Prenda / Producto", "Categoría", "Unidades Vendidas", "Ingresos Generados (Bs.)"]
    filas = []
    labels = []
    data_unidades = []

    for row in results:
        prod = row.producto
        cat = row.categoria
        unidades = int(row.unidades_vendidas)
        ingresos = float(row.ingresos_totales)

        filas.append({
            "Prenda / Producto": prod,
            "Categoría": cat,
            "Unidades Vendidas": unidades,
            "Ingresos Generados (Bs.)": round(ingresos, 2),
        })
        labels.append(prod)
        data_unidades.append(unidades)

    return {
        "tipo_reporte": "top_productos",
        "titulo": f"Top {limit} Productos Más Vendidos por Categoría",
        "tipo_grafico": "dona",
        "columnas": columnas,
        "filas": filas,
        "datos_grafico": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Unidades Vendidas",
                    "data": data_unidades,
                    "backgroundColor": ["#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16"][:len(labels)],
                }
            ],
        },
    }


def get_quarterly_branch_comparison(db: Session, tenant_id: int) -> dict[str, Any]:
    """Reporte 3: Comparativa de ventas entre sucursales de los últimos 3 meses (RF25-3)."""
    now = datetime.now(timezone.utc)
    months = []
    month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    for i in range(2, -1, -1):
        target_date = now - timedelta(days=i * 30)
        months.append({
            "year": target_date.year,
            "month": target_date.month,
            "label": f"{month_names[target_date.month - 1]} {target_date.year}",
        })

    branches = db.scalars(
        select(Branch).where(Branch.tenant_id == tenant_id, Branch.is_active == True)
    ).all()

    columnas = ["Sucursal"] + [m["label"] for m in months] + ["Total Trimestre (Bs.)"]
    filas = []
    datasets = []
    colors_list = ["#4F46E5", "#10B981", "#F59E0B", "#EC4899"]

    for idx, b in enumerate(branches):
        row_dict = {"Sucursal": b.name}
        total_trim = 0.0
        data_points = []

        for m in months:
            m_rev = db.execute(
                select(func.coalesce(func.sum(Sale.total), Decimal("0.00")))
                .where(
                    Sale.tenant_id == tenant_id,
                    Sale.branch_id == b.id,
                    func.extract("year", Sale.sale_date) == m["year"],
                    func.extract("month", Sale.sale_date) == m["month"],
                )
            ).scalar() or Decimal("0.00")
            val = round(float(m_rev), 2)
            row_dict[m["label"]] = val
            total_trim += val
            data_points.append(val)

        row_dict["Total Trimestre (Bs.)"] = round(total_trim, 2)
        filas.append(row_dict)

        datasets.append({
            "label": b.name,
            "data": data_points,
            "borderColor": colors_list[idx % len(colors_list)],
            "backgroundColor": colors_list[idx % len(colors_list)],
            "fill": False,
        })

    return {
        "tipo_reporte": "comparativa_trimestral",
        "titulo": "Comparativa de Ventas entre Sucursales (Últimos 3 Meses)",
        "tipo_grafico": "lineas",
        "columnas": columnas,
        "filas": filas,
        "datos_grafico": {
            "labels": [m["label"] for m in months],
            "datasets": datasets,
        },
    }


def get_low_stock_risk_report(db: Session, tenant_id: int) -> dict[str, Any]:
    """Reporte 4: Productos con menor existencia y riesgo de agotamiento (RF25-4)."""
    results = db.execute(
        select(
            Branch.name.label("sucursal"),
            Product.name.label("producto"),
            ProductVariant.codigo.label("codigo_sku"),
            Stock.physical_stock.label("stock_fisico"),
            Stock.reserved_stock.label("stock_reservado"),
            (Stock.physical_stock - Stock.reserved_stock).label("stock_disponible"),
            Stock.min_stock.label("stock_minimo"),
        )
        .join(Branch, Branch.id == Stock.branch_id)
        .join(ProductVariant, ProductVariant.id == Stock.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            Product.tenant_id == tenant_id,
            Stock.physical_stock <= (Stock.min_stock + 5),
        )
        .order_by("stock_disponible")
        .limit(20)
    ).all()

    columnas = ["Sucursal", "Producto", "Código / SKU", "Stock Físico", "Reservado", "Stock Disponible", "Stock Mínimo", "Estado"]
    filas = []
    labels = []
    data_disponible = []
    data_minimo = []

    for row in results:
        disp = int(row.stock_disponible)
        min_s = int(row.stock_minimo)
        estado = "AGOTADO" if disp <= 0 else ("CRÍTICO" if disp <= min_s else "PRECAUCIÓN")

        filas.append({
            "Sucursal": row.sucursal,
            "Producto": row.producto,
            "Código / SKU": row.codigo_sku or "N/A",
            "Stock Físico": int(row.stock_fisico),
            "Reservado": int(row.stock_reservado),
            "Stock Disponible": disp,
            "Stock Mínimo": min_s,
            "Estado": estado,
        })
        labels.append(f"{row.producto} ({row.sucursal})")
        data_disponible.append(disp)
        data_minimo.append(min_s)

    return {
        "tipo_reporte": "riesgo_stock",
        "titulo": "Inventario Crítico: Prendas con Riesgo Inminente de Agotamiento",
        "tipo_grafico": "barras",
        "columnas": columnas,
        "filas": filas,
        "datos_grafico": {
            "labels": labels[:10],
            "datasets": [
                {"label": "Stock Disponible", "data": data_disponible[:10], "backgroundColor": "#EF4444"},
                {"label": "Stock Mínimo Requerido", "data": data_minimo[:10], "backgroundColor": "#F59E0B"},
            ],
        },
    }


# ── INTERPRETADOR DE LENGUAJE NATURAL CON GEMINI Y SÍNTESIS NARRATIVA (RF23, RF24, RF26) ──

def process_generative_query(db: Session, tenant_id: int, prompt: str) -> dict[str, Any]:
    """
    Interpreta solicitud en lenguaje natural, ejecuta la consulta SQL filtrada
    por tenant_id y genera un análisis ejecutivo profesional con Gemini.
    """
    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else f"Tenant #{tenant_id}"

    # Clasificación con Gemini o RegEx de respaldo
    ai_provider = get_ai_provider()
    intent = None

    if ai_provider.__class__.__name__ != "DisabledAIProvider":
        try:
            classification_prompt = (
                f"Clasifica la siguiente consulta analítica para el sistema de indumentaria textil FashionStore.\n"
                f"Opciones válidas para 'intent':\n"
                f"- 'ventas_sucursal': Si pide ventas por tienda, sucursal, ingresos generales o facturación.\n"
                f"- 'top_productos': Si pide los más vendidos, prendas estrella, productos líderes, categorías más vendidas.\n"
                f"- 'comparativa_trimestral': Si pide evolución en el tiempo, últimos meses, trimestre o comparar sucursales.\n"
                f"- 'riesgo_stock': Si pide productos por agotarse, inventario bajo, stock crítico o desabastecimiento.\n"
                f"Consulta del usuario: \"{prompt}\"\n"
                f"Responde estrictamente en formato JSON con la clave 'intent'."
            )
            parsed = ai_provider.generate_json(classification_prompt)
            intent = parsed.get("intent")
        except Exception:
            intent = None

    # Respaldo por palabras clave
    if intent not in ["ventas_sucursal", "top_productos", "comparativa_trimestral", "riesgo_stock"]:
        p_lower = prompt.casefold()
        if any(w in p_lower for w in ["top", "mas vendido", "más vendido", "estrella", "populares", "prendas lider"]):
            intent = "top_productos"
        elif any(w in p_lower for w in ["comparativa", "meses", "trimestre", "evolucion", "evolución", "historico", "histórico"]):
            intent = "comparativa_trimestral"
        elif any(w in p_lower for w in ["agot", "critico", "crítico", "bajo", "escasez", "reorden", "inventario", "stock"]):
            intent = "riesgo_stock"
        else:
            intent = "ventas_sucursal"

    # Ejecutar reporte correspondiente
    if intent == "top_productos":
        report_data = get_top_products_report(db, tenant_id)
    elif intent == "comparativa_trimestral":
        report_data = get_quarterly_branch_comparison(db, tenant_id)
    elif intent == "riesgo_stock":
        report_data = get_low_stock_risk_report(db, tenant_id)
    else:
        report_data = get_branch_sales_report(db, tenant_id)

    # Generar síntesis ejecutiva con Gemini
    resumen_narrativo = ""
    if ai_provider.__class__.__name__ != "DisabledAIProvider":
        try:
            summary_prompt = (
                f"Eres un analista de negocios senior en indumentaria textil para la empresa '{tenant_name}'.\n"
                f"El usuario solicitó: \"{prompt}\".\n"
                f"A continuación tienes los datos extraídos en tiempo real:\n"
                f"Título del reporte: {report_data['titulo']}\n"
                f"Muestra de datos (primeras 5 filas): {report_data['filas'][:5]}\n"
                f"Redacta un resumen ejecutivo profesional y conciso (2 a 3 párrafos cortos) destacando los hallazgos principales "
                f"y una recomendación estratégica directa para el administrador. No uses formato markdown agresivo ni código."
            )
            resumen_narrativo = ai_provider.generate_text(summary_prompt).strip()
        except Exception:
            resumen_narrativo = ""

    if not resumen_narrativo:
        if intent == "top_productos":
            resumen_narrativo = f"El análisis de productos más vendidos para {tenant_name} evidencia una sólida rotación en las líneas principales de indumentaria. Se recomienda mantener stock de seguridad en las tallas centrales."
        elif intent == "riesgo_stock":
            resumen_narrativo = f"Se han detectado {len(report_data['filas'])} variantes de prendas en nivel crítico o por debajo del stock mínimo. Se aconseja emitir órdenes de compra inmediatas para evitar pérdida de ventas."
        elif intent == "comparativa_trimestral":
            resumen_narrativo = f"La comparativa trimestral refleja un comportamiento positivo entre sucursales, con un crecimiento constante en los puntos de venta principales."
        else:
            resumen_narrativo = f"El desempeño consolidado de ventas por sucursal para {tenant_name} muestra un flujo saludable de transacciones comerciales durante el período analizado."

    report_data["prompt_original"] = prompt
    report_data["empresa"] = tenant_name
    report_data["tenant_id"] = tenant_id
    report_data["resumen_ejecutivo"] = resumen_narrativo
    report_data["generado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return report_data


# ── EXPORTACIÓN A PDF (REPORTLAB) Y EXCEL (OPENPYXL) (RF27) ──

def export_report_to_pdf(report_data: dict[str, Any], tenant_name: str) -> io.BytesIO:
    """Genera archivo PDF profesional y estilizado del reporte (RF27)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    # Estilos tipográficos
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E1B4B"),
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#6B7280"),
    )
    summary_title_style = ParagraphStyle(
        "SummaryTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4338CA"),
    )
    summary_body_style = ParagraphStyle(
        "SummaryBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#374151"),
    )
    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#111827"),
    )
    header_cell_style = ParagraphStyle(
        "HeaderCellText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    story = []

    # Encabezado
    story.append(Paragraph(f"FashionStore SaaS — {tenant_name}", title_style))
    story.append(Paragraph(f"<b>Reporte:</b> {report_data.get('titulo', 'Reporte Ejecutivo')} | <b>Fecha:</b> {report_data.get('generado_en', datetime.now().strftime('%Y-%m-%d %H:%M'))}", subtitle_style))
    story.append(Spacer(1, 14))

    # Resumen Ejecutivo
    story.append(Paragraph("Resumen Ejecutivo y Análisis IA", summary_title_style))
    story.append(Spacer(1, 4))
    resumen = report_data.get("resumen_ejecutivo", "Sin observaciones.")
    story.append(Paragraph(resumen.replace("\n", "<br/>"), summary_body_style))
    story.append(Spacer(1, 16))

    # Tabla de datos
    columnas = report_data.get("columnas", [])
    filas = report_data.get("filas", [])

    if columnas and filas:
        table_data = []
        # Header
        table_data.append([Paragraph(str(col), header_cell_style) for col in columnas])
        # Rows
        for row in filas[:25]:  # Máximo 25 filas para asegurar legibilidad
            table_row = []
            for col in columnas:
                val = row.get(col, "")
                table_row.append(Paragraph(str(val), cell_style))
            table_data.append(table_row)

        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312E81")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F9FAFB")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ])
        )
        story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def export_report_to_excel(report_data: dict[str, Any], tenant_name: str) -> io.BytesIO:
    """Genera archivo de Excel (.xlsx) formateado con openpyxl (RF27)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte Ejecutivo"

    # Estilos
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
    title_font = Font(name="Calibri", size=14, bold=True, color="1E1B4B")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="6B7280")
    thin_border = Border(
        left=Side(style="thin", color="E5E7EB"),
        right=Side(style="thin", color="E5E7EB"),
        top=Side(style="thin", color="E5E7EB"),
        bottom=Side(style="thin", color="E5E7EB"),
    )
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    # Encabezado del documento
    ws["A1"] = f"FashionStore SaaS — {tenant_name}"
    ws["A1"].font = title_font
    ws["A2"] = f"Reporte: {report_data.get('titulo', 'Reporte Ejecutivo')} | Generado: {report_data.get('generado_en', datetime.now().strftime('%Y-%m-%d %H:%M'))}"
    ws["A2"].font = subtitle_font

    ws["A4"] = "Resumen Ejecutivo (IA):"
    ws["A4"].font = Font(name="Calibri", size=10, bold=True, color="4338CA")
    ws["A5"] = report_data.get("resumen_ejecutivo", "")
    ws["A5"].font = Font(name="Calibri", size=10, color="374151")

    # Tabla de datos a partir de fila 7
    columnas = report_data.get("columnas", [])
    filas = report_data.get("filas", [])
    start_row = 7

    for col_idx, col_name in enumerate(columnas, start=1):
        cell = ws.cell(row=start_row, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r_idx, row_dict in enumerate(filas, start=start_row + 1):
        is_zebra = (r_idx % 2 == 0)
        for c_idx, col_name in enumerate(columnas, start=1):
            val = row_dict.get(col_name, "")
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.border = thin_border
            if is_zebra:
                cell.fill = zebra_fill
            if isinstance(val, (int, float, Decimal)):
                cell.alignment = Alignment(horizontal="right")

    # Autoajuste de anchos de columna
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len and cell.row > 5:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

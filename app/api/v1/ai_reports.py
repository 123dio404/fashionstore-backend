from typing import Any
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_ai_plan, require_tenant
from app.models.tenant import Tenant
from app.services import ai_report_service

router = APIRouter(prefix="/ai-reports", tags=["ai-reports"])


class AIQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Consulta analítica en lenguaje natural (texto o voz)")


class ExportReportRequest(BaseModel):
    report_data: dict[str, Any] = Field(..., description="Estructura del reporte a exportar")


@router.post(
    "/query",
    summary="Consultar reporte generativo mediante lenguaje natural (texto o voz) (RF23, RF24, RF26, RF28)",
    dependencies=[Depends(require_ai_plan)],
)
def query_generative_report(
    payload: AIQueryRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    """
    Interpreta el lenguaje natural, ejecuta la consulta SQL filtrada por tenant_id
    y redacta el análisis ejecutivo profesional con Gemini.
    Requiere suscripción activa a Plan Profesional (RF28).
    """
    return ai_report_service.process_generative_query(
        db=db,
        tenant_id=tenant_id,
        prompt=payload.query,
    )


@router.get(
    "/sales-by-branch",
    summary="Reporte 1: Ventas por sucursal en un período (RF25-1)",
    dependencies=[Depends(require_ai_plan)],
)
def get_branch_sales(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    return ai_report_service.get_branch_sales_report(db=db, tenant_id=tenant_id, days=days)


@router.get(
    "/top-products",
    summary="Reporte 2: Top productos más vendidos por categoría (RF25-2)",
    dependencies=[Depends(require_ai_plan)],
)
def get_top_products(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    return ai_report_service.get_top_products_report(db=db, tenant_id=tenant_id, limit=limit)


@router.get(
    "/quarterly-comparison",
    summary="Reporte 3: Comparativa de ventas últimos 3 meses (RF25-3)",
    dependencies=[Depends(require_ai_plan)],
)
def get_quarterly_comparison(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    return ai_report_service.get_quarterly_branch_comparison(db=db, tenant_id=tenant_id)


@router.get(
    "/low-stock-risk",
    summary="Reporte 4: Prendas con riesgo inminente de agotamiento (RF25-4)",
    dependencies=[Depends(require_ai_plan)],
)
def get_low_stock_risk(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    return ai_report_service.get_low_stock_risk_report(db=db, tenant_id=tenant_id)


@router.post(
    "/export/pdf",
    summary="Exportar reporte a formato PDF (RF27)",
    dependencies=[Depends(require_ai_plan)],
)
def export_pdf(
    payload: ExportReportRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
):
    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else f"Tenant #{tenant_id}"
    pdf_buffer = ai_report_service.export_report_to_pdf(payload.report_data, tenant_name)

    filename = f"Reporte_FashionStore_{tenant_id}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/export/excel",
    summary="Exportar reporte a formato Excel .xlsx (RF27)",
    dependencies=[Depends(require_ai_plan)],
)
def export_excel(
    payload: ExportReportRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
):
    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else f"Tenant #{tenant_id}"
    xlsx_buffer = ai_report_service.export_report_to_excel(payload.report_data, tenant_name)

    filename = f"Reporte_FashionStore_{tenant_id}.xlsx"
    return StreamingResponse(
        xlsx_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

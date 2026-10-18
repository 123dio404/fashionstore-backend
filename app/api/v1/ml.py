from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role, require_tenant
from app.models.user import Role
from app.services import ml_service

router = APIRouter(prefix="/ml", tags=["machine-learning"])


class DemandPredictionRequest(BaseModel):
    branch_id: int | None = Field(None, description="Filtrar por ID de sucursal específica")
    category_id: int | None = Field(None, description="Filtrar por categoría textil específica")
    days: int = Field(7, ge=1, le=30, description="Días a proyectar (1 a 30 días)")


@router.get("/status", summary="Consultar estado y métricas de modelos ML (RF20, RF21)")
def get_ml_status() -> dict[str, Any]:
    """Retorna información de entrenamiento, algoritmos y métricas de validación."""
    return ml_service.get_model_status()


@router.post(
    "/train",
    summary="Generar datos sintéticos y reentrenar modelos (RF19, RF20, RF21)",
    dependencies=[Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))],
)
def train_ml_models() -> dict[str, Any]:
    """Genera nuevo dataset sintético y reentrena Random Forest y K-Means."""
    return ml_service.train_models()


@router.post("/predict-demand", summary="Predecir demanda de prendas y alertas de inventario (RF20)")
def predict_demand(
    request: DemandPredictionRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    """Calcula demanda estimada para las sucursales del tenant autenticado."""
    return ml_service.predict_demand(
        db=db,
        tenant_id=tenant_id,
        branch_id=request.branch_id,
        category_id=request.category_id,
        days=request.days,
    )


@router.get("/customer-segments", summary="Segmentación de clientes RFM con K-Means (RF21)")
def get_customer_segments(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    """Retorna distribución de clientes en los 4 segmentos RFM con estrategias recomendadas."""
    return ml_service.get_customer_segmentation_summary(db=db, tenant_id=tenant_id)


@router.get("/dashboard", summary="Dashboard analítico de Machine Learning (RF22)")
def get_ml_dashboard(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
) -> dict[str, Any]:
    """Compila pronósticos de demanda, riesgos de inventario y segmentación de clientes."""
    return ml_service.get_ml_dashboard_data(db=db, tenant_id=tenant_id)

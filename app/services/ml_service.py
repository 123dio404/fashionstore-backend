from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.clustering_model import SEGMENT_DEFINITIONS, clustering_model
from app.ml.demand_model import demand_model
from app.models.branch import Branch
from app.models.commerce import Sale, SaleItem
from app.models.inventory import Stock
from app.models.product import Category, Product, ProductVariant


def get_model_status() -> dict[str, Any]:
    """Retorna el estado, algoritmos y métricas de ambos modelos de ML (RF20, RF21)."""
    return {
        "supervised_demand_model": {
            "name": "Predicción de Demanda Textil",
            "algorithm": demand_model.metrics.get("algorithm", "RandomForestRegressor"),
            "trained": demand_model.model is not None,
            "trained_at": demand_model.trained_at,
            "metrics": {
                "r2_score": demand_model.metrics.get("r2_score"),
                "mae": demand_model.metrics.get("mae"),
                "rmse": demand_model.metrics.get("rmse"),
                "total_samples": demand_model.metrics.get("total_samples"),
            },
        },
        "unsupervised_clustering_model": {
            "name": "Segmentación de Clientes RFM",
            "algorithm": clustering_model.metrics.get("algorithm", "K-Means (k=4)"),
            "trained": clustering_model.model is not None,
            "trained_at": clustering_model.trained_at,
            "metrics": {
                "silhouette_score": clustering_model.metrics.get("silhouette_score"),
                "inertia": clustering_model.metrics.get("inertia"),
                "clusters_count": clustering_model.metrics.get("clusters_count", 4),
                "total_samples": clustering_model.metrics.get("total_samples"),
            },
            "segments_metadata": SEGMENT_DEFINITIONS,
        },
    }


def train_models() -> dict[str, Any]:
    """Dispara la generación de datos y reentrenamiento de ambos modelos."""
    demand_metrics = demand_model.train()
    cluster_metrics = clustering_model.train()
    return {
        "message": "Modelos entrenados y guardados con éxito",
        "demand_metrics": demand_metrics,
        "clustering_metrics": cluster_metrics,
    }


def predict_demand(
    db: Session,
    tenant_id: int,
    branch_id: int | None = None,
    category_id: int | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    Genera predicción de demanda para sucursales del tenant (RF20).
    Compara la demanda pronosticada contra el inventario físico disponible en la base de datos
    para detectar riesgos de desabastecimiento.
    """
    # Validar sucursales del tenant
    branch_query = select(Branch).where(Branch.tenant_id == tenant_id, Branch.is_active == True)
    if branch_id is not None:
        branch_query = branch_query.where(Branch.id == branch_id)
    branches = db.scalars(branch_query).all()

    if not branches:
        return {"error": "No se encontraron sucursales activas para este tenant", "proyecciones": []}

    categories = db.scalars(select(Category)).all()
    if category_id is not None:
        categories = [c for c in categories if c.id == category_id]

    projections = []
    stock_risk_alerts = []

    for branch in branches:
        for cat in categories:
            # Obtener precio promedio de productos de esta categoría en la empresa
            avg_price_res = db.execute(
                select(func.avg(Product.price))
                .where(
                    Product.tenant_id == tenant_id,
                    Product.category_id == cat.id,
                    Product.is_active == True,
                )
            ).scalar()
            base_price = float(avg_price_res or 99.99)

            # Obtener stock físico disponible actual en esta sucursal y categoría
            available_stock = db.execute(
                select(func.coalesce(func.sum(Stock.physical_stock - Stock.reserved_stock), 0))
                .join(ProductVariant, ProductVariant.id == Stock.variant_id)
                .join(Product, Product.id == ProductVariant.product_id)
                .where(
                    Stock.branch_id == branch.id,
                    Product.category_id == cat.id,
                    Product.tenant_id == tenant_id,
                )
            ).scalar() or 0

            # Proyección para los próximos N días
            daily_forecast = demand_model.forecast_days(
                branch_id=branch.id,
                category_id=cat.id,
                base_price=base_price,
                days=days,
            )

            total_projected_units = sum(d["demanda_estimada_unidades"] for d in daily_forecast)
            total_projected_revenue = sum(d["ingresos_proyectados_bs"] for d in daily_forecast)

            # Evaluación de riesgo de stock
            stock_deficit = round(total_projected_units - available_stock, 1)
            is_risk = stock_deficit > 0

            item = {
                "sucursal_id": branch.id,
                "sucursal_nombre": branch.name,
                "categoria_id": cat.id,
                "categoria_nombre": cat.name,
                "precio_promedio_bs": round(base_price, 2),
                "stock_disponible_actual": int(available_stock),
                "demanda_total_proyectada": round(total_projected_units, 1),
                "ingresos_totales_proyectados_bs": round(total_projected_revenue, 2),
                "alerta_desabastecimiento": is_risk,
                "deficit_unidades_estimado": max(0.0, stock_deficit),
                "pronostico_diario": daily_forecast,
            }
            projections.append(item)

            if is_risk:
                stock_risk_alerts.append({
                    "sucursal": branch.name,
                    "categoria": cat.name,
                    "stock_actual": int(available_stock),
                    "demanda_esperada": round(total_projected_units, 1),
                    "unidades_sugeridas_reorden": int(stock_deficit + 10),
                })

    return {
        "tenant_id": tenant_id,
        "dias_pronostico": days,
        "total_sucursales_evaluadas": len(branches),
        "total_categorias_evaluadas": len(categories),
        "alertas_riesgo_stock": stock_risk_alerts,
        "proyecciones": projections,
    }


def get_customer_segmentation_summary(db: Session, tenant_id: int) -> dict[str, Any]:
    """
    Retorna la segmentación de clientes RFM procesada por K-Means (RF21).
    Utiliza métricas de ventas reales registradas para el tenant o el dataset enriquecido.
    """
    # Métricas reales de clientes en la base de datos
    sales_by_client = db.execute(
        select(
            Sale.client_id,
            func.max(Sale.sale_date).label("last_sale"),
            func.count(Sale.id).label("freq"),
            func.sum(Sale.total).label("total_spent"),
        )
        .where(Sale.tenant_id == tenant_id, Sale.client_id.isnot(None))
        .group_by(Sale.client_id)
    ).all()

    now = datetime.now()
    scored_clients = []

    for client_id, last_sale, freq, total_spent in sales_by_client:
        recency = (now - last_sale.replace(tzinfo=None)).days if last_sale else 30
        res = clustering_model.predict_customer(
            recencia_dias=max(0, recency),
            frecuencia_compras=int(freq),
            monto_total_bs=float(total_spent or 0),
        )
        res["cliente_id"] = client_id
        scored_clients.append(res)

    # Si hay pocos clientes reales en el tenant, complementar con la distribución del modelo
    base_summary = clustering_model.metrics.get("segment_summary", [])

    return {
        "tenant_id": tenant_id,
        "algoritmo": "K-Means (k=4) con métricas RFM",
        "silhouette_score": clustering_model.metrics.get("silhouette_score", 0.55),
        "segment_distribution": base_summary,
        "clientes_evaluados_bd": scored_clients,
        "estrategias_recomendadas": [
            {
                "segmento": "VIP / Alto Valor",
                "color": "#10B981",
                "accion": "Asignar asesor de estilo personalizado y acceso exclusivo a nuevos lanzamientos.",
            },
            {
                "segmento": "Leales / Frecuentes",
                "color": "#3B82F6",
                "accion": "Incentivar con descuentos escalonados en compras combinadas (cross-selling).",
            },
            {
                "segmento": "Ocasionales / Recientes",
                "color": "#F59E0B",
                "accion": "Enviar cupón del 15% válido para su próxima compra dentro de los siguientes 15 días.",
            },
            {
                "segmento": "En Riesgo / Inactivos",
                "color": "#EF4444",
                "accion": "Campaña de re-enganche textil con prendas básicas en liquidación.",
            },
        ],
    }


def get_ml_dashboard_data(db: Session, tenant_id: int) -> dict[str, Any]:
    """
    Compila todas las métricas del módulo ML para alimentar el Dashboard interactivo (RF22).
    """
    status = get_model_status()
    predictions = predict_demand(db, tenant_id, days=7)
    segments = get_customer_segmentation_summary(db, tenant_id)

    # Top categorías con mayor demanda esperada
    cat_demand: dict[str, float] = {}
    for proj in predictions.get("proyecciones", []):
        cat_name = proj["categoria_nombre"]
        cat_demand[cat_name] = cat_demand.get(cat_name, 0.0) + proj["demanda_total_proyectada"]

    top_demand_categories = sorted(
        [{"categoria": k, "demanda_estimada": round(v, 1)} for k, v in cat_demand.items()],
        key=lambda x: x["demanda_estimada"],
        reverse=True,
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "tenant_id": tenant_id,
        "status": status,
        "top_demand_categories": top_demand_categories,
        "stock_risk_alerts": predictions.get("alertas_riesgo_stock", []),
        "proyecciones_resumen": predictions.get("proyecciones", [])[:6],
        "segmentacion_clientes": segments,
    }

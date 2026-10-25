import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_FILE = MODELS_DIR / "demand_model.joblib"


class DemandForecastingModel:
    """
    Modelo supervisado de predicción de demanda de prendas (RF20).
    Utiliza Random Forest Regressor de scikit-learn entrenado sobre factores
    de estacionalidad, sucursal, categoría textil y días de la semana.
    """

    FEATURES = ["branch_id", "category_id", "day_of_week", "month", "is_weekend", "promotion", "precio"]
    TARGET = "demanda_unidades"

    def __init__(self):
        self.model: RandomForestRegressor | None = None
        self.metrics: dict[str, Any] = {}
        self.trained_at: str | None = None
        self.load()

    def train(self, df: pd.DataFrame | None = None) -> dict[str, Any]:
        """Entrena el modelo y guarda los pesos con joblib."""
        if df is None:
            from app.ml.synthetic_data import DATA_DIR, generate_synthetic_sales
            csv_path = DATA_DIR / "synthetic_sales.csv"
            if not csv_path.exists():
                df = generate_synthetic_sales()
            else:
                df = pd.read_csv(csv_path)

        X = df[self.FEATURES]
        y = df[self.TARGET]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        regressor = RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        regressor.fit(X_train, y_train)

        # Evaluación
        y_pred = regressor.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        self.model = regressor
        self.trained_at = datetime.now().isoformat()
        self.metrics = {
            "r2_score": round(r2, 4),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "total_samples": len(df),
            "test_samples": len(y_test),
            "trained_at": self.trained_at,
            "algorithm": "RandomForestRegressor (100 estimators, max_depth=12)",
        }

        # Guardar en disco
        payload = {
            "model": self.model,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
            "features": self.FEATURES,
        }
        joblib.dump(payload, MODEL_FILE)
        return self.metrics

    def load(self) -> bool:
        """Carga el modelo guardado si existe."""
        if MODEL_FILE.exists():
            try:
                data = joblib.load(MODEL_FILE)
                self.model = data["model"]
                self.metrics = data.get("metrics", {})
                self.trained_at = data.get("trained_at")
                return True
            except Exception:
                return False
        return False

    def predict_single(
        self,
        branch_id: int,
        category_id: int,
        day_of_week: int,
        month: int,
        is_weekend: int,
        precio: float,
        promotion: int = 0,
    ) -> float:
        """Predice demanda esperada en unidades para un escenario puntual."""
        if self.model is None:
            self.train()
        features = pd.DataFrame([{
            "branch_id": branch_id,
            "category_id": category_id,
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": is_weekend,
            "promotion": promotion,
            "precio": precio,
        }])
        pred = self.model.predict(features)[0]
        return max(0.0, float(round(pred, 1)))

    def forecast_days(
        self,
        branch_id: int,
        category_id: int,
        base_price: float,
        days: int = 7
    ) -> list[dict[str, Any]]:
        """Genera proyección de demanda día por día para los próximos N días."""
        if self.model is None:
            self.train()

        forecasts = []
        start_date = datetime.now()

        for i in range(1, days + 1):
            target_date = start_date + timedelta(days=i)
            day_of_week = target_date.weekday()
            is_weekend = 1 if day_of_week in [4, 5, 6] else 0
            month = target_date.month

            pred_units = self.predict_single(
                branch_id=branch_id,
                category_id=category_id,
                day_of_week=day_of_week,
                month=month,
                is_weekend=is_weekend,
                precio=base_price,
                promotion=0
            )

            # Stock de seguridad recomendado: Demanda estimada * factor de variabilidad (1.25)
            safety_stock = int(np.ceil(pred_units * 1.25))

            forecasts.append({
                "fecha": target_date.strftime("%Y-%m-%d"),
                "dia_semana": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][day_of_week],
                "es_fin_de_semana": bool(is_weekend),
                "demanda_estimada_unidades": pred_units,
                "ingresos_proyectados_bs": round(pred_units * base_price, 2),
                "stock_seguridad_recomendado": safety_stock,
            })
        return forecasts


# Singleton global
demand_model = DemandForecastingModel()


if __name__ == "__main__":
    metrics = demand_model.train()
    print("Modelo supervisado entrenado exitosamente:", metrics)
    sample_forecast = demand_model.forecast_days(branch_id=1, category_id=1, base_price=79.99, days=7)
    print("Pronóstico próximos 7 días:")
    for f in sample_forecast:
        print(f" - {f['fecha']} ({f['dia_semana']}): {f['demanda_estimada_unidades']} u. (Ingresos: {f['ingresos_proyectados_bs']} Bs.)")

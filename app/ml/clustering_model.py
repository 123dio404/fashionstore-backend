from datetime import datetime
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_FILE = MODELS_DIR / "clustering_model.joblib"


SEGMENT_DEFINITIONS = {
    "VIP": {
        "nombre": "Clientes VIP / Alto Valor",
        "badge_color": "#10B981",  # Verde esmeralda
        "descripcion": "Compradores recurrentes con alta frecuencia de visita y ticket promedio superior.",
        "estrategia": "Atención prioritaria, invitaciones a ventas privadas y catálogo exclusivo.",
    },
    "LEAL": {
        "nombre": "Clientes Leales / Frecuentes",
        "badge_color": "#3B82F6",  # Azul moderno
        "descripcion": "Visitan la tienda regularmente y mantienen un flujo de compra estable.",
        "estrategia": "Programa de puntos y descuentos en nuevas colecciones.",
    },
    "OCASIONAL": {
        "nombre": "Clientes Ocasionales / Recientes",
        "badge_color": "#F59E0B",  # Ámbar
        "descripcion": "Compras esporádicas o clientes que acaban de incorporarse a la marca.",
        "estrategia": "Cupones de segunda compra y recordatorios por temporadas.",
    },
    "RIESGO": {
        "nombre": "Clientes en Riesgo / Inactivos",
        "badge_color": "#EF4444",  # Rojo
        "descripcion": "No realizan compras desde hace varios meses; riesgo alto de pérdida.",
        "estrategia": "Campañas de reactivación por WhatsApp/email con descuentos especiales.",
    },
}


class CustomerClusteringModel:
    """
    Modelo no supervisado de segmentación de clientes RFM (RF21).
    Utiliza K-Means clustering (k=4) y StandardScaler de scikit-learn.
    """

    FEATURES = ["recencia_dias", "frecuencia_compras", "monto_total_bs"]

    def __init__(self):
        self.model: KMeans | None = None
        self.scaler: StandardScaler | None = None
        self.cluster_mapping: dict[int, str] = {}
        self.metrics: dict[str, Any] = {}
        self.trained_at: str | None = None
        self.load()

    def train(self, df: pd.DataFrame | None = None) -> dict[str, Any]:
        """Entrena el clustering K-Means sobre métricas RFM."""
        if df is None:
            from app.ml.synthetic_data import DATA_DIR, generate_synthetic_customers
            csv_path = DATA_DIR / "synthetic_customers.csv"
            if not csv_path.exists():
                df = generate_synthetic_customers()
            else:
                df = pd.read_csv(csv_path)

        X = df[self.FEATURES].copy()

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Mapear clusters numéricos a perfiles de negocio según sus centroides reales
        # Mayor frecuencia y gasto = VIP; Mayor recencia = RIESGO
        centers = scaler.inverse_transform(kmeans.cluster_centers_)
        cluster_info = []
        for i, center in enumerate(centers):
            cluster_info.append({
                "cluster_id": i,
                "recencia_media": center[0],
                "frecuencia_media": center[1],
                "monto_medio": center[2],
            })

        # Ordenar por valor monetario y frecuencia para asignar etiquetas coherentes
        sorted_by_monetary = sorted(cluster_info, key=lambda c: c["monto_medio"], reverse=True)
        # El más alto es VIP
        vip_id = sorted_by_monetary[0]["cluster_id"]
        # El segundo más alto es LEAL
        leal_id = sorted_by_monetary[1]["cluster_id"]

        # De los 2 restantes, el de mayor recencia es RIESGO y el otro OCASIONAL
        remaining = sorted(sorted_by_monetary[2:], key=lambda c: c["recencia_media"], reverse=True)
        riesgo_id = remaining[0]["cluster_id"]
        ocasional_id = remaining[1]["cluster_id"]

        self.cluster_mapping = {
            vip_id: "VIP",
            leal_id: "LEAL",
            ocasional_id: "OCASIONAL",
            riesgo_id: "RIESGO",
        }

        # Silhouette score
        sil_score = float(silhouette_score(X_scaled, labels))
        inertia = float(kmeans.inertia_)

        self.model = kmeans
        self.scaler = scaler
        self.trained_at = datetime.now().isoformat()

        # Resumen de segmentos
        df_scored = df.copy()
        df_scored["cluster"] = labels
        df_scored["segmento_key"] = df_scored["cluster"].map(self.cluster_mapping)

        segment_summary = []
        for key in ["VIP", "LEAL", "OCASIONAL", "RIESGO"]:
            sub = df_scored[df_scored["segmento_key"] == key]
            definition = SEGMENT_DEFINITIONS[key]
            segment_summary.append({
                "segmento_key": key,
                "nombre": definition["nombre"],
                "color": definition["badge_color"],
                "total_clientes": len(sub),
                "porcentaje": round(len(sub) / len(df) * 100, 1),
                "recencia_promedio_dias": round(float(sub["recencia_dias"].mean()), 1) if not sub.empty else 0,
                "frecuencia_promedio": round(float(sub["frecuencia_compras"].mean()), 1) if not sub.empty else 0,
                "gasto_promedio_bs": round(float(sub["monto_total_bs"].mean()), 2) if not sub.empty else 0,
                "descripcion": definition["descripcion"],
                "estrategia_recomendada": definition["estrategia"],
            })

        self.metrics = {
            "silhouette_score": round(sil_score, 4),
            "inertia": round(inertia, 2),
            "total_samples": len(df),
            "clusters_count": 4,
            "trained_at": self.trained_at,
            "segment_summary": segment_summary,
            "algorithm": "K-Means (k=4) con StandardScaler (Métricas RFM)",
        }

        # Guardar en disco
        payload = {
            "model": self.model,
            "scaler": self.scaler,
            "cluster_mapping": self.cluster_mapping,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
        }
        joblib.dump(payload, MODEL_FILE)
        return self.metrics

    def load(self) -> bool:
        """Carga modelo guardado si existe."""
        if MODEL_FILE.exists():
            try:
                data = joblib.load(MODEL_FILE)
                self.model = data["model"]
                self.scaler = data["scaler"]
                self.cluster_mapping = data.get("cluster_mapping", {})
                self.metrics = data.get("metrics", {})
                self.trained_at = data.get("trained_at")
                return True
            except Exception:
                return False
        return False

    def predict_customer(self, recencia_dias: int, frecuencia_compras: int, monto_total_bs: float) -> dict[str, Any]:
        """Clasifica un cliente individual según sus métricas RFM."""
        if self.model is None or self.scaler is None:
            self.train()

        X = pd.DataFrame([{
            "recencia_dias": recencia_dias,
            "frecuencia_compras": frecuencia_compras,
            "monto_total_bs": monto_total_bs,
        }])
        X_scaled = self.scaler.transform(X)
        cluster_id = int(self.model.predict(X_scaled)[0])
        seg_key = self.cluster_mapping.get(cluster_id, "OCASIONAL")
        info = SEGMENT_DEFINITIONS.get(seg_key, SEGMENT_DEFINITIONS["OCASIONAL"])

        return {
            "cluster_id": cluster_id,
            "segmento_key": seg_key,
            "nombre": info["nombre"],
            "color": info["badge_color"],
            "descripcion": info["descripcion"],
            "estrategia_recomendada": info["estrategia"],
            "metricas_ingresadas": {
                "recencia_dias": recencia_dias,
                "frecuencia_compras": frecuencia_compras,
                "monto_total_bs": monto_total_bs,
            },
        }


# Singleton global
clustering_model = CustomerClusteringModel()


if __name__ == "__main__":
    metrics = clustering_model.train()
    print("Modelo no supervisado K-Means entrenado exitosamente:")
    print(f"Silhouette Score: {metrics['silhouette_score']} | Total Muestras: {metrics['total_samples']}")
    for seg in metrics["segment_summary"]:
        print(f" - [{seg['nombre']}]: {seg['total_clientes']} clientes ({seg['porcentaje']}%) | Gasto Promedio: {seg['gasto_promedio_bs']} Bs.")

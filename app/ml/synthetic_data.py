import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def generate_synthetic_sales(num_records: int = 3500) -> pd.DataFrame:
    """
    Genera dataset sintético realista de demanda textil (RF19).
    Simula estacionalidad, efecto fin de semana, promociones y categorías.
    """
    random.seed(42)
    np.random.seed(42)

    categories = [
        {"id": 1, "name": "Polos y Camisetas", "base_price": 79.99, "winter_factor": 0.7, "summer_factor": 1.4},
        {"id": 2, "name": "Camisas y Blusas", "base_price": 129.99, "winter_factor": 1.0, "summer_factor": 1.1},
        {"id": 3, "name": "Pantalones y Jeans", "base_price": 189.99, "winter_factor": 1.2, "summer_factor": 0.9},
        {"id": 4, "name": "Vestidos", "base_price": 220.00, "winter_factor": 0.6, "summer_factor": 1.6},
        {"id": 5, "name": "Chaquetas y Abrigos", "base_price": 320.00, "winter_factor": 2.2, "summer_factor": 0.3},
        {"id": 6, "name": "Calzado y Zapatos", "base_price": 260.00, "winter_factor": 1.1, "summer_factor": 1.1},
        {"id": 7, "name": "Accesorios y Bufandas", "base_price": 45.00, "winter_factor": 1.5, "summer_factor": 0.8},
    ]

    branches = [
        {"id": 1, "tenant_id": 1, "traffic_mult": 1.2},  # Sucursal Centro
        {"id": 2, "tenant_id": 1, "traffic_mult": 0.9},  # Sucursal Norte
        {"id": 3, "tenant_id": 2, "traffic_mult": 1.5},  # Sucursal Ventura Mall
        {"id": 4, "tenant_id": 2, "traffic_mult": 1.1},  # Sucursal Las Brisas
    ]

    start_date = datetime.now() - timedelta(days=365)
    records = []

    for _ in range(num_records):
        random_days = random.randint(0, 365)
        dt = start_date + timedelta(days=random_days)
        branch = random.choice(branches)
        category = random.choice(categories)

        day_of_week = dt.weekday()  # 0=Lunes, 6=Domingo
        is_weekend = 1 if day_of_week in [4, 5, 6] else 0  # Viernes a Domingo
        month = dt.month

        # Factores estacionales
        is_winter_month = month in [5, 6, 7, 8]
        seasonal_mult = category["winter_factor"] if is_winter_month else category["summer_factor"]

        # Efecto fin de semana
        weekend_mult = 1.45 if is_weekend else 0.9

        # Promoción aleatoria (15% de probabilidad)
        has_promo = 1 if random.random() < 0.15 else 0
        promo_mult = 1.35 if has_promo else 1.0

        # Precio con leve variación
        price_variation = round(category["base_price"] * random.uniform(0.9, 1.1), 2)

        # Cálculo de demanda en unidades
        base_demand = random.uniform(3.0, 9.0)
        demand = base_demand * branch["traffic_mult"] * seasonal_mult * weekend_mult * promo_mult
        demand = max(1, int(round(demand + np.random.normal(0, 1.2))))

        records.append({
            "fecha": dt.strftime("%Y-%m-%d"),
            "tenant_id": branch["tenant_id"],
            "branch_id": branch["id"],
            "category_id": category["id"],
            "categoria_nombre": category["name"],
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": is_weekend,
            "promotion": has_promo,
            "precio": price_variation,
            "demanda_unidades": demand,
        })

    df = pd.DataFrame(records)
    csv_path = DATA_DIR / "synthetic_sales.csv"
    df.to_csv(csv_path, index=False)
    return df


def generate_synthetic_customers(num_customers: int = 500) -> pd.DataFrame:
    """
    Genera dataset sintético de clientes con métricas RFM (Recencia, Frecuencia, Monto) (RF19/RF21).
    Distribuido en 4 perfiles realistas de compra de indumentaria textil.
    """
    random.seed(42)
    np.random.seed(42)

    records = []
    # Perfiles:
    # 1: VIP (Alta frecuencia, alto gasto, baja recencia) -> 15%
    # 2: Leales/Frecuentes (Media frecuencia, gasto medio-alto, baja recencia) -> 30%
    # 3: Ocasionales/Nuevos (Baja frecuencia, gasto medio, recencia media) -> 35%
    # 4: Inactivos/En riesgo (Baja frecuencia, bajo gasto, alta recencia) -> 20%

    for i in range(1, num_customers + 1):
        tenant_id = 1 if i % 2 == 0 else 2
        profile_roll = random.random()

        if profile_roll < 0.15:
            # VIP
            recency = random.randint(1, 20)
            frequency = random.randint(15, 45)
            monetary = round(frequency * random.uniform(180, 350), 2)
            profile_name = "VIP / Alto Valor"
        elif profile_roll < 0.45:
            # Leales
            recency = random.randint(5, 45)
            frequency = random.randint(6, 18)
            monetary = round(frequency * random.uniform(100, 220), 2)
            profile_name = "Leal / Frecuente"
        elif profile_roll < 0.80:
            # Ocasionales
            recency = random.randint(30, 120)
            frequency = random.randint(2, 6)
            monetary = round(frequency * random.uniform(70, 160), 2)
            profile_name = "Ocasional"
        else:
            # Inactivos / En riesgo
            recency = random.randint(130, 365)
            frequency = random.randint(1, 3)
            monetary = round(frequency * random.uniform(50, 120), 2)
            profile_name = "Inactivo / En Riesgo"

        records.append({
            "cliente_id": i,
            "tenant_id": tenant_id,
            "recencia_dias": recency,
            "frecuencia_compras": frequency,
            "monto_total_bs": monetary,
            "ticket_promedio_bs": round(monetary / max(frequency, 1), 2),
            "perfil_esperado": profile_name,
        })

    df = pd.DataFrame(records)
    csv_path = DATA_DIR / "synthetic_customers.csv"
    df.to_csv(csv_path, index=False)
    return df


if __name__ == "__main__":
    df_sales = generate_synthetic_sales()
    print(f"Dataset de ventas generado con {len(df_sales)} registros en {DATA_DIR / 'synthetic_sales.csv'}")
    df_cust = generate_synthetic_customers()
    print(f"Dataset de clientes generado con {len(df_cust)} registros en {DATA_DIR / 'synthetic_customers.csv'}")

"""Siembra el historial de compras del prototipo de Figma en la base.

Convierte las órdenes demo `ORD-4821`, `ORD-4765` y `ORD-4690` (los datos estáticos
de `figma-data.ts`) en ventas reales del cliente demo (`cliente@fashionstore.com`),
con sus líneas, pago y movimiento de inventario. Idempotente.

Es un wrapper de `app.services.seed_service.ensure_demo_purchases`. Si se prefiere
que corra al arranque de la API, activar `SEED_DEMO_PURCHASES=true`.

Uso en local (con el entorno virtual activo):
    python -m scripts.seed_demo_purchases

Contra una base externa (por ejemplo la de Render):
    DATABASE_URL='postgresql+psycopg2://usuario:clave@host/db' python -m scripts.seed_demo_purchases
"""

from __future__ import annotations

from app.services.seed_service import ensure_demo_purchases


def main() -> int:
    for line in ensure_demo_purchases():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
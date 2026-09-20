"""Crea (o restablece) las cuentas de prueba de los actores del sistema.

Actores (roles) del dominio Fashionstore:
  - Administrador
  - Encargado
  - Cajero
  - Cliente
  - Proveedor

Todas las cuentas usan la contraseña de prueba `admin123`.

Este script es un wrapper de `app.services.seed_service.ensure_demo_users`, que
también se ejecuta automáticamente al arrancar la API (si SEED_DEMO_USERS=true).

Uso en local (con el entorno virtual activo):
    python -m scripts.create_seed_users

Uso en Render (con el servicio api levantado):
    docker compose -f docker-compose.deploy.yml exec api python -m scripts.create_seed_users
"""

from __future__ import annotations

from app.services.seed_service import DEMO_PASSWORD, ensure_demo_users


def main() -> int:
    print(f"Contraseña de prueba: {DEMO_PASSWORD}\n")
    for line in ensure_demo_users():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

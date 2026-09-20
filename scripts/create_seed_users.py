"""Crea (o restablece) las cuentas de prueba de los actores del sistema.

Actores (roles) del dominio Fashionstore:
  - Administrador
  - Encargado
  - Cajero
  - Cliente
  - Proveedor

Todas las cuentas usan la contraseña de prueba `admin123`.

Uso en local (con el entorno virtual activo y DATABASE_URL apuntando a la base):
    python -m scripts.create_seed_users

Uso en Render (con el servicio api levantado):
    docker compose -f docker-compose.deploy.yml exec api python -m scripts.create_seed_users
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import Role, User
from app.services.auth_service import get_role, normalize_email

PASSWORD = "admin123"

# (rol, email genérico, nombre completo)
ACTORS: list[tuple[Role, str, str]] = [
    (Role.ADMINISTRADOR, "admin@fashionstore.com", "Administrador"),
    (Role.ENCARGADO, "encargado@fashionstore.com", "Encargado de tienda"),
    (Role.CAJERO, "cajero@fashionstore.com", "Cajero"),
    (Role.CLIENTE, "cliente@fashionstore.com", "Cliente de prueba"),
    (Role.PROVEEDOR, "proveedor@fashionstore.com", "Proveedor"),
]


def upsert_actor(role: Role, email: str, full_name: str) -> str:
    """Crea el usuario con el rol indicado o restablece sus credenciales si ya existe."""
    db = SessionLocal()
    try:
        normalized = normalize_email(email)
        rol = get_role(db, role)
        user = db.scalar(select(User).where(User.email == normalized))

        if user is None:
            user = User(
                email=normalized,
                full_name=full_name,
                password_hash=get_password_hash(PASSWORD),
                is_active=True,
            )
            user.roles = [rol]
            db.add(user)
            action = "creado"
        else:
            user.full_name = full_name
            user.password_hash = get_password_hash(PASSWORD)
            user.is_active = True
            user.roles = [rol]
            action = "actualizado"

        db.commit()
        return f"{role.value:<13} {action}: {normalized}"
    finally:
        db.close()


def main() -> int:
    print(f"Contraseña de prueba: {PASSWORD}\n")
    for role, email, name in ACTORS:
        print(upsert_actor(role, email, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

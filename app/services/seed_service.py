"""Cuentas de prueba de los actores del dominio (siembra de demo).

Los 5 actores (roles) del sistema y sus cuentas genéricas usan la contraseña
`admin123` y se (re)crean al arrancar la API cuando `SEED_DEMO_USERS=true`
(por defecto). Para producción real, desactivar con `SEED_DEMO_USERS=false`.

La siembra es idempotente: si una cuenta ya existe, restablece su contraseña a
`admin123` y garantiza que tenga el rol correcto.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import Role, User
from app.services.auth_service import get_role, normalize_email

DEMO_PASSWORD = "admin123"

# (rol, email genérico, nombre completo)
DEMO_ACTORS: list[tuple[Role, str, str]] = [
    (Role.ADMINISTRADOR, "admin@fashionstore.com", "Administrador"),
    (Role.ENCARGADO, "encargado@fashionstore.com", "Encargado de tienda"),
    (Role.CAJERO, "cajero@fashionstore.com", "Cajero"),
    (Role.CLIENTE, "cliente@fashionstore.com", "Cliente de prueba"),
    (Role.PROVEEDOR, "proveedor@fashionstore.com", "Proveedor"),
]


def upsert_actor(db, role: Role, email: str, full_name: str) -> str:
    """Crea el usuario con el rol indicado o restablece sus credenciales si ya existe."""
    normalized = normalize_email(email)
    rol = get_role(db, role)
    user = db.scalar(select(User).where(User.email == normalized))

    if user is None:
        user = User(
            email=normalized,
            full_name=full_name,
            password_hash=get_password_hash(DEMO_PASSWORD),
            is_active=True,
        )
        user.roles = [rol]
        db.add(user)
        action = "creado"
    else:
        user.full_name = full_name
        user.password_hash = get_password_hash(DEMO_PASSWORD)
        user.is_active = True
        user.roles = [rol]
        action = "actualizado"

    return f"{role.value}: {normalized} ({action})"


def ensure_demo_users() -> list[str]:
    """Crea/actualiza las 5 cuentas demo. Devuelve un resumen por cuenta."""
    db = SessionLocal()
    results: list[str] = []
    try:
        for role, email, name in DEMO_ACTORS:
            results.append(upsert_actor(db, role, email, name))
        db.commit()
    finally:
        db.close()
    return results

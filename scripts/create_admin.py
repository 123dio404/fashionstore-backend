"""Crea (o promueve) un usuario administrador en la base de datos configurada.

Uso dentro del contenedor:
    docker compose -f docker-compose.deploy.yml exec api python -m scripts.create_admin \\
        --email admin@fashionstore.com --password 'ClaveSegura123' --name 'Administrador'

Uso en local (con el entorno virtual activo y DATABASE_URL apuntando a la base):
    python -m scripts.create_admin --email admin@fashionstore.com --password 'ClaveSegura123'
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import Role, User
from app.services.auth_service import get_role, normalize_email


def upsert_admin(email: str, password: str, full_name: str) -> str:
    """Crea el usuario con rol Administrador o actualiza sus credenciales si ya existe."""
    db = SessionLocal()
    try:
        normalized = normalize_email(email)
        admin_role = get_role(db, Role.ADMINISTRADOR)
        user = db.scalar(select(User).where(User.email == normalized))

        if user is None:
            user = User(
                email=normalized,
                full_name=full_name,
                password_hash=get_password_hash(password),
                is_active=True,
            )
            user.roles = [admin_role]
            db.add(user)
            action = "creado"
        else:
            user.full_name = full_name or user.full_name
            user.password_hash = get_password_hash(password)
            user.is_active = True
            if all(role.nombre != admin_role.nombre for role in user.roles):
                user.roles.append(admin_role)
            action = "actualizado"

        db.commit()
        return f"Administrador {action}: {normalized} (id={user.id})"
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea o promueve un usuario administrador.")
    parser.add_argument("--email", required=True, help="Correo del administrador")
    parser.add_argument("--password", required=True, help="Contraseña (mínimo 8 caracteres)")
    parser.add_argument("--name", default="Administrador", help="Nombre completo")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.", file=sys.stderr)
        return 1

    print(upsert_admin(args.email, args.password, args.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

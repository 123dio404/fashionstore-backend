import enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch


class Role(str, enum.Enum):
    ADMINISTRADOR = "Administrador"
    ENCARGADO = "Encargado"
    CAJERO = "Cajero"
    CLIENTE = "Cliente"
    PROVEEDOR = "Proveedor"


class User(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column("nombre", String(150))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    telefono: Mapped[str | None] = mapped_column("telefono", String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column("password", String(255))
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False)

    roles: Mapped[list["Rol"]] = relationship(secondary="usuario_rol", back_populates="usuarios")

    @property
    def role(self) -> Optional[Role]:
        if not self.roles:
            return None
        try:
            return Role(self.roles[0].nombre)
        except ValueError:
            return None


class Rol(Base):
    __tablename__ = "rol"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)

    usuarios: Mapped[list["User"]] = relationship(secondary="usuario_rol", back_populates="roles")


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True)
    id_rol: Mapped[int] = mapped_column(Integer, ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True)

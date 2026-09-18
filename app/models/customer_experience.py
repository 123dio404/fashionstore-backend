import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Category, Product, ProductVariant, Size
    from app.models.user import User


class FittingSessionStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    PROCESANDO = "procesando"
    COMPLETADA = "completada"
    FALLIDA = "fallida"


class VirtualFittingSession(Base):
    __tablename__ = "sesion_prueba_virtual"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("id_usuario", ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    model_url: Mapped[str | None] = mapped_column("modelo_url", String(500), nullable=True)
    model_format: Mapped[str | None] = mapped_column("modelo_formato", String(10), nullable=True)
    model_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadatos_modelo", JSON, nullable=True)
    status: Mapped[FittingSessionStatus] = mapped_column(
        "estado", String(20), default=FittingSessionStatus.PENDIENTE.value, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    results: Mapped[list["VirtualFittingResult"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class VirtualFittingResult(Base):
    __tablename__ = "resultado_prueba_virtual"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        "id_sesion", ForeignKey("sesion_prueba_virtual.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[int] = mapped_column(
        "id_variante", ForeignKey("producto_variante.id", ondelete="RESTRICT"), index=True
    )
    size_id: Mapped[int | None] = mapped_column(
        "id_talla", ForeignKey("tallas.id", ondelete="RESTRICT"), nullable=True
    )
    result_url: Mapped[str | None] = mapped_column("resultado_url", String(500), nullable=True)
    confidence: Mapped[Decimal] = mapped_column("confianza", Numeric(5, 2), nullable=False)
    result_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadatos", JSON, nullable=True)

    session: Mapped["VirtualFittingSession"] = relationship(back_populates="results")


class UserPreference(Base):
    __tablename__ = "preferencia_usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        "id_usuario", ForeignKey("usuario.id", ondelete="CASCADE"), unique=True, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        "id_categoria", ForeignKey("categoria.id", ondelete="SET NULL"), nullable=True
    )
    preferred_brand: Mapped[str | None] = mapped_column("marca_preferida", String(100), nullable=True)
    preferred_colors: Mapped[list[str] | None] = mapped_column("colores_preferidos", JSON, nullable=True)
    preferred_sizes: Mapped[list[int] | None] = mapped_column("tallas_preferidas", JSON, nullable=True)
    min_price: Mapped[Decimal | None] = mapped_column("precio_minimo", Numeric(12, 2), nullable=True)
    max_price: Mapped[Decimal | None] = mapped_column("precio_maximo", Numeric(12, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category: Mapped["Category | None"] = relationship()


class Recommendation(Base):
    __tablename__ = "recomendacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("id_usuario", ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    recommendation_type: Mapped[str] = mapped_column("tipo", String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column("estado", String(20), default="activa", nullable=False)

    items: Mapped[list["RecommendationItem"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class RecommendationItem(Base):
    __tablename__ = "recomendacion_detalle"
    __table_args__ = (UniqueConstraint("id_recomendacion", "id_producto", name="uq_recomendacion_producto"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        "id_recomendacion", ForeignKey("recomendacion.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        "id_producto", ForeignKey("producto.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[Decimal] = mapped_column("puntuacion", Numeric(6, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column("motivo", Text, nullable=True)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class ChatConversation(Base):
    __tablename__ = "conversacion_chatbot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("id_usuario", ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column("titulo", String(150), nullable=True)
    context: Mapped[dict[str, Any] | None] = mapped_column("contexto", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column("fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("fecha_actualizacion", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.id")


class ChatMessage(Base):
    __tablename__ = "mensaje_chatbot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column("id_conversacion", ForeignKey("conversacion_chatbot.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column("rol", String(20), nullable=False)
    content: Mapped[str] = mapped_column("contenido", Text, nullable=False)
    context: Mapped[dict[str, Any] | None] = mapped_column("contexto", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column("fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False)
    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")

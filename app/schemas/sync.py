from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class SyncItemDetail(BaseModel):
    stock_id: int
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0)


class SyncOperationItem(BaseModel):
    uuid: str = Field(description="UUID v4 único generado en el cliente (PWA o Móvil)")
    type: str = Field(description="Tipo de operación: 'SALE' o 'RESERVATION'")
    created_at: datetime = Field(description="Fecha y hora de registro offline en el cliente")
    branch_id: int = Field(description="Sucursal donde se operó")
    client_id: int | None = Field(default=None, description="ID del cliente (si aplica)")
    total: Decimal = Field(description="Monto total de la transacción")
    payment_method: str = Field(default="efectivo", description="Método de pago (solo contado offline)")
    items: list[SyncItemDetail] = Field(min_length=1, description="Detalle de prendas involucradas")


class SyncBatchRequest(BaseModel):
    operations: list[SyncOperationItem] = Field(min_length=1, description="Lote de operaciones pendientes")


class SyncOperationResult(BaseModel):
    uuid: str
    type: str
    status: str = Field(description="'CONFIRMADO', 'CONFLICTO' o 'DUPLICADO_IDEMPOTENTE'")
    server_id: int | None = None
    message: str | None = None


class SyncBatchResponse(BaseModel):
    processed: int
    confirmed: int
    conflicts: int
    results: list[SyncOperationResult]

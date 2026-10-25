from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_current_user, get_db, require_role
from app.models.exchange import GarmentExchange
from app.models.user import Role, User
from app.schemas.exchange import ExchangeCreateRequest, ExchangeResponse
from app.services.exchange_service import process_garment_exchange

router = APIRouter(prefix="/commerce/exchanges", tags=["exchanges"])
staff = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO, Role.SUPERADMIN))


@router.post("", response_model=ExchangeResponse, status_code=status.HTTP_201_CREATED, dependencies=[staff])
def create_exchange(
    data: ExchangeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registra un cambio de prendas de vestir en tienda (Postventa / Desafío IV).
    Valida plazo máximo de 30 días, disponibilidad de la nueva prenda y emite la nota de cambio.
    """
    return process_garment_exchange(
        db=db,
        cashier_id=user.id,
        data=data,
        current_tenant_id=user.tenant_id,
    )


@router.get("", response_model=list[ExchangeResponse], dependencies=[staff])
def list_exchanges(
    branch_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista el historial de cambios de prendas realizados en la empresa."""
    query = select(GarmentExchange).order_by(GarmentExchange.created_at.desc())
    if user.tenant_id is not None:
        query = query.where(GarmentExchange.tenant_id == user.tenant_id)
    if branch_id is not None:
        query = query.where(GarmentExchange.branch_id == branch_id)
    exchanges = db.scalars(query).all()
    return [
        ExchangeResponse(
            id=e.id,
            original_sale_id=e.original_sale_id,
            branch_id=e.branch_id,
            tenant_id=e.tenant_id,
            returned_stock_id=e.returned_stock_id,
            new_stock_id=e.new_stock_id,
            quantity=e.quantity,
            price_difference=e.price_difference,
            reason=e.reason,
            created_at=e.created_at,
            receipt_number=f"CHG-{e.id:08d}",
        )
        for e in exchanges
    ]


@router.get("/{exchange_id}", response_model=ExchangeResponse, dependencies=[staff])
def get_exchange(
    exchange_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene el comprobante de un cambio de prenda específico."""
    exchange = db.get(GarmentExchange, exchange_id)
    if not exchange:
        raise HTTPException(status_code=404, detail="Registro de cambio no encontrado")
    if user.tenant_id is not None and exchange.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="El cambio pertenece a otra empresa")
    return ExchangeResponse(
        id=exchange.id,
        original_sale_id=exchange.original_sale_id,
        branch_id=exchange.branch_id,
        tenant_id=exchange.tenant_id,
        returned_stock_id=exchange.returned_stock_id,
        new_stock_id=exchange.new_stock_id,
        quantity=exchange.quantity,
        price_difference=exchange.price_difference,
        reason=exchange.reason,
        created_at=exchange.created_at,
        receipt_number=f"CHG-{exchange.id:08d}",
    )

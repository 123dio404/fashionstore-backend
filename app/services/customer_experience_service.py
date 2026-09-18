from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.commerce import Sale, SaleItem
from app.models.customer_experience import (
    ChatConversation, ChatMessage,
    Recommendation,
    RecommendationItem,
    UserPreference,
    VirtualFittingResult,
    VirtualFittingSession,
)
from app.models.inventory import Stock
from app.models.product import Category, Product, ProductVariant, Size
from app.schemas.customer_experience import (
    UserPreferenceUpsert,
    VirtualFittingResultCreate,
    VirtualFittingSessionCreate,
)


def create_fitting_session(db: Session, user_id: int, data: VirtualFittingSessionCreate) -> VirtualFittingSession:
    session = VirtualFittingSession(
        user_id=user_id,
        model_url=data.model_url,
        model_format=data.model_format,
        model_metadata=data.model_metadata,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_fitting_session(db: Session, session_id: int, user_id: int, privileged: bool = False) -> VirtualFittingSession:
    session = db.scalar(
        select(VirtualFittingSession)
        .options(selectinload(VirtualFittingSession.results))
        .where(VirtualFittingSession.id == session_id)
    )
    if session is None:
        raise HTTPException(404, "Virtual fitting session not found")
    if not privileged and session.user_id != user_id:
        raise HTTPException(403, "Insufficient permissions")
    return session


def add_fitting_result(
    db: Session, session: VirtualFittingSession, data: VirtualFittingResultCreate
) -> VirtualFittingResult:
    if db.get(ProductVariant, data.variant_id) is None:
        raise HTTPException(404, "Product variant not found")
    if data.size_id is not None and db.get(Size, data.size_id) is None:
        raise HTTPException(404, "Size not found")
    result = VirtualFittingResult(
        session_id=session.id,
        result_metadata=data.metadata,
        **data.model_dump(exclude={"metadata"}),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def update_fitting_status(db: Session, session: VirtualFittingSession, status: str) -> VirtualFittingSession:
    session.status = status
    db.commit()
    db.refresh(session)
    return session


def upsert_preferences(db: Session, user_id: int, data: UserPreferenceUpsert) -> UserPreference:
    if data.category_id is not None and db.get(Category, data.category_id) is None:
        raise HTTPException(404, "Category not found")
    if data.min_price is not None and data.max_price is not None and data.min_price > data.max_price:
        raise HTTPException(422, "min_price must not exceed max_price")
    preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if preference is None:
        preference = UserPreference(user_id=user_id)
        db.add(preference)
    for key, value in data.model_dump().items():
        setattr(preference, key, value)
    db.commit()
    db.refresh(preference)
    return preference


def get_preferences(db: Session, user_id: int) -> UserPreference | None:
    return db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))


def generate_recommendations(db: Session, user_id: int, limit: int = 10) -> Recommendation:
    preference = get_preferences(db, user_id)
    purchased_categories = {
        row[0]: row[1]
        for row in db.execute(
            select(Product.category_id, func.sum(SaleItem.quantity))
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .join(Stock, Stock.variant_id == ProductVariant.id)
            .join(SaleItem, SaleItem.stock_id == Stock.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.client_id == user_id)
            .group_by(Product.category_id)
        )
    }
    products = list(
        db.scalars(
            select(Product)
            .options(selectinload(Product.variants).selectinload(ProductVariant.stocks))
            .where(Product.is_active.is_(True))
            .order_by(Product.id)
        ).all()
    )
    scored: list[tuple[Product, Decimal, str]] = []
    for product in products:
        available = sum(stock.available_stock for variant in product.variants for stock in variant.stocks)
        if available <= 0:
            continue
        score = Decimal("0")
        reasons: list[str] = []
        if preference:
            if preference.category_id == product.category_id:
                score += 40
                reasons.append("categoría preferida")
            if preference.preferred_brand and preference.preferred_brand.lower() == (product.brand or "").lower():
                score += 25
                reasons.append("marca preferida")
            if preference.min_price is not None and product.price < preference.min_price:
                continue
            if preference.max_price is not None and product.price > preference.max_price:
                continue
        if product.category_id in purchased_categories:
            score += min(25, Decimal(purchased_categories[product.category_id]))
            reasons.append("historial de compras")
        score += min(10, Decimal(available))
        scored.append((product, score, ", ".join(reasons) or "disponibilidad"))
    scored.sort(key=lambda item: (-item[1], item[0].id))
    recommendation = Recommendation(user_id=user_id, recommendation_type="personalizada")
    recommendation.items = [
        RecommendationItem(product_id=product.id, score=score, reason=reason)
        for product, score, reason in scored[:limit]
    ]
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return db.scalar(
        select(Recommendation)
        .options(selectinload(Recommendation.items))
        .where(Recommendation.id == recommendation.id)
    )


def executive_analytics(db: Session, start_date, end_date) -> dict:
    sales = list(
        db.scalars(
            select(Sale).where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
        ).all()
    )
    total_revenue = sum((sale.total for sale in sales), Decimal("0"))
    units_by_sale = dict(
        db.execute(
            select(SaleItem.sale_id, func.sum(SaleItem.quantity))
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
            .group_by(SaleItem.sale_id)
        )
    )
    channel_rows: dict[str, dict] = {}
    for sale in sales:
        channel = channel_rows.setdefault(sale.sale_type, {"orders": 0, "units": 0, "revenue": Decimal("0")})
        channel["orders"] += 1
        channel["units"] += int(units_by_sale.get(sale.id, 0) or 0)
        channel["revenue"] += sale.total
    rotation_rows = db.execute(
        select(
            Product.id,
            Product.name,
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.coalesce(func.sum(Stock.physical_stock), 0),
        )
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(Stock, Stock.variant_id == ProductVariant.id)
        .outerjoin(SaleItem, SaleItem.stock_id == Stock.id)
        .outerjoin(Sale, (Sale.id == SaleItem.sale_id) & (Sale.sale_date >= start_date) & (Sale.sale_date <= end_date))
        .group_by(Product.id, Product.name)
        .order_by(Product.id)
    ).all()
    rotation = [
        {
            "product_id": product_id,
            "product_name": name,
            "units_sold": int(sold or 0),
            "current_stock": int(stock or 0),
            "rotation_rate": (Decimal(sold or 0) / Decimal(stock) if stock else Decimal("0")),
        }
        for product_id, name, sold, stock in rotation_rows
    ]
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_orders": len(sales),
        "total_units": sum(int(value or 0) for value in units_by_sale.values()),
        "total_revenue": total_revenue,
        "average_order_value": total_revenue / len(sales) if sales else Decimal("0"),
        "channels": [{"channel": key, **value} for key, value in sorted(channel_rows.items())],
        "inventory_rotation": rotation,
    }


def create_chat_conversation(db: Session, user_id: int, title=None, context=None):
    conversation = ChatConversation(user_id=user_id, title=title, context=context)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_chat_conversations(db: Session, user_id: int):
    return list(db.scalars(select(ChatConversation).options(selectinload(ChatConversation.messages)).where(ChatConversation.user_id == user_id).order_by(ChatConversation.updated_at.desc())).all())


def get_chat_conversation(db: Session, conversation_id: int, user_id: int, privileged=False):
    conversation = db.scalar(
        select(ChatConversation).options(selectinload(ChatConversation.messages)).where(ChatConversation.id == conversation_id)
    )
    if conversation is None:
        raise HTTPException(404, "Chat conversation not found")
    if not privileged and conversation.user_id != user_id:
        raise HTTPException(403, "Insufficient permissions")
    return conversation


def send_chat_message(db: Session, conversation: ChatConversation, content: str, context=None):
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=content, context=context))
    lowered = content.lower()
    if any(word in lowered for word in ("pedido", "orden", "compra")):
        answer = "Puedo ayudarte a revisar tus pedidos. Consulta el estado desde tu historial de compras."
    elif any(word in lowered for word in ("talla", "tamaño", "size")):
        answer = "Para elegir talla, revisa la guía de tallas del producto o usa la recomendación personalizada."
    elif any(word in lowered for word in ("promo", "descuento", "oferta")):
        answer = "Consulta las promociones activas para conocer descuentos disponibles."
    elif any(word in lowered for word in ("hola", "buenas")):
        answer = "¡Hola! Puedo ayudarte con productos, tallas, pedidos y promociones."
    else:
        answer = "Puedo ayudarte con productos, recomendaciones, tallas, pedidos y promociones. ¿Qué necesitas?"
    assistant_message = ChatMessage(conversation_id=conversation.id, role="assistant", content=answer, context=context)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message

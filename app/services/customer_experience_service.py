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
from app.models.product import Category, Product, ProductVariant, Season, Size
from app.providers import get_ai_provider
from app.schemas.customer_experience import (
    UserPreferenceUpsert,
    VirtualFittingResultCreate,
    VirtualFittingSessionCreate,
)
from app.services.chat_context_service import build_chat_context, deterministic_reply, render_prompt


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


# ── CU18: pesos del recomendador ───────────────────────────────────────────
# El documento define CU18 como sugerencias basadas en el historial del cliente,
# la temporada y la disponibilidad; RF25 añade las preferencias del cliente.
# Total máximo = 100 puntos.
CU18_WEIGHT_CATEGORY = Decimal("25")      # categoría favorita
CU18_WEIGHT_BRAND = Decimal("20")         # marca favorita
CU18_WEIGHT_HISTORY = Decimal("20")       # historial de compras
CU18_WEIGHT_SIZE = Decimal("10")          # talla preferida con stock
CU18_WEIGHT_COLOR = Decimal("10")         # color preferido con stock
CU18_WEIGHT_SEASON = Decimal("5")         # temporada activa
CU18_WEIGHT_AVAILABILITY = Decimal("10")  # disponibilidad en tienda
CU18_MAX_SCORE = Decimal("100")

# Motivos que se exponen en `detalle_recomendacion.motivo` y clasifican el `tipo`.
STYLE_REASONS = ("categoría preferida", "marca preferida", "talla preferida", "color preferido")
HISTORY_REASON = "historial de compras"
SEASONAL_REASON = "temporada"


def _active_season_ids(db: Session) -> set[int]:
    """Temporada comercial vigente hoy (fecha_inicio <= hoy <= fecha_fin)."""
    today = datetime.now(timezone.utc).date()
    return {
        season_id
        for season_id, start_date, end_date in db.execute(
            select(Season.id, Season.start_date, Season.end_date)
        ).all()
        if start_date is not None and end_date is not None and start_date <= today <= end_date
    }


def _preferred_size_ids(preference: UserPreference | None) -> set[int]:
    """`tallas_preferidas` guarda IDs de `tallas.id` (JSON de enteros)."""
    if preference is None or not preference.preferred_sizes:
        return set()
    ids: set[int] = set()
    for value in preference.preferred_sizes:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def _preferred_color_names(preference: UserPreference | None) -> set[str]:
    """`colores_preferidos` guarda nombres de color en texto libre."""
    if preference is None or not preference.preferred_colors:
        return set()
    return {str(value).strip().casefold() for value in preference.preferred_colors if str(value).strip()}


def _variant_available(variant: ProductVariant) -> int:
    return sum(stock.available_stock for stock in variant.stocks)


def _recommendation_type(reasons: list[str]) -> str:
    """`recomendacion.tipo`: categoría o tipo de recomendación estilística (documento)."""
    if any(reason in reasons for reason in STYLE_REASONS):
        return "estilo"
    if HISTORY_REASON in reasons:
        return "historial"
    if SEASONAL_REASON in reasons:
        return "temporada"
    return "disponibilidad"


def _preference_payload(preference: UserPreference | None) -> dict | None:
    if preference is None:
        return None
    return {
        "category_id": preference.category_id,
        "preferred_brand": preference.preferred_brand,
        "preferred_colors": preference.preferred_colors,
        "preferred_sizes": preference.preferred_sizes,
        "min_price": str(preference.min_price) if preference.min_price is not None else None,
        "max_price": str(preference.max_price) if preference.max_price is not None else None,
    }


def generate_recommendations(db: Session, user_id: int, limit: int = 10) -> Recommendation:
    preference = get_preferences(db, user_id)
    active_seasons = _active_season_ids(db)
    preferred_sizes = _preferred_size_ids(preference)
    preferred_colors = _preferred_color_names(preference)
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
            .options(
                selectinload(Product.variants).selectinload(ProductVariant.stocks),
                selectinload(Product.variants).selectinload(ProductVariant.color),
            )
            .where(Product.is_active.is_(True))
            .order_by(Product.id)
        ).all()
    )
    # (producto, puntaje, motivo, tipo de recomendación, stock disponible)
    scored: list[tuple[Product, Decimal, str, str, int]] = []
    for product in products:
        available = sum(_variant_available(variant) for variant in product.variants)
        if available <= 0:
            continue  # agotado: el documento condiciona la sugerencia a la disponibilidad
        if preference:
            if preference.min_price is not None and product.price < preference.min_price:
                continue
            if preference.max_price is not None and product.price > preference.max_price:
                continue
        score = Decimal("0")
        reasons: list[str] = []
        if preference and preference.category_id == product.category_id:
            score += CU18_WEIGHT_CATEGORY
            reasons.append("categoría preferida")
        brand = (preference.preferred_brand or "").strip().casefold() if preference else ""
        if brand and brand == (product.brand or "").strip().casefold():
            score += CU18_WEIGHT_BRAND
            reasons.append("marca preferida")
        purchased = purchased_categories.get(product.category_id)
        if purchased:
            score += min(CU18_WEIGHT_HISTORY, Decimal(purchased))
            reasons.append(HISTORY_REASON)
        in_stock = [variant for variant in product.variants if _variant_available(variant) > 0]
        if preferred_sizes and any(
            (variant.size_id in preferred_sizes)
            or any(stock.size_id in preferred_sizes for stock in variant.stocks if stock.available_stock > 0)
            for variant in in_stock
        ):
            score += CU18_WEIGHT_SIZE
            reasons.append("talla preferida")
        if preferred_colors and any(
            variant.color is not None and (variant.color.name or "").strip().casefold() in preferred_colors
            for variant in in_stock
        ):
            score += CU18_WEIGHT_COLOR
            reasons.append("color preferido")
        if product.season_id is not None and product.season_id in active_seasons:
            score += CU18_WEIGHT_SEASON
            reasons.append(SEASONAL_REASON)
        score += min(CU18_WEIGHT_AVAILABILITY, Decimal(available))
        score = min(CU18_MAX_SCORE, score)
        scored.append(
            (product, score, ", ".join(reasons) or "disponibilidad", _recommendation_type(reasons), available)
        )
    scored.sort(key=lambda item: (-item[1], item[0].id))
    provider = get_ai_provider()
    if provider.__class__.__name__ != "DisabledAIProvider":
        prompt = (
            "You are FashionStore's recommendation engine. Rank products for a customer. "
            "Return JSON {\"products\":[{\"id\":number,\"reason\":\"short reason\"}]}. "
            f"Customer preferences: {_preference_payload(preference)}. "
            f"Products: {[{'id': p.id, 'name': p.name, 'price': str(p.price), 'category_id': p.category_id} for p, _, _, _, _ in scored]}"
        )
        ranked = provider.generate_json(prompt).get("products", [])
        by_id = {product.id: (product, score, reason, kind, available) for product, score, reason, kind, available in scored}
        ai_scored = []
        for item in ranked:
            if isinstance(item, dict) and item.get("id") in by_id:
                product, score, default_reason, kind, available = by_id[item["id"]]
                ai_scored.append((product, score, str(item.get("reason") or default_reason), kind, available))
        if ai_scored:
            scored = ai_scored + [item for item in scored if item[0].id not in {x[0].id for x in ai_scored}]
    top = scored[:limit]
    # El documento describe `tipo` como la categoría o tipo de recomendación estilística.
    recommendation_type = top[0][3] if top else "disponibilidad"
    # El documento define el estado del aviso como Pendiente al generarse.
    recommendation = Recommendation(
        user_id=user_id, recommendation_type=recommendation_type, status="pendiente"
    )
    recommendation.items = [
        RecommendationItem(product_id=product.id, score=score, reason=reason)
        for product, score, reason, _, _ in top
    ]
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    result = db.scalar(
        select(Recommendation)
        .options(selectinload(Recommendation.items).selectinload(RecommendationItem.product))
        .where(Recommendation.id == recommendation.id)
    )
    # `available_stock` no es columna: es un atributo de instancia para la respuesta.
    availability_by_product = {product.id: available for product, _, _, _, available in top}
    for item in result.items:
        item.available_stock = availability_by_product.get(item.product_id)
    return result


def list_recommendations(db: Session, user_id: int, limit: int = 20) -> list[Recommendation]:
    """CU18: historial de bloques de recomendación con su estado y su detalle."""
    return list(
        db.scalars(
            select(Recommendation)
            .options(selectinload(Recommendation.items).selectinload(RecommendationItem.product))
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
            .limit(limit)
        ).all()
    )


def update_recommendation_status(
    db: Session, recommendation_id: int, user_id: int, status: str, privileged: bool = False
) -> Recommendation:
    """CU18: marca un bloque de recomendación como visto o descartado (documento)."""
    recommendation = db.scalar(
        select(Recommendation)
        .options(selectinload(Recommendation.items).selectinload(RecommendationItem.product))
        .where(Recommendation.id == recommendation_id)
    )
    if recommendation is None:
        raise HTTPException(404, "Recommendation not found")
    if not privileged and recommendation.user_id != user_id:
        raise HTTPException(403, "Insufficient permissions")
    recommendation.status = status
    db.commit()
    db.refresh(recommendation)
    return recommendation


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


def send_chat_message(db: Session, conversation: ChatConversation, content: str, context=None, user=None):
    """CU19: el asistente responde con los datos reales del cliente (RF25).

    El contexto se arma antes de guardar el mensaje para que el historial que viaja al modelo sea
    la conversación previa, sin el mensaje que se está respondiendo.
    """
    chat_context = build_chat_context(db, conversation, user, context)
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=content, context=context))
    provider = get_ai_provider()
    if provider.__class__.__name__ != "DisabledAIProvider":
        answer = provider.generate_text(render_prompt(content, chat_context))
    else:
        answer = deterministic_reply(content, chat_context)
    assistant_message = ChatMessage(
        conversation_id=conversation.id, role="assistant", content=answer, context=context
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message

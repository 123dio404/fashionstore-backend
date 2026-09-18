import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.commerce import Sale, SaleItem
from app.models.inventory import Stock
from app.models.product import Product, ProductVariant
from app.providers import get_ai_provider


def _date_range(start_date, end_date):
    end = end_date or datetime.now(timezone.utc)
    start = start_date or end - timedelta(days=30)
    if start > end:
        raise HTTPException(422, "start_date must not be after end_date")
    return start, end


def purchase_history(db: Session, client_id: int, start_date=None, end_date=None):
    query = (
        select(Sale)
        .options(selectinload(Sale.items).selectinload(SaleItem.stock).selectinload(Stock.variant).selectinload(ProductVariant.product))
        .where(Sale.client_id == client_id)
        .order_by(Sale.sale_date.desc())
    )
    if start_date is not None:
        query = query.where(Sale.sale_date >= start_date)
    if end_date is not None:
        query = query.where(Sale.sale_date <= end_date)
    sales = db.scalars(query).all()
    purchases = []
    for sale in sales:
        items = []
        for item in sale.items:
            product = item.stock.variant.product
            items.append({
                "product_id": product.id,
                "product_name": product.name,
                "variant_id": item.stock.variant_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.unit_price * item.quantity,
            })
        purchases.append({
            "sale_id": sale.id,
            "sale_date": sale.sale_date,
            "branch_id": sale.branch_id,
            "sale_type": sale.sale_type,
            "total": sale.total,
            "items": items,
        })
    return {
        "client_id": client_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_orders": len(sales),
        "total_spent": sum((sale.total for sale in sales), Decimal("0")),
        "purchases": purchases,
    }


def sales_report(db: Session, start_date=None, end_date=None):
    start, end = _date_range(start_date, end_date)
    sales = db.scalars(
        select(Sale).options(selectinload(Sale.items)).where(Sale.sale_date.between(start, end))
    ).all()
    groups = {name: defaultdict(lambda: {"orders": 0, "units": 0, "revenue": Decimal("0")})
              for name in ("channel", "branch", "day")}
    for sale in sales:
        units = sum(item.quantity for item in sale.items)
        for group, key in (
            (groups["channel"], sale.sale_type),
            (groups["branch"], str(sale.branch_id)),
            (groups["day"], sale.sale_date.date().isoformat()),
        ):
            group[key]["orders"] += 1
            group[key]["units"] += units
            group[key]["revenue"] += sale.total
    total = sum((sale.total for sale in sales), Decimal("0"))
    rows = lambda group: [{"key": key, **value} for key, value in sorted(group.items())]
    return {
        "start_date": start, "end_date": end, "total_orders": len(sales),
        "total_units": sum(sum(item.quantity for item in sale.items) for sale in sales),
        "total_revenue": total,
        "average_order_value": total / len(sales) if sales else Decimal("0"),
        "by_channel": rows(groups["channel"]), "by_branch": rows(groups["branch"]), "by_day": rows(groups["day"]),
    }


def inventory_report(db: Session):
    stocks = db.scalars(
        select(Stock).options(selectinload(Stock.variant).selectinload(ProductVariant.product)).order_by(Stock.id)
    ).all()
    rows = []
    for stock in stocks:
        product = stock.variant.product
        rows.append({
            "stock_id": stock.id, "branch_id": stock.branch_id, "product_id": product.id,
            "product_name": product.name, "variant_id": stock.variant_id,
            "physical_stock": stock.physical_stock, "reserved_stock": stock.reserved_stock,
            "available_stock": stock.available_stock, "min_stock": stock.min_stock,
            "below_minimum": stock.available_stock <= stock.min_stock,
        })
    return {
        "generated_at": datetime.now(timezone.utc),
        "total_skus": len(rows),
        "total_physical_units": sum(row["physical_stock"] for row in rows),
        "total_available_units": sum(row["available_stock"] for row in rows),
        "low_stock_count": sum(row["below_minimum"] for row in rows),
        "stock": rows,
    }


def dashboard(db: Session, start_date=None, end_date=None):
    sales = sales_report(db, start_date, end_date)
    inventory = inventory_report(db)
    top = defaultdict(lambda: {"product_id": 0, "product_name": "", "units": 0, "revenue": Decimal("0")})
    result = db.execute(
        select(Product.id, Product.name, SaleItem.quantity, SaleItem.unit_price)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(Stock, Stock.variant_id == ProductVariant.id)
        .join(SaleItem, SaleItem.stock_id == Stock.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.sale_date.between(sales["start_date"], sales["end_date"]))
    )
    for product_id, name, quantity, unit_price in result:
        row = top[product_id]
        row.update(product_id=product_id, product_name=name)
        row["units"] += quantity
        row["revenue"] += quantity * unit_price
    prices = {product.id: product.price for product in db.scalars(select(Product)).all()}
    return {
        **{key: sales[key] for key in ("start_date", "end_date", "total_orders", "total_units", "total_revenue", "average_order_value")},
        "low_stock_count": inventory["low_stock_count"],
        "inventory_value": sum((row["physical_stock"] * prices.get(row["product_id"], Decimal("0")) for row in inventory["stock"]), Decimal("0")),
        "top_products": sorted(top.values(), key=lambda row: (-row["units"], row["product_id"]))[:10],
        "channels": sales["by_channel"],
    }


def analytical_query(db: Session, query: str, client_id=None, start_date=None, end_date=None, audio=None):
    normalized = query.casefold()
    parameters = {"client_id": client_id, "start_date": start_date, "end_date": end_date}
    if audio is not None:
        parameters["audio"] = audio
    provider = get_ai_provider()
    if provider.__class__.__name__ != "DisabledAIProvider":
        interpretation = provider.generate_json(
            "Classify this FashionStore analytical query. Return JSON with intent equal to "
            "one of inventory, purchase_history, dashboard, sales, and optional client_id. "
            f"Query: {query}"
        )
        intent_hint = interpretation.get("intent", "sales")
        if intent_hint == "purchase_history" and client_id is None:
            client_id = interpretation.get("client_id")
        normalized = intent_hint
    if normalized in {"inventory", "purchase_history", "dashboard", "sales"}:
        intent = normalized
        if intent == "inventory":
            result = inventory_report(db)
        elif intent == "purchase_history":
            if client_id is None:
                raise HTTPException(422, "client_id is required for purchase history queries")
            result = purchase_history(db, client_id, start_date, end_date)
        elif intent == "dashboard":
            result = dashboard(db, start_date, end_date)
        else:
            result = sales_report(db, start_date, end_date)
    elif re.search(r"\b(inventario|stock|existencias|inventory)\b", normalized):
        intent, result = "inventory", inventory_report(db)
    elif re.search(r"\b(historial|compras|compr[ée])\b", normalized):
        if client_id is None:
            raise HTTPException(422, "client_id is required for purchase history queries")
        intent, result = "purchase_history", purchase_history(db, client_id, start_date, end_date)
    elif re.search(r"\b(dashboard|ejecutiv|resumen)\b", normalized):
        intent, result = "dashboard", dashboard(db, start_date, end_date)
    else:
        intent, result = "sales", sales_report(db, start_date, end_date)
    return {"query": query, "intent": intent, "parameters": parameters, "result": result}

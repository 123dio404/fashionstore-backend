"""Script de siembra inicial para FashionStore SaaS Multitenant.

Crea los 3 planes de suscripción (Básico, Profesional y Empresarial)
y las 9 empresas independientes (3 por plan) exigidas por el Segundo Parcial:
  Plan Básico ($29.99/mes, max 2 sucursales, sin IA):
    1. Moda Urbana S.A. (slug: urban-style) - Streetwear y moda casual
    2. Tenis Urbanos S.R.L. (slug: tenis-urbanos) - Sneakers y calzado urbano
    3. SportActive Ropa Deportiva (slug: sport-active) - Ropa fitness y entrenamiento

  Plan Profesional ($69.99/mes, max 5 sucursales, con IA):
    4. Mundo Medias S.R.L. (slug: mundo-medias) - Tienda especializada en medias
    5. Denim Co. Jeans Factory (slug: denim-co) - Jeans y ropa de mezclilla
    6. Relax Homewear & Pijamas (slug: relax-homewear) - Ropa de descanso y confort

  Plan Empresarial ($129.99/mes, max 15 sucursales, con IA):
    7. Elegance Boutique S.R.L. (slug: elegance-fashion) - Alta costura y vestidos de gala
    8. Sartoria Milán Bespoke (slug: sartoria-milan) - Sastrería fina y trajes a medida
    9. Nordic Winter & Coats (slug: nordic-winter) - Abrigos de lujo y prendas de invierno

Incluye usuarios Superadmin, Administradores, Cajeros y Clientes para cada empresa,
todas con la contraseña estándar: Admin123.
Aislamiento multitenant 100% verificado, precios en Bolivianos (Bs.) y siembra de ventas previas.
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
from sqlalchemy import func, select, text

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.tenant import Tenant, Plan, Subscription
from app.models.user import User, Rol, Role
from app.models.branch import Branch, City
from app.models.product import Product, Category, Color, Size, ProductVariant
from app.models.inventory import Stock
from app.models.commerce import Sale, SaleItem, SalePayment
from app.services.auth_service import normalize_email

DEMO_PASSWORD = "Admin123"


def ensure_role(db, role_name: str) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.nombre == role_name))
    if not rol:
        rol = Rol(nombre=role_name)
        db.add(rol)
        db.flush()
    return rol


def ensure_user(db, email: str, full_name: str, role_name: str, tenant_id: int | None = None) -> User:
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    rol = ensure_role(db, role_name)

    if not user:
        user = User(
            email=normalized,
            full_name=full_name,
            password_hash=get_password_hash(DEMO_PASSWORD),
            tenant_id=tenant_id,
            is_active=True,
        )
        user.roles = [rol]
        db.add(user)
    else:
        user.full_name = full_name
        user.password_hash = get_password_hash(DEMO_PASSWORD)
        user.tenant_id = tenant_id
        user.is_active = True
        if rol not in user.roles:
            user.roles.append(rol)
    db.flush()
    return user


def ensure_city(db, name: str) -> City:
    c = db.scalar(select(City).where(City.name == name))
    if not c:
        c = City(name=name)
        db.add(c)
        db.flush()
    return c


def ensure_category(db, name: str, tenant_id: int | None = None) -> Category:
    cat = db.scalar(select(Category).where(Category.name == name, Category.tenant_id == tenant_id))
    if not cat:
        cat = db.scalar(select(Category).where(Category.name == name, Category.tenant_id.is_(None)))
        if cat:
            cat.tenant_id = tenant_id
        else:
            cat = Category(name=name, tenant_id=tenant_id)
            db.add(cat)
        db.flush()
    return cat


def ensure_color(db, name: str) -> Color:
    col = db.scalar(select(Color).where(Color.name == name))
    if not col:
        col = Color(name=name)
        db.add(col)
        db.flush()
    return col


def ensure_size(db, name: str) -> Size:
    s = db.scalar(select(Size).where(Size.name == name))
    if not s:
        s = Size(name=name)
        db.add(s)
        db.flush()
    return s


def seed_past_sales_for_tenant(
    db,
    tenant_id: int,
    client: User,
    cashier: User,
    branch_stocks: list[tuple[Branch, list[Stock]]],
    min_sales: int = 4,
):
    current_count = db.scalar(select(func.count(Sale.id)).where(Sale.tenant_id == tenant_id)) or 0
    if current_count >= min_sales:
        return

    now_utc = datetime.now(timezone.utc)
    # Lista de ventas demo con items reales
    sales_config = [
        {"days_ago": 2, "type": "contado", "method": "efectivo", "items_qty": [(0, 1), (1, 2)]},
        {"days_ago": 8, "type": "contado", "method": "qr", "items_qty": [(0, 2)]},
        {"days_ago": 16, "type": "contado", "method": "tarjeta", "items_qty": [(1, 1), (2, 1)]},
        {"days_ago": 28, "type": "contado", "method": "efectivo", "items_qty": [(2, 2)]},
    ]

    for idx, cfg in enumerate(sales_config):
        if idx < current_count:
            continue
        # Seleccionar sucursal cíclicamente
        branch_idx = idx % len(branch_stocks)
        branch, available_stocks = branch_stocks[branch_idx]
        if not available_stocks:
            continue

        sale_date = now_utc - timedelta(days=cfg["days_ago"], hours=idx * 2)
        total = Decimal("0.00")
        sale_items_to_add = []

        for stock_offset, qty in cfg["items_qty"]:
            stk = available_stocks[stock_offset % len(available_stocks)]
            price = stk.variant.price or stk.variant.product.price
            total += price * Decimal(str(qty))
            sale_items_to_add.append((stk, qty, price))

        sale = Sale(
            tenant_id=tenant_id,
            client_id=client.id,
            user_id=cashier.id,
            branch_id=branch.id,
            sale_date=sale_date,
            total=total,
            sale_type=cfg["type"],
            sync_status="CONFIRMADO",
            delivery_status="ENTREGADO",
            delivered_at=sale_date + timedelta(hours=1),
        )
        db.add(sale)
        db.flush()

        for stk, qty, price in sale_items_to_add:
            db.add(SaleItem(sale_id=sale.id, stock_id=stk.id, quantity=qty, unit_price=price))

        ref = f"REF-{sale.id}-{cfg['method'].upper()}-{uuid.uuid4().hex[:6]}"
        db.add(SalePayment(sale_id=sale.id, amount=total, status="completado", paid_at=sale_date, reference=ref))
    db.flush()


PRODUCT_IMAGES = {
    # Moda Urbana S.A.
    "Remera Oversize Graphic Lab": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800&auto=format&fit=crop&q=80",
    "Rompevientos Windbreaker Techwear": "https://images.unsplash.com/photo-1544441893-675973e31985?w=800&auto=format&fit=crop&q=80",
    "Jogger Baggy Streetwear": "https://images.unsplash.com/photo-1552902865-b72c031ac5ea?w=800&auto=format&fit=crop&q=80",
    "Gorra Urbana Trucker Edition": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=800&auto=format&fit=crop&q=80",
    "Sneakers Clásicas Urbanas": "https://images.unsplash.com/photo-1605523741177-cd660595c2cf?w=800&auto=format&fit=crop&q=80",
    "Sneakers Blancas Chunky": "https://images.unsplash.com/photo-1552346154-21d32810aba3?w=800&auto=format&fit=crop&q=80",
    "Camisa Oxford Streetwear": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800&auto=format&fit=crop&q=80",
    "Chaqueta Denim Retro": "https://images.unsplash.com/photo-1603189343302-e603f7add05a?w=800&auto=format&fit=crop&q=80",
    "Pantalón Cargo Urbano": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=800&auto=format&fit=crop&q=80",
    "Hoodie Gráfico Streetwear": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&auto=format&fit=crop&q=80",

    # Tenis Urbanos S.R.L.
    "Tenis Running Boost Pro": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&auto=format&fit=crop&q=80",
    "Tenis Court Vintage Leather": "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=800&auto=format&fit=crop&q=80",
    "Tenis Skate Canvas Low": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=800&auto=format&fit=crop&q=80",
    "Tenis Plataforma Chunky Bold": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800&auto=format&fit=crop&q=80",
    "Tenis Trail All-Terrain Outdoor": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=800&auto=format&fit=crop&q=80",

    # SportActive Ropa Deportiva
    "Remera Técnica Dry-Fit Pro": "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=800&auto=format&fit=crop&q=80",
    "Leggings Seamless Alta Compresión": "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=800&auto=format&fit=crop&q=80",
    "Short Running 2 en 1 con Bolsillo": "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=800&auto=format&fit=crop&q=80",
    "Top Deportivo Alto Impacto": "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=800&auto=format&fit=crop&q=80",
    "Cortaviento Running Ultraligero": "https://images.unsplash.com/photo-1544441893-675973e31985?w=800&auto=format&fit=crop&q=80",

    # Mundo Medias S.R.L.
    "Medias Tobilleras Deportivas (Pack x3)": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=800&auto=format&fit=crop&q=80",
    "Medias de Compresión Graduada": "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=800&auto=format&fit=crop&q=80",
    "Medias Térmicas Polar de Invierno": "https://images.unsplash.com/photo-1646725582781-c09e1bcd431d?w=800&auto=format&fit=crop&q=80",
    "Medias Invisibles Antideslizantes": "https://images.unsplash.com/photo-1585499583264-491df5142e83?w=800&auto=format&fit=crop&q=80",
    "Pantis de Seda Fina Elegance": "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=800&auto=format&fit=crop&q=80",
    "Medias Ejecutivas Hilo de Escocia": "https://images.unsplash.com/photo-1608256246200-53e635b5b65f?w=800&auto=format&fit=crop&q=80",
    "Calcetines Lana Merino Senderismo": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=800&auto=format&fit=crop&q=80",
    "Medias Bucaneras Canalé Algodón": "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&auto=format&fit=crop&q=80",

    # Denim Co. Jeans Factory
    "Jeans Slim Fit Índigo Clásico": "https://images.unsplash.com/photo-1542272604-780c96856467?w=800&auto=format&fit=crop&q=80",
    "Jeans Mom Fit Vintage Celeste": "https://images.unsplash.com/photo-1582552938357-32b906df40cb?w=800&auto=format&fit=crop&q=80",
    "Cazadora Denim Forro Sherpa": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=800&auto=format&fit=crop&q=80",
    "Falda Midi Denim Abotonada": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=800&auto=format&fit=crop&q=80",
    "Overol Denim Carpenter Tradicional": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&auto=format&fit=crop&q=80",

    # Relax Homewear & Pijamas
    "Pijama Franela Cuadros Invierno": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800&auto=format&fit=crop&q=80",
    "Bata Kimono Satén Seda Royale": "https://images.unsplash.com/photo-1616091216791-a5360b5fc78a?w=800&auto=format&fit=crop&q=80",
    "Conjunto Soft Fleece Confort": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80",
    "Pantuflas Nordic Acolchadas": "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=800&auto=format&fit=crop&q=80",
    "Short Pijama Modal Transpirable": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=800&auto=format&fit=crop&q=80",

    # Elegance Boutique S.R.L.
    "Vestido de Gala Seda Royale": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=800&auto=format&fit=crop&q=80",
    "Traje Ejecutivo Italiano": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=800&auto=format&fit=crop&q=80",
    "Smoking Ceremonia Black Tie": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop&q=80",
    "Vestido Sirena Escote Corset": "https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=800&auto=format&fit=crop&q=80",
    "Abrigo de Cachemira Imperial": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=800&auto=format&fit=crop&q=80",
    "Blazer Doble Botonadura Sartorial": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=800&auto=format&fit=crop&q=80",
    "Vestido Midi Plisado Champagne": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=800&auto=format&fit=crop&q=80",
    "Blusa de Seda Crepe Organza": "https://images.unsplash.com/photo-1551803091-e20673f15770?w=800&auto=format&fit=crop&q=80",

    # Sartoria Milán Bespoke
    "Traje 3 Piezas Príncipe de Gales": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=800&auto=format&fit=crop&q=80",
    "Smoking Solapa Chal Velvet Black Tie": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop&q=80",
    "Blazer Doble Botonadura Navy Wool": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=800&auto=format&fit=crop&q=80",
    "Camisa Cuello Francés Hilo Doble 120s": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800&auto=format&fit=crop&q=80",
    "Pantalón Sartorial Pliegues Tiro Alto": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=800&auto=format&fit=crop&q=80",

    # Nordic Winter & Coats
    "Gabardina Trench Coat Impermeable": "https://images.unsplash.com/photo-1544441893-675973e31985?w=800&auto=format&fit=crop&q=80",
    "Parka Plumífero Expedition Térmica": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=800&auto=format&fit=crop&q=80",
    "Chaquetón Doble Faz Lana Merino": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80",
    "Abrigo Imperial Cachemira Italiana": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=800&auto=format&fit=crop&q=80",
    "Bufanda Alpaca Suri Tejida a Mano": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=800&auto=format&fit=crop&q=80",
}


def seed_saas_data():
    db = SessionLocal()
    try:
        print("1. Verificando roles del sistema...")
        ensure_role(db, "Superadmin")
        ensure_role(db, "Administrador")
        ensure_role(db, "Encargado")
        ensure_role(db, "Cajero")
        ensure_role(db, "Cliente")
        ensure_role(db, "Proveedor")

        print("2. Creando/actualizando los 3 planes de suscripción SaaS...")
        # Plan 1: Básico
        plan_basico = db.scalar(select(Plan).where(Plan.name == "Básico"))
        if not plan_basico:
            plan_basico = Plan(name="Básico", max_branches=2, has_ai_reports=False, monthly_price=Decimal("29.99"), is_active=True)
            db.add(plan_basico)
        else:
            plan_basico.max_branches = 2
            plan_basico.has_ai_reports = False
            plan_basico.monthly_price = Decimal("29.99")
            plan_basico.is_active = True

        # Plan 2: Profesional
        plan_pro = db.scalar(select(Plan).where(Plan.name == "Profesional"))
        if not plan_pro:
            plan_pro = Plan(name="Profesional", max_branches=5, has_ai_reports=True, monthly_price=Decimal("69.99"), is_active=True)
            db.add(plan_pro)
        else:
            plan_pro.max_branches = 5
            plan_pro.has_ai_reports = True
            plan_pro.monthly_price = Decimal("69.99")
            plan_pro.is_active = True

        # Plan 3: Empresarial
        plan_emp = db.scalar(select(Plan).where(Plan.name == "Empresarial"))
        if not plan_emp:
            plan_emp = Plan(name="Empresarial", max_branches=15, has_ai_reports=True, monthly_price=Decimal("129.99"), is_active=True)
            db.add(plan_emp)
        else:
            plan_emp.max_branches = 15
            plan_emp.has_ai_reports = True
            plan_emp.monthly_price = Decimal("129.99")
            plan_emp.is_active = True
        db.flush()

        print("3. Creando Superadministrador global SaaS...")
        ensure_user(db, "superadmin@fashionstore.com", "Superadministrador SaaS", "Superadmin", tenant_id=None)

        city_scz = ensure_city(db, "Santa Cruz de la Sierra")
        city_lpz = ensure_city(db, "La Paz")
        city_cbb = ensure_city(db, "Cochabamba")

        # Colores
        col_blanco = ensure_color(db, "Blanco")
        col_negro = ensure_color(db, "Negro")
        col_gris = ensure_color(db, "Gris")
        col_azul = ensure_color(db, "Azul")
        col_rojo = ensure_color(db, "Rojo")
        col_camel = ensure_color(db, "Camel")
        col_dorado = ensure_color(db, "Dorado")
        col_piel = ensure_color(db, "Piel")
        col_verde = ensure_color(db, "Verde")
        col_beige = ensure_color(db, "Beige")

        # Tallas
        size_s = ensure_size(db, "S")
        size_m = ensure_size(db, "M")
        size_l = ensure_size(db, "L")
        size_xl = ensure_size(db, "XL")
        size_39 = ensure_size(db, "39")
        size_40 = ensure_size(db, "40")
        size_41 = ensure_size(db, "41")
        size_42 = ensure_size(db, "42")

        now_utc = datetime.now(timezone.utc)

        def sync_subscription(tenant_id: int, plan: Plan):
            sub = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant_id))
            if not sub:
                sub = Subscription(
                    tenant_id=tenant_id,
                    plan_id=plan.id,
                    start_date=now_utc - timedelta(days=60),
                    end_date=now_utc + timedelta(days=305),
                    status="Activa",
                )
                db.add(sub)
            else:
                sub.plan_id = plan.id
                sub.status = "Activa"
            db.flush()

        # =========================================================================
        # GRUPO 1: PLAN BÁSICO ($29.99/mes, max 2 sucursales, sin IA)
        # =========================================================================

        # -------------------------------------------------------------------------
        # TENANT 1: Moda Urbana S.A.
        # -------------------------------------------------------------------------
        print("4. Configurando Tenant 1: Moda Urbana S.A. (Plan Básico)...")
        t1 = db.scalar(select(Tenant).where(Tenant.slug == "urban-style"))
        if not t1:
            t1 = Tenant(name="Moda Urbana S.A.", slug="urban-style", tax_id="1020304050", status="Activo")
            db.add(t1)
            db.flush()
        sync_subscription(t1.id, plan_basico)

        u_admin_t1 = ensure_user(db, "admin@urbanstyle.com", "Admin Moda Urbana", "Administrador", tenant_id=t1.id)
        u_cajero_t1 = ensure_user(db, "cajero@urbanstyle.com", "Cajero Sucursal Centro", "Cajero", tenant_id=t1.id)
        u_cliente_t1 = ensure_user(db, "cliente@urbanstyle.com", "Cliente Moda Urbana", "Cliente", tenant_id=t1.id)

        b1_1 = db.get(Branch, 1)
        if b1_1:
            b1_1.tenant_id = t1.id
        else:
            b1_1 = Branch(tenant_id=t1.id, city_id=city_scz.id, name="Sucursal Centro", address="Calle 21 de Mayo #142", phone="70011223", is_active=True)
            db.add(b1_1)
        b1_2 = db.get(Branch, 6)
        if b1_2:
            b1_2.tenant_id = t1.id
        else:
            b1_2 = Branch(tenant_id=t1.id, city_id=city_scz.id, name="Sucursal Norte", address="Av. Banzer 4to Anillo", phone="70011224", is_active=True)
            db.add(b1_2)
        db.flush()

        cat_t1_urb = ensure_category(db, "Moda Urbana & Streetwear", t1.id)
        cat_t1_acc = ensure_category(db, "Accesorios Urbanos", t1.id)
        cat_t1_calz = ensure_category(db, "Calzado Urbano", t1.id)
        cat_t1_ropa = ensure_category(db, "Ropa Casual", t1.id)

        t1_products = [
            {"name": "Remera Oversize Graphic Lab", "brand": "StreetWear Lab", "cat": cat_t1_urb, "price": Decimal("95.00"), "ws_price": Decimal("75.00"), "code": "URB-REM-BLK-L", "col": col_negro, "sz": size_l, "s1": 25, "s2": 15},
            {"name": "Rompevientos Windbreaker Techwear", "brand": "Metro Denim", "cat": cat_t1_urb, "price": Decimal("210.00"), "ws_price": Decimal("175.00"), "code": "URB-WIND-GRY-M", "col": col_gris, "sz": size_m, "s1": 18, "s2": 12},
            {"name": "Jogger Baggy Streetwear", "brand": "StreetWear Lab", "cat": cat_t1_urb, "price": Decimal("165.00"), "ws_price": Decimal("135.00"), "code": "URB-JOG-BLK-M", "col": col_negro, "sz": size_m, "s1": 20, "s2": 14},
            {"name": "Gorra Urbana Trucker Edition", "brand": "Urban Style Co.", "cat": cat_t1_acc, "price": Decimal("65.00"), "ws_price": Decimal("50.00"), "code": "URB-CAP-BLK-U", "col": col_negro, "sz": size_m, "s1": 30, "s2": 20},
            {"name": "Sneakers Clásicas Urbanas", "brand": "Urban Kicks", "cat": cat_t1_calz, "price": Decimal("280.00"), "ws_price": Decimal("235.00"), "code": "URB-SNK-WHT-41", "col": col_blanco, "sz": size_41, "s1": 14, "s2": 10},
        ]
        t1_stocks_b1 = []
        t1_stocks_b2 = []
        for pdata in t1_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t1.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t1.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b1_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b1_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=5)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b1_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b1_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=3)
                db.add(st2)
                db.flush()
            t1_stocks_b1.append(st1)
            t1_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t1.id, u_cliente_t1, u_cajero_t1, [(b1_1, t1_stocks_b1), (b1_2, t1_stocks_b2)], min_sales=4)

        # -------------------------------------------------------------------------
        # TENANT 2: Tenis Urbanos S.R.L.
        # -------------------------------------------------------------------------
        print("5. Configurando Tenant 2: Tenis Urbanos S.R.L. (Plan Básico)...")
        t2 = db.scalar(select(Tenant).where(Tenant.slug == "tenis-urbanos"))
        if not t2:
            t2 = Tenant(name="Tenis Urbanos S.R.L.", slug="tenis-urbanos", tax_id="1020304051", status="Activo")
            db.add(t2)
            db.flush()
        sync_subscription(t2.id, plan_basico)

        u_admin_t2 = ensure_user(db, "admin@tenisurbanos.com", "Admin Tenis Urbanos", "Administrador", tenant_id=t2.id)
        u_cajero_t2 = ensure_user(db, "cajero@tenisurbanos.com", "Cajero Sucursal Equipetrol", "Cajero", tenant_id=t2.id)
        u_cliente_t2 = ensure_user(db, "cliente@tenisurbanos.com", "Cliente Tenis Urbanos", "Cliente", tenant_id=t2.id)

        b2_1 = db.scalar(select(Branch).where(Branch.tenant_id == t2.id, Branch.name == "Sucursal Equipetrol"))
        if not b2_1:
            b2_1 = Branch(tenant_id=t2.id, city_id=city_scz.id, name="Sucursal Equipetrol", address="Av. San Martín esq. Calle 7", phone="71022331", is_active=True)
            db.add(b2_1)
        b2_2 = db.scalar(select(Branch).where(Branch.tenant_id == t2.id, Branch.name == "Sucursal San Martín"))
        if not b2_2:
            b2_2 = Branch(tenant_id=t2.id, city_id=city_scz.id, name="Sucursal San Martín", address="Centro Comercial El Chuubi Local 14", phone="71022332", is_active=True)
            db.add(b2_2)
        db.flush()

        cat_t2_run = ensure_category(db, "Tenis Running", t2.id)
        cat_t2_cas = ensure_category(db, "Tenis Casuales & Skate", t2.id)
        cat_t2_ret = ensure_category(db, "Tenis Retro & Vintage", t2.id)

        t2_products = [
            {"name": "Tenis Running Boost Pro", "brand": "KicksLab", "cat": cat_t2_run, "price": Decimal("380.00"), "ws_price": Decimal("320.00"), "code": "TEN-RUN-RED-42", "col": col_rojo, "sz": size_42, "s1": 20, "s2": 15},
            {"name": "Tenis Court Vintage Leather", "brand": "Urban Sole", "cat": cat_t2_ret, "price": Decimal("320.00"), "ws_price": Decimal("280.00"), "code": "TEN-VNT-WHT-41", "col": col_blanco, "sz": size_41, "s1": 18, "s2": 12},
            {"name": "Tenis Skate Canvas Low", "brand": "StreetKicks", "cat": cat_t2_cas, "price": Decimal("260.00"), "ws_price": Decimal("220.00"), "code": "TEN-SKT-BLK-40", "col": col_negro, "sz": size_40, "s1": 22, "s2": 14},
            {"name": "Tenis Plataforma Chunky Bold", "brand": "SoleStudio", "cat": cat_t2_cas, "price": Decimal("340.00"), "ws_price": Decimal("290.00"), "code": "TEN-CHK-WHT-39", "col": col_blanco, "sz": size_39, "s1": 15, "s2": 10},
            {"name": "Tenis Trail All-Terrain Outdoor", "brand": "Apex Footwear", "cat": cat_t2_run, "price": Decimal("420.00"), "ws_price": Decimal("360.00"), "code": "TEN-TRL-GRY-42", "col": col_gris, "sz": size_42, "s1": 16, "s2": 11},
        ]
        t2_stocks_b1 = []
        t2_stocks_b2 = []
        for pdata in t2_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t2.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t2.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b2_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b2_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=4)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b2_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b2_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=3)
                db.add(st2)
                db.flush()
            t2_stocks_b1.append(st1)
            t2_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t2.id, u_cliente_t2, u_cajero_t2, [(b2_1, t2_stocks_b1), (b2_2, t2_stocks_b2)], min_sales=4)

        # -------------------------------------------------------------------------
        # TENANT 3: SportActive Ropa Deportiva
        # -------------------------------------------------------------------------
        print("6. Configurando Tenant 3: SportActive Ropa Deportiva (Plan Básico)...")
        t3 = db.scalar(select(Tenant).where(Tenant.slug == "sport-active"))
        if not t3:
            t3 = Tenant(name="SportActive Ropa Deportiva", slug="sport-active", tax_id="1020304052", status="Activo")
            db.add(t3)
            db.flush()
        sync_subscription(t3.id, plan_basico)

        u_admin_t3 = ensure_user(db, "admin@sportactive.com", "Admin SportActive", "Administrador", tenant_id=t3.id)
        u_cajero_t3 = ensure_user(db, "cajero@sportactive.com", "Cajero Megacenter", "Cajero", tenant_id=t3.id)
        u_cliente_t3 = ensure_user(db, "cliente@sportactive.com", "Cliente SportActive", "Cliente", tenant_id=t3.id)

        b3_1 = db.scalar(select(Branch).where(Branch.tenant_id == t3.id, Branch.name == "Sucursal Megacenter"))
        if not b3_1:
            b3_1 = Branch(tenant_id=t3.id, city_id=city_scz.id, name="Sucursal Megacenter", address="Megacenter Santa Cruz Local 45", phone="71033441", is_active=True)
            db.add(b3_1)
        b3_2 = db.scalar(select(Branch).where(Branch.tenant_id == t3.id, Branch.name == "Sucursal Cañoto"))
        if not b3_2:
            b3_2 = Branch(tenant_id=t3.id, city_id=city_scz.id, name="Sucursal Cañoto", address="Av. Cañoto #620", phone="71033442", is_active=True)
            db.add(b3_2)
        db.flush()

        cat_t3_masc = ensure_category(db, "Ropa Fitness Masculina", t3.id)
        cat_t3_fem = ensure_category(db, "Ropa Fitness Femenina", t3.id)
        cat_t3_acc = ensure_category(db, "Accesorios Deportivos", t3.id)

        t3_products = [
            {"name": "Remera Técnica Dry-Fit Pro", "brand": "ActivePro", "cat": cat_t3_masc, "price": Decimal("95.00"), "ws_price": Decimal("75.00"), "code": "SPT-DRY-BLU-L", "col": col_azul, "sz": size_l, "s1": 25, "s2": 15},
            {"name": "Leggings Seamless Alta Compresión", "brand": "GymFlex", "cat": cat_t3_fem, "price": Decimal("145.00"), "ws_price": Decimal("120.00"), "code": "SPT-LEG-BLK-M", "col": col_negro, "sz": size_m, "s1": 30, "s2": 20},
            {"name": "Short Running 2 en 1 con Bolsillo", "brand": "SprintTech", "cat": cat_t3_masc, "price": Decimal("120.00"), "ws_price": Decimal("95.00"), "code": "SPT-SHT-GRY-M", "col": col_gris, "sz": size_m, "s1": 22, "s2": 16},
            {"name": "Top Deportivo Alto Impacto", "brand": "FitQueen", "cat": cat_t3_fem, "price": Decimal("110.00"), "ws_price": Decimal("85.00"), "code": "SPT-TOP-RED-S", "col": col_rojo, "sz": size_s, "s1": 20, "s2": 14},
            {"name": "Cortaviento Running Ultraligero", "brand": "AeroWind", "cat": cat_t3_masc, "price": Decimal("210.00"), "ws_price": Decimal("180.00"), "code": "SPT-WND-BLK-L", "col": col_negro, "sz": size_l, "s1": 15, "s2": 10},
        ]
        t3_stocks_b1 = []
        t3_stocks_b2 = []
        for pdata in t3_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t3.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t3.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b3_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b3_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=5)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b3_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b3_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=4)
                db.add(st2)
                db.flush()
            t3_stocks_b1.append(st1)
            t3_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t3.id, u_cliente_t3, u_cajero_t3, [(b3_1, t3_stocks_b1), (b3_2, t3_stocks_b2)], min_sales=4)

        # =========================================================================
        # GRUPO 2: PLAN PROFESIONAL ($69.99/mes, max 5 sucursales, con IA)
        # =========================================================================

        # -------------------------------------------------------------------------
        # TENANT 4: Mundo Medias S.R.L.
        # -------------------------------------------------------------------------
        print("7. Configurando Tenant 4: Mundo Medias S.R.L. (Plan Profesional)...")
        t4 = db.scalar(select(Tenant).where(Tenant.slug == "mundo-medias"))
        if not t4:
            t4 = Tenant(name="Mundo Medias S.R.L.", slug="mundo-medias", tax_id="3040506070", status="Activo")
            db.add(t4)
            db.flush()
        sync_subscription(t4.id, plan_pro)

        u_admin_t4 = ensure_user(db, "admin@mundomedias.com", "Admin Mundo Medias", "Administrador", tenant_id=t4.id)
        u_cajero_t4 = ensure_user(db, "cajero@mundomedias.com", "Cajero Sucursal Cañoto", "Cajero", tenant_id=t4.id)
        u_cliente_t4 = ensure_user(db, "cliente@mundomedias.com", "Cliente Mundo Medias", "Cliente", tenant_id=t4.id)

        b4_1 = db.scalar(select(Branch).where(Branch.tenant_id == t4.id, Branch.name == "Sucursal Cañoto"))
        if not b4_1:
            b4_1 = Branch(tenant_id=t4.id, city_id=city_scz.id, name="Sucursal Cañoto", address="Av. Cañoto esq. México #450", phone="70033441", is_active=True)
            db.add(b4_1)
        b4_2 = db.scalar(select(Branch).where(Branch.tenant_id == t4.id, Branch.name == "Sucursal Mutualista"))
        if not b4_2:
            b4_2 = Branch(tenant_id=t4.id, city_id=city_scz.id, name="Sucursal Mutualista", address="3er Anillo Externo y Av. Mutualista", phone="70033442", is_active=True)
            db.add(b4_2)
        b4_3 = db.scalar(select(Branch).where(Branch.tenant_id == t4.id, Branch.name == "Sucursal La Ramada"))
        if not b4_3:
            b4_3 = Branch(tenant_id=t4.id, city_id=city_scz.id, name="Sucursal La Ramada", address="Av. Grigotá #310", phone="70033443", is_active=True)
            db.add(b4_3)
        db.flush()

        cat_t4_dep = ensure_category(db, "Medias Deportivas", t4.id)
        cat_t4_cla = ensure_category(db, "Medias Clásicas y Ejecutivas", t4.id)
        cat_t4_ter = ensure_category(db, "Medias Térmicas y Especiales", t4.id)

        medias_catalog = [
            {"name": "Medias Tobilleras Deportivas (Pack x3)", "cat": cat_t4_dep, "brand": "Mundo Medias Sport", "price": Decimal("35.00"), "ws_price": Decimal("28.00"), "variants": [{"code": "MED-DEPO-WHT-M", "col": col_blanco, "sz": size_m}, {"code": "MED-DEPO-BLK-L", "col": col_negro, "sz": size_l}]},
            {"name": "Medias de Compresión Graduada", "cat": cat_t4_ter, "brand": "MediActive Care", "price": Decimal("85.00"), "ws_price": Decimal("70.00"), "variants": [{"code": "MED-COMP-BLK-M", "col": col_negro, "sz": size_m}, {"code": "MED-COMP-SKN-L", "col": col_piel, "sz": size_l}]},
            {"name": "Medias Térmicas Polar de Invierno", "cat": cat_t4_ter, "brand": "WinterWarm", "price": Decimal("45.00"), "ws_price": Decimal("38.00"), "variants": [{"code": "MED-POLR-GRY-M", "col": col_gris, "sz": size_m}, {"code": "MED-POLR-BLK-L", "col": col_negro, "sz": size_l}]},
            {"name": "Medias Invisibles Antideslizantes", "cat": cat_t4_dep, "brand": "Mundo Medias Casual", "price": Decimal("25.00"), "ws_price": Decimal("20.00"), "variants": [{"code": "MED-INVI-WHT-S", "col": col_blanco, "sz": size_s}, {"code": "MED-INVI-BLK-M", "col": col_negro, "sz": size_m}]},
            {"name": "Pantis de Seda Fina Elegance", "cat": cat_t4_cla, "brand": "SilkTouch", "price": Decimal("50.00"), "ws_price": Decimal("40.00"), "variants": [{"code": "MED-PANT-BLK-M", "col": col_negro, "sz": size_m}, {"code": "MED-PANT-SKN-M", "col": col_piel, "sz": size_m}]},
            {"name": "Medias Ejecutivas Hilo de Escocia", "cat": cat_t4_cla, "brand": "SilkTouch", "price": Decimal("40.00"), "ws_price": Decimal("32.00"), "variants": [{"code": "MED-EJEC-BLK-M", "col": col_negro, "sz": size_m}, {"code": "MED-EJEC-GRY-L", "col": col_gris, "sz": size_l}]},
            {"name": "Calcetines Lana Merino Senderismo", "cat": cat_t4_ter, "brand": "WinterWarm", "price": Decimal("55.00"), "ws_price": Decimal("45.00"), "variants": [{"code": "MED-MERI-GRY-M", "col": col_gris, "sz": size_m}, {"code": "MED-MERI-BLK-L", "col": col_negro, "sz": size_l}]},
            {"name": "Medias Bucaneras Canalé Algodón", "cat": cat_t4_dep, "brand": "Mundo Medias Casual", "price": Decimal("38.00"), "ws_price": Decimal("30.00"), "variants": [{"code": "MED-BUCA-BLK-M", "col": col_negro, "sz": size_m}, {"code": "MED-BUCA-WHT-S", "col": col_blanco, "sz": size_s}]},
        ]
        t4_stocks_b1 = []
        t4_stocks_b2 = []
        for pdata in medias_catalog:
            p = db.scalar(select(Product).where(Product.tenant_id == t4.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t4.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                # PRESERVAR SUBIDAS DEL USUARIO
                if not p.image_url or (not p.image_url.startswith("/uploads/") and not p.image_url.startswith("http")):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            for vd in pdata["variants"]:
                v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == vd["code"]))
                if not v:
                    v = ProductVariant(product_id=p.id, codigo=vd["code"], color_id=vd["col"].id, size_id=vd["sz"].id, price=pdata["price"], is_active=True)
                    db.add(v)
                    db.flush()

                st1 = db.scalar(select(Stock).where(Stock.branch_id == b4_1.id, Stock.variant_id == v.id))
                if not st1:
                    st1 = Stock(branch_id=b4_1.id, variant_id=v.id, size_id=vd["sz"].id, physical_stock=35, reserved_stock=0, min_stock=5)
                    db.add(st1)
                    db.flush()
                st2 = db.scalar(select(Stock).where(Stock.branch_id == b4_2.id, Stock.variant_id == v.id))
                if not st2:
                    st2 = Stock(branch_id=b4_2.id, variant_id=v.id, size_id=vd["sz"].id, physical_stock=25, reserved_stock=0, min_stock=5)
                    db.add(st2)
                    db.flush()
                t4_stocks_b1.append(st1)
                t4_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t4.id, u_cliente_t4, u_cajero_t4, [(b4_1, t4_stocks_b1), (b4_2, t4_stocks_b2)], min_sales=4)

        # -------------------------------------------------------------------------
        # TENANT 5: Denim Co. Jeans Factory
        # -------------------------------------------------------------------------
        print("8. Configurando Tenant 5: Denim Co. Jeans Factory (Plan Profesional)...")
        t5 = db.scalar(select(Tenant).where(Tenant.slug == "denim-co"))
        if not t5:
            t5 = Tenant(name="Denim Co. Jeans Factory", slug="denim-co", tax_id="3040506071", status="Activo")
            db.add(t5)
            db.flush()
        sync_subscription(t5.id, plan_pro)

        u_admin_t5 = ensure_user(db, "admin@denimco.com", "Admin Denim Co.", "Administrador", tenant_id=t5.id)
        u_cajero_t5 = ensure_user(db, "cajero@denimco.com", "Cajero Sucursal El Trompillo", "Cajero", tenant_id=t5.id)
        u_cliente_t5 = ensure_user(db, "cliente@denimco.com", "Cliente Denim Co.", "Cliente", tenant_id=t5.id)

        b5_1 = db.scalar(select(Branch).where(Branch.tenant_id == t5.id, Branch.name == "Sucursal El Trompillo"))
        if not b5_1:
            b5_1 = Branch(tenant_id=t5.id, city_id=city_scz.id, name="Sucursal El Trompillo", address="Av. El Trompillo #820", phone="72044551", is_active=True)
            db.add(b5_1)
        b5_2 = db.scalar(select(Branch).where(Branch.tenant_id == t5.id, Branch.name == "Sucursal Prado La Paz"))
        if not b5_2:
            b5_2 = Branch(tenant_id=t5.id, city_id=city_lpz.id, name="Sucursal Prado La Paz", address="Av. 16 de Julio #1440 (El Prado)", phone="72044552", is_active=True)
            db.add(b5_2)
        b5_3 = db.scalar(select(Branch).where(Branch.tenant_id == t5.id, Branch.name == "Sucursal América"))
        if not b5_3:
            b5_3 = Branch(tenant_id=t5.id, city_id=city_cbb.id, name="Sucursal América", address="Av. América y Pando #510", phone="72044553", is_active=True)
            db.add(b5_3)
        db.flush()

        cat_t5_slim = ensure_category(db, "Jeans Slim & Regular", t5.id)
        cat_t5_mom = ensure_category(db, "Jeans Mom & Flare", t5.id)
        cat_t5_caz = ensure_category(db, "Chaquetas & Cazadoras Denim", t5.id)
        cat_t5_otr = ensure_category(db, "Prendas Mezclilla & Overoles", t5.id)

        t5_products = [
            {"name": "Jeans Slim Fit Índigo Clásico", "brand": "Denim Co. Heritage", "cat": cat_t5_slim, "price": Decimal("220.00"), "ws_price": Decimal("180.00"), "code": "DNM-SLM-BLU-32", "col": col_azul, "sz": size_m, "s1": 25, "s2": 15},
            {"name": "Jeans Mom Fit Vintage Celeste", "brand": "BlueWave", "cat": cat_t5_mom, "price": Decimal("240.00"), "ws_price": Decimal("195.00"), "code": "DNM-MOM-BLU-28", "col": col_azul, "sz": size_s, "s1": 22, "s2": 18},
            {"name": "Cazadora Denim Forro Sherpa", "brand": "Denim Co. Outerwear", "cat": cat_t5_caz, "price": Decimal("320.00"), "ws_price": Decimal("270.00"), "code": "DNM-SHR-BLU-L", "col": col_azul, "sz": size_l, "s1": 18, "s2": 12},
            {"name": "Falda Midi Denim Abotonada", "brand": "Urban Denim", "cat": cat_t5_otr, "price": Decimal("180.00"), "ws_price": Decimal("145.00"), "code": "DNM-SKT-BLU-M", "col": col_azul, "sz": size_m, "s1": 15, "s2": 10},
            {"name": "Overol Denim Carpenter Tradicional", "brand": "Denim Works", "cat": cat_t5_otr, "price": Decimal("290.00"), "ws_price": Decimal("240.00"), "code": "DNM-OVR-BLU-L", "col": col_azul, "sz": size_l, "s1": 14, "s2": 10},
        ]
        t5_stocks_b1 = []
        t5_stocks_b2 = []
        for pdata in t5_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t5.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t5.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b5_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b5_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=5)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b5_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b5_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=4)
                db.add(st2)
                db.flush()
            t5_stocks_b1.append(st1)
            t5_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t5.id, u_cliente_t5, u_cajero_t5, [(b5_1, t5_stocks_b1), (b5_2, t5_stocks_b2)], min_sales=4)

        # -------------------------------------------------------------------------
        # TENANT 6: Relax Homewear & Pijamas
        # -------------------------------------------------------------------------
        print("9. Configurando Tenant 6: Relax Homewear & Pijamas (Plan Profesional)...")
        t6 = db.scalar(select(Tenant).where(Tenant.slug == "relax-homewear"))
        if not t6:
            t6 = Tenant(name="Relax Homewear & Pijamas", slug="relax-homewear", tax_id="3040506072", status="Activo")
            db.add(t6)
            db.flush()
        sync_subscription(t6.id, plan_pro)

        u_admin_t6 = ensure_user(db, "admin@relaxhomewear.com", "Admin Relax Homewear", "Administrador", tenant_id=t6.id)
        u_cajero_t6 = ensure_user(db, "cajero@relaxhomewear.com", "Cajero Equipetrol Norte", "Cajero", tenant_id=t6.id)
        u_cliente_t6 = ensure_user(db, "cliente@relaxhomewear.com", "Cliente Relax Homewear", "Cliente", tenant_id=t6.id)

        b6_1 = db.scalar(select(Branch).where(Branch.tenant_id == t6.id, Branch.name == "Sucursal Equipetrol Norte"))
        if not b6_1:
            b6_1 = Branch(tenant_id=t6.id, city_id=city_scz.id, name="Sucursal Equipetrol Norte", address="Calle Los Tucanes #300", phone="72055661", is_active=True)
            db.add(b6_1)
        b6_2 = db.scalar(select(Branch).where(Branch.tenant_id == t6.id, Branch.name == "Sucursal Cine Center"))
        if not b6_2:
            b6_2 = Branch(tenant_id=t6.id, city_id=city_scz.id, name="Sucursal Cine Center", address="Cine Center 2do Piso Local 18", phone="72055662", is_active=True)
            db.add(b6_2)
        b6_3 = db.scalar(select(Branch).where(Branch.tenant_id == t6.id, Branch.name == "Sucursal Calacoto"))
        if not b6_3:
            b6_3 = Branch(tenant_id=t6.id, city_id=city_lpz.id, name="Sucursal Calacoto", address="Calle 15 de Calacoto #780", phone="72055663", is_active=True)
            db.add(b6_3)
        db.flush()

        cat_t6_pij = ensure_category(db, "Pijamas de Invierno & Confort", t6.id)
        cat_t6_bat = ensure_category(db, "Batas y Kimonos", t6.id)
        cat_t6_lou = ensure_category(db, "Homewear & Loungewear", t6.id)
        cat_t6_pan = ensure_category(db, "Calzado de Descanso", t6.id)

        t6_products = [
            {"name": "Pijama Franela Cuadros Invierno", "brand": "ComfortSleep", "cat": cat_t6_pij, "price": Decimal("185.00"), "ws_price": Decimal("150.00"), "code": "RLX-PIJ-RED-M", "col": col_rojo, "sz": size_m, "s1": 25, "s2": 15},
            {"name": "Bata Kimono Satén Seda Royale", "brand": "Relax Elegance", "cat": cat_t6_bat, "price": Decimal("210.00"), "ws_price": Decimal("175.00"), "code": "RLX-BAT-GLD-L", "col": col_dorado, "sz": size_l, "s1": 20, "s2": 12},
            {"name": "Conjunto Soft Fleece Confort", "brand": "CloudWear", "cat": cat_t6_lou, "price": Decimal("195.00"), "ws_price": Decimal("160.00"), "code": "RLX-FLC-GRY-M", "col": col_gris, "sz": size_m, "s1": 22, "s2": 14},
            {"name": "Pantuflas Nordic Acolchadas", "brand": "WarmFeet", "cat": cat_t6_pan, "price": Decimal("115.00"), "ws_price": Decimal("90.00"), "code": "RLX-PAN-CAM-39", "col": col_camel, "sz": size_39, "s1": 28, "s2": 18},
            {"name": "Short Pijama Modal Transpirable", "brand": "PureModal", "cat": cat_t6_pij, "price": Decimal("95.00"), "ws_price": Decimal("75.00"), "code": "RLX-SHT-BLU-S", "col": col_azul, "sz": size_s, "s1": 20, "s2": 15},
        ]
        t6_stocks_b1 = []
        t6_stocks_b2 = []
        for pdata in t6_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t6.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t6.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b6_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b6_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=5)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b6_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b6_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=4)
                db.add(st2)
                db.flush()
            t6_stocks_b1.append(st1)
            t6_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t6.id, u_cliente_t6, u_cajero_t6, [(b6_1, t6_stocks_b1), (b6_2, t6_stocks_b2)], min_sales=4)

        # =========================================================================
        # GRUPO 3: PLAN EMPRESARIAL ($129.99/mes, max 15 sucursales, con IA)
        # =========================================================================

        # -------------------------------------------------------------------------
        # TENANT 7: Elegance Boutique S.R.L.
        # -------------------------------------------------------------------------
        print("10. Configurando Tenant 7: Elegance Boutique S.R.L. (Plan Empresarial)...")
        t7 = db.scalar(select(Tenant).where(Tenant.slug == "elegance-fashion"))
        if not t7:
            t7 = Tenant(name="Elegance Boutique S.R.L.", slug="elegance-fashion", tax_id="9080706050", status="Activo")
            db.add(t7)
            db.flush()
        sync_subscription(t7.id, plan_emp)

        u_admin_t7 = ensure_user(db, "admin@elegance.com", "Admin Elegance Boutique", "Administrador", tenant_id=t7.id)
        u_cajero_t7 = ensure_user(db, "cajero@elegance.com", "Cajero Ventura Mall", "Cajero", tenant_id=t7.id)
        u_cliente_t7 = ensure_user(db, "cliente@elegance.com", "Cliente Elegance Boutique", "Cliente", tenant_id=t7.id)

        b7_1 = db.scalar(select(Branch).where(Branch.tenant_id == t7.id, Branch.name == "Sucursal Ventura Mall"))
        if not b7_1:
            b7_1 = Branch(tenant_id=t7.id, city_id=city_scz.id, name="Sucursal Ventura Mall", address="Ventura Mall, Nivel 2, Local 215", phone="70099881", is_active=True)
            db.add(b7_1)
        b7_2 = db.scalar(select(Branch).where(Branch.tenant_id == t7.id, Branch.name == "Sucursal Las Brisas"))
        if not b7_2:
            b7_2 = Branch(tenant_id=t7.id, city_id=city_scz.id, name="Sucursal Las Brisas", address="Las Brisas Centro Comercial, Nivel 1", phone="70099882", is_active=True)
            db.add(b7_2)
        b7_3 = db.scalar(select(Branch).where(Branch.tenant_id == t7.id, Branch.name == "Sucursal Calacoto"))
        if not b7_3:
            b7_3 = Branch(tenant_id=t7.id, city_id=city_lpz.id, name="Sucursal Calacoto", address="Av. Ballivián entre 12 y 13 Calacoto", phone="70099883", is_active=True)
            db.add(b7_3)
        db.flush()

        cat_t7_alta = ensure_category(db, "Alta Costura y Vestidos", t7.id)
        cat_t7_sas = ensure_category(db, "Sastrería y Trajes", t7.id)
        cat_t7_abr = ensure_category(db, "Abrigos y Tapados", t7.id)

        elegance_catalog = [
            {"name": "Vestido de Gala Seda Royale", "brand": "Elegance Signature", "cat": cat_t7_alta, "price": Decimal("650.00"), "ws_price": Decimal("520.00"), "code": "ELG-DRS-BLK-M", "col": col_negro, "sz": size_m, "s1": 15, "s2": 10},
            {"name": "Traje Ejecutivo Italiano", "brand": "Elegance Sartoria", "cat": cat_t7_sas, "price": Decimal("880.00"), "ws_price": Decimal("720.00"), "code": "ELG-SUIT-BLU-L", "col": col_azul, "sz": size_l, "s1": 8, "s2": 2},
            {"name": "Smoking Ceremonia Black Tie", "brand": "Elegance Sartoria", "cat": cat_t7_sas, "price": Decimal("950.00"), "ws_price": Decimal("780.00"), "code": "ELG-SMOK-BLK-L", "col": col_negro, "sz": size_l, "s1": 12, "s2": 6},
            {"name": "Vestido Sirena Escote Corset", "brand": "Elegance Signature", "cat": cat_t7_alta, "price": Decimal("720.00"), "ws_price": Decimal("580.00"), "code": "ELG-SIRN-RED-M", "col": col_rojo, "sz": size_m, "s1": 9, "s2": 7},
            {"name": "Abrigo de Cachemira Imperial", "brand": "Elegance Sartoria", "cat": cat_t7_abr, "price": Decimal("1100.00"), "ws_price": Decimal("890.00"), "code": "ELG-COAT-CAM-M", "col": col_camel, "sz": size_m, "s1": 7, "s2": 5},
            {"name": "Blazer Doble Botonadura Sartorial", "brand": "Elegance Sartoria", "cat": cat_t7_sas, "price": Decimal("590.00"), "ws_price": Decimal("480.00"), "code": "ELG-BLAZ-GRY-L", "col": col_gris, "sz": size_l, "s1": 11, "s2": 8},
            {"name": "Vestido Midi Plisado Champagne", "brand": "Elegance Signature", "cat": cat_t7_alta, "price": Decimal("580.00"), "ws_price": Decimal("470.00"), "code": "ELG-PLIS-GLD-S", "col": col_dorado, "sz": size_s, "s1": 14, "s2": 9},
            {"name": "Blusa de Seda Crepe Organza", "brand": "Elegance Atelier", "cat": cat_t7_alta, "price": Decimal("320.00"), "ws_price": Decimal("250.00"), "code": "ELG-BLUS-WHT-S", "col": col_blanco, "sz": size_s, "s1": 18, "s2": 12},
        ]
        t7_stocks_b1 = []
        t7_stocks_b2 = []
        for pdata in elegance_catalog:
            p = db.scalar(select(Product).where(Product.tenant_id == t7.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t7.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b7_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b7_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=3)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b7_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b7_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=2)
                db.add(st2)
                db.flush()
            t7_stocks_b1.append(st1)
            t7_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t7.id, u_cliente_t7, u_cajero_t7, [(b7_1, t7_stocks_b1), (b7_2, t7_stocks_b2)], min_sales=4)

        # -------------------------------------------------------------------------
        # TENANT 8: Sartoria Milán Bespoke
        # -------------------------------------------------------------------------
        print("11. Configurando Tenant 8: Sartoria Milán Bespoke (Plan Empresarial)...")
        t8 = db.scalar(select(Tenant).where(Tenant.slug == "sartoria-milan"))
        if not t8:
            t8 = Tenant(name="Sartoria Milán Bespoke", slug="sartoria-milan", tax_id="9080706051", status="Activo")
            db.add(t8)
            db.flush()
        sync_subscription(t8.id, plan_emp)

        u_admin_t8 = ensure_user(db, "admin@sartoriamilan.com", "Admin Sartoria Milán", "Administrador", tenant_id=t8.id)
        u_cajero_t8 = ensure_user(db, "cajero@sartoriamilan.com", "Cajero Manzana 40", "Cajero", tenant_id=t8.id)
        u_cliente_t8 = ensure_user(db, "cliente@sartoriamilan.com", "Cliente Sartoria Milán", "Cliente", tenant_id=t8.id)

        b8_1 = db.scalar(select(Branch).where(Branch.tenant_id == t8.id, Branch.name == "Sucursal Manzana 40"))
        if not b8_1:
            b8_1 = Branch(tenant_id=t8.id, city_id=city_scz.id, name="Sucursal Manzana 40", address="Manzana 40 Plaza Empresarial, Torre 1", phone="73066771", is_active=True)
            db.add(b8_1)
        b8_2 = db.scalar(select(Branch).where(Branch.tenant_id == t8.id, Branch.name == "Sucursal Los Tajibos Mall"))
        if not b8_2:
            b8_2 = Branch(tenant_id=t8.id, city_id=city_scz.id, name="Sucursal Los Tajibos Mall", address="Galería Hotel Los Tajibos Local 8", phone="73066772", is_active=True)
            db.add(b8_2)
        b8_3 = db.scalar(select(Branch).where(Branch.tenant_id == t8.id, Branch.name == "Sucursal San Miguel"))
        if not b8_3:
            b8_3 = Branch(tenant_id=t8.id, city_id=city_lpz.id, name="Sucursal San Miguel", address="Calle Gabriel René Moreno #1200", phone="73066773", is_active=True)
            db.add(b8_3)
        db.flush()

        cat_t8_bes = ensure_category(db, "Trajes Bespoke a Medida", t8.id)
        cat_t8_smo = ensure_category(db, "Smokings de Ceremonia", t8.id)
        cat_t8_bla = ensure_category(db, "Blazers Sartoriales", t8.id)
        cat_t8_cam = ensure_category(db, "Camisería Fina & Pantalones", t8.id)

        t8_products = [
            {"name": "Traje 3 Piezas Príncipe de Gales", "brand": "Sartoria Milán", "cat": cat_t8_bes, "price": Decimal("2450.00"), "ws_price": Decimal("2100.00"), "code": "MIL-TRJ-GRY-L", "col": col_gris, "sz": size_l, "s1": 8, "s2": 5},
            {"name": "Smoking Solapa Chal Velvet Black Tie", "brand": "Milán Gala", "cat": cat_t8_smo, "price": Decimal("2800.00"), "ws_price": Decimal("2350.00"), "code": "MIL-SMK-BLK-L", "col": col_negro, "sz": size_l, "s1": 6, "s2": 4},
            {"name": "Blazer Doble Botonadura Navy Wool", "brand": "Sartoria Milán", "cat": cat_t8_bla, "price": Decimal("1650.00"), "ws_price": Decimal("1400.00"), "code": "MIL-BLZ-BLU-M", "col": col_azul, "sz": size_m, "s1": 10, "s2": 6},
            {"name": "Camisa Cuello Francés Hilo Doble 120s", "brand": "Milán Atelier", "cat": cat_t8_cam, "price": Decimal("480.00"), "ws_price": Decimal("390.00"), "code": "MIL-CAM-WHT-M", "col": col_blanco, "sz": size_m, "s1": 20, "s2": 15},
            {"name": "Pantalón Sartorial Pliegues Tiro Alto", "brand": "Milán Tailoring", "cat": cat_t8_cam, "price": Decimal("680.00"), "ws_price": Decimal("550.00"), "code": "MIL-PAN-GRY-L", "col": col_gris, "sz": size_l, "s1": 14, "s2": 9},
        ]
        t8_stocks_b1 = []
        t8_stocks_b2 = []
        for pdata in t8_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t8.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t8.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b8_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b8_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=2)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b8_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b8_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=2)
                db.add(st2)
                db.flush()
            t8_stocks_b1.append(st1)
            t8_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t8.id, u_cliente_t8, u_cajero_t8, [(b8_1, t8_stocks_b1), (b8_2, t8_stocks_b2)], min_sales=4)

        # -------------------------------------------------------------------------
        # TENANT 9: Nordic Winter & Coats
        # -------------------------------------------------------------------------
        print("12. Configurando Tenant 9: Nordic Winter & Coats (Plan Empresarial)...")
        t9 = db.scalar(select(Tenant).where(Tenant.slug == "nordic-winter"))
        if not t9:
            t9 = Tenant(name="Nordic Winter & Coats", slug="nordic-winter", tax_id="9080706052", status="Activo")
            db.add(t9)
            db.flush()
        sync_subscription(t9.id, plan_emp)

        u_admin_t9 = ensure_user(db, "admin@nordicwinter.com", "Admin Nordic Winter", "Administrador", tenant_id=t9.id)
        u_cajero_t9 = ensure_user(db, "cajero@nordicwinter.com", "Cajero Equipetrol Design", "Cajero", tenant_id=t9.id)
        u_cliente_t9 = ensure_user(db, "cliente@nordicwinter.com", "Cliente Nordic Winter", "Cliente", tenant_id=t9.id)

        b9_1 = db.scalar(select(Branch).where(Branch.tenant_id == t9.id, Branch.name == "Sucursal Equipetrol Design"))
        if not b9_1:
            b9_1 = Branch(tenant_id=t9.id, city_id=city_scz.id, name="Sucursal Equipetrol Design", address="Calle 9 Oeste #220", phone="73077881", is_active=True)
            db.add(b9_1)
        b9_2 = db.scalar(select(Branch).where(Branch.tenant_id == t9.id, Branch.name == "Sucursal Ventura Luxury"))
        if not b9_2:
            b9_2 = Branch(tenant_id=t9.id, city_id=city_scz.id, name="Sucursal Ventura Luxury", address="Boulevard Gastronómico Ventura Mall Local L-4", phone="73077882", is_active=True)
            db.add(b9_2)
        b9_3 = db.scalar(select(Branch).where(Branch.tenant_id == t9.id, Branch.name == "Sucursal Sopocachi"))
        if not b9_3:
            b9_3 = Branch(tenant_id=t9.id, city_id=city_lpz.id, name="Sucursal Sopocachi", address="Plaza Abaroa esq. Sánchez Lima #500", phone="73077883", is_active=True)
            db.add(b9_3)
        db.flush()

        cat_t9_abr = ensure_category(db, "Abrigos de Alta Costura", t9.id)
        cat_t9_prk = ensure_category(db, "Parkas & Plumíferos", t9.id)
        cat_t9_trn = ensure_category(db, "Trench Coats & Gabardinas", t9.id)
        cat_t9_alp = ensure_category(db, "Accesorios de Lana & Alpaca", t9.id)

        t9_products = [
            {"name": "Gabardina Trench Coat Impermeable", "brand": "Nordic Studio", "cat": cat_t9_trn, "price": Decimal("980.00"), "ws_price": Decimal("820.00"), "code": "NOR-TRN-CAM-M", "col": col_camel, "sz": size_m, "s1": 15, "s2": 10},
            {"name": "Parka Plumífero Expedition Térmica", "brand": "Nordic Explorer", "cat": cat_t9_prk, "price": Decimal("1450.00"), "ws_price": Decimal("1250.00"), "code": "NOR-PRK-BLK-L", "col": col_negro, "sz": size_l, "s1": 12, "s2": 8},
            {"name": "Chaquetón Doble Faz Lana Merino", "brand": "Nordic Heritage", "cat": cat_t9_abr, "price": Decimal("1850.00"), "ws_price": Decimal("1550.00"), "code": "NOR-CHQ-GRY-L", "col": col_gris, "sz": size_l, "s1": 8, "s2": 5},
            {"name": "Abrigo Imperial Cachemira Italiana", "brand": "Nordic Luxury", "cat": cat_t9_abr, "price": Decimal("2200.00"), "ws_price": Decimal("1850.00"), "code": "NOR-ABR-CAM-M", "col": col_camel, "sz": size_m, "s1": 7, "s2": 4},
            {"name": "Bufanda Alpaca Suri Tejida a Mano", "brand": "Andean Nordic", "cat": cat_t9_alp, "price": Decimal("350.00"), "ws_price": Decimal("280.00"), "code": "NOR-BUF-BEI-U", "col": col_beige, "sz": size_m, "s1": 25, "s2": 15},
        ]
        t9_stocks_b1 = []
        t9_stocks_b2 = []
        for pdata in t9_products:
            p = db.scalar(select(Product).where(Product.tenant_id == t9.id, Product.name == pdata["name"]))
            if not p:
                p = Product(tenant_id=t9.id, category_id=pdata["cat"].id, name=pdata["name"], brand=pdata["brand"], price=pdata["price"], wholesale_price=pdata["ws_price"], image_url=PRODUCT_IMAGES.get(pdata["name"]), is_active=True)
                db.add(p)
                db.flush()
            else:
                p.category_id = pdata["cat"].id
                p.price = pdata["price"]
                p.wholesale_price = pdata["ws_price"]
                if not p.image_url or not p.image_url.startswith("/uploads/"):
                    p.image_url = PRODUCT_IMAGES.get(pdata["name"], p.image_url)

            v = db.scalar(select(ProductVariant).where(ProductVariant.codigo == pdata["code"]))
            if not v:
                v = ProductVariant(product_id=p.id, codigo=pdata["code"], color_id=pdata["col"].id, size_id=pdata["sz"].id, price=pdata["price"], is_active=True)
                db.add(v)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b9_1.id, Stock.variant_id == v.id))
            if not st1:
                st1 = Stock(branch_id=b9_1.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s1"], reserved_stock=0, min_stock=2)
                db.add(st1)
                db.flush()
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b9_2.id, Stock.variant_id == v.id))
            if not st2:
                st2 = Stock(branch_id=b9_2.id, variant_id=v.id, size_id=pdata["sz"].id, physical_stock=pdata["s2"], reserved_stock=0, min_stock=2)
                db.add(st2)
                db.flush()
            t9_stocks_b1.append(st1)
            t9_stocks_b2.append(st2)
        db.flush()
        seed_past_sales_for_tenant(db, t9.id, u_cliente_t9, u_cajero_t9, [(b9_1, t9_stocks_b1), (b9_2, t9_stocks_b2)], min_sales=4)

        db.commit()
        print("\n✅ Siembra SaaS completada exitosamente con 9 Tenants (3 por Plan)!")
        print("─────────────────────────────────────────────────────────────────────────────")
        print("Superadmin SaaS:          superadmin@fashionstore.com   | Admin123")
        print("── PLAN BÁSICO ($29.99/mes, max 2 sucursales) ──")
        print("1. Moda Urbana S.A.:      admin@urbanstyle.com          | Admin123")
        print("                          cajero@urbanstyle.com         | Admin123")
        print("                          cliente@urbanstyle.com        | Admin123")
        print("2. Tenis Urbanos S.R.L.:  admin@tenisurbanos.com        | Admin123")
        print("                          cajero@tenisurbanos.com       | Admin123")
        print("                          cliente@tenisurbanos.com      | Admin123")
        print("3. SportActive Deportiva: admin@sportactive.com         | Admin123")
        print("                          cajero@sportactive.com        | Admin123")
        print("                          cliente@sportactive.com       | Admin123")
        print("── PLAN PROFESIONAL ($69.99/mes, max 5 sucursales, con IA) ──")
        print("4. Mundo Medias S.R.L.:   admin@mundomedias.com         | Admin123")
        print("                          cajero@mundomedias.com        | Admin123")
        print("                          cliente@mundomedias.com       | Admin123")
        print("5. Denim Co. Jeans:       admin@denimco.com             | Admin123")
        print("                          cajero@denimco.com            | Admin123")
        print("                          cliente@denimco.com           | Admin123")
        print("6. Relax Homewear:        admin@relaxhomewear.com       | Admin123")
        print("                          cajero@relaxhomewear.com      | Admin123")
        print("                          cliente@relaxhomewear.com     | Admin123")
        print("── PLAN EMPRESARIAL ($129.99/mes, max 15 sucursales, con IA) ──")
        print("7. Elegance Boutique:     admin@elegance.com            | Admin123")
        print("                          cajero@elegance.com           | Admin123")
        print("                          cliente@elegance.com          | Admin123")
        print("8. Sartoria Milán:        admin@sartoriamilan.com       | Admin123")
        print("                          cajero@sartoriamilan.com      | Admin123")
        print("                          cliente@sartoriamilan.com     | Admin123")
        print("9. Nordic Winter & Coats: admin@nordicwinter.com        | Admin123")
        print("                          cajero@nordicwinter.com       | Admin123")
        print("                          cliente@nordicwinter.com      | Admin123")
        print("─────────────────────────────────────────────────────────────────────────────")
    except Exception as e:
        db.rollback()
        print(f"❌ Error en siembra SaaS: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_saas_data()

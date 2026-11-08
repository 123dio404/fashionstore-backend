"""Script de siembra inicial para FashionStore SaaS Multitenant.

Crea los 3 planes de suscripción (Básico, Profesional y Empresarial),
las 3 empresas independientes exigidas por el Segundo Parcial:
  1. Moda Urbana S.A. (Plan Básico) - Ropa urbana y casual
  2. Mundo Medias S.R.L. (Plan Profesional) - Tienda especializada en medias
  3. Elegance Boutique S.R.L. (Plan Empresarial) - Alta costura y trajes ejecutivos con IA

Incluye usuarios Superadmin, Administradores, Cajeros y Clientes para cada empresa,
todas con la contraseña estándar: Admin123.
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal
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


def ensure_category(db, name: str, tenant_id: int | None = None) -> Category:
    cat = db.scalar(select(Category).where(Category.name == name, Category.tenant_id == tenant_id))
    if not cat:
        # Si existe huérfana sin tenant, asignarla
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


PRODUCT_IMAGES = {
    # Moda Urbana S.A.
    "Camisa Oxford Streetwear": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800&auto=format&fit=crop&q=80",
    "Blazer Oversize Lana": "https://images.unsplash.com/photo-1613915617430-8ab0fd7c6baf?w=800&auto=format&fit=crop&q=80",
    "Blazer Estructurado Street": "https://images.unsplash.com/photo-1629511565591-a1d494ad6c58?w=800&auto=format&fit=crop&q=80",
    "Chaqueta Denim Retro": "https://images.unsplash.com/photo-1603189343302-e603f7add05a?w=800&auto=format&fit=crop&q=80",
    "Sneakers Clásicas Urbanas": "https://images.unsplash.com/photo-1605523741177-cd660595c2cf?w=800&auto=format&fit=crop&q=80",
    "Sneakers Blancas Chunky": "https://images.unsplash.com/photo-1552346154-21d32810aba3?w=800&auto=format&fit=crop&q=80",
    "Vestido Midi Fluido": "https://images.unsplash.com/photo-1664076458686-3449062080ac?w=800&auto=format&fit=crop&q=80",
    "Vestido Midi Rojo Urbano": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&auto=format&fit=crop&q=80",
    "Conjunto Punto Acanalado": "https://images.unsplash.com/photo-1645996830718-127f7e4f74fc?w=800&auto=format&fit=crop&q=80",
    "Pantalón Cargo Urbano": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=800&auto=format&fit=crop&q=80",
    "Hoodie Gráfico Streetwear": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&auto=format&fit=crop&q=80",
    "Remera Oversize Graphic Lab": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800&auto=format&fit=crop&q=80",
    "Rompevientos Windbreaker Techwear": "https://images.unsplash.com/photo-1544441893-675973e31985?w=800&auto=format&fit=crop&q=80",
    "Jogger Baggy Streetwear": "https://images.unsplash.com/photo-1552902865-b72c031ac5ea?w=800&auto=format&fit=crop&q=80",
    "Gorra Urbana Trucker Edition": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=800&auto=format&fit=crop&q=80",

    # Mundo Medias S.R.L.
    "Medias Tobilleras Deportivas (Pack x3)": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=800&auto=format&fit=crop&q=80",
    "Medias de Compresión Graduada": "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=800&auto=format&fit=crop&q=80",
    "Medias Térmicas Polar de Invierno": "https://images.unsplash.com/photo-1646725582781-c09e1bcd431d?w=800&auto=format&fit=crop&q=80",
    "Medias Invisibles Antideslizantes": "https://images.unsplash.com/photo-1585499583264-491df5142e83?w=800&auto=format&fit=crop&q=80",
    "Pantis de Seda Fina Elegance": "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=800&auto=format&fit=crop&q=80",
    "Medias Ejecutivas Hilo de Escocia": "https://images.unsplash.com/photo-1608256246200-53e635b5b65f?w=800&auto=format&fit=crop&q=80",
    "Calcetines Lana Merino Senderismo": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=800&auto=format&fit=crop&q=80",
    "Medias Bucaneras Canalé Algodón": "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&auto=format&fit=crop&q=80",

    # Elegance Boutique S.R.L.
    "Vestido de Gala Seda Royale": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=800&auto=format&fit=crop&q=80",
    "Traje Ejecutivo Italiano": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=800&auto=format&fit=crop&q=80",
    "Smoking Ceremonia Black Tie": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop&q=80",
    "Vestido Sirena Escote Corset": "https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=800&auto=format&fit=crop&q=80",
    "Abrigo de Cachemira Imperial": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=800&auto=format&fit=crop&q=80",
    "Blazer Doble Botonadura Sartorial": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=800&auto=format&fit=crop&q=80",
    "Vestido Midi Plisado Champagne": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=800&auto=format&fit=crop&q=80",
    "Blusa de Seda Crepe Organza": "https://images.unsplash.com/photo-1551803091-e20673f15770?w=800&auto=format&fit=crop&q=80",
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
            plan_basico = Plan(
                name="Básico",
                max_branches=2,
                has_ai_reports=False,
                monthly_price=Decimal("29.99"),
                is_active=True,
            )
            db.add(plan_basico)
        else:
            plan_basico.max_branches = 2
            plan_basico.has_ai_reports = False
            plan_basico.monthly_price = Decimal("29.99")
            plan_basico.is_active = True

        # Plan 2: Profesional
        plan_pro = db.scalar(select(Plan).where(Plan.name == "Profesional"))
        if not plan_pro:
            plan_pro = Plan(
                name="Profesional",
                max_branches=5,
                has_ai_reports=True,
                monthly_price=Decimal("69.99"),
                is_active=True,
            )
            db.add(plan_pro)
        else:
            plan_pro.max_branches = 5
            plan_pro.has_ai_reports = True
            plan_pro.monthly_price = Decimal("69.99")
            plan_pro.is_active = True

        # Plan 3: Empresarial
        plan_emp = db.scalar(select(Plan).where(Plan.name == "Empresarial"))
        if not plan_emp:
            plan_emp = Plan(
                name="Empresarial",
                max_branches=15,
                has_ai_reports=True,
                monthly_price=Decimal("129.99"),
                is_active=True,
            )
            db.add(plan_emp)
        else:
            plan_emp.max_branches = 15
            plan_emp.has_ai_reports = True
            plan_emp.monthly_price = Decimal("129.99")
            plan_emp.is_active = True

        db.flush()

        print("3. Creando Superadministrador global SaaS...")
        ensure_user(db, "superadmin@fashionstore.com", "Superadministrador SaaS", "Superadmin", tenant_id=None)

        city = db.scalar(select(City))
        if not city:
            city = City(name="Santa Cruz de la Sierra")
            db.add(city)
            db.flush()

        # Colores y tallas base del sistema
        col_blanco = ensure_color(db, "Blanco")
        col_negro = ensure_color(db, "Negro")
        col_gris = ensure_color(db, "Gris")
        col_azul = ensure_color(db, "Azul")
        col_rojo = ensure_color(db, "Rojo")
        col_camel = ensure_color(db, "Camel")
        col_dorado = ensure_color(db, "Dorado")
        col_piel = ensure_color(db, "Piel")

        size_s = ensure_size(db, "S")
        size_m = ensure_size(db, "M")
        size_l = ensure_size(db, "L")
        size_xl = ensure_size(db, "XL")

        # ─────────────────────────────────────────────────────────────
        # 4. TENANT 1: Moda Urbana S.A. (Plan Básico)
        # ─────────────────────────────────────────────────────────────
        print("4. Configurando Tenant 1 (Moda Urbana S.A. - Plan Básico)...")
        tenant1 = db.scalar(select(Tenant).where(Tenant.slug == "urban-style"))
        if not tenant1:
            tenant1 = Tenant(
                name="Moda Urbana S.A.",
                slug="urban-style",
                tax_id="1020304050",
                status="Activo",
            )
            db.add(tenant1)
            db.flush()

        sub1 = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant1.id))
        now_utc = datetime.now(timezone.utc)
        if not sub1:
            sub1 = Subscription(
                tenant_id=tenant1.id,
                plan_id=plan_basico.id,
                start_date=now_utc,
                end_date=now_utc + timedelta(days=365),
                status="Activa",
            )
            db.add(sub1)
        else:
            sub1.plan_id = plan_basico.id
            sub1.status = "Activa"

        ensure_user(db, "admin@urbanstyle.com", "Admin Moda Urbana", "Administrador", tenant_id=tenant1.id)
        ensure_user(db, "cajero@urbanstyle.com", "Cajero Sucursal Centro", "Cajero", tenant_id=tenant1.id)
        ensure_user(db, "cliente@urbanstyle.com", "Cliente Moda Urbana", "Cliente", tenant_id=tenant1.id)

        # Sucursales Tenant 1 (Máximo 2)
        b1 = db.get(Branch, 1)
        if b1:
            b1.tenant_id = tenant1.id
        else:
            b1 = Branch(
                tenant_id=tenant1.id,
                city_id=city.id,
                name="Sucursal Centro",
                address="Calle 21 de Mayo #142",
                phone="70011223",
                is_active=True,
            )
            db.add(b1)

        b2 = db.get(Branch, 6)
        if b2:
            b2.tenant_id = tenant1.id
        else:
            b2 = Branch(
                tenant_id=tenant1.id,
                city_id=city.id,
                name="Sucursal Norte",
                address="Av. Banzer 4to Anillo",
                phone="70011224",
                is_active=True,
            )
            db.add(b2)
        db.flush()

        # Asignar y renombrar productos para Moda Urbana S.A. (eliminando marcas FashionStore)
        brand_map = {
            'Camisa Oxford': ('Camisa Oxford Streetwear', 'Urban Style Co.'),
            'Blazer Oversize Lana': ('Blazer Oversize Lana', 'Urban Casual'),
            'Blazer Estructurado': ('Blazer Estructurado Street', 'Urban Style Co.'),
            'Chaqueta Denim': ('Chaqueta Denim Retro', 'Metro Denim'),
            'Sneakers Clásicas': ('Sneakers Clásicas Urbanas', 'Urban Kicks'),
            'Sneakers Blancas': ('Sneakers Blancas Chunky', 'Urban Kicks'),
            'Vestido Midi Fluido': ('Vestido Midi Fluido', 'Urban Chic'),
            'Vestido Midi Rojo': ('Vestido Midi Rojo Urbano', 'Urban Chic'),
            'Conjunto Punto Acanalado': ('Conjunto Punto Acanalado', 'StreetWear Lab'),
        }
        cat_street = ensure_category(db, "Moda Urbana & Streetwear", tenant1.id)
        cat_acc_urb = ensure_category(db, "Accesorios Urbanos", tenant1.id)
        cat_calz_urb = ensure_category(db, "Calzado Urbano", tenant1.id)
        cat_ropa_urb = ensure_category(db, "Ropa Casual", tenant1.id)

        category_remapping_t1 = {
            'Sneakers Clásicas Urbanas': cat_calz_urb,
            'Sneakers Blancas Chunky': cat_calz_urb,
            'Camisa Oxford Streetwear': cat_ropa_urb,
            'Chaqueta Denim Retro': cat_ropa_urb,
            'Pantalón Cargo Urbano': cat_ropa_urb,
            'Blazer Oversize Lana': cat_street,
            'Blazer Estructurado Street': cat_street,
            'Vestido Midi Fluido': cat_street,
            'Vestido Midi Rojo Urbano': cat_street,
            'Conjunto Punto Acanalado': cat_street,
            'Hoodie Gráfico Streetwear': cat_street,
            'Remera Oversize Graphic Lab': cat_street,
            'Rompevientos Windbreaker Techwear': cat_street,
            'Jogger Baggy Streetwear': cat_street,
            'Gorra Urbana Trucker Edition': cat_acc_urb,
        }
        for p in db.scalars(select(Product).where(Product.tenant_id == tenant1.id)).all():
            if p.name in brand_map:
                p.name, p.brand = brand_map[p.name]
            elif p.brand == 'FashionStore':
                p.brand = 'Urban Style Co.'
            if p.name in category_remapping_t1:
                p.category_id = category_remapping_t1[p.name].id
            if p.name in PRODUCT_IMAGES and not p.image_url:
                p.image_url = PRODUCT_IMAGES[p.name]
        db.flush()
        streetwear_new = [
            {
                "name": "Remera Oversize Graphic Lab",
                "brand": "StreetWear Lab",
                "category": cat_street,
                "price": Decimal("35.00"),
                "code": "URB-REM-BLK-L",
                "color": col_negro,
                "size": size_l,
                "stock_b1": 25,
                "stock_b2": 15,
            },
            {
                "name": "Rompevientos Windbreaker Techwear",
                "brand": "Metro Denim",
                "category": cat_street,
                "price": Decimal("75.00"),
                "code": "URB-WIND-GRY-M",
                "color": col_gris,
                "size": size_m,
                "stock_b1": 18,
                "stock_b2": 12,
            },
            {
                "name": "Jogger Baggy Streetwear",
                "brand": "StreetWear Lab",
                "category": cat_street,
                "price": Decimal("52.00"),
                "code": "URB-JOG-BLK-M",
                "color": col_negro,
                "size": size_m,
                "stock_b1": 20,
                "stock_b2": 14,
            },
            {
                "name": "Gorra Urbana Trucker Edition",
                "brand": "Urban Style Co.",
                "category": cat_acc_urb,
                "price": Decimal("28.00"),
                "code": "URB-CAP-BLK-U",
                "color": col_negro,
                "size": size_m,
                "stock_b1": 30,
                "stock_b2": 20,
            },
        ]
        for s_item in streetwear_new:
            p_st = db.scalar(select(Product).where(Product.tenant_id == tenant1.id, Product.name == s_item["name"]))
            if not p_st:
                p_st = Product(
                    tenant_id=tenant1.id,
                    category_id=s_item["category"].id,
                    name=s_item["name"],
                    brand=s_item["brand"],
                    price=s_item["price"],
                    image_url=PRODUCT_IMAGES.get(s_item["name"]),
                    is_active=True,
                )
                db.add(p_st)
                db.flush()
            else:
                p_st.category_id = s_item["category"].id
                if not p_st.image_url:
                    p_st.image_url = PRODUCT_IMAGES.get(s_item["name"])

            v_st = db.scalar(select(ProductVariant).where(ProductVariant.codigo == s_item["code"]))
            if not v_st:
                v_st = ProductVariant(
                    product_id=p_st.id,
                    codigo=s_item["code"],
                    color_id=s_item["color"].id,
                    size_id=s_item["size"].id,
                    price=s_item["price"],
                    is_active=True,
                )
                db.add(v_st)
                db.flush()

            st1 = db.scalar(select(Stock).where(Stock.branch_id == b1.id, Stock.variant_id == v_st.id))
            if not st1:
                db.add(Stock(branch_id=b1.id, variant_id=v_st.id, size_id=s_item["size"].id, physical_stock=s_item["stock_b1"], reserved_stock=0, min_stock=5))
            st2 = db.scalar(select(Stock).where(Stock.branch_id == b2.id, Stock.variant_id == v_st.id))
            if not st2:
                db.add(Stock(branch_id=b2.id, variant_id=v_st.id, size_id=s_item["size"].id, physical_stock=s_item["stock_b2"], reserved_stock=0, min_stock=3))
        db.flush()

        # ─────────────────────────────────────────────────────────────
        # 5. TENANT 2: Mundo Medias S.R.L. (Plan Profesional) - Tienda de Medias
        # ─────────────────────────────────────────────────────────────
        print("5. Configurando Tenant 2 (Mundo Medias S.R.L. - Plan Profesional)...")
        tenant2 = db.scalar(select(Tenant).where(Tenant.slug == "mundo-medias"))
        if not tenant2:
            tenant2 = Tenant(
                name="Mundo Medias S.R.L.",
                slug="mundo-medias",
                tax_id="3040506070",
                status="Activo",
            )
            db.add(tenant2)
            db.flush()

        sub2 = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant2.id))
        if not sub2:
            sub2 = Subscription(
                tenant_id=tenant2.id,
                plan_id=plan_pro.id,
                start_date=now_utc,
                end_date=now_utc + timedelta(days=365),
                status="Activa",
            )
            db.add(sub2)
        else:
            sub2.plan_id = plan_pro.id
            sub2.status = "Activa"

        user_admin_mm = ensure_user(db, "admin@mundomedias.com", "Admin Mundo Medias", "Administrador", tenant_id=tenant2.id)
        user_cajero_mm = ensure_user(db, "cajero@mundomedias.com", "Cajero Sucursal Cañoto", "Cajero", tenant_id=tenant2.id)
        user_cliente_mm = ensure_user(db, "cliente@mundomedias.com", "Cliente Mundo Medias", "Cliente", tenant_id=tenant2.id)

        # Sucursales de Mundo Medias
        b_mm1 = db.scalar(select(Branch).where(Branch.tenant_id == tenant2.id, Branch.name == "Sucursal Cañoto"))
        if not b_mm1:
            b_mm1 = Branch(
                tenant_id=tenant2.id,
                city_id=city.id,
                name="Sucursal Cañoto",
                address="Av. Cañoto esq. México #450",
                phone="70033441",
                is_active=True,
            )
            db.add(b_mm1)

        b_mm2 = db.scalar(select(Branch).where(Branch.tenant_id == tenant2.id, Branch.name == "Sucursal Mutualista"))
        if not b_mm2:
            b_mm2 = Branch(
                tenant_id=tenant2.id,
                city_id=city.id,
                name="Sucursal Mutualista",
                address="3er Anillo Externo y Av. Mutualista",
                phone="70033442",
                is_active=True,
            )
            db.add(b_mm2)
        db.flush()

        # Limpieza de stock residual o cruzado entre diferentes sucursales/empresas
        db.execute(
            text("""
                DELETE FROM inventario
                WHERE id IN (
                    SELECT s.id
                    FROM inventario s
                    JOIN sucursal b ON s.id_sucursal = b.id
                    JOIN producto_variante pv ON s.id_variante = pv.id
                    JOIN producto p ON pv.id_producto = p.id
                    WHERE (b.id_empresa IS NOT NULL AND p.id_empresa IS NOT NULL AND b.id_empresa != p.id_empresa)
                       OR (b.id_empresa IS NULL AND s.id_sucursal IN (2, 3))
                )
            """)
        )
        db.flush()

        # Categorías especializadas de Medias
        cat_dep = ensure_category(db, "Medias Deportivas", tenant2.id)
        cat_cla = ensure_category(db, "Medias Clásicas y Ejecutivas", tenant2.id)
        cat_ter = ensure_category(db, "Medias Térmicas y Especiales", tenant2.id)

        # Colores y tallas
        col_blanco = ensure_color(db, "Blanco")
        col_negro = ensure_color(db, "Negro")
        col_gris = ensure_color(db, "Gris")
        col_piel = ensure_color(db, "Piel")

        size_s = ensure_size(db, "S")
        size_m = ensure_size(db, "M")
        size_l = ensure_size(db, "L")

        # Catálogo exclusivo de Medias
        medias_catalog = [
            {
                "name": "Medias Tobilleras Deportivas (Pack x3)",
                "category": cat_dep,
                "brand": "Mundo Medias Sport",
                "price": Decimal("35.00"),
                "variants": [
                    {"code": "MED-DEPO-WHT-M", "color": col_blanco, "size": size_m},
                    {"code": "MED-DEPO-BLK-L", "color": col_negro, "size": size_l},
                ],
            },
            {
                "name": "Medias de Compresión Graduada",
                "category": cat_ter,
                "brand": "MediActive Care",
                "price": Decimal("85.00"),
                "variants": [
                    {"code": "MED-COMP-BLK-M", "color": col_negro, "size": size_m},
                    {"code": "MED-COMP-SKN-L", "color": col_piel, "size": size_l},
                ],
            },
            {
                "name": "Medias Térmicas Polar de Invierno",
                "category": cat_ter,
                "brand": "WinterWarm",
                "price": Decimal("45.00"),
                "variants": [
                    {"code": "MED-POLR-GRY-M", "color": col_gris, "size": size_m},
                    {"code": "MED-POLR-BLK-L", "color": col_negro, "size": size_l},
                ],
            },
            {
                "name": "Medias Invisibles Antideslizantes",
                "category": cat_dep,
                "brand": "Mundo Medias Casual",
                "price": Decimal("25.00"),
                "variants": [
                    {"code": "MED-INVI-WHT-S", "color": col_blanco, "size": size_s},
                    {"code": "MED-INVI-BLK-M", "color": col_negro, "size": size_m},
                ],
            },
            {
                "name": "Pantis de Seda Fina Elegance",
                "category": cat_cla,
                "brand": "SilkTouch",
                "price": Decimal("50.00"),
                "variants": [
                    {"code": "MED-PANT-BLK-M", "color": col_negro, "size": size_m},
                    {"code": "MED-PANT-SKN-M", "color": col_piel, "size": size_m},
                ],
            },
            {
                "name": "Medias Ejecutivas Hilo de Escocia",
                "category": cat_cla,
                "brand": "SilkTouch",
                "price": Decimal("40.00"),
                "variants": [
                    {"code": "MED-EJEC-BLK-M", "color": col_negro, "size": size_m},
                    {"code": "MED-EJEC-GRY-L", "color": col_gris, "size": size_l},
                ],
            },
            {
                "name": "Calcetines Lana Merino Senderismo",
                "category": cat_ter,
                "brand": "WinterWarm",
                "price": Decimal("55.00"),
                "variants": [
                    {"code": "MED-MERI-GRY-M", "color": col_gris, "size": size_m},
                    {"code": "MED-MERI-BLK-L", "color": col_negro, "size": size_l},
                ],
            },
            {
                "name": "Medias Bucaneras Canalé Algodón",
                "category": cat_dep,
                "brand": "Mundo Medias Casual",
                "price": Decimal("38.00"),
                "variants": [
                    {"code": "MED-BUCA-BLK-M", "color": col_negro, "size": size_m},
                    {"code": "MED-BUCA-WHT-S", "color": col_blanco, "size": size_s},
                ],
            },
        ]

        for p_data in medias_catalog:
            prod = db.scalar(select(Product).where(Product.tenant_id == tenant2.id, Product.name == p_data["name"]))
            if not prod:
                prod = Product(
                    tenant_id=tenant2.id,
                    category_id=p_data["category"].id,
                    name=p_data["name"],
                    brand=p_data["brand"],
                    price=p_data["price"],
                    image_url=PRODUCT_IMAGES.get(p_data["name"]),
                    is_active=True,
                )
                db.add(prod)
                db.flush()
            else:
                prod.category_id = p_data["category"].id
                if not prod.image_url:
                    prod.image_url = PRODUCT_IMAGES.get(p_data["name"])

            for var_data in p_data["variants"]:
                variant = db.scalar(select(ProductVariant).where(ProductVariant.codigo == var_data["code"]))
                if not variant:
                    variant = ProductVariant(
                        product_id=prod.id,
                        codigo=var_data["code"],
                        color_id=var_data["color"].id,
                        size_id=var_data["size"].id,
                        price=p_data["price"],
                        is_active=True,
                    )
                    db.add(variant)
                    db.flush()

                # Stock en Sucursal Cañoto
                stk1 = db.scalar(select(Stock).where(Stock.branch_id == b_mm1.id, Stock.variant_id == variant.id))
                if not stk1:
                    db.add(
                        Stock(
                            branch_id=b_mm1.id,
                            variant_id=variant.id,
                            size_id=var_data["size"].id,
                            physical_stock=35,
                            reserved_stock=0,
                            min_stock=5,
                        )
                    )

                # Stock en Sucursal Mutualista
                stk2 = db.scalar(select(Stock).where(Stock.branch_id == b_mm2.id, Stock.variant_id == variant.id))
                if not stk2:
                    db.add(
                        Stock(
                            branch_id=b_mm2.id,
                            variant_id=variant.id,
                            size_id=var_data["size"].id,
                            physical_stock=25,
                            reserved_stock=0,
                            min_stock=5,
                        )
                    )
        db.flush()

        # Siembra de ventas demo para Mundo Medias (para reportes de ventas y métricas)
        ventas_mm = db.scalar(select(func.count(Sale.id)).where(Sale.tenant_id == tenant2.id)) or 0
        if ventas_mm < 3:
            stk_sample = db.scalar(select(Stock).where(Stock.branch_id == b_mm1.id))
            if stk_sample:
                s_mm1 = Sale(
                    tenant_id=tenant2.id,
                    client_id=user_cliente_mm.id,
                    user_id=user_cajero_mm.id,
                    branch_id=b_mm1.id,
                    sale_date=now_utc - timedelta(days=2),
                    total=Decimal("70.00"),
                    sale_type="contado",
                    sync_status="CONFIRMADO",
                )
                db.add(s_mm1)
                db.flush()
                db.add(SaleItem(sale_id=s_mm1.id, stock_id=stk_sample.id, quantity=2, unit_price=Decimal("35.00")))
                db.add(SalePayment(sale_id=s_mm1.id, amount=Decimal("70.00"), status="completado", paid_at=s_mm1.sale_date))

                s_mm2 = Sale(
                    tenant_id=tenant2.id,
                    client_id=user_cliente_mm.id,
                    user_id=user_cajero_mm.id,
                    branch_id=b_mm2.id,
                    sale_date=now_utc - timedelta(days=15),
                    total=Decimal("85.00"),
                    sale_type="contado",
                    sync_status="CONFIRMADO",
                )
                db.add(s_mm2)
                db.flush()
                db.add(SaleItem(sale_id=s_mm2.id, stock_id=stk_sample.id, quantity=1, unit_price=Decimal("85.00")))
                db.add(SalePayment(sale_id=s_mm2.id, amount=Decimal("85.00"), status="completado", paid_at=s_mm2.sale_date))
                db.flush()

        # ─────────────────────────────────────────────────────────────
        # 6. TENANT 3: Elegance Boutique S.R.L. (Plan Empresarial - Alta Costura e IA)
        # ─────────────────────────────────────────────────────────────
        print("6. Configurando Tenant 3 (Elegance Boutique S.R.L. - Plan Empresarial)...")
        tenant3 = db.scalar(select(Tenant).where(Tenant.slug == "elegance-fashion"))
        if not tenant3:
            tenant3 = Tenant(
                name="Elegance Boutique S.R.L.",
                slug="elegance-fashion",
                tax_id="9080706050",
                status="Activo",
            )
            db.add(tenant3)
            db.flush()

        sub3 = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant3.id))
        if not sub3:
            sub3 = Subscription(
                tenant_id=tenant3.id,
                plan_id=plan_emp.id,
                start_date=now_utc,
                end_date=now_utc + timedelta(days=365),
                status="Activa",
            )
            db.add(sub3)
        else:
            sub3.plan_id = plan_emp.id
            sub3.status = "Activa"

        ensure_user(db, "admin@elegance.com", "Admin Elegance Boutique", "Administrador", tenant_id=tenant3.id)
        ensure_user(db, "cajero@elegance.com", "Cajero Ventura Mall", "Cajero", tenant_id=tenant3.id)
        ensure_user(db, "cliente@elegance.com", "Cliente Elegance Boutique", "Cliente", tenant_id=tenant3.id)

        # Sucursales Tenant 3 (Empresarial)
        b3 = db.scalar(select(Branch).where(Branch.tenant_id == tenant3.id, Branch.name == "Sucursal Ventura Mall"))
        if not b3:
            b3 = Branch(
                tenant_id=tenant3.id,
                city_id=city.id,
                name="Sucursal Ventura Mall",
                address="Ventura Mall, Nivel 2, Local 215",
                phone="70099881",
                is_active=True,
            )
            db.add(b3)

        b4 = db.scalar(select(Branch).where(Branch.tenant_id == tenant3.id, Branch.name == "Sucursal Las Brisas"))
        if not b4:
            b4 = Branch(
                tenant_id=tenant3.id,
                city_id=city.id,
                name="Sucursal Las Brisas",
                address="Las Brisas Centro Comercial, Nivel 1",
                phone="70099882",
                is_active=True,
            )
            db.add(b4)
        db.flush()

        # Productos de alta costura para Tenant 3
        cat_alta_costura = ensure_category(db, "Alta Costura y Vestidos", tenant3.id)
        cat_sastreria = ensure_category(db, "Sastrería y Trajes", tenant3.id)
        cat_abrigos = ensure_category(db, "Abrigos y Tapados", tenant3.id)

        col_azul = ensure_color(db, "Azul")
        col_rojo = ensure_color(db, "Rojo")
        col_camel = ensure_color(db, "Camel")
        col_dorado = ensure_color(db, "Dorado")

        elegance_catalog = [
            {
                "name": "Vestido de Gala Seda Royale",
                "brand": "Elegance Signature",
                "category": cat_alta_costura,
                "price": Decimal("450.00"),
                "code": "ELG-DRS-BLK-M",
                "color": col_negro,
                "size": size_m,
                "stock_b3": 15,
                "stock_b4": 10,
            },
            {
                "name": "Traje Ejecutivo Italiano",
                "brand": "Elegance Sartoria",
                "category": cat_sastreria,
                "price": Decimal("680.00"),
                "code": "ELG-SUIT-BLU-L",
                "color": col_azul,
                "size": size_l,
                "stock_b3": 8,
                "stock_b4": 2, # Bajo stock para reporte analítico
            },
            {
                "name": "Smoking Ceremonia Black Tie",
                "brand": "Elegance Sartoria",
                "category": cat_sastreria,
                "price": Decimal("550.00"),
                "code": "ELG-SMOK-BLK-L",
                "color": col_negro,
                "size": size_l,
                "stock_b3": 12,
                "stock_b4": 6,
            },
            {
                "name": "Vestido Sirena Escote Corset",
                "brand": "Elegance Signature",
                "category": cat_alta_costura,
                "price": Decimal("520.00"),
                "code": "ELG-SIRN-RED-M",
                "color": col_rojo,
                "size": size_m,
                "stock_b3": 9,
                "stock_b4": 7,
            },
            {
                "name": "Abrigo de Cachemira Imperial",
                "brand": "Elegance Sartoria",
                "category": cat_abrigos,
                "price": Decimal("480.00"),
                "code": "ELG-COAT-CAM-M",
                "color": col_camel,
                "size": size_m,
                "stock_b3": 7,
                "stock_b4": 5,
            },
            {
                "name": "Blazer Doble Botonadura Sartorial",
                "brand": "Elegance Sartoria",
                "category": cat_sastreria,
                "price": Decimal("390.00"),
                "code": "ELG-BLAZ-GRY-L",
                "color": col_gris,
                "size": size_l,
                "stock_b3": 11,
                "stock_b4": 8,
            },
            {
                "name": "Vestido Midi Plisado Champagne",
                "brand": "Elegance Signature",
                "category": cat_alta_costura,
                "price": Decimal("380.00"),
                "code": "ELG-PLIS-GLD-S",
                "color": col_dorado,
                "size": size_s,
                "stock_b3": 14,
                "stock_b4": 9,
            },
            {
                "name": "Blusa de Seda Crepe Organza",
                "brand": "Elegance Atelier",
                "category": cat_alta_costura,
                "price": Decimal("210.00"),
                "code": "ELG-BLUS-WHT-S",
                "color": col_blanco,
                "size": size_s,
                "stock_b3": 18,
                "stock_b4": 12,
            },
        ]

        for item in elegance_catalog:
            p_obj = db.scalar(select(Product).where(Product.tenant_id == tenant3.id, Product.name == item["name"]))
            if not p_obj:
                p_obj = Product(
                    tenant_id=tenant3.id,
                    category_id=item["category"].id,
                    name=item["name"],
                    brand=item["brand"],
                    price=item["price"],
                    image_url=PRODUCT_IMAGES.get(item["name"]),
                    is_active=True,
                )
                db.add(p_obj)
                db.flush()
            else:
                p_obj.category_id = item["category"].id
                if not p_obj.image_url:
                    p_obj.image_url = PRODUCT_IMAGES.get(item["name"])

            var_obj = db.scalar(select(ProductVariant).where(ProductVariant.codigo == item["code"]))
            if not var_obj:
                var_obj = ProductVariant(
                    product_id=p_obj.id,
                    codigo=item["code"],
                    color_id=item["color"].id,
                    size_id=item["size"].id,
                    price=item["price"],
                    is_active=True,
                )
                db.add(var_obj)
                db.flush()

            stk_3 = db.scalar(select(Stock).where(Stock.branch_id == b3.id, Stock.variant_id == var_obj.id))
            if not stk_3:
                db.add(
                    Stock(
                        branch_id=b3.id,
                        variant_id=var_obj.id,
                        size_id=item["size"].id,
                        physical_stock=item["stock_b3"],
                        reserved_stock=1,
                        min_stock=3,
                    )
                )

            stk_4 = db.scalar(select(Stock).where(Stock.branch_id == b4.id, Stock.variant_id == var_obj.id))
            if not stk_4:
                db.add(
                    Stock(
                        branch_id=b4.id,
                        variant_id=var_obj.id,
                        size_id=item["size"].id,
                        physical_stock=item["stock_b4"],
                        reserved_stock=0,
                        min_stock=5 if item["stock_b4"] < 5 else 2,
                    )
                )
        db.flush()

        # Siembra de ventas demo para Tenant 3
        ventas_existentes = db.scalar(select(func.count(Sale.id)).where(Sale.tenant_id == tenant3.id)) or 0
        if ventas_existentes < 4:
            admin_t3 = db.scalar(select(User).where(User.email == "admin@elegance.com"))
            stk_v = db.scalar(select(Stock).join(ProductVariant).join(Product).where(Product.tenant_id == tenant3.id, Stock.branch_id == b3.id))
            stk_b = db.scalar(select(Stock).join(ProductVariant).join(Product).where(Product.tenant_id == tenant3.id, Stock.branch_id == b4.id))

            s1 = Sale(
                tenant_id=tenant3.id,
                client_id=admin_t3.id,
                user_id=admin_t3.id,
                branch_id=b3.id,
                sale_date=now_utc - timedelta(days=5),
                total=Decimal("900.00"),
                sale_type="contado",
                sync_status="CONFIRMADO",
            )
            db.add(s1)
            db.flush()
            if stk_v:
                db.add(SaleItem(sale_id=s1.id, stock_id=stk_v.id, quantity=2, unit_price=Decimal("450.00")))
            db.add(SalePayment(sale_id=s1.id, amount=Decimal("900.00"), status="completado", paid_at=s1.sale_date))

            s2 = Sale(
                tenant_id=tenant3.id,
                client_id=admin_t3.id,
                user_id=admin_t3.id,
                branch_id=b3.id,
                sale_date=now_utc - timedelta(days=35),
                total=Decimal("450.00"),
                sale_type="contado",
                sync_status="CONFIRMADO",
            )
            db.add(s2)
            db.flush()
            if stk_v:
                db.add(SaleItem(sale_id=s2.id, stock_id=stk_v.id, quantity=1, unit_price=Decimal("450.00")))
            db.add(SalePayment(sale_id=s2.id, amount=Decimal("450.00"), status="completado", paid_at=s2.sale_date))

            s3 = Sale(
                tenant_id=tenant3.id,
                client_id=admin_t3.id,
                user_id=admin_t3.id,
                branch_id=b4.id,
                sale_date=now_utc - timedelta(days=65),
                total=Decimal("680.00"),
                sale_type="contado",
                sync_status="CONFIRMADO",
            )
            db.add(s3)
            db.flush()
            if stk_b:
                db.add(SaleItem(sale_id=s3.id, stock_id=stk_b.id, quantity=1, unit_price=Decimal("680.00")))
            db.add(SalePayment(sale_id=s3.id, amount=Decimal("680.00"), status="completado", paid_at=s3.sale_date))

            s4 = Sale(
                tenant_id=tenant3.id,
                client_id=admin_t3.id,
                user_id=admin_t3.id,
                branch_id=b4.id,
                sale_date=now_utc - timedelta(days=12),
                total=Decimal("680.00"),
                sale_type="contado",
                sync_status="CONFIRMADO",
            )
            db.add(s4)
            db.flush()
            if stk_b:
                db.add(SaleItem(sale_id=s4.id, stock_id=stk_b.id, quantity=1, unit_price=Decimal("680.00")))
            db.add(SalePayment(sale_id=s4.id, amount=Decimal("680.00"), status="completado", paid_at=s4.sale_date))

        db.commit()
        print("\n✅ Siembra SaaS completada exitosamente!")
        print("─────────────────────────────────────────────────────────────────────────────")
        print("Superadmin SaaS:       superadmin@fashionstore.com  | Admin123")
        print("Tenant 1 (Básico):     admin@urbanstyle.com         | Admin123")
        print("                       cajero@urbanstyle.com        | Admin123")
        print("                       cliente@urbanstyle.com       | Admin123")
        print("Tenant 2 (Profesional):admin@mundomedias.com        | Admin123")
        print("                       cajero@mundomedias.com       | Admin123")
        print("                       cliente@mundomedias.com      | Admin123")
        print("Tenant 3 (Empresarial):admin@elegance.com           | Admin123")
        print("                       cajero@elegance.com          | Admin123")
        print("                       cliente@elegance.com         | Admin123")
        print("─────────────────────────────────────────────────────────────────────────────")
    except Exception as e:
        db.rollback()
        print(f"❌ Error en siembra SaaS: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_saas_data()

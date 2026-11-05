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
from sqlalchemy import func, select

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


def ensure_category(db, name: str) -> Category:
    cat = db.scalar(select(Category).where(Category.name == name))
    if not cat:
        cat = Category(name=name)
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
                has_ai_reports=False,
                monthly_price=Decimal("69.99"),
                is_active=True,
            )
            db.add(plan_pro)
        else:
            plan_pro.max_branches = 5
            plan_pro.has_ai_reports = False
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

        # Asignar productos existentes a Tenant 1
        existing_products = db.scalars(select(Product).where(Product.tenant_id.is_(None))).all()
        for p in existing_products:
            p.tenant_id = tenant1.id
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

        # Categorías especializadas de Medias
        cat_dep = ensure_category(db, "Medias Deportivas")
        cat_cla = ensure_category(db, "Medias Clásicas y Ejecutivas")
        cat_ter = ensure_category(db, "Medias Térmicas y Especiales")

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
                    is_active=True,
                )
                db.add(prod)
                db.flush()

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
        cat_damas = db.scalar(select(Category).where(Category.name.ilike("%dama%"))) or ensure_category(db, "Vestidos y Alta Costura")

        p_elegance = db.scalar(select(Product).where(Product.tenant_id == tenant3.id, Product.name == "Vestido de Gala Seda Royale"))
        if not p_elegance:
            p_elegance = Product(
                tenant_id=tenant3.id,
                category_id=cat_damas.id,
                name="Vestido de Gala Seda Royale",
                brand="Elegance Signature",
                price=Decimal("450.00"),
                is_active=True,
            )
            db.add(p_elegance)
            db.flush()

            var1 = ProductVariant(
                product_id=p_elegance.id,
                codigo="ELG-DRS-BLK-M",
                color_id=col_negro.id,
                size_id=size_m.id,
                price=Decimal("450.00"),
                is_active=True,
            )
            db.add(var1)
            db.flush()

            stock_elegance = Stock(
                branch_id=b3.id,
                variant_id=var1.id,
                size_id=size_m.id,
                physical_stock=15,
                reserved_stock=2,
                min_stock=3,
            )
            db.add(stock_elegance)

        # Producto 2: Traje Ejecutivo Italiano (con bajo stock para Reporte 4)
        p_traje = db.scalar(select(Product).where(Product.tenant_id == tenant3.id, Product.name == "Traje Ejecutivo Italiano"))
        if not p_traje:
            p_traje = Product(
                tenant_id=tenant3.id,
                category_id=cat_damas.id,
                name="Traje Ejecutivo Italiano",
                brand="Elegance Sartoria",
                price=Decimal("680.00"),
                is_active=True,
            )
            db.add(p_traje)
            db.flush()

            col_azul = ensure_color(db, "Azul")
            var2 = ProductVariant(
                product_id=p_traje.id,
                codigo="ELG-SUIT-BLU-L",
                color_id=col_azul.id,
                size_id=size_l.id,
                price=Decimal("680.00"),
                is_active=True,
            )
            db.add(var2)
            db.flush()

            stock_critico = Stock(
                branch_id=b4.id,
                variant_id=var2.id,
                size_id=size_l.id,
                physical_stock=2,
                reserved_stock=0,
                min_stock=5,
            )
            db.add(stock_critico)
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

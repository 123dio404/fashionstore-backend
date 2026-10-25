"""Script de siembra inicial para FashionStore SaaS Multitenant.

Crea los planes de suscripción (Básico y Profesional), las dos empresas independientes
exigidas por el Segundo Parcial (Moda Urbana S.A. y Elegance Boutique S.R.L.),
sus usuarios administradores y cajeros, sus sucursales y sus inventarios independientes.
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
from app.services.auth_service import normalize_email

DEMO_PASSWORD = "admin123"


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


def seed_saas_data():
    db = SessionLocal()
    try:
        print("1. Verificando roles del sistema...")
        ensure_role(db, "Superadmin")
        ensure_role(db, "Administrador")
        ensure_role(db, "Encargado")
        ensure_role(db, "Cajero")
        ensure_role(db, "Cliente")

        print("2. Creando planes de suscripción...")
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

        plan_pro = db.scalar(select(Plan).where(Plan.name == "Profesional"))
        if not plan_pro:
            plan_pro = Plan(
                name="Profesional",
                max_branches=10,
                has_ai_reports=True,
                monthly_price=Decimal("99.99"),
                is_active=True,
            )
            db.add(plan_pro)
        db.flush()

        print("3. Creando Superadministrador global SaaS...")
        ensure_user(db, "superadmin@fashionstore.com", "Superadministrador SaaS", "Superadmin", tenant_id=None)

        print("4. Creando Empresa 1 (Tenant 1: Moda Urbana S.A. - Plan Básico)...")
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
        if not sub1:
            sub1 = Subscription(
                tenant_id=tenant1.id,
                plan_id=plan_basico.id,
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc) + timedelta(days=365),
                status="Activa",
            )
            db.add(sub1)

        ensure_user(db, "admin@urbanstyle.com", "Admin Moda Urbana", "Administrador", tenant_id=tenant1.id)
        ensure_user(db, "cajero@urbanstyle.com", "Cajero Sucursal Centro", "Cajero", tenant_id=tenant1.id)

        print("5. Creando Empresa 2 (Tenant 2: Elegance Boutique S.R.L. - Plan Profesional)...")
        tenant2 = db.scalar(select(Tenant).where(Tenant.slug == "elegance-fashion"))
        if not tenant2:
            tenant2 = Tenant(
                name="Elegance Boutique S.R.L.",
                slug="elegance-fashion",
                tax_id="9080706050",
                status="Activo",
            )
            db.add(tenant2)
            db.flush()

        sub2 = db.scalar(select(Subscription).where(Subscription.tenant_id == tenant2.id))
        if not sub2:
            sub2 = Subscription(
                tenant_id=tenant2.id,
                plan_id=plan_pro.id,
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc) + timedelta(days=365),
                status="Activa",
            )
            db.add(sub2)

        ensure_user(db, "admin@elegance.com", "Admin Elegance Boutique", "Administrador", tenant_id=tenant2.id)
        ensure_user(db, "cajero@elegance.com", "Cajero Ventura Mall", "Cajero", tenant_id=tenant2.id)

        print("6. Configurando sucursales por tenant...")
        city = db.scalar(select(City))
        if not city:
            city = City(name="Santa Cruz de la Sierra")
            db.add(city)
            db.flush()

        # Sucursales Tenant 1 (Máx 2 en Básico: se asocian las sucursales existentes del parcial 1)
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


        # Sucursales Tenant 2 (Profesional)
        b3 = db.scalar(select(Branch).where(Branch.tenant_id == tenant2.id, Branch.name == "Sucursal Ventura Mall"))
        if not b3:
            b3 = Branch(
                tenant_id=tenant2.id,
                city_id=city.id,
                name="Sucursal Ventura Mall",
                address="Ventura Mall, Nivel 2, Local 215",
                phone="70099881",
                is_active=True,
            )
            db.add(b3)

        b4 = db.scalar(select(Branch).where(Branch.tenant_id == tenant2.id, Branch.name == "Sucursal Las Brisas"))
        if not b4:
            b4 = Branch(
                tenant_id=tenant2.id,
                city_id=city.id,
                name="Sucursal Las Brisas",
                address="Las Brisas Centro Comercial, Nivel 1",
                phone="70099882",
                is_active=True,
            )
            db.add(b4)

        db.flush()

        print("7. Asignando productos a tenants...")
        # Asegurar que productos existentes tengan tenant_id = tenant1.id
        existing_products = db.scalars(select(Product).where(Product.tenant_id.is_(None))).all()
        for p in existing_products:
            p.tenant_id = tenant1.id
        db.flush()

        # Crear productos exclusivos para Tenant 2 (Elegance Boutique)
        cat_damas = db.scalar(select(Category).where(Category.name.ilike("%dama%")))
        if not cat_damas:
            cat_damas = db.scalar(select(Category))
            if not cat_damas:
                cat_damas = Category(name="Vestidos y Alta Costura")
                db.add(cat_damas)
                db.flush()

        p_elegance = db.scalar(select(Product).where(Product.tenant_id == tenant2.id, Product.name == "Vestido de Gala Seda Royale"))
        if not p_elegance:
            p_elegance = Product(
                tenant_id=tenant2.id,
                category_id=cat_damas.id,
                name="Vestido de Gala Seda Royale",
                brand="Elegance Signature",
                price=Decimal("450.00"),
                is_active=True,
            )
            db.add(p_elegance)
            db.flush()

            # Variantes
            color_negro = db.scalar(select(Color).where(Color.name == "Negro")) or Color(name="Negro")
            size_m = db.scalar(select(Size).where(Size.name == "M")) or Size(name="M")
            db.add(color_negro)
            db.add(size_m)
            db.flush()

            var1 = ProductVariant(
                product_id=p_elegance.id,
                codigo="ELG-DRS-BLK-M",
                color_id=color_negro.id,
                size_id=size_m.id,
                price=Decimal("450.00"),
                is_active=True,
            )
            db.add(var1)
            db.flush()

            # Stock en Sucursal Ventura Mall
            stock_elegance = Stock(
                branch_id=b3.id,
                variant_id=var1.id,
                size_id=size_m.id,
                physical_stock=15,
                reserved_stock=2,
                min_stock=3,
            )
            db.add(stock_elegance)

        # Producto 2: Traje Ejecutivo Italiano (con bajo stock en Las Brisas para Reporte 4)
        p_traje = db.scalar(select(Product).where(Product.tenant_id == tenant2.id, Product.name == "Traje Ejecutivo Italiano"))
        if not p_traje:
            p_traje = Product(
                tenant_id=tenant2.id,
                category_id=cat_damas.id,
                name="Traje Ejecutivo Italiano",
                brand="Elegance Sartoria",
                price=Decimal("680.00"),
                is_active=True,
            )
            db.add(p_traje)
            db.flush()

            color_azul = db.scalar(select(Color).where(Color.name == "Azul")) or Color(name="Azul")
            size_l = db.scalar(select(Size).where(Size.name == "L")) or Size(name="L")
            db.add(color_azul)
            db.add(size_l)
            db.flush()

            var2 = ProductVariant(
                product_id=p_traje.id,
                codigo="ELG-SUIT-BLU-L",
                color_id=color_azul.id,
                size_id=size_l.id,
                price=Decimal("680.00"),
                is_active=True,
            )
            db.add(var2)
            db.flush()

            # Stock crítico (solo 2 disponibles, mínimo 5) para probar Reporte 4
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

        # Siembra de ventas demo para Tenant 2 (distribuidas en los últimos 3 meses)
        from app.models.commerce import Sale, SaleItem, SalePayment
        ventas_existentes = db.scalar(select(func.count(Sale.id)).where(Sale.tenant_id == tenant2.id)) or 0
        if ventas_existentes < 4:
            admin_t2 = db.scalar(select(User).where(User.email == "admin@elegance.com"))
            stk_v = db.scalar(select(Stock).join(ProductVariant).join(Product).where(Product.tenant_id == tenant2.id, Stock.branch_id == b3.id))
            stk_b = db.scalar(select(Stock).join(ProductVariant).join(Product).where(Product.tenant_id == tenant2.id, Stock.branch_id == b4.id))

            now_utc = datetime.now(timezone.utc)
            # Venta mes actual (Ventura Mall)
            s1 = Sale(
                tenant_id=tenant2.id,
                client_id=admin_t2.id,
                user_id=admin_t2.id,
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

            # Venta mes anterior (Ventura Mall)
            s2 = Sale(
                tenant_id=tenant2.id,
                client_id=admin_t2.id,
                user_id=admin_t2.id,
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

            # Venta hace 2 meses (Las Brisas)
            s3 = Sale(
                tenant_id=tenant2.id,
                client_id=admin_t2.id,
                user_id=admin_t2.id,
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

            # Venta reciente (Las Brisas)
            s4 = Sale(
                tenant_id=tenant2.id,
                client_id=admin_t2.id,
                user_id=admin_t2.id,
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
        print("─────────────────────────────────────────────────────────────")
        print("Superadmin SaaS:       superadmin@fashionstore.com  | admin123")
        print("Tenant 1 (Básico):     admin@urbanstyle.com         | admin123")
        print("                       cajero@urbanstyle.com        | admin123")
        print("Tenant 2 (Profesional):admin@elegance.com           | admin123")
        print("                       cajero@elegance.com          | admin123")
        print("─────────────────────────────────────────────────────────────")
    except Exception as e:
        db.rollback()
        print(f"❌ Error en siembra SaaS: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_saas_data()

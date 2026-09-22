"""Cuentas de prueba de los actores del dominio (siembra de demo).

Los 5 actores (roles) del sistema y sus cuentas genéricas usan la contraseña
`admin123` y se (re)crean al arrancar la API cuando `SEED_DEMO_USERS=true`
(por defecto). Para producción real, desactivar con `SEED_DEMO_USERS=false`.

La siembra es idempotente: si una cuenta ya existe, restablece su contraseña a
`admin123` y garantiza que tenga el rol correcto.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.branch import Branch, City
from app.models.inventory import Stock
from app.models.product import Category, Color, Product, ProductVariant, Season, Size
from app.models.user import Role, User
from app.services.auth_service import get_role, normalize_email

DEMO_PASSWORD = "admin123"

# (rol, email genérico, nombre completo)
DEMO_ACTORS: list[tuple[Role, str, str]] = [
    (Role.ADMINISTRADOR, "admin@fashionstore.com", "Administrador"),
    (Role.ENCARGADO, "encargado@fashionstore.com", "Encargado de tienda"),
    (Role.CAJERO, "cajero@fashionstore.com", "Cajero"),
    (Role.CLIENTE, "cliente@fashionstore.com", "Cliente de prueba"),
    (Role.PROVEEDOR, "proveedor@fashionstore.com", "Proveedor"),
]


def upsert_actor(db, role: Role, email: str, full_name: str) -> str:
    """Crea el usuario con el rol indicado o restablece sus credenciales si ya existe."""
    normalized = normalize_email(email)
    rol = get_role(db, role)
    user = db.scalar(select(User).where(User.email == normalized))

    if user is None:
        user = User(
            email=normalized,
            full_name=full_name,
            password_hash=get_password_hash(DEMO_PASSWORD),
            is_active=True,
        )
        user.roles = [rol]
        db.add(user)
        action = "creado"
    else:
        user.full_name = full_name
        user.password_hash = get_password_hash(DEMO_PASSWORD)
        user.is_active = True
        user.roles = [rol]
        action = "actualizado"

    return f"{role.value}: {normalized} ({action})"


def ensure_demo_users() -> list[str]:
    """Crea/actualiza las 5 cuentas demo. Devuelve un resumen por cuenta."""
    db = SessionLocal()
    results: list[str] = []
    try:
        for role, email, name in DEMO_ACTORS:
            results.append(upsert_actor(db, role, email, name))
        db.commit()
    finally:
        db.close()
    return results


# --------------------------------------------------------------------------- #
# Catálogo de demostración (CU08 / CU10 / CU11 / CU17)                        #
# --------------------------------------------------------------------------- #
# Sin catálogo la base queda vacía y ninguna venta puede tocar inventario real.
# La siembra es idempotente: el producto existente solo actualiza precio y modelo
# 3D, y ni las variantes ni el stock se duplican (tienen constraints únicos).

# Modelos 3D de demostración del Khronos Group: los mismos que consumen la web y
# el móvil en el Vestidor Virtual AR cuando el producto no trae uno propio.
AR_CLOTH_MODEL = (
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/"
    "main/Models/SheenCloth/glTF/SheenCloth.gltf"
)
AR_SHOE_MODEL = (
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/"
    "master/2.0/MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb"
)
AR_ACCESSORY_MODEL = (
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/"
    "main/Models/SunglassesKhronos/glTF-Binary/SunglassesKhronos.glb"
)

DEMO_CITIES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Ciudad de Guatemala",
        [
            ("Sucursal Centro", "6a Avenida 12-34, Zona 1"),
            ("Sucursal Norte", "Calzada Roosevelt 22-10, Zona 7"),
            ("Sucursal Sur", "Boulevard Villa Lobos 15-60, Zona 12"),
        ],
    )
]

DEMO_SEASONS: list[tuple[str, str, str]] = [
    ("Primavera-Verano", "2026-03-01", "2026-08-31"),
    ("Otoño-Invierno", "2026-09-01", "2027-02-28"),
]

DEMO_CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
DEMO_SHOE_SIZES = ["36", "37", "38", "39", "40", "41", "42"]

# (nombre, marca, categoría, precio, tallas de la demo, colores de la demo)
DEMO_CATALOG: list[tuple[str, str, str, str, list[str], list[str]]] = [
    ("Blazer Oversize Lana", "Massimo", "Mujer", "89.99", ["S", "M", "L"], ["Negro", "Beige"]),
    ("Vestido Midi Fluido", "Zara Studio", "Mujer", "67.50", ["S", "M", "L"], ["Terracota", "Negro"]),
    ("Conjunto Punto Acanalado", "COS", "Mujer", "54.00", ["S", "M", "L"], ["Gris", "Camel"]),
    ("Blazer Estructurado", "Massimo", "Mujer", "112.00", ["S", "M", "L"], ["Negro", "Carbón"]),
    ("Sneakers Clásicas", "Nike", "Calzado", "79.99", ["38", "39", "40"], ["Blanco", "Negro"]),
    ("Chaqueta Denim", "Levis", "Hombre", "95.00", ["S", "M", "L"], ["Índigo", "Negro"]),
    ("Vestido Midi Rojo", "Zara Studio", "Mujer", "74.99", ["S", "M", "L"], ["Rojo", "Terracota"]),
    ("Sneakers Blancas", "Adidas", "Calzado", "59.99", ["38", "39", "40"], ["Blanco", "Gris"]),
]

# Stock físico inicial por sucursal (CU21: existencias por sucursal).
DEMO_BRANCH_STOCK = {"Sucursal Centro": 6, "Sucursal Norte": 3, "Sucursal Sur": 9}
DEMO_MIN_STOCK = 2


def model_3d_for(category: str) -> tuple[str, str]:
    """Modelo 3D y formato que corresponden a la categoría del producto (CU17)."""
    value = category.casefold()
    if "calz" in value or "zapat" in value:
        return AR_SHOE_MODEL, "glb"
    if "acces" in value or "gafa" in value:
        return AR_ACCESSORY_MODEL, "glb"
    return AR_CLOTH_MODEL, "gltf"


def slug(value: str) -> str:
    """Código ASCII en mayúsculas sin acentos ('Índigo' → 'INDIGO')."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return "".join(char for char in normalized.upper() if char.isalnum())


def get_or_create(db, model, **kwargs):
    """Devuelve la fila existente (buscada por `kwargs`) o la crea."""
    instance = db.scalar(select(model).filter_by(**kwargs))
    if instance is not None:
        return instance
    instance = model(**kwargs)
    db.add(instance)
    db.flush()
    return instance


def ensure_demo_catalog() -> list[str]:
    """Siembra la red de sucursales, los parámetros y los 8 productos demo con sus
    variantes (talla × color) y stock por sucursal. Idempotente."""
    db = SessionLocal()
    summary: list[str] = []
    try:
        # 1. Ciudades y sucursales (se reutiliza la sucursal si ya existe por nombre,
        #    para no duplicar "Sucursal Centro" cuando la base ya tiene datos).
        branch_total = 0
        for city_name, branches in DEMO_CITIES:
            city = get_or_create(db, City, name=city_name)
            for branch_name, address in branches:
                branch = db.scalar(select(Branch).where(Branch.name == branch_name))
                if branch is None:
                    branch = Branch(
                        city_id=city.id, name=branch_name, address=address, is_active=True
                    )
                    db.add(branch)
                    db.flush()
                    branch_total += 1
        summary.append(f"sucursales nuevas: {branch_total}")

        # 2. Parámetros (temporadas, tallas)
        for season_name, start, end in DEMO_SEASONS:
            get_or_create(
                db,
                Season,
                name=season_name,
                start_date=date.fromisoformat(start),
                end_date=date.fromisoformat(end),
            )
        for size_name in DEMO_CLOTHING_SIZES + DEMO_SHOE_SIZES:
            get_or_create(db, Size, name=size_name)
        summary.append(f"tallas: {len(DEMO_CLOTHING_SIZES + DEMO_SHOE_SIZES)}")

        # 3. Productos con variantes y stock por sucursal
        branches = db.scalars(select(Branch).order_by(Branch.id)).all()
        created = 0
        variants_created = 0
        for name, brand, category_name, price, sizes, colors in DEMO_CATALOG:
            category = get_or_create(db, Category, name=category_name)
            season_name = "Primavera-Verano" if category_name == "Calzado" else "Otoño-Invierno"
            season = db.scalar(select(Season).where(Season.name == season_name))
            model_url, model_format = model_3d_for(category_name)

            product = db.scalar(select(Product).where(Product.name == name))
            if product is None:
                product = Product(
                    name=name,
                    brand=brand,
                    category_id=category.id,
                    season_id=season.id if season is not None else None,
                    price=Decimal(price),
                    model_3d_url=model_url,
                    model_3d_format=model_format,
                )
                db.add(product)
                db.flush()
                created += 1
            product.brand = brand
            product.category_id = category.id
            product.season_id = season.id if season is not None else None
            product.price = Decimal(price)
            product.is_active = True
            product.model_3d_url = model_url
            product.model_3d_format = model_format

            for size_name in sizes:
                size = db.scalar(select(Size).where(Size.name == size_name))
                for color_name in colors:
                    color = get_or_create(db, Color, name=color_name)
                    code = f"FS-{product.id:03d}-{size_name}-{slug(color_name)[:4]}"
                    variant = db.scalar(
                        select(ProductVariant).where(ProductVariant.codigo == code)
                    )
                    if variant is None:
                        variant = ProductVariant(
                            product_id=product.id,
                            codigo=code,
                            price=Decimal(price),
                            size_id=size.id if size is not None else None,
                            color_id=color.id,
                        )
                        db.add(variant)
                        db.flush()
                        variants_created += 1
                    variant.price = Decimal(price)
                    variant.is_active = True
                    variant.size_id = size.id if size is not None else None
                    variant.color_id = color.id

                    for branch in branches:
                        stock = db.scalar(
                            select(Stock).where(
                                Stock.branch_id == branch.id,
                                Stock.variant_id == variant.id,
                            )
                        )
                        target = DEMO_BRANCH_STOCK.get(branch.name, 4)
                        if stock is None:
                            stock = Stock(branch_id=branch.id, variant_id=variant.id)
                            db.add(stock)
                        stock.size_id = size.id if size is not None else None
                        stock.min_stock = DEMO_MIN_STOCK
                        if not stock.physical_stock:
                            stock.physical_stock = target

        summary.append(f"productos nuevos: {created}/{len(DEMO_CATALOG)}")
        summary.append(f"variantes nuevas: {variants_created}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return summary

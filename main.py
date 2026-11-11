import logging
import os
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.services.seed_service import ensure_demo_catalog, ensure_demo_purchases, ensure_demo_users
import app.models  # noqa: F401

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == 'development':
        Base.metadata.create_all(bind=engine)
    if settings.seed_demo_users:
        try:
            for line in ensure_demo_users():
                logger.info("Cuenta demo: %s", line)
        except Exception:
            logger.exception("No se pudieron sembrar las cuentas demo")
    if settings.seed_demo_catalog:
        try:
            for line in ensure_demo_catalog():
                logger.info("Catálogo demo: %s", line)
        except Exception:
            logger.exception("No se pudo sembrar el catálogo demo")
    if settings.seed_demo_purchases:
        try:
            for line in ensure_demo_purchases():
                logger.info("Compras demo: %s", line)
        except Exception:
            logger.exception("No se pudo sembrar el historial de compras demo")
    yield

app = FastAPI(title=settings.app_name, version='1.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(api_router)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get('/health', tags=['health'])
@app.head('/health', tags=['health'])
def health() -> dict[str, Any]:
    return {
        'status': 'ok',
        'commit': os.environ.get('RENDER_GIT_COMMIT', '')[:7] or 'unknown',
    }


@app.get('/health/schema', tags=['health'])
def health_schema() -> dict[str, Any]:
    """Diagnóstico: columnas que deben existir tras la sincronización de arranque."""
    from sqlalchemy import inspect

    expected = {
        'categoria': ['id_empresa'],
        'producto': ['imagen_url'],
    }
    inspector = inspect(engine)
    missing: list[str] = []
    for table, columns in expected.items():
        if not inspector.has_table(table):
            missing.append(f'{table} (tabla ausente)')
            continue
        existing = {column['name'] for column in inspector.get_columns(table)}
        for column in columns:
            if column not in existing:
                missing.append(f'{table}.{column}')
    return {
        'ok': not missing,
        'commit': os.environ.get('RENDER_GIT_COMMIT', '')[:7] or 'unknown',
        'missing': missing,
    }

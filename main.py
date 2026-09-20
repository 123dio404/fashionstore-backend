import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.services.seed_service import ensure_demo_users
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
    yield

app = FastAPI(title=settings.app_name, version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(api_router)

@app.get('/health', tags=['health'])
def health() -> dict[str,str]: return {'status':'ok'}

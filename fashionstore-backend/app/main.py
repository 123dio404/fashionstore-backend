from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
import app.models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == 'development': Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.app_name, version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(api_router)

@app.get('/health', tags=['health'])
def health() -> dict[str,str]: return {'status':'ok'}

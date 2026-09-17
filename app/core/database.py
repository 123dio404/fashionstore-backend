from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


if not settings.database_url.startswith("postgresql"):
    raise RuntimeError("El backend solo soporta PostgreSQL: configura DATABASE_URL con postgresql://...")

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session and always close it."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

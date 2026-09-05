# FashionStore Backend

FastAPI + SQLAlchemy 2.0 backend for CU01-CU09.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The default development database is SQLite (`fashionstore.db`). Set `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS` and `ACCESS_TOKEN_EXPIRE_MINUTES` in the environment for deployment. For migrations:

```bash
alembic upgrade head
```

Interactive API documentation is available at `/docs`.

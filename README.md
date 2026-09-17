# FashionStore Backend

FastAPI + SQLAlchemy 2.0 backend for CU01-CU18. The API includes authentication and roles, branches and catalog management, variants with GLB/GLTF metadata, multi-branch inventory, cart and payment-provider workflows, POS receipts, fitting-room reservations, virtual fitting sessions, personalized recommendations, and executive analytics.

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

## Main endpoint groups

- `/api/v1/auth`, `/api/v1/users`: registration, JWT login, profiles, users and roles.
- `/api/v1/cities`, `/api/v1/branches`, `/api/v1/products`, `/api/v1/products/parameters/*`, `/api/v1/suppliers`: branches and catalog.
- `/api/v1/inventory`: availability, adjustments, transfers and movement history.
- `/api/v1/commerce`: carts, digital checkout, POS sales/receipts, and fitting-room reservation workflows.
- `/api/v1/fitting`, `/api/v1/recommendations`: virtual fitting, preferences and recommendations.
- `/api/v1/analytics/executive`: omnichannel sales and inventory-rotation metrics.

The built-in `mock` payment provider is deterministic and intended for development. Configure a real provider before production use.

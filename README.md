# FashionStore Backend

FastAPI + SQLAlchemy 2.0 backend for CU01-CU24. The API includes authentication and roles, branches and catalog management, variants with GLB/GLTF metadata, multi-branch inventory, cart and payment-provider workflows, POS receipts, fitting-room reservations, purchase history, virtual fitting sessions, personalized recommendations, chatbot conversations, collections, promotions, sales and inventory reports, executive dashboards, and analytical queries.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

The default development database is SQLite (`fashionstore.db`). Set `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS` and `ACCESS_TOKEN_EXPIRE_MINUTES` in the environment for deployment. For migrations:

```bash
alembic upgrade head
```

Interactive API documentation is available at `/docs`.

## Actors and authorization

- **CL**: `Cliente`, the end user who registers, shops, reserves, reviews purchases, uses the virtual fitting room, recommendations, and chatbot.
- **AD**: `Administrador`, with platform-wide management and reporting permissions.
- **ES**: `Encargado`, responsible for branch operations, inventory, reservations, suppliers, and sales reports.
- **CA**: `Cajero`, responsible for POS sales and in-store reservation handling.
- **PR**: `Proveedor`, supported as an authenticated profile; supplier catalog operations remain controlled by AD/ES.
- **PP**: payment provider abstraction (`mock` in development).
- **IA**: deterministic recommendation, chatbot, and analytical-query services, ready to be replaced by external AI providers.

## Modules and requirements

1. **Security and access** — RF01-RF02: registration, JWT authentication, profiles, users, roles, and permissions.
2. **Branches and geographic network** — RF03: cities, branches, contact data, and fitting-room capacity.
3. **Catalog, products, and collections** — RF04-RF07 and RF23: garments, variants, parameters, suppliers, catalog queries, collections, and promotions.
4. **Multi-branch inventory** — RF08 and RF20-RF22: availability, atomic sale decrements, reserved/available stock, and movements.
5. **Reservations and physical fitting rooms** — RF09-RF12: multi-item reservations, lifecycle, branch assignment, status tracking, and stock retention/release.
6. **Sales, billing, and POS** — RF14-RF19: cart, digital checkout, POS, payment states, receipts, and payment-provider integration point.
7. **Immersive experience** — RF13: virtual fitting sessions and GLB/GLTF result metadata; AR rendering is consumed by the mobile client.
8. **Artificial intelligence services** — RF25: recommendations, chatbot assistance, and analytical query services.
9. **Business reporting and analytics** — RF24: purchase history, sales/inventory reports, executive dashboard, and text/voice-ready analytical reports.

## Main endpoint groups

- `/api/v1/auth`, `/api/v1/users`: CU01-CU03.
- `/api/v1/cities`, `/api/v1/branches`, `/api/v1/products`, `/api/v1/products/parameters/*`, `/api/v1/suppliers`: CU04-CU08 and CU20.
- `/api/v1/inventory`: CU09 and CU22.
- `/api/v1/commerce`: CU10-CU16.
- `/api/v1/fitting`, `/api/v1/recommendations`, `/api/v1/chatbot`: CU17-CU19.
- `/api/v1/collections`, `/api/v1/promotions`: CU20.
- `/api/v1/reports`: CU16 and CU21-CU24.

The built-in `mock` payment provider is deterministic and intended for development. Configure a real provider before production use.

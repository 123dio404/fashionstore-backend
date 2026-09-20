# FashionStore Backend

FastAPI + SQLAlchemy 2.0 backend for CU01-CU24. The API includes authentication and roles, branches and catalog management, variants with GLB/GLTF metadata, multi-branch inventory, cart and payment-provider workflows, POS receipts, fitting-room reservations, purchase history, virtual fitting sessions, personalized recommendations, chatbot conversations, collections, promotions, sales and inventory reports, executive dashboards, and analytical queries.

## Related repositories

| Repositorio | Contenido |
| :-- | :-- |
| `fashionstore-backend` | Esta API (FastAPI + PostgreSQL) |
| `fashionstore-mobile` | App Flutter (CU13 y CU17 son mobile-only) |
| `fashionstore-web` | Cliente Angular 20 (22 CU) |
| `fashionstore-design` | Diseño: sistema de diseño, tokens, logo y prototipos navegables de Figma (local: `../design`) |

El diseño es el **titular** de cómo se ve cada pantalla: si el prototipo muestra un dato que la API
todavía no expone, se agrega al backlog del backend (ver `design/DESIGN.md`).

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

The backend only supports **PostgreSQL**: `app/core/database.py` raises if `DATABASE_URL` is not a
`postgresql://` URL. The default URL points to the database of the bundled `docker-compose.yml`
(port 5433):

```bash
docker compose up -d      # PostgreSQL 16 + pgAdmin
alembic upgrade head      # crear/actualizar el esquema
uvicorn main:app --reload
```

Set these variables in the environment for deployment:

```dotenv
DATABASE_URL=postgresql+psycopg2://fashionstore:fashionstore@localhost:5433/fashionstore
SECRET_KEY=replace-me
ACCESS_TOKEN_EXPIRE_MINUTES=60
AI_PROVIDER_MODE=disabled
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
SPEECH_PROVIDER_MODE=disabled
GOOGLE_SPEECH_API_KEY=
GOOGLE_SPEECH_LANGUAGE_CODE=es-CO
```

Set `AI_PROVIDER_MODE=gemini` to enable Gemini for CU18 recommendations, CU19 chatbot,
and CU24 analytical-query interpretation. Set `SPEECH_PROVIDER_MODE=google` to enable
`POST /api/v1/reports/analytical-query/voice` (multipart field `audio`). Missing credentials
or upstream failures return explicit errors; deterministic behavior is used only while the
corresponding provider mode is `disabled`. Never commit credentials.

For migrations:

```bash
alembic upgrade head
```

Interactive API documentation is available at `/docs`.

## Deployment

Production runs **only on PostgreSQL** and ships with containers: `Dockerfile`,
`docker-entrypoint.sh` (applies `alembic upgrade head` before starting uvicorn) and
`docker-compose.deploy.yml` (Postgres 16 + API with healthchecks). See **[DEPLOY.md](./DEPLOY.md)** for
the server and PaaS recipes, the required environment variables and how to create the first
administrator (`python -m scripts.create_admin ...`).

## Actors and authorization

- **CL**: `Cliente`, the end user who registers, shops, reserves, reviews purchases, uses the virtual fitting room, recommendations, and chatbot.
- **AD**: `Administrador`, with platform-wide management and reporting permissions.
- **ES**: `Encargado`, responsible for branch operations, inventory, reservations, suppliers, and sales reports.
- **CA**: `Cajero`, responsible for POS sales and in-store reservation handling.
- **PR**: `Proveedor`, supported as an authenticated profile; supplier catalog operations remain controlled by AD/ES.
- **PP**: payment provider abstraction (`mock` in development).
- **IA**: Gemini adapter for recommendations, chatbot, and analytical-query interpretation, with an explicit disabled-mode fallback.

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
  CU18 exposes `GET/PUT /recommendations/preferences`, `POST /recommendations` (alias
  `/recommendations/generate`), `GET /recommendations` (history with `estado`) and
  `PATCH /recommendations/{id}` to mark it `pendiente`, `visto` or `descartado`.
- `/api/v1/collections`, `/api/v1/promotions`: CU20.
- `/api/v1/reports`: CU16 and CU21-CU24.

The built-in `mock` payment provider is deterministic and intended for development. Configure a real provider before production use.

## Integraciones externas y configuración

- Pagos: `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` y opcionalmente `STRIPE_API_BASE`. El checkout crea PaymentIntents con `Idempotency-Key`; el webhook es `/api/v1/commerce/payments/stripe/webhook` y verifica firma. `mock` solo se acepta en `development`/`test`.
- Facturación fiscal: `FISCAL_PROVIDER=not_configured` por defecto. `POST /api/v1/commerce/sales/{id}/invoice` devuelve explícitamente 503 hasta conectar un proveedor; los recibos internos no son facturas fiscales.
- Notificaciones: `NOTIFICATION_PROVIDER=not_configured` por defecto. `POST /api/v1/commerce/sales/{id}/notifications` devuelve 503 hasta conectar un proveedor; no se afirma entrega.
- Voz: `SPEECH_PROVIDER_MODE` y `GOOGLE_SPEECH_API_KEY` son opcionales. AR móvil usa modelos `.glb`/`.gltf` mediante ARCore/ARKit; no implementa try-on corporal avanzado.

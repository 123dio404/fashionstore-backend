# Despliegue del backend

Dos caminos: **Docker Compose en un servidor** (recomendado, incluye base de datos) o un
**PaaS** (Render/Railway/Fly) con Postgres gestionado. El backend **solo funciona con PostgreSQL**.

## Opción A — Servidor con Docker (recomendado)

Requisitos: servidor Linux con Docker y Docker Compose, puerto 8000 accesible (o detrás de Nginx).

```bash
git clone https://github.com/123dio404/fashionstore-backend.git
cd fashionstore-backend

cp .env.example .env
# Edita .env:
#   SECRET_KEY        → python -c "import secrets; print(secrets.token_urlsafe(48))"
#   POSTGRES_PASSWORD → una clave real
#   CORS_ORIGINS      → ["https://tu-frontend.com"]
#   DATABASE_URL      → lo sobrescribe el compose (host `db`), no hace falta tocarlo

docker compose -f docker-compose.deploy.yml up -d --build
```

Qué hace el compose de despliegue:

1. Levanta **Postgres 16** con volumen persistente (`pgdata`).
2. Construye la imagen de la API (`Dockerfile`) y espera a que la base esté sana.
3. El contenedor de la API ejecuta `alembic upgrade head` y luego `uvicorn` en el puerto 8000.

Verificación:

```bash
curl http://localhost:8000/health          # {"status":"ok"}
curl http://localhost:8000/docs            # documentación interactiva
```

> **No se monta `db/init.sql`**: ese archivo es la referencia del diccionario de datos del
> documento. El esquema real lo crea Alembic; montarlo provocaría tablas duplicadas.

### Primer administrador (obligatorio: sin él no hay gestión)

```bash
docker compose -f docker-compose.deploy.yml exec api \
  python -m scripts.create_admin --email admin@tudominio.com --password 'ClaveSegura123' --name 'Administrador'
```

Luego entra en la web con ese correo: verás el menú de Administrador completo
(usuarios, catálogo, inventario, sucursales, proveedores, parámetros, promociones, informes).

### Datos de catálogo

La base arranca **vacía**: crea categorías, tallas, colores, temporadas, sucursales y prendas desde
la propia web (`/admin/parameters`, `/admin/branches`, `/admin/products`) y carga stock en
`/admin/inventory`. Un *seeder* con datos de demostración está en el backlog del diseño.

### HTTPS y dominio

Coloca Nginx o Caddy delante del puerto 8000 (ejemplo con Caddy: `api.tudominio.com { reverse_proxy 127.0.0.1:8000 }`)
y recuerda agregar ese dominio a `CORS_ORIGINS`. El contenedor ya arranca uvicorn con
`--proxy-headers`, así que respeta `X-Forwarded-*`.

## Opción B — PaaS (Render / Railway / Fly.io)

| Ajuste | Valor |
| :-- | :-- |
| Build | `pip install -r requirements.txt` |
| Start | `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |
| Variables | las de `.env.example` (con `DATABASE_URL` del Postgres gestionado y `ENVIRONMENT=production`) |

Con el `Dockerfile` incluido también puedes desplegar directo en Fly.io o en un servicio que
construya imágenes.

## Variables que importan en producción

| Variable | Por qué |
| :-- | :-- |
| `DATABASE_URL` | El backend **rechaza** cualquier URL que no sea `postgresql://` |
| `SECRET_KEY` | Firma los JWT; sin cambiarla los tokens son falsificables |
| `CORS_ORIGINS` | Debe incluir el dominio del front o el navegador bloqueará las llamadas |
| `ENVIRONMENT=production` | Evita `create_all` y deja el esquema solo en manos de Alembic |
| `PAYMENT_PROVIDER` / `STRIPE_SECRET_KEY` | Sin claves, el checkout (CU11) falla con error explícito |
| `AI_PROVIDER_MODE` / `SPEECH_PROVIDER_MODE` | `disabled` = respuestas deterministas; `gemini`/`google` requieren claves |

## Actualizar una versión desplegada

```bash
git pull
docker compose -f docker-compose.deploy.yml up -d --build   # reaplica migraciones al arrancar
```

## Copias de seguridad

```bash
docker compose -f docker-compose.deploy.yml exec db \
  pg_dump -U fashionstore fashionstore > respaldo_$(date +%F).sql
```

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
3. El contenedor de la API crea el esquema desde los modelos
   (`scripts/init_schema.py`: `Base.metadata.create_all` + `alembic stamp head`)
   y luego levanta `uvicorn` en el puerto 8000.

Verificación:

```bash
curl http://localhost:8000/health          # {"status":"ok"}
curl http://localhost:8000/docs            # documentación interactiva
```

> **No se monta `db/init.sql`**: ese archivo es la referencia del diccionario de datos del
> documento. El esquema real se crea desde los **modelos** del backend (`create_all`);
> montarlo o correr la cadena histórica de Alembic provocaría tablas duplicadas o fallos
> (esa cadena mezcla tablas en inglés y en español).

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

## Opción B — Railway (API + PostgreSQL gestionado) ⭐

Railway construye la imagen con el `Dockerfile` del repo y te da HTTPS y dominio público sin
configurar nada. Pasos:

1. **New Project → Deploy from GitHub repo** → `fashionstore-backend`. Railway detecta el
   `Dockerfile` y lo usa como builder (si no, en *Settings → Build → Builder* elige **Dockerfile**).
2. **+ New → Database → PostgreSQL** (queda como servicio aparte dentro del mismo proyecto).
3. En el servicio de la **API** → *Variables* → agrega:

   | Variable | Valor |
   | :-- | :-- |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referencia al servicio de la base) |
   | `SECRET_KEY` | un valor propio: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `ENVIRONMENT` | `production` |
   | `CORS_ORIGINS` | `["https://tu-web.vercel.app"]` ← **JSON**, entre corchetes y comillas |
   | `PAYMENT_PROVIDER` | `stripe` (o `not_configured` para la demo sin cobro) |
   | `AI_PROVIDER_MODE` | `disabled` (o `gemini` + `GEMINI_API_KEY`) |
   | `SPEECH_PROVIDER_MODE` | `disabled` (o `google` + `GOOGLE_SPEECH_API_KEY`) |

   No hace falta definir `PORT`: Railway lo inyecta y el `docker-entrypoint.sh` lo respeta.
   Tampoco `RUN_MIGRATIONS`: por defecto es `1`, así que **el esquema se inicializa solo**
   en cada despliegue, antes de arrancar uvicorn.
4. **Settings → Networking → Generate Domain** → obtienes algo como
   `https://fashionstore-backend-production.up.railway.app`. Esa es la URL base de la API:
   `.../api/v1`.
5. **Settings → Deploy → Healthcheck Path**: `/health`.
6. Verifica: `curl https://<tu-dominio>/health` → `{"status":"ok"}` y `https://<tu-dominio>/docs`.

### Primer administrador en Railway

El script necesita llegar a la base, y la URL privada de Railway solo funciona dentro de la red del
proyecto. Dos formas:

**a) Desde tu máquina con la URL pública** (recomendado):

```bash
# Copia DATABASE_PUBLIC_URL desde el servicio Postgres → Variables
cd fashionstore-backend
source .venv/bin/activate
DATABASE_URL="postgresql+psycopg2://postgres:<clave>@<host>.railway.app:<puerto>/railway" \
  python -m scripts.create_admin --email admin@tudominio.com --password 'ClaveSegura123' --name 'Administrador'
```

**b) Por SQL** (Postgres → *Data* → *Query*), generando el hash de la contraseña con
`python -c "from app.core.security import get_password_hash; print(get_password_hash('ClaveSegura123'))"`:

```sql
INSERT INTO rol (nombre) VALUES ('Administrador') ON CONFLICT (nombre) DO NOTHING;
INSERT INTO usuario (nombre, email, password, estado)
VALUES ('Administrador', 'admin@tudominio.com', '<hash-bcrypt>', TRUE);
INSERT INTO usuario_rol (id_usuario, id_rol)
SELECT u.id, r.id FROM usuario u, rol r
WHERE u.email = 'admin@tudominio.com' AND r.nombre = 'Administrador';
```

### Actualizar en Railway

Cada `git push` a la rama conectada redespliega. Ojo: la base **no se resetea** (Railway mantiene el
volumen), y el `git pull` no hace falta porque Railway construye desde GitHub.

## Opción C — Otros PaaS (Render / Fly.io)

Mismos ajustes que Railway:

| Ajuste | Valor |
| :-- | :-- |
| Builder | Dockerfile (o `pip install -r requirements.txt`) |
| Start | `python -m scripts.init_schema && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |
| Variables | las de `.env.example`, con `DATABASE_URL` del Postgres gestionado y `ENVIRONMENT=production` |

### Render con Blueprint (recomendado)

El repo incluye `render.yaml`: crea **en un mismo proyecto** el Web Service de la API
(`Dockerfile`) y su **PostgreSQL gestionado**, conectados automáticamente.

1. **Render → New → Blueprint** → conecta el repo `123dio404/fashionstore-backend`.
   Render detecta `render.yaml`, crea la base y el servicio, y despliega.
2. La variable `DATABASE_URL` se inyecta sola desde el Postgres (Render la entrega como
   `postgres://...`; el backend la normaliza a `postgresql+psycopg2://`). `SECRET_KEY` se
   genera aleatoriamente y `CORS_ORIGINS` ya incluye `https://fashionstore-web-eight.vercel.app`.
3. El `Dockerfile` aplica migraciones al arrancar (`docker-entrypoint.sh`), así que con el primer
   deploy el esquema queda listo. Verifica: `curl https://<tu-servicio>.onrender.com/health`.
4. **Primer administrador** (sin él no hay gestión): genera el hash y crea el usuario desde
   **Postgres → Data → Query** (la base de Render no expone `exec`):

   ```bash
   # en tu máquina
   source .venv/bin/activate
   python -c "from app.core.security import get_password_hash; print(get_password_hash('ClaveSegura123'))"
   ```

   ```sql
   INSERT INTO rol (nombre) VALUES ('Administrador') ON CONFLICT (nombre) DO NOTHING;
   INSERT INTO usuario (nombre, email, password, estado)
   VALUES ('Administrador', 'admin@tudominio.com', '<hash-bcrypt>', TRUE);
   INSERT INTO usuario_rol (id_usuario, id_rol)
   SELECT u.id, r.id FROM usuario u, rol r
   WHERE u.email = 'admin@tudominio.com' AND r.nombre = 'Administrador';
   ```

5. Cada `git push` a la rama conectada redespliega; la base **no se resetea**.
   Para cambiar Stripe/IA edita la variable en el dashboard del servicio.

## Variables que importan en producción

| Variable | Por qué |
| :-- | :-- |
| `DATABASE_URL` | El backend **rechaza** cualquier URL que no sea `postgresql://` |
| `SECRET_KEY` | Firma los JWT; sin cambiarla los tokens son falsificables |
| `CORS_ORIGINS` | Debe incluir el dominio del front o el navegador bloqueará las llamadas |
| `ENVIRONMENT=production` | Evita que la app cree el esquema con `create_all` en cada arranque (en despliegue lo hace el entrypoint/Start command) |
| `PAYMENT_PROVIDER` / `STRIPE_SECRET_KEY` | Sin claves, el checkout (CU11) falla con error explícito |
| `AI_PROVIDER_MODE` / `SPEECH_PROVIDER_MODE` | `disabled` = respuestas deterministas; `gemini`/`google` requieren claves |

## Actualizar una versión desplegada

```bash
git pull
docker compose -f docker-compose.deploy.yml up -d --build   # reaplica migraciones al arrancar
```

## La app móvil (Flutter) no va en Railway ni en Vercel

Railway/Vercel alojan servicios web; la app Flutter se **compila y distribuye**:

```bash
cd fashionstore-mobile
flutter build apk --release --dart-define=API_BASE_URL=https://<tu-api>/api/v1
# o para Play Store:
flutter build appbundle --release --dart-define=API_BASE_URL=https://<tu-api>/api/v1
```

- El APK/AAB queda en `build/app/outputs/` y se instala o se sube a Play Console / Firebase App
  Distribution.
- La URL de la API se inyecta en tiempo de compilación con `--dart-define`; si cambias de backend hay
  que **recompilar** (no se puede cambiar en caliente).
- Recuerda que el móvil usa `http://10.0.2.2:8000/api/v1` para el emulador de Android y que el
  backend debe permitir el origen correspondiente (el móvil nativo no está sujeto a CORS, así que no
  necesita entrar en `CORS_ORIGINS`).

## Copias de seguridad

```bash
docker compose -f docker-compose.deploy.yml exec db \
  pg_dump -U fashionstore fashionstore > respaldo_$(date +%F).sql
```

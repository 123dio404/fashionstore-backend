#!/usr/bin/env sh
# Arranque del contenedor de la API: aplica migraciones y levanta uvicorn.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Aplicando migraciones (alembic upgrade head)"
  alembic upgrade head
fi

echo "==> Arrancando API en el puerto ${PORT:-8000}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'

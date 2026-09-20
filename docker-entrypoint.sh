#!/usr/bin/env sh
# Arranque del contenedor de la API: inicializa el esquema y levanta uvicorn.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Inicializando esquema (scripts/init_schema.py)"
  python -m scripts.init_schema
fi

echo "==> Arrancando API en el puerto ${PORT:-8000}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
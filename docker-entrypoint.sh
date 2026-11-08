#!/usr/bin/env sh
# Arranque del contenedor de la API: inicializa el esquema y levanta uvicorn.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Inicializando esquema (scripts/init_schema.py)"
  python -m scripts.init_schema
fi

# La siembra SaaS es pesada (9 tenants, catálogos y ventas) y no debe bloquear
# el arranque: Render espera /health y, si el seed tarda, el deploy parece
# colgado. Se ejecuta solo cuando se pide explícitamente con RUN_SEED=1.
if [ "${RUN_SEED:-0}" = "1" ]; then
  echo "==> Sembrando/actualizando los 9 tenants SaaS (scripts/seed_saas.py)"
  python -m scripts.seed_saas
fi

echo "==> Arrancando API en el puerto ${PORT:-8000}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
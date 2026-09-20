FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Dependencias del sistema: compilador y cabeceras para psycopg2, curl para el healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencias de Python primero: mejor caché de capas.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código y migraciones
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY main.py ./
COPY scripts ./scripts
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]

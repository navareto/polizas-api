# syntax=docker/dockerfile:1
# Etapa 1: instala las dependencias en un entorno virtual aislado.
FROM python:3.11.9-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# Etapa 2: la imagen final lleva solo el entorno ya construido y el código del servicio.
FROM python:3.11.9-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/polizas.db

# Usuario sin privilegios; /data es el único sitio donde el servicio escribe (la base SQLite).
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir /data && chown app:app /data

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app main.py config.py database.py modelos.py esquemas.py servicios.py modelo.pkl alembic.ini ./
COPY --chown=app:app alembic ./alembic

USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Aplica las migraciones sobre la base de /data y arranca escuchando en todas las interfaces (sin --reload).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]

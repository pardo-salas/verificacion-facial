# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Imagen de la API de verificación facial (FastAPI + OpenCV YuNet/SFace)
# Etapas:
#   base    -> dependencias, modelos ONNX validados y código de la app
#   test    -> base + pytest; ejecuta las pruebas automatizadas
#   runtime -> imagen final, usuario sin privilegios (etapa por defecto)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MODELS_DIR=/app/models

WORKDIR /app

# libglib2.0-0 es la única librería de sistema que necesita opencv-headless
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 1) Dependencias (se cachean mientras requirements.txt no cambie)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2) Modelos preentrenados: se descargan y validan en tiempo de construcción
COPY scripts/descargar_modelos.py scripts/
RUN python scripts/descargar_modelos.py --destino ${MODELS_DIR}

# 3) Código de la aplicación
COPY app/ app/

# ---------------------------------------------------------------------------
FROM base AS test
COPY requirements-dev.txt pytest.ini ./
RUN pip install -r requirements-dev.txt
COPY tests/ tests/
COPY scripts/ scripts/
CMD ["pytest", "-v"]

# ---------------------------------------------------------------------------
FROM base AS runtime
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "app.healthcheck"]

# PORT lo define el proveedor de nube (Render, Cloud Run); localmente usa 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

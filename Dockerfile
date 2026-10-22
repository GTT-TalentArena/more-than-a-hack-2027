# Entorno común de GTT: Python + dependencias fijadas. La imagen NO lleva código ni datos:
# compose.yaml monta el repo en solo lectura, los datos del partido en solo lectura y ./salidas.
# Guía: docs/DOCKER.md
FROM python:3.11.17-slim@sha256:cce12316475d7d56d605f76e1d811d0dc4e7227f2d4afd29951521264f504ff8

# Sin .pyc en el repo montado y un solo hilo en BLAS: mismos números en cualquier máquina
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    HOME=/tmp

# git solo para registrar el commit y si hay cambios sin commitear en cada ejecución
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /app

COPY docker/requirements.lock /tmp/requirements.lock
RUN pip install --root-user-action=ignore -r /tmp/requirements.lock

WORKDIR /app
ENTRYPOINT ["python", "docker/pipeline.py"]
CMD ["--help"]

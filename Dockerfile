# GTT common environment: Python + pinned dependencies. The image carries NO code or data:
# compose.yaml mounts the repo read-only, the match data read-only, and ./salidas.
# Guide: docs/DOCKER.md
FROM python:3.11.17-slim@sha256:cce12316475d7d56d605f76e1d811d0dc4e7227f2d4afd29951521264f504ff8

# No .pyc in the mounted repo and a single BLAS thread: the same numbers on any machine
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    HOME=/tmp

# git only to record the commit, and whether there are uncommitted changes, on each run
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /app

COPY docker/requirements.lock /tmp/requirements.lock
RUN pip install --root-user-action=ignore -r /tmp/requirements.lock

WORKDIR /app
ENTRYPOINT ["python", "docker/pipeline.py"]
CMD ["--help"]

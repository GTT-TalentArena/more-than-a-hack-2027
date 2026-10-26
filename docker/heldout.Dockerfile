# Held-out harness (issue #47): the project's environment plus kloppy to read the DFL open data.
# Same pinned base and the same numpy/pandas as the main Dockerfile, so the models run on the same
# numerical stack. Like the main image, it carries no code and no data: both are mounted.
FROM python:3.11.17-slim@sha256:cce12316475d7d56d605f76e1d811d0dc4e7227f2d4afd29951521264f504ff8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /app

COPY docker/heldout.lock /tmp/heldout.lock
RUN pip install --root-user-action=ignore -r /tmp/heldout.lock

WORKDIR /app
ENTRYPOINT ["python", "-m", "heldout"]
CMD ["--help"]

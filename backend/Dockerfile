FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    EMBEDDING_CACHE_DIR=/opt/models

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /opt/models \
    && chown appuser /app /opt/models

COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-download the embedding model so the first upload does not wait for ~470 MB (ADR-02)
COPY --chown=appuser app/retrieval/embed.py /tmp/embed.py
USER appuser
RUN python /tmp/embed.py --download /opt/models

COPY --chown=appuser alembic.ini pyproject.toml entrypoint.sh ./
COPY --chown=appuser alembic ./alembic
COPY --chown=appuser app ./app

EXPOSE 8000

# --- production image ---
FROM base AS prod
CMD ["sh", "/app/entrypoint.sh"]

# --- development image: dev tools + tests ---
FROM base AS dev
USER root
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
USER appuser
COPY --chown=appuser tests ./tests
CMD ["sh", "/app/entrypoint.sh", "--reload"]

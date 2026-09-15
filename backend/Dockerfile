FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini pyproject.toml entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# --- production image ---
FROM base AS prod
CMD ["sh", "/app/entrypoint.sh"]

# --- development image: dev tools + tests ---
FROM base AS dev
USER root
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY tests ./tests
RUN chown -R appuser /app
USER appuser
CMD ["sh", "/app/entrypoint.sh", "--reload"]

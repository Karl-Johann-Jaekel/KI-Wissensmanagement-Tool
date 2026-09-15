"""Test setup: dedicated database `<db>_test`, fake access key, no external calls."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_ACCESS_KEY = "test-access-key-123"

_base_url = make_url(os.environ["DATABASE_URL"])
_test_url = _base_url.set(database=f"{_base_url.database}_test")
os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)
os.environ["ACCESS_KEY"] = TEST_ACCESS_KEY
os.environ["MISTRAL_API_KEY"] = "not-used-in-tests"


def _create_test_database() -> None:
    admin = create_engine(_base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _test_url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    from alembic import command
    from alembic.config import Config

    from app.config import get_settings

    get_settings.cache_clear()
    _create_test_database()
    cfg = Config("alembic.ini")
    cfg.attributes["url"] = os.environ["DATABASE_URL"]
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_database: None) -> Iterator[None]:
    yield
    from app.db import get_engine

    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE notebooks, sources, chunks, messages, notes CASCADE"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app, headers={"X-Access-Key": TEST_ACCESS_KEY}) as c:
        yield c
    app.dependency_overrides.clear()

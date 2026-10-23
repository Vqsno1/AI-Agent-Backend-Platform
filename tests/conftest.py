import os

# ruff: noqa: E402 -- configure isolated test settings before importing the app

# Each test resets a dedicated test database. Never use the application DB.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite://")
os.environ["API_KEYS"] = '{"test-alice":"alice", "test-bob":"bob"}'
os.environ["LLM_PROVIDER"] = "mock"
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

get_settings.cache_clear()
import app.services.execution_service as execution
from app.db.models import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def db_factory(monkeypatch):
    url = os.environ["DATABASE_URL"]
    if url != "sqlite://" and not (make_url(url).database or "").endswith("_test"):
        raise ValueError("TEST_DATABASE_URL must use a dedicated database ending in _test")
    options = (
        {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        if url == "sqlite://"
        else {}
    )
    engine = create_engine(url, **options)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(execution, "engine", engine)
    monkeypatch.setattr(execution, "SessionLocal", factory)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api(db_factory, monkeypatch):
    app = create_app()

    def session():
        with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    monkeypatch.setattr("app.main.run_task.apply_async", lambda **kwargs: None)
    with TestClient(app) as client:
        client.headers["X-API-Key"] = "test-alice"
        yield client

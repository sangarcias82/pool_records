from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

# Isolate the test DB before the app modules bind the engine.
TEST_DB = Path(__file__).resolve().parent / "test_aquacontrol.db"
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DEMO_PASSWORD"] = "AquaDemo1!"
os.environ["PBKDF2_ITERATIONS"] = "1000"  # fast hashing for tests only

from app.config import get_settings
from app.db import Base, get_db, reset_engine
from app.main import create_app
from app.models import AppUser, Client
from app.seed import seed_if_empty

get_settings.cache_clear()
reset_engine(os.environ["DATABASE_URL"])

from tests.helpers import ADMIN, PASSWORD, SUPERVISOR, TECH  # noqa: E402


@pytest.fixture()
def db_session():
    from app import db as db_module

    Base.metadata.drop_all(bind=db_module.engine)
    Base.metadata.create_all(bind=db_module.engine)
    session = sessionmaker(bind=db_module.engine, autoflush=False, autocommit=False)()
    seed_if_empty(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session, tmp_path):
    application = create_app(frontend_dist=tmp_path / "no-dist")

    def _override_db():
        yield db_session

    application.dependency_overrides[get_db] = _override_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture()
def login_as(client):
    def _login(email: str, password: str = PASSWORD) -> dict:
        response = client.post("/api/auth/login", json={"login": email, "password": password})
        assert response.status_code == 200, response.text
        return response.json()

    return _login


@pytest.fixture()
def admin(client, login_as):
    login_as(ADMIN)
    return client


@pytest.fixture()
def supervisor(client, login_as):
    login_as(SUPERVISOR)
    return client


@pytest.fixture()
def tech(client, login_as):
    login_as(TECH)
    return client


@pytest.fixture()
def seeded_clients(db_session):
    return db_session.scalars(select(Client).order_by(Client.id)).all()


@pytest.fixture()
def user_by_email(db_session):
    def _get(email: str) -> AppUser:
        return db_session.scalar(select(AppUser).where(AppUser.email == email))

    return _get

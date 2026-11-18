from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine(database_url: str):
    sqlite = database_url.startswith("sqlite")
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if sqlite else {})
    if sqlite:
        event.listen(engine, "connect", lambda conn, _rec: conn.execute("PRAGMA foreign_keys=ON"))
    return engine


engine = _build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app import models  # noqa: F401
    from app.seed import seed_if_empty

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def reset_engine(database_url: str) -> None:
    """Rebuild the global engine/session for tests that need an isolated DB."""
    global engine, SessionLocal
    engine = _build_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

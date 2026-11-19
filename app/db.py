import logging
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import Engine, create_engine, event, inspect
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


# Tables still in pre-release shape: if an existing database has an older layout of one of these, it is renamed
# to ``<table>_legacy_<UTC timestamp>`` (rows kept, never deleted) and rebuilt. Any other outdated table stops
# startup with a clear message instead of failing later with 500s. Remove a table from here once it is stable.
REBUILDABLE_TABLES = frozenset({"measurement"})

log = logging.getLogger(__name__)


class SchemaOutdated(RuntimeError):
    pass


def outdated_tables(bind: Engine) -> dict[str, list[str]]:
    """Existing tables missing columns the models declare -> sorted missing column names."""
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    result = {}
    for name, table in Base.metadata.tables.items():
        if name in existing:
            missing = {c.name for c in table.columns} - {c["name"] for c in inspector.get_columns(name)}
            if missing:
                result[name] = sorted(missing)
    return result


def upgrade_schema(bind: Engine) -> list[str]:
    """Set aside outdated pre-release tables, then create missing tables. Returns the legacy table names."""
    outdated = outdated_tables(bind)
    blocked = {name: cols for name, cols in outdated.items() if name not in REBUILDABLE_TABLES}
    if blocked:
        raise SchemaOutdated(
            f"Database schema is older than the code (missing columns: {blocked}). "
            "Delete the database file to re-create it with demo data, or migrate it by hand."
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    legacy = []
    with bind.begin() as conn:
        for name in sorted(outdated):
            # Named indexes keep their names after a rename and would clash with the rebuilt table's indexes.
            for index in inspect(conn).get_indexes(name):
                conn.exec_driver_sql(f'DROP INDEX "{index["name"]}"')
            conn.exec_driver_sql(f'ALTER TABLE "{name}" RENAME TO "{name}_legacy_{stamp}"')
            legacy.append(f"{name}_legacy_{stamp}")
            log.warning("Table %s had an older layout (missing %s); kept as %s and rebuilt.", name, outdated[name], legacy[-1])
    Base.metadata.create_all(bind=bind)  # creates missing tables only; never alters existing ones
    return legacy


def init_db() -> None:
    from app import models  # noqa: F401
    from app.seed import run_seed

    upgrade_schema(engine)
    with SessionLocal() as db:
        run_seed(db)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def reset_engine(database_url: str) -> None:
    """Rebuild the global engine/session for tests that need an isolated DB."""
    global engine, SessionLocal
    engine = _build_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

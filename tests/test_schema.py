"""Startup schema handling (no migrations): outdated pre-release tables are set aside, others stop startup."""

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db import REBUILDABLE_TABLES, Base, SchemaOutdated, outdated_tables, upgrade_schema

# measurement as created by the previous iteration (record_id / created_by_id, no unit / folio)
OLD_MEASUREMENT = """
CREATE TABLE measurement (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, record_seq INTEGER NOT NULL,
    record_id VARCHAR(20) NOT NULL, pool_id INTEGER NOT NULL, parameter_id INTEGER NOT NULL, value FLOAT NOT NULL,
    measured_at DATETIME NOT NULL, notes VARCHAR(500), created_at DATETIME NOT NULL, created_by_id INTEGER NOT NULL,
    status VARCHAR(12) NOT NULL, direction VARCHAR(4), rule_id INTEGER, rule_min FLOAT, rule_max FLOAT,
    rule_classification VARCHAR(20), UNIQUE (organization_id, record_seq)
)"""


@pytest.fixture()
def engine(tmp_path):
    bind = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    yield bind
    bind.dispose()


def _tables(bind):
    return set(inspect(bind).get_table_names())


def test_fresh_database_gets_every_table(engine):
    assert upgrade_schema(engine) == []
    assert _tables(engine) == set(Base.metadata.tables)
    assert outdated_tables(engine) == {}


def test_old_measurement_table_is_kept_as_legacy_and_rebuilt(engine, caplog):
    Base.metadata.create_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n != "measurement"])
    with engine.begin() as conn:
        conn.exec_driver_sql(OLD_MEASUREMENT)
        conn.exec_driver_sql("CREATE INDEX ix_measurement_pool_id ON measurement (pool_id)")  # same name as the new one
        conn.exec_driver_sql(
            "INSERT INTO measurement VALUES (1, 1, 1, 'MED-000001', 1, 1, 7.4, '2025-01-01', NULL, '2025-01-01', 1,"
            " 'NO_RULE', NULL, NULL, NULL, NULL, NULL)"
        )
    assert "unit" in outdated_tables(engine)["measurement"]

    with caplog.at_level("WARNING"):
        legacy = upgrade_schema(engine)

    assert len(legacy) == 1 and legacy[0].startswith("measurement_legacy_")
    assert "kept as measurement_legacy_" in caplog.text
    assert outdated_tables(engine) == {}
    columns = {c["name"] for c in inspect(engine).get_columns("measurement")}
    assert {"folio", "unit", "recorded_by_id"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text(f'SELECT record_id FROM "{legacy[0]}"')).scalar() == "MED-000001"  # rows kept
        assert conn.execute(text("SELECT count(*) FROM measurement")).scalar() == 0
    assert upgrade_schema(engine) == []  # idempotent once rebuilt


def test_other_outdated_tables_stop_startup_with_a_clear_message(engine):
    assert "pool" not in REBUILDABLE_TABLES
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE pool (id INTEGER PRIMARY KEY, name VARCHAR(160))")
    with pytest.raises(SchemaOutdated, match=r"missing columns: \{'pool': \['client_id'"):
        upgrade_schema(engine)
    assert _tables(engine) == {"pool"}  # nothing was touched


def test_app_startup_rejects_an_unknown_time_zone(monkeypatch, tmp_path):
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "timezone", "Mars/Olympus_Mons")
    with pytest.raises(RuntimeError, match="not an IANA time zone"):
        create_app(frontend_dist=tmp_path)

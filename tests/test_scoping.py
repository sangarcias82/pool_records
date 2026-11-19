"""Organization scoping helpers (R2): one place that decides whether a row belongs to the caller."""

import pytest
from sqlalchemy import select

from app.models import Client, Organization, Pool, WaterParameter
from app.services.scoping import get_owned, scoped_select
from app.utils import BusinessError


@pytest.fixture()
def foreign_client(db_session):
    other = Organization(name="Other", slug="other")
    db_session.add(other)
    db_session.flush()
    row = Client(organization_id=other.id, name="Foreign")
    db_session.add(row)
    db_session.commit()
    return row


def test_get_owned_returns_rows_of_the_organization(db_session, seeded_clients):
    mine = seeded_clients[0]
    assert get_owned(db_session, Client, mine.organization_id, mine.id) is mine


def test_missing_rows_are_not_found(db_session):
    with pytest.raises(BusinessError) as info:
        get_owned(db_session, Client, 1, 9999)
    assert info.value.key == "err.not_found"


def test_foreign_rows_look_exactly_like_missing_ones(db_session, foreign_client):
    with pytest.raises(BusinessError) as info:
        get_owned(db_session, Client, 1, foreign_client.id)
    assert info.value.key == "err.not_found" and info.value.params == {}


def test_scoped_select_filters_by_organization(db_session, foreign_client):
    mine = db_session.scalars(scoped_select(Client, 1)).all()
    theirs = db_session.scalars(scoped_select(Client, foreign_client.organization_id)).all()
    assert {c.name for c in mine} == {"Club Deportivo Las Palmas", "Hotel Brisa Marina"}
    assert [c.name for c in theirs] == ["Foreign"]
    assert db_session.scalars(scoped_select(Pool, foreign_client.organization_id)).all() == []


def test_global_models_are_rejected(db_session):
    with pytest.raises(TypeError, match="WaterParameter is not organization-scoped"):
        scoped_select(WaterParameter, 1)
    ph_id = db_session.scalar(select(WaterParameter.id).where(WaterParameter.code == "PH"))
    with pytest.raises(TypeError):
        get_owned(db_session, WaterParameter, 1, ph_id)


def test_foreign_pool_is_404_through_the_api(admin, db_session, foreign_client):
    pool = Pool(organization_id=foreign_client.organization_id, client_id=foreign_client.id, name="P", volume_liters=10)
    db_session.add(pool)
    db_session.commit()
    assert admin.get(f"/api/pools/{pool.id}").status_code == 404
    assert admin.post(f"/api/clients/{foreign_client.id}/pools", json={"name": "X", "volume_liters": 5}).status_code == 404
    assert pool.id not in {p["id"] for p in admin.get("/api/pools").json()}

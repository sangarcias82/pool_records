from sqlalchemy import select

from app.models import Client


def test_list_shows_seeded_clients_with_pool_counts(admin):
    rows = {c["name"]: c for c in admin.get("/api/clients").json()}
    assert set(rows) == {"Club Deportivo Las Palmas", "Hotel Brisa Marina"}
    assert rows["Club Deportivo Las Palmas"]["pool_count"] == 1


def test_create_client(admin, db_session):
    response = admin.post("/api/clients", json={"name": "Residencial Los Pinos", "email": "ANA@pinos.example"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@pinos.example"
    created = db_session.scalar(select(Client).where(Client.name == "Residencial Los Pinos"))
    assert created.organization_id == 1 and created.id == body["id"]
    assert admin.get(f"/api/clients/{body['id']}").json()["pools"] == []


def test_create_requires_name_and_valid_email(admin):
    response = admin.post("/api/clients", json={"name": "  "})
    assert response.status_code == 422 and response.json()["key"] == "err.client_name"
    response = admin.post("/api/clients", json={"name": "X", "email": "not-an-email"})
    assert response.status_code == 422 and response.json()["key"] == "err.email"


def test_detail_includes_pools(admin, seeded_clients):
    body = admin.get(f"/api/clients/{seeded_clients[0].id}").json()
    assert [p["name"] for p in body["pools"]] == ["Semiolímpica"]


def test_missing_client_is_404(admin):
    assert admin.get("/api/clients/9999").status_code == 404


def test_other_organization_is_hidden(admin, db_session):
    from app.models import Organization

    other = Organization(name="Other", slug="other")
    db_session.add(other)
    db_session.flush()
    foreign = Client(organization_id=other.id, name="Foreign")
    db_session.add(foreign)
    db_session.commit()
    assert admin.get(f"/api/clients/{foreign.id}").status_code == 404
    assert "Foreign" not in {c["name"] for c in admin.get("/api/clients").json()}

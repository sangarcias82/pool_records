def test_list_and_filter_by_client(admin, seeded_clients):
    assert len(admin.get("/api/pools").json()) == 2
    rows = admin.get("/api/pools", params={"client_id": seeded_clients[1].id}).json()
    assert [p["name"] for p in rows] == ["Alberca infantil"]
    assert rows[0]["client_name"] == "Hotel Brisa Marina" and rows[0]["environment"] == "INDOOR"


def test_create_pool_under_client(supervisor, seeded_clients):
    cid = seeded_clients[0].id
    response = supervisor.post(f"/api/clients/{cid}/pools", json={"name": "Jacuzzi", "volume_liters": "2500,5", "environment": "indoor"})
    assert response.status_code == 201
    body = response.json()
    assert body["volume_liters"] == 2500.5 and body["environment"] == "INDOOR" and body["client_id"] == cid
    assert supervisor.get(f"/api/pools/{body['id']}").json()["name"] == "Jacuzzi"


def test_pool_validation(admin, seeded_clients):
    url = f"/api/clients/{seeded_clients[0].id}/pools"
    cases = [
        ({"name": " ", "volume_liters": 10}, "err.pool_name"),
        ({"name": "A"}, "err.volume"),
        ({"name": "A", "volume_liters": 0}, "err.volume"),
        ({"name": "A", "volume_liters": "abc"}, "err.number"),
        ({"name": "A", "volume_liters": 10, "environment": "MOON"}, "err.environment"),
    ]
    for payload, key in cases:
        response = admin.post(url, json=payload)
        assert response.status_code == 422 and response.json()["key"] == key, payload


def test_pool_for_missing_client_is_404(admin):
    assert admin.post("/api/clients/9999/pools", json={"name": "A", "volume_liters": 10}).status_code == 404
    assert admin.get("/api/pools/9999").status_code == 404


def test_technician_can_read_but_not_create(tech, seeded_clients):
    assert tech.get("/api/pools").status_code == 200
    assert tech.post(f"/api/clients/{seeded_clients[0].id}/pools", json={"name": "A", "volume_liters": 10}).status_code == 403

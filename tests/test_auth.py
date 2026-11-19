from sqlalchemy import select

from app.auth import hash_password, verify_password
from app.models import AppUser, UserCredential
from tests.helpers import ADMIN, PASSWORD, SUPERVISOR, TECH


def test_login_returns_user_with_capabilities(client):
    response = client.post("/api/auth/login", json={"login": ADMIN, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == ADMIN and body["role"] == "ORG_ADMIN"
    assert body["organization"]["name"] == "Laguna Azul Servicios"
    assert body["can"] == {"manage_clients": True, "manage_norm_rules": True, "capture_measurements": True}
    assert "password_hash" not in body and PASSWORD not in str(body)
    assert "aquacontrol_session" in response.cookies


def test_login_each_demo_role_and_me(client, login_as, user_by_email):
    expected = {
        ADMIN: ("ORG_ADMIN", True),
        SUPERVISOR: ("SUPERVISOR", True),
        TECH: ("TECHNICIAN", False),
    }
    for email, (role, manager) in expected.items():
        login_as(email)
        me = client.get("/api/auth/me").json()
        assert me["role"] == role == user_by_email(email).role
        assert me["can"]["manage_clients"] is manager
        client.post("/api/auth/logout")


def test_login_is_case_insensitive_on_email(client, login_as):
    login_as(ADMIN.upper())
    assert client.get("/api/auth/me").status_code == 200


def test_bad_password_and_unknown_user_share_message(client):
    messages = set()
    for email, password in ((ADMIN, "wrong"), ("nobody@example.com", PASSWORD), ("", ""), (ADMIN, "")):
        response = client.post("/api/auth/login", json={"login": email, "password": password})
        assert response.status_code == 401
        messages.add(response.json()["detail"])
    assert messages == {"Invalid credentials."}
    assert client.get("/api/auth/me").status_code == 401


def test_inactive_user_cannot_login(client, db_session, user_by_email):
    user_by_email(TECH).active = False
    db_session.commit()
    assert client.post("/api/auth/login", json={"login": TECH, "password": PASSWORD}).status_code == 401


def test_inactive_user_loses_existing_session(client, login_as, db_session, user_by_email):
    login_as(TECH)
    user_by_email(TECH).active = False
    db_session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_session(client, login_as):
    login_as(ADMIN)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/clients").status_code == 401


def test_login_requires_a_json_body_shape(client):
    assert client.post("/api/auth/login", json={"login": 5}).status_code == 422
    assert client.post("/api/auth/login", content="nope", headers={"Content-Type": "application/json"}).status_code == 422


def test_password_hash_only_in_credential_table(db_session):
    assert not hasattr(AppUser, "password_hash")
    creds = db_session.scalars(select(UserCredential)).all()
    assert len(creds) == 3
    for cred in creds:
        assert cred.password_hash.startswith("pbkdf2_sha256$")
        assert PASSWORD not in cred.password_hash
    assert len({c.password_hash for c in creds}) == 3  # unique salts


def test_hash_and_verify_roundtrip():
    stored = hash_password("S3cret!", iterations=1000)
    assert verify_password("S3cret!", stored)
    assert not verify_password("other", stored)
    assert not verify_password("S3cret!", "not-a-hash")


def test_language_is_stored_in_the_session(client, login_as):
    login_as(ADMIN)
    assert client.get("/api/auth/me").json()["lang"] == "en"
    assert client.post("/api/lang", json={"lang": "es"}).json() == {"lang": "es"}
    assert client.get("/api/auth/me").json()["lang"] == "es"
    assert client.get("/api/clients/9999").json()["detail"] == "Registro no encontrado."
    client.post("/api/lang", json={"lang": "en"})
    assert client.get("/api/clients/9999").json()["detail"] == "Record not found."


def test_unknown_language_falls_back_to_english(client, login_as):
    login_as(ADMIN)
    assert client.post("/api/lang", json={"lang": "fr"}).json() == {"lang": "en"}


def test_accept_language_header_is_used_until_a_choice_is_stored(client, login_as):
    login_as(ADMIN)
    response = client.get("/api/clients/9999", headers={"Accept-Language": "es-MX,es;q=0.9,en;q=0.5"})
    assert response.json()["detail"] == "Registro no encontrado."
    response = client.get("/api/clients/9999", headers={"Accept-Language": "fr-FR"})
    assert response.json()["detail"] == "Record not found."
    client.post("/api/lang", json={"lang": "en"})
    response = client.get("/api/clients/9999", headers={"Accept-Language": "es"})
    assert response.json()["detail"] == "Record not found."  # stored choice wins


def test_login_can_set_the_language(client):
    response = client.post("/api/auth/login", json={"login": ADMIN, "password": PASSWORD, "lang": "es"})
    assert response.json()["lang"] == "es"
    bad = client.post("/api/auth/login", json={"login": ADMIN, "password": "x", "lang": "es"})
    assert bad.json()["detail"] == "Credenciales inválidas."


def test_technician_blocked_from_creating_clients(tech):
    response = tech.post("/api/clients", json={"name": "Nope"})
    assert response.status_code == 403 and response.json()["key"] == "forbidden"


def test_supervisor_can_create_clients(client, login_as):
    login_as(SUPERVISOR)
    assert client.post("/api/clients", json={"name": "Hecho por supervisor"}).status_code == 201


# --- Capability map (R3) ---------------------------------------------------------------------------------


def test_me_flags_mirror_the_capability_map(client, login_as):
    from app.models import CAPABILITIES

    for email, role in ((ADMIN, "ORG_ADMIN"), (SUPERVISOR, "SUPERVISOR"), (TECH, "TECHNICIAN")):
        login_as(email)
        expected = {name: role in roles for name, roles in CAPABILITIES.items()}
        assert client.get("/api/auth/me").json()["can"] == expected
        client.post("/api/auth/logout")


def test_every_capability_names_known_roles():
    from app.models import CAPABILITIES, ROLES

    for name, roles in CAPABILITIES.items():
        assert roles and roles <= set(ROLES), name


def test_unknown_capability_fails_fast():
    import pytest

    from app.auth import require_capability

    with pytest.raises(ValueError, match="Unknown capability 'manage_everything'"):
        require_capability("manage_everything")


def test_user_can_rejects_unknown_capability(user_by_email):
    import pytest

    admin_user = user_by_email(ADMIN)
    assert admin_user.can("manage_clients") is True
    assert user_by_email(TECH).can("manage_clients") is False
    with pytest.raises(KeyError):
        admin_user.can("typo")

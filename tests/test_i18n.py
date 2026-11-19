"""Internationalization guards: server dictionaries, translated error responses, and SPA labels for backend enums.

The SPA side (keys used in the code exist, EN/ES parity) is tested by frontend/src/i18n/*.test.ts.
"""

import re
from pathlib import Path

import pytest

from app.i18n import EN, ES, t
from app.models import CLASSIFICATIONS, DIRECTION_HIGH, DIRECTION_LOW, ENVIRONMENTS, STATUSES
from app.seed import PARAMETER_CATALOG

ROOT = Path(__file__).resolve().parent.parent
# Same text in both languages on purpose (proper names, symbols, placeholders only).
SAME_IN_BOTH = {"param.PH"}
SPA_SAME_IN_BOTH = {
    "brand.name", "param.PH", "field.folio", "rules.editedBy",
}


def _spa_dictionary(lang: str) -> dict[str, str]:
    text = (ROOT / "frontend" / "src" / "i18n" / f"{lang}.ts").read_text(encoding="utf-8")
    return dict(re.findall(r'^\s*"([^"]+)":\s*"((?:[^"\\]|\\.)*)",\s*$', text, re.M))


SPA_EN, SPA_ES = _spa_dictionary("en"), _spa_dictionary("es")


# --- server ------------------------------------------------------------------------------------------------


def test_server_dictionaries_have_the_same_keys_and_placeholders():
    assert set(EN) == set(ES)
    for key in EN:
        assert set(re.findall(r"\{(\w+)\}", EN[key])) == set(re.findall(r"\{(\w+)\}", ES[key])), key


def test_spanish_server_texts_are_translated():
    assert sorted(k for k in EN if EN[k] == ES[k] and k not in SAME_IN_BOTH) == []


def test_every_error_key_used_by_the_code_exists():
    used = set()
    for path in (ROOT / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'(?:BusinessError|Forbidden|Unauthenticated)\(\s*"([^"]+)"', source))
    assert used and used <= set(EN)


def test_every_catalog_parameter_has_a_server_name():
    for spec in PARAMETER_CATALOG:
        assert f"param.{spec.code}" in EN and f"param.{spec.code}" in ES, spec.code


@pytest.mark.parametrize(
    ("lang", "expected"),
    [("en", "25 is outside the possible range of free chlorine."), ("es", "25 está fuera del rango posible de cloro libre.")],
)
def test_parameter_names_inside_messages_follow_the_language(admin, lang, expected):
    admin.post("/api/lang", json={"lang": lang})
    response = admin.post("/api/measurements", json={"pool_id": 1, "parameter_id": 2, "value": 25})
    assert response.json() == {"detail": expected, "key": "err.rule_range"}


def test_unknown_dictionary_entry_falls_back_to_the_catalog_name(admin, db_session):
    from app.models import WaterParameter

    db_session.add(WaterParameter(code="ORP", name="ORP", physical_min=0, physical_max=1000, decimals=0, sort_order=5))
    db_session.commit()
    orp = admin.get("/api/parameters").json()[0]
    admin.post("/api/lang", json={"lang": "es"})
    response = admin.post("/api/measurements", json={"pool_id": 1, "parameter_id": orp["id"], "value": 5000})
    assert response.json()["detail"] == "5000 está fuera del rango posible de ORP."


@pytest.mark.parametrize(
    ("request_kwargs", "status", "key", "es"),
    [
        ({"method": "GET", "url": "/api/clients"}, 401, "err.unauthenticated", "Inicia sesión."),
        ({"method": "GET", "url": "/api/nope"}, 404, "err.unknown_endpoint", "Ruta de API desconocida."),
        ({"method": "POST", "url": "/api/auth/login", "json": {"login": "x", "password": "y"}}, 401, "login.invalid",
         "Credenciales inválidas."),
        ({"method": "POST", "url": "/api/clients", "json": {"name": 5}}, 401, "err.unauthenticated", "Inicia sesión."),
    ],
)
def test_every_error_response_is_translated_and_keyed(client, request_kwargs, status, key, es):
    for lang, detail in (("en", t("en", key)), ("es", es)):
        response = client.request(**request_kwargs, headers={"Accept-Language": lang})
        assert response.status_code == status and response.json() == {"detail": detail, "key": key}


# --- SPA labels for backend values ------------------------------------------------------------------------------


@pytest.mark.parametrize("dictionary", [SPA_EN, SPA_ES], ids=["en", "es"])
def test_spa_has_a_label_for_every_backend_enum_value(dictionary):
    expected = (
        {f"status.{s}" for s in STATUSES}
        | {f"direction.{d}" for d in (DIRECTION_LOW, DIRECTION_HIGH)}
        | {f"class.{c}" for c in CLASSIFICATIONS}
        | {f"env.{e}" for e in ENVIRONMENTS}
        | {f"param.{spec.code}" for spec in PARAMETER_CATALOG}
    )
    assert expected - set(dictionary) == set()


def test_spanish_spa_texts_are_translated():
    same = {k for k in SPA_EN if SPA_EN[k] == SPA_ES.get(k)} - SPA_SAME_IN_BOTH
    assert sorted(same) == []


def test_localized_parameters_read_as_their_fallback_outside_a_response():
    from app.utils import BusinessError, Localized

    error = BusinessError("err.rule_range", value=15, parameter=Localized("param.PH", "pH"))
    assert error.params["value"] == "15" and isinstance(error.params["parameter"], Localized)
    assert str(error.params["parameter"]) == "pH"  # e.g. in logs

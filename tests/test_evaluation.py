"""The pure evaluation helper: no database, plain objects in, a frozen snapshot out."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.evaluation import Evaluation, evaluate
from app.utils import BusinessError, parse_float

# Same file drives frontend/src/lib/evaluation.test.ts: server and SPA preview must agree case by case.
SHARED = json.loads(
    (Path(__file__).resolve().parent.parent / "frontend/src/lib/evaluation.cases.json").read_text(encoding="utf-8")
)


def rule(min_value=7.2, max_value=7.8, rule_id=1, classification="NORMATIVE"):
    return SimpleNamespace(id=rule_id, min_value=min_value, max_value=max_value, classification=classification)


def test_value_inside_bounds_is_ok():
    assert evaluate(7.4, rule()) == Evaluation("OK", None, 1, 7.2, 7.8, "NORMATIVE")


def test_value_below_min_is_out_of_range_low():
    assert evaluate(6.9, rule()) == Evaluation("OUT_OF_RANGE", "LOW", 1, 7.2, 7.8, "NORMATIVE")


def test_value_above_max_is_out_of_range_high():
    assert evaluate(8.1, rule()) == Evaluation("OUT_OF_RANGE", "HIGH", 1, 7.2, 7.8, "NORMATIVE")


def test_no_rule_is_no_rule_without_snapshot():
    assert evaluate(7.4, None) == Evaluation("NO_RULE", None, None, None, None, None)


@pytest.mark.parametrize("value", [7.2, 7.8])
def test_bounds_are_inclusive(value):
    assert evaluate(value, rule()).status == "OK"


@pytest.mark.parametrize(
    ("min_value", "max_value", "value", "expected"),
    [
        (None, 0.2, 0.0, ("OK", None)),  # max-only (combined chlorine)
        (None, 0.2, 0.21, ("OUT_OF_RANGE", "HIGH")),
        (None, 0.2, -5.0, ("OK", None)),  # no lower bound at all
        (650, None, 700, ("OK", None)),  # min-only
        (650, None, 600, ("OUT_OF_RANGE", "LOW")),
        (28, 28, 28, ("OK", None)),  # single allowed value
        (28, 28, 28.01, ("OUT_OF_RANGE", "HIGH")),
        (None, None, 1e9, ("OK", None)),  # unbounded (the database forbids it; the helper stays total)
    ],
)
def test_one_sided_and_degenerate_rules(min_value, max_value, value, expected):
    result = evaluate(value, rule(min_value, max_value))
    assert (result.status, result.direction) == expected
    assert (result.rule_min, result.rule_max) == (min_value, max_value)


def test_snapshot_copies_the_rule_and_is_immutable():
    source = rule(rule_id=42, classification="COMPLEMENTARY")
    result = evaluate(7.0, source)
    source.min_value, source.max_value = 0, 14  # later edits of the rule object...
    assert (result.rule_id, result.rule_min, result.rule_max) == (42, 7.2, 7.8)  # ...do not reach the snapshot
    assert result.rule_classification == "COMPLEMENTARY"
    with pytest.raises(FrozenInstanceError):
        result.status = "OK"  # type: ignore[misc]


@pytest.mark.parametrize("case", SHARED["evaluate"], ids=lambda c: c["name"])
def test_shared_evaluation_contract(case):
    rule = SimpleNamespace(**case["rule"]) if case["rule"] else None
    result = evaluate(case["value"], rule)
    assert {"status": result.status, "direction": result.direction} == case["expected"]
    if rule is None:
        assert (result.rule_id, result.rule_min, result.rule_max, result.rule_classification) == (None,) * 4
    else:
        assert (result.rule_id, result.rule_min, result.rule_max, result.rule_classification) == (
            rule.id, rule.min_value, rule.max_value, rule.classification)


@pytest.mark.parametrize("case", SHARED["parse_decimal"], ids=lambda c: repr(c["input"]))
def test_shared_decimal_contract(case):
    if case.get("invalid"):
        with pytest.raises(BusinessError) as info:
            parse_float(case["input"])
        assert info.value.key == "err.number"
    else:
        assert parse_float(case["input"]) == case["expected"]


def test_numbers_from_json_bodies_still_parse():
    assert [parse_float(v) for v in (7.4, 7, 1e-7, 1e20, None)] == [7.4, 7.0, 1e-7, 1e20, None]
    with pytest.raises(BusinessError):
        parse_float(True)  # JSON true is not a measurement

"""Pure evaluation of one value against one norm rule. No database, no session, no clock.

The measurement service looks up the organization's *active* rule for the parameter and passes it here (or
``None``); the returned ``Evaluation`` is copied onto the measurement row as a snapshot. Rules:

- no rule                      -> ``NO_RULE`` (no direction, no snapshot)
- ``min <= value <= max``      -> ``OK`` (bounds inclusive; a missing bound is unbounded on that side)
- ``value < min``              -> ``OUT_OF_RANGE`` + ``LOW``
- ``value > max``              -> ``OUT_OF_RANGE`` + ``HIGH``

Values are compared exactly as stored (no rounding to the parameter's display decimals).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from app.models import DIRECTION_HIGH, DIRECTION_LOW, STATUS_NO_RULE, STATUS_OK, STATUS_OUT_OF_RANGE


class RuleLike(Protocol):
    """What evaluation reads from a rule (``models.NormRule`` satisfies it)."""

    id: int
    min_value: Optional[float]
    max_value: Optional[float]
    classification: str


@dataclass(frozen=True)
class Evaluation:
    status: str
    direction: Optional[str] = None
    rule_id: Optional[int] = None
    rule_min: Optional[float] = None
    rule_max: Optional[float] = None
    rule_classification: Optional[str] = None


def evaluate(value: float, rule: Optional[RuleLike]) -> Evaluation:
    """Classify ``value`` against ``rule`` and return the status plus a snapshot of the rule used."""
    if rule is None:
        return Evaluation(STATUS_NO_RULE)
    snapshot = {
        "rule_id": rule.id,
        "rule_min": rule.min_value,
        "rule_max": rule.max_value,
        "rule_classification": rule.classification,
    }
    if rule.min_value is not None and value < rule.min_value:
        return Evaluation(STATUS_OUT_OF_RANGE, DIRECTION_LOW, **snapshot)
    if rule.max_value is not None and value > rule.max_value:
        return Evaluation(STATUS_OUT_OF_RANGE, DIRECTION_HIGH, **snapshot)
    return Evaluation(STATUS_OK, **snapshot)

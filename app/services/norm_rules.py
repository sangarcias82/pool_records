"""Per-organization norm rules: the acceptable range of each water parameter.

Reads are open to every signed-in user (capture and evaluation need them); updates need ``manage_norm_rules``.
Validation happens on the merged result of the stored rule and the patch, so a partial update can never leave
``min_value > max_value`` or a rule without bounds.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session, contains_eager, selectinload

from app.models import CLASSIFICATIONS, NormRule, WaterParameter
from app.services.scoping import get_owned, scoped_select
from app.utils import BusinessError, Localized, parse_float, utc_now

EDITABLE_FIELDS = ("min_value", "max_value", "active", "classification")


def list_rules(db: Session, org_id: int) -> list[NormRule]:
    """Every rule of the organization (active and inactive) in parameter display order."""
    stmt = (
        scoped_select(NormRule, org_id)
        .join(NormRule.parameter)
        .options(contains_eager(NormRule.parameter), selectinload(NormRule.updated_by))
        .order_by(WaterParameter.sort_order, WaterParameter.code)
    )
    return list(db.scalars(stmt))


def get_rule(db: Session, org_id: int, rule_id: int) -> NormRule:
    return get_owned(db, NormRule, org_id, rule_id)


def _bound(raw: Any, parameter: WaterParameter) -> Optional[float]:
    """Parse one bound (``None``/blank clears it) and keep it inside the parameter's physical range."""
    value = parse_float(raw)
    if value is None:
        return None
    below = parameter.physical_min is not None and value < parameter.physical_min
    above = parameter.physical_max is not None and value > parameter.physical_max
    if below or above:
        raise BusinessError(
            "err.rule_range", value=f"{value:g}", parameter=Localized(f"param.{parameter.code}", parameter.name)
        )
    return value


def _classification(raw: Any) -> str:
    value = raw.strip().upper() if isinstance(raw, str) else None
    if value not in CLASSIFICATIONS:
        raise BusinessError("err.rule_classification")
    return value


def update_rule(db: Session, org_id: int, rule_id: int, changes: dict[str, Any], user_id: int) -> NormRule:
    """Apply a partial update. Only keys present in ``changes`` are touched; a no-op does not bump ``updated_at``."""
    rule = get_rule(db, org_id, rule_id)
    unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
    if unknown:
        raise BusinessError("err.rule_field", field=unknown[0])

    merged = {field: getattr(rule, field) for field in EDITABLE_FIELDS}
    for bound in ("min_value", "max_value"):
        if bound in changes:
            merged[bound] = _bound(changes[bound], rule.parameter)
    if "active" in changes:
        if not isinstance(changes["active"], bool):
            raise BusinessError("err.rule_active")
        merged["active"] = changes["active"]
    if "classification" in changes:
        merged["classification"] = _classification(changes["classification"])

    low, high = merged["min_value"], merged["max_value"]
    if low is None and high is None:
        raise BusinessError("err.rule_bounds")
    if low is not None and high is not None and low > high:
        raise BusinessError("err.rule_order")

    if any(getattr(rule, field) != value for field, value in merged.items()):
        for field, value in merged.items():
            setattr(rule, field, value)
        rule.updated_at = utc_now()
        rule.updated_by_id = user_id
        db.commit()
    return rule

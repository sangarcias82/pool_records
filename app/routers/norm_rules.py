"""Norm rules of the signed-in user's organization: read for everyone, edit for ``manage_norm_rules``."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import serializers
from app.auth import require_capability, require_user
from app.db import get_db
from app.models import AppUser
from app.schemas import NormRulePatch
from app.services import norm_rules as rule_service

router = APIRouter(prefix="/api/norm-rules", tags=["norm-rules"])
rule_admin = require_capability("manage_norm_rules")


@router.get("")
def list_rules(user: AppUser = Depends(require_user), db: Session = Depends(get_db)) -> list[dict]:
    return [serializers.norm_rule(r) for r in rule_service.list_rules(db, user.organization_id)]


@router.patch("/{rule_id}")
def update_rule(
    rule_id: int, body: NormRulePatch, user: AppUser = Depends(rule_admin), db: Session = Depends(get_db)
) -> dict:
    """Partial update of ``min_value``, ``max_value``, ``active`` and/or ``classification``."""
    changes = body.model_dump(exclude_unset=True)
    return serializers.norm_rule(rule_service.update_rule(db, user.organization_id, rule_id, changes, user.id))

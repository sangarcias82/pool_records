"""Request bodies. Numbers may arrive as JSON numbers or text such as ``"7,4"``."""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict


class LoginIn(BaseModel):
    login: str = ""
    password: str = ""
    lang: Optional[str] = None


class LangIn(BaseModel):
    lang: str


class ClientIn(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class PoolIn(BaseModel):
    name: Optional[str] = None
    volume_liters: Optional[Union[float, str]] = None
    environment: Optional[str] = None


class NormRulePatch(BaseModel):
    """Partial update: only the keys present in the JSON body change (``null`` clears a bound).

    Values are loosely typed on purpose and checked by ``services.norm_rules`` so each mistake gets its own
    translated key; unknown keys are kept (``extra="allow"``) so the service can reject them by name.
    """

    model_config = ConfigDict(extra="allow")

    min_value: Any = None
    max_value: Any = None
    active: Any = None
    classification: Any = None


class MeasurementIn(BaseModel):
    """``POST /api/measurements``. Loosely typed on purpose: ``services.measurements`` validates every field and
    answers with a translated key. ``value`` may be ``7.4`` or ``"7,4"``; ``measured_at`` is ISO 8601 (no
    offset = UTC, omitted = now); ``unit`` is optional and, if sent, must match the parameter's unit."""

    pool_id: Any = None
    parameter_id: Any = None
    value: Any = None
    unit: Any = None
    measured_at: Any = None
    notes: Optional[str] = None

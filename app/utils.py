"""Small parsing helpers shared by services."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Optional

class Localized:
    """A message parameter translated when the response is built (the request's language is not known earlier).

    ``BusinessError("err.rule_range", parameter=Localized("param.PH", "pH"))`` -> "... de pH" / "... of pH";
    ``fallback`` is used when the dictionaries have no entry for ``key``.
    """

    def __init__(self, key: str, fallback: str):
        self.key = key
        self.fallback = fallback

    def __str__(self) -> str:
        return self.fallback


class BusinessError(Exception):
    """Domain rule violation. ``key`` is an i18n key (see ``app.i18n``); ``params`` fill ``{placeholders}``
    (plain values become text; ``Localized`` values are translated per request)."""

    def __init__(self, key: str, **params: object):
        super().__init__(key)
        self.key = key
        self.params = {k: v if isinstance(v, Localized) else str(v) for k, v in params.items()}


# Plain decimal, optional sign and exponent. Deliberately narrower than float(): no "1_000", "inf", "nan" or
# thousands separators, so the SPA preview (frontend/src/lib/evaluation.ts parseDecimal) reads input identically.
# Shared cases: frontend/src/lib/evaluation.cases.json.
_DECIMAL_RE = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")


def parse_float(raw: Any) -> Optional[float]:
    """Parse a decimal typed by a person. Accepts ``7,4`` and ``7.4``; blank -> None; anything else -> err.number."""
    text = "" if raw is None else str(raw).strip().replace(",", ".")
    if not text:
        return None
    value = float(text) if _DECIMAL_RE.fullmatch(text) else math.nan
    if not math.isfinite(value):  # also "1e999" (overflows to inf)
        raise BusinessError("err.number", value=raw)
    return value


def parse_id(raw: Any) -> Optional[int]:
    """Positive integer id from JSON (``3``) or text (``"3"``); anything else (``True``, ``3.5``, ``"x"``) -> None."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    text = raw.strip() if isinstance(raw, str) else ""
    return int(text) if text.isdigit() and int(text) > 0 else None


def clean_text(raw: Optional[str], max_len: int = 255) -> Optional[str]:
    return (raw or "").strip()[:max_len] or None


def utc_now() -> datetime:
    """Current time in UTC. Store this; SQLite keeps it naive and ``iso_utc`` re-attaches the zone."""
    return datetime.now(timezone.utc)


def to_utc_naive(value: datetime) -> datetime:
    """Convert to UTC and drop the zone for storage. SQLite would otherwise drop the offset WITHOUT converting
    (08:00-06:00 would be stored as 08:00). Naive input is taken as UTC already."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    """ISO 8601 with an explicit UTC offset (``...+00:00``); naive values are taken as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()

"""Small parsing helpers shared by services."""

from __future__ import annotations

import math
from typing import Any, Optional



class BusinessError(Exception):
    """Domain rule violation. ``key`` is an i18n key (see ``app.i18n``); ``params`` fill ``{placeholders}``."""

    def __init__(self, key: str, **params: object):
        super().__init__(key)
        self.key = key
        self.params = {k: str(v) for k, v in params.items()}


def parse_float(raw: Any) -> Optional[float]:
    """Parse a decimal typed by a person. Accepts ``7,4`` and ``7.4``; blank -> None."""
    text = "" if raw is None else str(raw).strip().replace(",", ".")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise BusinessError("err.number", value=raw)
    return value


def clean_text(raw: Optional[str], max_len: int = 255) -> Optional[str]:
    return (raw or "").strip()[:max_len] or None

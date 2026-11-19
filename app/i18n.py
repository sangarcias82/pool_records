"""Server-side messages (errors and login, EN/ES). Everything else is translated in the SPA.

Parity and completeness are tested in tests/test_i18n.py."""

from __future__ import annotations

SUPPORTED_LANGS = ("en", "es")

EN = {
    "forbidden": "You do not have permission for this action.",
    "login.invalid": "Invalid credentials.",
    "err.required": "Please fill in the required fields.",
    "err.not_found": "Record not found.",
    "err.number": "'{value}' is not a valid number.",
    "err.client_name": "Client name is required.",
    "err.email": "Enter a valid email address.",
    "err.pool_name": "Pool name is required.",
    "err.volume": "Volume must be a positive number of liters.",
    "err.environment": "Environment must be OUTDOOR or INDOOR.",
    "err.rule_bounds": "A rule needs a minimum, a maximum or both.",
    "err.rule_order": "The minimum must be less than or equal to the maximum.",
    "err.rule_range": "{value} is outside the possible range of {parameter}.",
    "err.rule_classification": "Classification must be NORMATIVE or COMPLEMENTARY.",
    "err.rule_active": "'active' must be true or false.",
    "err.rule_field": "'{field}' cannot be changed here. Editable: min_value, max_value, active, classification.",
    "err.parameter": "Choose an active water parameter.",
    "err.pool": "Choose a pool.",
    "err.unit": "Unit '{unit}' does not match this parameter (expected {expected}).",
    "err.value": "Enter the measured value.",
    "err.measured_at": "Use an ISO 8601 date and time, e.g. 2025-06-01T08:30:00-06:00.",
    "err.measured_future": "The measurement time cannot be in the future.",
    "err.status_filter": "Status must be OK, OUT_OF_RANGE or NO_RULE.",
    "err.unauthenticated": "Please sign in.",
    "err.unknown_endpoint": "Unknown API endpoint.",
    # Parameter names inside messages (lower case: they appear mid-sentence). The SPA has its own labels.
    "param.PH": "pH",
    "param.FREE_CHLORINE": "free chlorine",
    "param.TOTAL_CHLORINE": "total chlorine",
    "param.COMBINED_CHLORINE": "combined chlorine",
    "param.CYANURIC_ACID": "cyanuric acid",
    "param.TURBIDITY": "turbidity",
    "param.TOTAL_ALKALINITY": "total alkalinity",
    "param.CALCIUM_HARDNESS": "calcium hardness",
    "param.TEMPERATURE": "temperature",
    "param.TDS": "total dissolved solids",
}

ES = {
    "forbidden": "No tienes permiso para esta acción.",
    "login.invalid": "Credenciales inválidas.",
    "err.required": "Completa los campos obligatorios.",
    "err.not_found": "Registro no encontrado.",
    "err.number": "'{value}' no es un número válido.",
    "err.client_name": "El nombre del cliente es obligatorio.",
    "err.email": "Ingresa un correo válido.",
    "err.pool_name": "El nombre de la alberca es obligatorio.",
    "err.volume": "El volumen debe ser un número positivo de litros.",
    "err.environment": "La ubicación debe ser OUTDOOR (exterior) o INDOOR (interior).",
    "err.rule_bounds": "Una regla necesita un mínimo, un máximo o ambos.",
    "err.rule_order": "El mínimo debe ser menor o igual que el máximo.",
    "err.rule_range": "{value} está fuera del rango posible de {parameter}.",
    "err.rule_classification": "La clasificación debe ser NORMATIVE (normativa) o COMPLEMENTARY (complementaria).",
    "err.rule_active": "«active» debe ser true o false.",
    "err.rule_field": "'{field}' no se puede modificar aquí. Editables: min_value, max_value, active, classification.",
    "err.parameter": "Elige un parámetro de agua activo.",
    "err.pool": "Elige una alberca.",
    "err.unit": "La unidad '{unit}' no corresponde a este parámetro (se espera {expected}).",
    "err.value": "Ingresa el valor medido.",
    "err.measured_at": "Usa fecha y hora ISO 8601, p. ej. 2025-06-01T08:30:00-06:00.",
    "err.measured_future": "La hora de la medición no puede estar en el futuro.",
    "err.status_filter": "El estado debe ser OK, OUT_OF_RANGE o NO_RULE.",
    "err.unauthenticated": "Inicia sesión.",
    "err.unknown_endpoint": "Ruta de API desconocida.",
    "param.PH": "pH",
    "param.FREE_CHLORINE": "cloro libre",
    "param.TOTAL_CHLORINE": "cloro total",
    "param.COMBINED_CHLORINE": "cloro combinado",
    "param.CYANURIC_ACID": "ácido cianúrico",
    "param.TURBIDITY": "turbidez",
    "param.TOTAL_ALKALINITY": "alcalinidad total",
    "param.CALCIUM_HARDNESS": "dureza cálcica",
    "param.TEMPERATURE": "temperatura",
    "param.TDS": "sólidos disueltos totales",
}

MESSAGES = {"en": EN, "es": ES}


def t(lang: str, key: str, **kwargs: str) -> str:
    text = MESSAGES.get(lang, EN).get(key) or EN.get(key) or key
    try:
        return text.format(**kwargs) if kwargs else text
    except (KeyError, ValueError, IndexError):
        return text

"""Server-side messages (errors and login). Everything else is translated in the SPA."""

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
    "err.environment": "El tipo debe ser OUTDOOR o INDOOR.",
}

MESSAGES = {"en": EN, "es": ES}


def t(lang: str, key: str, **kwargs: str) -> str:
    text = MESSAGES.get(lang, EN).get(key) or EN.get(key) or key
    try:
        return text.format(**kwargs) if kwargs else text
    except (KeyError, ValueError, IndexError):
        return text

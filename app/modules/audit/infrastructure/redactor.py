# app/modules/audit/infrastructure/redactor.py
import re
from typing import Any, Dict, List, Set

# Conjunto de claves sensibles a censurar (sensible a mayúsculas/minúsculas y variaciones comunes)
SENSITIVE_KEYS: Set[str] = {
    "password",
    "pass",
    "token",
    "secret",
    "authorization",
    "recovery_code",
    "cookie",
    "refresh_token",
    "access_token",
    "current_password",
    "new_password",
    "api_key",
    "shared_secret",
    "voucher",
    "checked_image",
    "profile_image",
    "banner_es",
    "banner_pr",
    "banner_en",
    "popup_es",
    "popup_pr",
    "popup_en",
}

# Regex para enmascarar parcialmente datos financieros e identificadores (CCI, CPF, PIX, etc.)
FINANCIAL_MASK_REGEX = re.compile(r"^\d{10,24}$")


def redact_value(key: str, value: Any) -> Any:
    if value is None:
        return None

    key_lower = key.lower()

    # Censurar completamente claves estrictamente sensibles
    if any(sens in key_lower for sens in SENSITIVE_KEYS):
        return "[REDACTED]"

    # Enmascarar parcialmente identificadores financieros si son strings numéricos largos
    if isinstance(value, str):
        if key_lower in ("account_number", "cci", "cpf", "pix", "card_number", "document_number") or FINANCIAL_MASK_REGEX.match(value):
            if len(value) > 6:
                return f"{value[:3]}***{value[-3:]}"
            return "***"

    return redact_data(value)


def redact_data(data: Any) -> Any:
    """
    Sanitizador defensivo y recursivo para censurar contraseñas, tokens, cookies
    y datos sensibles dentro de dicts, listas o estructuras complejas.
    """
    if isinstance(data, dict):
        redacted_dict: Dict[str, Any] = {}
        for k, v in data.items():
            redacted_dict[k] = redact_value(str(k), v)
        return redacted_dict
    elif isinstance(data, list):
        return [redact_data(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(redact_data(item) for item in data)
    return data

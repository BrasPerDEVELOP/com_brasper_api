"""Contact lists are independent of unique login credentials."""
from email_validator import validate_email, EmailNotValidError


def unique_emails(values):
    result = []
    seen = set()
    for value in values:
        address = str(value or "").strip()
        if address and address.casefold() not in seen:
            result.append(address)
            seen.add(address.casefold())
    return result


def validate_emails(values):
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError("Los correos deben ser una lista de hasta 20 direcciones")
    result = []
    for value in values:
        if not isinstance(value, str) or len(value.strip()) > 255:
            raise ValueError("Cada correo debe ser una dirección válida de hasta 255 caracteres")
        try:
            result.append(validate_email(value.strip(), check_deliverability=False).normalized)
        except EmailNotValidError as exc:
            raise ValueError("Revisa el formato de cada correo electrónico") from exc
    return unique_emails(result)


def registered_emails(user):
    return unique_emails([getattr(user, "email", None), *(getattr(user, "emails", None) or [])])

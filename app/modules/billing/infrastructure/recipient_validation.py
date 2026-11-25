"""Shared fiscal/marketing email checks. DNS approval is not mailbox verification."""
import asyncio
import re

from email_validator import EmailNotValidError, caching_resolver, validate_email
from sqlalchemy import text

from app.shared.contact_emails import validate_emails

_resolver = caching_resolver(timeout=2)


class RecipientValidationError(ValueError):
    pass


class MailboxNotFound(RecipientValidationError):
    def __init__(self, recipient):
        self.recipient = recipient
        super().__init__(f"El correo {recipient} fue rechazado como inexistente. Corrige el destinatario antes de reenviar.")


def validate_recipient_domain(recipient):
    try:
        result = validate_email(recipient, check_deliverability=True, dns_resolver=_resolver)
    except EmailNotValidError as exc:
        raise RecipientValidationError(
            f"No se puede enviar a {recipient}: revisa el formato y que el dominio reciba correos."
        ) from exc
    if not getattr(result, "mx", None):
        raise RecipientValidationError(
            f"No se pudo verificar el dominio de {recipient}. Intenta nuevamente en unos minutos."
        )
    return result.normalized


async def check_invoice_recipients(db, recipients):
    try:
        recipients = validate_emails(recipients)
    except ValueError as exc:
        raise RecipientValidationError(str(exc)) from exc
    if not recipients:
        raise ValueError("Selecciona al menos un correo")
    blocked = (await db.execute(text(
        "SELECT email FROM billing.email_suppressions WHERE email = ANY(:emails)"
    ), {"emails": [address.casefold() for address in recipients]})).scalars().all()
    if blocked:
        raise MailboxNotFound(blocked[0])
    # Threaded DNS keeps the API event loop responsive. Bound the whole batch.
    try:
        await asyncio.wait_for(asyncio.gather(*[
            asyncio.to_thread(validate_recipient_domain, address) for address in recipients
        ]), timeout=10)
    except asyncio.TimeoutError as exc:
        raise RecipientValidationError("No se pudo verificar el dominio de los correos. Intenta nuevamente en unos minutos.") from exc


async def record_invalid_mailbox(db, recipient):
    # Only called for a definitive SMTP 550 / 5.1.1. Never for auth, quota or DNS timeouts.
    await db.execute(text(
        "INSERT INTO billing.email_suppressions (email, reason) VALUES (:email, 'smtp_5.1.1') "
        "ON CONFLICT (email) DO NOTHING"
    ), {"email": recipient.strip().casefold()})


def raise_for_invalid_mailbox(recipient, refusal):
    code, message = refusal
    message = message.decode('utf-8', errors='replace') if isinstance(message, bytes) else str(message)
    if code == 550 and re.search(r"(?<![\d.])5\.1\.1(?![\d.])", message):
        raise MailboxNotFound(recipient)

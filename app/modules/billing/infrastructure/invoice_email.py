"""Envío opcional del PDF oficial del comprobante, separado del SMTP de marketing."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.settings import Settings
from app.modules.billing.infrastructure.recipient_validation import validate_recipient_domain, raise_for_invalid_mailbox


def ensure_invoice_email_ready(settings: Settings, recipient: str | None) -> None:
    from email_validator import EmailNotValidError, validate_email

    if not recipient:
        raise ValueError("Ingresa el correo del cliente para enviar el comprobante")
    try:
        validate_email(recipient, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError("El correo del cliente no es válido") from exc
    if not all((settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL)):
        raise ValueError("El correo de comprobantes no está configurado en el servidor")
    if not settings.SMTP_USE_TLS:
        raise ValueError("El correo de comprobantes requiere SMTP con TLS")


def send_invoice_pdf(settings: Settings, *, recipient: str, full_number: str,
                     issuer_name: str, pdf: bytes, filename: str) -> None:
    ensure_invoice_email_ready(settings, recipient)
    recipient = validate_recipient_domain(recipient)
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("El proveedor no entregó un PDF válido")
    message = EmailMessage()
    message["From"] = formataddr((issuer_name, settings.SMTP_FROM_EMAIL))
    message["To"] = recipient
    message["Subject"] = f"Comprobante electrónico {full_number}"
    message.set_content(
        f"Hola,\n\nAdjuntamos el comprobante electrónico {full_number} "
        f"emitido por {issuer_name}.\n\nSaludos,\n{issuer_name}"
    )
    message.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        try:
            refused = smtp.send_message(message)
        except smtplib.SMTPRecipientsRefused as exc:
            for address, refusal in exc.recipients.items():
                if address.casefold() == recipient.casefold():
                    raise_for_invalid_mailbox(recipient, refusal)
            raise
        if refused:
            for address, refusal in refused.items():
                if address.casefold() == recipient.casefold():
                    raise_for_invalid_mailbox(recipient, refusal)
            raise smtplib.SMTPRecipientsRefused(refused)

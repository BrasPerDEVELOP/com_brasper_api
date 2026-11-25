"""Durable, explicit PDF delivery. No fiscal issuance happens in this flow."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.orm import selectinload

from app.modules.billing.infrastructure.invoice_email import ensure_invoice_email_ready, send_invoice_pdf
from app.modules.omie.application.service import OmieBillingService
from app.modules.omie.domain.models import OmieInvoice
from app.modules.omie.infrastructure.pdf import download_pdf
from app.modules.omie.infrastructure.client import OmieError
from app.modules.transactions.domain.models import Transaction
from app.shared.contact_emails import registered_emails, unique_emails, validate_emails
from app.modules.billing.infrastructure.recipient_validation import check_invoice_recipients, record_invalid_mailbox, MailboxNotFound

logger = logging.getLogger(__name__)


class OmieEmailRepository:
    def __init__(self, db):
        self.db = db

    async def get(self, tx_id):
        row = await self.db.get(OmieInvoice, tx_id, populate_existing=True)
        if row is None:
            raise LookupError("No hay una nota fiscal para esta operación")
        return row

    async def contacts(self, tx_id):
        tx = (await self.db.execute(select(Transaction).options(selectinload(Transaction.user)).where(
            Transaction.id == tx_id
        ))).scalar_one_or_none()
        return registered_emails(tx.user if tx else None)

    async def queue(self, tx_id, recipients):
        # Atomic condition prevents competing requests from replacing an active job.
        result = await self.db.execute(update(OmieInvoice).where(
            OmieInvoice.transaction_id == tx_id, OmieInvoice.status == "issued",
            or_(OmieInvoice.email_status.is_(None), OmieInvoice.email_status.in_(["sent", "failed"])),
        ).values(email_status="pending", email_recipients=recipients, email_sent_at=None, email_error=None))
        await self.db.commit()
        return result.rowcount == 1

    async def pending(self, limit):
        return (await self.db.execute(select(OmieInvoice.transaction_id).where(
            OmieInvoice.email_status == "pending"
        ).order_by(OmieInvoice.created_at).limit(limit))).scalars().all()

    async def claim(self, tx_id):
        result = await self.db.execute(update(OmieInvoice).where(
            OmieInvoice.transaction_id == tx_id, OmieInvoice.email_status == "pending",
        ).values(email_status="sending"))
        await self.db.commit()
        return result.rowcount == 1

    async def delivered(self, row, recipient):
        row.email_delivered_to = unique_emails([*(row.email_delivered_to or []), recipient])
        await self.db.commit()

    async def complete(self, row, status, error=None):
        row.email_status = status
        row.email_error = error
        row.email_sent_at = datetime.now(timezone.utc) if status == "sent" else None
        await self.db.commit()


class OmieEmailService:
    def __init__(self, db, settings, *, repo=None, billing=None):
        self.settings = settings
        self.repo = repo or OmieEmailRepository(db)
        self.billing = billing or OmieBillingService(db, settings)

    async def details(self, tx_id):
        row = await self.repo.get(tx_id)
        return {
            "customer_emails": await self.repo.contacts(tx_id),
            "email_status": row.email_status,
            "email_error": row.email_error,
            "email_recipients": row.email_recipients or [],
            "email_delivered_to": row.email_delivered_to or [],
            "email_sent_at": row.email_sent_at.isoformat() if row.email_sent_at else None,
        }

    async def request(self, tx_id, recipients):
        row = await self.repo.get(tx_id)
        if row.status != "issued" or not row.nfse_id or not row.nfse_number:
            raise ValueError("Solo puedes enviar el PDF de una nota fiscal emitida")
        recipients = validate_emails(recipients if recipients is not None else await self.repo.contacts(tx_id))
        if not recipients:
            raise ValueError("Selecciona al menos un correo")
        for recipient in recipients:
            ensure_invoice_email_ready(self.settings, recipient)
        delivered = {email.casefold() for email in row.email_delivered_to or []}
        recipients = [email for email in recipients if email.casefold() not in delivered]
        if not recipients:
            raise ValueError("El PDF ya fue enviado a todos los correos seleccionados")
        await check_invoice_recipients(self.repo.db, recipients)
        if not await self.repo.queue(tx_id, recipients):
            raise ValueError("El PDF tiene un envío en curso. Actualiza el detalle")
        return await self.details(tx_id)

    async def deliver_pending(self, limit=20):
        delivered = 0
        for tx_id in await self.repo.pending(limit):
            if not await self.repo.claim(tx_id):
                continue
            row = await self.repo.get(tx_id)
            smtp_completed = False
            try:
                if row.status != "issued":
                    raise ValueError("La nota fiscal ya no está emitida")
                pending = [email for email in unique_emails(row.email_recipients or [])
                           if email.casefold() not in {e.casefold() for e in row.email_delivered_to or []}]
                if pending:
                    await check_invoice_recipients(self.repo.db, pending)
                # Reuses the note-number and URL validation of the PDF action.
                document = await self.billing.pdf(tx_id)
                pdf = await download_pdf(document["url"])
                completed = {email.casefold() for email in row.email_delivered_to or []}
                for recipient in unique_emails(row.email_recipients or []):
                    if recipient.casefold() in completed:
                        continue
                    await asyncio.to_thread(
                        send_invoice_pdf, self.settings, recipient=recipient,
                        full_number=f"NFS-e {row.nfse_number}",
                        issuer_name=row.snapshot.get("issuer") or "BrasPer",
                        pdf=pdf, filename=f"NFSe-{row.nfse_id}.pdf",
                    )
                    smtp_completed = True
                    await self.repo.delivered(row, recipient)
                    smtp_completed = False
            except Exception as exc:
                logger.warning("No se pudo completar el correo de Omie para %s", tx_id)
                if smtp_completed:
                    # Keep the claim when SMTP succeeded but persistence failed.
                    # Retrying automatically could duplicate a delivered message.
                    raise
                if isinstance(exc, MailboxNotFound):
                    await record_invalid_mailbox(self.repo.db, exc.recipient)
                message = str(exc)[:600] if isinstance(exc, (ValueError, OmieError)) else "No se pudo entregar el correo. Intenta más tarde."
                await self.repo.complete(row, "failed", error=message)
            else:
                await self.repo.complete(row, "sent")
                delivered += 1
        return delivered

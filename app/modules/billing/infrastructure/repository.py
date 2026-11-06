# app/modules/billing/infrastructure/repository.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.billing.domain.enums import OPEN_INVOICE_STATUSES
from app.modules.billing.domain.models import BillingSeries, Invoice, InvoiceEvent
from app.modules.billing.interfaces.repository import BillingRepositoryInterface
from app.modules.coin.domain.models import TaxRate, Commission
from app.modules.coin.infrastructure.repository import SQLAlchemyCommissionAccountingSettingsRepository
from app.modules.transactions.infrastructure.repository import SQLAlchemyTransactionRepository
from app.modules.billing.domain.amounts import accounting_final_sale
from app.modules.transactions.domain.models import Transaction


class SQLAlchemyBillingRepository(BillingRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.session = db

    # --- Datos de la operación ---------------------------------------------
    async def get_transaction_for_billing(self, transaction_id: UUID) -> Optional[Transaction]:
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.user))
            .where(Transaction.id == transaction_id, Transaction.deleted.is_(False))
        )
        return (await self.session.execute(stmt)).unique().scalar_one_or_none()

    async def get_final_sale_for_billing(self, transaction):
        rule = await SQLAlchemyCommissionAccountingSettingsRepository(self.session).get_current()
        percentages = await SQLAlchemyTransactionRepository(self.session).accounting_percentages([transaction.id])
        commission = (await self.session.execute(
            select(Commission).where(
                Commission.id == transaction.commission_id,
                Commission.deleted.is_(False),
            )
        )).scalar_one_or_none()
        return accounting_final_sale(
            transaction.origin_amount,
            commission.percentage if commission is not None else None,
            percentages.get(transaction.id),
            amount_threshold=rule.amount_threshold if rule is not None else 100,
            fixed_commission=rule.fixed_commission if rule is not None else 3,
        )

    async def get_tax_rate(self, tax_rate_id: UUID) -> Optional[TaxRate]:
        stmt = select(TaxRate).where(TaxRate.id == tax_rate_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_transaction_billing_date(self, transaction_id: UUID, value: datetime) -> None:
        await self.session.execute(
            text(
                'UPDATE "transaction".transactions SET billing_date = :value '
                "WHERE id = :id AND billing_date IS NULL"
            ),
            {"value": value, "id": transaction_id},
        )

    # --- Series ----------------------------------------------------------------
    async def _series_row_for_update(
        self, issuer_ruc: str, document_type: str, series: str, environment: str
    ) -> BillingSeries:
        # Alta idempotente de la fila: dos procesos pueden intentar crearla a la vez.
        await self.session.execute(
            text(
                'INSERT INTO "billing".series '
                "(id, issuer_ruc, document_type, series, environment, last_number, is_active, deleted, enable) "
                "VALUES (:id, :issuer_ruc, :document_type, :series, :environment, 0, true, false, true) "
                "ON CONFLICT ON CONSTRAINT uq_billing_series DO NOTHING"
            ),
            {
                "id": uuid.uuid4(),
                "issuer_ruc": issuer_ruc,
                "document_type": document_type,
                "series": series,
                "environment": environment,
            },
        )
        stmt = (
            select(BillingSeries)
            .where(
                BillingSeries.issuer_ruc == issuer_ruc,
                BillingSeries.document_type == document_type,
                BillingSeries.series == series,
                BillingSeries.environment == environment,
            )
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def reserve_next_number(
        self, issuer_ruc: str, document_type: str, series: str, environment: str
    ) -> int:
        row = await self._series_row_for_update(issuer_ruc, document_type, series, environment)
        if not row.is_active:
            raise ValueError(f"La serie {series} ({document_type}) de {issuer_ruc} está inactiva")
        row.last_number = int(row.last_number or 0) + 1
        await self.session.flush()
        return row.last_number

    async def list_series(self, environment: str) -> list[BillingSeries]:
        stmt = (
            select(BillingSeries)
            .where(BillingSeries.environment == environment, BillingSeries.deleted.is_(False))
            .order_by(BillingSeries.issuer_ruc, BillingSeries.document_type, BillingSeries.series)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def set_last_number(
        self, issuer_ruc: str, document_type: str, series: str, environment: str, last_number: int
    ) -> BillingSeries:
        row = await self._series_row_for_update(issuer_ruc, document_type, series, environment)
        row.last_number = int(last_number)
        await self.session.flush()
        return row

    # --- Comprobantes ------------------------------------------------------------
    async def get_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.deleted.is_(False))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_open_invoice(self, transaction_id: UUID) -> Optional[Invoice]:
        stmt = (
            select(Invoice)
            .where(
                Invoice.transaction_id == transaction_id,
                Invoice.deleted.is_(False),
                Invoice.status.in_(OPEN_INVOICE_STATUSES),
            )
            .order_by(Invoice.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest_invoice(self, transaction_id: UUID) -> Optional[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.transaction_id == transaction_id, Invoice.deleted.is_(False))
            .order_by(Invoice.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_invoices(
        self,
        *,
        status: Optional[str] = None,
        document_type: Optional[str] = None,
        transaction_id: Optional[UUID] = None,
        issuer_ruc: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Invoice], int]:
        conditions = [Invoice.deleted.is_(False)]
        if status:
            conditions.append(Invoice.status == status)
        if document_type:
            conditions.append(Invoice.document_type == document_type)
        if transaction_id is not None:
            conditions.append(Invoice.transaction_id == transaction_id)
        if issuer_ruc:
            conditions.append(Invoice.issuer_ruc == issuer_ruc)
        if date_from is not None:
            conditions.append(Invoice.issue_date >= date_from)
        if date_to is not None:
            conditions.append(Invoice.issue_date <= date_to)
        total = (
            await self.session.execute(select(func.count()).select_from(Invoice).where(*conditions))
        ).scalar_one()
        stmt = (
            select(Invoice)
            .where(*conditions)
            .order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, int(total or 0)

    async def list_by_status(self, statuses: Sequence[str], *, limit: int = 50) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.deleted.is_(False), Invoice.status.in_(list(statuses)))
            .order_by(Invoice.last_polled_at.asc().nulls_first(), Invoice.created_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_pending_emails(self, *, limit: int = 50) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.deleted.is_(False), Invoice.status == "accepted", Invoice.email_status == "pending")
            .order_by(Invoice.accepted_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def claim_invoice_email(self, invoice_id: UUID) -> bool:
        # Commit antes del SMTP: si el proceso cae durante el envío, no se repite
        # automáticamente un correo cuyo resultado ya no podemos conocer.
        stmt = (
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.deleted.is_(False),
                   Invoice.status == "accepted", Invoice.email_status == "pending")
            .values(email_status="sending")
            .returning(Invoice.id)
        )
        claimed = (await self.session.execute(stmt)).scalar_one_or_none() is not None
        await self.session.commit()
        return claimed

    async def queue_invoice_email(self, invoice_id: UUID, recipients: list[str]) -> bool:
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == invoice_id, Invoice.deleted.is_(False),
                Invoice.status == "accepted",
                or_(Invoice.email_status.is_(None), Invoice.email_status.in_(["failed", "sent"])),
            )
            .values(email_recipients=recipients, email_requested=True, email_status="pending", email_sent_at=None)
            .returning(Invoice.id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def record_email_delivery(self, invoice_id: UUID, recipient: str) -> None:
        # Only the worker that claimed the invoice can reach this point.
        invoice = await self.get_invoice(invoice_id)
        invoice.email_delivered_to = [*(invoice.email_delivered_to or []), recipient]
        await self.add_event(invoice_id, "email_sent", {"recipient": recipient})
        await self.session.commit()

    async def complete_invoice_email(self, invoice_id: UUID, *, sent: bool) -> None:
        values = {"email_status": "sent" if sent else "failed"}
        if sent:
            values["email_sent_at"] = datetime.now(timezone.utc)
        await self.session.execute(update(Invoice).where(Invoice.id == invoice_id).values(**values))
        await self.session.commit()

    async def latest_invoices_for_transactions(self, transaction_ids: Sequence[UUID]) -> list[Invoice]:
        if not transaction_ids:
            return []
        stmt = (
            select(Invoice)
            .where(Invoice.deleted.is_(False), Invoice.transaction_id.in_(list(transaction_ids)))
            .distinct(Invoice.transaction_id)
            .order_by(Invoice.transaction_id, Invoice.created_at.desc(), Invoice.number.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_stale_reserved(self, reserved_before: datetime, *, limit: int = 50) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(
                Invoice.deleted.is_(False),
                Invoice.status == "reserved",
                or_(Invoice.reserved_at.is_(None), Invoice.reserved_at < reserved_before),
            )
            .order_by(Invoice.reserved_at.asc().nulls_first())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_events(self, invoice_id: UUID) -> list[InvoiceEvent]:
        stmt = (
            select(InvoiceEvent)
            .where(InvoiceEvent.invoice_id == invoice_id)
            .order_by(InvoiceEvent.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def add_invoice(self, entity: Invoice) -> Invoice:
        self.session.add(entity)
        return entity

    async def add_event(self, invoice_id: UUID, event: str, payload: Optional[dict] = None) -> InvoiceEvent:
        entity = InvoiceEvent(invoice_id=invoice_id, event=event, payload=payload)
        self.session.add(entity)
        return entity

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity) -> None:
        await self.session.refresh(entity)

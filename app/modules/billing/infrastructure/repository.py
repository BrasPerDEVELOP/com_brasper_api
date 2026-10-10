# app/modules/billing/infrastructure/repository.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.billing.domain.enums import OPEN_INVOICE_STATUSES
from app.modules.billing.domain.models import BillingSeries, Invoice, InvoiceEvent
from app.modules.billing.interfaces.repository import BillingRepositoryInterface
from app.modules.coin.domain.models import TaxRate
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
        self, document_type: str, series: str, environment: str
    ) -> BillingSeries:
        # Alta idempotente de la fila: dos procesos pueden intentar crearla a la vez.
        await self.session.execute(
            text(
                'INSERT INTO "billing".series '
                "(id, document_type, series, environment, last_number, is_active, deleted, enable) "
                "VALUES (:id, :document_type, :series, :environment, 0, true, false, true) "
                "ON CONFLICT ON CONSTRAINT uq_billing_series DO NOTHING"
            ),
            {
                "id": uuid.uuid4(),
                "document_type": document_type,
                "series": series,
                "environment": environment,
            },
        )
        stmt = (
            select(BillingSeries)
            .where(
                BillingSeries.document_type == document_type,
                BillingSeries.series == series,
                BillingSeries.environment == environment,
            )
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def reserve_next_number(self, document_type: str, series: str, environment: str) -> int:
        row = await self._series_row_for_update(document_type, series, environment)
        if not row.is_active:
            raise ValueError(f"La serie {series} ({document_type}) está inactiva")
        row.last_number = int(row.last_number or 0) + 1
        await self.session.flush()
        return row.last_number

    async def list_series(self, environment: str) -> list[BillingSeries]:
        stmt = (
            select(BillingSeries)
            .where(BillingSeries.environment == environment, BillingSeries.deleted.is_(False))
            .order_by(BillingSeries.document_type, BillingSeries.series)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def set_last_number(
        self, document_type: str, series: str, environment: str, last_number: int
    ) -> BillingSeries:
        row = await self._series_row_for_update(document_type, series, environment)
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

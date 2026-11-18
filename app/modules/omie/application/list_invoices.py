"""Read persisted Omie NFS-e attempts without making remote API calls."""
from datetime import datetime

from sqlalchemy import func, select

from app.modules.omie.domain.models import OmieInvoice
from app.modules.transactions.domain.models import Transaction
from app.modules.omie.application.description import saved_description


def invoice_list_item(invoice: OmieInvoice, transaction_code: str) -> dict:
    snapshot = invoice.snapshot or {}
    return {
        "transaction_id": str(invoice.transaction_id),
        "transaction_code": transaction_code,
        "status": invoice.status,
        "total": str(invoice.total),
        "currency": "BRL",
        "os_id": invoice.os_id,
        "issued_at": snapshot.get("issued_at"),
        "nfse_number": invoice.nfse_number,
        "customer": snapshot.get("customer", ""),
        "document": snapshot.get("document", ""),
        "issuer": snapshot.get("issuer", ""),
        "service": snapshot.get("service", ""),
        "description": saved_description(snapshot),
        "error": invoice.error,
        "created_at": invoice.created_at.isoformat(),
    }


async def list_invoices(db, *, page: int, page_size: int, status: str | None,
                        date_from: datetime | None, date_to: datetime | None) -> dict:
    conditions = []
    if status:
        conditions.append(OmieInvoice.status == status)
    if date_from:
        conditions.append(OmieInvoice.created_at >= date_from)
    if date_to:
        conditions.append(OmieInvoice.created_at <= date_to)

    total = (await db.execute(select(func.count()).select_from(OmieInvoice).where(*conditions))).scalar_one()
    rows = (await db.execute(
        select(OmieInvoice, Transaction.code)
        .join(Transaction, Transaction.id == OmieInvoice.transaction_id)
        .where(*conditions)
        .order_by(OmieInvoice.created_at.desc(), OmieInvoice.transaction_id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    return {"items": [invoice_list_item(invoice, code) for invoice, code in rows],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size)}


async def records_for_transactions(db, transaction_ids):
    rows = (await db.execute(select(OmieInvoice).where(
        OmieInvoice.transaction_id.in_(transaction_ids)
    ))).scalars().all()
    from app.modules.omie.application.service import public_record
    return {str(row.transaction_id): public_record(row) for row in rows}

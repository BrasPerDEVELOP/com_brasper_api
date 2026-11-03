"""El PDF se envía una sola vez después de que SUNAT acepta el comprobante."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.billing.application import use_cases


@pytest.mark.asyncio
async def test_delivery_claims_accepted_invoice_once(monkeypatch):
    invoice = SimpleNamespace(
        id=uuid4(), issuer_ruc="20608550454", customer_email="cliente@example.com",
        full_number="BB02-00000001",
    )
    repo = SimpleNamespace(
        list_pending_emails=AsyncMock(return_value=[invoice]),
        claim_invoice_email=AsyncMock(side_effect=[True, False]),
        complete_invoice_email=AsyncMock(), add_event=AsyncMock(), commit=AsyncMock(),
    )
    pdf = AsyncMock(return_value=(b"%PDF-1.7\n", "boleta.pdf"))
    monkeypatch.setattr(use_cases.GetInvoicePdfUseCase, "execute", pdf)
    sent = []
    monkeypatch.setattr(use_cases, "send_invoice_pdf", lambda *args, **kwargs: sent.append(kwargs))
    settings = SimpleNamespace(billing_issuer=lambda ruc: SimpleNamespace(display_name="BRASPER 21 S.A.C."))
    delivery = use_cases.DeliverPendingInvoiceEmailsUseCase(repo, None, settings)

    assert await delivery.execute() == 1
    assert len(sent) == 1
    assert sent[0]["recipient"] == "cliente@example.com"
    repo.complete_invoice_email.assert_awaited_once_with(invoice.id, sent=True)
    assert await delivery.execute() == 0
    assert len(sent) == 1

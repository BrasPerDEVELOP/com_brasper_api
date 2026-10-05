"""Contrato HTTP de /billing: permisos catalogados, 503 con el módulo apagado y respuestas."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.db.base import get_db
from app.main import app
from app.modules.auth.domain.permissions import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from app.modules.billing.adapters.dependencies import (
    billing_status_uc,
    get_invoice_uc,
    issue_invoice_uc,
    list_invoices_uc,
    require_billing_enabled,
)
from app.modules.billing.application.schemas import BillingStatusDTO, InvoiceDTO, InvoiceListDTO
from app.modules.billing.application.use_cases import BillingDisabledError


def _invoice_dto(**overrides) -> InvoiceDTO:
    data = dict(
        id=uuid4(),
        transaction_id=uuid4(),
        document_type="03",
        document_type_label="Boleta de venta",
        series="B001",
        number=1,
        full_number="B001-00000001",
        file_name="20608550454-03-B001-00000001",
        environment="development",
        currency="PEN",
        taxable_amount=33.9,
        igv_amount=6.1,
        total_amount=40.0,
        igv_rate=0.18,
        customer_doc_type="1",
        customer_doc_number="45678912",
        customer_name="MARIA PEREZ",
        status="sent",
        issue_date=datetime(2026, 10, 3, tzinfo=timezone.utc),
        apisunat_document_id="doc-1",
        sunat_status="PENDIENTE",
    )
    data.update(overrides)
    return InvoiceDTO(**data)


def _db_mock():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def test_billing_permissions_are_catalogued():
    for permission in ("billing.view", "billing.issue", "billing.void"):
        assert permission in ALL_PERMISSIONS
    accounting = DEFAULT_ROLE_PERMISSIONS["accounting"]
    assert "billing.view" in accounting and "billing.issue" in accounting
    assert "billing.void" not in accounting  # anular queda en admin hasta nuevo aviso
    assert "billing.issue" not in DEFAULT_ROLE_PERMISSIONS["sales"]


def test_issue_responds_503_when_billing_is_disabled():
    settings = get_settings()
    previous = settings.BILLING_ENABLED
    settings.BILLING_ENABLED = False
    app.dependency_overrides[get_db] = _db_mock
    try:
        client = TestClient(app)
        response = client.post(f"/billing/transactions/{uuid4()}/issue")
        assert response.status_code == 503
        assert "BILLING_ENABLED" in response.json()["detail"]
    finally:
        settings.BILLING_ENABLED = previous
        app.dependency_overrides.pop(get_db, None)


def test_billing_endpoints_contract():
    dto = _invoice_dto()
    status_uc = MagicMock()
    status_uc.execute = AsyncMock(
        return_value=BillingStatusDTO(
            enabled=True,
            auto_issue=False,
            environment="development",
            is_production=False,
            issuer_ruc="20608550454",
            issuer_name="BRASPER 21 S.A.C.",
            series_boleta="B001",
            series_factura="F001",
            commission_includes_igv=True,
            igv_rate=0.18,
        )
    )
    list_uc = MagicMock()
    list_uc.execute = AsyncMock(return_value=InvoiceListDTO(items=[dto], total=1, skip=0, limit=50))
    get_uc = MagicMock()
    get_uc.execute = AsyncMock(return_value=dto)
    get_uc.for_transaction = AsyncMock(return_value=None)
    issue_uc = MagicMock()
    issue_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_db] = _db_mock
    app.dependency_overrides[billing_status_uc] = lambda: status_uc
    app.dependency_overrides[list_invoices_uc] = lambda: list_uc
    app.dependency_overrides[get_invoice_uc] = lambda: get_uc
    app.dependency_overrides[issue_invoice_uc] = lambda: issue_uc
    app.dependency_overrides[require_billing_enabled] = lambda: None
    try:
        client = TestClient(app)

        response = client.get("/billing/status")
        assert response.status_code == 200
        assert response.json()["series_boleta"] == "B001"

        response = client.get("/billing/invoices", params={"status": "sent", "limit": 10})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1 and body["items"][0]["full_number"] == "B001-00000001"
        assert list_uc.execute.await_args.kwargs["status"] == "sent"
        assert list_uc.execute.await_args.kwargs["limit"] == 10

        response = client.get("/billing/invoices", params={"document_type": "99"})
        assert response.status_code == 422

        response = client.get(f"/billing/invoices/{dto.id}")
        assert response.status_code == 200 and response.json()["status"] == "sent"

        response = client.get(f"/billing/transactions/{dto.transaction_id}/invoice")
        assert response.status_code == 404

        response = client.post(
            f"/billing/transactions/{dto.transaction_id}/issue",
            json={"customer_name": "Acme SAC"},
        )
        assert response.status_code == 201
        assert response.json()["file_name"] == dto.file_name
        args, kwargs = issue_uc.execute.await_args
        assert args[0] == dto.transaction_id and args[1].customer_name == "Acme SAC"

        issue_uc.execute = AsyncMock(side_effect=ValueError("La operación ya tiene el comprobante"))
        response = client.post(f"/billing/transactions/{dto.transaction_id}/issue")
        assert response.status_code == 400

        issue_uc.execute = AsyncMock(side_effect=LookupError("Operación no encontrada"))
        response = client.post(f"/billing/transactions/{uuid4()}/issue")
        assert response.status_code == 404

        issue_uc.execute = AsyncMock(side_effect=BillingDisabledError("apagado"))
        response = client.post(f"/billing/transactions/{uuid4()}/issue")
        assert response.status_code == 503

        response = client.post(f"/billing/invoices/{dto.id}/void", json={"reason": "no"})
        assert response.status_code == 422  # motivo de al menos 3 caracteres
    finally:
        for dep in (get_db, billing_status_uc, list_invoices_uc, get_invoice_uc, issue_invoice_uc, require_billing_enabled):
            app.dependency_overrides.pop(dep, None)

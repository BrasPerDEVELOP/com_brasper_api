"""Casos de uso de facturación: emisión, reintentos, consulta de estado y anulación."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional, Sequence
from uuid import UUID, uuid4

import pytest

from app.core.settings import get_settings
from app.modules.billing.application.schemas import IssueInvoiceCmd
from app.modules.billing.application.triggers import should_auto_issue
from app.modules.billing.application.use_cases import (
    AlignSeriesUseCase,
    BillingDisabledError,
    IssueInvoiceUseCase,
    PollInvoiceUseCase,
    PollPendingInvoicesUseCase,
    RetryInvoiceUseCase,
    VoidInvoiceUseCase,
    resolve_customer,
)
from app.modules.billing.domain.enums import OPEN_INVOICE_STATUSES, BillingDocumentType, InvoiceStatus
from app.modules.billing.domain.models import BillingSeries, Invoice, InvoiceEvent
from app.modules.billing.interfaces.apisunat_client import (
    ApisunatClientInterface,
    ApisunatError,
    ApisunatTimeout,
    DocumentInfo,
    SendBillResult,
)
from app.modules.billing.interfaces.repository import BillingRepositoryInterface
from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import TransactionStatus


# --- Dobles ----------------------------------------------------------------
def _user(document_type="dni", document_number="45678912", names="María", lastnames="Pérez", email="m@x.pe"):
    return SimpleNamespace(
        document_type=document_type, document_number=document_number, names=names, lastnames=lastnames, email=email
    )


def _transaction(status=TransactionStatus.completed, commission_result=40.0, user=None, code="PEN-BRL-000123"):
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        commission_result=commission_result,
        payment_date=datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc),
        tax_rate_id=uuid4(),
        code=code,
        user=user or _user(),
    )


class FakeRepo(BillingRepositoryInterface):
    def __init__(self, transaction, currency=Currency.pen):
        self.transaction = transaction
        self.tax_rate = SimpleNamespace(coin_a=currency)
        self.invoices: list[Invoice] = []
        self.events: list[InvoiceEvent] = []
        self.series: dict[tuple[str, str, str], BillingSeries] = {}
        self.billing_dates: dict[UUID, datetime] = {}
        self.commits = 0

    async def get_transaction_for_billing(self, transaction_id):
        return self.transaction if self.transaction.id == transaction_id else None

    async def get_tax_rate(self, tax_rate_id):
        return self.tax_rate

    async def set_transaction_billing_date(self, transaction_id, value):
        self.billing_dates.setdefault(transaction_id, value)

    async def reserve_next_number(self, document_type, series, environment):
        row = self.series.setdefault(
            (document_type, series, environment),
            BillingSeries(document_type=document_type, series=series, environment=environment, last_number=0),
        )
        row.last_number += 1
        return row.last_number

    async def list_series(self, environment):
        return [r for r in self.series.values() if r.environment == environment]

    async def set_last_number(self, document_type, series, environment, last_number):
        row = self.series.setdefault(
            (document_type, series, environment),
            BillingSeries(document_type=document_type, series=series, environment=environment, last_number=0),
        )
        row.last_number = last_number
        return row

    async def get_invoice(self, invoice_id):
        return next((i for i in self.invoices if i.id == invoice_id), None)

    async def get_open_invoice(self, transaction_id):
        return next(
            (i for i in reversed(self.invoices) if i.transaction_id == transaction_id and i.status in OPEN_INVOICE_STATUSES),
            None,
        )

    async def get_latest_invoice(self, transaction_id):
        return next((i for i in reversed(self.invoices) if i.transaction_id == transaction_id), None)

    async def list_invoices(self, *, status=None, document_type=None, transaction_id=None, date_from=None, date_to=None, skip=0, limit=50):
        items = [i for i in self.invoices if (status is None or i.status == status)]
        return items[skip : skip + limit], len(items)

    async def list_by_status(self, statuses: Sequence[str], *, limit=50):
        return [i for i in self.invoices if i.status in statuses][:limit]

    async def list_events(self, invoice_id):
        return [e for e in self.events if e.invoice_id == invoice_id]

    async def add_invoice(self, entity):
        entity.id = entity.id or uuid4()
        self.invoices.append(entity)
        return entity

    async def add_event(self, invoice_id, event, payload=None):
        e = InvoiceEvent(invoice_id=invoice_id, event=event, payload=payload)
        e.id = uuid4()
        self.events.append(e)
        return e

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    async def refresh(self, entity):
        pass

    def event_names(self, invoice_id):
        return [e.event for e in self.events if e.invoice_id == invoice_id]


class FakeClient(ApisunatClientInterface):
    def __init__(self):
        self.send_results: list = []
        self.sent: list[dict] = []
        self.by_id: dict[str, DocumentInfo] = {}
        self.found: Optional[DocumentInfo] = None
        self.pdf = b"%PDF-1.4 fake"
        self.pdf_requests = 0
        self.void_result = SendBillResult(status="PENDIENTE", document_id="void-1", raw={})
        self.voided: list[dict] = []
        self.last = {"lastNumber": 0}

    async def send_bill(self, **kwargs):
        self.sent.append(kwargs)
        result = self.send_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def get_by_id(self, document_id):
        info = self.by_id[document_id]
        if isinstance(info, Exception):
            raise info
        return info

    async def find_by_file_name(self, file_name):
        return self.found

    async def get_pdf(self, document_id, *, pdf_format, file_name):
        self.pdf_requests += 1
        return self.pdf

    async def void_bill(self, *, document_id, reason):
        self.voided.append({"document_id": document_id, "reason": reason})
        return self.void_result

    async def last_document(self, *, document_type, series):
        return self.last


class FakeFileService:
    def __init__(self):
        self.saved: dict[str, bytes] = {}

    async def save_raw(self, key, content):
        self.saved[key] = content
        return key

    async def read_file(self, key):
        return (self.saved[key], "application/pdf") if key in self.saved else None


def _settings(**overrides):
    base = {
        "BILLING_ENABLED": True,
        "BILLING_AUTO_ISSUE": False,
        "BILLING_COMMISSION_INCLUDES_IGV": True,
        "BILLING_IGV_RATE": 0.18,
        "APISUNAT_PERSONA_ID": "persona",
        "APISUNAT_PERSONA_TOKEN": "token",
        "APISUNAT_ENVIRONMENT": "development",
        "BILLING_SERIES_BOLETA": "B001",
        "BILLING_SERIES_FACTURA": "F001",
        "BILLING_ISSUER_RUC": "20608550454",
        "BILLING_SEND_CUSTOMER_EMAIL": False,
        "BILLING_START_DATE": "",
    }
    base.update(overrides)
    return get_settings().model_copy(update=base)


PENDING = SendBillResult(status="PENDIENTE", document_id="doc-1", raw={"status": "PENDIENTE", "documentId": "doc-1"})


# --- resolve_customer ------------------------------------------------------
def test_dni_da_boleta_y_ruc_da_factura():
    doc_type, customer = resolve_customer(None, _user(), None)
    assert doc_type is BillingDocumentType.boleta
    assert (customer.doc_type, customer.doc_number, customer.name) == ("1", "45678912", "MARÍA PÉREZ")

    doc_type, customer = resolve_customer(None, _user("ruc", "20123456789", names="ACME S.A.C.", lastnames=""), None)
    assert doc_type is BillingDocumentType.factura
    assert customer.doc_type == "6" and customer.name == "ACME S.A.C."


def test_ruc_sin_razon_social_falla_y_cmd_la_completa():
    user = _user("ruc", "20123456789", names="", lastnames="")
    with pytest.raises(ValueError, match="razón social"):
        resolve_customer(None, user, None)
    _, customer = resolve_customer(None, user, IssueInvoiceCmd(customer_name="Acme SAC", customer_address="Jr. Lima 1"))
    assert customer.name == "ACME SAC" and customer.address == "Jr. Lima 1"


def test_cpf_y_pasaporte_van_sin_documento_o_con_codigo_7():
    _, cpf = resolve_customer(None, _user("cpf", "12345678901", names="João", lastnames="Silva"), None)
    assert cpf.doc_type == "0" and cpf.doc_number == "12345678901"
    _, passport = resolve_customer(None, _user("passport", "AB123", names="John", lastnames="Doe"), None)
    assert passport.doc_type == "7"
    _, nobody = resolve_customer(None, _user("other", None, names="", lastnames=""), None)
    assert (nobody.doc_type, nobody.doc_number, nobody.name) == ("0", "-", "CLIENTE")


# --- Emisión ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_emite_boleta_reserva_numero_y_queda_enviada():
    tx = _transaction()
    repo, client = FakeRepo(tx), FakeClient()
    client.send_results = [PENDING]

    dto = await IssueInvoiceUseCase(repo, client, _settings()).execute(tx.id, actor="tester@brasper.com")

    assert dto.document_type == "03" and dto.series == "B001" and dto.number == 1
    assert dto.file_name == "20608550454-03-B001-00000001"
    assert dto.status == InvoiceStatus.sent.value and dto.apisunat_document_id == "doc-1"
    assert (dto.taxable_amount, dto.igv_amount, dto.total_amount) == (33.90, 6.10, 40.00)
    assert dto.currency == "PEN" and dto.environment == "development"
    assert repo.billing_dates[tx.id] is not None
    assert repo.event_names(dto.id) == ["reserved", "sent"]
    # El commit de la reserva ocurre ANTES del envío y hay otro tras la respuesta.
    assert repo.commits == 2
    sent = client.sent[0]
    assert sent["file_name"] == dto.file_name and sent["customer_email"] is None
    assert sent["document_body"]["cbc:ID"]["_text"] == "B001-00000001"


@pytest.mark.asyncio
async def test_emite_factura_en_dolares_a_cliente_con_ruc():
    tx = _transaction(user=_user("ruc", "20123456789", names="ACME S.A.C.", lastnames=""), commission_result=118.0)
    repo, client = FakeRepo(tx, currency=Currency.usd), FakeClient()
    client.send_results = [PENDING]
    dto = await IssueInvoiceUseCase(repo, client, _settings()).execute(tx.id)
    assert dto.document_type == "01" and dto.series == "F001" and dto.currency == "USD"
    assert (dto.taxable_amount, dto.igv_amount, dto.total_amount) == (100.0, 18.0, 118.0)


@pytest.mark.asyncio
async def test_no_emite_si_no_esta_completada_o_sin_comision_o_ya_tiene_comprobante():
    settings = _settings()
    tx = _transaction(status=TransactionStatus.verified)
    with pytest.raises(ValueError, match="completadas"):
        await IssueInvoiceUseCase(FakeRepo(tx), FakeClient(), settings).execute(tx.id)

    tx = _transaction(commission_result=0)
    with pytest.raises(ValueError, match="comisión"):
        await IssueInvoiceUseCase(FakeRepo(tx), FakeClient(), settings).execute(tx.id)

    tx = _transaction()
    repo, client = FakeRepo(tx), FakeClient()
    client.send_results = [PENDING]
    await IssueInvoiceUseCase(repo, client, settings).execute(tx.id)
    with pytest.raises(ValueError, match="ya tiene el comprobante B001-00000001"):
        await IssueInvoiceUseCase(repo, client, settings).execute(tx.id)

    with pytest.raises(LookupError):
        await IssueInvoiceUseCase(repo, client, settings).execute(uuid4())


@pytest.mark.asyncio
async def test_fecha_de_corte_y_modulo_apagado():
    tx = _transaction()
    with pytest.raises(ValueError, match="fecha de corte"):
        await IssueInvoiceUseCase(FakeRepo(tx), FakeClient(), _settings(BILLING_START_DATE="2026-11-01")).execute(tx.id)
    with pytest.raises(BillingDisabledError):
        await IssueInvoiceUseCase(FakeRepo(tx), FakeClient(), _settings(BILLING_ENABLED=False)).execute(tx.id)


@pytest.mark.asyncio
async def test_error_de_apisunat_conserva_el_numero_y_el_reintento_lo_reutiliza():
    tx = _transaction()
    repo, client = FakeRepo(tx), FakeClient()
    client.send_results = [
        SendBillResult(status="ERROR", error={"message": "token inválido"}, raw={"status": "ERROR"}),
        PENDING,
    ]
    settings = _settings()
    dto = await IssueInvoiceUseCase(repo, client, settings).execute(tx.id)
    assert dto.status == InvoiceStatus.error.value and "token inválido" in dto.last_error
    assert dto.attempts == 1

    retried = await RetryInvoiceUseCase(repo, client, settings).execute(dto.id, actor="x")
    assert retried.id == dto.id and retried.file_name == dto.file_name
    assert retried.status == InvoiceStatus.sent.value and retried.attempts == 2
    assert repo.event_names(dto.id) == ["reserved", "send_failed", "retry", "sent"]


@pytest.mark.asyncio
async def test_timeout_busca_el_documento_antes_de_darlo_por_perdido():
    tx = _transaction()
    repo, client = FakeRepo(tx), FakeClient()
    client.send_results = [ApisunatTimeout("timeout")]
    client.found = DocumentInfo(document_id="doc-recuperado", status="PENDIENTE", file_name="20608550454-03-B001-00000001")
    dto = await IssueInvoiceUseCase(repo, client, _settings()).execute(tx.id)
    assert dto.status == InvoiceStatus.sent.value and dto.apisunat_document_id == "doc-recuperado"

    tx2 = _transaction()
    repo2, client2 = FakeRepo(tx2), FakeClient()
    client2.send_results = [ApisunatTimeout("timeout")]
    dto2 = await IssueInvoiceUseCase(repo2, client2, _settings()).execute(tx2.id)
    assert dto2.status == InvoiceStatus.error.value


# --- Consulta de estado ----------------------------------------------------
async def _sent_invoice(repo, client, settings):
    client.send_results = [PENDING]
    dto = await IssueInvoiceUseCase(repo, client, settings).execute(repo.transaction.id)
    return await repo.get_invoice(dto.id)


@pytest.mark.asyncio
async def test_aceptado_guarda_enlaces_y_pdf_en_r2():
    tx = _transaction()
    repo, client, files, settings = FakeRepo(tx), FakeClient(), FakeFileService(), _settings()
    invoice = await _sent_invoice(repo, client, settings)
    client.by_id["doc-1"] = DocumentInfo(
        document_id="doc-1", status="ACEPTADO", xml_url="https://x/xml", cdr_url="https://x/cdr", notes=["obs 4252"]
    )

    changed = await PollPendingInvoicesUseCase(PollInvoiceUseCase(repo, client, settings, files), repo).execute()

    assert changed == 1
    assert invoice.status == InvoiceStatus.accepted.value and invoice.sunat_status == "ACEPTADO"
    assert invoice.xml_url == "https://x/xml" and invoice.cdr_url == "https://x/cdr" and invoice.notes == ["obs 4252"]
    assert invoice.pdf_key == f"invoices/{invoice.issue_date.year}/{invoice.file_name}.pdf"
    assert files.saved[invoice.pdf_key] == client.pdf
    assert repo.event_names(invoice.id) == ["reserved", "sent", "accepted", "pdf_stored"]


@pytest.mark.asyncio
async def test_rechazado_consume_numero_y_el_reintento_emite_el_siguiente():
    tx = _transaction()
    repo, client, settings = FakeRepo(tx), FakeClient(), _settings()
    invoice = await _sent_invoice(repo, client, settings)
    client.by_id["doc-1"] = DocumentInfo(document_id="doc-1", status="RECHAZADO", faults=[{"code": "2017", "message": "RUC inválido"}])
    await PollInvoiceUseCase(repo, client, settings).execute(invoice)
    assert invoice.status == InvoiceStatus.rejected.value and "2017" in invoice.last_error

    client.send_results = [SendBillResult(status="PENDIENTE", document_id="doc-2", raw={})]
    retried = await RetryInvoiceUseCase(repo, client, settings).execute(invoice.id)
    assert retried.id != invoice.id and retried.number == 2
    assert retried.file_name == "20608550454-03-B001-00000002" and retried.status == InvoiceStatus.sent.value
    assert invoice.status == InvoiceStatus.rejected.value  # el rechazado se conserva


@pytest.mark.asyncio
async def test_excepcion_reenvia_con_el_mismo_numero_y_pendiente_no_cambia():
    tx = _transaction()
    repo, client, settings = FakeRepo(tx), FakeClient(), _settings()
    invoice = await _sent_invoice(repo, client, settings)

    client.by_id["doc-1"] = DocumentInfo(document_id="doc-1", status="PENDIENTE")
    await PollInvoiceUseCase(repo, client, settings).execute(invoice)
    assert invoice.status == InvoiceStatus.sent.value and invoice.last_polled_at is not None

    client.by_id["doc-1"] = DocumentInfo(document_id="doc-1", status="EXCEPCION", faults=[{"code": "3033"}])
    await PollInvoiceUseCase(repo, client, settings).execute(invoice)
    assert invoice.status == InvoiceStatus.exception.value

    client.send_results = [SendBillResult(status="PENDIENTE", document_id="doc-3", raw={})]
    retried = await RetryInvoiceUseCase(repo, client, settings).execute(invoice.id)
    assert retried.id == invoice.id and retried.number == 1 and retried.apisunat_document_id == "doc-3"


@pytest.mark.asyncio
async def test_fallo_de_red_al_consultar_no_cambia_el_estado():
    tx = _transaction()
    repo, client, settings = FakeRepo(tx), FakeClient(), _settings()
    invoice = await _sent_invoice(repo, client, settings)
    client.by_id["doc-1"] = ApisunatError("caído")
    await PollInvoiceUseCase(repo, client, settings).execute(invoice)
    assert invoice.status == InvoiceStatus.sent.value and invoice.last_error == "caído"


# --- Anulación -------------------------------------------------------------
@pytest.mark.asyncio
async def test_anula_solo_comprobantes_aceptados():
    tx = _transaction()
    repo, client, settings = FakeRepo(tx), FakeClient(), _settings()
    invoice = await _sent_invoice(repo, client, settings)
    with pytest.raises(ValueError, match="aceptado"):
        await VoidInvoiceUseCase(repo, client, settings).execute(invoice.id, "Error en el monto")

    client.by_id["doc-1"] = DocumentInfo(document_id="doc-1", status="ACEPTADO")
    await PollInvoiceUseCase(repo, client, settings).execute(invoice)
    dto = await VoidInvoiceUseCase(repo, client, settings).execute(invoice.id, "Error en el monto", actor="admin")
    assert dto.status == InvoiceStatus.voided.value and dto.void_reason == "Error en el monto"
    assert client.voided == [{"document_id": "doc-1", "reason": "Error en el monto"}]
    # Anulado deja de ser "vivo": la operación puede volver a facturarse.
    assert await repo.get_open_invoice(tx.id) is None


# --- Series y disparador ---------------------------------------------------
@pytest.mark.asyncio
async def test_alinear_series_nunca_retrocede():
    tx = _transaction()
    repo, client, settings = FakeRepo(tx), FakeClient(), _settings()
    await repo.set_last_number("03", "B001", "development", 10)
    client.last = {"suggestedNumber": 8}  # APISUNAT va por el 7 → local sigue en 10
    result = await AlignSeriesUseCase(repo, client, settings).execute()
    boleta = next(r for r in result if r.document_type == "03")
    assert (boleta.previous_last_number, boleta.apisunat_last_number, boleta.new_last_number) == (10, 7, 10)
    factura = next(r for r in result if r.document_type == "01")
    assert factura.new_last_number == 7


def test_should_auto_issue_respeta_configuracion_y_transicion(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    monkeypatch.setattr(settings, "BILLING_AUTO_ISSUE", True)
    assert should_auto_issue(TransactionStatus.verified, TransactionStatus.completed)
    assert should_auto_issue(None, TransactionStatus.completed)
    assert not should_auto_issue(TransactionStatus.completed, TransactionStatus.completed)
    assert not should_auto_issue(TransactionStatus.verified, TransactionStatus.verified)
    monkeypatch.setattr(settings, "BILLING_AUTO_ISSUE", False)
    assert not should_auto_issue(TransactionStatus.verified, TransactionStatus.completed)

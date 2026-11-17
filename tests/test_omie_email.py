from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest

from app.modules.omie.application import email_delivery as module
from app.modules.omie.infrastructure import pdf as pdf_module


def fixture_service():
    row = SimpleNamespace(transaction_id=uuid4(), status="issued", nfse_id=42, nfse_number="16298",
                          snapshot={"issuer": "BRASPER"}, email_status=None, email_error=None, email_recipients=[],
                          email_delivered_to=[], email_sent_at=None)
    repo = SimpleNamespace(get=AsyncMock(return_value=row), contacts=AsyncMock(return_value=["client@example.com"]),
                           queue=AsyncMock(return_value=True), pending=AsyncMock(return_value=[row.transaction_id]),
                           claim=AsyncMock(return_value=True), delivered=AsyncMock(), complete=AsyncMock())
    settings = SimpleNamespace(SMTP_HOST="smtp.example.com", SMTP_USERNAME="test", SMTP_PASSWORD="test",
                               SMTP_FROM_EMAIL="sender@example.com", SMTP_USE_TLS=True)
    billing = SimpleNamespace(pdf=AsyncMock(return_value={"url": "https://click.omie.com/note.pdf"}))
    return module.OmieEmailService(None, settings, repo=repo, billing=billing), row, repo


@pytest.mark.asyncio
async def test_request_prefills_contacts_and_does_not_call_omie_or_change_customer():
    service, row, repo = fixture_service()
    data = await service.request(row.transaction_id, None)
    assert data["customer_emails"] == ["client@example.com"]
    repo.queue.assert_awaited_once_with(row.transaction_id, ["client@example.com"])
    service.billing.pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_normalizes_and_excludes_already_delivered():
    service, row, repo = fixture_service()
    row.email_delivered_to = ["client@example.com"]
    await service.request(row.transaction_id, ["CLIENT@example.com", " other@example.com ", "other@example.com"])
    repo.queue.assert_awaited_once_with(row.transaction_id, ["other@example.com"])


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "cancelled", "review_required"])
async def test_unissued_notes_never_queue(status):
    service, row, repo = fixture_service()
    row.status = status
    with pytest.raises(ValueError, match="emitida"):
        await service.request(row.transaction_id, ["client@example.com"])
    repo.queue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("recipients", [[], ["invalid"], [f"user{i}@example.com" for i in range(21)]])
async def test_invalid_recipients_never_queue(recipients):
    service, row, repo = fixture_service()
    with pytest.raises(ValueError):
        await service.request(row.transaction_id, recipients)
    repo.queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_request_is_rejected():
    service, row, repo = fixture_service()
    repo.queue.return_value = False
    with pytest.raises(ValueError, match="en curso"):
        await service.request(row.transaction_id, ["client@example.com"])


@pytest.mark.asyncio
async def test_worker_sends_individual_pdf_and_skips_delivered(monkeypatch):
    service, row, repo = fixture_service()
    row.email_recipients = ["one@example.com", "TWO@example.com", "three@example.com"]
    row.email_delivered_to = ["two@example.com"]
    monkeypatch.setattr(module, "download_pdf", AsyncMock(return_value=b"%PDF-1.7\n"))
    sender = Mock()
    monkeypatch.setattr(module, "send_invoice_pdf", sender)
    assert await service.deliver_pending() == 1
    assert [call.kwargs["recipient"] for call in sender.call_args_list] == ["one@example.com", "three@example.com"]
    assert sender.call_args.kwargs["pdf"].startswith(b"%PDF-")
    assert sender.call_args.kwargs["full_number"] == "NFS-e 16298"
    assert repo.delivered.await_count == 2
    repo.complete.assert_awaited_once_with(row, "sent")


@pytest.mark.asyncio
async def test_second_worker_cannot_send_claimed_job(monkeypatch):
    service, _, repo = fixture_service()
    repo.claim.return_value = False
    sender = Mock()
    monkeypatch.setattr(module, "send_invoice_pdf", sender)
    assert await service.deliver_pending() == 0
    sender.assert_not_called()
    service.billing.pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_failure_preserves_successful_recipients(monkeypatch):
    service, row, repo = fixture_service()
    row.email_recipients = ["one@example.com", "two@example.com"]
    monkeypatch.setattr(module, "download_pdf", AsyncMock(return_value=b"%PDF-1.7\n"))
    sender = Mock(side_effect=[None, RuntimeError("SMTP failure")])
    monkeypatch.setattr(module, "send_invoice_pdf", sender)
    assert await service.deliver_pending() == 0
    repo.delivered.assert_awaited_once_with(row, "one@example.com")
    repo.complete.assert_awaited_once_with(row, "failed", error="No se pudo entregar el correo. Intenta más tarde.")


@pytest.mark.asyncio
async def test_persistence_failure_after_smtp_does_not_release_claim(monkeypatch):
    service, row, repo = fixture_service()
    row.email_recipients = ["one@example.com"]
    repo.delivered.side_effect = RuntimeError("database failure")
    monkeypatch.setattr(module, "download_pdf", AsyncMock(return_value=b"%PDF-1.7\n"))
    monkeypatch.setattr(module, "send_invoice_pdf", Mock())
    with pytest.raises(RuntimeError, match="database"):
        await service.deliver_pending()
    repo.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelled_after_queue_is_not_sent(monkeypatch):
    service, row, repo = fixture_service()
    row.status = "cancelled"
    sender = Mock()
    monkeypatch.setattr(module, "send_invoice_pdf", sender)
    await service.deliver_pending()
    sender.assert_not_called()
    repo.complete.assert_awaited_once_with(row, "failed", error="La nota fiscal ya no está emitida")


@pytest.mark.asyncio
async def test_pdf_download_validates_each_redirect_and_file():
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
    with pytest.raises(ValueError, match="enlace"):
        await pdf_module.download_pdf("https://click.omie.com/pdf", transport=httpx.MockTransport(respond))
    assert len(calls) == 1
    with pytest.raises(ValueError, match="PDF válido"):
        await pdf_module.download_pdf("https://click.omie.com/pdf", transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"<html>Login</html>")))


@pytest.mark.asyncio
async def test_pdf_download_follows_official_omie_cdn_redirect():
    def respond(request):
        if request.url.host == "click.omie.com":
            return httpx.Response(302, headers={"location": "https://cdn.omie.com.br/nfse.pdf"})
        assert request.url.host == "cdn.omie.com.br"
        return httpx.Response(200, content=b"%PDF-1.7\n")
    assert await pdf_module.download_pdf("https://click.omie.com/pdf", transport=httpx.MockTransport(respond)) == b"%PDF-1.7\n"


@pytest.mark.asyncio
async def test_pdf_download_is_bounded_and_sends_no_credentials(monkeypatch):
    def respond(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, content=b"%PDF-1.7\nhello")
    transport = httpx.MockTransport(respond)
    assert await pdf_module.download_pdf("https://app.omie.com.br/pdf", transport=transport) == b"%PDF-1.7\nhello"
    monkeypatch.setattr(pdf_module, "MAX_PDF_BYTES", 10)
    with pytest.raises(ValueError, match="tamaño"):
        await pdf_module.download_pdf("https://app.omie.com.br/pdf", transport=transport)

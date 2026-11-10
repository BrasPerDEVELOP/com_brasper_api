from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZipFile
import httpx
import pytest
from app.modules.billing.application.monthly_export import export_month

@pytest.mark.asyncio
async def test_month_export_contains_three_files_and_uses_lima_month(monkeypatch):
    invoice = SimpleNamespace(id='1', issuer_ruc='20611936428', file_name='20611936428-03-BB02-00000007', status='accepted', xml_url='https://cdn.apisunat.com/document.xml', cdr_url='https://cdn.apisunat.com/cdr.zip')
    repo = SimpleNamespace(list_invoices=AsyncMock(return_value=([invoice], 1)))
    pdf = SimpleNamespace(execute=AsyncMock(return_value=(b'%PDF-test', invoice.file_name+'.pdf')))
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url): return SimpleNamespace(content=bytes.fromhex('504b0304')+b'test' if url.endswith('.zip') else b'<xml/>', raise_for_status=lambda: None)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Client())
    data = await export_month(repo, pdf, 2026, 11, '20611936428')
    with ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        assert len(names) == 3
        assert any(name.endswith('.pdf') for name in names)
        assert any(name.endswith('-XML.xml') for name in names)
        assert any(name.endswith('-CDR.zip') for name in names)
    filters = repo.list_invoices.call_args.kwargs
    assert filters['date_from'].isoformat() == '2026-11-01T00:00:00-05:00'
    assert filters['date_to'].isoformat() == '2026-12-01T00:00:00-05:00'

from unittest.mock import AsyncMock
import pytest
from app.modules.billing.adapters.router import list_invoices
from app.modules.billing.application.schemas import InvoiceListDTO

@pytest.mark.asyncio
async def test_invoice_pages_translate_to_database_offset():
    uc = AsyncMock()
    await list_invoices(uc, status_filter='accepted', document_type=None,
                        transaction_id=None, issuer_ruc=None, date_from=None, date_to=None,
                        skip=0, limit=50, page=3, page_size=10)
    assert uc.execute.call_args.kwargs['skip'] == 20
    assert uc.execute.call_args.kwargs['limit'] == 10
    assert uc.execute.call_args.kwargs['status'] == 'accepted'

@pytest.mark.parametrize('total,skip,limit,page,pages', [(24,10,10,2,3),(0,0,10,1,1),(20,10,10,2,2)])
def test_invoice_pagination_metadata(total,skip,limit,page,pages):
    data=InvoiceListDTO(items=[],total=total,skip=skip,limit=limit).model_dump()
    assert data['page'] == page
    assert data['page_size'] == limit
    assert data['total_pages'] == pages

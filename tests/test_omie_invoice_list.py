from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.omie.application.list_invoices import list_invoices


@pytest.mark.asyncio
async def test_omie_invoice_list_reads_saved_notes_with_backend_pagination():
    note = SimpleNamespace(transaction_id=uuid4(), status="issued", total=Decimal("46.20"),
                           os_id=123, nfse_number="1533915", error=None,
                           snapshot={"customer": "Cliente real", "document": "12345678901",
                                     "issuer": "BRASPER 21", "service": "Remessa internacional"},
                           created_at=datetime(2026, 11, 14, tzinfo=timezone.utc))
    count_result = SimpleNamespace(scalar_one=lambda: 11)
    rows_result = SimpleNamespace(all=lambda: [(note, "BxP-002439")])
    db = SimpleNamespace(execute=AsyncMock(side_effect=[count_result, rows_result]))

    result = await list_invoices(db, page=2, page_size=10, status="issued",
                                 date_from=datetime(2026, 11, 1, tzinfo=timezone.utc), date_to=None)

    assert (result["total"], result["page"], result["total_pages"]) == (11, 2, 2)
    assert result["items"][0]["transaction_code"] == "BxP-002439"
    assert result["items"][0]["nfse_number"] == "1533915"
    assert result["items"][0]["customer"] == "Cliente real"
    assert result["items"][0]["total"] == "46.20"
    count_sql, rows_sql = (str(call.args[0].compile(compile_kwargs={"literal_binds": True}))
                           for call in db.execute.await_args_list)
    assert "status = 'issued'" in count_sql
    assert "2026-11-01" in count_sql
    assert "LIMIT 10 OFFSET 10" in rows_sql

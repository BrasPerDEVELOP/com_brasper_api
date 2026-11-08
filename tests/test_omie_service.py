from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.modules.omie.application.service import OmieBillingService, build_order, customer_document, omie_route
from app.modules.omie.infrastructure.client import OmieUncertainResult


def test_routes_are_only_brl_to_pen_or_usd():
    for target in ("pen", "usd"):
        assert omie_route(SimpleNamespace(coin_a="brl", coin_b=target))
    for origin,target in (("pen","brl"),("usd","brl"),("brl","brl")):
        assert not omie_route(SimpleNamespace(coin_a=origin,coin_b=target))


def test_secondary_cpf_and_missing_identity():
    user=SimpleNamespace(document_type="ce",document_number="123",identifications=[SimpleNamespace(document_type="cpf",document_number="123.456.789-01",deleted=False)])
    assert customer_document(user)=="12345678901"
    user.identifications=[]
    with pytest.raises(ValueError,match="CPF"):
        customer_document(user)


def test_order_uses_gross_final_sale_and_omie_service_not_peruvian_igv():
    tx=uuid4()
    order=build_order(tx,"BxP-123",1,2,3,"1.01.02",Decimal("9.60"))
    assert order["Cabecalho"]["cCodIntOS"]==f"brasper-{tx}"
    assert order["ServicosPrestados"]==[{"nCodServico":2,"nQtde":1,"nValUnit":9.6,"cDadosAdicItem":"Remessa internacional - operacao BxP-123"}]
    assert order["InformacoesAdicionais"]["nCodCC"]==3
    assert order["Email"]["cEnvLink"]=="N"


class Db:
    def __init__(self):
        self.row=None
        self.commits=0
    def add(self,row): self.row=row
    async def commit(self): self.commits+=1
    async def get(self,*args): return self.row


@pytest.mark.asyncio
async def test_durable_claim_precedes_order_and_uses_final_sale():
    db=Db()
    calls=[]
    async def call(method,params):
        assert db.commits >= 1
        calls.append(method)
        return {"nCodOS":123,"cCodStatus":"0"}
    svc=OmieBillingService(db,SimpleNamespace(),SimpleNamespace(call=call))
    svc.preview=AsyncMock(return_value={"can_issue":True,"total":"9.60","document":"12345678901","_order":{"payload":"test"}})
    result=await svc.issue(uuid4(),Decimal("9.60"),"12345678901")
    assert calls==["IncluirOS","ValidarOS","FaturarOS"]
    assert result["status"]=="pending" and result["total"]=="9.60"


@pytest.mark.asyncio
async def test_timeout_keeps_attempt_and_never_faturates_again():
    db=Db(); calls=[]
    async def call(method,params):
        calls.append(method)
        raise OmieUncertainResult("timeout")
    svc=OmieBillingService(db,SimpleNamespace(),SimpleNamespace(call=call))
    svc.preview=AsyncMock(return_value={"can_issue":True,"total":"9.60","document":"12345678901","_order":{}})
    result=await svc.issue(uuid4(),Decimal("9.60"),"12345678901")
    assert result["status"]=="review_required"
    assert calls==["IncluirOS"] and db.row is not None


@pytest.mark.asyncio
async def test_stale_amount_blocks_before_any_mutation():
    db=Db(); client=SimpleNamespace(call=AsyncMock())
    svc=OmieBillingService(db,SimpleNamespace(),client)
    svc.preview=AsyncMock(return_value={"can_issue":True,"total":"9.60","document":"12345678901"})
    with pytest.raises(ValueError,match="cambiaron"):
        await svc.issue(uuid4(),Decimal("14.52"),"12345678901")
    assert db.row is None
    client.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_attempt_blocks_duplicate():
    db=Db(); client=SimpleNamespace(call=AsyncMock())
    svc=OmieBillingService(db,SimpleNamespace(),client)
    svc.preview=AsyncMock(return_value={"can_issue":False})
    with pytest.raises(ValueError,match="Ya existe"):
        await svc.issue(uuid4(),Decimal("9.60"),"12345678901")
    client.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_rejects_wrong_total():
    db=Db(); db.row=SimpleNamespace(os_id=123,total=Decimal("9.60"),snapshot={"document":"12345678901"})
    client=SimpleNamespace(call=AsyncMock(return_value={"nfseEncontradas":[{"OrdemServico":{"nCodigoOS":123},"Cabecalho":{"cCNPJEmissor":"50754016000168","nValorNFSe":14.52,"cAmbienteNFSe":"P","cCPFDestinatario":"12345678901"}}]}))
    svc=OmieBillingService(db,SimpleNamespace(OMIE_ISSUER_CNPJ="50754016000168"),client)
    with pytest.raises(ValueError,match="total"):
        await svc.refresh(uuid4())
    assert db.commits==0

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.modules.omie.application.service import OmieBillingService, build_order, customer_document, find_omie_customer, omie_route
from app.modules.omie.adapters.router import RegisterCustomerRequest
from app.modules.omie.infrastructure.client import OmieError, OmieUncertainResult
from app.modules.transactions.domain.enums import TransactionStatus


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


def test_customer_registration_requires_real_contact_and_address():
    details = {"legal_name": "Cliente Real", "email": "cliente@example.com",
               "street": "Rua Real", "number": "123", "district": "Centro",
               "city": "São Paulo", "state": "SP"}
    assert RegisterCustomerRequest(**details).city == "São Paulo"
    with pytest.raises(ValueError):
        RegisterCustomerRequest(**{**details, "email": "invalid"})
    with pytest.raises(ValueError):
        RegisterCustomerRequest(**{**details, "street": " "})
    with pytest.raises(ValueError):
        RegisterCustomerRequest(**{**details, "phone_number": "12345678"})


@pytest.mark.asyncio
async def test_customer_missing_in_omie_has_actionable_error():
    client = SimpleNamespace(call=AsyncMock(side_effect=OmieError("ERROR: Não existem registros para a página [1]!")))
    with pytest.raises(ValueError, match="no hay un cliente con ese documento en Omie"):
        await find_omie_customer(client, "12345678901")
    client.call.assert_awaited_once_with("ListarClientes", {
        "pagina": 1, "registros_por_pagina": 50,
        "clientesFiltro": {"cnpj_cpf": "12345678901"},
    })


@pytest.mark.asyncio
async def test_customer_lookup_does_not_hide_omie_api_failure():
    client = SimpleNamespace(call=AsyncMock(side_effect=OmieError("API_ADDON_REQUIRED")))
    with pytest.raises(OmieError, match="API_ADDON_REQUIRED"):
        await find_omie_customer(client, "12345678901")


@pytest.mark.asyncio
async def test_customer_lookup_requires_matching_active_document():
    client = SimpleNamespace(call=AsyncMock(return_value={"clientes_cadastro": [
        {"cnpj_cpf": "123.456.789-01", "codigo_cliente_omie": 42, "inativo": "N"},
        {"cnpj_cpf": "999.999.999-99", "codigo_cliente_omie": 43, "inativo": "N"},
    ]}))
    assert (await find_omie_customer(client, "12345678901"))["codigo_cliente_omie"] == 42


@pytest.mark.asyncio
async def test_preview_offers_registration_when_customer_is_missing():
    tx = SimpleNamespace(id=uuid4(), code="BxP-123", status=TransactionStatus.completed,
                         tax_rate_id=uuid4(), user=SimpleNamespace(names="CLIENTE", lastnames="REAL",
                         email=None, document_type="cpf", document_number="12345678901", identifications=[]))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: tx)),
                         get=AsyncMock(return_value=None))
    async def call(method, params):
        if method == "ListarEmpresas":
            return {"empresas_cadastro": [{"cnpj": "50754016000168", "gera_nfse": "S", "razao_social": "BRASPER"}]}
        if method == "ListarContasCorrentes":
            return {"ListarContasCorrentes": [{"nCodCC": 12, "descricao": "Banco do Brasil"}]}
        if method == "ConsultarCadastroServico":
            return {"cabecalho": {"cCodCateg": "1.01.02", "cDescricao": "Remessa internacional"}}
        raise OmieError("ERROR: Não existem registros para a página [1]!")
    settings = SimpleNamespace(OMIE_ENABLED=True, OMIE_APP_KEY="key", OMIE_APP_SECRET="secret",
                               OMIE_ISSUER_CNPJ="50754016000168", OMIE_ACCOUNT_ID=12, OMIE_SERVICE_ID=1)
    svc = OmieBillingService(db, settings, SimpleNamespace(call=call))
    svc.billing = SimpleNamespace(get_tax_rate=AsyncMock(return_value=SimpleNamespace(coin_a="brl", coin_b="pen")),
                                  get_open_invoice=AsyncMock(return_value=None),
                                  get_final_sale_for_billing=AsyncMock(return_value=Decimal("9.60")))
    result = await svc.preview(tx.id)
    assert result["customer_registration_required"] is True
    assert result["can_issue"] is False
    assert result["customer"] == "CLIENTE REAL"
    assert result["document"] == "12345678901"
    assert result["total"] == "9.60"


@pytest.mark.asyncio
async def test_register_customer_uses_verified_brasper_identity_and_real_address():
    client = SimpleNamespace(call=AsyncMock(return_value={"codigo_cliente_omie": 42}))
    svc = OmieBillingService(Db(), SimpleNamespace(), client)
    svc.preview = AsyncMock(return_value={
        "customer_registration_required": True,
        "customer": "CLIENTE REAL", "document": "12345678901",
    })
    details = SimpleNamespace(legal_name="CLIENTE REAL", email="cliente@example.com", street="Rua Real", number="123",
                              district="Centro", city="São Paulo", state="SP", postal_code=None,
                              phone_area_code=None, phone_number=None)
    result = await svc.register_customer(uuid4(), details)
    assert result == {"customer_id": 42, "document": "12345678901"}
    method, payload = client.call.await_args.args
    assert method == "IncluirCliente"
    assert payload["cnpj_cpf"] == "123.456.789-01"
    assert payload["razao_social"] == "CLIENTE REAL"
    assert payload["codigo_cliente_integracao"] == "brasper-customer-12345678901"
    assert payload["endereco"] == "Rua Real" and payload["estado"] == "SP"


@pytest.mark.asyncio
async def test_register_customer_does_not_write_when_already_present():
    client = SimpleNamespace(call=AsyncMock())
    svc = OmieBillingService(Db(), SimpleNamespace(), client)
    svc.preview = AsyncMock(return_value={"customer_registration_required": False})
    with pytest.raises(ValueError, match="ya existe"):
        await svc.register_customer(uuid4(), SimpleNamespace())
    client.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_customer_reconciles_uncertain_response_without_second_write():
    calls = []
    async def call(method, params):
        calls.append(method)
        if method == "IncluirCliente":
            raise OmieUncertainResult("timeout")
        return {"clientes_cadastro": [{"cnpj_cpf": "123.456.789-01",
                                       "codigo_cliente_omie": 42, "inativo": "N"}]}
    svc = OmieBillingService(Db(), SimpleNamespace(), SimpleNamespace(call=call))
    svc.preview = AsyncMock(return_value={"customer_registration_required": True,
                                         "customer": "CLIENTE REAL", "document": "12345678901"})
    details = SimpleNamespace(legal_name="CLIENTE REAL", email="cliente@example.com", street="Rua Real", number="123",
                              district="Centro", city="São Paulo", state="SP", postal_code=None,
                              phone_area_code=None, phone_number=None)
    assert (await svc.register_customer(uuid4(), details))["customer_id"] == 42
    assert calls == ["IncluirCliente", "ListarClientes"]


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

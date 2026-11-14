import json

import httpx
import pytest
from fastapi import HTTPException

from app.modules.omie.adapters.router import result
from app.modules.omie.infrastructure.client import OmieClient, OmieError, OmieRateLimited, OmieUncertainResult


@pytest.mark.asyncio
async def test_envelope_and_method_endpoint():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"nCodOS": 123, "cCodStatus": "0"})
    client = OmieClient("test-key", "test-secret", transport=httpx.MockTransport(handler))
    assert (await client.call("IncluirOS", {"Cabecalho": {"cCodIntOS": "tx-1"}}))["nCodOS"] == 123
    assert len(requests) == 1
    assert str(requests[0].url) == "https://app.omie.com.br/api/v1/servicos/os/"
    assert json.loads(requests[0].content)["param"] == [{"Cabecalho": {"cCodIntOS": "tx-1"}}]


@pytest.mark.asyncio
async def test_customer_registration_uses_omie_clients_endpoint():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"codigo_cliente_omie": 42, "codigo_status": "0"})
    client = OmieClient("test-key", "test-secret", transport=httpx.MockTransport(handler))
    result = await client.call("IncluirCliente", {"cnpj_cpf": "123.456.789-01"})
    assert result["codigo_cliente_omie"] == 42
    assert len(requests) == 1
    assert str(requests[0].url) == "https://app.omie.com.br/api/v1/geral/clientes/"
    assert json.loads(requests[0].content)["call"] == "IncluirCliente"


@pytest.mark.asyncio
async def test_timeout_never_retries_issuance():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)
    client = OmieClient("test-key", "test-secret", transport=httpx.MockTransport(handler))
    with pytest.raises(OmieUncertainResult):
        await client.call("FaturarOS", {"nCodOS": 123})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_errors_do_not_expose_credentials():
    def handler(request):
        return httpx.Response(400, json={"faultstring": "test-key test-secret invalid"})
    client = OmieClient("test-key", "test-secret", transport=httpx.MockTransport(handler))
    with pytest.raises(OmieError) as error:
        await client.call("ListarEmpresas", {})
    assert "test-key" not in str(error.value)
    assert "test-secret" not in str(error.value)


@pytest.mark.asyncio
async def test_redundant_request_exposes_cooldown_without_retrying():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(400, json={"faultstring":
            "ERROR: Consumo redundante detectado. Aguarde 33 segundos para tentar novamente (REDUNDANT)."})
    client = OmieClient("key", "secret", transport=httpx.MockTransport(handler))
    with pytest.raises(OmieRateLimited) as error:
        await client.call("ListarNFSEs", {"nCodigoOS": 123})
    assert error.value.retry_after == 33
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_redundant_request_returns_retry_after_to_frontend():
    async def operation():
        raise OmieRateLimited(33)
    with pytest.raises(HTTPException) as error:
        await result(operation())
    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "33"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body", [(503, {}), (200, []), (200, {"cCodStatus": "1", "cDescStatus": "Invalid"})])
async def test_rejects_failed_or_unexpected_responses(status, body):
    client = OmieClient("key", "secret", transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)))
    with pytest.raises(OmieError):
        await client.call("FaturarOS", {})

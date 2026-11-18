from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.error import URLError

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.users.application.schemas.document_lookup import DocumentLookupRequest
from app.modules.users.infrastructure import document_lookup as module


@pytest.fixture
def settings():
    return SimpleNamespace(APIPERU_TOKEN="peru-secret", APIPERU_BASE_URL="https://apiperu.dev/api",
                           CPFCNPJ_TOKEN="br-secret", CPFCNPJ_BASE_URL="https://api.cpfcnpj.com.br")


@pytest.mark.parametrize("kind,number,body,names,lastnames", [
    ("dni", "00112233", {"success": True, "data": {"numero": "00112233", "nombres": "JUAN CARLOS", "apellido_paterno": "PEREZ", "apellido_materno": "GARCIA"}}, "JUAN CARLOS", "PEREZ GARCIA"),
    ("ruc", "20123456789", {"success": True, "data": {"ruc": "20123456789", "nombre_o_razon_social": "EMPRESA SAC"}}, "EMPRESA SAC", ""),
    ("cpf", "001.234.567-89", {"status": 1, "cpf": "001.234.567-89", "nome": "JOAO DA SILVA", "saldo": 12}, "JOAO DA SILVA", ""),
    ("cnpj", "12.ABC.345/0001-23", {"status": 1, "cnpj": "12.ABC.345/0001-23", "razao": "EMPRESA LTDA"}, "EMPRESA LTDA", ""),
])
@pytest.mark.asyncio
async def test_provider_mapping_and_minimal_response(monkeypatch, settings, kind, number, body, names, lastnames):
    calls = []
    def fetch(url, token, payload):
        calls.append((url, token, payload))
        return 200, body
    monkeypatch.setattr(module, "_fetch", fetch)
    request = DocumentLookupRequest(document_type=kind, document_number=number)
    result = await module.lookup_document(request, settings)
    assert (result.names, result.lastnames) == (names, lastnames)
    assert result.document_number == request.document_number
    assert set(result.model_dump()) == {"document_type", "document_number", "names", "lastnames", "source"}
    if kind in {"dni", "ruc"}:
        assert calls == [(f"https://apiperu.dev/api/{kind}", "peru-secret", {kind: request.document_number})]
    else:
        assert calls == [(f"https://api.cpfcnpj.com.br/br-secret/{1 if kind == 'cpf' else 4}/{request.document_number}", None, None)]


@pytest.mark.parametrize("kind,number", [("ce", "12345678"), ("dni", "123"), ("dni", "12345a78"), ("cpf", "123/../../x"), ("cnpj", "123456789012AB")])
def test_invalid_input_never_reaches_provider(kind, number):
    with pytest.raises(ValidationError):
        DocumentLookupRequest(document_type=kind, document_number=number)


@pytest.mark.parametrize("status,payload,expected", [
    (200, {"status": 0, "erroCodigo": 1001, "erro": "secret"}, 503),
    (200, {"status": 0, "erroCodigo": 102}, 404),
    (200, {"status": 0, "erroCodigo": 100}, 422),
    (429, {}, 429), (403, {}, 503), (500, {}, 503),
    (200, {"status": 1, "nome": "Someone", "cpf": "99999999999"}, 502),
    (200, {"status": 1}, 502),
])
@pytest.mark.asyncio
async def test_safe_provider_failures(monkeypatch, settings, status, payload, expected):
    monkeypatch.setattr(module, "_fetch", lambda *args: (status, payload))
    with pytest.raises(module.DocumentLookupError) as exc:
        await module.lookup_document(DocumentLookupRequest(document_type="cpf", document_number="00123456789"), settings)
    assert exc.value.status == expected
    assert "secret" not in str(exc.value)


@pytest.mark.asyncio
async def test_missing_configuration_does_not_call_provider(monkeypatch, settings):
    settings.APIPERU_TOKEN = ""
    def forbidden(*args):
        pytest.fail("Must not call provider")
    monkeypatch.setattr(module, "_fetch", forbidden)
    with pytest.raises(module.DocumentLookupError) as exc:
        await module.lookup_document(DocumentLookupRequest(document_type="dni", document_number="00112233"), settings)
    assert exc.value.status == 503


def test_network_exception_does_not_expose_token(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError("https://api.cpfcnpj.com.br/secret/1/12345678901")
    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=fail))
    with pytest.raises(module.DocumentLookupError) as exc:
        module._fetch("https://api.cpfcnpj.com.br/secret/1/12345678901", None, None)
    assert "secret" not in str(exc.value)
    assert "12345678901" not in str(exc.value)


@pytest.mark.asyncio
async def test_lookup_always_requires_authenticated_operator(monkeypatch):
    from app.modules.users.adapters.router import user_routes
    load = AsyncMock(return_value=["users.create"])
    monkeypatch.setattr(user_routes, "_load_permissions", load)
    with pytest.raises(HTTPException) as exc:
        await user_routes.authorize_document_lookup({}, None)
    assert exc.value.status_code == 401
    load.assert_not_awaited()
    await user_routes.authorize_document_lookup({"user_id": "operator"}, None)
    load.return_value = ["users.view"]
    with pytest.raises(HTTPException) as exc:
        await user_routes.authorize_document_lookup({"user_id": "viewer"}, None)
    assert exc.value.status_code == 403

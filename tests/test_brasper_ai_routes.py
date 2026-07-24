"""Contratos y seguridad de la integración privada con com_brasper_ia."""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.modules.brasper.adapters.router.ai_routes import get_ai_service
from app.modules.brasper.application.ai_schemas import (
    AIClientDTO,
    AIClientLookupDTO,
    AIClientUpsertDTO,
    AIDepositAccountDTO,
)


class FakeAIService:
    async def lookup_client(self, **_kwargs):
        return AIClientLookupDTO(found=True, client=AIClientDTO(
            id=uuid4(), names="Ana", lastnames="Pérez", code_phone="+51",
            phone="999111222", document_type="dni", document_verified=True,
            is_first_transfer=False,
        ))

    async def upsert_client(self, _cmd):
        return AIClientUpsertDTO(id=uuid4(), created=True, is_first_transfer=True)

    async def deposit_accounts(self, currency):
        return [AIDepositAccountDTO(
            id=uuid4(), currency=currency.upper(), country="PE", bank="BCP",
            company="Brasper SAC", account="000-111", pix=None,
        )]


def test_ai_routes_fail_closed_without_secret():
    settings = get_settings()
    previous = settings.BRASPER_IA_SHARED_SECRET
    settings.BRASPER_IA_SHARED_SECRET = ""
    try:
        response = TestClient(app).get(
            "/brasper/ai/clients/lookup", params={"phone": 999111222})
        assert response.status_code == 503
    finally:
        settings.BRASPER_IA_SHARED_SECRET = previous


def test_ai_routes_require_matching_secret():
    settings = get_settings()
    previous = settings.BRASPER_IA_SHARED_SECRET
    settings.BRASPER_IA_SHARED_SECRET = "integration-test-secret"
    try:
        response = TestClient(app).get(
            "/brasper/ai/clients/lookup",
            params={"phone": 999111222},
            headers={"X-Brasper-IA-Secret": "wrong"},
        )
        assert response.status_code == 401
    finally:
        settings.BRASPER_IA_SHARED_SECRET = previous


def test_ai_contracts_return_minimum_safe_data():
    settings = get_settings()
    previous = settings.BRASPER_IA_SHARED_SECRET
    settings.BRASPER_IA_SHARED_SECRET = "integration-test-secret"
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    client = TestClient(app)
    headers = {"X-Brasper-IA-Secret": "integration-test-secret"}
    try:
        lookup = client.get(
            "/brasper/ai/clients/lookup",
            params={"code_phone": "+51", "phone": 999111222},
            headers=headers,
        )
        assert lookup.status_code == 200, lookup.text
        body = lookup.json()
        assert body["found"] is True and body["client"]["document_verified"] is True
        assert "document_number" not in body["client"]

        upsert = client.post("/brasper/ai/clients/upsert", headers=headers, json={
            "names": "Ana", "lastnames": "Pérez", "document_type": "dni",
            "document_number": "12345678", "code_phone": "+51", "phone": 999111222,
        })
        assert upsert.status_code == 200 and upsert.json()["created"] is True, upsert.text

        accounts = client.get(
            "/brasper/ai/deposit-accounts", params={"currency": "PEN"}, headers=headers)
        assert accounts.status_code == 200, accounts.text
        assert accounts.json()["data"][0]["company"] == "Brasper SAC"
    finally:
        app.dependency_overrides.pop(get_ai_service, None)
        settings.BRASPER_IA_SHARED_SECRET = previous

"""API privada y de mínimo privilegio para com_brasper_ia."""
from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.brasper.application.ai_schemas import (
    AIClientLookupDTO,
    AIOperationStatusesDTO,
    AIClientHistoryDTO,
    AIClientUpsertCmd,
    AIClientUpsertDTO,
    AIDepositAccountsDTO,
)
from app.modules.brasper.application.ai_service import BrasperAIService
from app.modules.brasper.application.campaign_quote import CampaignQuoteRequest, quote_for_client

from app.core.routing import LegacyAliasRouter

router = LegacyAliasRouter(prefix="/ai", tags=["brasper-ai"])


def require_ai_secret(x_brasper_ia_secret: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().BRASPER_IA_SHARED_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="Integración IA no configurada")
    if not x_brasper_ia_secret or not hmac.compare_digest(x_brasper_ia_secret, expected):
        raise HTTPException(status_code=401, detail="Credencial de integración inválida")


def get_ai_service(db: AsyncSession = Depends(get_db)) -> BrasperAIService:
    return BrasperAIService(db)


@router.post("/quotes", dependencies=[Depends(require_ai_secret)])
async def personalized_quote(body: CampaignQuoteRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await quote_for_client(db, body)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/clients/lookup", response_model=AIClientLookupDTO,
            dependencies=[Depends(require_ai_secret)])
async def lookup_client(
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    code_phone: str | None = Query(None),
    phone: int | None = Query(None, gt=0),
    full_name: str | None = Query(None, min_length=2, max_length=201),
):
    return await service.lookup_client(code_phone=code_phone, phone=phone, full_name=full_name)


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.get("/clients/{user_id}/history", response_model=AIClientHistoryDTO,
            dependencies=[Depends(require_ai_secret)])
async def client_history(
    user_id: UUID,
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    code_phone: str = Query(..., pattern=r"^\+[0-9]{1,4}$"),
    phone: int = Query(..., gt=0, le=999_999_999_999_999),
):
    result = await service.client_history(user_id, code_phone=code_phone, phone=phone)
    if result is None:
        raise HTTPException(status_code=404, detail="Cliente no disponible para esta identidad")
    return result


@router.get("/clients/{user_id}/operations", response_model=AIOperationStatusesDTO,
            dependencies=[Depends(require_ai_secret)])
async def operation_status(
    user_id: UUID,
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    code_phone: str = Query(..., pattern=r"^\+[0-9]{1,4}$"),
    phone: int = Query(..., gt=0, le=999_999_999_999_999),
    reference: str | None = Query(None, min_length=1, max_length=80),
):
    result = await service.operation_status(user_id, code_phone=code_phone, phone=phone, reference=reference)
    if result is None:
        raise HTTPException(404, "Cliente no disponible para esta identidad")
    return AIOperationStatusesDTO(data=result)


@router.post("/clients/upsert", response_model=AIClientUpsertDTO,
             dependencies=[Depends(require_ai_secret)])
async def upsert_client(
    cmd: AIClientUpsertCmd,
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    audit_event=Depends(stage_mutation_audit("ai.upsert_client", "client")),
):
    result = await service.upsert_client(cmd)
    if audit_event and result:
        audit_event.entity_id = str(result.id)
        audit_event.meta_data = {
            "created": result.created,
            "fields_received": sorted(cmd.model_fields_set),
        }
    return result


@router.get("/deposit-accounts", response_model=AIDepositAccountsDTO,
            dependencies=[Depends(require_ai_secret)])
async def deposit_accounts(
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    currency: str = Query(..., min_length=3, max_length=3),
):
    return AIDepositAccountsDTO(data=await service.deposit_accounts(currency))

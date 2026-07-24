"""API privada y de mínimo privilegio para com_brasper_ia."""
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.brasper.application.ai_schemas import (
    AIClientLookupDTO,
    AIClientUpsertCmd,
    AIClientUpsertDTO,
    AIDepositAccountsDTO,
)
from app.modules.brasper.application.ai_service import BrasperAIService

router = APIRouter(prefix="/ai", tags=["brasper-ai"])


def require_ai_secret(x_brasper_ia_secret: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().BRASPER_IA_SHARED_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="Integración IA no configurada")
    if not x_brasper_ia_secret or not hmac.compare_digest(x_brasper_ia_secret, expected):
        raise HTTPException(status_code=401, detail="Credencial de integración inválida")


def get_ai_service(db: AsyncSession = Depends(get_db)) -> BrasperAIService:
    return BrasperAIService(db)


@router.get("/clients/lookup", response_model=AIClientLookupDTO,
            dependencies=[Depends(require_ai_secret)])
async def lookup_client(
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    code_phone: str | None = Query(None),
    phone: int | None = Query(None, gt=0),
    full_name: str | None = Query(None, min_length=2, max_length=201),
):
    return await service.lookup_client(code_phone=code_phone, phone=phone, full_name=full_name)


@router.post("/clients/upsert", response_model=AIClientUpsertDTO,
             dependencies=[Depends(require_ai_secret)])
async def upsert_client(
    cmd: AIClientUpsertCmd,
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
):
    return await service.upsert_client(cmd)


@router.get("/deposit-accounts", response_model=AIDepositAccountsDTO,
            dependencies=[Depends(require_ai_secret)])
async def deposit_accounts(
    service: Annotated[BrasperAIService, Depends(get_ai_service)],
    currency: str = Query(..., min_length=3, max_length=3),
):
    return AIDepositAccountsDTO(data=await service.deposit_accounts(currency))

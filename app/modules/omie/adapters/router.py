from decimal import Decimal
from uuid import UUID
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.routing import LegacyAliasRouter
from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit
from app.modules.omie.application.service import OmieBillingService
from app.modules.omie.infrastructure.client import OmieError

router = LegacyAliasRouter(prefix="/omie", tags=["omie"])


class IssueRequest(BaseModel):
    expected_total: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    expected_document: str = Field(pattern=r"^\d{11}(\d{3})?$")


def service(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if not settings.OMIE_ENABLED or not settings.OMIE_APP_KEY or not settings.OMIE_APP_SECRET:
        raise HTTPException(503, "La integración de Omie no está habilitada")
    return OmieBillingService(db, settings)


async def result(operation):
    try:
        data = await operation
        if isinstance(data, dict):
            data.pop("_order", None)
        return data
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except OmieError as exc:
        raise HTTPException(502, str(exc)) from None


@router.get("/transactions/{transaction_id}/preview", dependencies=[Depends(require_permission("billing.view"))])
async def preview(transaction_id: UUID, svc=Depends(service)):
    return await result(svc.preview(transaction_id))


@router.post("/transactions/{transaction_id}/issue", dependencies=[Depends(require_permission("billing.issue")), Depends(stage_mutation_audit("omie.invoices.issue", "transaction"))])
async def issue(transaction_id: UUID, body: IssueRequest, svc=Depends(service)):
    return await result(svc.issue(transaction_id, body.expected_total, body.expected_document))


@router.post("/transactions/{transaction_id}/refresh", dependencies=[Depends(require_permission("billing.view")), Depends(stage_mutation_audit("omie.invoices.refresh", "transaction"))])
async def refresh(transaction_id: UUID, svc=Depends(service)):
    return await result(svc.refresh(transaction_id))


@router.get("/transactions/{transaction_id}/pdf", dependencies=[Depends(require_permission("billing.view"))])
async def pdf(transaction_id: UUID, svc=Depends(service)):
    return await result(svc.pdf(transaction_id))

"""Admin-only integration; conversational secret cannot change promotions."""
import hmac
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.brasper.application.campaign_service import CampaignService, CampaignConflict
from app.modules.transactions.application.schemas.campaign_schema import CampaignDraft
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


def require_campaign_admin(x_brasper_ia_admin_secret: str | None = Header(None)):
    expected = get_settings().BRASPER_IA_ADMIN_SECRET
    if not expected:
        raise HTTPException(503, "Administración de campañas no configurada")
    if expected == get_settings().BRASPER_IA_SHARED_SECRET:
        raise HTTPException(503, "La administración requiere un secreto distinto al del bot")
    if not x_brasper_ia_admin_secret or not hmac.compare_digest(expected, x_brasper_ia_admin_secret):
        raise HTTPException(401, "Credencial administrativa inválida")


router = APIRouter(prefix="/ai/admin/campaigns", tags=["brasper-ai-campaigns"], dependencies=[Depends(require_campaign_admin)])


def service(db=Depends(get_db)):
    return CampaignService(db)


class SaveIn(BaseModel):
    draft: CampaignDraft
    actor: str = Field(min_length=1, max_length=250)
    expected_version: int = Field(default=0, ge=0)


class PublishIn(BaseModel):
    version: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=250)


async def invoke(awaitable):
    try:
        return await awaitable
    except CampaignConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, "Código o versión ya existente; recarga la lista") from exc


@router.get("")
async def index(svc=Depends(service)):
    return {"campaigns": await svc.list()}


@router.get("/{coupon_id}/history")
async def history(coupon_id: UUID, svc=Depends(service)):
    return {"versions": await invoke(svc.history(coupon_id))}


@router.post("")
async def create(body: SaveIn, svc=Depends(service), audit=Depends(stage_mutation_audit("ai.campaign.draft", "coupon"))):
    result = await invoke(svc.save(body.draft, body.actor, expected_version=body.expected_version))
    if audit:
        audit.entity_id = result["id"]
        audit.meta_data = {"actor": body.actor, "version": result["version"]}
    return result


@router.put("/{coupon_id}")
async def save(coupon_id: UUID, body: SaveIn, svc=Depends(service), audit=Depends(stage_mutation_audit("ai.campaign.draft", "coupon"))):
    result = await invoke(svc.save(body.draft, body.actor, coupon_id, body.expected_version))
    if audit:
        audit.entity_id = str(coupon_id)
        audit.meta_data = {"actor": body.actor, "version": result["version"]}
    return result


@router.post("/{coupon_id}/publish")
async def publish(coupon_id: UUID, body: PublishIn, svc=Depends(service), audit=Depends(stage_mutation_audit("ai.campaign.publish", "coupon"))):
    result = await invoke(svc.publish(coupon_id, body.version, body.actor))
    if audit:
        audit.entity_id = str(coupon_id)
        audit.meta_data = {"actor": body.actor, "version": body.version}
    return result


@router.post("/{coupon_id}/disable")
async def disable(coupon_id: UUID, svc=Depends(service), audit=Depends(stage_mutation_audit("ai.campaign.disable", "coupon"))):
    result = await invoke(svc.disable(coupon_id))
    if audit:
        audit.entity_id = str(coupon_id)
    return result

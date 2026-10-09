from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.auth.infrastructure.dependencies import get_current_user
from app.modules.brasper.application.identity_links import ChannelSubject, IdentityLinks, RedeemLink, TooMany, Unavailable
from .ai_routes import require_ai_secret
from app.modules.brasper.application.ai_service import BrasperAIService
from app.modules.brasper.application.ai_schemas import AIOperationStatusesDTO

router = APIRouter(tags=["brasper-identity"])


def require_link_enabled():
    if not get_settings().BRASPER_IA_IDENTITY_LINK_ENABLED:
        raise HTTPException(503, "Vinculación de identidad no habilitada")


@router.post("/identity-links", dependencies=[Depends(require_link_enabled)])
async def issue(body: ChannelSubject, current_user=Depends(get_current_user), session=Depends(get_db)):
    try:
        user_id = UUID(str(current_user.get("user_id", "")))
    except ValueError:
        raise HTTPException(401, "Inicia sesión en tu cuenta Brasper")
    try:
        return await IdentityLinks(session).issue(user_id, body)
    except Unavailable as exc:
        raise HTTPException(403, str(exc)) from exc
    except TooMany as exc:
        raise HTTPException(429, str(exc)) from exc


@router.delete("/identity-links", dependencies=[Depends(require_link_enabled)])
async def revoke(current_user=Depends(get_current_user), session=Depends(get_db)):
    try:
        user_id = UUID(str(current_user.get("user_id", "")))
    except ValueError:
        raise HTTPException(401, "Inicia sesión en tu cuenta Brasper")
    return await IdentityLinks(session).revoke_all(user_id)


@router.post("/ai/identity-links/redeem", dependencies=[Depends(require_ai_secret), Depends(require_link_enabled)])
async def redeem(body: RedeemLink, session=Depends(get_db)):
    try:
        return await IdentityLinks(session).redeem(body)
    except Unavailable as exc:
        raise HTTPException(401, str(exc)) from exc


@router.get("/ai/identity-links/{user_id}/operations", response_model=AIOperationStatusesDTO,
            dependencies=[Depends(require_ai_secret), Depends(require_link_enabled)])
async def linked_operations(user_id: UUID, channel: str, subject: str,
                            x_brasper_identity_grant: str = Header(...),
                            reference: str | None = Query(None, min_length=1, max_length=80),
                            session=Depends(get_db)):
    links = IdentityLinks(session)
    try:
        await links.authorize(user_id, x_brasper_identity_grant, channel, subject)
    except Unavailable as exc:
        raise HTTPException(401, str(exc)) from exc
    # Contact data comes exclusively from the authenticated account, never chat input.
    user = await links._user(user_id)
    if user is None:
        raise HTTPException(401, "Identidad no autorizada")
    result = await BrasperAIService(session).operation_status(
        user_id, code_phone=user.code_phone.value if hasattr(user.code_phone, "value") else user.code_phone,
        phone=user.phone, reference=reference)
    if result is None:
        raise HTTPException(404, "Cliente no disponible para esta identidad")
    return AIOperationStatusesDTO(data=result)

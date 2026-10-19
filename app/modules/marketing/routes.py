import asyncio
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit
from app.core.permissions import require_permission
from app.core.routing import LegacyAliasRouter
from app.db.base import get_db
from app.modules.marketing.mail import check_config, decode_unsubscribe, send_email
from app.modules.marketing.models import Campaign, Recipient, Suppression
from app.modules.marketing.schemas import CampaignInput, TestInput, PreviewInput
from app.modules.marketing.template_renderer import (
    ASSET_DIR, ALL_ASSET_NAMES, TEMPLATES, render_email,
)
from app.modules.users.domain.models import User
from app.core.settings import get_settings

router = LegacyAliasRouter(prefix="/marketing", tags=["Marketing"])


@router.get("/templates", dependencies=[Depends(require_permission("marketing.view"))])
async def templates():
    return {"items": list(TEMPLATES.values())}


@router.post("/preview", dependencies=[Depends(require_permission("marketing.view")),
             Depends(stage_mutation_audit("marketing.preview", "marketing_template"))])
async def preview(payload: PreviewInput):
    return {"html": render_email(payload.subject, payload.body, "#preview-unsubscribe",
                                  payload.template_key, asset_base=get_settings().PUBLIC_URL)}


@router.get("/assets/brasper-peru-pt-v1/{filename}", include_in_schema=False)
async def template_asset(filename: str):
    if filename not in ALL_ASSET_NAMES:
        raise HTTPException(404, "Imagen no encontrada")
    return FileResponse(ASSET_DIR / filename, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/configuration", dependencies=[Depends(require_permission("marketing.view"))])
async def configuration():
    s = get_settings()
    try:
        check_config()
        configured = True
    except HTTPException:
        configured = False
    return {"from_email": s.SMTP_FROM_EMAIL, "ready": configured and s.MARKETING_ENABLED}


@router.get("/clients", dependencies=[Depends(require_permission("marketing.create"))])
async def clients(q: str = Query("", max_length=100), skip: int = Query(0, ge=0),
                  limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    stmt = select(User.email).where(User.deleted.is_(False), User.enable.is_(True),
        User.role == "client", User.email.is_not(None))
    if q:
        stmt = stmt.where(User.email.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%"))
    emails = (await db.execute(stmt.order_by(User.email).offset(skip).limit(limit))).scalars().all()
    return {"items": emails}


async def find_campaign(db, campaign_id, lock=False):
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    if lock:
        stmt = stmt.with_for_update()
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Campaña no encontrada")
    return item


async def campaign_dto(db, item):
    counts = dict((await db.execute(select(Recipient.status, func.count()).where(
        Recipient.campaign_id == item.id).group_by(Recipient.status))).all())
    return dict(id=item.id, name=item.name, subject=item.subject, body=item.body,
                template_key=item.template_key,
                status=item.status, created_at=item.created_at, counts=counts, total=sum(counts.values()))


@router.get("/campaigns", dependencies=[Depends(require_permission("marketing.view"))])
async def campaigns(db: AsyncSession = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    items = (await db.execute(select(Campaign).order_by(Campaign.created_at.desc()).offset(skip).limit(limit))).scalars().all()
    return {"items": [await campaign_dto(db, item) for item in items],
            "total": (await db.execute(select(func.count()).select_from(Campaign))).scalar_one()}


@router.post("/campaigns", status_code=201, dependencies=[Depends(require_permission("marketing.create")), Depends(stage_mutation_audit("marketing.create", "marketing_campaign"))])
async def create(payload: CampaignInput, db: AsyncSession = Depends(get_db)):
    if not payload.consent_confirmed:
        raise HTTPException(422, "Confirma que los destinatarios autorizaron recibir correos")
    item = Campaign(name=payload.name, subject=payload.subject, body=payload.body, template_key=payload.template_key)
    db.add(item)
    await db.flush()
    db.add_all([Recipient(campaign_id=item.id, email=email) for email in sorted({str(e).lower() for e in payload.emails})])
    await db.commit()
    return await campaign_dto(db, item)


@router.get("/campaigns/{campaign_id}/recipients", dependencies=[Depends(require_permission("marketing.view"))])
async def recipients(campaign_id: UUID, db: AsyncSession = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    await find_campaign(db, campaign_id)
    items = (await db.execute(select(Recipient).where(Recipient.campaign_id == campaign_id).order_by(Recipient.email).offset(skip).limit(limit))).scalars().all()
    return {"items": [dict(email=r.email, status=r.status, error=r.error, sent_at=r.sent_at) for r in items]}


@router.post("/campaigns/{campaign_id}/test", dependencies=[Depends(require_permission("marketing.send")), Depends(stage_mutation_audit("marketing.test", "marketing_campaign"))])
async def test_send(campaign_id: UUID, payload: TestInput, db: AsyncSession = Depends(get_db)):
    item = await find_campaign(db, campaign_id)
    check_config()
    email = str(payload.email).lower()
    if await db.get(Suppression, email):
        raise HTTPException(409, "El destinatario solicitó la baja")
    try:
        await asyncio.to_thread(send_email, email, item.subject, item.body, True, item.template_key)
    except Exception:
        raise HTTPException(502, "No se pudo enviar la prueba; revisa la configuración SMTP")
    return {"detail": "Correo de prueba aceptado por SMTP"}


@router.post("/campaigns/{campaign_id}/send", dependencies=[Depends(require_permission("marketing.send")), Depends(stage_mutation_audit("marketing.send", "marketing_campaign"))])
async def queue(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    check_config()
    if not get_settings().MARKETING_ENABLED:
        raise HTTPException(503, "Activa MARKETING_ENABLED para procesar envíos")
    item = await find_campaign(db, campaign_id, lock=True)
    if item.status != "draft":
        raise HTTPException(409, "Esta campaña ya fue puesta en cola")
    item.status = "queued"
    await db.commit()
    return await campaign_dto(db, item)


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_confirmation(token: str = Query(max_length=2000)):
    decode_unsubscribe(token)
    return '<html lang="es"><meta charset="utf-8"><title>Baja de correos</title><h1>Brasper Transferencias</h1><form method="post"><input type="hidden" name="unused" value=""><p>¿Deseas dejar de recibir correos de marketing?</p><button>Confirmar baja</button></form></html>'


@router.post("/unsubscribe", response_class=HTMLResponse, dependencies=[Depends(stage_mutation_audit("marketing.unsubscribe", "marketing_suppression"))])
async def unsubscribe(token: str = Query(max_length=2000), db: AsyncSession = Depends(get_db)):
    email = decode_unsubscribe(token)
    await db.execute(insert(Suppression).values(email=email).on_conflict_do_nothing())
    await db.commit()
    return '<html lang="es"><meta charset="utf-8"><h1>Baja registrada</h1><p>No recibirás más correos de marketing de Brasper.</p></html>'

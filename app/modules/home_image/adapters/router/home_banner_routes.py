"""Rutas para HomeBanner - solo GET, POST, PUT."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile

from app.modules.auth.infrastructure.dependencies import has_permission, require_permission

from app.modules.home_image.application.schemas import (
    HomeBannerCreateCmd,
    HomeBannerUpdateCmd,
    HomeBannerReadDTO,
)
from app.modules.home_image.adapters.dependencies import (
    GetHomeBannerByIdUseCaseDep,
    ListHomeBannersUseCaseDep,
    CreateHomeBannerUseCaseDep,
    UpdateHomeBannerUseCaseDep,
)
from app.shared.services.file_service import save_home_banner_image

from app.core.routing import LegacyAliasRouter

router = LegacyAliasRouter(prefix="/home-image", tags=["home-banner"])


@router.get("", response_model=List[HomeBannerReadDTO])
async def list_home_banners(
    use_case: ListHomeBannersUseCaseDep,
    can_view_disabled: bool = Depends(has_permission("home_banner.view")),
):
    items = await use_case.execute()
    return items if can_view_disabled else [item for item in items if item.enable]


@router.get("/{home_banner_id}", response_model=HomeBannerReadDTO)
async def get_home_banner_by_id(
    home_banner_id: UUID,
    use_case: GetHomeBannerByIdUseCaseDep,
    can_view_disabled: bool = Depends(has_permission("home_banner.view")),
):
    entity = await use_case.execute(home_banner_id)
    if not entity or (not entity.enable and not can_view_disabled):
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post(
    "",
    response_model=HomeBannerReadDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("home_banner.update"))],
)
async def create_home_banner(
    use_case: CreateHomeBannerUseCaseDep,
    enable: bool = Form(True),
    banner_es: Optional[UploadFile] = File(None),
    banner_pr: Optional[UploadFile] = File(None),
    banner_en: Optional[UploadFile] = File(None),
    audit_event=Depends(stage_mutation_audit("home_banner.create", "home_banner")),
):
    banner_es_path = await save_home_banner_image(banner_es, "es") if banner_es else None
    banner_pr_path = await save_home_banner_image(banner_pr, "pr") if banner_pr else None
    banner_en_path = await save_home_banner_image(banner_en, "en") if banner_en else None

    cmd = HomeBannerCreateCmd(
        banner_es=banner_es_path,
        banner_pr=banner_pr_path,
        banner_en=banner_en_path,
        enable=enable,
    )
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "",
    response_model=HomeBannerReadDTO,
    dependencies=[Depends(require_permission("home_banner.update"))],
)
async def update_home_banner(
    use_case: UpdateHomeBannerUseCaseDep,
    get_use_case: GetHomeBannerByIdUseCaseDep,
    id: UUID = Form(...),
    enable: Optional[bool] = Form(None),
    banner_es: Optional[UploadFile] = File(None),
    banner_pr: Optional[UploadFile] = File(None),
    banner_en: Optional[UploadFile] = File(None),
    audit_event=Depends(stage_mutation_audit("home_banner.update", "home_banner")),
):
    previous = await get_use_case.execute(id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    banner_es_path = await save_home_banner_image(banner_es, "es") if banner_es else None
    banner_pr_path = await save_home_banner_image(banner_pr, "pr") if banner_pr else None
    banner_en_path = await save_home_banner_image(banner_en, "en") if banner_en else None

    cmd = HomeBannerUpdateCmd(
        id=id,
        banner_es=banner_es_path,
        banner_pr=banner_pr_path,
        banner_en=banner_en_path,
        enable=enable,
    )
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    return entity

"""Rutas para HomePopup - GET, POST, PUT."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile

from app.modules.auth.infrastructure.dependencies import has_permission, require_permission

from app.modules.home_image.application.schemas import (
    HomePopupCreateCmd,
    HomePopupUpdateCmd,
    HomePopupReadDTO,
)
from app.modules.home_image.adapters.dependencies import (
    GetHomePopupByIdUseCaseDep,
    ListHomePopupsUseCaseDep,
    CreateHomePopupUseCaseDep,
    UpdateHomePopupUseCaseDep,
)
from app.shared.services.file_service import save_home_popup_image

from app.core.routing import LegacyAliasRouter

router = LegacyAliasRouter(prefix="/home-popup", tags=["home-popup"])


@router.get("", response_model=List[HomePopupReadDTO])
async def list_home_popups(
    use_case: ListHomePopupsUseCaseDep,
    can_view_disabled: bool = Depends(has_permission("home_banner.view")),
):
    items = await use_case.execute()
    return items if can_view_disabled else [item for item in items if item.enable]


@router.get("/{home_popup_id}", response_model=HomePopupReadDTO)
async def get_home_popup_by_id(
    home_popup_id: UUID,
    use_case: GetHomePopupByIdUseCaseDep,
    can_view_disabled: bool = Depends(has_permission("home_banner.view")),
):
    entity = await use_case.execute(home_popup_id)
    if not entity or (not entity.enable and not can_view_disabled):
        raise HTTPException(status_code=404, detail="Popup no encontrado")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post(
    "",
    response_model=HomePopupReadDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("home_banner.update"))],
)
async def create_home_popup(
    use_case: CreateHomePopupUseCaseDep,
    enable: bool = Form(True),
    popup_es: Optional[UploadFile] = File(None),
    popup_pr: Optional[UploadFile] = File(None),
    popup_en: Optional[UploadFile] = File(None),
    audit_event=Depends(stage_mutation_audit("home_popup.create", "home_popup")),
):
    popup_es_path = await save_home_popup_image(popup_es, "es") if popup_es else None
    popup_pr_path = await save_home_popup_image(popup_pr, "pr") if popup_pr else None
    popup_en_path = await save_home_popup_image(popup_en, "en") if popup_en else None

    cmd = HomePopupCreateCmd(
        popup_es=popup_es_path,
        popup_pr=popup_pr_path,
        popup_en=popup_en_path,
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
    response_model=HomePopupReadDTO,
    dependencies=[Depends(require_permission("home_banner.update"))],
)
async def update_home_popup(
    use_case: UpdateHomePopupUseCaseDep,
    get_use_case: GetHomePopupByIdUseCaseDep,
    id: UUID = Form(...),
    enable: Optional[bool] = Form(None),
    popup_es: Optional[UploadFile] = File(None),
    popup_pr: Optional[UploadFile] = File(None),
    popup_en: Optional[UploadFile] = File(None),
    audit_event=Depends(stage_mutation_audit("home_popup.update", "home_popup")),
):
    previous = await get_use_case.execute(id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    popup_es_path = await save_home_popup_image(popup_es, "es") if popup_es else None
    popup_pr_path = await save_home_popup_image(popup_pr, "pr") if popup_pr else None
    popup_en_path = await save_home_popup_image(popup_en, "en") if popup_en else None

    cmd = HomePopupUpdateCmd(
        id=id,
        popup_es=popup_es_path,
        popup_pr=popup_pr_path,
        popup_en=popup_en_path,
        enable=enable,
    )
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Popup no encontrado")
    return entity

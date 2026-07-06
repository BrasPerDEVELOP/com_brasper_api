"""Rutas para HomePopup - GET, POST, PUT."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile

from app.modules.auth.infrastructure.dependencies import require_permission

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

router = APIRouter(prefix="/home-popup", tags=["home-popup"])


@router.get("/", response_model=List[HomePopupReadDTO])
async def list_home_popups(use_case: ListHomePopupsUseCaseDep):
    return await use_case.execute()


@router.get("/{home_popup_id}", response_model=HomePopupReadDTO)
async def get_home_popup_by_id(home_popup_id: UUID, use_case: GetHomePopupByIdUseCaseDep):
    entity = await use_case.execute(home_popup_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Popup no encontrado")
    return entity


@router.post(
    "/",
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
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/",
    response_model=HomePopupReadDTO,
    dependencies=[Depends(require_permission("home_banner.update"))],
)
async def update_home_popup(
    use_case: UpdateHomePopupUseCaseDep,
    id: UUID = Form(...),
    enable: Optional[bool] = Form(None),
    popup_es: Optional[UploadFile] = File(None),
    popup_pr: Optional[UploadFile] = File(None),
    popup_en: Optional[UploadFile] = File(None),
):
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
    if not entity:
        raise HTTPException(status_code=404, detail="Popup no encontrado")
    return entity

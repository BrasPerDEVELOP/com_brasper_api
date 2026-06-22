"""Rutas para HomeBanner - solo GET, POST, PUT."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, status, UploadFile

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

router = APIRouter(prefix="/home-image", tags=["home-banner"])


@router.get("/", response_model=List[HomeBannerReadDTO])
async def list_home_banners(use_case: ListHomeBannersUseCaseDep):
    return await use_case.execute()


@router.get("/{home_banner_id}", response_model=HomeBannerReadDTO)
async def get_home_banner_by_id(home_banner_id: UUID, use_case: GetHomeBannerByIdUseCaseDep):
    entity = await use_case.execute(home_banner_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    return entity


@router.post("/", response_model=HomeBannerReadDTO, status_code=status.HTTP_201_CREATED)
async def create_home_banner(
    use_case: CreateHomeBannerUseCaseDep,
    enable: bool = Form(True),
    banner_es: Optional[UploadFile] = File(None),
    banner_pr: Optional[UploadFile] = File(None),
    banner_en: Optional[UploadFile] = File(None),
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
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=HomeBannerReadDTO)
async def update_home_banner(
    use_case: UpdateHomeBannerUseCaseDep,
    id: UUID = Form(...),
    enable: Optional[bool] = Form(None),
    banner_es: Optional[UploadFile] = File(None),
    banner_pr: Optional[UploadFile] = File(None),
    banner_en: Optional[UploadFile] = File(None),
):
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
    if not entity:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    return entity

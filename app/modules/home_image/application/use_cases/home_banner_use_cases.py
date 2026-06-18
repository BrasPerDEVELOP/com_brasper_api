"""Casos de uso CRUD para HomeBanner (solo GET, POST, PUT)."""
from uuid import UUID
from typing import List, Optional

from app.modules.home_image.domain.models import HomeBanner
from app.modules.home_image.interfaces.home_banner_repository import HomeBannerRepositoryInterface
from app.modules.home_image.application.schemas.home_banner_schema import (
    HomeBannerCreateCmd,
    HomeBannerUpdateCmd,
    HomeBannerReadDTO,
)
from app.shared.services.file_service import delete_home_banner_image


class GetHomeBannerByIdUseCase:
    def __init__(self, repo: HomeBannerRepositoryInterface):
        self.repo = repo

    async def execute(self, home_banner_id: UUID) -> Optional[HomeBannerReadDTO]:
        entity = await self.repo.get(home_banner_id)
        if not entity:
            return None
        return HomeBannerReadDTO.model_validate(entity)


class ListHomeBannersUseCase:
    def __init__(self, repo: HomeBannerRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[HomeBannerReadDTO]:
        items = await self.repo.list()
        return [HomeBannerReadDTO.model_validate(x) for x in items]


class CreateHomeBannerUseCase:
    def __init__(self, repo: HomeBannerRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: HomeBannerCreateCmd) -> HomeBannerReadDTO:
        entity = HomeBanner(
            banner_es=cmd.banner_es,
            banner_pr=cmd.banner_pr,
            banner_en=cmd.banner_en,
            enable=cmd.enable,
            content=cmd.content,
            indicators=cmd.indicators,
            appearance=cmd.appearance,
            show_image=cmd.show_image,
            show_indicators=cmd.show_indicators,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return HomeBannerReadDTO.model_validate(saved)


class UpdateHomeBannerUseCase:
    def __init__(self, repo: HomeBannerRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: HomeBannerUpdateCmd) -> Optional[HomeBannerReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        previous_banner_es = entity.banner_es
        previous_banner_pr = entity.banner_pr
        previous_banner_en = entity.banner_en

        if cmd.banner_es is not None:
            entity.banner_es = cmd.banner_es
        if cmd.banner_pr is not None:
            entity.banner_pr = cmd.banner_pr
        if cmd.banner_en is not None:
            entity.banner_en = cmd.banner_en
        if cmd.enable is not None:
            entity.enable = cmd.enable
        for field in ("content", "indicators", "appearance", "show_image", "show_indicators"):
            value = getattr(cmd, field)
            if value is not None:
                setattr(entity, field, value)
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)

        if cmd.banner_es is not None and previous_banner_es and previous_banner_es != entity.banner_es:
            await delete_home_banner_image(previous_banner_es)
        if cmd.banner_pr is not None and previous_banner_pr and previous_banner_pr != entity.banner_pr:
            await delete_home_banner_image(previous_banner_pr)
        if cmd.banner_en is not None and previous_banner_en and previous_banner_en != entity.banner_en:
            await delete_home_banner_image(previous_banner_en)

        return HomeBannerReadDTO.model_validate(entity)

from datetime import datetime, timezone

from app.core.pagination.offset import PaginatedResult
from app.modules.brasper.domain.models import ContacForm
from app.modules.brasper.interfaces.contact_form_repository import ContactFormRepositoryInterface
from app.modules.brasper.application.schemas.contact_form_schema import (
    ContactFormCreateCmd,
    ContactFormListPage,
    ContactFormReadDTO,
)


class CreateContactFormUseCase:
    def __init__(self, repo: ContactFormRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: ContactFormCreateCmd) -> ContactFormReadDTO:
        submitted = cmd.submitted_at
        if submitted is None:
            submitted = datetime.now(timezone.utc)
        entity = ContacForm(
            full_name=cmd.full_name,
            email=cmd.email,
            affiliation=cmd.affiliation,
            profile=cmd.profile,
            interest=cmd.interest,
            message=cmd.message,
            locale=cmd.locale,
            source=cmd.source,
            submitted_at=submitted,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return ContactFormReadDTO.model_validate(saved)


class ListContactFormsUseCase:
    def __init__(self, repo: ContactFormRepositoryInterface):
        self.repo = repo

    async def execute(self, *, limit: int, skip: int) -> ContactFormListPage:
        raw = await self.repo.list(limit=limit, offset=skip)
        if isinstance(raw, PaginatedResult):
            items = [ContactFormReadDTO.model_validate(x) for x in raw.items]
            return ContactFormListPage(
                items=items,
                total=raw.total,
                skip=raw.skip,
                limit=raw.limit,
                has_next=raw.has_next,
                has_previous=raw.has_previous,
            )
        items = [ContactFormReadDTO.model_validate(x) for x in raw]
        return ContactFormListPage(
            items=items,
            total=len(items),
            skip=skip,
            limit=limit,
            has_next=False,
            has_previous=skip > 0 and len(items) > 0,
        )

from datetime import datetime, timezone

from app.modules.brasper.domain.models import ContacForm
from app.modules.brasper.interfaces.contact_form_repository import ContactFormRepositoryInterface
from app.modules.brasper.application.schemas.contact_form_schema import (
    ContactFormCreateCmd,
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

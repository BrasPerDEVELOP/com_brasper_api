"""Inyección de dependencias del módulo brasper."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.brasper.interfaces.contact_form_repository import ContactFormRepositoryInterface
from app.modules.brasper.infrastructure.repository import SQLAlchemyContactFormRepository
from app.modules.brasper.application.use_cases import CreateContactFormUseCase


def get_contact_form_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactFormRepositoryInterface:
    return SQLAlchemyContactFormRepository(db)


def create_contact_form_uc(
    repo: Annotated[ContactFormRepositoryInterface, Depends(get_contact_form_repository)],
) -> CreateContactFormUseCase:
    return CreateContactFormUseCase(repo)


CreateContactFormUseCaseDep = Annotated[CreateContactFormUseCase, Depends(create_contact_form_uc)]

"""Ruta pública para enviar el formulario de contacto / membresía."""
from fastapi import APIRouter, Depends, Query, status

from app.modules.brasper.application.schemas import (
    ContactFormCreateCmd,
    ContactFormListPage,
    ContactFormReadDTO,
)
from app.modules.brasper.application.use_cases import ListContactFormsUseCase
from app.modules.brasper.adapters.dependencies import CreateContactFormUseCaseDep
from app.modules.brasper.adapters.dependencies.brasper_dependencies import list_contact_forms_uc

router = APIRouter(tags=["brasper"])


@router.get(
    "/contact-form",
    response_model=ContactFormListPage,
    response_model_by_alias=True,
    summary="Listar envíos guardados (público)",
)
async def contact_form_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    use_case: ListContactFormsUseCase = Depends(list_contact_forms_uc),
):
    return await use_case.execute(limit=limit, skip=skip)


@router.post(
    "/contact-form",
    response_model=ContactFormReadDTO,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar formulario de contacto / membresía",
)
async def submit_contact_form(
    cmd: ContactFormCreateCmd,
    use_case: CreateContactFormUseCaseDep,
):
    return await use_case.execute(cmd)

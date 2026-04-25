"""Ruta pública para enviar el formulario de contacto / membresía."""
from fastapi import APIRouter, status

from app.modules.brasper.application.schemas import ContactFormCreateCmd, ContactFormReadDTO
from app.modules.brasper.adapters.dependencies import CreateContactFormUseCaseDep

router = APIRouter()


@router.post(
    "/contact-form",
    response_model=ContactFormReadDTO,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def submit_contact_form(
    cmd: ContactFormCreateCmd,
    use_case: CreateContactFormUseCaseDep,
):
    return await use_case.execute(cmd)

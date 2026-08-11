# app/modules/transactions/adapters/router/bank_routes.py
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.transactions.application.schemas import (
    BankCreateCmd,
    BankUpdateCmd,
    BankReadDTO,
    BankOptionDTO,
    BanksByCountryCurrencyDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetBankByIdUseCaseDep,
    ListBanksUseCaseDep,
    ListBankNamesUseCaseDep,
    ListBanksByCountryCurrencyUseCaseDep,
    CreateBankUseCaseDep,
    UpdateBankUseCaseDep,
    DeleteBankUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/banks", tags=["banks"])


@router.get("", response_model=List[BankReadDTO])
async def list_banks(
    use_case: ListBanksUseCaseDep,
    bank: Optional[str] = Query(None, description="Filtro por nombre de banco (parcial)"),
    company: Optional[str] = Query(None, description="Filtro por empresa (parcial)"),
    currency: Optional[str] = Query(None, description="Filtro por moneda: PEN, USD, BRL"),
    currency_display: Optional[str] = Query(
        None,
        description='Filtro por moneda legible: "Soles (PEN)", "Dólares (USD)", "Reales (BRL)"',
    ),
    social_actor: Optional[str] = Query(
        None,
        description="Filtro por actor social: naturalPerson, legalEntity, generalAspect",
    ),
):
    """Lista bancos con filtros opcionales por bank, company, currency, currency_display, social_actor."""
    return await use_case.execute(
        bank=bank,
        company=company,
        currency=currency,
        currency_display=currency_display,
        social_actor=social_actor,
    )


@router.get("/by-country-currency", response_model=BanksByCountryCurrencyDTO)
async def list_banks_by_country_currency(use_case: ListBanksByCountryCurrencyUseCaseDep):
    """Devuelve bancos agrupados por país (PE, BR) y moneda (PEN, USD, BRL)."""
    return await use_case.execute()


@router.get("/names", response_model=List[BankOptionDTO])
async def list_bank_names(use_case: ListBankNamesUseCaseDep):
    """Devuelve lista de bancos con id, bank, currency, country (ordenados por nombre y moneda)."""
    return await use_case.execute()


@router.get("/{bank_id}", response_model=BankReadDTO)
async def get_bank_by_id(bank_id: UUID, use_case: GetBankByIdUseCaseDep):
    entity = await use_case.execute(bank_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=BankReadDTO, status_code=status.HTTP_201_CREATED)
async def create_bank(
    cmd: BankCreateCmd,
    use_case: CreateBankUseCaseDep,
    _permissions=Depends(require_permission("company_bank_accounts.create")),
    audit_event=Depends(stage_mutation_audit("banks.create", "bank")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=BankReadDTO)
async def update_bank(
    cmd: BankUpdateCmd,
    use_case: UpdateBankUseCaseDep,
    get_use_case: GetBankByIdUseCaseDep,
    _permissions=Depends(require_permission("company_bank_accounts.update")),
    audit_event=Depends(stage_mutation_audit("banks.update", "bank")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    return entity


@router.delete("/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank(
    bank_id: UUID,
    use_case: DeleteBankUseCaseDep,
    get_use_case: GetBankByIdUseCaseDep,
    _permissions=Depends(require_permission("company_bank_accounts.delete")),
    audit_event=Depends(stage_mutation_audit("banks.delete", "bank")),
):
    previous = await get_use_case.execute(bank_id)
    if audit_event:
        audit_event.entity_id = str(bank_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(bank_id)

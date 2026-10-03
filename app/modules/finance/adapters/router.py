# app/modules/finance/adapters/router.py
"""Rutas de tasas mensuales a soles y egresos."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.routing import LegacyAliasRouter
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit
from app.modules.auth.infrastructure.dependencies import get_current_user, require_permission
from app.modules.finance.adapters.dependencies import (
    CreateExpenseUseCaseDep,
    DeleteExpenseUseCaseDep,
    GetExpenseUseCaseDep,
    ListExpenseCategoriesUseCaseDep,
    ListExpensesUseCaseDep,
    ListFxRatesUseCaseDep,
    UpdateExpenseUseCaseDep,
    UpsertFxRatesUseCaseDep,
)
from app.modules.finance.application.schemas import (
    ExpenseCategoryDTO,
    ExpenseCreateCmd,
    ExpenseDTO,
    ExpenseListDTO,
    ExpenseUpdateCmd,
    FxMonthRateDTO,
    FxRatesUpsertCmd,
)

router = LegacyAliasRouter(prefix="/finance", tags=["finance"])


# --- Tasas mensuales a soles --------------------------------------------
@router.get(
    "/fx-rates",
    response_model=list[FxMonthRateDTO],
    dependencies=[Depends(require_permission("fx_rates.view"))],
)
async def list_fx_rates(
    use_case: ListFxRatesUseCaseDep,
    year: int = Query(..., ge=2015, le=2100),
):
    """Tasas (BRL, USD → PEN) registradas para el año."""
    return await use_case.execute(year)


@router.put(
    "/fx-rates",
    response_model=list[FxMonthRateDTO],
    dependencies=[Depends(require_permission("fx_rates.update"))],
)
async def upsert_fx_rates(
    cmd: FxRatesUpsertCmd,
    use_case: UpsertFxRatesUseCaseDep,
    audit_event=Depends(stage_mutation_audit("finance.fx_rates.upsert", "fx_month_rate")),
):
    """Crea o actualiza una o varias tasas (año, mes, moneda)."""
    try:
        saved = await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if audit_event:
        audit_event.new_values = cmd.model_dump(mode="json")
    return saved


# --- Egresos -------------------------------------------------------------
@router.get(
    "/expense-categories",
    response_model=list[ExpenseCategoryDTO],
    dependencies=[Depends(require_permission("expenses.view"))],
)
async def list_expense_categories(use_case: ListExpenseCategoriesUseCaseDep):
    return await use_case.execute()


@router.get(
    "/expenses",
    response_model=ExpenseListDTO,
    dependencies=[Depends(require_permission("expenses.view"))],
)
async def list_expenses(
    use_case: ListExpensesUseCaseDep,
    year: int = Query(..., ge=2015, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    category_id: Optional[UUID] = Query(None),
):
    return await use_case.execute(year=year, month=month, category_id=category_id)


@router.post(
    "/expenses",
    response_model=ExpenseDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("expenses.create"))],
)
async def create_expense(
    cmd: ExpenseCreateCmd,
    use_case: CreateExpenseUseCaseDep,
    actor=Depends(get_current_user),
    audit_event=Depends(stage_mutation_audit("finance.expenses.create", "expense")),
):
    try:
        created = await use_case.execute(cmd, created_by=str(actor.get("email") or actor.get("user_id") or "") or None)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if audit_event:
        audit_event.entity_id = str(created.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    return created


@router.put(
    "/expenses",
    response_model=ExpenseDTO,
    dependencies=[Depends(require_permission("expenses.update"))],
)
async def update_expense(
    cmd: ExpenseUpdateCmd,
    use_case: UpdateExpenseUseCaseDep,
    get_use_case: GetExpenseUseCaseDep,
    audit_event=Depends(stage_mutation_audit("finance.expenses.update", "expense")),
):
    previous = await get_use_case.execute(cmd.id)
    if not previous:
        raise HTTPException(status_code=404, detail="Egreso no encontrado")
    if audit_event:
        audit_event.entity_id = str(cmd.id)
        audit_event.old_values = previous.model_dump(mode="json")
        audit_event.new_values = cmd.model_dump(mode="json", exclude_unset=True)
    try:
        updated = await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Egreso no encontrado")
    return updated


@router.delete(
    "/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("expenses.delete"))],
)
async def delete_expense(
    expense_id: UUID,
    use_case: DeleteExpenseUseCaseDep,
    get_use_case: GetExpenseUseCaseDep,
    audit_event=Depends(stage_mutation_audit("finance.expenses.delete", "expense")),
):
    previous = await get_use_case.execute(expense_id)
    if audit_event:
        audit_event.entity_id = str(expense_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    if not await use_case.execute(expense_id):
        raise HTTPException(status_code=404, detail="Egreso no encontrado")


__all__ = ["router"]

# app/modules/transactions/adapters/router/bank_account_routes.py
from uuid import UUID
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.settings import get_settings
from app.modules.auth.infrastructure.dependencies import (
    get_current_user,
    get_current_user_permissions,
)
from app.modules.transactions.application.schemas import (
    BankAccountCreateCmd,
    BankAccountUpdateCmd,
    BankAccountReadDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetBankAccountByIdUseCaseDep,
    ListBankAccountsUseCaseDep,
    CreateBankAccountUseCaseDep,
    UpdateBankAccountUseCaseDep,
    DeleteBankAccountUseCaseDep,
)

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])

PermissionsDep = Annotated[List[str], Depends(get_current_user_permissions)]
CurrentUserDep = Annotated[dict, Depends(get_current_user)]


def _auth_bypassed() -> bool:
    """En entornos con `AUTH_REQUIRED=False` no hay sesión que autorizar."""
    return not get_settings().AUTH_REQUIRED


def _caller_id(current_user: dict) -> str:
    caller_id = current_user.get("user_id")
    if not caller_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida"
        )
    return str(caller_id)


def _ensure_access(
    permission: str,
    owner_id: Optional[UUID],
    permissions: List[str],
    current_user: dict,
) -> None:
    """Autoriza la operación sobre una cuenta bancaria.

    El dueño de la cuenta siempre puede operarla: los clientes administran sus
    propias cuentas desde la app pública y no tienen permisos de backoffice.
    Para cuentas de terceros se exige `permission`. Pasar `owner_id=None` fuerza
    la verificación del permiso (p. ej. reasignar la cuenta a otro usuario).
    """
    if _auth_bypassed():
        return
    caller_id = _caller_id(current_user)
    if owner_id is not None and str(owner_id) == caller_id:
        return
    if permission not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso requerido: {permission}",
        )


@router.get("/", response_model=List[BankAccountReadDTO])
async def list_bank_accounts(
    use_case: ListBankAccountsUseCaseDep,
    permissions: PermissionsDep,
    current_user: CurrentUserDep,
    user_id: Optional[UUID] = Query(None, description="Filtro por ID de usuario"),
):
    """Lista cuentas bancarias. Sin `bank_accounts.view` solo devuelve las propias."""
    if not _auth_bypassed() and "bank_accounts.view" not in permissions:
        caller_id = _caller_id(current_user)
        if user_id is not None and str(user_id) != caller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: bank_accounts.view",
            )
        user_id = UUID(caller_id)
    return await use_case.execute(user_id=user_id)


@router.get("/{bank_account_id}", response_model=BankAccountReadDTO)
async def get_bank_account_by_id(
    bank_account_id: UUID,
    use_case: GetBankAccountByIdUseCaseDep,
    permissions: PermissionsDep,
    current_user: CurrentUserDep,
):
    entity = await use_case.execute(bank_account_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    _ensure_access("bank_accounts.view", entity.user_id, permissions, current_user)
    return entity


@router.post("/", response_model=BankAccountReadDTO, status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    cmd: BankAccountCreateCmd,
    use_case: CreateBankAccountUseCaseDep,
    permissions: PermissionsDep,
    current_user: CurrentUserDep,
):
    _ensure_access("bank_accounts.create", cmd.user_id, permissions, current_user)
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=BankAccountReadDTO)
async def update_bank_account(
    cmd: BankAccountUpdateCmd,
    use_case: UpdateBankAccountUseCaseDep,
    get_use_case: GetBankAccountByIdUseCaseDep,
    permissions: PermissionsDep,
    current_user: CurrentUserDep,
):
    existing = await get_use_case.execute(cmd.id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    _ensure_access("bank_accounts.update", existing.user_id, permissions, current_user)
    if cmd.user_id is not None and str(cmd.user_id) != str(existing.user_id):
        # Mover la cuenta a otro usuario no es una operación de dueño.
        _ensure_access("bank_accounts.update", None, permissions, current_user)
    try:
        entity = await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not entity:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    return entity


@router.delete("/{bank_account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_account(
    bank_account_id: UUID,
    use_case: DeleteBankAccountUseCaseDep,
    get_use_case: GetBankAccountByIdUseCaseDep,
    permissions: PermissionsDep,
    current_user: CurrentUserDep,
):
    existing = await get_use_case.execute(bank_account_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    _ensure_access("bank_accounts.delete", existing.user_id, permissions, current_user)
    if not await use_case.execute(bank_account_id):
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")

# app/modules/transactions/adapters/router/transaction_routes.py
"""Rutas para el módulo de transacciones."""
import json
from datetime import datetime
from typing import List, Optional, Tuple, Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.modules.transactions.domain.enums import TransactionStatus
from app.shared.services.file_service import save_transaction_voucher
from app.modules.transactions.application.schemas import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
    ImportRequestCmd,
    ImportResponseDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetTransactionByIdUseCaseDep,
    ListTransactionsUseCaseDep,
    CreateTransactionUseCaseDep,
    UpdateTransactionUseCaseDep,
    DeleteTransactionUseCaseDep,
    ImportTransactionsUseCaseDep,
)

router = APIRouter(tags=["transactions"])

# Constantes de mensajes de error
MSG_TRANSACTION_NOT_FOUND = "Transacción no encontrada"
MSG_INVALID_JSON = "JSON inválido"

def _is_form_request(content_type: str) -> bool:
    """Indica si el Content-Type corresponde a form-data."""
    return "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type


async def _parse_create_request(
    request: Request,
) -> Tuple[
    TransactionCreateCmd,
    Optional[UploadFile],
    Optional[UploadFile],
    Optional[UploadFile],
]:
    """Parsea el request y retorna (cmd, send_voucher, payment_voucher, checked_image)."""
    if _is_form_request(request.headers.get("content-type", "")):
        form = await request.form()
        return TransactionCreateCmd.from_form_data(form)
    body = await request.json()
    return TransactionCreateCmd.model_validate(body), None, None, None


async def _parse_update_request(
    request: Request,
) -> Tuple[
    TransactionUpdateCmd,
    Optional[UploadFile],
    Optional[UploadFile],
    Optional[UploadFile],
]:
    """Parsea el request y retorna (cmd, send_voucher, payment_voucher, checked_image)."""
    if _is_form_request(request.headers.get("content-type", "")):
        form = await request.form()
        return TransactionUpdateCmd.from_form_data(form)
    body = await request.json()
    return TransactionUpdateCmd.model_validate(body), None, None, None


async def _apply_transaction_uploads(
    cmd: Union[TransactionCreateCmd, TransactionUpdateCmd],
    send_file: Optional[UploadFile],
    payment_file: Optional[UploadFile],
    checked_image_file: Optional[UploadFile],
) -> None:
    """Guarda vouchers e imagen de checklist; asigna rutas relativas al cmd."""
    if send_file and send_file.filename:
        cmd.send_voucher = await save_transaction_voucher(send_file, "send")
    if payment_file and payment_file.filename:
        cmd.payment_voucher = await save_transaction_voucher(payment_file, "payment")
    if checked_image_file and checked_image_file.filename:
        cmd.checked_image = await save_transaction_voucher(checked_image_file, "checked")


# =============================================================================
# Rutas
# =============================================================================


@router.get("/", response_model=List[TransactionReadDTO])
async def list_transactions(
    use_case: ListTransactionsUseCaseDep,
    status: Optional[TransactionStatus] = Query(
        None,
        description="Filtro por estado (verification, verified, completed, failed, pending, checked, …)",
    ),
    user_id: Optional[UUID] = Query(None, description="Filtro por ID de usuario"),
    bank_account_origin_id: Optional[UUID] = Query(None, description="Filtro por cuenta origen"),
    bank_account_destination_id: Optional[UUID] = Query(None, description="Filtro por cuenta destino"),
    created_at_from: Optional[datetime] = Query(None, description="Filtro: transacciones desde esta fecha (ISO)"),
    created_at_to: Optional[datetime] = Query(None, description="Filtro: transacciones hasta esta fecha (ISO)"),
):
    """Lista transacciones con filtros opcionales."""
    return await use_case.execute(
        status=status,
        user_id=user_id,
        bank_account_origin_id=bank_account_origin_id,
        bank_account_destination_id=bank_account_destination_id,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )


@router.post(
    "/import/",
    response_model=ImportResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Importar datos (JSON)",
    responses={
        201: {"description": "Importación completada"},
        400: {"description": "Datos inválidos"},
    },
)
async def import_data(use_case: ImportTransactionsUseCaseDep, body: ImportRequestCmd):
    """Recibe JSON con datos parseados. El frontend parsea el archivo localmente y envía los datos."""
    try:
        return await use_case.execute(body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors())
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referencia inválida en los datos importados",
        )


@router.get("/{transaction_id}", response_model=TransactionReadDTO)
async def get_transaction_by_id(transaction_id: UUID, use_case: GetTransactionByIdUseCaseDep):
    """Obtiene una transacción por ID."""
    entity = await use_case.execute(transaction_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_TRANSACTION_NOT_FOUND)
    return entity


@router.post(
    "/",
    response_model=TransactionReadDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create Transaction",
    responses={
        201: {"description": "Transacción creada"},
        400: {"description": "Datos inválidos"},
        422: {"description": "Error de validación"},
    },
    openapi_extra={"requestBody": TransactionCreateCmd.openapi_request_body()},
)
async def create_transaction(request: Request, use_case: CreateTransactionUseCaseDep):
    """Crea transacción. Acepta JSON o form-data (multipart)."""
    try:
        cmd, send_f, pay_f, checked_img_f = await _parse_create_request(request)
        await _apply_transaction_uploads(cmd, send_f, pay_f, checked_img_f)
        return await use_case.execute(cmd)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{MSG_INVALID_JSON}: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors())
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referencia inválida: bank_account_origin, bank_account_destination, user, tax_rate, commission o coupon no existe",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/",
    response_model=TransactionReadDTO,
    responses={
        200: {"description": "Transacción actualizada"},
        400: {"description": "Datos inválidos"},
        404: {"description": "Transacción no encontrada"},
    },
)
async def update_transaction(request: Request, use_case: UpdateTransactionUseCaseDep):
    """Actualiza transacción. Acepta JSON o form-data (multipart)."""
    try:
        cmd, send_f, pay_f, checked_img_f = await _parse_update_request(request)
        await _apply_transaction_uploads(cmd, send_f, pay_f, checked_img_f)
        entity = await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_TRANSACTION_NOT_FOUND)
    return entity


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Transaction",
)
async def delete_transaction(transaction_id: UUID, use_case: DeleteTransactionUseCaseDep):
    """Elimina una transacción por ID."""
    await use_case.execute(transaction_id)

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
    TransactionListPage,
    TransactionMetricsDTO,
    ImportRequestCmd,
    ImportResponseDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetTransactionByIdUseCaseDep,
    ListTransactionsUseCaseDep,
    GetTransactionMetricsUseCaseDep,
    CreateTransactionUseCaseDep,
    UpdateTransactionUseCaseDep,
    DeleteTransactionUseCaseDep,
    ImportTransactionsUseCaseDep,
)
from app.modules.transactions.application.use_cases.transaction_use_cases import (
    _parse_currency_filter,
)

router = APIRouter(tags=["transactions"])

# Constantes de mensajes de error
MSG_TRANSACTION_NOT_FOUND = "Transacción no encontrada"
MSG_INVALID_JSON = "JSON inválido"

def _is_form_request(content_type: str) -> bool:
    """Indica si el Content-Type corresponde a form-data."""
    return "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type


def _as_upload_file(value: object) -> Optional[UploadFile]:
    """Retorna el archivo solo si realmente es un UploadFile válido."""
    if value is None or isinstance(value, str):
        return None
    filename = getattr(value, "filename", None)
    read = getattr(value, "read", None)
    if filename and callable(read):
        return value
    return None


def _as_upload_files(value: object) -> List[UploadFile]:
    values = value if isinstance(value, list) else [value]
    files: List[UploadFile] = []
    for item in values:
        file = _as_upload_file(item)
        if file is not None:
            files.append(file)
    return files


async def _parse_create_request(
    request: Request,
) -> Tuple[
    TransactionCreateCmd,
    List[UploadFile],
    List[UploadFile],
    List[UploadFile],
]:
    """Parsea el request y retorna (cmd, send_voucher, payment_voucher, checked_image)."""
    if _is_form_request(request.headers.get("content-type", "")):
        form = await request.form()
        return TransactionCreateCmd.from_form_data(form)
    body = await request.json()
    return TransactionCreateCmd.model_validate(body), [], [], []


async def _parse_update_request(
    request: Request,
) -> Tuple[
    TransactionUpdateCmd,
    List[UploadFile],
    List[UploadFile],
    List[UploadFile],
]:
    """Parsea el request y retorna (cmd, send_voucher, payment_voucher, checked_image)."""
    if _is_form_request(request.headers.get("content-type", "")):
        form = await request.form()
        return TransactionUpdateCmd.from_form_data(form)
    body = await request.json()
    return TransactionUpdateCmd.model_validate(body), [], [], []


async def _save_transaction_vouchers(files: List[UploadFile], prefix: str) -> List[str]:
    paths: List[str] = []
    for file in _as_upload_files(files):
        if file.filename:
            paths.append(await save_transaction_voucher(file, prefix))
    return paths


async def _apply_transaction_uploads(
    cmd: Union[TransactionCreateCmd, TransactionUpdateCmd],
    send_files: List[UploadFile],
    payment_files: List[UploadFile],
    checked_image_files: List[UploadFile],
) -> None:
    """Guarda vouchers e imagen de checklist; asigna rutas relativas al cmd."""
    send_paths = await _save_transaction_vouchers(send_files, "send")
    payment_paths = await _save_transaction_vouchers(payment_files, "payment")
    checked_paths = await _save_transaction_vouchers(checked_image_files, "checked")

    if send_paths:
        cmd.send_vouchers = send_paths
        cmd.send_voucher = send_paths[0]
    if payment_paths:
        cmd.payment_vouchers = payment_paths
        cmd.payment_voucher = payment_paths[0]
    if checked_paths:
        cmd.checked_images = checked_paths
        cmd.checked_image = checked_paths[0]


# =============================================================================
# Rutas
# =============================================================================


@router.get("/", response_model=TransactionListPage)
async def list_transactions(
    use_case: ListTransactionsUseCaseDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[TransactionStatus] = Query(
        None,
        description="Filtro por estado (verification, verified, completed, failed, pending, checked, …)",
    ),
    user_id: Optional[UUID] = Query(None, description="Filtro por ID de usuario"),
    bank_account_origin_id: Optional[UUID] = Query(None, description="Filtro por cuenta origen"),
    bank_account_destination_id: Optional[UUID] = Query(None, description="Filtro por cuenta destino"),
    bank_account_id: Optional[UUID] = Query(None, description="Filtro por cuenta (origen o destino)"),
    created_at_from: Optional[datetime] = Query(None, description="Filtro: transacciones desde esta fecha (ISO)"),
    created_at_to: Optional[datetime] = Query(None, description="Filtro: transacciones hasta esta fecha (ISO)"),
    send_date_from: Optional[datetime] = Query(None, description="Filtro: send_date desde esta fecha (ISO)"),
    send_date_to: Optional[datetime] = Query(None, description="Filtro: send_date hasta esta fecha (ISO)"),
    search: Optional[str] = Query(None, description="Búsqueda de texto libre por código, nº de operación o id"),
    currency: Optional[str] = Query(
        None,
        description="Filtro por moneda (PEN, USD, BRL): origen o destino de la tasa",
    ),
    origin_currency: Optional[str] = Query(
        None,
        description="Filtro por moneda origen de la tasa (coin_a)",
    ),
    destination_currency: Optional[str] = Query(
        None,
        description="Filtro por moneda destino de la tasa (coin_b)",
    ),
):
    """Lista transacciones con filtros opcionales y paginación."""
    try:
        currency_filter = _parse_currency_filter(currency)
        origin_currency_filter = _parse_currency_filter(origin_currency)
        destination_currency_filter = _parse_currency_filter(destination_currency)
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=400,
            detail="Moneda no válida. Use PEN, USD o BRL.",
        )
    return await use_case.execute(
        limit=limit,
        skip=skip,
        status=status,
        user_id=user_id,
        bank_account_origin_id=bank_account_origin_id,
        bank_account_destination_id=bank_account_destination_id,
        bank_account_id=bank_account_id,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        send_date_from=send_date_from,
        send_date_to=send_date_to,
        search=search,
        currency=currency_filter,
        origin_currency=origin_currency_filter,
        destination_currency=destination_currency_filter,
    )


@router.get("/metrics", response_model=TransactionMetricsDTO)
async def transaction_metrics(use_case: GetTransactionMetricsUseCaseDep):
    """Métricas agregadas para el dashboard (sobre todas las transacciones)."""
    return await use_case.execute()


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
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{MSG_INVALID_JSON}: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors())
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

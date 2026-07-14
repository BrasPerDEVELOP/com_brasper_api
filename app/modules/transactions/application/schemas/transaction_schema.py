# app/modules/transactions/application/schemas/transaction_schema.py
import json
from datetime import datetime
from typing import Any, List, Optional, Tuple
from uuid import UUID

from fastapi import File, Form, UploadFile
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, field_serializer, model_validator

from app.modules.transactions.domain.enums import AccountFlowType, BankCountry, SocialActor, TransactionStatus
from app.modules.users.domain.enums import UserRole
from app.shared.media import to_media_url, to_media_urls



def _parse_optional_datetime(v: Optional[str]) -> Optional[datetime]:
    """Convierte string ISO a datetime o None."""
    if not v or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_optional_float(v: Optional[str]) -> Optional[float]:
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_optional_uuid(v: Optional[str]) -> Optional[UUID]:
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        return UUID(v)
    except (ValueError, TypeError):
        return None


def _parse_checked(v: Any) -> Optional[bool]:
    """Parse checkbox value to bool or None if not provided."""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    return str(v).lower() in ("true", "1", "yes", "on")


def _field_present(value: Any) -> bool:
    """Indica si un campo opcional fue enviado en el request."""
    return value is not None


def _as_upload_file(value: Any) -> Optional[UploadFile]:
    """Retorna el archivo si el valor se comporta como UploadFile."""
    if value is None or isinstance(value, str):
        return None
    filename = getattr(value, "filename", None)
    read = getattr(value, "read", None)
    if filename and callable(read):
        return value
    return None


def _as_upload_files(value: Any) -> List[UploadFile]:
    """Normaliza uno o varios valores de form-data a lista de UploadFile."""
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    files: List[UploadFile] = []
    for item in values:
        file = _as_upload_file(item)
        if file is not None:
            files.append(file)
    return files


def _form_upload_files(form: Any, *keys: str) -> List[UploadFile]:
    files: List[UploadFile] = []
    for key in keys:
        if key not in form:
            continue
        if hasattr(form, "getlist"):
            files.extend(_as_upload_files(form.getlist(key)))
        else:
            files.extend(_as_upload_files(form.get(key)))
    return files


class TransactionDestinationInput(BaseModel):
    bank_account_id: UUID
    amount: float = Field(gt=0)


class TransactionDestinationDTO(TransactionDestinationInput):
    id: UUID
    position: int

    model_config = ConfigDict(from_attributes=True)


def _parse_destinations(value: Any) -> Optional[List[TransactionDestinationInput]]:
    """Acepta la lista JSON del multipart o una lista ya decodificada."""
    if value is None or value == "":
        return None
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, list):
        raise ValueError("destinations debe ser una lista")
    return [TransactionDestinationInput.model_validate(item) for item in raw]


def _parse_string_list(value: Any) -> Optional[List[str]]:
    """Lista de strings desde form-data: JSON array, valor único o lista ya decodificada."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                value = json.loads(s)
            except (TypeError, ValueError):
                value = [s]
        else:
            value = [s]
    if not isinstance(value, list):
        value = [value]
    return [str(item).strip() for item in value if item is not None and str(item).strip()]


class TransactionCreateCmd(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bank_account_origin": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "bank_account_destination": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "agent_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "tax_rate_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "commission_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "verification",
                "origin_amount": 100.0,
                "destination_amount": 95.0,
                "code": "",
                "commission_result": 5.0,
                "total_to_send": 100.0,
                "bank_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "social_reason_bank_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "bank_name": "Banco ejemplo",
                "company_name": "Empresa ejemplo",
                "coupon_discount_code": "SUMMER10",
                "coupon_origin_amount": 100.0,
                "coupon_destination_amount": 90.0,
                "coupon_discount_percentage": 10.0,
                "coupon_discount_commission": 0.5,
                "coupon_discount_total_to_send": 99.5,
            }
        }
    )

    @staticmethod
    def openapi_request_body() -> dict:
        """Especificación OpenAPI del request body (JSON y multipart)."""
        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/TransactionCreateCmd"},
                },
                "multipart/form-data": {
                    "schema": {"$ref": "#/components/schemas/TransactionCreateCmd"},
                },
            },
        }

    bank_account_origin: Optional[UUID] = None
    bank_account_destination: UUID
    destinations: Optional[List[TransactionDestinationInput]] = None
    user_id: UUID
    agent_id: Optional[UUID] = None
    tax_rate_id: UUID
    commission_id: UUID
    bank_id: Optional[UUID] = Field(
        default=None,
        description="Opcional; debe coincidir con el banco de la cuenta destino. Si se omite, se asigna desde el servidor.",
    )
    social_reason_bank_id: Optional[UUID] = Field(
        default=None,
        description="Banco exacto elegido como razón social; el servidor deriva company_name desde este banco.",
    )
    bank_name: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Opcional; snapshot del nombre del banco (Bank.bank). Si se omite, se rellena desde la cuenta destino.",
    )
    company_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Opcional; snapshot de la empresa (Bank.company). Si se omite, se rellena desde la cuenta destino.",
    )
    status: TransactionStatus = TransactionStatus.verification
    origin_amount: float
    destination_amount: float
    code: str = Field(
        default="",
        description="Generado en servidor (p. ej. PxB-0000000001); el valor enviado se ignora",
    )
    operation_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("operation_number", "numero_operacion"),
        description="Número de operación asignado al editar/verificar la transacción",
    )
    commission_result: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("commission_result", "resultado_comision"),
    )
    total_to_send: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("total_to_send", "total_a_enviar"),
    )
    tax_amount: Optional[float] = None
    coupon_id: Optional[UUID] = None
    coupon_discount_code: Optional[str] = None
    coupon_origin_amount: Optional[float] = None
    coupon_destination_amount: Optional[float] = None
    coupon_discount_percentage: Optional[float] = None
    coupon_discount_commission: Optional[float] = None
    coupon_discount_total_to_send: Optional[float] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = Field(
        default=None,
        description="Ruta relativa de archivo asociado al checklist; acepta imagen o documento (multipart: campo checked_image)",
    )
    send_vouchers: Optional[List[str]] = None
    payment_vouchers: Optional[List[str]] = None
    checked_images: Optional[List[str]] = None
    checked: bool = False

    @classmethod
    def from_form(
        cls,
        bank_account_origin: Optional[str] = Form(None, description="UUID cuenta origen (opcional)"),
        bank_account_destination: str = Form(..., description="UUID cuenta destino"),
        destinations: Optional[str] = Form(None, description="Distribución destino como JSON"),
        user_id: str = Form(..., description="UUID de usuario"),
        agent_id: Optional[str] = Form(None, description="UUID del agente asignado"),
        tax_rate_id: str = Form(..., description="UUID de tasa"),
        commission_id: str = Form(..., description="UUID de comisión"),
        bank_id: Optional[str] = Form(None, description="UUID del banco (opcional; debe coincidir con cuenta destino)"),
        social_reason_bank_id: Optional[str] = Form(None, description="UUID del banco elegido como razón social"),
        bank_name: Optional[str] = Form(None, description="Nombre del banco (opcional; snapshot)"),
        company_name: Optional[str] = Form(None, description="Nombre de empresa (opcional; snapshot)"),
        status: str = Form(
            "verification",
            description="Estado: verification, verified, completed, failed, pending, …",
        ),
        origin_amount: str = Form(..., description="Monto origen"),
        destination_amount: str = Form(..., description="Monto destino"),
        code: str = Form("", description="Opcional; el servidor genera el código (PxB-…)"),
        operation_number: Optional[str] = Form(None),
        commission_result: Optional[str] = Form(None),
        total_to_send: Optional[str] = Form(None),
        tax_amount: Optional[str] = Form(None),
        coupon_id: Optional[str] = Form(None),
        coupon_discount_code: Optional[str] = Form(None),
        coupon_origin_amount: Optional[str] = Form(None),
        coupon_destination_amount: Optional[str] = Form(None),
        coupon_discount_percentage: Optional[str] = Form(None),
        coupon_discount_commission: Optional[str] = Form(None),
        coupon_discount_total_to_send: Optional[str] = Form(None),
        send_date: Optional[str] = Form(None),
        payment_date: Optional[str] = Form(None),
        send_voucher: Optional[UploadFile] = File(None),
        payment_voucher: Optional[UploadFile] = File(None),
        checked_image: Optional[UploadFile] = File(None),
        checked: bool = Form(False),
    ) -> Tuple[
        "TransactionCreateCmd",
        List[UploadFile],
        List[UploadFile],
        List[UploadFile],
    ]:
        cmd = cls(
            bank_account_origin=_parse_optional_uuid(bank_account_origin),
            bank_account_destination=UUID(bank_account_destination),
            destinations=_parse_destinations(destinations),
            user_id=UUID(user_id),
            agent_id=_parse_optional_uuid(agent_id),
            tax_rate_id=UUID(tax_rate_id),
            commission_id=UUID(commission_id),
            bank_id=_parse_optional_uuid(bank_id),
            social_reason_bank_id=_parse_optional_uuid(social_reason_bank_id),
            bank_name=bank_name.strip() if bank_name and bank_name.strip() else None,
            company_name=company_name.strip() if company_name and company_name.strip() else None,
            status=TransactionStatus(status) if status else TransactionStatus.verification,
            origin_amount=float(origin_amount),
            destination_amount=float(destination_amount),
            code=code,
            operation_number=(
                operation_number.strip()
                if operation_number and operation_number.strip()
                else None
            ),
            commission_result=_parse_optional_float(commission_result),
            total_to_send=_parse_optional_float(total_to_send),
            tax_amount=_parse_optional_float(tax_amount),
            coupon_id=_parse_optional_uuid(coupon_id),
            coupon_discount_code=(
                coupon_discount_code.strip()
                if coupon_discount_code and coupon_discount_code.strip()
                else None
            ),
            coupon_origin_amount=_parse_optional_float(coupon_origin_amount),
            coupon_destination_amount=_parse_optional_float(coupon_destination_amount),
            coupon_discount_percentage=_parse_optional_float(coupon_discount_percentage),
            coupon_discount_commission=_parse_optional_float(coupon_discount_commission),
            coupon_discount_total_to_send=_parse_optional_float(coupon_discount_total_to_send),
            send_date=_parse_optional_datetime(send_date),
            payment_date=_parse_optional_datetime(payment_date),
            send_voucher=None,  # se llenará en la ruta tras guardar
            payment_voucher=None,
            checked_image=None,
            send_vouchers=None,
            payment_vouchers=None,
            checked_images=None,
            checked=checked,
        )
        return cmd, _as_upload_files(send_voucher), _as_upload_files(payment_voucher), _as_upload_files(checked_image)

    @classmethod
    def from_form_data(
        cls, form: Any
    ) -> Tuple[
        "TransactionCreateCmd",
        List[UploadFile],
        List[UploadFile],
        List[UploadFile],
    ]:
        """Construye cmd desde form-data. Retorna (cmd, send_voucher, payment_voucher, checked_image)."""
        _get = lambda k, d="": form.get(k, d) if hasattr(form, "get") else d
        cmd = cls(
            bank_account_origin=_parse_optional_uuid(_get("bank_account_origin")),
            bank_account_destination=UUID(_get("bank_account_destination", "")),
            destinations=_parse_destinations(_get("destinations") or None),
            user_id=UUID(_get("user_id", "")),
            agent_id=_parse_optional_uuid(_get("agent_id")),
            tax_rate_id=UUID(_get("tax_rate_id", "")),
            commission_id=UUID(_get("commission_id", "")),
            bank_id=_parse_optional_uuid(_get("bank_id")),
            social_reason_bank_id=_parse_optional_uuid(_get("social_reason_bank_id")),
            bank_name=(
                str(_get("bank_name") or "").strip() or None
            ),
            company_name=(
                str(_get("company_name") or "").strip() or None
            ),
            status=TransactionStatus(_get("status", "verification") or "verification"),
            origin_amount=float(_get("origin_amount", 0)),
            destination_amount=float(_get("destination_amount", 0)),
            code=_get("code", ""),
            operation_number=(
                str(_get("operation_number") or _get("numero_operacion") or "").strip() or None
            ),
            commission_result=_parse_optional_float(
                _get("commission_result") or _get("resultado_comision")
            ),
            total_to_send=_parse_optional_float(
                _get("total_to_send") or _get("total_a_enviar")
            ),
            tax_amount=_parse_optional_float(_get("tax_amount")),
            coupon_id=_parse_optional_uuid(_get("coupon_id")),
            coupon_discount_code=(
                str(_get("coupon_discount_code") or "").strip() or None
            ),
            coupon_origin_amount=_parse_optional_float(_get("coupon_origin_amount")),
            coupon_destination_amount=_parse_optional_float(_get("coupon_destination_amount")),
            coupon_discount_percentage=_parse_optional_float(_get("coupon_discount_percentage")),
            coupon_discount_commission=_parse_optional_float(_get("coupon_discount_commission")),
            coupon_discount_total_to_send=_parse_optional_float(
                _get("coupon_discount_total_to_send")
            ),
            send_date=_parse_optional_datetime(_get("send_date")),
            payment_date=_parse_optional_datetime(_get("payment_date")),
            send_voucher=None,
            payment_voucher=None,
            checked_image=None,
            send_vouchers=None,
            payment_vouchers=None,
            checked_images=None,
            checked=_get("checked", "false").lower() in ("true", "1", "yes"),
        )
        send_f = _form_upload_files(form, "send_voucher", "send_vouchers", "send_voucher_files")
        pay_f = _form_upload_files(form, "payment_voucher", "payment_vouchers", "payment_voucher_files")
        checked_img_f = _form_upload_files(form, "checked_image", "checked_images", "checked_image_files")
        return cmd, send_f, pay_f, checked_img_f


class TransactionUpdateCmd(BaseModel):
    id: UUID
    bank_account_origin: Optional[UUID] = None
    bank_account_destination: Optional[UUID] = None
    destinations: Optional[List[TransactionDestinationInput]] = None
    # bank_id/bank_name siguen a la cuenta destino; la razón social se identifica
    # de forma independiente y company_name se deriva del banco seleccionado.
    social_reason_bank_id: Optional[UUID] = None
    company_name: Optional[str] = None
    user_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    tax_rate_id: Optional[UUID] = None
    commission_id: Optional[UUID] = None
    status: Optional[TransactionStatus] = None
    origin_amount: Optional[float] = None
    destination_amount: Optional[float] = None
    code: Optional[str] = None
    operation_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("operation_number", "numero_operacion"),
    )
    commission_result: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("commission_result", "resultado_comision"),
    )
    total_to_send: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("total_to_send", "total_a_enviar"),
    )
    tax_amount: Optional[float] = None
    coupon_id: Optional[UUID] = None
    coupon_discount_code: Optional[str] = None
    coupon_origin_amount: Optional[float] = None
    coupon_destination_amount: Optional[float] = None
    coupon_discount_percentage: Optional[float] = None
    coupon_discount_commission: Optional[float] = None
    coupon_discount_total_to_send: Optional[float] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = None
    send_vouchers: Optional[List[str]] = None
    payment_vouchers: Optional[List[str]] = None
    checked_images: Optional[List[str]] = None
    # Borrado individual: lista autoritativa de archivos EXISTENTES a conservar
    # (keys relativas o URLs completas del GET). Los uploads del request se agregan después.
    send_vouchers_keep: Optional[List[str]] = None
    payment_vouchers_keep: Optional[List[str]] = None
    checked_images_keep: Optional[List[str]] = None
    checked: Optional[bool] = None
    remove_send_voucher: Optional[bool] = None
    remove_payment_voucher: Optional[bool] = None
    remove_checked_image: Optional[bool] = None

    @classmethod
    def from_form(
        cls,
        id: str = Form(..., description="UUID de la transacción"),
        bank_account_origin: Optional[str] = Form(None),
        bank_account_destination: Optional[str] = Form(None),
        destinations: Optional[str] = Form(None),
        social_reason_bank_id: Optional[str] = Form(None),
        company_name: Optional[str] = Form(None),
        user_id: Optional[str] = Form(None),
        agent_id: Optional[str] = Form(None),
        tax_rate_id: Optional[str] = Form(None),
        commission_id: Optional[str] = Form(None),
        status: Optional[str] = Form(None),
        origin_amount: Optional[str] = Form(None),
        destination_amount: Optional[str] = Form(None),
        code: Optional[str] = Form(None),
        operation_number: Optional[str] = Form(None),
        commission_result: Optional[str] = Form(None),
        total_to_send: Optional[str] = Form(None),
        tax_amount: Optional[str] = Form(None),
        coupon_id: Optional[str] = Form(None),
        coupon_discount_code: Optional[str] = Form(None),
        coupon_origin_amount: Optional[str] = Form(None),
        coupon_destination_amount: Optional[str] = Form(None),
        coupon_discount_percentage: Optional[str] = Form(None),
        coupon_discount_commission: Optional[str] = Form(None),
        coupon_discount_total_to_send: Optional[str] = Form(None),
        send_date: Optional[str] = Form(None),
        payment_date: Optional[str] = Form(None),
        send_voucher: Optional[UploadFile] = File(None),
        payment_voucher: Optional[UploadFile] = File(None),
        checked_image: Optional[UploadFile] = File(None),
        checked: Optional[str] = Form(None),
        remove_send_voucher: Optional[str] = Form(None),
        remove_payment_voucher: Optional[str] = Form(None),
        remove_checked_image: Optional[str] = Form(None),
    ) -> Tuple[
        "TransactionUpdateCmd",
        List[UploadFile],
        List[UploadFile],
        List[UploadFile],
    ]:
        payload = {"id": UUID(id)}
        if _field_present(bank_account_origin):
            payload["bank_account_origin"] = _parse_optional_uuid(bank_account_origin)
        if _field_present(bank_account_destination):
            payload["bank_account_destination"] = _parse_optional_uuid(bank_account_destination)
        if _field_present(destinations):
            payload["destinations"] = _parse_destinations(destinations)
        if _field_present(social_reason_bank_id):
            payload["social_reason_bank_id"] = _parse_optional_uuid(social_reason_bank_id)
        if _field_present(company_name):
            payload["company_name"] = company_name.strip() if company_name and company_name.strip() else None
        if _field_present(user_id):
            payload["user_id"] = _parse_optional_uuid(user_id)
        if _field_present(agent_id):
            payload["agent_id"] = _parse_optional_uuid(agent_id)
        if _field_present(tax_rate_id):
            payload["tax_rate_id"] = _parse_optional_uuid(tax_rate_id)
        if _field_present(commission_id):
            payload["commission_id"] = _parse_optional_uuid(commission_id)
        if _field_present(status):
            payload["status"] = TransactionStatus(status) if status else None
        if _field_present(origin_amount):
            payload["origin_amount"] = _parse_optional_float(origin_amount)
        if _field_present(destination_amount):
            payload["destination_amount"] = _parse_optional_float(destination_amount)
        if _field_present(code):
            payload["code"] = code
        if _field_present(operation_number):
            payload["operation_number"] = (
                operation_number.strip()
                if operation_number and operation_number.strip()
                else None
            )
        if _field_present(commission_result):
            payload["commission_result"] = _parse_optional_float(commission_result)
        if _field_present(total_to_send):
            payload["total_to_send"] = _parse_optional_float(total_to_send)
        if _field_present(tax_amount):
            payload["tax_amount"] = _parse_optional_float(tax_amount)
        if _field_present(coupon_id):
            payload["coupon_id"] = _parse_optional_uuid(coupon_id)
        if _field_present(coupon_discount_code):
            payload["coupon_discount_code"] = (
                coupon_discount_code.strip()
                if coupon_discount_code and coupon_discount_code.strip()
                else None
            )
        if _field_present(coupon_origin_amount):
            payload["coupon_origin_amount"] = _parse_optional_float(coupon_origin_amount)
        if _field_present(coupon_destination_amount):
            payload["coupon_destination_amount"] = _parse_optional_float(coupon_destination_amount)
        if _field_present(coupon_discount_percentage):
            payload["coupon_discount_percentage"] = _parse_optional_float(coupon_discount_percentage)
        if _field_present(coupon_discount_commission):
            payload["coupon_discount_commission"] = _parse_optional_float(coupon_discount_commission)
        if _field_present(coupon_discount_total_to_send):
            payload["coupon_discount_total_to_send"] = _parse_optional_float(
                coupon_discount_total_to_send
            )
        if _field_present(send_date):
            payload["send_date"] = _parse_optional_datetime(send_date)
        if _field_present(payment_date):
            payload["payment_date"] = _parse_optional_datetime(payment_date)
        if _field_present(checked):
            payload["checked"] = _parse_checked(checked)
        if _field_present(remove_send_voucher):
            payload["remove_send_voucher"] = _parse_checked(remove_send_voucher)
        if _field_present(remove_payment_voucher):
            payload["remove_payment_voucher"] = _parse_checked(remove_payment_voucher)
        if _field_present(remove_checked_image):
            payload["remove_checked_image"] = _parse_checked(remove_checked_image)

        cmd = cls(**payload)
        return cmd, _as_upload_files(send_voucher), _as_upload_files(payment_voucher), _as_upload_files(checked_image)

    @classmethod
    def from_form_data(
        cls, form: Any
    ) -> Tuple[
        "TransactionUpdateCmd",
        List[UploadFile],
        List[UploadFile],
        List[UploadFile],
    ]:
        """Construye cmd desde form-data. Retorna (cmd, send_voucher, payment_voucher, checked_image)."""
        _get = lambda k, d=None: form.get(k, d) if hasattr(form, "get") else d
        payload = {"id": UUID(_get("id", ""))}
        if "bank_account_origin" in form:
            payload["bank_account_origin"] = _parse_optional_uuid(_get("bank_account_origin"))
        if "bank_account_destination" in form:
            payload["bank_account_destination"] = _parse_optional_uuid(_get("bank_account_destination"))
        if "destinations" in form:
            payload["destinations"] = _parse_destinations(_get("destinations"))
        if "social_reason_bank_id" in form:
            payload["social_reason_bank_id"] = _parse_optional_uuid(_get("social_reason_bank_id"))
        if "company_name" in form:
            payload["company_name"] = str(_get("company_name") or "").strip() or None
        if "user_id" in form:
            payload["user_id"] = _parse_optional_uuid(_get("user_id"))
        if "agent_id" in form:
            payload["agent_id"] = _parse_optional_uuid(_get("agent_id"))
        if "tax_rate_id" in form:
            payload["tax_rate_id"] = _parse_optional_uuid(_get("tax_rate_id"))
        if "commission_id" in form:
            payload["commission_id"] = _parse_optional_uuid(_get("commission_id"))
        if "status" in form:
            payload["status"] = TransactionStatus(_get("status")) if _get("status") else None
        if "origin_amount" in form:
            payload["origin_amount"] = _parse_optional_float(_get("origin_amount"))
        if "destination_amount" in form:
            payload["destination_amount"] = _parse_optional_float(_get("destination_amount"))
        if "code" in form:
            payload["code"] = _get("code")
        if "operation_number" in form or "numero_operacion" in form:
            raw_operation_number = _get("operation_number") or _get("numero_operacion")
            payload["operation_number"] = (
                str(raw_operation_number).strip()
                if raw_operation_number and str(raw_operation_number).strip()
                else None
            )
        if "commission_result" in form or "resultado_comision" in form:
            payload["commission_result"] = _parse_optional_float(
                _get("commission_result") or _get("resultado_comision")
            )
        if "total_to_send" in form or "total_a_enviar" in form:
            payload["total_to_send"] = _parse_optional_float(
                _get("total_to_send") or _get("total_a_enviar")
            )
        if "tax_amount" in form:
            payload["tax_amount"] = _parse_optional_float(_get("tax_amount"))
        if "coupon_id" in form:
            payload["coupon_id"] = _parse_optional_uuid(_get("coupon_id"))
        if "coupon_discount_code" in form:
            payload["coupon_discount_code"] = (
                str(_get("coupon_discount_code") or "").strip() or None
            )
        if "coupon_origin_amount" in form:
            payload["coupon_origin_amount"] = _parse_optional_float(_get("coupon_origin_amount"))
        if "coupon_destination_amount" in form:
            payload["coupon_destination_amount"] = _parse_optional_float(
                _get("coupon_destination_amount")
            )
        if "coupon_discount_percentage" in form:
            payload["coupon_discount_percentage"] = _parse_optional_float(
                _get("coupon_discount_percentage")
            )
        if "coupon_discount_commission" in form:
            payload["coupon_discount_commission"] = _parse_optional_float(
                _get("coupon_discount_commission")
            )
        if "coupon_discount_total_to_send" in form:
            payload["coupon_discount_total_to_send"] = _parse_optional_float(
                _get("coupon_discount_total_to_send")
            )
        if "send_date" in form:
            payload["send_date"] = _parse_optional_datetime(_get("send_date"))
        if "payment_date" in form:
            payload["payment_date"] = _parse_optional_datetime(_get("payment_date"))
        if "checked" in form:
            payload["checked"] = _parse_checked(_get("checked"))
        if "remove_send_voucher" in form:
            payload["remove_send_voucher"] = _parse_checked(_get("remove_send_voucher"))
        if "remove_payment_voucher" in form:
            payload["remove_payment_voucher"] = _parse_checked(_get("remove_payment_voucher"))
        if "remove_checked_image" in form:
            payload["remove_checked_image"] = _parse_checked(_get("remove_checked_image"))
        if "send_vouchers_keep" in form:
            payload["send_vouchers_keep"] = _parse_string_list(_get("send_vouchers_keep"))
        if "payment_vouchers_keep" in form:
            payload["payment_vouchers_keep"] = _parse_string_list(_get("payment_vouchers_keep"))
        if "checked_images_keep" in form:
            payload["checked_images_keep"] = _parse_string_list(_get("checked_images_keep"))

        cmd = cls(**payload)
        send_f = _form_upload_files(form, "send_voucher", "send_vouchers", "send_voucher_files")
        pay_f = _form_upload_files(form, "payment_voucher", "payment_vouchers", "payment_voucher_files")
        checked_img_f = _form_upload_files(form, "checked_image", "checked_images", "checked_image_files")
        return cmd, send_f, pay_f, checked_img_f


class TransactionUserRef(BaseModel):
    """Referencia al usuario de la transacción (mismo id que `user_id`)."""

    id: UUID
    role: Optional[UserRole] = None

    @field_validator("role", mode="before")
    @classmethod
    def _coerce_role(cls, v: Any) -> Any:
        if v is None or v == "":
            return None
        if isinstance(v, UserRole):
            return v
        try:
            return UserRole(v)
        except ValueError:
            return None


class TransactionReadDTO(BaseModel):
    id: UUID
    bank_account_origin_id: Optional[UUID] = None
    bank_account_destination_id: UUID
    destinations: List[TransactionDestinationDTO] = Field(default_factory=list)
    bank_id: Optional[UUID] = None
    social_reason_bank_id: Optional[UUID] = None
    bank_name: Optional[str] = None
    company_name: Optional[str] = None
    user_id: UUID
    agent_id: Optional[UUID] = None
    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus
    origin_amount: float
    destination_amount: float
    code: str
    operation_number: Optional[str] = None
    commission_result: Optional[float] = None
    total_to_send: Optional[float] = None
    tax_amount: Optional[float] = None
    coupon_id: Optional[UUID] = None
    coupon_discount_code: Optional[str] = None
    coupon_origin_amount: Optional[float] = None
    coupon_destination_amount: Optional[float] = None
    coupon_discount_percentage: Optional[float] = None
    coupon_discount_commission: Optional[float] = None
    coupon_discount_total_to_send: Optional[float] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = None
    send_vouchers: List[str] = Field(default_factory=list)
    payment_vouchers: List[str] = Field(default_factory=list)
    checked_images: List[str] = Field(default_factory=list)
    checked: bool = False
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime
    user: TransactionUserRef

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("send_voucher", "payment_voucher", "checked_image")
    def _serialize_voucher_media(self, value, _info):
        return to_media_url(value)

    @field_serializer("send_vouchers", "payment_vouchers", "checked_images")
    def _serialize_voucher_media_lists(self, value, _info):
        return to_media_urls(value)

    @field_validator("send_vouchers", "payment_vouchers", "checked_images", mode="before")
    @classmethod
    def _coerce_voucher_list(cls, value: Any) -> List[str]:
        if value is None or value == "":
            return []
        values = value if isinstance(value, list) else [value]
        return [str(item).strip() for item in values if str(item).strip()]

    @model_validator(mode="before")
    @classmethod
    def _inject_user_from_orm(cls, data: Any) -> Any:
        from app.modules.transactions.domain.models import Transaction as TransactionModel

        if isinstance(data, TransactionModel):
            payload = {c.name: getattr(data, c.name) for c in data.__table__.columns}
            payload["destinations"] = list(getattr(data, "destinations", None) or [])
            u = getattr(data, "user", None)
            payload["user"] = {
                "id": data.user_id,
                "role": u.role if u is not None else None,
            }
            return payload
        if isinstance(data, dict) and "user_id" in data and "user" not in data:
            uid = data["user_id"]
            return {
                **data,
                "user": {"id": uid, "role": data.get("user_role")},
            }
        return data


class TransactionListPage(BaseModel):
    items: list[TransactionReadDTO]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_previous: bool


class TransactionMetricsDTO(BaseModel):
    """Agregados globales para el dashboard (sobre todas las transacciones)."""

    total: int
    by_status: dict[str, int]
    volume_origin: float
    volume_destination: float
    last_7_days: int


class BankAccountImportPayload(BaseModel):
    """Cuenta bancaria para importación (sin user_id; se asigna al crear)."""

    bank_id: UUID
    account_flow: AccountFlowType
    account_holder_type: SocialActor
    bank_country: BankCountry
    holder_names: Optional[str] = None
    holder_surnames: Optional[str] = None
    document_number: Optional[int] = None
    business_name: Optional[str] = None
    ruc_number: Optional[int] = None
    legal_representative_name: Optional[str] = None
    legal_representative_document: Optional[int] = None
    account_number: Optional[int] = None
    account_number_confirmation: Optional[int] = None
    cci_number: Optional[int] = None
    cci_number_confirmation: Optional[int] = None
    pix_key: Optional[str] = None
    pix_key_confirmation: Optional[str] = None
    pix_key_type: Optional[str] = None
    cpf: Optional[int] = None


class TransactionImportPayload(BaseModel):
    """Campos de transacción para importación (sin user_id, cuentas ni code; se asignan/autogeneran al crear)."""

    agent_id: Optional[UUID] = None
    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus = TransactionStatus.verification
    origin_amount: float
    destination_amount: float
    operation_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("operation_number", "numero_operacion"),
    )
    commission_result: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("commission_result", "resultado_comision"),
    )
    total_to_send: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("total_to_send", "total_a_enviar"),
    )
    tax_amount: Optional[float] = None
    coupon_id: Optional[UUID] = None
    coupon_discount_code: Optional[str] = None
    coupon_origin_amount: Optional[float] = None
    coupon_destination_amount: Optional[float] = None
    coupon_discount_percentage: Optional[float] = None
    coupon_discount_commission: Optional[float] = None
    coupon_discount_total_to_send: Optional[float] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = None


class UserWithBankAccount(BaseModel):
    """Usuario con su cuenta bancaria. Cada usuario se relaciona directamente con su bank_account."""

    user: Any  # UserCreateCmd
    bank_account: BankAccountImportPayload


class ImportTransactionItem(BaseModel):
    """Item de importación: user_origin + bank_account_origin (emisor), user_destination + bank_account_destination (receptor), transaction.
    Se pueden crear usuarios y bank_accounts desde cero. Cada bank_account pertenece a su user.
    """

    user_origin: UserWithBankAccount  # Emisor: usuario + su cuenta origen
    user_destination: UserWithBankAccount  # Receptor: usuario + su cuenta destino
    transaction: TransactionImportPayload


class ImportRequestCmd(BaseModel):
    """Body JSON para importación. Cada item: emisor (user+cuenta), receptor (user+cuenta), transacción."""

    items: List[ImportTransactionItem] = Field(default_factory=list, description="Items a importar")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "user_origin": {
                            "user": {
                                "names": "Juan",
                                "lastnames": "Pérez",
                                "email": "juan@example.com",
                                "password": "secret123",
                            },
                            "bank_account": {
                                "bank_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "account_flow": "origin",
                                "account_holder_type": "naturalPerson",
                                "bank_country": "pe",
                            },
                        },
                        "user_destination": {
                            "user": {
                                "names": "María",
                                "lastnames": "García",
                                "email": "maria@example.com",
                                "password": "secret456",
                            },
                            "bank_account": {
                                "bank_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "account_flow": "destination",
                                "account_holder_type": "naturalPerson",
                                "bank_country": "br",
                            },
                        },
                        "transaction": {
                            "tax_rate_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "commission_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "origin_amount": 100.0,
                            "destination_amount": 95.0,
                        },
                    }
                ]
            }
        }
    )


class ImportResponseDTO(BaseModel):
    """Respuesta del endpoint de importación de datos."""

    created_transactions: int = 0
    created_users: int = 0
    created_bank_accounts: int = 0
    message: str = "Importación completada"

# app/modules/transactions/application/schemas/transaction_schema.py
from datetime import datetime
from typing import Any, List, Optional, Tuple
from uuid import UUID

from fastapi import File, Form, UploadFile
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field

from app.modules.transactions.domain.enums import AccountFlowType, BankCountry, SocialActor, TransactionStatus



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


class TransactionCreateCmd(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bank_account_origin": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "bank_account_destination": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "tax_rate_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "commission_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "verification",
                "origin_amount": 100.0,
                "destination_amount": 95.0,
                "code": "",
                "commission_result": 5.0,
                "total_to_send": 100.0,
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

    bank_account_origin: UUID
    bank_account_destination: UUID
    user_id: UUID
    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus = TransactionStatus.verification
    origin_amount: float
    destination_amount: float
    code: str = Field(
        default="",
        description="Generado en servidor (p. ej. PxB-0000000001); el valor enviado se ignora",
    )
    commission_result: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("commission_result", "resultado_comision"),
    )
    total_to_send: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("total_to_send", "total_a_enviar"),
    )
    coupon_id: Optional[UUID] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = Field(
        default=None,
        description="Ruta relativa de imagen asociada al checklist (multipart: campo checked_image)",
    )
    checked: bool = False

    @classmethod
    def from_form(
        cls,
        bank_account_origin: str = Form(..., description="UUID cuenta origen"),
        bank_account_destination: str = Form(..., description="UUID cuenta destino"),
        user_id: str = Form(..., description="UUID de usuario"),
        tax_rate_id: str = Form(..., description="UUID de tasa"),
        commission_id: str = Form(..., description="UUID de comisión"),
        status: str = Form(
            "verification",
            description="Estado: verification, verified, completed, failed, pending, …",
        ),
        origin_amount: str = Form(..., description="Monto origen"),
        destination_amount: str = Form(..., description="Monto destino"),
        code: str = Form("", description="Opcional; el servidor genera el código (PxB-…)"),
        commission_result: Optional[str] = Form(None),
        total_to_send: Optional[str] = Form(None),
        coupon_id: Optional[str] = Form(None),
        send_date: Optional[str] = Form(None),
        payment_date: Optional[str] = Form(None),
        send_voucher: Optional[UploadFile] = File(None),
        payment_voucher: Optional[UploadFile] = File(None),
        checked_image: Optional[UploadFile] = File(None),
        checked: bool = Form(False),
    ) -> Tuple[
        "TransactionCreateCmd",
        Optional[UploadFile],
        Optional[UploadFile],
        Optional[UploadFile],
    ]:
        cmd = cls(
            bank_account_origin=UUID(bank_account_origin),
            bank_account_destination=UUID(bank_account_destination),
            user_id=UUID(user_id),
            tax_rate_id=UUID(tax_rate_id),
            commission_id=UUID(commission_id),
            status=TransactionStatus(status) if status else TransactionStatus.verification,
            origin_amount=float(origin_amount),
            destination_amount=float(destination_amount),
            code=code,
            commission_result=_parse_optional_float(commission_result),
            total_to_send=_parse_optional_float(total_to_send),
            coupon_id=_parse_optional_uuid(coupon_id),
            send_date=_parse_optional_datetime(send_date),
            payment_date=_parse_optional_datetime(payment_date),
            send_voucher=None,  # se llenará en la ruta tras guardar
            payment_voucher=None,
            checked_image=None,
            checked=checked,
        )
        return cmd, send_voucher, payment_voucher, checked_image

    @classmethod
    def from_form_data(
        cls, form: Any
    ) -> Tuple[
        "TransactionCreateCmd",
        Optional[UploadFile],
        Optional[UploadFile],
        Optional[UploadFile],
    ]:
        """Construye cmd desde form-data. Retorna (cmd, send_voucher, payment_voucher, checked_image)."""
        _get = lambda k, d="": form.get(k, d) if hasattr(form, "get") else d
        cmd = cls(
            bank_account_origin=UUID(_get("bank_account_origin", "")),
            bank_account_destination=UUID(_get("bank_account_destination", "")),
            user_id=UUID(_get("user_id", "")),
            tax_rate_id=UUID(_get("tax_rate_id", "")),
            commission_id=UUID(_get("commission_id", "")),
            status=TransactionStatus(_get("status", "verification") or "verification"),
            origin_amount=float(_get("origin_amount", 0)),
            destination_amount=float(_get("destination_amount", 0)),
            code=_get("code", ""),
            commission_result=_parse_optional_float(
                _get("commission_result") or _get("resultado_comision")
            ),
            total_to_send=_parse_optional_float(
                _get("total_to_send") or _get("total_a_enviar")
            ),
            coupon_id=_parse_optional_uuid(_get("coupon_id")),
            send_date=_parse_optional_datetime(_get("send_date")),
            payment_date=_parse_optional_datetime(_get("payment_date")),
            send_voucher=None,
            payment_voucher=None,
            checked_image=None,
            checked=_get("checked", "false").lower() in ("true", "1", "yes"),
        )
        send_f = form.get("send_voucher") if "send_voucher" in form else None
        pay_f = form.get("payment_voucher") if "payment_voucher" in form else None
        checked_img_f = form.get("checked_image") if "checked_image" in form else None
        if send_f and not getattr(send_f, "filename", True):
            send_f = None
        if pay_f and not getattr(pay_f, "filename", True):
            pay_f = None
        if checked_img_f and not getattr(checked_img_f, "filename", True):
            checked_img_f = None
        return cmd, send_f, pay_f, checked_img_f


class TransactionUpdateCmd(BaseModel):
    id: UUID
    bank_account_origin: Optional[UUID] = None
    bank_account_destination: Optional[UUID] = None
    user_id: Optional[UUID] = None
    tax_rate_id: Optional[UUID] = None
    commission_id: Optional[UUID] = None
    status: Optional[TransactionStatus] = None
    origin_amount: Optional[float] = None
    destination_amount: Optional[float] = None
    code: Optional[str] = None
    commission_result: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("commission_result", "resultado_comision"),
    )
    total_to_send: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("total_to_send", "total_a_enviar"),
    )
    coupon_id: Optional[UUID] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = None
    checked: Optional[bool] = None

    @classmethod
    def from_form(
        cls,
        id: str = Form(..., description="UUID de la transacción"),
        bank_account_origin: Optional[str] = Form(None),
        bank_account_destination: Optional[str] = Form(None),
        user_id: Optional[str] = Form(None),
        tax_rate_id: Optional[str] = Form(None),
        commission_id: Optional[str] = Form(None),
        status: Optional[str] = Form(None),
        origin_amount: Optional[str] = Form(None),
        destination_amount: Optional[str] = Form(None),
        code: Optional[str] = Form(None),
        commission_result: Optional[str] = Form(None),
        total_to_send: Optional[str] = Form(None),
        coupon_id: Optional[str] = Form(None),
        send_date: Optional[str] = Form(None),
        payment_date: Optional[str] = Form(None),
        send_voucher: Optional[UploadFile] = File(None),
        payment_voucher: Optional[UploadFile] = File(None),
        checked_image: Optional[UploadFile] = File(None),
        checked: Optional[str] = Form(None),
    ) -> Tuple[
        "TransactionUpdateCmd",
        Optional[UploadFile],
        Optional[UploadFile],
        Optional[UploadFile],
    ]:
        cmd = cls(
            id=UUID(id),
            bank_account_origin=_parse_optional_uuid(bank_account_origin),
            bank_account_destination=_parse_optional_uuid(bank_account_destination),
            user_id=_parse_optional_uuid(user_id),
            tax_rate_id=_parse_optional_uuid(tax_rate_id),
            commission_id=_parse_optional_uuid(commission_id),
            status=TransactionStatus(status) if status else None,
            origin_amount=_parse_optional_float(origin_amount),
            destination_amount=_parse_optional_float(destination_amount),
            code=code,
            commission_result=_parse_optional_float(commission_result),
            total_to_send=_parse_optional_float(total_to_send),
            coupon_id=_parse_optional_uuid(coupon_id),
            send_date=_parse_optional_datetime(send_date),
            payment_date=_parse_optional_datetime(payment_date),
            send_voucher=None,
            payment_voucher=None,
            checked_image=None,
            checked=_parse_checked(checked),
        )
        return cmd, send_voucher, payment_voucher, checked_image

    @classmethod
    def from_form_data(
        cls, form: Any
    ) -> Tuple[
        "TransactionUpdateCmd",
        Optional[UploadFile],
        Optional[UploadFile],
        Optional[UploadFile],
    ]:
        """Construye cmd desde form-data. Retorna (cmd, send_voucher, payment_voucher, checked_image)."""
        _get = lambda k, d=None: form.get(k, d) if hasattr(form, "get") else d
        cmd = cls(
            id=UUID(_get("id", "")),
            bank_account_origin=_parse_optional_uuid(_get("bank_account_origin")),
            bank_account_destination=_parse_optional_uuid(_get("bank_account_destination")),
            user_id=_parse_optional_uuid(_get("user_id")),
            tax_rate_id=_parse_optional_uuid(_get("tax_rate_id")),
            commission_id=_parse_optional_uuid(_get("commission_id")),
            status=TransactionStatus(_get("status")) if _get("status") else None,
            origin_amount=_parse_optional_float(_get("origin_amount")),
            destination_amount=_parse_optional_float(_get("destination_amount")),
            code=_get("code"),
            commission_result=_parse_optional_float(
                _get("commission_result") or _get("resultado_comision")
            ),
            total_to_send=_parse_optional_float(
                _get("total_to_send") or _get("total_a_enviar")
            ),
            coupon_id=_parse_optional_uuid(_get("coupon_id")),
            send_date=_parse_optional_datetime(_get("send_date")),
            payment_date=_parse_optional_datetime(_get("payment_date")),
            send_voucher=None,
            payment_voucher=None,
            checked_image=None,
            checked=_parse_checked(_get("checked")),
        )
        send_f = form.get("send_voucher") if "send_voucher" in form else None
        pay_f = form.get("payment_voucher") if "payment_voucher" in form else None
        checked_img_f = form.get("checked_image") if "checked_image" in form else None
        if send_f and not getattr(send_f, "filename", True):
            send_f = None
        if pay_f and not getattr(pay_f, "filename", True):
            pay_f = None
        if checked_img_f and not getattr(checked_img_f, "filename", True):
            checked_img_f = None
        return cmd, send_f, pay_f, checked_img_f


class TransactionUserRef(BaseModel):
    """Referencia mínima al usuario de la transacción (mismo id que `user_id`)."""

    id: UUID


class TransactionReadDTO(BaseModel):
    id: UUID
    bank_account_origin_id: UUID
    bank_account_destination_id: UUID
    user_id: UUID
    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus
    origin_amount: float
    destination_amount: float
    code: str
    commission_result: Optional[float] = None
    total_to_send: Optional[float] = None
    coupon_id: Optional[UUID] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None
    checked_image: Optional[str] = None
    checked: bool = False
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def user(self) -> TransactionUserRef:
        return TransactionUserRef(id=self.user_id)


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

    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus = TransactionStatus.verification
    origin_amount: float
    destination_amount: float
    commission_result: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("commission_result", "resultado_comision"),
    )
    total_to_send: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("total_to_send", "total_a_enviar"),
    )
    coupon_id: Optional[UUID] = None
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

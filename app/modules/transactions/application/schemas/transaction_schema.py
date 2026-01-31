# app/modules/transactions/application/schemas/transaction_schema.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.transactions.domain.enums import TransactionStatus


class TransactionCreateCmd(BaseModel):
    bank_account_id: UUID
    user_id: UUID
    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus = TransactionStatus.pending
    origin_amount: float
    destination_amount: float
    code: str
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None


class TransactionUpdateCmd(BaseModel):
    id: UUID
    bank_account_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    tax_rate_id: Optional[UUID] = None
    commission_id: Optional[UUID] = None
    status: Optional[TransactionStatus] = None
    origin_amount: Optional[float] = None
    destination_amount: Optional[float] = None
    code: Optional[str] = None
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None


class TransactionReadDTO(BaseModel):
    id: UUID
    bank_account_id: UUID
    user_id: UUID
    tax_rate_id: UUID
    commission_id: UUID
    status: TransactionStatus
    origin_amount: float
    destination_amount: float
    code: str
    send_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    send_voucher: Optional[str] = None
    payment_voucher: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

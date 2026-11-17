from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.routing import LegacyAliasRouter
from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit
from app.modules.omie.application.service import OmieBillingService
from app.modules.omie.application.email_delivery import OmieEmailService
from app.shared.contact_emails import validate_emails
from app.modules.omie.application.list_invoices import list_invoices, records_for_transactions
from app.modules.omie.infrastructure.client import OmieError, OmieRateLimited

router = LegacyAliasRouter(prefix="/omie", tags=["omie"])


class IssueRequest(BaseModel):
    expected_total: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    expected_document: str = Field(pattern=r"^\d{11}(\d{3})?$")


class OmieEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipients: list[str] | None = None

    @field_validator("recipients", mode="before")
    @classmethod
    def check_recipients(cls, value):
        if value is None:
            return None
        result = validate_emails(value)
        if not result:
            raise ValueError("Selecciona al menos un correo")
        return result


class RegisterCustomerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    legal_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    street: str = Field(min_length=1, max_length=60)
    number: str = Field(min_length=1, max_length=60)
    district: str = Field(min_length=1, max_length=60)
    city: str = Field(min_length=1, max_length=40)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}-?\d{3}$")
    phone_area_code: str | None = Field(default=None, pattern=r"^\d{2,5}$")
    phone_number: str | None = Field(default=None, min_length=6, max_length=15)

    @model_validator(mode="after")
    def phone_fields_together(self):
        if bool(self.phone_area_code) != bool(self.phone_number):
            raise ValueError("Indica el DDD y el teléfono juntos")
        return self


def service(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if not settings.OMIE_ENABLED or not settings.OMIE_APP_KEY or not settings.OMIE_APP_SECRET:
        raise HTTPException(503, "La integración de Omie no está habilitada")
    return OmieBillingService(db, settings)


async def result(operation):
    try:
        data = await operation
        if isinstance(data, dict):
            data.pop("_order", None)
        return data
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except OmieRateLimited as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": str(exc.retry_after)}) from None
    except OmieError as exc:
        raise HTTPException(502, str(exc)) from None


@router.get("/transactions/{transaction_id}/preview", dependencies=[Depends(require_permission("billing.view"))])
async def preview(transaction_id: UUID, svc=Depends(service)):
    return await result(svc.preview(transaction_id))


OmieStatus = Literal["creating", "validating", "billing", "pending", "issued", "cancelled", "review_required"]


@router.get("/invoices", dependencies=[Depends(require_permission("billing.view"))])
async def invoices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status: OmieStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "La fecha inicial debe ser anterior o igual a la final")
    return await list_invoices(db, page=page, page_size=page_size, status=status,
                               date_from=date_from, date_to=date_to)


@router.post("/transactions/{transaction_id}/customer", dependencies=[Depends(require_permission("billing.issue")), Depends(stage_mutation_audit("omie.customers.register", "transaction"))])
async def register_customer(transaction_id: UUID, body: RegisterCustomerRequest, svc=Depends(service)):
    return await result(svc.register_customer(transaction_id, body))


@router.post("/transactions/{transaction_id}/issue", dependencies=[Depends(require_permission("billing.issue")), Depends(stage_mutation_audit("omie.invoices.issue", "transaction"))])
async def issue(transaction_id: UUID, body: IssueRequest, svc=Depends(service)):
    return await result(svc.issue(transaction_id, body.expected_total, body.expected_document))


@router.post("/transactions/{transaction_id}/refresh", dependencies=[Depends(require_permission("billing.view")), Depends(stage_mutation_audit("omie.invoices.refresh", "transaction"))])
async def refresh(transaction_id: UUID, svc=Depends(service)):
    return await result(svc.refresh(transaction_id))


@router.get("/transactions/{transaction_id}/pdf", dependencies=[Depends(require_permission("billing.view"))])
async def pdf(transaction_id: UUID, svc=Depends(service)):
    return await result(svc.pdf(transaction_id))


@router.get("/transactions/{transaction_id}/email", dependencies=[Depends(require_permission("billing.view"))])
async def email_details(transaction_id: UUID, svc=Depends(service)):
    return await result(OmieEmailService(svc.db, svc.settings, billing=svc).details(transaction_id))


@router.post("/transactions/{transaction_id}/email", status_code=202, dependencies=[
    Depends(require_permission("billing.issue")), Depends(stage_mutation_audit("omie.invoices.email", "transaction")),
])
async def request_email(transaction_id: UUID, body: OmieEmailRequest, svc=Depends(service)):
    return await result(OmieEmailService(svc.db, svc.settings, billing=svc).request(transaction_id, body.recipients))


@router.get("/transaction-records", dependencies=[Depends(require_permission("billing.view"))])
async def transaction_records(
    transaction_ids: list[UUID] = Query(..., min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    return await records_for_transactions(db, transaction_ids)

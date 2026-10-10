# app/modules/billing/adapters/dependencies.py
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings
from app.db.base import get_db
from app.modules.billing.application.use_cases import (
    AlignSeriesUseCase,
    BillingStatusUseCase,
    GetInvoicePdfUseCase,
    GetInvoiceUseCase,
    IssueInvoiceUseCase,
    LatestInvoicesForTransactionsUseCase,
    ListInvoicesUseCase,
    PollInvoiceUseCase,
    PreviewInvoiceUseCase,
    RetryInvoiceUseCase,
    VoidInvoiceUseCase,
)
from app.modules.billing.infrastructure.apisunat_client import ApisunatClientsFromSettings
from app.modules.billing.infrastructure.repository import SQLAlchemyBillingRepository
from app.modules.billing.interfaces.apisunat_client import ApisunatClientProvider
from app.modules.billing.interfaces.repository import BillingRepositoryInterface


def build_apisunat_client(settings: Settings) -> ApisunatClientProvider:
    """Clientes de APISUNAT por empresa emisora (cada RUC con su token)."""
    return ApisunatClientsFromSettings(settings)


def get_billing_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> BillingRepositoryInterface:
    return SQLAlchemyBillingRepository(db)


def get_apisunat_client() -> ApisunatClientProvider:
    return build_apisunat_client(get_settings())


def get_file_service():
    from app.shared.services.file_service import file_service

    return file_service


def require_billing_enabled() -> None:
    if not get_settings().BILLING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La facturación electrónica está deshabilitada (BILLING_ENABLED=False)",
        )


RepoDep = Annotated[BillingRepositoryInterface, Depends(get_billing_repository)]
ClientDep = Annotated[ApisunatClientProvider, Depends(get_apisunat_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
FileServiceDep = Annotated[object, Depends(get_file_service)]


def issue_invoice_uc(repo: RepoDep, client: ClientDep, settings: SettingsDep) -> IssueInvoiceUseCase:
    return IssueInvoiceUseCase(repo, client, settings)


def retry_invoice_uc(repo: RepoDep, client: ClientDep, settings: SettingsDep) -> RetryInvoiceUseCase:
    return RetryInvoiceUseCase(repo, client, settings)


def void_invoice_uc(repo: RepoDep, client: ClientDep, settings: SettingsDep) -> VoidInvoiceUseCase:
    return VoidInvoiceUseCase(repo, client, settings)


def poll_invoice_uc(
    repo: RepoDep, client: ClientDep, settings: SettingsDep, file_service: FileServiceDep
) -> PollInvoiceUseCase:
    return PollInvoiceUseCase(repo, client, settings, file_service)


def get_invoice_uc(repo: RepoDep) -> GetInvoiceUseCase:
    return GetInvoiceUseCase(repo)


def list_invoices_uc(repo: RepoDep) -> ListInvoicesUseCase:
    return ListInvoicesUseCase(repo)


def get_invoice_pdf_uc(
    repo: RepoDep, client: ClientDep, settings: SettingsDep, file_service: FileServiceDep
) -> GetInvoicePdfUseCase:
    return GetInvoicePdfUseCase(repo, client, settings, file_service)


def billing_status_uc(repo: RepoDep, settings: SettingsDep) -> BillingStatusUseCase:
    return BillingStatusUseCase(repo, settings)


def preview_invoice_uc(repo: RepoDep, settings: SettingsDep) -> PreviewInvoiceUseCase:
    return PreviewInvoiceUseCase(repo, settings)


def latest_invoices_uc(repo: RepoDep) -> LatestInvoicesForTransactionsUseCase:
    return LatestInvoicesForTransactionsUseCase(repo)


def align_series_uc(repo: RepoDep, client: ClientDep, settings: SettingsDep) -> AlignSeriesUseCase:
    return AlignSeriesUseCase(repo, client, settings)


IssueInvoiceUseCaseDep = Annotated[IssueInvoiceUseCase, Depends(issue_invoice_uc)]
RetryInvoiceUseCaseDep = Annotated[RetryInvoiceUseCase, Depends(retry_invoice_uc)]
VoidInvoiceUseCaseDep = Annotated[VoidInvoiceUseCase, Depends(void_invoice_uc)]
PollInvoiceUseCaseDep = Annotated[PollInvoiceUseCase, Depends(poll_invoice_uc)]
GetInvoiceUseCaseDep = Annotated[GetInvoiceUseCase, Depends(get_invoice_uc)]
ListInvoicesUseCaseDep = Annotated[ListInvoicesUseCase, Depends(list_invoices_uc)]
GetInvoicePdfUseCaseDep = Annotated[GetInvoicePdfUseCase, Depends(get_invoice_pdf_uc)]
BillingStatusUseCaseDep = Annotated[BillingStatusUseCase, Depends(billing_status_uc)]
AlignSeriesUseCaseDep = Annotated[AlignSeriesUseCase, Depends(align_series_uc)]
PreviewInvoiceUseCaseDep = Annotated[PreviewInvoiceUseCase, Depends(preview_invoice_uc)]
LatestInvoicesUseCaseDep = Annotated[LatestInvoicesForTransactionsUseCase, Depends(latest_invoices_uc)]

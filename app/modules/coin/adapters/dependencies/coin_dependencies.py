# app/modules/coin/adapters/dependencies/coin_dependencies.py
"""Inyección de dependencias del módulo coin para las rutas (adapters)."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.coin.interfaces.tax_rate_trial_repository import TaxRateTrialRepositoryInterface
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.coin.infrastructure.repository import (
    SQLAlchemyTaxRateRepository,
    SQLAlchemyTaxRateTrialRepository,
    SQLAlchemyCommissionRepository,
)
from app.modules.coin.application.use_cases import (
    GetTaxRateByIdUseCase,
    ListTaxRatesUseCase,
    CreateTaxRateUseCase,
    UpdateTaxRateUseCase,
    DeleteTaxRateUseCase,
    GetTaxRateTrialByIdUseCase,
    ListTaxRateTrialsUseCase,
    CreateTaxRateTrialUseCase,
    UpdateTaxRateTrialUseCase,
    DeleteTaxRateTrialUseCase,
    GetCommissionByIdUseCase,
    ListCommissionsUseCase,
    CreateCommissionUseCase,
    UpdateCommissionUseCase,
    DeleteCommissionUseCase,
)


# --- Repositorios ---

def get_tax_rate_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxRateRepositoryInterface:
    return SQLAlchemyTaxRateRepository(db)


def get_commission_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommissionRepositoryInterface:
    return SQLAlchemyCommissionRepository(db)


# --- TaxRate: factories de casos de uso ---

def get_tax_rate_by_id_uc(
    repo: Annotated[TaxRateRepositoryInterface, Depends(get_tax_rate_repository)],
) -> GetTaxRateByIdUseCase:
    return GetTaxRateByIdUseCase(repo)


def list_tax_rates_uc(
    repo: Annotated[TaxRateRepositoryInterface, Depends(get_tax_rate_repository)],
) -> ListTaxRatesUseCase:
    return ListTaxRatesUseCase(repo)


def create_tax_rate_uc(
    repo: Annotated[TaxRateRepositoryInterface, Depends(get_tax_rate_repository)],
) -> CreateTaxRateUseCase:
    return CreateTaxRateUseCase(repo)


def update_tax_rate_uc(
    repo: Annotated[TaxRateRepositoryInterface, Depends(get_tax_rate_repository)],
) -> UpdateTaxRateUseCase:
    return UpdateTaxRateUseCase(repo)


def delete_tax_rate_uc(
    repo: Annotated[TaxRateRepositoryInterface, Depends(get_tax_rate_repository)],
) -> DeleteTaxRateUseCase:
    return DeleteTaxRateUseCase(repo)


# --- TaxRateTrial (tasa prueba): repositorio y factories ---

def get_tax_rate_trial_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxRateTrialRepositoryInterface:
    return SQLAlchemyTaxRateTrialRepository(db)


def get_tax_rate_trial_by_id_uc(
    repo: Annotated[TaxRateTrialRepositoryInterface, Depends(get_tax_rate_trial_repository)],
) -> GetTaxRateTrialByIdUseCase:
    return GetTaxRateTrialByIdUseCase(repo)


def list_tax_rate_trials_uc(
    repo: Annotated[TaxRateTrialRepositoryInterface, Depends(get_tax_rate_trial_repository)],
) -> ListTaxRateTrialsUseCase:
    return ListTaxRateTrialsUseCase(repo)


def create_tax_rate_trial_uc(
    repo: Annotated[TaxRateTrialRepositoryInterface, Depends(get_tax_rate_trial_repository)],
) -> CreateTaxRateTrialUseCase:
    return CreateTaxRateTrialUseCase(repo)


def update_tax_rate_trial_uc(
    repo: Annotated[TaxRateTrialRepositoryInterface, Depends(get_tax_rate_trial_repository)],
) -> UpdateTaxRateTrialUseCase:
    return UpdateTaxRateTrialUseCase(repo)


def delete_tax_rate_trial_uc(
    repo: Annotated[TaxRateTrialRepositoryInterface, Depends(get_tax_rate_trial_repository)],
) -> DeleteTaxRateTrialUseCase:
    return DeleteTaxRateTrialUseCase(repo)


# --- Commission: factories de casos de uso ---

def get_commission_by_id_uc(
    repo: Annotated[CommissionRepositoryInterface, Depends(get_commission_repository)],
) -> GetCommissionByIdUseCase:
    return GetCommissionByIdUseCase(repo)


def list_commissions_uc(
    repo: Annotated[CommissionRepositoryInterface, Depends(get_commission_repository)],
) -> ListCommissionsUseCase:
    return ListCommissionsUseCase(repo)


def create_commission_uc(
    repo: Annotated[CommissionRepositoryInterface, Depends(get_commission_repository)],
) -> CreateCommissionUseCase:
    return CreateCommissionUseCase(repo)


def update_commission_uc(
    repo: Annotated[CommissionRepositoryInterface, Depends(get_commission_repository)],
) -> UpdateCommissionUseCase:
    return UpdateCommissionUseCase(repo)


def delete_commission_uc(
    repo: Annotated[CommissionRepositoryInterface, Depends(get_commission_repository)],
) -> DeleteCommissionUseCase:
    return DeleteCommissionUseCase(repo)


# --- Tipos anotados para inyección en rutas (sin Depends explícito en el handler) ---

GetTaxRateByIdUseCaseDep = Annotated[GetTaxRateByIdUseCase, Depends(get_tax_rate_by_id_uc)]
ListTaxRatesUseCaseDep = Annotated[ListTaxRatesUseCase, Depends(list_tax_rates_uc)]
CreateTaxRateUseCaseDep = Annotated[CreateTaxRateUseCase, Depends(create_tax_rate_uc)]
UpdateTaxRateUseCaseDep = Annotated[UpdateTaxRateUseCase, Depends(update_tax_rate_uc)]
DeleteTaxRateUseCaseDep = Annotated[DeleteTaxRateUseCase, Depends(delete_tax_rate_uc)]

GetTaxRateTrialByIdUseCaseDep = Annotated[GetTaxRateTrialByIdUseCase, Depends(get_tax_rate_trial_by_id_uc)]
ListTaxRateTrialsUseCaseDep = Annotated[ListTaxRateTrialsUseCase, Depends(list_tax_rate_trials_uc)]
CreateTaxRateTrialUseCaseDep = Annotated[CreateTaxRateTrialUseCase, Depends(create_tax_rate_trial_uc)]
UpdateTaxRateTrialUseCaseDep = Annotated[UpdateTaxRateTrialUseCase, Depends(update_tax_rate_trial_uc)]
DeleteTaxRateTrialUseCaseDep = Annotated[DeleteTaxRateTrialUseCase, Depends(delete_tax_rate_trial_uc)]

GetCommissionByIdUseCaseDep = Annotated[GetCommissionByIdUseCase, Depends(get_commission_by_id_uc)]
ListCommissionsUseCaseDep = Annotated[ListCommissionsUseCase, Depends(list_commissions_uc)]
CreateCommissionUseCaseDep = Annotated[CreateCommissionUseCase, Depends(create_commission_uc)]
UpdateCommissionUseCaseDep = Annotated[UpdateCommissionUseCase, Depends(update_commission_uc)]
DeleteCommissionUseCaseDep = Annotated[DeleteCommissionUseCase, Depends(delete_commission_uc)]

# app/modules/coin/adapters/dependencies/coin_dependencies.py
"""Inyección de dependencias del módulo coin para las rutas (adapters)."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.coin.interfaces.tax_rate_trial_repository import TaxRateTrialRepositoryInterface
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.coin.interfaces.commission_accounting_repository import (
    CommissionAccountingRepositoryInterface,
)
from app.modules.coin.interfaces.commission_accounting_settings_repository import (
    CommissionAccountingSettingsRepositoryInterface,
)
from app.modules.coin.interfaces.commission_trial_repository import CommissionTrialRepositoryInterface
from app.modules.coin.infrastructure.repository import (
    SQLAlchemyTaxRateRepository,
    SQLAlchemyTaxRateTrialRepository,
    SQLAlchemyCommissionRepository,
    SQLAlchemyCommissionAccountingRepository,
    SQLAlchemyCommissionAccountingSettingsRepository,
    SQLAlchemyCommissionTrialRepository,
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
    GetCommissionAccountingByIdUseCase,
    ListCommissionAccountingsUseCase,
    CreateCommissionAccountingUseCase,
    UpdateCommissionAccountingUseCase,
    DeleteCommissionAccountingUseCase,
    GetCommissionAccountingSettingsUseCase,
    UpsertCommissionAccountingSettingsUseCase,
    GetCommissionTrialByIdUseCase,
    ListCommissionTrialsUseCase,
    CreateCommissionTrialUseCase,
    UpdateCommissionTrialUseCase,
    DeleteCommissionTrialUseCase,
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


def get_commission_accounting_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommissionAccountingRepositoryInterface:
    return SQLAlchemyCommissionAccountingRepository(db)


def get_commission_accounting_settings_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommissionAccountingSettingsRepositoryInterface:
    return SQLAlchemyCommissionAccountingSettingsRepository(db)


def get_commission_trial_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommissionTrialRepositoryInterface:
    return SQLAlchemyCommissionTrialRepository(db)


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


# --- CommissionTrial (comisión prueba): repositorio y factories ---

def get_commission_trial_by_id_uc(
    repo: Annotated[CommissionTrialRepositoryInterface, Depends(get_commission_trial_repository)],
) -> GetCommissionTrialByIdUseCase:
    return GetCommissionTrialByIdUseCase(repo)


def list_commission_trials_uc(
    repo: Annotated[CommissionTrialRepositoryInterface, Depends(get_commission_trial_repository)],
) -> ListCommissionTrialsUseCase:
    return ListCommissionTrialsUseCase(repo)


def create_commission_trial_uc(
    repo: Annotated[CommissionTrialRepositoryInterface, Depends(get_commission_trial_repository)],
) -> CreateCommissionTrialUseCase:
    return CreateCommissionTrialUseCase(repo)


def update_commission_trial_uc(
    repo: Annotated[CommissionTrialRepositoryInterface, Depends(get_commission_trial_repository)],
) -> UpdateCommissionTrialUseCase:
    return UpdateCommissionTrialUseCase(repo)


def delete_commission_trial_uc(
    repo: Annotated[CommissionTrialRepositoryInterface, Depends(get_commission_trial_repository)],
) -> DeleteCommissionTrialUseCase:
    return DeleteCommissionTrialUseCase(repo)


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


# --- CommissionAccounting (comisión contable): factories de casos de uso ---

def get_commission_accounting_by_id_uc(
    repo: Annotated[CommissionAccountingRepositoryInterface, Depends(get_commission_accounting_repository)],
) -> GetCommissionAccountingByIdUseCase:
    return GetCommissionAccountingByIdUseCase(repo)


def list_commission_accountings_uc(
    repo: Annotated[CommissionAccountingRepositoryInterface, Depends(get_commission_accounting_repository)],
) -> ListCommissionAccountingsUseCase:
    return ListCommissionAccountingsUseCase(repo)


def create_commission_accounting_uc(
    repo: Annotated[CommissionAccountingRepositoryInterface, Depends(get_commission_accounting_repository)],
) -> CreateCommissionAccountingUseCase:
    return CreateCommissionAccountingUseCase(repo)


def update_commission_accounting_uc(
    repo: Annotated[CommissionAccountingRepositoryInterface, Depends(get_commission_accounting_repository)],
) -> UpdateCommissionAccountingUseCase:
    return UpdateCommissionAccountingUseCase(repo)


def delete_commission_accounting_uc(
    repo: Annotated[CommissionAccountingRepositoryInterface, Depends(get_commission_accounting_repository)],
) -> DeleteCommissionAccountingUseCase:
    return DeleteCommissionAccountingUseCase(repo)


def get_commission_accounting_settings_uc(
    repo: Annotated[
        CommissionAccountingSettingsRepositoryInterface,
        Depends(get_commission_accounting_settings_repository),
    ],
) -> GetCommissionAccountingSettingsUseCase:
    return GetCommissionAccountingSettingsUseCase(repo)


def upsert_commission_accounting_settings_uc(
    repo: Annotated[
        CommissionAccountingSettingsRepositoryInterface,
        Depends(get_commission_accounting_settings_repository),
    ],
) -> UpsertCommissionAccountingSettingsUseCase:
    return UpsertCommissionAccountingSettingsUseCase(repo)


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
GetCommissionTrialByIdUseCaseDep = Annotated[GetCommissionTrialByIdUseCase, Depends(get_commission_trial_by_id_uc)]
ListCommissionTrialsUseCaseDep = Annotated[ListCommissionTrialsUseCase, Depends(list_commission_trials_uc)]
CreateCommissionTrialUseCaseDep = Annotated[CreateCommissionTrialUseCase, Depends(create_commission_trial_uc)]
UpdateCommissionTrialUseCaseDep = Annotated[UpdateCommissionTrialUseCase, Depends(update_commission_trial_uc)]
DeleteCommissionTrialUseCaseDep = Annotated[DeleteCommissionTrialUseCase, Depends(delete_commission_trial_uc)]

GetCommissionByIdUseCaseDep = Annotated[GetCommissionByIdUseCase, Depends(get_commission_by_id_uc)]
ListCommissionsUseCaseDep = Annotated[ListCommissionsUseCase, Depends(list_commissions_uc)]
CreateCommissionUseCaseDep = Annotated[CreateCommissionUseCase, Depends(create_commission_uc)]
UpdateCommissionUseCaseDep = Annotated[UpdateCommissionUseCase, Depends(update_commission_uc)]
DeleteCommissionUseCaseDep = Annotated[DeleteCommissionUseCase, Depends(delete_commission_uc)]

GetCommissionAccountingByIdUseCaseDep = Annotated[
    GetCommissionAccountingByIdUseCase, Depends(get_commission_accounting_by_id_uc)
]
ListCommissionAccountingsUseCaseDep = Annotated[
    ListCommissionAccountingsUseCase, Depends(list_commission_accountings_uc)
]
CreateCommissionAccountingUseCaseDep = Annotated[
    CreateCommissionAccountingUseCase, Depends(create_commission_accounting_uc)
]
UpdateCommissionAccountingUseCaseDep = Annotated[
    UpdateCommissionAccountingUseCase, Depends(update_commission_accounting_uc)
]
DeleteCommissionAccountingUseCaseDep = Annotated[
    DeleteCommissionAccountingUseCase, Depends(delete_commission_accounting_uc)
]
GetCommissionAccountingSettingsUseCaseDep = Annotated[
    GetCommissionAccountingSettingsUseCase, Depends(get_commission_accounting_settings_uc)
]
UpsertCommissionAccountingSettingsUseCaseDep = Annotated[
    UpsertCommissionAccountingSettingsUseCase, Depends(upsert_commission_accounting_settings_uc)
]

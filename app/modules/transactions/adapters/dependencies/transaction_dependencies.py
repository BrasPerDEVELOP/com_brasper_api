# app/modules/transactions/adapters/dependencies/transaction_dependencies.py
"""Inyección de dependencias del módulo transactions para las rutas."""
from typing import Annotated, TYPE_CHECKING

from fastapi import Depends

if TYPE_CHECKING:
    from app.modules.users.application.use_cases import CreateUserUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.coin.adapters.dependencies.coin_dependencies import get_commission_repository, get_tax_rate_repository
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.modules.transactions.interfaces.bank_repository import BankRepositoryInterface
from app.modules.transactions.interfaces.bank_account_repository import BankAccountRepositoryInterface
from app.modules.transactions.interfaces.coupon_repository import CouponRepositoryInterface
from app.modules.transactions.infrastructure.repository import SQLAlchemyTransactionRepository
from app.modules.transactions.infrastructure.bank_repository import SQLAlchemyBankRepository
from app.modules.transactions.infrastructure.bank_account_repository import SQLAlchemyBankAccountRepository
from app.modules.transactions.infrastructure.coupon_repository import SQLAlchemyCouponRepository
from app.core.containers.users import create_user_uc, get_user_repository
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.modules.transactions.application.use_cases import (
    GetTransactionByIdUseCase,
    ListTransactionsUseCase,
    CreateTransactionUseCase,
    UpdateTransactionUseCase,
    DeleteTransactionUseCase,
    ImportTransactionsUseCase,
    GetBankByIdUseCase,
    ListBanksUseCase,
    ListBankNamesUseCase,
    ListBanksByCountryCurrencyUseCase,
    CreateBankUseCase,
    UpdateBankUseCase,
    DeleteBankUseCase,
    GetBankAccountByIdUseCase,
    ListBankAccountsUseCase,
    CreateBankAccountUseCase,
    UpdateBankAccountUseCase,
    DeleteBankAccountUseCase,
    GetCouponByIdUseCase,
    ListCouponsUseCase,
    CreateCouponUseCase,
    UpdateCouponUseCase,
    DeleteCouponUseCase,
)


def get_transaction_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TransactionRepositoryInterface:
    return SQLAlchemyTransactionRepository(db)


def get_bank_account_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BankAccountRepositoryInterface:
    return SQLAlchemyBankAccountRepository(db)


def get_transaction_by_id_uc(
    repo: Annotated[TransactionRepositoryInterface, Depends(get_transaction_repository)],
) -> GetTransactionByIdUseCase:
    return GetTransactionByIdUseCase(repo)


def list_transactions_uc(
    repo: Annotated[TransactionRepositoryInterface, Depends(get_transaction_repository)],
) -> ListTransactionsUseCase:
    return ListTransactionsUseCase(repo)


def create_transaction_uc(
    repo: Annotated[TransactionRepositoryInterface, Depends(get_transaction_repository)],
    tax_rate_repo: Annotated[
        TaxRateRepositoryInterface, Depends(get_tax_rate_repository)
    ],
    user_repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
    bank_account_repo: Annotated[
        BankAccountRepositoryInterface, Depends(get_bank_account_repository)
    ],
    commission_repo: Annotated[CommissionRepositoryInterface, Depends(get_commission_repository)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateTransactionUseCase:
    return CreateTransactionUseCase(repo, tax_rate_repo, user_repo, bank_account_repo, commission_repo, db)


def update_transaction_uc(
    repo: Annotated[TransactionRepositoryInterface, Depends(get_transaction_repository)],
    bank_account_repo: Annotated[
        BankAccountRepositoryInterface, Depends(get_bank_account_repository)
    ],
) -> UpdateTransactionUseCase:
    return UpdateTransactionUseCase(repo, bank_account_repo)


def delete_transaction_uc(
    repo: Annotated[TransactionRepositoryInterface, Depends(get_transaction_repository)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeleteTransactionUseCase:
    return DeleteTransactionUseCase(repo, db)


GetTransactionByIdUseCaseDep = Annotated[GetTransactionByIdUseCase, Depends(get_transaction_by_id_uc)]
ListTransactionsUseCaseDep = Annotated[ListTransactionsUseCase, Depends(list_transactions_uc)]
CreateTransactionUseCaseDep = Annotated[CreateTransactionUseCase, Depends(create_transaction_uc)]
UpdateTransactionUseCaseDep = Annotated[UpdateTransactionUseCase, Depends(update_transaction_uc)]
DeleteTransactionUseCaseDep = Annotated[DeleteTransactionUseCase, Depends(delete_transaction_uc)]


# Bank
def get_bank_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BankRepositoryInterface:
    return SQLAlchemyBankRepository(db)


def get_bank_by_id_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> GetBankByIdUseCase:
    return GetBankByIdUseCase(repo)


def list_banks_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> ListBanksUseCase:
    return ListBanksUseCase(repo)


def list_bank_names_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> ListBankNamesUseCase:
    return ListBankNamesUseCase(repo)


def list_banks_by_country_currency_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> ListBanksByCountryCurrencyUseCase:
    return ListBanksByCountryCurrencyUseCase(repo)


def create_bank_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> CreateBankUseCase:
    return CreateBankUseCase(repo)


def update_bank_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> UpdateBankUseCase:
    return UpdateBankUseCase(repo)


def delete_bank_uc(
    repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> DeleteBankUseCase:
    return DeleteBankUseCase(repo)


GetBankByIdUseCaseDep = Annotated[GetBankByIdUseCase, Depends(get_bank_by_id_uc)]
ListBanksUseCaseDep = Annotated[ListBanksUseCase, Depends(list_banks_uc)]
ListBankNamesUseCaseDep = Annotated[ListBankNamesUseCase, Depends(list_bank_names_uc)]
ListBanksByCountryCurrencyUseCaseDep = Annotated[ListBanksByCountryCurrencyUseCase, Depends(list_banks_by_country_currency_uc)]
CreateBankUseCaseDep = Annotated[CreateBankUseCase, Depends(create_bank_uc)]
UpdateBankUseCaseDep = Annotated[UpdateBankUseCase, Depends(update_bank_uc)]
DeleteBankUseCaseDep = Annotated[DeleteBankUseCase, Depends(delete_bank_uc)]


# BankAccount
def get_bank_account_by_id_uc(
    repo: Annotated[BankAccountRepositoryInterface, Depends(get_bank_account_repository)],
) -> GetBankAccountByIdUseCase:
    return GetBankAccountByIdUseCase(repo)


def list_bank_accounts_uc(
    repo: Annotated[BankAccountRepositoryInterface, Depends(get_bank_account_repository)],
) -> ListBankAccountsUseCase:
    return ListBankAccountsUseCase(repo)


def create_bank_account_uc(
    repo: Annotated[BankAccountRepositoryInterface, Depends(get_bank_account_repository)],
    bank_repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> CreateBankAccountUseCase:
    return CreateBankAccountUseCase(repo, bank_repo)


def update_bank_account_uc(
    repo: Annotated[BankAccountRepositoryInterface, Depends(get_bank_account_repository)],
    bank_repo: Annotated[BankRepositoryInterface, Depends(get_bank_repository)],
) -> UpdateBankAccountUseCase:
    return UpdateBankAccountUseCase(repo, bank_repo)


def delete_bank_account_uc(
    repo: Annotated[BankAccountRepositoryInterface, Depends(get_bank_account_repository)],
) -> DeleteBankAccountUseCase:
    return DeleteBankAccountUseCase(repo)


GetBankAccountByIdUseCaseDep = Annotated[GetBankAccountByIdUseCase, Depends(get_bank_account_by_id_uc)]
ListBankAccountsUseCaseDep = Annotated[ListBankAccountsUseCase, Depends(list_bank_accounts_uc)]
CreateBankAccountUseCaseDep = Annotated[CreateBankAccountUseCase, Depends(create_bank_account_uc)]
UpdateBankAccountUseCaseDep = Annotated[UpdateBankAccountUseCase, Depends(update_bank_account_uc)]
DeleteBankAccountUseCaseDep = Annotated[DeleteBankAccountUseCase, Depends(delete_bank_account_uc)]


def import_transactions_uc(
    create_transaction: Annotated[CreateTransactionUseCase, Depends(create_transaction_uc)],
    create_user: Annotated["CreateUserUseCase", Depends(create_user_uc)],
    create_bank_account: Annotated[CreateBankAccountUseCase, Depends(create_bank_account_uc)],
    transaction_repo: Annotated[
        TransactionRepositoryInterface, Depends(get_transaction_repository)
    ],
    tax_rate_repo: Annotated[
        TaxRateRepositoryInterface, Depends(get_tax_rate_repository)
    ],
) -> ImportTransactionsUseCase:
    return ImportTransactionsUseCase(
        create_transaction_uc=create_transaction,
        create_user_uc=create_user,
        create_bank_account_uc=create_bank_account,
        transaction_repo=transaction_repo,
        tax_rate_repo=tax_rate_repo,
    )


ImportTransactionsUseCaseDep = Annotated[ImportTransactionsUseCase, Depends(import_transactions_uc)]


# Coupon
def get_coupon_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CouponRepositoryInterface:
    return SQLAlchemyCouponRepository(db)


def get_coupon_by_id_uc(
    repo: Annotated[CouponRepositoryInterface, Depends(get_coupon_repository)],
) -> GetCouponByIdUseCase:
    return GetCouponByIdUseCase(repo)


def list_coupons_uc(
    repo: Annotated[CouponRepositoryInterface, Depends(get_coupon_repository)],
) -> ListCouponsUseCase:
    return ListCouponsUseCase(repo)


def create_coupon_uc(
    repo: Annotated[CouponRepositoryInterface, Depends(get_coupon_repository)],
) -> CreateCouponUseCase:
    return CreateCouponUseCase(repo)


def update_coupon_uc(
    repo: Annotated[CouponRepositoryInterface, Depends(get_coupon_repository)],
) -> UpdateCouponUseCase:
    return UpdateCouponUseCase(repo)


def delete_coupon_uc(
    repo: Annotated[CouponRepositoryInterface, Depends(get_coupon_repository)],
) -> DeleteCouponUseCase:
    return DeleteCouponUseCase(repo)


GetCouponByIdUseCaseDep = Annotated[GetCouponByIdUseCase, Depends(get_coupon_by_id_uc)]
ListCouponsUseCaseDep = Annotated[ListCouponsUseCase, Depends(list_coupons_uc)]
CreateCouponUseCaseDep = Annotated[CreateCouponUseCase, Depends(create_coupon_uc)]
UpdateCouponUseCaseDep = Annotated[UpdateCouponUseCase, Depends(update_coupon_uc)]
DeleteCouponUseCaseDep = Annotated[DeleteCouponUseCase, Depends(delete_coupon_uc)]

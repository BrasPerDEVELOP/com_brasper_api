# app/modules/transactions/application/use_cases/transaction_use_cases.py
"""Casos de uso CRUD para Transaction."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.users.application.use_cases import CreateUserUseCase
    from app.modules.transactions.application.use_cases.bank_account_use_cases import CreateBankAccountUseCase

from app.shared.query_filter import FilterSchema, OperatorEnum, QueryFilter
from app.core.pagination.offset import PaginatedResult
from app.modules.coin.domain.enums import Currency
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.transactions.domain.models import Coupon, Transaction
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.world_cup.enums import ExchangeRateScope
from app.modules.world_cup.models import CouponRedemption
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.users.domain.enums import UserRole
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.modules.transactions.interfaces.transaction_repository import (
    TransactionRepositoryInterface,
)
from app.modules.transactions.interfaces.bank_account_repository import (
    BankAccountRepositoryInterface,
)
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
    TransactionListPage,
    TransactionMetricsDTO,
    ImportRequestCmd,
    ImportResponseDTO,
)

# Mapeo cmd -> entity (campos con sufijo _id en el modelo)
_CMD_TO_ENTITY = {
    "bank_account_origin": "bank_account_origin_id",
    "bank_account_destination": "bank_account_destination_id",
}

# Roles elegibles para asignación automática de agente al crear transacción (sin agent_id explícito).
_TRANSACTION_AGENT_ROLES = (UserRole.admin.value, UserRole.sales.value)


async def _resolve_agent_id_for_create(
    user_repo: UserRepositoryInterface,
    explicit_agent_id: Optional[UUID],
) -> Optional[UUID]:
    if explicit_agent_id is not None:
        return explicit_agent_id
    candidates = await user_repo.list_ids_by_roles(_TRANSACTION_AGENT_ROLES)
    if not candidates:
        return None
    return secrets.choice(candidates)


def _non_empty_str(value: Optional[str]) -> bool:
    return value is not None and str(value).strip() != ""


def _voucher_paths(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_voucher_paths(item))
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _merge_voucher_paths(*values: object) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in values:
        for path in _voucher_paths(value):
            if path in seen:
                continue
            seen.add(path)
            merged.append(path)
    return merged


def _sync_legacy_voucher_fields(data: dict) -> None:
    for singular, plural in (
        ("send_voucher", "send_vouchers"),
        ("payment_voucher", "payment_vouchers"),
        ("checked_image", "checked_images"),
    ):
        paths = _merge_voucher_paths(data.get(plural), data.get(singular))
        if paths:
            data[plural] = paths
            data[singular] = paths[0]
        elif plural in data:
            data[plural] = []
            data[singular] = None


def _append_voucher_updates(entity: Transaction, updates: dict) -> None:
    for singular, plural in (
        ("send_voucher", "send_vouchers"),
        ("payment_voucher", "payment_vouchers"),
        ("checked_image", "checked_images"),
    ):
        incoming = _merge_voucher_paths(updates.pop(plural, None), updates.pop(singular, None))
        if not incoming:
            continue
        paths = _merge_voucher_paths(getattr(entity, plural, None), getattr(entity, singular, None), incoming)
        updates[plural] = paths
        updates[singular] = paths[0] if paths else None


def _is_transaction_pipeline_complete(entity: Transaction) -> bool:
    """True si checklist y datos operativos (montos, send_date, vouchers) están completos.
    `payment_date` no se exige aquí: se asigna en servidor al pasar a completed."""
    return (
        entity.checked is True
        and entity.commission_result is not None
        and entity.total_to_send is not None
        and entity.send_date is not None
        and bool(_merge_voucher_paths(entity.send_vouchers, entity.send_voucher))
        and bool(_merge_voucher_paths(entity.payment_vouchers, entity.payment_voucher))
    )


def sync_transaction_status_from_checklist(entity: Transaction) -> None:
    """Asigna status según checklist y completitud; no modifica transacciones fallidas.
    Al pasar a `completed` por primera vez, fija `payment_date` a ahora (UTC)."""
    previous_status = entity.status
    if entity.status == TransactionStatus.failed:
        return
    if not entity.checked:
        entity.status = TransactionStatus.verification
        return
    if _is_transaction_pipeline_complete(entity):
        if previous_status != TransactionStatus.completed:
            entity.payment_date = datetime.now(timezone.utc)
        entity.status = TransactionStatus.completed
    else:
        entity.status = TransactionStatus.verified


def _parse_currency_filter(value: Optional[str]) -> Optional[Currency]:
    """Convierte PEN, pen, usd, etc. a Currency; None si viene vacío."""
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        return Currency(raw.upper())
    except ValueError:
        return Currency[raw.lower()]


def _build_transaction_query_filter(
    user_id: Optional[UUID] = None,
    bank_account_origin_id: Optional[UUID] = None,
    bank_account_destination_id: Optional[UUID] = None,
    created_at_from: Optional[datetime] = None,
    created_at_to: Optional[datetime] = None,
) -> Optional[QueryFilter]:
    """Construye QueryFilter para transacciones.

    Nota: el estado se filtra aparte (estado "efectivo") y la búsqueda de texto
    y el rango por ``send_date`` se resuelven en el repositorio.
    """
    filter_specs = [
        (user_id, "user_id", OperatorEnum.EQ),
        (bank_account_origin_id, "bank_account_origin_id", OperatorEnum.EQ),
        (bank_account_destination_id, "bank_account_destination_id", OperatorEnum.EQ),
        (created_at_from, "created_at", OperatorEnum.GTE),
        (created_at_to, "created_at", OperatorEnum.LTE),
    ]
    filters = [
        FilterSchema(field=field, value=val, operator=op)
        for val, field, op in filter_specs
        if val is not None
    ]
    return QueryFilter(filters=filters) if filters else None


def _cmd_to_entity_data(data: dict) -> dict:
    """Convierte nombres de campos del cmd al modelo entity."""
    return {
        _CMD_TO_ENTITY.get(k, k): v
        for k, v in data.items()
        if k != "id"
    }


async def _hydrate_bank_snapshot_from_destination(
    bank_account_repo: BankAccountRepositoryInterface,
    *,
    bank_account_destination_id: UUID,
    entity_data: dict,
) -> None:
    """Rellena bank_id, bank_name y company_name desde la cuenta destino y su Bank."""
    from sqlalchemy.orm import selectinload

    from app.modules.transactions.domain.models import BankAccount

    acc = await bank_account_repo.get(
        bank_account_destination_id,
        eager_options=(selectinload(BankAccount.bank),),
    )
    if not acc:
        raise ValueError(
            f"No existe cuenta bancaria destino con id {bank_account_destination_id}"
        )
    entity_data["bank_id"] = acc.bank_id
    b = acc.bank
    if b is not None:
        entity_data["bank_name"] = b.bank
        entity_data["company_name"] = b.company


def _drop_null_voucher_paths_unless_remove(
    updates: dict,
    remove_send: bool,
    remove_payment: bool,
    remove_checked: bool,
) -> None:
    """Evita que `null` o defaults en el payload borren archivos; solo aplica con remove_*_voucher o remove_checked_image."""
    if not remove_send and updates.get("send_voucher") is None:
        updates.pop("send_voucher", None)
    if not remove_payment and updates.get("payment_voucher") is None:
        updates.pop("payment_voucher", None)
    if not remove_checked and updates.get("checked_image") is None:
        updates.pop("checked_image", None)
    if not remove_send and updates.get("send_vouchers") is None:
        updates.pop("send_vouchers", None)
    if not remove_payment and updates.get("payment_vouchers") is None:
        updates.pop("payment_vouchers", None)
    if not remove_checked and updates.get("checked_images") is None:
        updates.pop("checked_images", None)


_TXN_LOAD_USER = (selectinload(Transaction.user),)


class GetTransactionByIdUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, transaction_id: UUID) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(transaction_id, eager_options=_TXN_LOAD_USER)
        return TransactionReadDTO.model_validate(entity) if entity else None


class ListTransactionsUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        *,
        limit: int,
        skip: int,
        status: Optional[TransactionStatus] = None,
        user_id: Optional[UUID] = None,
        bank_account_origin_id: Optional[UUID] = None,
        bank_account_destination_id: Optional[UUID] = None,
        bank_account_id: Optional[UUID] = None,
        created_at_from: Optional[datetime] = None,
        created_at_to: Optional[datetime] = None,
        send_date_from: Optional[datetime] = None,
        send_date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        currency: Optional[Currency] = None,
        origin_currency: Optional[Currency] = None,
        destination_currency: Optional[Currency] = None,
    ) -> TransactionListPage:
        query_filter = _build_transaction_query_filter(
            user_id=user_id,
            bank_account_origin_id=bank_account_origin_id,
            bank_account_destination_id=bank_account_destination_id,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
        raw = await self.repo.list(
            query_filter=query_filter,
            eager_options=_TXN_LOAD_USER,
            limit=limit,
            offset=skip,
            currency=currency,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            search=search,
            effective_status=status.value if status is not None else None,
            send_date_from=send_date_from,
            send_date_to=send_date_to,
            bank_account_id=bank_account_id,
        )
        if isinstance(raw, PaginatedResult):
            items = [TransactionReadDTO.model_validate(x) for x in raw.items]
            return TransactionListPage(
                items=items,
                total=raw.total,
                skip=raw.skip,
                limit=raw.limit,
                has_next=raw.has_next,
                has_previous=raw.has_previous,
            )
        items = [TransactionReadDTO.model_validate(x) for x in raw]
        return TransactionListPage(
            items=items,
            total=len(items),
            skip=skip,
            limit=limit,
            has_next=False,
            has_previous=skip > 0,
        )


class GetTransactionMetricsUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self) -> TransactionMetricsDTO:
        data = await self.repo.metrics()
        return TransactionMetricsDTO(**data)


class CreateTransactionUseCase:
    def __init__(
        self,
        repo: TransactionRepositoryInterface,
        tax_rate_repo: TaxRateRepositoryInterface,
        user_repo: UserRepositoryInterface,
        bank_account_repo: BankAccountRepositoryInterface,
        commission_repo: Optional[CommissionRepositoryInterface] = None,
        session: Optional[AsyncSession] = None,
    ):
        self.repo = repo
        self._tax_rate_repo = tax_rate_repo
        self._user_repo = user_repo
        self._bank_account_repo = bank_account_repo
        self._commission_repo = commission_repo
        self._session = session

    async def _apply_server_financials(self, cmd, tax_rate, entity_data) -> Optional[Coupon]:
        """Recalcula los importes y reserva el cupón; el guard permite tests/consumidores legacy."""
        if self._commission_repo is None or self._session is None:
            return None
        commission = await self._commission_repo.get(cmd.commission_id)
        if not commission:
            raise ValueError(f"No existe commission con id {cmd.commission_id}")
        if commission.coin_a != tax_rate.coin_a or commission.coin_b != tax_rate.coin_b:
            raise ValueError("La comisión no corresponde al par de monedas de la tasa")
        amount = float(cmd.origin_amount)
        if amount <= 0:
            raise ValueError("El monto de origen debe ser mayor que cero")
        if commission.min_amount is not None and amount < float(commission.min_amount):
            raise ValueError("El monto está por debajo del rango de comisión")
        if commission.max_amount is not None and amount > float(commission.max_amount):
            raise ValueError("El monto supera el rango de comisión")
        base_commission = round(amount * float(commission.percentage) / 100, 2)
        coupon = None
        discount = 0.0
        if cmd.coupon_id:
            coupon = (await self._session.execute(
                select(Coupon).where(Coupon.id == cmd.coupon_id, Coupon.deleted.is_(False)).with_for_update()
            )).scalar_one_or_none()
            if not coupon or not coupon.is_active or coupon.lifecycle_status != "ACTIVE":
                raise ValueError("El cupón no está activo")
            now = datetime.now(timezone.utc)
            if (coupon.start_date and coupon.start_date > now) or (coupon.end_date and coupon.end_date < now):
                raise ValueError("El cupón no está vigente")
            exchange_rate_scopes = getattr(coupon, "exchange_rate_scopes", None)
            if exchange_rate_scopes:
                if not ExchangeRateScope.matches_pair(exchange_rate_scopes, tax_rate.coin_a, tax_rate.coin_b):
                    raise ValueError("El cupón no corresponde al par de monedas")
            elif (
                coupon.origin_currency is not None and coupon.origin_currency != tax_rate.coin_a
            ) or (
                coupon.destination_currency is not None and coupon.destination_currency != tax_rate.coin_b
            ):
                raise ValueError("El cupón no corresponde al par de monedas")
            if coupon.used_count >= coupon.max_uses:
                raise ValueError("El cupón agotó sus usos")
            if coupon.per_user_limit:
                used_by_user = await self._session.scalar(select(func.count(CouponRedemption.id)).where(
                    CouponRedemption.coupon_id == coupon.id,
                    CouponRedemption.user_id == cmd.user_id,
                    CouponRedemption.deleted.is_(False),
                ))
                if int(used_by_user or 0) >= coupon.per_user_limit:
                    raise ValueError("Ya alcanzaste el límite de uso de este cupón")
            discount = round(min(base_commission * float(coupon.discount_percentage) / 100, base_commission), 2)
            coupon.used_count += 1
        effective_commission = round(base_commission - discount, 2)
        total_to_send = round(amount - effective_commission, 2)
        destination_amount = round(total_to_send * float(tax_rate.tax), 2)
        entity_data.update({
            "commission_result": effective_commission,
            "total_to_send": total_to_send,
            "destination_amount": destination_amount,
            "coupon_discount_code": coupon.code if coupon else None,
            "coupon_origin_amount": amount if coupon else None,
            "coupon_destination_amount": destination_amount if coupon else None,
            "coupon_discount_percentage": float(coupon.discount_percentage) if coupon else None,
            "coupon_discount_commission": discount if coupon else None,
            "coupon_discount_total_to_send": total_to_send if coupon else None,
        })
        return coupon

    async def execute(self, cmd: TransactionCreateCmd) -> TransactionReadDTO:
        entity_data = _cmd_to_entity_data(cmd.model_dump())
        entity_data["agent_id"] = await _resolve_agent_id_for_create(
            self._user_repo,
            entity_data.get("agent_id"),
        )
        await _hydrate_bank_snapshot_from_destination(
            self._bank_account_repo,
            bank_account_destination_id=entity_data["bank_account_destination_id"],
            entity_data=entity_data,
        )
        reserved_bank_id = entity_data.get("bank_id")
        bank_overrides = cmd.model_dump(
            exclude_unset=True,
            include={"bank_id", "bank_name", "company_name"},
        )
        if bank_overrides.get("bank_id") is not None:
            if bank_overrides["bank_id"] != reserved_bank_id:
                raise ValueError("bank_id no coincide con el banco de la cuenta destino")
        for key, val in bank_overrides.items():
            if val is not None:
                entity_data[key] = val
        tax_rate = await self._tax_rate_repo.get(cmd.tax_rate_id)
        if not tax_rate:
            raise ValueError(f"No existe tax_rate con id {cmd.tax_rate_id}")
        coupon = await self._apply_server_financials(cmd, tax_rate, entity_data)
        entity_data["code"] = await self.repo.next_sequential_transaction_code(
            tax_rate.coin_a.value,
            tax_rate.coin_b.value,
        )
        # Alta: sin checklist; estado en verificación (el cliente no puede activar el check al crear)
        entity_data["checked"] = False
        entity_data["status"] = TransactionStatus.verification
        # Fecha/hora de creación de la operación (envío); no se toma del cliente
        entity_data["send_date"] = datetime.now(timezone.utc)
        _sync_legacy_voucher_fields(entity_data)
        entity = Transaction(**entity_data)
        sync_transaction_status_from_checklist(entity)
        saved = await self.repo.add(entity)
        if coupon and self._session is not None:
            self._session.add(CouponRedemption(coupon_id=coupon.id, user_id=cmd.user_id, transaction_id=saved.id))
        await self.repo.commit()
        await self.repo.refresh(saved, load_noload_relations=["user"])
        return TransactionReadDTO.model_validate(saved)


class UpdateTransactionUseCase:
    def __init__(
        self,
        repo: TransactionRepositoryInterface,
        bank_account_repo: BankAccountRepositoryInterface,
    ):
        self.repo = repo
        self._bank_account_repo = bank_account_repo

    async def execute(self, cmd: TransactionUpdateCmd) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(cmd.id, eager_options=_TXN_LOAD_USER)
        if not entity:
            return None

        updates = _cmd_to_entity_data(cmd.model_dump(exclude_unset=True))
        remove_send_voucher = bool(updates.pop("remove_send_voucher", None))
        remove_payment_voucher = bool(updates.pop("remove_payment_voucher", None))
        remove_checked_image = bool(updates.pop("remove_checked_image", None))
        # No escribir NULL en rutas de archivo por "null" en JSON u objeto reenviado: solo
        # se borra con remove_*; actualizar un voucher no afecta a los demás.
        _drop_null_voucher_paths_unless_remove(
            updates, remove_send_voucher, remove_payment_voucher, remove_checked_image
        )
        # No actualizar checked si es None (el modelo requiere bool)
        updates = {k: v for k, v in updates.items() if k != "checked" or v is not None}

        if remove_send_voucher:
            updates["send_voucher"] = None
            updates["send_vouchers"] = []
        if remove_payment_voucher:
            updates["payment_voucher"] = None
            updates["payment_vouchers"] = []
        if remove_checked_image:
            updates["checked_image"] = None
            updates["checked_images"] = []

        _append_voucher_updates(entity, updates)

        dest_id = updates.get("bank_account_destination_id")
        if dest_id is not None:
            snap: dict = {}
            await _hydrate_bank_snapshot_from_destination(
                self._bank_account_repo,
                bank_account_destination_id=dest_id,
                entity_data=snap,
            )
            updates["bank_id"] = snap.get("bank_id")
            updates["bank_name"] = snap.get("bank_name")
            # Respeta la razón social enviada explícitamente (igual que en create);
            # solo se deriva de la cuenta destino cuando el request no la trae.
            if updates.get("company_name") is None:
                updates["company_name"] = snap.get("company_name")

        for attr, value in updates.items():
            setattr(entity, attr, value)

        sync_transaction_status_from_checklist(entity)

        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity, load_noload_relations=["user"])
        return TransactionReadDTO.model_validate(entity)


class DeleteTransactionUseCase:
    def __init__(self, repo: TransactionRepositoryInterface, session: Optional[AsyncSession] = None):
        self.repo = repo
        self._session = session

    async def execute(self, transaction_id: UUID) -> None:
        if self._session is not None:
            transaction = await self._session.get(Transaction, transaction_id)
            if transaction and transaction.coupon_id:
                coupon = (await self._session.execute(select(Coupon).where(Coupon.id == transaction.coupon_id).with_for_update())).scalar_one_or_none()
                redemptions = (await self._session.execute(select(CouponRedemption).where(CouponRedemption.transaction_id == transaction_id, CouponRedemption.deleted.is_(False)))).scalars().all()
                for redemption in redemptions:
                    redemption.deleted = True
                if coupon and redemptions:
                    coupon.used_count = max(coupon.used_count - len(redemptions), 0)
        await self.repo.delete(transaction_id)
        await self.repo.commit()


class ImportTransactionsUseCase:
    """Caso de uso para recibir archivo de importación. Valida formato y retorna metadata.
    Usa CreateTransactionUseCase, CreateUserUseCase y CreateBankAccountUseCase para crear entidades al importar.
    """

    def __init__(
        self,
        create_transaction_uc: "CreateTransactionUseCase",
        create_user_uc: "CreateUserUseCase",
        create_bank_account_uc: "CreateBankAccountUseCase",
        transaction_repo: TransactionRepositoryInterface,
        tax_rate_repo: TaxRateRepositoryInterface,
    ):
        self._create_transaction = create_transaction_uc
        self._create_user = create_user_uc
        self._create_bank_account = create_bank_account_uc
        self._transaction_repo = transaction_repo
        self._tax_rate_repo = tax_rate_repo

    async def execute(self, body: ImportRequestCmd) -> ImportResponseDTO:
        """Procesa la importación: por cada item crea user_origin+bank_account_origin, user_destination+bank_account_destination,
        y transaction. Cada usuario se relaciona directamente con su bank_account.
        """
        from app.modules.transactions.application.schemas.bank_account_schema import BankAccountCreateCmd
        from app.modules.users.application.schemas.user_schema import UserCreateCmd

        created_users = 0
        created_bank_accounts = 0
        created_transactions = 0

        for item in body.items:
            # Emisor: user_origin + bank_account_origin (cada bank_account pertenece a su user)
            user_origin_cmd = UserCreateCmd.model_validate(item.user_origin.user)
            user_origin_dto = await self._create_user.execute(user_origin_cmd, profile_image=None)
            user_origin_id = user_origin_dto.id
            created_users += 1

            bank_origin_data = item.user_origin.bank_account.model_dump()
            bank_origin_data["user_id"] = user_origin_id
            bank_origin_cmd = BankAccountCreateCmd.model_validate(bank_origin_data)
            bank_origin_dto = await self._create_bank_account.execute(bank_origin_cmd)
            created_bank_accounts += 1

            # Receptor: user_destination + bank_account_destination
            user_dest_cmd = UserCreateCmd.model_validate(item.user_destination.user)
            user_dest_dto = await self._create_user.execute(user_dest_cmd, profile_image=None)
            user_dest_id = user_dest_dto.id
            created_users += 1

            bank_dest_data = item.user_destination.bank_account.model_dump()
            bank_dest_data["user_id"] = user_dest_id
            bank_dest_cmd = BankAccountCreateCmd.model_validate(bank_dest_data)
            bank_dest_dto = await self._create_bank_account.execute(bank_dest_cmd)
            created_bank_accounts += 1

            # Transaction: user_id = emisor, code = secuencial PxB-0000000001 (según tasa/moneda)
            tax_rate = await self._tax_rate_repo.get(item.transaction.tax_rate_id)
            if not tax_rate:
                raise ValueError(
                    f"No existe tax_rate con id {item.transaction.tax_rate_id}"
                )
            code = await self._transaction_repo.next_sequential_transaction_code(
                tax_rate.coin_a.value,
                tax_rate.coin_b.value,
            )
            txn_data = item.transaction.model_dump()
            txn_data["user_id"] = user_origin_id
            txn_data["bank_account_origin"] = bank_origin_dto.id
            txn_data["bank_account_destination"] = bank_dest_dto.id
            txn_data["code"] = code
            txn_cmd = TransactionCreateCmd.model_validate(txn_data)
            await self._create_transaction.execute(txn_cmd)
            created_transactions += 1

        return ImportResponseDTO(
            created_transactions=created_transactions,
            created_users=created_users,
            created_bank_accounts=created_bank_accounts,
        )

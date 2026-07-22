# app/modules/transactions/application/use_cases/transaction_use_cases.py
"""Casos de uso CRUD para Transaction."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
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
from app.modules.transactions.domain.models import Coupon, CouponRedemption, Transaction, TransactionDestination
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.transactions.domain.enums import AccountFlowType, ExchangeRateScope, TransactionStatus
from app.modules.users.domain.enums import UserRole
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.modules.transactions.interfaces.transaction_repository import (
    TransactionRepositoryInterface,
)
from app.modules.transactions.interfaces.bank_account_repository import (
    BankAccountRepositoryInterface,
)
from app.modules.transactions.interfaces.bank_repository import BankRepositoryInterface
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

# Código sentinela de la "calculadora especial": descuento de comisión manual, sin cupón real.
SPECIAL_CALCULATOR_DISCOUNT_CODE = "ESPECIAL"


def _is_special_calculator_code(code: Optional[str]) -> bool:
    """True si el código corresponde a la calculadora especial (no un cupón real)."""
    return bool(code) and code.strip().upper() == SPECIAL_CALCULATOR_DISCOUNT_CODE


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


def _voucher_matches(existing: str, provided: str) -> bool:
    """Compara una key almacenada con el valor recibido (key relativa o URL completa del GET)."""
    stored = str(existing or "").strip().lstrip("/")
    candidate = str(provided or "").strip()
    if not stored or not candidate:
        return False
    candidate = candidate.split("?", 1)[0].split("#", 1)[0]
    normalized = candidate.lstrip("/")
    if normalized == stored:
        return True
    return candidate.endswith(f"/{stored}")


_VOUCHER_UPDATE_FIELDS = (
    ("send_voucher", "send_vouchers", "remove_send_voucher", "send_vouchers_keep"),
    ("payment_voucher", "payment_vouchers", "remove_payment_voucher", "payment_vouchers_keep"),
    ("checked_image", "checked_images", "remove_checked_image", "checked_images_keep"),
)


def _apply_voucher_updates(
    entity: Transaction,
    updates: dict,
    removes: dict,
    keeps: dict,
) -> None:
    """Resuelve el estado final de cada grupo de vouchers en un PUT.

    - `remove_*` → borra todo el grupo.
    - `*_keep` → conserva solo los archivos existentes listados (borrado individual).
    - Sin remove ni keep → los existentes se conservan y los uploads se agregan (append).
    En todos los casos los archivos subidos en el request se agregan al final; un `null`
    en el payload nunca borra rutas porque los valores de voucher se resuelven aquí.
    """
    for singular, plural, remove_key, keep_key in _VOUCHER_UPDATE_FIELDS:
        incoming = _merge_voucher_paths(updates.pop(plural, None), updates.pop(singular, None))
        keep = keeps.get(keep_key)
        if removes.get(remove_key):
            base: list[str] = []
        else:
            existing = _merge_voucher_paths(
                getattr(entity, plural, None), getattr(entity, singular, None)
            )
            if keep is not None:
                base = [
                    path
                    for path in existing
                    if any(_voucher_matches(path, kept) for kept in keep)
                ]
            else:
                if not incoming:
                    continue
                base = existing
        paths = _merge_voucher_paths(base, incoming)
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


async def _hydrate_social_reason_snapshot(
    bank_repo: BankRepositoryInterface,
    *,
    social_reason_bank_id: UUID,
    entity_data: dict,
) -> None:
    """Valida y persiste la razón social exacta elegida por su banco."""
    bank = await bank_repo.get(social_reason_bank_id)
    if not bank:
        raise ValueError(
            f"No existe banco de razón social con id {social_reason_bank_id}"
        )
    entity_data["social_reason_bank_id"] = social_reason_bank_id
    entity_data["company_name"] = bank.company


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _destination_items_total(destinations: list) -> Decimal:
    return sum((_money(item.amount) for item in destinations), Decimal("0.00"))


def _merge_destination_entities(
    existing: list, replacements: list
) -> list:
    """Reutiliza las filas existentes por cuenta al reemplazar `destinations`.

    SQLAlchemy ejecuta los INSERT antes que los DELETE dentro del mismo flush;
    reemplazar la colección con la misma cuenta violaría la restricción única
    (transaction_id, bank_account_id) → IntegrityError 500. Actualizar la fila
    existente en su lugar evita el conflicto; las cuentas quitadas se eliminan
    vía delete-orphan y solo las realmente nuevas se insertan.
    """
    by_account = {row.bank_account_id: row for row in existing}
    merged = []
    for replacement in replacements:
        current = by_account.get(replacement.bank_account_id)
        if current is not None:
            current.amount = replacement.amount
            current.position = replacement.position
            merged.append(current)
        else:
            merged.append(replacement)
    return merged


async def _build_transaction_destinations(
    bank_account_repo: BankAccountRepositoryInterface,
    *,
    destinations: list,
    user_id: UUID,
    destination_currency: Currency,
    destination_amount: float,
) -> list[TransactionDestination]:
    """Valida la distribución explícita y construye sus entidades ordenadas."""
    from app.modules.transactions.domain.models import BankAccount

    if not destinations:
        raise ValueError("Debe indicar al menos una cuenta destino")
    seen: set[UUID] = set()
    entities: list[TransactionDestination] = []
    total = Decimal("0.00")
    for position, item in enumerate(destinations):
        account_id = item.bank_account_id
        if account_id in seen:
            raise ValueError("No se puede repetir una cuenta destino")
        seen.add(account_id)
        amount = _money(item.amount)
        if amount <= 0:
            raise ValueError("Cada monto destino debe ser mayor que cero")
        account = await bank_account_repo.get(
            account_id,
            eager_options=(selectinload(BankAccount.bank),),
        )
        if not account:
            raise ValueError(f"No existe cuenta bancaria destino con id {account_id}")
        if account.user_id != user_id:
            raise ValueError("Todas las cuentas destino deben pertenecer al cliente")
        if account.account_flow != AccountFlowType.destination:
            raise ValueError("Todas las cuentas seleccionadas deben ser cuentas destino")
        if account.bank is None or account.bank.currency != destination_currency:
            raise ValueError("Todas las cuentas destino deben usar la moneda de recepción")
        total += amount
        entities.append(
            TransactionDestination(
                bank_account_id=account_id,
                amount=float(amount),
                position=position,
            )
        )
    expected_total = _money(destination_amount)
    # El frontend y el servidor calculan comisión/tasa en momentos distintos.
    # Una diferencia de un centavo puede aparecer por el orden de redondeo; la
    # distribución manual es el total operativo que finalmente se transferirá.
    if abs(total - expected_total) > Decimal("0.01"):
        raise ValueError(
            "La suma de cuentas destino debe coincidir con el monto a recibir "
            f"(distribuido: {total:.2f}; calculado: {expected_total:.2f})"
        )
    return entities


_TXN_LOAD_USER = (
    selectinload(Transaction.user),
    selectinload(Transaction.destinations),
)


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
        bank_repo: BankRepositoryInterface,
        commission_repo: Optional[CommissionRepositoryInterface] = None,
        session: Optional[AsyncSession] = None,
    ):
        self.repo = repo
        self._tax_rate_repo = tax_rate_repo
        self._user_repo = user_repo
        self._bank_account_repo = bank_account_repo
        self._bank_repo = bank_repo
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
        if commission.max_amount is not None and amount > float(commission.max_amount):
            raise ValueError("El monto supera el rango de comisión")
        base_commission = round(amount * float(commission.percentage) / 100, 2)
        coupon = None
        discount = 0.0
        is_special = False
        special_discount_percentage: Optional[float] = None
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
        elif _is_special_calculator_code(cmd.coupon_discount_code):
            # Calculadora especial: descuento de comisión manual, sin cupón real. Puede ser
            # negativo (recargo). Se PERSISTE para que el monto especial sea correcto server-side
            # y no dependa solo del navegador (sessionStorage).
            is_special = True
            discount = round(float(cmd.coupon_discount_commission or 0.0), 2)
            special_discount_percentage = (
                float(cmd.coupon_discount_percentage)
                if cmd.coupon_discount_percentage is not None
                else None
            )
        effective_commission = round(base_commission - discount, 2)
        # La comisión efectiva no puede superar el monto de origen (envío no negativo).
        if effective_commission > amount:
            effective_commission = amount
        total_to_send = round(amount - effective_commission, 2)
        effective_tax_rate = float(tax_rate.tax)
        if is_special and cmd.tax_amount is not None:
            requested_tax_rate = float(cmd.tax_amount)
            if not isfinite(requested_tax_rate) or requested_tax_rate <= 0:
                raise ValueError("La tasa especial debe ser mayor que cero")
            effective_tax_rate = requested_tax_rate
        destination_amount = round(total_to_send * effective_tax_rate, 2)
        financials: dict = {
            "commission_result": effective_commission,
            "total_to_send": total_to_send,
            "destination_amount": destination_amount,
            # En una operación normal manda siempre el catálogo. La calculadora
            # especial puede enviar una tasa manual y debe conservarse en el
            # snapshot financiero para que el servidor reproduzca la cotización.
            "tax_amount": effective_tax_rate,
        }
        if coupon:
            financials.update({
                "coupon_discount_code": coupon.code,
                "coupon_origin_amount": amount,
                "coupon_destination_amount": destination_amount,
                "coupon_discount_percentage": float(coupon.discount_percentage),
                "coupon_discount_commission": discount,
                "coupon_discount_total_to_send": total_to_send,
            })
        elif is_special:
            financials.update({
                "coupon_discount_code": SPECIAL_CALCULATOR_DISCOUNT_CODE,
                "coupon_origin_amount": amount,
                "coupon_destination_amount": destination_amount,
                "coupon_discount_percentage": special_discount_percentage,
                "coupon_discount_commission": discount,
                "coupon_discount_total_to_send": total_to_send,
            })
        else:
            financials.update({
                "coupon_discount_code": None,
                "coupon_origin_amount": None,
                "coupon_destination_amount": None,
                "coupon_discount_percentage": None,
                "coupon_discount_commission": None,
                "coupon_discount_total_to_send": None,
            })
        entity_data.update(financials)
        return coupon

    async def execute(self, cmd: TransactionCreateCmd) -> TransactionReadDTO:
        entity_data = _cmd_to_entity_data(cmd.model_dump())
        entity_data.pop("destinations", None)
        requested_destinations = cmd.destinations
        entity_data["agent_id"] = await _resolve_agent_id_for_create(
            self._user_repo,
            entity_data.get("agent_id"),
        )
        if requested_destinations:
            entity_data["bank_account_destination_id"] = requested_destinations[0].bank_account_id
        await _hydrate_bank_snapshot_from_destination(
            self._bank_account_repo,
            bank_account_destination_id=entity_data["bank_account_destination_id"],
            entity_data=entity_data,
        )
        reserved_bank_id = entity_data.get("bank_id")
        requested_bank_data = cmd.model_dump(
            exclude_unset=True,
            include={"bank_id", "company_name", "social_reason_bank_id"},
        )
        if requested_bank_data.get("bank_id") is not None:
            if requested_bank_data["bank_id"] != reserved_bank_id:
                raise ValueError("bank_id no coincide con el banco de la cuenta destino")

        social_reason_bank_id = requested_bank_data.get("social_reason_bank_id")
        if social_reason_bank_id is not None:
            await _hydrate_social_reason_snapshot(
                self._bank_repo,
                social_reason_bank_id=social_reason_bank_id,
                entity_data=entity_data,
            )
        elif requested_bank_data.get("company_name") is not None:
            # Compatibilidad temporal con clientes anteriores al campo FK.
            entity_data["company_name"] = requested_bank_data["company_name"]
        tax_rate = await self._tax_rate_repo.get(cmd.tax_rate_id)
        if not tax_rate:
            raise ValueError(f"No existe tax_rate con id {cmd.tax_rate_id}")
        coupon = await self._apply_server_financials(cmd, tax_rate, entity_data)
        if requested_destinations is not None:
            destination_entities = await _build_transaction_destinations(
                self._bank_account_repo,
                destinations=requested_destinations,
                user_id=cmd.user_id,
                destination_currency=tax_rate.coin_b,
                destination_amount=entity_data["destination_amount"],
            )
            distributed_total = _destination_items_total(requested_destinations)
            entity_data["destination_amount"] = float(distributed_total)
            if entity_data.get("coupon_destination_amount") is not None:
                entity_data["coupon_destination_amount"] = float(distributed_total)
        else:
            destination_entities = [
                TransactionDestination(
                    bank_account_id=entity_data["bank_account_destination_id"],
                    amount=float(_money(entity_data["destination_amount"])),
                    position=0,
                )
            ]
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
        entity.destinations = destination_entities
        sync_transaction_status_from_checklist(entity)
        saved = await self.repo.add(entity)
        if coupon and self._session is not None:
            self._session.add(CouponRedemption(coupon_id=coupon.id, user_id=cmd.user_id, transaction_id=saved.id))
        await self.repo.commit()
        await self.repo.refresh(saved, load_noload_relations=["user", "destinations"])
        return TransactionReadDTO.model_validate(saved)


class UpdateTransactionUseCase:
    def __init__(
        self,
        repo: TransactionRepositoryInterface,
        bank_account_repo: BankAccountRepositoryInterface,
        bank_repo: BankRepositoryInterface,
        tax_rate_repo: TaxRateRepositoryInterface,
    ):
        self.repo = repo
        self._bank_account_repo = bank_account_repo
        self._bank_repo = bank_repo
        self._tax_rate_repo = tax_rate_repo

    async def execute(self, cmd: TransactionUpdateCmd) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(cmd.id, eager_options=_TXN_LOAD_USER)
        if not entity:
            return None

        updates = _cmd_to_entity_data(cmd.model_dump(exclude_unset=True))
        updates.pop("destinations", None)
        requested_destinations = (
            cmd.destinations if "destinations" in cmd.model_fields_set else None
        )
        removes = {
            "remove_send_voucher": bool(updates.pop("remove_send_voucher", None)),
            "remove_payment_voucher": bool(updates.pop("remove_payment_voucher", None)),
            "remove_checked_image": bool(updates.pop("remove_checked_image", None)),
        }
        keeps = {
            "send_vouchers_keep": updates.pop("send_vouchers_keep", None),
            "payment_vouchers_keep": updates.pop("payment_vouchers_keep", None),
            "checked_images_keep": updates.pop("checked_images_keep", None),
        }
        # No actualizar checked si es None (el modelo requiere bool)
        updates = {k: v for k, v in updates.items() if k != "checked" or v is not None}

        # Estado final de vouchers: remove_* borra el grupo, *_keep conserva solo los
        # existentes listados (borrado individual) y los uploads siempre se agregan.
        _apply_voucher_updates(entity, updates, removes, keeps)

        fields_set = cmd.model_fields_set
        social_reason_was_sent = "social_reason_bank_id" in fields_set
        company_name_was_sent = "company_name" in fields_set
        if requested_destinations:
            updates["bank_account_destination_id"] = requested_destinations[0].bank_account_id
        dest_id = updates.get("bank_account_destination_id")
        destination_snapshot: dict = {}
        if dest_id is not None:
            await _hydrate_bank_snapshot_from_destination(
                self._bank_account_repo,
                bank_account_destination_id=dest_id,
                entity_data=destination_snapshot,
            )
            updates["bank_id"] = destination_snapshot.get("bank_id")
            updates["bank_name"] = destination_snapshot.get("bank_name")

            # Compatibilidad para registros legacy: si aún no tienen una FK de
            # razón social, conservan el comportamiento histórico al cambiar la
            # cuenta destino. Una selección persistida nunca se sobrescribe.
            if (
                not social_reason_was_sent
                and not company_name_was_sent
                and entity.social_reason_bank_id is None
            ):
                updates["company_name"] = destination_snapshot.get("company_name")

        if social_reason_was_sent:
            social_reason_bank_id = updates.get("social_reason_bank_id")
            if social_reason_bank_id is not None:
                await _hydrate_social_reason_snapshot(
                    self._bank_repo,
                    social_reason_bank_id=social_reason_bank_id,
                    entity_data=updates,
                )
            elif not company_name_was_sent:
                # Al limpiar una selección, deja un snapshot legacy coherente con
                # la cuenta destino aunque esta no venga repetida en el request.
                if not destination_snapshot:
                    await _hydrate_bank_snapshot_from_destination(
                        self._bank_account_repo,
                        bank_account_destination_id=entity.bank_account_destination_id,
                        entity_data=destination_snapshot,
                    )
                updates["company_name"] = destination_snapshot.get("company_name")
        elif entity.social_reason_bank_id is not None:
            # Un cliente antiguo puede reenviar `company_name` sin conocer el FK.
            # Mientras exista una selección exacta, el banco persistido es la fuente
            # autoritativa y evita que ese snapshot quede desincronizado.
            await _hydrate_social_reason_snapshot(
                self._bank_repo,
                social_reason_bank_id=entity.social_reason_bank_id,
                entity_data=updates,
            )

        replacement_destinations: Optional[list[TransactionDestination]] = None
        if requested_destinations is not None:
            tax_rate_id = updates.get("tax_rate_id", entity.tax_rate_id)
            tax_rate = await self._tax_rate_repo.get(tax_rate_id)
            if not tax_rate:
                raise ValueError(f"No existe tax_rate con id {tax_rate_id}")
            replacement_destinations = await _build_transaction_destinations(
                self._bank_account_repo,
                destinations=requested_destinations,
                user_id=updates.get("user_id", entity.user_id),
                destination_currency=tax_rate.coin_b,
                destination_amount=updates.get("destination_amount", entity.destination_amount),
            )
            distributed_total = _destination_items_total(requested_destinations)
            updates["destination_amount"] = float(distributed_total)
            if updates.get("coupon_destination_amount") is not None:
                updates["coupon_destination_amount"] = float(distributed_total)
        elif "destination_amount" in updates:
            existing_destinations = list(entity.destinations or [])
            if len(existing_destinations) > 1:
                current_total = sum((_money(item.amount) for item in existing_destinations), Decimal("0.00"))
                if current_total != _money(updates["destination_amount"]):
                    raise ValueError(
                        "Debe enviar destinations al modificar una transacción con varias cuentas"
                    )
            elif existing_destinations:
                existing_destinations[0].amount = float(_money(updates["destination_amount"]))
            else:
                replacement_destinations = [
                    TransactionDestination(
                        bank_account_id=updates.get(
                            "bank_account_destination_id",
                            entity.bank_account_destination_id,
                        ),
                        amount=float(_money(updates["destination_amount"])),
                        position=0,
                    )
                ]

        for attr, value in updates.items():
            setattr(entity, attr, value)
        if replacement_destinations is not None:
            entity.destinations = _merge_destination_entities(
                list(entity.destinations or []), replacement_destinations
            )

        sync_transaction_status_from_checklist(entity)

        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity, load_noload_relations=["user", "destinations"])
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

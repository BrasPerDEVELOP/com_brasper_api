# app/modules/metrics/infrastructure/repository.py
"""Repositorio SQL de métricas por periodo (día / semana / mes).

Agrupa transacciones por periodo (vía ``date_trunc(<granularity>, created_at)``
de PostgreSQL) para un corredor (par de monedas), con filtros opcionales de
estado y asesor.

Semántica de los campos (documentada para que negocio pueda ajustarla):
- ``envios_count``          nº de transacciones del periodo.
- ``envios_volume_origin``  suma de ``origin_amount`` (volumen en moneda origen).
- ``caja_origin_in``        suma de lo que entra a caja en origen: ``total_to_send``
                            si existe, si no ``origin_amount``.
- ``caja_destination_out``  suma de ``destination_amount`` (entregado en destino).
- ``facturado_destino``     igual que ``caja_destination_out`` (facturado en destino).
- ``caja_diferencia``       ``caja_origin_in - envios_volume_origin`` (mismo tipo de moneda).
- ``clientes_nuevos``       clientes cuya PRIMERA transacción del corredor cae en ese
                            periodo (adquisición), sobre todo el histórico del corredor.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coin.domain.enums import Currency
from app.modules.coin.domain.models import TaxRate
from app.modules.metrics.interfaces.metrics_repository import MetricsRepositoryInterface
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.domain.models import Tag, Transaction, TransactionTag
from app.modules.users.domain.models import User

# Granularidades soportadas (valor aceptado por date_trunc de PostgreSQL).
VALID_GRANULARITIES = ("day", "week", "month")
SUPPORTED_CORRIDORS = {
    "PEN_BRL": (Currency.pen, Currency.brl),
    "BRL_PEN": (Currency.brl, Currency.pen),
    "USD_BRL": (Currency.usd, Currency.brl),
    "BRL_USD": (Currency.brl, Currency.usd),
}
SUPPORTED_CURRENCIES = tuple(currency.value for currency in Currency)


def _empty_currency_map() -> dict[str, float]:
    return {currency: 0.0 for currency in SUPPORTED_CURRENCIES}


def _align(d: date, granularity: str) -> date:
    """Inicio del periodo que contiene ``d`` según la granularidad.

    Coincide con lo que devuelve ``date_trunc(granularity, ...)``:
    día → mismo día; semana → lunes; mes → día 1.
    """
    if granularity == "week":
        return d - timedelta(days=d.weekday())
    if granularity == "month":
        return d.replace(day=1)
    return d


def _advance(d: date, granularity: str) -> date:
    """Siguiente inicio de periodo tras ``d``."""
    if granularity == "week":
        return d + timedelta(days=7)
    if granularity == "month":
        return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    return d + timedelta(days=1)


def _status_condition(value: str):
    """Traduce un estado "de presentación" a la condición SQL equivalente.

    Espeja la lógica del frontend/transacciones: ``verified`` incluye ``checked`` y
    ``verification`` con ``checked=True``. Devuelve ``None`` si no se reconoce.
    """
    v = (value or "").strip().lower()
    if not v:
        return None
    if v in ("verified", "checked"):
        return or_(
            Transaction.status.in_([TransactionStatus.verified, TransactionStatus.checked]),
            and_(Transaction.status == TransactionStatus.verification, Transaction.checked.is_(True)),
        )
    if v == "verification":
        return and_(
            Transaction.status == TransactionStatus.verification,
            Transaction.checked.is_(False),
        )
    try:
        return Transaction.status == TransactionStatus(v)
    except ValueError:
        return None


class SQLAlchemyMetricsRepository(MetricsRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.session = db

    def _scope_conditions(
        self,
        *,
        origin_currency: Currency,
        destination_currency: Currency,
        status: Optional[str],
        agent_id: Optional[UUID],
    ) -> list:
        """Condiciones de corredor/estado/asesor (sin acotar por fecha)."""
        conditions = [
            Transaction.deleted.is_(False),
            TaxRate.coin_a == origin_currency,
            TaxRate.coin_b == destination_currency,
        ]
        if status:
            cond = _status_condition(status)
            if cond is not None:
                conditions.append(cond)
        if agent_id is not None:
            conditions.append(Transaction.agent_id == agent_id)
        return conditions

    def _overview_scope_conditions(
        self,
        *,
        corridor: str,
        status: Optional[str],
        agent_id: Optional[UUID],
        tag_ids: Optional[list[UUID]],
    ) -> list:
        conditions = [Transaction.deleted.is_(False)]
        if corridor == "all":
            conditions.append(
                or_(
                    *[
                        and_(TaxRate.coin_a == origin, TaxRate.coin_b == destination)
                        for origin, destination in SUPPORTED_CORRIDORS.values()
                    ]
                )
            )
        else:
            origin, destination = SUPPORTED_CORRIDORS[corridor]
            conditions.extend(
                [TaxRate.coin_a == origin, TaxRate.coin_b == destination]
            )
        if status:
            condition = _status_condition(status)
            if condition is not None:
                conditions.append(condition)
        if agent_id is not None:
            conditions.append(Transaction.agent_id == agent_id)
        if tag_ids:
            tagged_transaction_ids = select(TransactionTag.transaction_id).where(
                TransactionTag.deleted.is_(False),
                TransactionTag.tag_id.in_(tag_ids),
            )
            conditions.append(Transaction.id.in_(tagged_transaction_ids))
        return conditions

    async def overview_metrics(
        self,
        *,
        corridor: str,
        date_from: date,
        date_to: date,
        granularity: str = "week",
        status: Optional[str] = None,
        agent_id: Optional[UUID] = None,
        tag_ids: Optional[list[UUID]] = None,
    ) -> dict:
        """Agregados del panel, calculados sobre un único universo filtrado."""
        gran = granularity if granularity in VALID_GRANULARITIES else "week"
        series_start = _align(date_from, gran)
        lower = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        upper = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        period = func.date_trunc(gran, Transaction.created_at)
        scope = self._overview_scope_conditions(
            corridor=corridor,
            status=status,
            agent_id=agent_id,
            tag_ids=tag_ids,
        )
        in_range = [Transaction.created_at >= lower, Transaction.created_at < upper]

        series_stmt = (
            select(
                period.label("period"),
                TaxRate.coin_a.label("currency"),
                func.count(Transaction.id).label("envios_count"),
                func.coalesce(func.sum(Transaction.origin_amount), 0).label("volume_origin"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .where(*scope, *in_range)
            .group_by(period, TaxRate.coin_a)
        )
        series_rows = (await self.session.execute(series_stmt)).all()
        series_by_period: dict[date, dict] = {}
        for row in series_rows:
            key = row.period.date() if hasattr(row.period, "date") else row.period
            point = series_by_period.setdefault(
                key,
                {
                    "envios_count": 0,
                    "clientes_nuevos": 0,
                    "volume_origin": _empty_currency_map(),
                },
            )
            currency = row.currency.value if hasattr(row.currency, "value") else str(row.currency)
            point["envios_count"] += int(row.envios_count or 0)
            point["volume_origin"][currency] += float(row.volume_origin or 0)

        new_clients_stmt = (
            select(
                period.label("period"),
                func.count(func.distinct(Transaction.id)).label("clientes_nuevos"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .join(TransactionTag, TransactionTag.transaction_id == Transaction.id)
            .join(Tag, Tag.id == TransactionTag.tag_id)
            .where(
                *scope,
                *in_range,
                TransactionTag.deleted.is_(False),
                Tag.deleted.is_(False),
                Tag.counts_as_new_client.is_(True),
            )
            .group_by(period)
        )
        for row in (await self.session.execute(new_clients_stmt)).all():
            key = row.period.date() if hasattr(row.period, "date") else row.period
            point = series_by_period.setdefault(
                key,
                {
                    "envios_count": 0,
                    "clientes_nuevos": 0,
                    "volume_origin": _empty_currency_map(),
                },
            )
            point["clientes_nuevos"] = int(row.clientes_nuevos or 0)

        status_stmt = (
            select(
                Transaction.status,
                Transaction.checked,
                func.count(Transaction.id).label("count"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .where(*scope, *in_range)
            .group_by(Transaction.status, Transaction.checked)
        )
        status_counts: dict[str, int] = {}
        for row in (await self.session.execute(status_stmt)).all():
            raw_status = row.status.value if hasattr(row.status, "value") else str(row.status)
            if raw_status in ("verified", "checked") or (
                raw_status == "verification" and bool(row.checked)
            ):
                key = "verified"
            elif raw_status in ("verification", "pending"):
                key = "verification"
            else:
                key = raw_status
            status_counts[key] = status_counts.get(key, 0) + int(row.count or 0)

        tag_stmt = (
            select(
                Tag.id,
                Tag.label,
                Tag.color,
                Tag.active,
                func.count(func.distinct(Transaction.id)).label("count"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .join(TransactionTag, TransactionTag.transaction_id == Transaction.id)
            .join(Tag, Tag.id == TransactionTag.tag_id)
            .where(
                *scope,
                *in_range,
                TransactionTag.deleted.is_(False),
                Tag.deleted.is_(False),
            )
            .group_by(Tag.id, Tag.label, Tag.color, Tag.active)
            .order_by(func.count(func.distinct(Transaction.id)).desc(), Tag.label)
        )
        tag_rows = (await self.session.execute(tag_stmt)).all()

        agent = aliased(User)
        agent_stmt = (
            select(
                Transaction.agent_id,
                agent.names,
                agent.lastnames,
                agent.email,
                TaxRate.coin_a.label("currency"),
                func.count(Transaction.id).label("envios_count"),
                func.coalesce(func.sum(Transaction.origin_amount), 0).label("volume_origin"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .outerjoin(agent, agent.id == Transaction.agent_id)
            .where(*scope, *in_range)
            .group_by(
                Transaction.agent_id,
                agent.names,
                agent.lastnames,
                agent.email,
                TaxRate.coin_a,
            )
        )
        agents: dict[Optional[UUID], dict] = {}
        for row in (await self.session.execute(agent_stmt)).all():
            name = " ".join(part.strip() for part in (row.names, row.lastnames) if part and part.strip())
            item = agents.setdefault(
                row.agent_id,
                {
                    "agent_id": str(row.agent_id) if row.agent_id else None,
                    "agent_name": name or row.email or "Sin asesor",
                    "envios_count": 0,
                    "volume_origin": _empty_currency_map(),
                },
            )
            currency = row.currency.value if hasattr(row.currency, "value") else str(row.currency)
            item["envios_count"] += int(row.envios_count or 0)
            item["volume_origin"][currency] += float(row.volume_origin or 0)

        series: list[dict] = []
        totals = {
            "envios_count": 0,
            "clientes_nuevos": 0,
            "active_agents": sum(1 for key in agents if key is not None),
            "volume_origin": _empty_currency_map(),
        }
        cursor = series_start
        end = _align(date_to, gran)
        while cursor <= end:
            values = series_by_period.get(
                cursor,
                {
                    "envios_count": 0,
                    "clientes_nuevos": 0,
                    "volume_origin": _empty_currency_map(),
                },
            )
            point = {"period_start": cursor.isoformat(), **values}
            series.append(point)
            totals["envios_count"] += values["envios_count"]
            totals["clientes_nuevos"] += values["clientes_nuevos"]
            for currency, amount in values["volume_origin"].items():
                totals["volume_origin"][currency] += amount
            cursor = _advance(cursor, gran)

        origin_currency = destination_currency = None
        corridor_label = "Todos"
        if corridor != "all":
            origin, destination = SUPPORTED_CORRIDORS[corridor]
            origin_currency = origin.value
            destination_currency = destination.value
            corridor_label = f"{origin.value}→{destination.value}"

        return {
            "range": {
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "origin_currency": origin_currency,
                "destination_currency": destination_currency,
                "corridor": corridor_label,
                "granularity": gran,
            },
            "series": series,
            "totals": totals,
            "breakdown_by_status": [
                {"key": key, "count": count}
                for key, count in sorted(status_counts.items(), key=lambda item: item[1], reverse=True)
            ],
            "breakdown_by_tag": [
                {
                    "tag_id": str(row.id),
                    "label": row.label,
                    "color": row.color,
                    "active": bool(row.active),
                    "count": int(row.count or 0),
                }
                for row in tag_rows
            ],
            "breakdown_by_agent": sorted(
                agents.values(),
                key=lambda item: (-item["envios_count"], item["agent_name"]),
            ),
        }

    async def period_metrics(
        self,
        *,
        origin_currency: Currency,
        destination_currency: Currency,
        date_from: date,
        date_to: date,
        granularity: str = "week",
        status: Optional[str] = None,
        agent_id: Optional[UUID] = None,
    ) -> dict:
        gran = granularity if granularity in VALID_GRANULARITIES else "week"
        start = _align(date_from, gran)
        # Límite superior exclusivo: inicio del día siguiente a date_to.
        upper = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        lower = datetime.combine(start, time.min, tzinfo=timezone.utc)

        # Expresión de "inicio de periodo" según la granularidad.
        period = func.date_trunc(gran, Transaction.created_at)

        scope = self._scope_conditions(
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            status=status,
            agent_id=agent_id,
        )
        in_range = [Transaction.created_at >= lower, Transaction.created_at < upper]

        caja_origin_expr = func.coalesce(Transaction.total_to_send, Transaction.origin_amount)

        # Agregado principal por periodo (dentro del rango).
        agg_stmt = (
            select(
                period.label("period"),
                func.count().label("envios_count"),
                func.coalesce(func.sum(Transaction.origin_amount), 0).label("envios_volume_origin"),
                func.coalesce(func.sum(caja_origin_expr), 0).label("caja_origin_in"),
                func.coalesce(func.sum(Transaction.destination_amount), 0).label("caja_destination_out"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .where(*scope, *in_range)
            .group_by(period)
        )
        agg_rows = (await self.session.execute(agg_stmt)).all()

        by_period: dict[date, dict] = {}
        for row in agg_rows:
            key = row.period.date() if hasattr(row.period, "date") else row.period
            origin_in = float(row.caja_origin_in or 0)
            volume_origin = float(row.envios_volume_origin or 0)
            destination_out = float(row.caja_destination_out or 0)
            by_period[key] = {
                "envios_count": int(row.envios_count or 0),
                "envios_volume_origin": volume_origin,
                "caja_origin_in": origin_in,
                "caja_destination_out": destination_out,
                "caja_diferencia": origin_in - volume_origin,
                "facturado_destino": destination_out,
            }

        # Clientes nuevos: primera transacción del corredor por usuario (sin acotar
        # por fecha), agrupada por periodo; solo se muestran las que caen en el rango.
        first_tx_sq = (
            select(
                Transaction.user_id.label("user_id"),
                func.date_trunc(gran, func.min(Transaction.created_at)).label("first_period"),
            )
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .where(*scope)
            .group_by(Transaction.user_id)
            .subquery()
        )
        nuevos_stmt = select(
            first_tx_sq.c.first_period, func.count().label("nuevos")
        ).group_by(first_tx_sq.c.first_period)
        nuevos_rows = (await self.session.execute(nuevos_stmt)).all()
        nuevos_by_period: dict[date, int] = {}
        for row in nuevos_rows:
            key = row.first_period.date() if hasattr(row.first_period, "date") else row.first_period
            nuevos_by_period[key] = int(row.nuevos or 0)

        # Serie continua de periodos desde ``start`` hasta cubrir ``date_to``.
        weeks: list[dict] = []
        totals = {
            "envios_count": 0,
            "envios_volume_origin": 0.0,
            "clientes_nuevos": 0,
            "caja_origin_in": 0.0,
            "caja_destination_out": 0.0,
            "caja_diferencia": 0.0,
            "facturado_destino": 0.0,
        }
        cursor = start
        end = _align(date_to, gran)
        while cursor <= end:
            agg = by_period.get(cursor)
            nuevos = nuevos_by_period.get(cursor, 0)
            point = {
                "period_start": cursor.isoformat(),
                "envios_count": agg["envios_count"] if agg else 0,
                "envios_volume_origin": agg["envios_volume_origin"] if agg else 0.0,
                "clientes_nuevos": nuevos,
                "caja_origin_in": agg["caja_origin_in"] if agg else 0.0,
                "caja_destination_out": agg["caja_destination_out"] if agg else 0.0,
                "caja_diferencia": agg["caja_diferencia"] if agg else 0.0,
                "facturado_destino": agg["facturado_destino"] if agg else 0.0,
            }
            weeks.append(point)
            totals["envios_count"] += point["envios_count"]
            totals["envios_volume_origin"] += point["envios_volume_origin"]
            totals["clientes_nuevos"] += point["clientes_nuevos"]
            totals["caja_origin_in"] += point["caja_origin_in"]
            totals["caja_destination_out"] += point["caja_destination_out"]
            totals["caja_diferencia"] += point["caja_diferencia"]
            totals["facturado_destino"] += point["facturado_destino"]
            cursor = _advance(cursor, gran)

        return {
            "range": {
                "date_from": start.isoformat(),
                "date_to": date_to.isoformat(),
                "origin_currency": origin_currency.value,
                "destination_currency": destination_currency.value,
                "corridor": f"{origin_currency.value}→{destination_currency.value}",
                "granularity": gran,
            },
            "weeks": weeks,
            "totals": totals,
        }

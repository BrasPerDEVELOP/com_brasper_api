# app/modules/metrics/infrastructure/management_repository.py
"""Repositorio SQL del panel gerencial (agregados mensuales de un año).

Semántica (replica las hojas del Excel de gerencia):
- ``envios_count``        nº de transacciones del mes.
- ``envios_by_currency``  nº de transacciones por moneda de origen (``TaxRate.coin_a``).
- ``envios_by_company``   nº de transacciones por razón social (``Bank.company`` de la
                          cuenta de empresa ``social_reason_bank_id``; si falta, el texto
                          libre ``Transaction.company_name``; si falta, "Sin razón social").
- ``active_clients``      clientes distintos (``user_id``) con ≥1 transacción en el mes.
- ``new_clients``         clientes cuya PRIMERA transacción histórica cae en el mes.
- ``volume_origin``       suma de ``origin_amount`` por moneda de origen.
- ``commission_origin``   suma de ``commission_result`` (comisión cobrada) por moneda de origen.
- ``*_pen``               lo anterior expresado en soles con la tasa mensual de
                          ``finance.fx_month_rates`` (PEN = 1). ``None`` si falta una tasa.
- ``expenses_pen``        egresos del mes (``finance.expenses``), siempre en soles.
- ``net_pen``             ``revenue_pen - expenses_pen``.

Zona horaria: ``created_at`` se persiste como hora de Lima (ver
``app/db/configuration_hour.py``: ``now() AT TIME ZONE 'America/Lima'`` con sesión
en UTC), por eso ``date_trunc('month', created_at)`` ya corta los meses como los
ve el negocio y NO se aplica otra conversión.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coin.domain.enums import Currency
from app.modules.coin.domain.models import TaxRate
from app.modules.finance.domain.models import Expense, ExpenseCategory, FxMonthRate
from app.modules.metrics.infrastructure.repository import (
    SUPPORTED_CORRIDORS,
    _status_condition,
)
from app.modules.metrics.interfaces.management_repository import (
    ManagementRepositoryInterface,
)
from app.modules.transactions.domain.models import Bank, Transaction
from app.modules.users.domain.models import User

NO_COMPANY = "Sin razón social"
SUPPORTED_CURRENCIES = tuple(currency.value for currency in Currency)


def _empty_month(period_start: date) -> dict:
    return {
        "period_start": period_start.isoformat(),
        "envios_count": 0,
        "envios_by_currency": {c: 0 for c in SUPPORTED_CURRENCIES},
        "envios_by_company": {},
        "active_clients": 0,
        "new_clients": 0,
        "volume_origin": {c: 0.0 for c in SUPPORTED_CURRENCIES},
        "commission_origin": {c: 0.0 for c in SUPPORTED_CURRENCIES},
        "volume_pen_by_currency": {c: 0.0 for c in SUPPORTED_CURRENCIES},
        "volume_pen_total": 0.0,
        "revenue_pen": 0.0,
        "expenses_pen": 0.0,
        "net_pen": 0.0,
    }


def apply_fx(
    month: dict, year: int, month_number: int, fx: dict[tuple[int, int, str], float]
) -> list[str]:
    """Expresa volumen y comisión del mes en soles. Devuelve las monedas sin tasa."""
    missing: list[str] = []
    volume_total = 0.0
    revenue_total = 0.0
    for code in SUPPORTED_CURRENCIES:
        volume = month["volume_origin"].get(code, 0.0)
        commission = month["commission_origin"].get(code, 0.0)
        rate = 1.0 if code == "PEN" else fx.get((year, month_number, code))
        if rate is None:
            month["volume_pen_by_currency"][code] = None
            if volume > 0 or commission > 0:
                missing.append(code)
            continue
        month["volume_pen_by_currency"][code] = round(volume * rate, 2)
        volume_total += volume * rate
        revenue_total += commission * rate
    if missing:
        month["volume_pen_total"] = None
        month["revenue_pen"] = None
        month["net_pen"] = None
    else:
        month["volume_pen_total"] = round(volume_total, 2)
        month["revenue_pen"] = round(revenue_total, 2)
        month["net_pen"] = round(revenue_total - month["expenses_pen"], 2)
    return missing


def _month_key(value) -> date:
    d = value.date() if hasattr(value, "date") else value
    return d.replace(day=1)


def _currency_code(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def company_expression():
    """Razón social efectiva de la transacción (catálogo > texto libre > fallback)."""
    return func.coalesce(
        Bank.company,
        func.nullif(func.trim(Transaction.company_name), ""),
        NO_COMPANY,
    )


class SQLAlchemyManagementRepository(ManagementRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.session = db

    def _scope(
        self,
        *,
        corridor: str,
        currency: Optional[Currency],
        company: Optional[str],
        status: Optional[str],
    ) -> list:
        conditions = [Transaction.deleted.is_(False)]
        if corridor != "all":
            origin, destination = SUPPORTED_CORRIDORS[corridor]
            conditions.extend([TaxRate.coin_a == origin, TaxRate.coin_b == destination])
        if currency is not None:
            conditions.append(TaxRate.coin_a == currency)
        if company:
            conditions.append(company_expression() == company)
        if status:
            condition = _status_condition(status)
            if condition is not None:
                conditions.append(condition)
        return conditions

    def _base(self, stmt):
        """Joins comunes: tasa (moneda) y cuenta de empresa (razón social)."""
        return stmt.join(TaxRate, Transaction.tax_rate_id == TaxRate.id).outerjoin(
            Bank, Bank.id == Transaction.social_reason_bank_id
        )

    async def dashboard(
        self,
        *,
        year: int,
        corridor: str = "all",
        currency: Optional[Currency] = None,
        company: Optional[str] = None,
        status: Optional[str] = None,
        top_month: Optional[int] = None,
        top_limit: int = 15,
    ) -> dict:
        # El rango incluye diciembre del año anterior para la variación de enero.
        range_start = date(year - 1, 12, 1)
        range_end = date(year, 12, 31)
        lower = datetime.combine(range_start, time.min, tzinfo=timezone.utc)
        upper = datetime.combine(range_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        period = func.date_trunc("month", Transaction.created_at)
        scope = self._scope(corridor=corridor, currency=currency, company=company, status=status)
        in_range = [Transaction.created_at >= lower, Transaction.created_at < upper]

        months: dict[date, dict] = {
            date(year - 1, 12, 1): _empty_month(date(year - 1, 12, 1)),
            **{date(year, m, 1): _empty_month(date(year, m, 1)) for m in range(1, 13)},
        }

        # 1) Envíos y volumen por mes × moneda.
        by_currency_stmt = self._base(
            select(
                period.label("period"),
                TaxRate.coin_a.label("currency"),
                func.count(Transaction.id).label("envios_count"),
                func.coalesce(func.sum(Transaction.origin_amount), 0).label("volume_origin"),
                func.coalesce(func.sum(Transaction.commission_result), 0).label(
                    "commission_origin"
                ),
            )
        ).where(*scope, *in_range).group_by(period, TaxRate.coin_a)
        for row in (await self.session.execute(by_currency_stmt)).all():
            month = months.get(_month_key(row.period))
            if month is None:
                continue
            code = _currency_code(row.currency)
            month["envios_count"] += int(row.envios_count or 0)
            month["envios_by_currency"][code] = month["envios_by_currency"].get(code, 0) + int(
                row.envios_count or 0
            )
            month["volume_origin"][code] = month["volume_origin"].get(code, 0.0) + float(
                row.volume_origin or 0
            )
            month["commission_origin"][code] = month["commission_origin"].get(code, 0.0) + float(
                row.commission_origin or 0
            )

        # 2) Envíos por mes × razón social.
        company_expr = company_expression()
        by_company_stmt = self._base(
            select(
                period.label("period"),
                company_expr.label("company"),
                func.count(Transaction.id).label("envios_count"),
            )
        ).where(*scope, *in_range).group_by(period, company_expr)
        companies: set[str] = set()
        for row in (await self.session.execute(by_company_stmt)).all():
            month = months.get(_month_key(row.period))
            if month is None:
                continue
            name = str(row.company)
            companies.add(name)
            month["envios_by_company"][name] = month["envios_by_company"].get(name, 0) + int(
                row.envios_count or 0
            )

        # 3) Clientes activos por mes.
        active_stmt = self._base(
            select(
                period.label("period"),
                func.count(func.distinct(Transaction.user_id)).label("active_clients"),
            )
        ).where(*scope, *in_range).group_by(period)
        for row in (await self.session.execute(active_stmt)).all():
            month = months.get(_month_key(row.period))
            if month is not None:
                month["active_clients"] = int(row.active_clients or 0)

        # 4) Clientes nuevos: primera transacción histórica (dentro del universo
        #    filtrado, sin acotar por fecha) agrupada por mes.
        first_tx_sq = (
            self._base(
                select(
                    Transaction.user_id.label("user_id"),
                    func.min(Transaction.created_at).label("first_at"),
                )
            )
            .where(*scope)
            .group_by(Transaction.user_id)
            .subquery()
        )
        first_period = func.date_trunc("month", first_tx_sq.c.first_at)
        new_stmt = (
            select(first_period.label("period"), func.count().label("new_clients"))
            .where(first_tx_sq.c.first_at >= lower, first_tx_sq.c.first_at < upper)
            .group_by(first_period)
        )
        for row in (await self.session.execute(new_stmt)).all():
            month = months.get(_month_key(row.period))
            if month is not None:
                month["new_clients"] = int(row.new_clients or 0)

        # 5) Top clientes del mes seleccionado (por defecto: último mes con envíos).
        year_months = [months[date(year, m, 1)] for m in range(1, 13)]
        if top_month is None:
            with_data = [m for m in range(1, 13) if year_months[m - 1]["envios_count"] > 0]
            top_month = with_data[-1] if with_data else min(datetime.now(timezone.utc).month, 12)
        month_start = date(year, top_month, 1)
        month_end = date(year + 1, 1, 1) if top_month == 12 else date(year, top_month + 1, 1)
        top_stmt = (
            self._base(
                select(
                    Transaction.user_id,
                    User.names,
                    User.lastnames,
                    User.email,
                    func.count(Transaction.id).label("envios_count"),
                )
            )
            .join(User, User.id == Transaction.user_id)
            .where(
                *scope,
                Transaction.created_at >= datetime.combine(month_start, time.min, tzinfo=timezone.utc),
                Transaction.created_at < datetime.combine(month_end, time.min, tzinfo=timezone.utc),
            )
            .group_by(Transaction.user_id, User.names, User.lastnames, User.email)
            .order_by(func.count(Transaction.id).desc(), User.names, User.lastnames)
            .limit(max(1, top_limit))
        )
        top_items = []
        for row in (await self.session.execute(top_stmt)).all():
            name = " ".join(p.strip() for p in (row.names, row.lastnames) if p and p.strip())
            top_items.append(
                {
                    "user_id": str(row.user_id),
                    "name": name or row.email or "Sin nombre",
                    "envios_count": int(row.envios_count or 0),
                }
            )

        # 6) Soles, ingresos y egresos (finance). Los egresos no dependen de los
        #    filtros de transacciones: son gastos de la empresa.
        fx_stmt = select(FxMonthRate).where(
            FxMonthRate.deleted.is_(False), FxMonthRate.year.in_([year - 1, year])
        )
        fx: dict[tuple[int, int, str], float] = {
            (r.year, r.month, _currency_code(r.currency)): float(r.rate_to_pen)
            for r in (await self.session.execute(fx_stmt)).scalars().all()
        }
        exp_month = extract("month", Expense.expense_date)
        exp_year = extract("year", Expense.expense_date)
        expenses_stmt = (
            select(exp_year, exp_month, func.coalesce(func.sum(Expense.amount_pen), 0))
            .where(Expense.deleted.is_(False), exp_year.in_([year - 1, year]))
            .group_by(exp_year, exp_month)
        )
        for row in (await self.session.execute(expenses_stmt)).all():
            key = date(int(row[0]), int(row[1]), 1)
            if key in months:
                months[key]["expenses_pen"] = round(float(row[2] or 0), 2)
        fx_missing: list[dict] = []
        for key, month in months.items():
            for code in apply_fx(month, key.year, key.month, fx):
                if key.year == year:
                    fx_missing.append({"month": key.month, "currency": code})

        category_total = func.coalesce(func.sum(Expense.amount_pen), 0)
        by_category_stmt = (
            select(ExpenseCategory.name, category_total)
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(Expense.deleted.is_(False), exp_year == year, exp_month == top_month)
            .group_by(ExpenseCategory.name)
            .order_by(category_total.desc(), ExpenseCategory.name)
        )
        category_rows = [
            (str(r[0]), float(r[1] or 0))
            for r in (await self.session.execute(by_category_stmt)).all()
        ]
        category_sum = sum(amount for _, amount in category_rows)
        expenses_by_category = [
            {
                "category": name,
                "amount_pen": round(amount, 2),
                "share": round(amount / category_sum * 100, 1) if category_sum else 0.0,
            }
            for name, amount in category_rows
        ]

        totals = {
            "envios_count": sum(m["envios_count"] for m in year_months),
            # Activos del año = suma de activos mensuales NO es correcta (un cliente
            # repite); se calcula aparte con una consulta sobre todo el año.
            "active_clients": 0,
            "new_clients": sum(m["new_clients"] for m in year_months),
            "volume_origin": {c: 0.0 for c in SUPPORTED_CURRENCIES},
        }
        for m in year_months:
            for code, amount in m["volume_origin"].items():
                totals["volume_origin"][code] = totals["volume_origin"].get(code, 0.0) + amount
        totals["expenses_pen"] = round(sum(m["expenses_pen"] for m in year_months), 2)
        with_data = [m for m in year_months if m["envios_count"] > 0]
        if with_data and all(m["volume_pen_total"] is not None for m in with_data):
            totals["volume_pen_total"] = round(sum(m["volume_pen_total"] for m in with_data), 2)
            totals["revenue_pen"] = round(sum(m["revenue_pen"] for m in with_data), 2)
            totals["net_pen"] = round(totals["revenue_pen"] - totals["expenses_pen"], 2)
        else:
            totals["volume_pen_total"] = totals["revenue_pen"] = totals["net_pen"] = None
        year_lower = datetime.combine(date(year, 1, 1), time.min, tzinfo=timezone.utc)
        active_year_stmt = self._base(
            select(func.count(func.distinct(Transaction.user_id)))
        ).where(*scope, Transaction.created_at >= year_lower, Transaction.created_at < upper)
        totals["active_clients"] = int((await self.session.execute(active_year_stmt)).scalar() or 0)

        corridor_label = "Todos"
        if corridor != "all":
            origin, destination = SUPPORTED_CORRIDORS[corridor]
            corridor_label = f"{origin.value}→{destination.value}"

        return {
            "range": {
                "year": year,
                "date_from": date(year, 1, 1).isoformat(),
                "date_to": range_end.isoformat(),
                "corridor": corridor_label,
                "currency": currency.value if currency else None,
                "company": company or None,
                "status": status or None,
            },
            "months": year_months,
            "previous_month": months[date(year - 1, 12, 1)],
            "totals": totals,
            "companies": sorted(companies, key=lambda name: (name == NO_COMPANY, name.lower())),
            "top_clients": {"month": top_month, "items": top_items},
            "fx_missing": fx_missing,
            "expenses_by_category": expenses_by_category,
        }

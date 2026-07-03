"""  """"""Tests del ordenamiento determinista de QueryFilter (paginación estable)."""
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.modules.transactions.domain.models import Transaction
from app.shared.query_filter import QueryFilter


def _order_sql(order_by) -> str:
    qf = QueryFilter(order_by=order_by)
    stmt = qf.apply(select(Transaction), Transaction)
    full = str(stmt.compile(dialect=postgresql.dialect()))
    # Devuelve solo la cláusula ORDER BY
    return full[full.index("ORDER BY"):] if "ORDER BY" in full else ""


def test_desc_order_applies_and_adds_id_tiebreaker():
    sql = _order_sql([("created_at", "desc")])
    assert "created_at DESC" in sql
    assert "transactions.id DESC" in sql  # desempate determinista


def test_asc_order_is_respected():
    # Antes se ignoraba silenciosamente el asc; ahora debe aplicarse.
    sql = _order_sql([("created_at", "asc")])
    assert "created_at ASC" in sql
    assert "transactions.id DESC" in sql


def test_no_duplicate_tiebreaker_when_ordering_by_id():
    sql = _order_sql([("id", "asc")])
    assert sql.count("transactions.id") == 1


def test_no_order_no_tiebreaker():
    sql = _order_sql([])
    assert sql == ""

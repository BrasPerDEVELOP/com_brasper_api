"""Tests de los filtros de listado de transacciones (estado efectivo + búsqueda).

Validan el SQL generado contra el dialecto real (PostgreSQL), que es lo que
importa para el endpoint ``GET /transactions/`` con paginación de servidor.
"""
from sqlalchemy.dialects import postgresql

from app.modules.transactions.infrastructure.repository import (
    _effective_status_condition,
    _search_condition,
    _tag_ids_condition,
)


def _sql(condition) -> str:
    return str(
        condition.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_effective_status_verified_includes_checked_and_verification_checked():
    sql = _sql(_effective_status_condition("verified"))
    # verified/checked directos + verification marcada como checked
    assert "status IN ('verified', 'checked')" in sql
    assert "status = 'verification'" in sql
    assert "checked IS true" in sql


def test_effective_status_checked_is_alias_of_verified():
    assert _sql(_effective_status_condition("checked")) == _sql(
        _effective_status_condition("verified")
    )


def test_effective_status_verification_excludes_checked():
    sql = _sql(_effective_status_condition("verification"))
    assert "status = 'verification'" in sql
    assert "checked IS false" in sql


def test_effective_status_simple_states_are_equality():
    for state in ("pending", "completed", "failed"):
        sql = _sql(_effective_status_condition(state))
        assert sql == f"transaction.transactions.status = '{state}'"


def test_effective_status_unknown_returns_none():
    assert _effective_status_condition("bogus") is None
    assert _effective_status_condition("") is None
    assert _effective_status_condition(None) is None


def test_search_condition_matches_code_operation_and_id():
    sql = _sql(_search_condition("ABC"))
    # El compilador escapa `%` como `%%` al renderizar literales.
    assert "code ILIKE '%%ABC%%'" in sql
    assert "operation_number ILIKE '%%ABC%%'" in sql
    # id (UUID) se castea a texto para la búsqueda
    assert "CAST(transaction.transactions.id AS VARCHAR) ILIKE '%%ABC%%'" in sql


def test_tag_ids_condition_is_or_any_selected_tag():
    from uuid import UUID

    first = UUID("74360c1b-8101-429c-b6fd-47aa2f5ac47c")
    second = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    sql = _sql(_tag_ids_condition([first, second, first]))
    assert "transaction_tags.tag_id IN" in sql
    assert str(first) in sql
    assert str(second) in sql
    assert "transaction.transactions.id IN" in sql


def test_tag_ids_condition_empty_returns_none():
    assert _tag_ids_condition([]) is None
    assert _tag_ids_condition(()) is None


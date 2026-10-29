from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.users.application.user_metrics import summarize_user_metrics, GetUserMetricsUseCase
from app.modules.users.infrastructure.user_metrics_repository import UserMetricsRepository


def row(country="brasil", phone_code="+55", area="11", name="São Paulo", total=1, enabled=1):
    return dict(country=country, phone_code=phone_code, area=area, name=name, total=total, enabled=enabled)


def test_groups_same_ddd_and_keeps_missing_users_in_denominator():
    result = summarize_user_metrics([
        row(total=2, enabled=2), row(name="São Paulo — região metropolitana"),
        row(area="", name="", enabled=0), row(area="00", name="Inválido"),
        row(country="perú", phone_code="+51", area="01"),
    ])
    assert result["total"] == 6
    assert result["active"] == 5
    assert result["brazil"] == 5
    assert result["brazil_located"] == 3
    assert result["brazil_missing_area"] == 2
    assert len(result["areas"]) == 1
    assert result["areas"][0]["count"] == 3
    assert result["areas"][0]["percentage"] == 60
    assert "São Paulo" in result["areas"][0]["name"]


def test_brazil_aliases_and_phone_fallback_do_not_override_explicit_country():
    result = summarize_user_metrics([
        row(country="brazil"), row(country="br"), row(country="bra"),
        row(country="", phone_code="55", area="21", name=""),
        row(country="perú", phone_code="+55"),
    ])
    assert result["brazil"] == 4
    assert result["areas"][1]["name"] == "Área DDD 21"
    assert sum(item["count"] for item in result["countries"]) == 5


def test_empty_metrics_have_no_division_by_zero():
    result = summarize_user_metrics([])
    assert result["total"] == result["brazil"] == result["brazil_missing_area"] == 0
    assert result["areas"] == result["countries"] == []


@pytest.mark.asyncio
async def test_repository_aggregates_in_sql_and_excludes_deleted():
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session.execute.return_value = result
    await UserMetricsRepository(session).grouped(role="client")
    compiled = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "GROUP BY" in sql and "count(" in sql
    assert "deleted IS false" in sql
    assert "client" in compiled.params.values()
    assert "document_number" not in sql and '"user"."user".phone,' not in sql


@pytest.mark.asyncio
async def test_use_case_passes_role_filter():
    repo = AsyncMock()
    repo.grouped.return_value = [row(total=3)]
    assert (await GetUserMetricsUseCase(repo).execute(role="client"))["total"] == 3
    repo.grouped.assert_awaited_once_with(role="client")


def test_metrics_route_requires_users_view():
    import inspect
    from app.modules.users.adapters.router.user_routes import router
    route = next(route for route in router.routes if route.path.rstrip("/") == "/user/metrics")
    assert any(inspect.getclosurevars(dependency.call).nonlocals.get("permission") == "users.view"
               for dependency in route.dependant.dependencies)
    from app.main import app
    paths = app.openapi()["paths"]
    assert "/user/metrics" in paths or "/user/metrics/" in paths

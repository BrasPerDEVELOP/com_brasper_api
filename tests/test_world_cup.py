from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.world_cup.provider import FootballDataProvider, _normalize_status
from app.modules.world_cup.schemas import MatchSelection, PublicLiveResponse
from app.modules.world_cup.enums import ExchangeRateScope
from app.modules.world_cup.service import MATCH_MAX_DURATION, WorldCupService, estimate_match_end


def test_football_data_status_mapping_covers_coupon_transitions():
    assert _normalize_status("IN_PLAY") == "LIVE"
    assert _normalize_status("PAUSED") == "LIVE"
    assert _normalize_status("FINISHED") == "FINISHED"
    assert _normalize_status("POSTPONED") == "POSTPONED"


def test_football_data_fixture_mapping():
    item = {
        "id": 42,
        "utcDate": "2026-06-17T22:00:00Z",
        "status": "IN_PLAY",
        "stage": "GROUP_STAGE",
        "group": "GROUP_A",
        "homeTeam": {"id": 1, "name": "Peru", "tla": "PER"},
        "awayTeam": {"id": 2, "name": "Brazil", "tla": "BRA"},
        "score": {"fullTime": {"home": 1, "away": 0}},
    }
    match = FootballDataProvider._map(item)
    assert match is not None
    assert match.provider_id == "football-data:42"
    assert match.status == "LIVE"
    assert match.stage == "GROUP_A"
    assert match.home_score == 1
    assert match.starts_at == datetime(2026, 6, 17, 22, tzinfo=timezone.utc)


def test_coupon_code_template_is_sanitized():
    match = SimpleNamespace(home_team_code="PER", away_team_code="BRA", home_team="Peru", away_team="Brazil", starts_at=datetime(2026, 6, 17, tzinfo=timezone.utc))
    assert WorldCupService._render_code("Mundial {HOME} / {AWAY} {DATE}", match) == "MUNDIAL-PER-BRA-0617"


def test_match_selection_accepts_per_match_coupon_rules():
    selection = MatchSelection(
        selected=True,
        discount_percentage=20,
        max_uses=50,
    )
    assert selection.discount_percentage == 20
    assert selection.max_uses == 50
    assert set(selection.model_dump()) == {"selected", "discount_percentage", "max_uses", "exchange_rate_scope"}


def test_match_selection_rejects_invalid_discount():
    with pytest.raises(ValidationError):
        MatchSelection(selected=True, discount_percentage=101)


def test_match_selection_accepts_optional_exchange_rate_scope():
    selection = MatchSelection(selected=True, exchange_rate_scope="USD_BRL")
    assert selection.exchange_rate_scope is ExchangeRateScope.usd_brl
    assert "exchange_rate_scope" in selection.model_dump()


def test_match_selection_exchange_rate_scope_defaults_to_none():
    selection = MatchSelection(selected=True)
    assert selection.exchange_rate_scope is None


def test_estimate_match_end_is_four_hour_hard_window():
    starts = datetime(2026, 6, 17, 22, 0, tzinfo=timezone.utc)
    assert estimate_match_end(starts) == starts + MATCH_MAX_DURATION
    assert estimate_match_end(starts) == datetime(2026, 6, 18, 2, 0, tzinfo=timezone.utc)


def test_public_live_response_omits_internal_fields():
    payload = {
        "live": [{
            "home_team": "Peru", "away_team": "Brazil",
            "home_team_code": "PER", "away_team_code": "BRA",
            "stage": "GROUP_A", "starts_at": datetime(2026, 6, 17, 22, tzinfo=timezone.utc),
            "status": "LIVE",
            "coupon": {"code": "X", "discount_percentage": 10, "exchange_rate_scope": "BRL_PEN",
                       "ends_at_estimate": datetime(2026, 6, 18, 2, tzinfo=timezone.utc)},
        }],
        "next": None,
    }
    parsed = PublicLiveResponse.model_validate(payload)
    dumped = parsed.model_dump()
    coupon_fields = set(dumped["live"][0]["coupon"])
    assert coupon_fields == {"code", "discount_percentage", "exchange_rate_scope", "ends_at_estimate"}
    match_fields = set(dumped["live"][0])
    assert "raw_data" not in match_fields and "notification_emails" not in match_fields
    assert match_fields == {"home_team", "away_team", "home_team_code", "away_team_code", "stage", "starts_at", "status", "coupon"}


@pytest.mark.parametrize("scope", list(ExchangeRateScope))
def test_exchange_rate_scope_round_trip(scope):
    origin, destination = scope.currencies
    assert ExchangeRateScope.from_currencies(origin, destination) is scope


def test_all_exchange_rates_supports_campaign_storage_value():
    assert ExchangeRateScope.from_currencies("ALL", "ALL") is ExchangeRateScope.all

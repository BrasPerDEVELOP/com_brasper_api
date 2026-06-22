from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ProviderMatch:
    provider_id: str
    stage: str | None
    home_team: str
    away_team: str
    home_team_code: str | None
    away_team_code: str | None
    home_score: int | None
    away_score: int | None
    starts_at: datetime
    status: str
    raw_data: dict


class SportsProvider(Protocol):
    async def fixtures(self, start: datetime, end: datetime) -> list[ProviderMatch]: ...
    async def live(self) -> list[ProviderMatch]: ...


class FootballDataProvider:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, token: str, competition_code: str = "WC"):
        self.token = token.strip()
        self.competition_code = competition_code.strip().upper() or "WC"

    async def fixtures(self, start: datetime, end: datetime) -> list[ProviderMatch]:
        return await self._request({
            "dateFrom": start.date().isoformat(),
            "dateTo": end.date().isoformat(),
        })

    async def live(self) -> list[ProviderMatch]:
        now = datetime.now(timezone.utc)
        return await self.fixtures(now - timedelta(days=1), now + timedelta(days=1))

    async def _request(self, params: dict[str, str]) -> list[ProviderMatch]:
        if not self.token:
            raise RuntimeError("football-data.org no está configurado")
        headers = {"X-Auth-Token": self.token}
        path = f"/competitions/{self.competition_code}/matches"
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(f"{self.BASE_URL}{path}", params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        return [mapped for item in payload.get("matches", []) if (mapped := self._map(item))]

    @staticmethod
    def _map(item: dict) -> ProviderMatch | None:
        home = item.get("homeTeam") or {}
        away = item.get("awayTeam") or {}
        if item.get("id") is None or not item.get("utcDate") or not home or not away:
            return None
        start_text = str(item["utcDate"]).replace("Z", "+00:00")
        starts_at = datetime.fromisoformat(start_text)
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        score_container = item.get("score") or {}
        score = score_container.get("fullTime") or score_container.get("regularTime") or {}
        return ProviderMatch(
            provider_id=f"football-data:{item['id']}",
            stage=str(item.get("group") or item.get("stage") or "") or None,
            home_team=str(home.get("name") or home.get("shortName") or "Local"),
            away_team=str(away.get("name") or away.get("shortName") or "Visitante"),
            home_team_code=home.get("tla"),
            away_team_code=away.get("tla"),
            home_score=_as_int(score.get("home")),
            away_score=_as_int(score.get("away")),
            starts_at=starts_at.astimezone(timezone.utc),
            status=_normalize_status(str(item.get("status") or "")),
            raw_data=item,
        )


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_status(value: str) -> str:
    value = value.upper()
    if value in {"LIVE", "INPLAY", "IN_PLAY", "PAUSED", "1ST", "2ND", "HT", "ET", "PEN_LIVE"}:
        return "LIVE"
    if value in {"FT", "AET", "FT_PEN", "FINISHED", "ENDED"}:
        return "FINISHED"
    if value in {"POSTP", "POSTPONED", "SUSPENDED"}:
        return "POSTPONED"
    if value in {"CANC", "CANCELLED", "ABAN", "ABANDONED"}:
        return "CANCELLED"
    return "SCHEDULED"

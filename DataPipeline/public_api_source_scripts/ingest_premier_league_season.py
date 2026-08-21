"""Ingest Premier League season data from football-data.org.

Defaults to the previous season and writes a small local dataset that can be
used for downstream analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq

from DataPipeline.configs.config import (
    FOOTBALL_DATA_TOKEN,
    INGEST_COMPETITION,
    INGEST_OUTPUT_DIR,
    INGEST_SEASONS,
)


BASE_URL = "https://api.football-data.org/v4"


@dataclass(frozen=True)
class SeasonBundle:
    season: int
    output_dir: Path
    raw_dir: Path
    parquet_dir: Path


def fetch_json(path: str, token: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(
        url,
        headers={
            "X-Auth-Token": token,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def build_bundle(base_dir: Path, season: int) -> SeasonBundle:
    output_dir = base_dir / "data" / "raw" / "premier_league" / f"season_{season}"
    raw_dir = output_dir / "raw"
    parquet_dir = output_dir / "parquet"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    return SeasonBundle(season=season, output_dir=output_dir, raw_dir=raw_dir, parquet_dir=parquet_dir)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def extract_teams(teams_payload: dict[str, Any]) -> list[dict[str, Any]]:
    teams = teams_payload.get("teams", [])
    return [
        {
            "id": team.get("id"),
            "name": team.get("name"),
            "shortName": team.get("shortName"),
            "tla": team.get("tla"),
            "venue": team.get("venue"),
            "website": team.get("website"),
            "clubColors": team.get("clubColors"),
            "founded": team.get("founded"),
            "coach": team.get("coach", {}).get("name"),
        }
        for team in teams
    ]


def extract_squad(teams_payload: dict[str, Any]) -> list[dict[str, Any]]:
    squad_rows = []
    for team in teams_payload.get("teams", []):
        for player in team.get("squad", []):
            squad_rows.append(
                {
                    "team_id": team.get("id"),
                    "team": team.get("name"),
                    "player_id": player.get("id"),
                    "player": player.get("name"),
                    "position": player.get("position"),
                    "dateOfBirth": player.get("dateOfBirth"),
                    "nationality": player.get("nationality"),
                }
            )
    return squad_rows


def extract_standings(standings_payload: dict[str, Any]) -> list[dict[str, Any]]:
    standings = standings_payload.get("standings", [])
    table = standings[0].get("table", []) if standings else []
    return [
        {
            "position": item.get("position"),
            "team_id": item.get("team", {}).get("id"),
            "team": item.get("team", {}).get("name"),
            "playedGames": item.get("playedGames"),
            "won": item.get("won"),
            "draw": item.get("draw"),
            "lost": item.get("lost"),
            "points": item.get("points"),
            "goalsFor": item.get("goalsFor"),
            "goalsAgainst": item.get("goalsAgainst"),
            "goalDifference": item.get("goalDifference"),
        }
        for item in table
    ]


def extract_matches(matches_payload: dict[str, Any]) -> list[dict[str, Any]]:
    matches = matches_payload.get("matches", [])
    return [
        {
            "id": item.get("id"),
            "utcDate": item.get("utcDate"),
            "status": item.get("status"),
            "matchday": item.get("matchday"),
            "homeTeam_id": item.get("homeTeam", {}).get("id"),
            "homeTeam": item.get("homeTeam", {}).get("name"),
            "awayTeam_id": item.get("awayTeam", {}).get("id"),
            "awayTeam": item.get("awayTeam", {}).get("name"),
            "homeScore": item.get("score", {}).get("fullTime", {}).get("home"),
            "awayScore": item.get("score", {}).get("fullTime", {}).get("away"),
            "winner": item.get("score", {}).get("winner"),
        }
        for item in matches
    ]


def extract_scorers(scorers_payload: dict[str, Any]) -> list[dict[str, Any]]:
    scorers = scorers_payload.get("scorers", [])
    return [
        {
            "player_id": item.get("player", {}).get("id"),
            "player": item.get("player", {}).get("name"),
            "team_id": item.get("team", {}).get("id"),
            "team": item.get("team", {}).get("name"),
            "goals": item.get("goals"),
            "assists": item.get("assists"),
            "penalties": item.get("penalties"),
        }
        for item in scorers
    ]


def ingest_season(token: str, competition_code: str, season: int, base_dir: Path) -> SeasonBundle:
    bundle = build_bundle(base_dir, season)
    params = {"season": str(season)}

    competition = fetch_json(f"/competitions/{competition_code}", token, params)
    standings = fetch_json(f"/competitions/{competition_code}/standings", token, params)
    matches = fetch_json(f"/competitions/{competition_code}/matches", token, params)
    teams = fetch_json(f"/competitions/{competition_code}/teams", token, params)
    scorers = fetch_json(f"/competitions/{competition_code}/scorers", token, params)

    write_json(bundle.raw_dir / "competition.json", competition)
    write_json(bundle.raw_dir / "standings.json", standings)
    write_json(bundle.raw_dir / "matches.json", matches)
    write_json(bundle.raw_dir / "teams.json", teams)
    write_json(bundle.raw_dir / "scorers.json", scorers)

    write_parquet(bundle.parquet_dir / "teams.parquet", extract_teams(teams))
    write_parquet(bundle.parquet_dir / "squad.parquet", extract_squad(teams))
    write_parquet(bundle.parquet_dir / "standings.parquet", extract_standings(standings))
    write_parquet(bundle.parquet_dir / "matches.parquet", extract_matches(matches))
    write_parquet(bundle.parquet_dir / "scorers.parquet", extract_scorers(scorers))

    return bundle


def main() -> int:
    token = FOOTBALL_DATA_TOKEN
    if not token:
        raise SystemExit("Missing API token. Set FOOTBALL_DATA_TOKEN or update DataPipeline/configs/config.ini.")

    try:
        bundles = [ingest_season(token, INGEST_COMPETITION, season, INGEST_OUTPUT_DIR) for season in INGEST_SEASONS]
    except HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace").strip()
        raise SystemExit(f"HTTP error while calling the API: {error.code} {error.reason}. Response: {response_body}") from error
    except URLError as error:
        raise SystemExit(f"Network error while calling the API: {error.reason}") from error

    for bundle in bundles:
        print(f"Saved {INGEST_COMPETITION} season {bundle.season} data to {bundle.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
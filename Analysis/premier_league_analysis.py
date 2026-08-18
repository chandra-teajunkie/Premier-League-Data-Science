# %% Load data
from pathlib import Path

import pandas as pd
import plotly.express as px

from DataPipeline.configs.config import INGEST_OUTPUT_DIR, INGEST_SEASONS


SEASON = INGEST_SEASONS[0]
DATA_DIR = Path(INGEST_OUTPUT_DIR) / "data" / "raw" / "premier_league" / f"season_{SEASON}" / "parquet"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

teams = pd.read_parquet(DATA_DIR / "teams.parquet")
standings = pd.read_parquet(DATA_DIR / "standings.parquet")
matches = pd.read_parquet(DATA_DIR / "matches.parquet")
scorers = pd.read_parquet(DATA_DIR / "scorers.parquet")

print(f"Premier League {SEASON}/{str(SEASON + 1)[-2:]}")
print({"teams": teams.shape, "standings": standings.shape, "matches": matches.shape, "scorers": scorers.shape})

# %% Validate and clean data
required_columns = {
    "teams": {"id", "name"},
    "standings": {"position", "team", "points", "goalDifference"},
    "matches": {"id", "utcDate", "homeTeam", "awayTeam", "homeScore", "awayScore"},
    "scorers": {"player", "team", "goals"},
}

for table_name, columns in required_columns.items():
    missing_columns = columns - set(globals()[table_name].columns)
    if missing_columns:
        raise ValueError(f"{table_name} is missing columns: {sorted(missing_columns)}")

matches["utcDate"] = pd.to_datetime(matches["utcDate"], utc=True)
for column in ["homeScore", "awayScore", "matchday"]:
    matches[column] = pd.to_numeric(matches[column], errors="coerce")
for column in ["position", "points", "goalDifference", "playedGames", "won", "draw", "lost"]:
    if column in standings:
        standings[column] = pd.to_numeric(standings[column], errors="coerce")
scorers["goals"] = pd.to_numeric(scorers["goals"], errors="coerce").fillna(0)

completed_matches = matches[
    matches["status"].eq("FINISHED")
    & matches["homeScore"].notna()
    & matches["awayScore"].notna()
].copy()

# %% Data quality
quality_report = pd.DataFrame(
    {
        "table": ["teams", "standings", "matches", "scorers"],
        "rows": [len(teams), len(standings), len(matches), len(scorers)],
        "duplicate_rows": [teams.duplicated().sum(), standings.duplicated().sum(), matches.duplicated().sum(), scorers.duplicated().sum()],
        "missing_cells": [teams.isna().sum().sum(), standings.isna().sum().sum(), matches.isna().sum().sum(), scorers.isna().sum().sum()],
    }
)

print(quality_report)
print(f"Completed matches: {len(completed_matches)}")

# %% Match metrics
completed_matches["total_goals"] = completed_matches["homeScore"] + completed_matches["awayScore"]
completed_matches["home_points"] = (
    completed_matches["homeScore"].gt(completed_matches["awayScore"]).astype(int) * 3
    + completed_matches["homeScore"].eq(completed_matches["awayScore"]).astype(int)
)
completed_matches["away_points"] = (
    completed_matches["awayScore"].gt(completed_matches["homeScore"]).astype(int) * 3
    + completed_matches["homeScore"].eq(completed_matches["awayScore"]).astype(int)
)

print(completed_matches[["utcDate", "homeTeam", "awayTeam", "homeScore", "awayScore", "total_goals"]].head())

# %% Team performance
home_summary = completed_matches.groupby("homeTeam").agg(
    home_played=("id", "count"),
    home_points=("home_points", "sum"),
    home_goals_for=("homeScore", "sum"),
    home_goals_against=("awayScore", "sum"),
)
away_summary = completed_matches.groupby("awayTeam").agg(
    away_played=("id", "count"),
    away_points=("away_points", "sum"),
    away_goals_for=("awayScore", "sum"),
    away_goals_against=("homeScore", "sum"),
)

team_summary = home_summary.join(away_summary, how="outer").fillna(0).reset_index(names="team")
team_summary["played"] = team_summary["home_played"] + team_summary["away_played"]
team_summary["points"] = team_summary["home_points"] + team_summary["away_points"]
team_summary["goals_for"] = team_summary["home_goals_for"] + team_summary["away_goals_for"]
team_summary["goals_against"] = team_summary["home_goals_against"] + team_summary["away_goals_against"]
team_summary["goal_difference"] = team_summary["goals_for"] - team_summary["goals_against"]
team_summary["points_per_game"] = team_summary["points"] / team_summary["played"]
team_summary = team_summary.sort_values(["points", "goal_difference"], ascending=False)

print(team_summary[["team", "played", "points", "goals_for", "goals_against", "goal_difference", "points_per_game"]])

# %% Recent form
home_results = completed_matches[["utcDate", "homeTeam", "home_points"]].rename(columns={"homeTeam": "team", "home_points": "points"})
away_results = completed_matches[["utcDate", "awayTeam", "away_points"]].rename(columns={"awayTeam": "team", "away_points": "points"})
long_results = pd.concat([home_results, away_results], ignore_index=True).sort_values("utcDate")
long_results["result"] = long_results["points"].map({3: "W", 1: "D", 0: "L"})
long_results["form_points"] = long_results.groupby("team")["points"].transform(lambda values: values.rolling(5, min_periods=1).sum())
latest_form = long_results.groupby("team", as_index=False).tail(1).sort_values("form_points", ascending=False)
print(latest_form[["team", "result", "form_points"]])

# %% Scorers and descriptive statistics
top_scorers = scorers.sort_values(["goals", "assists"], ascending=False).head(10)
print(top_scorers)
print(completed_matches[["homeScore", "awayScore", "total_goals"]].describe())
print(standings[["position", "points", "goalDifference", "goalsFor", "goalsAgainst"]].corr())

# %% Interactive Plotly diagnostics
monthly_goals = completed_matches.set_index("utcDate").resample("MS")["total_goals"].mean().rename("goals_per_match").reset_index()

points_figure = px.bar(
    team_summary.sort_values("points"),
    x="points",
    y="team",
    orientation="h",
    color="points",
    color_continuous_scale="Blues",
    hover_data=["played", "goals_for", "goals_against", "goal_difference", "points_per_game"],
    title=f"Premier League {SEASON}/{str(SEASON + 1)[-2:]} points",
)
points_figure.show()

scorers_figure = px.bar(
    top_scorers.sort_values("goals"),
    x="goals",
    y="player",
    orientation="h",
    color="team",
    hover_data=["assists", "penalties"],
    title="Top scorers",
)
scorers_figure.show()

goals_figure = px.line(
    monthly_goals,
    x="utcDate",
    y="goals_per_match",
    markers=True,
    title="Average goals per match by month",
    labels={"utcDate": "Month", "goals_per_match": "Goals per match"},
)
goals_figure.show()

home_away_figure = px.scatter(
    team_summary,
    x="home_points",
    y="away_points",
    text="team",
    size="points",
    color="goal_difference",
    color_continuous_scale="RdYlGn",
    hover_data=["points", "points_per_game", "goals_for", "goals_against"],
    title="Home points versus away points",
    labels={"home_points": "Home points", "away_points": "Away points"},
)
home_away_figure.update_traces(textposition="top center")
home_away_figure.show()

# %% Export analysis outputs
quality_report.to_csv(RESULTS_DIR / f"season_{SEASON}_quality_report.csv", index=False)
team_summary.to_parquet(RESULTS_DIR / f"season_{SEASON}_team_summary.parquet", index=False)
latest_form.to_parquet(RESULTS_DIR / f"season_{SEASON}_latest_form.parquet", index=False)
top_scorers.to_parquet(RESULTS_DIR / f"season_{SEASON}_top_scorers.parquet", index=False)
monthly_goals.to_csv(RESULTS_DIR / f"season_{SEASON}_monthly_goals.csv")

print(f"Analysis outputs written to {RESULTS_DIR}")

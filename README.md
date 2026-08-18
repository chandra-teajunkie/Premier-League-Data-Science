# Premier-League-Data-Science
Data Science Pipeline and Analysis for Premier League

## Season ingestion pipeline

To pull a reusable dataset for analysis, run the season ingestion script. It reads the competition and season settings from `DataPipeline/configs/config.ini` and writes raw JSON plus Parquet tables under `data/raw/premier_league/season_<year>/`.

```bash
./.venv/bin/python DataPipeline/public_api_source_scripts/ingest_premier_league_season.py
```

To change the competition or ingest multiple seasons, edit `DataPipeline/configs/config.ini`:

```ini
[ingestion]
competition = PL
seasons = 2025
# seasons = 2025,2024
```

The current ingestion captures competition metadata, teams, standings, matches, and top scorers. That is enough to start a first notebook for team-level and season-level analysis.

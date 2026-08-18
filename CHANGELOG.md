# Changelog

## Unreleased

### Added
- Premier League ingestion pipeline for season-level data collection from football-data.org.
- Shared repo config under `DataPipeline/configs/config.ini` for token, competition, and season settings.
- Parquet-based analysis outputs alongside raw JSON snapshots.
- Ingestion of competition metadata, teams, standings, matches, and top scorers.
- Support for one season or multiple seasons through a single `seasons` config value.

### Notes
- The current dataset is intended as the first analysis base for Premier League work, with Champions League support planned later using the same ingestion shape.

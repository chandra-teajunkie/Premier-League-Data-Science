"""Shared configuration for repo scripts.

All token lookup should go through this module so every script uses the same
environment-variable behavior.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from datetime import date


CONFIG_FILE = Path(__file__).with_name("config.ini")
CONFIG = configparser.ConfigParser()
CONFIG.read(CONFIG_FILE)

FOOTBALL_DATA_TOKEN = os.getenv(
    "FOOTBALL_DATA_TOKEN",
    CONFIG.get("tokens", "football_data_token", fallback="").strip(),
).strip()

INGEST_COMPETITION = CONFIG.get("ingestion", "competition", fallback="PL").strip()
INGEST_SEASONS = [int(item.strip()) for item in CONFIG.get("ingestion", "seasons", fallback="").split(",") if item.strip()] or [date.today().year - 1]
INGEST_OUTPUT_DIR = Path(
    CONFIG.get(
        "ingestion",
        "output_dir",
        fallback=str(Path(__file__).resolve().parents[2]),
    )
)
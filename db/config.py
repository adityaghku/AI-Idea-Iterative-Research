"""Configuration loading from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/idea_harvester",
    )


def get_database_url_sync() -> str:
    return os.getenv(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/idea_harvester",
    )


DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_TOKENS = 2000
DEFAULT_TEMPERATURE = 0.7

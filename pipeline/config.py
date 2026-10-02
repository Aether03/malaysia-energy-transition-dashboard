"""Paths, connection settings and source URLs.

Only the server and database names are configurable (via `.env`); authentication is
always Windows integrated auth, so there are no secrets to store (doc 02 §7).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SQL_DIR = ROOT / "sql"
MIGRATIONS_DIR = SQL_DIR / "migrations"
VIEWS_DIR = SQL_DIR / "views"
TRANSFORM_DIR = SQL_DIR / "transform"
SEED_DIR = ROOT / "seed"
RAW_DIR = ROOT / "data" / "raw"
LOG_DIR = ROOT / "logs"

ASEAN_ISO3: tuple[str, ...] = ("BRN", "KHM", "IDN", "LAO", "MYS", "MMR", "PHL", "SGP", "THA", "VNM")

EMBER_YEARLY_URL = (
    "https://files.ember-energy.org/public-downloads/generation/outputs/"
    "release_generation_yearly_global.csv"
)
OWID_ENERGY_URL = "https://owid-public.owid.io/data/energy/owid-energy-data.csv"
DOSM_SUPPLY_URL = "https://storage.data.gov.my/energy/electricity_supply.csv"
DOSM_CONSUMPTION_URL = "https://storage.data.gov.my/energy/electricity_consumption.csv"
# DTH: Thai power system hourly data, Zenodo record pinned to v1.0 (published 2025-09-13).
THAILAND_ZENODO_RECORD = "17109911"
THAILAND_FILE_URL = f"https://zenodo.org/api/records/{THAILAND_ZENODO_RECORD}/files/{{file_name}}/content"
# Zenodo's published MD5 per file (record metadata, checked 2026-10-03). Zenodo sends no
# Last-Modified/ETag, so the checksum is the version: a revised file stops the run.
THAILAND_MD5 = {
    "system_2023.csv": "426d0db764f75780f589a8aeb6b1ef65",
    "system_2024.csv": "5c1f09d6641ad6addb6f282f981e808a",
}


@dataclass(frozen=True)
class DbSettings:
    server: str
    database: str

    def connection_string(self, database: str | None = None) -> str:
        # TrustServerCertificate: the local dev instance uses a self-signed certificate.
        return (
            f"Server={self.server};Database={database or self.database};"
            "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes"
        )


def db_settings() -> DbSettings:
    return DbSettings(
        server=os.getenv("SQL_SERVER", "localhost"),
        database=os.getenv("SQL_DATABASE", "EnergyDW"),
    )

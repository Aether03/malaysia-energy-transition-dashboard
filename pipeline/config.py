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

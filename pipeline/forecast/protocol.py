"""The locked backtest protocol (M3 plan protocol guard #1).

`docs/forecast.md` §Protocol is the single source of the run's settings: the first ```json
fenced block under the `## Protocol` heading. A FINAL run reads its settings only from there,
and `committed_protocol` refuses it unless the protocol and the forecast code are committed
and unchanged in the working tree. The commit hashes go into `dw.forecast_run`.

The JSON block has exactly this shape (the values are examples):

    {
      "features": ["hour", "iso_weekday", ...],      # must equal features.FEATURE_COLUMNS
      "data_start": "2023-01-08",                    # first fit hour, local midnight
      "es_days": 28,
      "dev":   {"first_month": "2023-10", "last_month": "2023-12"},
      "final": {"first_month": "2024-01", "last_month": "2024-12"},
      "lightgbm": {"objective": "l2", "learning_rate": 0.05, ...},
      "seed": 20231008,
      "num_threads": 1,
      "bootstrap": {"n_boot": 2000, "level": 0.95}
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import config

PROTOCOL_REL = "docs/forecast.md"
GUARDED_REL: tuple[str, ...] = (PROTOCOL_REL, "pipeline/forecast")


class ProtocolError(RuntimeError):
    """The protocol is missing, malformed, or not committed as required for a FINAL run."""


@dataclass(frozen=True)
class Protocol:
    features: tuple[str, ...]
    data_start: pd.Timestamp
    es_days: int
    dev_first_month: str
    dev_last_month: str
    final_first_month: str
    final_last_month: str
    lightgbm: dict[str, Any]
    seed: int
    num_threads: int
    n_boot: int
    level: float
    raw: dict[str, Any]  # the parsed JSON block as written, stored in forecast_run.params_json


def parse_protocol(text: str) -> Protocol:
    """Parse the first ```json block in the `## Protocol` section of a markdown document.

    The section runs from the `## Protocol` heading to the next heading of level 2 or higher.
    Raises ProtocolError if the section or its json block is missing, the JSON is invalid, a key
    is missing or has the wrong type, `features` differs from `features.FEATURE_COLUMNS`, a month
    is not 'YYYY-MM', a first month is after its last month, or the dev months reach into the
    final period (dev last month >= final first month).
    """
    raise NotImplementedError


def load_protocol(path: Path = config.ROOT / PROTOCOL_REL) -> Protocol:
    """`parse_protocol` on the file's text (UTF-8). Raises ProtocolError if the file is missing."""
    raise NotImplementedError


def committed_protocol(repo: Path = config.ROOT) -> tuple[str, str]:
    """The `--final` gate. Returns (protocol_commit, head_commit).

    `protocol_commit` is the hash of the last commit that touched `PROTOCOL_REL`, `head_commit`
    the hash of HEAD; both 40 lowercase hex characters, read with `git` run in `repo`.

    Raises ProtocolError if `repo` is not a git work tree, `PROTOCOL_REL` is missing or not
    tracked, or any path under `GUARDED_REL` has an uncommitted change: staged, unstaged, or an
    untracked file.
    """
    raise NotImplementedError

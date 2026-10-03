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

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import config
from pipeline.forecast.features import FEATURE_COLUMNS

PROTOCOL_REL = "docs/forecast.md"
GUARDED_REL: tuple[str, ...] = (PROTOCOL_REL, "pipeline/forecast")


_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_KEYS = ("features", "data_start", "es_days", "dev", "final", "lightgbm", "seed", "num_threads", "bootstrap")


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
    block = _protocol_block(text)
    try:
        raw = json.loads(block)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"the protocol block is not valid JSON: {exc}") from exc
    return protocol_from_dict(raw)


def protocol_from_dict(raw: Any) -> Protocol:
    """Validate a parsed protocol block (also used to replay a FINAL run from its stored settings)."""
    if not isinstance(raw, dict):
        raise ProtocolError("the protocol block must be a JSON object")
    missing = [k for k in _KEYS if k not in raw]
    unknown = [k for k in raw if k not in _KEYS]
    if missing or unknown:
        raise ProtocolError(f"protocol keys: missing {missing}, unknown {unknown}")

    features = raw["features"]
    if not isinstance(features, list) or tuple(features) != FEATURE_COLUMNS:
        raise ProtocolError(f"protocol features {features!r} differ from the code's {list(FEATURE_COLUMNS)}")
    data_start = raw["data_start"]
    if not isinstance(data_start, str) or not _DAY.fullmatch(data_start):
        raise ProtocolError(f"data_start must be 'YYYY-MM-DD', got {data_start!r}")
    dev_first, dev_last = _months(raw, "dev")
    final_first, final_last = _months(raw, "final")
    if dev_last >= final_first:
        raise ProtocolError(f"dev months reach into the final period ({dev_last} >= {final_first})")
    bootstrap = _section(raw, "bootstrap", ("n_boot", "level"))
    level = bootstrap["level"]
    if not _is_number(level) or not 0 < level < 1:
        raise ProtocolError(f"bootstrap level must be a number strictly between 0 and 1, got {level!r}")
    if not isinstance(raw["lightgbm"], dict):
        raise ProtocolError("lightgbm must be an object of LightGBM parameters")
    return Protocol(
        features=tuple(features),
        data_start=pd.Timestamp(data_start),
        es_days=_positive_int(raw["es_days"], "es_days"),
        dev_first_month=dev_first,
        dev_last_month=dev_last,
        final_first_month=final_first,
        final_last_month=final_last,
        lightgbm=dict(raw["lightgbm"]),
        seed=_int(raw["seed"], "seed"),
        num_threads=_positive_int(raw["num_threads"], "num_threads"),
        n_boot=_positive_int(bootstrap["n_boot"], "bootstrap.n_boot"),
        level=float(level),
        raw=raw,
    )


def load_protocol(path: Path = config.ROOT / PROTOCOL_REL) -> Protocol:
    """`parse_protocol` on the file's text (UTF-8). Raises ProtocolError if the file is missing."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProtocolError(f"no protocol file at {path}") from exc
    return parse_protocol(text)


def committed_protocol(repo: Path = config.ROOT) -> tuple[str, str]:
    """The `--final` gate. Returns (protocol_commit, head_commit).

    `protocol_commit` is the hash of the last commit that touched `PROTOCOL_REL`, `head_commit`
    the hash of HEAD; both 40 lowercase hex characters, read with `git` run in `repo`.

    Raises ProtocolError if `repo` is not a git work tree, `PROTOCOL_REL` is missing or not
    tracked, or any path under `GUARDED_REL` has an uncommitted change: staged, unstaged, or an
    untracked file.
    """
    if _git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise ProtocolError(f"{repo} is not a git work tree")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", PROTOCOL_REL], cwd=repo, capture_output=True, text=True, check=False
    )
    if tracked.returncode != 0:
        raise ProtocolError(f"{PROTOCOL_REL} is not committed")
    changes = _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "--", *GUARDED_REL)
    if changes:
        raise ProtocolError(f"uncommitted changes in the protocol or forecast code:\n{changes}")
    protocol_commit = _git(repo, "log", "-1", "--format=%H", "--", PROTOCOL_REL)
    head_commit = _git(repo, "rev-parse", "HEAD")
    for name, value in (("protocol commit", protocol_commit), ("HEAD", head_commit)):
        if not _HEX40.fullmatch(value):
            raise ProtocolError(f"unexpected {name} hash {value!r}")
    return protocol_commit, head_commit


def _git(repo: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ProtocolError(f"git is not available: {exc}") from exc
    if done.returncode != 0:
        raise ProtocolError(f"git {' '.join(args)} failed in {repo}: {done.stderr.strip()}")
    return done.stdout.strip()


def _protocol_block(text: str) -> str:
    """The first ```json block between `## Protocol` and the next level-1 or level-2 heading."""
    in_section = in_fence = in_json = found_section = False
    block: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_json:
                return "\n".join(block)
            if in_section and not in_fence and stripped[3:].strip().lower() == "json":
                in_json = True
            in_fence = not in_fence
            continue
        if in_json:
            block.append(line)
        elif not in_fence and re.match(r"#{1,2}\s", line):
            if in_section:
                break
            in_section = re.fullmatch(r"##\s+Protocol\s*", line.rstrip()) is not None
            found_section = found_section or in_section
    if in_json:
        raise ProtocolError("the protocol json block is not closed")
    if not found_section:
        raise ProtocolError("no '## Protocol' section")
    raise ProtocolError("the '## Protocol' section has no ```json block")


def _section(raw: dict[str, Any], name: str, keys: tuple[str, ...]) -> dict[str, Any]:
    section = raw[name]
    if not isinstance(section, dict) or any(k not in section for k in keys):
        raise ProtocolError(f"{name} must be an object with keys {list(keys)}")
    return section


def _months(raw: dict[str, Any], name: str) -> tuple[str, str]:
    section = _section(raw, name, ("first_month", "last_month"))
    first, last = section["first_month"], section["last_month"]
    for value in (first, last):
        if not isinstance(value, str) or not _MONTH.fullmatch(value):
            raise ProtocolError(f"{name} months must be 'YYYY-MM', got {value!r}")
    if first > last:
        raise ProtocolError(f"{name} first month {first} is after its last month {last}")
    return first, last


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError(f"{name} must be an integer, got {value!r}")
    return value


def _positive_int(value: Any, name: str) -> int:
    if _int(value, name) < 1:
        raise ProtocolError(f"{name} must be at least 1, got {value!r}")
    return value

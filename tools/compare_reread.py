"""Compare every parsed handbook cell with the independent re-read (M4 step 7).

Two fresh-context agents transcribed every pinned cell from the page images, blind to the parser,
into git-ignored data/private/reread_A.csv and reread_B.csv. This tool merges them into
data/private/handbook_2023_reread.csv (read by tests/test_handbook_pdf.py) and diffs them with
raw.handbook_cell for the pinned edition.

The handbook is restricted (M4 plan Q1): by default only cell ids and counts are printed. Pass
--show-values to see both readings of each differing cell on this terminal while settling them
by eye; never paste that output into a committed file.

    .venv/Scripts/python tools/compare_reread.py [--show-values]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import db
from pipeline.sources import handbook

PRIVATE = ROOT / "data" / "private"
PARTS = ("reread_A.csv", "reread_B.csv")
MERGED = PRIVATE / "handbook_2023_reread.csv"


def _read_parts() -> dict[tuple[str, int, int], str]:
    reread: dict[tuple[str, int, int], str] = {}
    for name in PARTS:
        with (PRIVATE / name).open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                key = (row["table_code"], int(row["row_pos"]), int(row["col_pos"]))
                if key in reread:
                    raise SystemExit(f"{name}: duplicate cell {key}")
                reread[key] = "".join(row["value_text"].split())
    return reread


def _parsed() -> dict[tuple[str, int, int], str]:
    cursor = db.connect().cursor()
    cursor.execute(
        "SELECT table_code, row_pos, col_pos, value_text FROM raw.handbook_cell WHERE edition = ?", (handbook.EDITION,)
    )
    return {(t, int(r), int(c)): v for t, r, c, v in cursor.fetchall()}


def main() -> int:
    show = "--show-values" in sys.argv[1:]
    reread, parsed = _read_parts(), _parsed()
    with MERGED.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["table_code", "row_pos", "col_pos", "value_text"])
        writer.writerows([*k, v] for k, v in sorted(reread.items()))
    empty = sorted(k for k, v in reread.items() if not v)
    only_parsed, only_reread = sorted(set(parsed) - set(reread)), sorted(set(reread) - set(parsed))
    differ = sorted(k for k in set(parsed) & set(reread) if parsed[k] != reread[k])
    print(f"parsed {len(parsed)} cells, re-read {len(reread)} cells, {len(empty)} re-read blanks")
    print(f"only parsed: {len(only_parsed)}  only re-read: {len(only_reread)}  differing: {len(differ)}")
    for k in only_parsed[:20] + only_reread[:20] + empty[:20]:
        print("  coverage", k)
    for k in differ:
        print("  differs", k, f"parsed={parsed[k]!r} reread={reread[k]!r}" if show else "")
    return 0 if not (differ or only_parsed or only_reread or empty) else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Make committed parser fixtures from the handbook PDF WITHOUT committing any of its numbers.

M4 plan Q8: the parser is tested test-first on page fixtures, but the handbook is restricted
(Q1), so a fixture keeps a pinned page's real word layout (texts, boxes, wrapped labels, rotated
text already dropped) and replaces every number with a synthetic one of the same shape.

Kept as printed, chosen by POSITION, never by text (M4 review H2): numbers on a pinned table's
header lines (years), in its row-label zone (year row labels, "2015" in "GDP at 2015 Prices"),
and on its anchor or sub-heading lines ("31st December 2021", "per 1,000 Customers", the page
furniture). A real value that happens to equal a heading token is still replaced.

Replaced: every other numeric token, including tables on the page that aren't pinned. Each digit is redrawn (seeded per page, so re-runs are
identical), commas, decimal point, sign and percent sign stay, a leading non-zero digit stays
non-zero, and the token is redrawn until it differs from the original. A lone "-" stays "-".

    .venv/Scripts/python tools/make_handbook_fixture.py path/to/Malaysia_Energy_Statistics_Handbook_2023.pdf

Writes tests/fixtures/handbook/p<page>.json, each marked "synthetic": true.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.sources import handbook

OUT_DIR = ROOT / "tests" / "fixtures" / "handbook"
NOTE = (
    "SYNTHETIC: the word layout of a pinned handbook page with every number replaced "
    "(tools/make_handbook_fixture.py). Contains no Energy Commission data."
)


def kept_positions(words: list[handbook.Word], specs: list[handbook.TableSpec]) -> set[int]:
    """Indexes (into `words`) of the words that are headings, not data, for the page's pinned tables."""
    index = {id(w): i for i, w in enumerate(words)}
    keep: set[int] = set()
    lines = handbook.group_lines(words)
    for spec in specs:
        for line in lines:  # anchor and sub-heading lines (also outside the region)
            if (spec.start_after and spec.start_after in line.text) or spec.stop_before in line.text or line.text in spec.ignore_lines:
                keep |= {index[id(w)] for w in line.words}
        region = handbook.table_region(lines, spec)
        for line in region[: spec.header_lines]:
            keep |= {index[id(w)] for w in line.words}
        for line in region[spec.header_lines :]:
            keep |= {index[id(w)] for w in line.words if w.x0 < spec.label_x_max}
    return keep


def scramble(token: str, rng: random.Random) -> str:
    """A different token of the same shape (digits redrawn; punctuation and length kept)."""
    if token == "-" or not any(ch.isdigit() for ch in token):
        return token
    for _ in range(100):
        out, first = [], True
        for ch in token:
            if ch.isdigit():
                out.append(str(rng.randint(1, 9) if first and ch != "0" else rng.randint(0, 9)))
                first = False
            else:
                out.append(ch)
                first = first and ch in "-"
        candidate = "".join(out)
        if candidate != token:
            return candidate
    raise RuntimeError(f"could not scramble {token!r}")


def fixture_for(pdf, page_no: int, specs: list[handbook.TableSpec]) -> dict:
    rng = random.Random(f"handbook-fixture-p{page_no}")
    real = handbook.words_from_page(pdf.pages[page_no - 1])
    keep = kept_positions(real, specs)
    words = []
    replaced = kept = 0
    for i, w in enumerate(real):
        text = w.text
        if handbook.VALUE_TOKEN.fullmatch(text) and text != "-":
            if i in keep:
                kept += 1
            else:
                text = scramble(text, rng)
                replaced += 1
        words.append({"text": text, "x0": round(w.x0, 2), "x1": round(w.x1, 2), "top": round(w.top, 2), "bottom": round(w.bottom, 2)})
    print(f"p{page_no}: {len(words)} words, {replaced} numbers replaced, {kept} heading numbers kept")
    return {"synthetic": True, "note": NOTE, "edition": handbook.EDITION, "page": page_no, "words": words}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    pdf_path = Path(sys.argv[1])
    handbook.verify_checksum(pdf_path)  # fixtures must come from the pinned file
    by_page: dict[int, list[handbook.TableSpec]] = {}
    for spec in handbook.TABLES[handbook.EDITION]:
        by_page.setdefault(spec.page, []).append(spec)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, specs in sorted(by_page.items()):
            data = fixture_for(pdf, page_no, specs)
            (OUT_DIR / f"p{page_no}.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Turn Power BI Desktop's whole-report PDF into the public export set (M5 step 5, plan Q2).

Desktop has File > Export > Export to PDF, but no per-page PNG. So:
1. In Desktop, export the whole report to `data/private/report_full.pdf` (git-ignored: it holds P3/P3b,
   whose Energy Commission handbook charts are published only while D5's consent is GRANTED).
2. Run `.venv/Scripts/python tools/export_pages.py`. It writes `docs/report.pdf` (public pages only) and
   `docs/img/NN_<page>.png` at 1280x720.

PDF pages are matched to the visible pages of `pages.json`, in order (Desktop exports visible pages only;
the count must agree). A page is dropped while its source's consent (seed/data_source.csv) is not GRANTED,
and a marker check refuses to write anything if restricted page text shows up on a kept page.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "report" / "EnergyTransition.Report" / "definition" / "pages"
FULL_PDF = ROOT / "data" / "private" / "report_full.pdf"
OUT_PDF = ROOT / "docs" / "report.pdf"
OUT_IMG = ROOT / "docs" / "img"
WIDTH, HEIGHT = 1280, 720

# Pages that show a restricted source, and that source's code in seed/data_source.csv.
RESTRICTED_PAGES = {"p3_regions": "D5", "p3b_state_reliability": "D5"}
# Text that only those pages print (titles from the P3 SAIFI bar and the P3b map measures). Each restricted
# page must contain one, which proves the page mapping; no kept page may contain any.
RESTRICTED_MARKERS = ("SAIFI by region", "darker = less reliable")


def visible_pages(pages_dir: Path = PAGES_DIR) -> list[tuple[str, str]]:
    """(name, display name) of every page Desktop exports, in report order."""
    order = json.loads((pages_dir / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    pages = []
    for name in order:
        page = json.loads((pages_dir / name / "page.json").read_text(encoding="utf-8"))
        if page.get("visibility") != "HiddenInViewMode":
            pages.append((name, page["displayName"]))
    return pages


def consent(seed: Path = ROOT / "seed" / "data_source.csv") -> dict[str, str]:
    with seed.open(encoding="utf-8", newline="") as f:
        return {row["data_source_code"]: row["consent_status"] for row in csv.DictReader(f)}


def keep_flags(pages: list[tuple[str, str]], consent_by_source: dict[str, str]) -> list[bool]:
    """Fails closed: a restricted page is kept only when its source's consent is GRANTED."""
    return [
        name not in RESTRICTED_PAGES or consent_by_source.get(RESTRICTED_PAGES[name]) == "GRANTED" for name, _ in pages
    ]


def check_markers(texts: list[str], keep: list[bool], pages: list[tuple[str, str]]) -> list[str]:
    """Problems that must stop the export: a restricted page without a marker (the mapping is off), or an
    unrestricted page with one (restricted text would be published without its consent)."""
    problems = []
    for text, kept, (name, _) in zip(texts, keep, pages, strict=True):
        found = [m for m in RESTRICTED_MARKERS if m in text]
        restricted = name in RESTRICTED_PAGES
        if found and not restricted:
            problems.append(f"{name}: kept page contains restricted marker(s) {found}")
        if restricted and not found:
            state = "kept" if kept else "dropped"
            problems.append(f"{name}: {state} page has no restricted marker; is the page order right?")
    return problems


def slug(index: int, display_name: str) -> str:
    return f"{index:02d}_" + re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip("_")


def main() -> int:
    if not FULL_PDF.exists():
        print(f"{FULL_PDF.relative_to(ROOT)} not found: export the report from Desktop first")
        return 1
    pages = visible_pages()
    src = pdfium.PdfDocument(FULL_PDF)
    if len(src) != len(pages):
        print(f"The PDF has {len(src)} pages but the report has {len(pages)} visible pages")
        return 1
    texts = [src[i].get_textpage().get_text_range() for i in range(len(src))]
    keep = keep_flags(pages, consent())
    problems = check_markers(texts, keep, pages)
    if problems:
        print("\n".join(problems))
        return 1

    kept = [i for i, k in enumerate(keep) if k]
    out = pdfium.PdfDocument.new()  # a new document: no metadata from Desktop's export
    out.import_pages(src, pages=kept)
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT_PDF)

    OUT_IMG.mkdir(parents=True, exist_ok=True)
    for old in OUT_IMG.glob("[0-9][0-9]_*.png"):
        old.unlink()  # a page renamed or dropped since the last export must not linger
    for n, i in enumerate(kept, 1):
        page = src[i]
        image = page.render(scale=WIDTH / page.get_width()).to_pil()
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT))
        path = OUT_IMG / f"{slug(n, pages[i][1])}.png"
        image.save(path, optimize=True)
        print(f"{path.relative_to(ROOT)}  <- PDF page {i + 1} ({pages[i][0]})")
    dropped = [pages[i][0] for i, k in enumerate(keep) if not k]
    print(f"{OUT_PDF.relative_to(ROOT)}: {len(kept)} of {len(pages)} pages; dropped {dropped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

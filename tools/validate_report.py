"""Static checks of the generated report pages (M2 steps 8-10).

Loads every page.json / visual.json under report/EnergyTransition.Report/definition/pages and checks:
unique visual names (<= 50 chars) per page, positions inside the page, every measure/column/table
referenced exists in the TMDL files, navigation and tooltip targets exist, and visual interactions point at
real visuals. M5 step 4 adds: every visual except report_builder.DECORATIVE has non-empty alt text; every
page except a tooltip page has the ⓘ About button; every page with a nav rail has the Fail badge; a
visualTooltip has only `show` and `section` (Desktop's shape; a `type` property stops the page rendering).

    .venv/Scripts/python tools/validate_report.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from report_builder import DECORATIVE

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "report" / "EnergyTransition.Report" / "definition" / "pages"
TABLES = ROOT / "report" / "EnergyTransition.SemanticModel" / "definition" / "tables"


def unquote(name: str) -> str:
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") else name


def parse_model() -> dict[str, dict[str, set[str]]]:
    model: dict[str, dict[str, set[str]]] = {}
    for f in TABLES.glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^table\s+(.+?)\s*$", text, re.MULTILINE)
        table = unquote(m.group(1))
        cols = {unquote(x) for x in re.findall(r"^\tcolumn\s+('(?:[^']|'')+'|[^\s=]+)", text, re.MULTILINE)}
        meas = {unquote(x) for x in re.findall(r"^\tmeasure\s+('(?:[^']|'')+'|[^\s=]+)", text, re.MULTILINE)}
        model[table] = {"columns": cols, "measures": meas}
    return model


def walk(node, aliases, errors, where, model):
    if isinstance(node, dict):
        if "From" in node and isinstance(node["From"], list):
            aliases = {**aliases, **{f["Name"]: f["Entity"] for f in node["From"]}}
        for kind in ("Column", "Measure"):
            if kind in node and isinstance(node[kind], dict) and "Expression" in node[kind]:
                ref = node[kind]["Expression"].get("SourceRef", {})
                entity = ref.get("Entity") or aliases.get(ref.get("Source"))
                prop = node[kind]["Property"]
                key = "columns" if kind == "Column" else "measures"
                if entity not in model:
                    errors.append(f"{where}: unknown table {entity!r}")
                elif prop not in model[entity][key]:
                    errors.append(f"{where}: {kind.lower()} {entity}[{prop}] not in model")
        meta = node.get("metadata")
        if isinstance(meta, str) and "." in meta:
            table, prop = meta.split(".", 1)
            if table not in model or prop not in model[table]["measures"] | model[table]["columns"]:
                errors.append(f"{where}: selector metadata {meta!r} not in model")
        for v in node.values():
            walk(v, aliases, errors, where, model)
    elif isinstance(node, list):
        for v in node:
            walk(v, aliases, errors, where, model)


def literal(node):
    return node["expr"]["Literal"]["Value"].strip("'") if node else None


def alt_text(visual: dict) -> str:
    """The visual's altText literal ('' when absent)."""
    for entry in visual["visual"].get("visualContainerObjects", {}).get("general", []):
        return literal(entry["properties"].get("altText")) or ""
    return ""


def main() -> int:
    model = parse_model()
    errors: list[str] = []
    meta = json.loads((PAGES / "pages.json").read_text(encoding="utf-8"))
    page_dirs = {p.name for p in PAGES.iterdir() if p.is_dir()}
    for name in meta["pageOrder"]:
        if name not in page_dirs:
            errors.append(f"pages.json lists missing page {name}")
    for name in page_dirs - set(meta["pageOrder"]):
        errors.append(f"page folder {name} missing from pages.json")

    total = 0
    for page_dir in sorted(PAGES.iterdir()):
        if not page_dir.is_dir():
            continue
        page = json.loads((page_dir / "page.json").read_text(encoding="utf-8"))
        pw, ph = page["width"], page["height"]
        names: dict[str, int] = {}
        visuals = {}
        for vf in sorted((page_dir / "visuals").glob("*/visual.json")):
            v = json.loads(vf.read_text(encoding="utf-8"))
            total += 1
            n = v["name"]
            where = f"{page_dir.name}/{n}"
            if n != vf.parent.name:
                errors.append(f"{where}: name differs from folder")
            names[n] = names.get(n, 0) + 1
            visuals[n] = v
            if len(n) > 50:
                errors.append(f"{where}: name longer than 50 chars")
            pos = v["position"]
            if pos["x"] < 0 or pos["y"] < 0 or pos["x"] + pos["width"] > pw + 1e-6 or pos["y"] + pos["height"] > ph + 1e-6:
                errors.append(f"{where}: outside {pw}x{ph}: {pos}")
            walk(v, {}, errors, where, model)
            vco = v["visual"].get("visualContainerObjects", {})
            for entry in vco.get("visualLink", []):
                target = literal(entry["properties"].get("navigationSection"))
                if target and target not in page_dirs:
                    errors.append(f"{where}: navigates to missing page {target}")
            for entry in vco.get("visualTooltip", []):
                target = literal(entry["properties"].get("section"))
                if target not in page_dirs:
                    errors.append(f"{where}: tooltip page {target} missing")
                if set(entry["properties"]) != {"show", "section"}:
                    errors.append(f"{where}: visualTooltip must have only show and section: {sorted(entry['properties'])}")
            if n not in DECORATIVE and not alt_text(v).strip():
                errors.append(f"{where}: no alt text")
            if v["visual"]["visualType"] == "card":
                h = pos["height"]
                if h < 40:
                    errors.append(f"{where}: classic card shorter than 40 px")
        for n, c in names.items():
            if c > 1:
                errors.append(f"{page_dir.name}: duplicate visual name {n}")
        if page.get("type") != "Tooltip":
            if "frame_info" not in visuals:
                errors.append(f"{page_dir.name}: no ⓘ About button (frame_info)")
            if any(n.startswith("frame_nav_") and n != "frame_nav_selected" for n in visuals) and "frame_nav_badge" not in visuals:
                errors.append(f"{page_dir.name}: has a nav rail but no Fail badge (frame_nav_badge)")
        walk(page, {}, errors, page_dir.name, model)
        for it in page.get("visualInteractions", []):
            for end in ("source", "target"):
                if it[end] not in visuals:
                    errors.append(f"{page_dir.name}: interaction {end} {it[end]} is not a visual")
        print(f"{page_dir.name}: {len(visuals)} visuals, page {pw}x{ph}, type {page.get('type', 'Default')}")
    # Desktop 2.158 saves bookmark options its own loader rejects under schema 2.1.0 (M2 close-out).
    for path in sorted((PAGES.parent / "bookmarks").glob("*.bookmark.json")):
        if "preserveNewVisualVisibility" in json.loads(path.read_text(encoding="utf-8")).get("options", {}):
            errors.append(f"bookmarks/{path.name}: options.preserveNewVisualVisibility blocks opening; remove it")
    print(f"{total} visuals checked, {len(errors)} problems")
    for e in errors:
        print("  -", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

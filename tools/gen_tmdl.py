"""Generate Power BI TMDL table files from the mart views (M1 step 8).

Column names and types are read from SQL Server, so the semantic model can't drift from
the database contract (doc 05 §2.6). Measures, relationships and the theme are
hand-written and are not touched by this script. Lineage tags that Power BI Desktop added
are kept, so a regeneration only shows real column changes in the diff.

    .venv/Scripts/python tools/gen_tmdl.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config, db

TABLES_DIR = config.ROOT / "report" / "EnergyTransition.SemanticModel" / "definition" / "tables"

MART_VIEWS = (
    "dim_country", "dim_source", "dim_year", "data_source", "kpi", "netr_target",
    "generation_annual", "country_annual", "run_latest", "dq_latest", "re_capacity_official",
)  # fmt: skip

TYPE_MAP = {
    "int": "int64", "bigint": "int64", "smallint": "int64", "tinyint": "int64",
    "bit": "boolean",
    "decimal": "double", "numeric": "double", "float": "double", "real": "double",
    "nvarchar": "string", "varchar": "string", "nchar": "string", "char": "string",
    "datetime2": "dateTime", "datetime": "dateTime", "date": "dateTime",
}  # fmt: skip

SORT_BY = {("dim_source", "display_name"): "sort_order"}

# Fact-table years are hidden so every year filter goes through dim_year (DAX review, LOW).
HIDDEN = {("generation_annual", "year"), ("country_annual", "year")}


def _columns(cursor, view: str) -> list[tuple[str, str, int]]:
    cursor.execute(
        "SELECT c.name, t.name, c.scale FROM sys.columns AS c "
        "JOIN sys.types AS t ON t.user_type_id = c.user_type_id "
        "WHERE c.object_id = OBJECT_ID(?) ORDER BY c.column_id",
        (f"mart.{view}",),
    )
    return [(name, type_name, scale) for name, type_name, scale in cursor.fetchall()]


def _existing_tags(path: Path) -> dict[str | None, str]:
    """Lineage tags from the previous file: {None: table tag, column name: column tag}."""
    tags: dict[str | None, str] = {}
    if not path.exists():
        return tags
    column: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("\tcolumn "):
            column = line.split(" ", 1)[1].strip()
        elif line.startswith("\tpartition "):
            column = None
        elif line.startswith("\tlineageTag: ") and column is None:
            tags[None] = line.split(": ", 1)[1].strip()
        elif line.startswith("\t\tlineageTag: ") and column is not None:
            tags[column] = line.split(": ", 1)[1].strip()
        elif line.startswith("\tannotation "):
            tags.setdefault("__annotations__", "")
            tags["__annotations__"] += line + "\n\n"
    return tags


def _column_tmdl(view: str, name: str, sql_type: str, scale: int, tag: str | None = None) -> str:
    # Attribute order follows what Power BI Desktop writes, to keep diffs quiet.
    data_type = TYPE_MAP[sql_type]
    lines = [f"\tcolumn {name}", f"\t\tdataType: {data_type}"]
    if name.endswith("_key") or (view, name) in HIDDEN:
        lines.append("\t\tisHidden")
    if data_type == "double":
        lines.append(f"\t\tformatString: {'0.' + '0' * min(scale, 3) if scale else '0'}")
    elif data_type == "int64":
        lines.append("\t\tformatString: 0")
    elif data_type == "dateTime":
        lines.append("\t\tformatString: General Date")
    if tag:
        lines.append(f"\t\tlineageTag: {tag}")
    lines.append("\t\tsummarizeBy: none")  # all aggregation goes through explicit measures
    lines.append(f"\t\tsourceColumn: {name}")
    if (view, name) in SORT_BY:
        lines.append(f"\t\tsortByColumn: {SORT_BY[(view, name)]}")
    return "\n".join(lines)


def _table_tmdl(view: str, columns: list[tuple[str, str, int]], tags: dict[str | None, str]) -> str:
    column_blocks = "\n\n".join(_column_tmdl(view, *col, tag=tags.get(col[0])) for col in columns)
    partition = (
        f"\tpartition {view} = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        "\t\t\t\tlet\n"
        "\t\t\t\t    Source = Sql.Database(SqlServer, SqlDatabase),\n"
        f'\t\t\t\t    {view} = Source{{[Schema="mart",Item="{view}"]}}[Data]\n'
        "\t\t\t\tin\n"
        f"\t\t\t\t    {view}\n"
    )
    header = f"table {view}\n" + (f"\tlineageTag: {tags[None]}\n" if None in tags else "")
    annotations = tags.get("__annotations__", "")  # Desktop-added table annotations, kept verbatim
    return f"{header}\n{column_blocks}\n\n{partition}\n{annotations}"


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    cursor = db.connect().cursor()
    for view in MART_VIEWS:
        columns = _columns(cursor, view)
        if not columns:
            raise SystemExit(f"mart.{view} not found; run `python -m pipeline db migrate` first")
        path = TABLES_DIR / f"{view}.tmdl"
        path.write_text(_table_tmdl(view, columns, _existing_tags(path)), encoding="utf-8")
        print(f"{view}: {len(columns)} columns")


if __name__ == "__main__":
    main()

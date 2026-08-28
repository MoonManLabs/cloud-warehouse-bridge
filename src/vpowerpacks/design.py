from __future__ import annotations

from dataclasses import dataclass

from .profiler import ColumnProfile, SourceProfile


@dataclass
class DesignAdvice:
    segmentation_candidates: list[str]
    partition_candidates: list[str]
    sort_order_candidates: list[str]
    materialization_candidates: list[str]
    sql: str
    markdown: str


def build_design_advice(profile: SourceProfile, schema: str, table: str) -> DesignAdvice:
    columns = profile.columns
    segmentation = _segmentation_candidates(columns)
    partitions = _partition_candidates(columns)
    sort_order = _sort_order_candidates(columns)
    materialize = _materialization_candidates(columns)
    sql = _design_sql(schema, table, segmentation, partitions, sort_order)
    markdown = _design_markdown(segmentation, partitions, sort_order, materialize)
    return DesignAdvice(segmentation, partitions, sort_order, materialize, sql, markdown)


def _segmentation_candidates(columns: list[ColumnProfile]) -> list[str]:
    preferred_tokens = ("tenant", "account", "customer", "user", "device", "property", "id")
    candidates = [
        column.name
        for column in columns
        if column.recommended_vertica_type in {"INT", "VARCHAR(1024)"}
        and any(token in column.name for token in preferred_tokens)
    ]
    return _dedupe(candidates[:3])


def _partition_candidates(columns: list[ColumnProfile]) -> list[str]:
    candidates = [
        column.name
        for column in columns
        if column.recommended_vertica_type in {"DATE", "TIMESTAMP"}
        or any(token in column.name for token in ("date", "month", "year", "ts", "time"))
    ]
    return _dedupe(candidates[:3])


def _sort_order_candidates(columns: list[ColumnProfile]) -> list[str]:
    priority_tokens = ("tenant", "account", "customer", "state", "region", "date", "ts", "time", "id")
    scored: list[tuple[int, str]] = []
    for column in columns:
        score = sum(1 for token in priority_tokens if token in column.name)
        if score:
            scored.append((score, column.name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return _dedupe([name for _, name in scored[:5]])


def _materialization_candidates(columns: list[ColumnProfile]) -> list[str]:
    return [
        column.name
        for column in columns
        if column.recommended_vertica_type == "LONG VARCHAR"
        or any(token in column.name for token in ("payload", "attrs", "json", "raw"))
    ][:5]


def _design_sql(
    schema: str,
    table: str,
    segmentation: list[str],
    partitions: list[str],
    sort_order: list[str],
) -> str:
    lines = [
        "-- Draft physical-design advice. Review with real workload predicates before applying.",
        f"-- Target table: {schema}.{table}",
    ]
    if segmentation:
        lines.append(f"-- Segmentation candidates: {', '.join(segmentation)}")
    else:
        lines.append("-- Segmentation candidates: unavailable from current profile.")
    if partitions:
        lines.append(f"-- Partition candidates: {', '.join(partitions)}")
    else:
        lines.append("-- Partition candidates: unavailable from current profile.")
    if sort_order:
        lines.append(f"-- Sort-order candidates: {', '.join(sort_order)}")
    else:
        lines.append("-- Sort-order candidates: unavailable from current profile.")
    lines.append("")
    if segmentation or sort_order:
        ordered = ", ".join(sort_order or segmentation)
        segmented = segmentation[0] if segmentation else "/* choose_segmentation_key */"
        lines.append(
            f"""-- Example projection skeleton:
-- CREATE PROJECTION {schema}.{table}_pp_auto
-- AS SELECT * FROM {schema}.{table}
-- ORDER BY {ordered}
-- SEGMENTED BY HASH({segmented}) ALL NODES;"""
        )
    return "\n".join(lines) + "\n"


def _design_markdown(
    segmentation: list[str],
    partitions: list[str],
    sort_order: list[str],
    materialize: list[str],
) -> str:
    return f"""## Physical Design Advice

- Segmentation candidates: {_render_list(segmentation)}
- Partition candidates: {_render_list(partitions)}
- Sort-order candidates: {_render_list(sort_order)}
- Semi-structured/materialization candidates: {_render_list(materialize)}

These are first-pass hints from source-profile evidence only. Validate them against actual predicates, joins, concurrency, load cadence, and retention policy before applying in Vertica.
"""


def _render_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none from current profile"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out

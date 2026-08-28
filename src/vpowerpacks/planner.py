from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re

from .design import DesignAdvice, build_design_advice
from .profiler import ColumnProfile, SourceProfile


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class IngestPlan:
    profile: SourceProfile
    create_table_sql: str
    external_table_sql: str
    copy_sql: str
    copy_batches_sql: str
    design_advice_sql: str
    markdown: str


def build_ingest_plan(
    profile: SourceProfile,
    schema: str,
    table: str,
    *,
    batch_target_bytes: int = 256 * 1024**3,
    batch_max_files: int = 512,
) -> IngestPlan:
    _validate_identifier(schema, "schema")
    _validate_identifier(table, "table")
    if batch_target_bytes <= 0:
        raise ValueError("batch_target_bytes must be positive.")
    if batch_max_files <= 0:
        raise ValueError("batch_max_files must be positive.")
    columns = profile.columns or [
        ColumnProfile(name="raw_payload", observed_types=["unknown"], recommended_vertica_type="LONG VARCHAR")
    ]
    create_sql = _create_table_sql(schema, table, columns)
    external_sql = _external_table_sql(profile, schema, table, columns)
    copy_sql = _copy_sql(profile, schema, table)
    batches = build_copy_batches(profile, batch_target_bytes=batch_target_bytes, batch_max_files=batch_max_files)
    copy_batches_sql = _copy_batches_sql(profile, schema, table, batches)
    design_advice = build_design_advice(profile, schema, table)
    markdown = _markdown(profile, schema, table, batches, batch_target_bytes, batch_max_files, design_advice)
    return IngestPlan(profile, create_sql, external_sql, copy_sql, copy_batches_sql, design_advice.sql, markdown)


def _validate_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe Vertica {label} identifier: {value!r}. Use letters, numbers, and underscores only.")


def write_plan(plan: IngestPlan, output: str | Path) -> None:
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "source_profile.json").write_text(json.dumps(plan.profile.to_dict(), indent=2) + "\n", encoding="utf-8")
    (out / "vertica_create_table.sql").write_text(plan.create_table_sql, encoding="utf-8")
    (out / "vertica_external_table.sql").write_text(plan.external_table_sql, encoding="utf-8")
    (out / "vertica_copy_load.sql").write_text(plan.copy_sql, encoding="utf-8")
    (out / "vertica_copy_batches.sql").write_text(plan.copy_batches_sql, encoding="utf-8")
    (out / "vertica_physical_design_advice.sql").write_text(plan.design_advice_sql, encoding="utf-8")
    (out / "INGEST_PLAN.md").write_text(plan.markdown, encoding="utf-8")


def build_copy_batches(
    profile: SourceProfile,
    *,
    batch_target_bytes: int = 256 * 1024**3,
    batch_max_files: int = 512,
) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_bytes = 0
    for obj in profile.objects:
        obj_size = obj.size_bytes or 0
        should_flush = current and (
            len(current) >= batch_max_files or (current_bytes + obj_size > batch_target_bytes and current_bytes > 0)
        )
        if should_flush:
            batches.append(current)
            current = []
            current_bytes = 0
        current.append(obj.uri)
        current_bytes += obj_size
    if current:
        batches.append(current)
    return batches


def _create_table_sql(schema: str, table: str, columns: list[ColumnProfile]) -> str:
    cols = ",\n".join(f"  {col.name} {col.recommended_vertica_type}" for col in columns)
    return f"""CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.{table} (
{cols}
);
"""


def _external_table_sql(profile: SourceProfile, schema: str, table: str, columns: list[ColumnProfile]) -> str:
    if not profile.columns and profile.detected_format in {"csv", "parquet"}:
        return (
            "-- External table SQL unavailable: column metadata was not inferred.\n"
            "-- Provide a local sample file, explicit schema, or optional metadata dependency before generating executable SQL.\n"
        )
    cols = ",\n".join(f"  {col.name} {col.recommended_vertica_type}" for col in columns)
    source = _source_pattern(profile)
    parser = _parser(profile.detected_format)
    if profile.detected_format == "unknown":
        return "-- External table SQL unavailable: source format was not recognized.\n"
    return f"""-- Draft external-table path. Validate syntax and credentials in the target Vertica version.
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE EXTERNAL TABLE {schema}.{table}_ext (
{cols}
)
AS COPY FROM {_sql_string_literal(source)}
{parser};
"""


def _copy_sql(profile: SourceProfile, schema: str, table: str) -> str:
    source = _source_pattern(profile)
    parser = _parser(profile.detected_format)
    if profile.detected_format == "unknown":
        parser = "DELIMITER ','"
    return f"""-- Draft bulk-load path. Prefer this for hot partitions and repeated analytics.
COPY {schema}.{table}
FROM {_sql_string_literal(source)}
{parser}
REJECTED DATA AS TABLE {schema}.{table}_rejects;
"""


def _copy_batches_sql(profile: SourceProfile, schema: str, table: str, batches: list[list[str]]) -> str:
    if not batches:
        return "-- No COPY batches generated because the source profile has no retained object samples.\n"
    if profile.source_kind == "s3_inventory" and profile.total_object_count > len(profile.objects):
        return (
            "-- COPY batch SQL intentionally omitted for inventory-scale sources.\n"
            "-- The profile retained sampled objects only. Generate executable batches from a complete manifest\n"
            "-- in the controlled runtime where object-store access and retry policy are configured.\n"
        )
    parser = _parser(profile.detected_format)
    if profile.detected_format == "unknown":
        parser = "DELIMITER ','"
    statements = [
        "-- Draft COPY batch plan. Validate credentials, parser options, and resource pools before execution.",
        f"-- Batches: {len(batches)}",
    ]
    for idx, uris in enumerate(batches, start=1):
        sources = ",\n  ".join(_sql_string_literal(uri) for uri in uris)
        statements.append(
            f"""-- Batch {idx}: {len(uris)} file(s)
COPY {schema}.{table}
FROM
  {sources}
{parser}
REJECTED DATA AS TABLE {schema}.{table}_rejects;"""
        )
    return "\n\n".join(statements) + "\n"


def _source_pattern(profile: SourceProfile) -> str:
    if profile.source_kind == "s3_inventory":
        return profile.source_uri.rstrip("/") + "/*"
    if len(profile.objects) == 1:
        return profile.objects[0].uri
    parent = str(Path(profile.objects[0].uri).parent)
    suffixes = {Path(obj.uri).suffix for obj in profile.objects}
    suffix = suffixes.pop() if len(suffixes) == 1 else "*"
    return f"{parent}/*{suffix if suffix != '*' else ''}"


def _parser(fmt: str) -> str:
    if fmt == "csv":
        return "DELIMITER ',' ENCLOSED BY '\"' SKIP 1"
    if fmt == "parquet":
        return "PARQUET"
    if fmt in {"json", "jsonl"}:
        return "PARSER FJSONPARSER()"
    return ""


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _markdown(
    profile: SourceProfile,
    schema: str,
    table: str,
    batches: list[list[str]],
    batch_target_bytes: int,
    batch_max_files: int,
    design_advice: DesignAdvice,
) -> str:
    caveats = "\n".join(f"- {item}" for item in profile.caveats) or "- None from profiler."
    columns = "\n".join(
        f"- `{col.name}`: {col.recommended_vertica_type} from {', '.join(col.observed_types)}"
        for col in profile.columns
    ) or "- No columns inferred; use a sampled file or optional metadata dependency."
    if profile.source_kind == "s3_inventory" and profile.total_object_count > len(profile.objects):
        batch_summary = (
            f"- Inventory-scale source: retained {len(profile.objects)} sample objects from "
            f"{profile.total_object_count} total objects.\n"
            "- Executable COPY batches require the full manifest in the controlled runtime."
        )
    else:
        batch_summary = (
            f"- Planned COPY batches from retained objects: {len(batches)}\n"
            f"- Target bytes per batch: {batch_target_bytes}\n"
            f"- Max files per batch: {batch_max_files}"
        )
    return f"""# Vertica Ingest Plan

## Source

- URI: `{profile.source_uri}`
- Kind: `{profile.source_kind}`
- Detected format: `{profile.detected_format}`
- Objects: {profile.total_object_count}
- Known bytes: {profile.total_known_bytes}
- Profiled object samples retained: {len(profile.objects)}
- Sampled rows: {profile.row_sample_count}

## Target

- Schema: `{schema}`
- Table: `{table}`

## Inferred Columns

{columns}

## Recommended Flow

1. Use the generated external table for smoke tests, schema validation, and cold-data exploration.
2. Use the generated `COPY` load for hot partitions and repeated analytics.
3. After load, add projections, segmentation, and partitioning based on actual workload predicates.
4. Track rejects as a first-class data-quality signal.
5. Benchmark external read, bulk load, and loaded-table query performance separately.

## COPY Batch Planning

{batch_summary}

{design_advice.markdown}

## Caveats

{caveats}
"""

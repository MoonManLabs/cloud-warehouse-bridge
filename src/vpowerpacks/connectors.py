from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


IDENTIFIER_PART_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SOURCE_TYPES = {"databricks", "postgres", "snowflake", "sqlserver"}


@dataclass
class ConnectorPlan:
    source_type: str
    source_table: str
    target_schema: str
    target_table: str
    extract_sql: str
    landing_sql: str
    copy_sql: str
    markdown: str


def build_connector_plan(
    *,
    source_type: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    output_format: str = "csv",
    incremental_column: str | None = None,
) -> ConnectorPlan:
    normalized_source_type = source_type.lower()
    if normalized_source_type not in SOURCE_TYPES:
        raise ValueError(
            f"Unsupported source type: {source_type!r}. "
            "Use databricks, postgres, snowflake, or sqlserver."
        )
    _validate_qualified_name(source_table, "source_table")
    _validate_identifier(target_schema, "target_schema")
    _validate_identifier(target_table, "target_table")
    if incremental_column:
        _validate_identifier(incremental_column, "incremental_column")
    normalized_format = output_format.lower()
    if normalized_format not in {"csv", "parquet"}:
        raise ValueError("output_format must be csv or parquet.")

    extract_sql = _extract_sql(normalized_source_type, source_table, incremental_column)
    landing_sql = _landing_sql(target_schema, target_table)
    copy_sql = _connector_copy_sql(target_schema, target_table, normalized_format)
    markdown = _connector_markdown(
        normalized_source_type,
        source_table,
        target_schema,
        target_table,
        normalized_format,
        incremental_column,
    )
    return ConnectorPlan(
        source_type=normalized_source_type,
        source_table=source_table,
        target_schema=target_schema,
        target_table=target_table,
        extract_sql=extract_sql,
        landing_sql=landing_sql,
        copy_sql=copy_sql,
        markdown=markdown,
    )


def write_connector_plan(plan: ConnectorPlan, output: str | Path) -> None:
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "source_extract.sql").write_text(plan.extract_sql, encoding="utf-8")
    (out / "vertica_landing_table.sql").write_text(plan.landing_sql, encoding="utf-8")
    (out / "vertica_connector_copy.sql").write_text(plan.copy_sql, encoding="utf-8")
    (out / "CONNECTOR_PLAN.md").write_text(plan.markdown, encoding="utf-8")


def _extract_sql(source_type: str, source_table: str, incremental_column: str | None) -> str:
    where = ""
    if incremental_column and source_type == "postgres":
        where = f"\nWHERE {incremental_column} >= :last_successful_watermark"
    elif incremental_column and source_type == "sqlserver":
        where = f"\nWHERE {incremental_column} >= @last_successful_watermark"
    elif incremental_column and source_type in {"databricks", "snowflake"}:
        where = f"\nWHERE {incremental_column} >= '{{LAST_SUCCESSFUL_WATERMARK}}'"

    if source_type == "postgres":
        return f"""-- PostgreSQL snapshot extract template.
-- Use psql \\copy, a server-side COPY, or a controlled extractor process.
SELECT *
FROM {source_table}{where}
ORDER BY 1;
"""
    if source_type == "sqlserver":
        return f"""-- SQL Server snapshot extract template.
-- Use bcp, sqlcmd, or a controlled extractor process.
SELECT *
FROM {source_table}{where}
ORDER BY 1;
"""
    if source_type == "databricks":
        return f"""-- Databricks export template.
-- Use Databricks SQL for metadata/sampling and a Databricks job for large exports.
-- For production-scale movement, write curated output to object storage as Parquet.
CREATE OR REPLACE TEMP VIEW vertica_powerpack_export AS
SELECT *
FROM {source_table}{where};

-- Example Spark/SQL export shape. Review storage path, partitioning, and permissions.
-- INSERT OVERWRITE DIRECTORY 's3://example-landing/databricks/{source_table.replace('.', '/')}/'
-- USING PARQUET
-- SELECT * FROM vertica_powerpack_export;
"""
    return f"""-- Snowflake unload template.
-- Use COPY INTO an external stage for production-scale exports.
COPY INTO @example_external_stage/{source_table.replace('.', '/')}/
FROM (
  SELECT *
  FROM {source_table}{where}
)
FILE_FORMAT = (TYPE = PARQUET)
OVERWRITE = FALSE;
"""


def _landing_sql(schema: str, table: str) -> str:
    return f"""-- Draft landing table. Replace column definitions after profiling the extract sample.
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.{table}_landing (
  raw_payload LONG VARCHAR,
  source_file VARCHAR(2048),
  loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _connector_copy_sql(schema: str, table: str, output_format: str) -> str:
    parser = "PARQUET" if output_format == "parquet" else "DELIMITER ',' ENCLOSED BY '\"' SKIP 1"
    return f"""-- Draft Vertica load template for connector extracts.
-- Replace the source URI with the controlled object-store or filesystem landing path.
COPY {schema}.{table}_landing
FROM 's3://example-landing/{schema}/{table}/*'
{parser}
REJECTED DATA AS TABLE {schema}.{table}_landing_rejects;
"""


def _connector_markdown(
    source_type: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    output_format: str,
    incremental_column: str | None,
) -> str:
    incremental = (
        f"`{incremental_column}` watermark filter included in the extract template."
        if incremental_column
        else "No incremental column provided; this is a full-snapshot template."
    )
    source_notes = _source_notes(source_type)
    return f"""# Vertica Connector Plan

## Source

- Source type: `{source_type}`
- Source table: `{source_table}`
- Extract mode: {incremental}
- Extract artifact format: `{output_format}`

## Source-Specific Guidance

{source_notes}

## Target

- Schema: `{target_schema}`
- Landing table: `{target_schema}.{target_table}_landing`

## Flow

1. Extract from the source database using its native client or a controlled extractor.
2. Write immutable files to a landing path.
3. Profile a small extract sample with `vpowerpacks plan`.
4. Generate typed Vertica DDL from the profile before production loads.
5. Load into Vertica with explicit reject capture.
6. Promote from landing into typed target tables only after row counts, rejects, and checksums pass.

## Safety

- This plan does not connect to the source database.
- This plan does not connect to Vertica.
- Generated SQL is a review artifact until an operator applies it.
- Incremental extraction requires a durable watermark store outside this template.
"""


def _source_notes(source_type: str) -> str:
    if source_type == "databricks":
        return (
            "- Use Databricks SQL/JDBC for metadata, sampling, and control queries.\n"
            "- Use a Databricks/Spark job to export large curated datasets as Parquet to object storage.\n"
            "- Treat Delta-specific behavior, nested fields, arrays/maps, timestamps, and partition layout as migration readiness checks before Vertica load."
        )
    if source_type == "snowflake":
        return (
            "- Use Snowflake `COPY INTO` to unload table/query results to an external stage.\n"
            "- Prefer Parquet for typed bulk movement unless CSV is required for operational compatibility.\n"
            "- Validate stage permissions, file sizing, compression, and unload query determinism before Vertica load."
        )
    if source_type == "postgres":
        return "- Use native PostgreSQL export tooling or a controlled extractor. Keep production credentials outside generated artifacts."
    return "- Use native SQL Server export tooling or a controlled extractor. Keep production credentials outside generated artifacts."


def _validate_qualified_name(value: str, label: str) -> None:
    parts = value.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"Unsafe {label}: {value!r}. Use one to three dot-separated identifiers.")
    for part in parts:
        _validate_identifier(part, label)


def _validate_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_PART_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe {label}: {value!r}. Use letters, numbers, and underscores only.")

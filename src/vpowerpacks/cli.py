from __future__ import annotations

import argparse

from .connectors import build_connector_plan, write_connector_plan
from .offload import build_offload_assessment, write_offload_assessment
from .planner import build_ingest_plan, write_plan
from .profiler import profile_inventory_csv, profile_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vpowerpacks")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Profile a source and generate Vertica ingest SQL.")
    plan.add_argument("--source", required=True, help="Local path or s3:// URI.")
    plan.add_argument("--inventory-csv", help="Optional object inventory CSV with key/uri/path/object and size columns.")
    plan.add_argument("--schema-sample", help="Optional local sample file used to infer columns for an inventory source.")
    plan.add_argument("--format-hint", default="parquet", help="Format hint for inventory-only planning.")
    plan.add_argument("--schema", required=True, help="Target Vertica schema.")
    plan.add_argument("--table", required=True, help="Target Vertica table.")
    plan.add_argument("--output", required=True, help="Output directory for generated plan artifacts.")
    plan.add_argument("--sample-rows", type=int, default=1000, help="Rows to sample for text formats.")
    plan.add_argument("--batch-target-gib", type=float, default=256.0, help="Target GiB per COPY batch.")
    plan.add_argument("--batch-max-files", type=int, default=512, help="Maximum files per COPY batch.")

    connector = sub.add_parser("connector-plan", help="Generate a safe source-database extract and Vertica landing plan.")
    connector.add_argument("--source-type", required=True, choices=["databricks", "postgres", "snowflake", "sqlserver"])
    connector.add_argument("--source-table", required=True, help="Source table name, optionally schema-qualified.")
    connector.add_argument("--target-schema", required=True, help="Target Vertica schema.")
    connector.add_argument("--target-table", required=True, help="Target Vertica table stem.")
    connector.add_argument("--output", required=True, help="Output directory for generated connector artifacts.")
    connector.add_argument("--output-format", choices=["csv", "parquet"], default="csv")
    connector.add_argument("--incremental-column", help="Optional source timestamp/id column for incremental extracts.")

    offload = sub.add_parser(
        "offload-advisor",
        help="Generate a neutral Databricks/Snowflake to Vertica workload-fit assessment.",
    )
    offload.add_argument("--source-type", required=True, choices=["databricks", "snowflake"])
    offload.add_argument("--workload-name", required=True)
    offload.add_argument("--domain", default="general analytics")
    offload.add_argument("--data-volume-tib", required=True, type=float)
    offload.add_argument("--monthly-runs", required=True, type=int)
    offload.add_argument("--avg-runtime-minutes", required=True, type=float)
    offload.add_argument("--concurrency", required=True, type=int)
    offload.add_argument("--retention-days", required=True, type=int)
    offload.add_argument("--stable-schema", action="store_true")
    offload.add_argument("--object-store-path", default="s3://example-landing/workload/")
    offload.add_argument("--output", required=True, help="Output directory for generated offload assessment.")

    args = parser.parse_args(argv)
    if args.command == "plan":
        if args.inventory_csv:
            profile = profile_inventory_csv(args.inventory_csv, args.source, format_hint=args.format_hint)
            if args.schema_sample:
                sample_profile = profile_source(args.schema_sample, sample_rows=args.sample_rows)
                profile.columns = sample_profile.columns
                profile.row_sample_count = sample_profile.row_sample_count
                profile.caveats.append(f"Columns inferred from local schema sample: {args.schema_sample}.")
        else:
            profile = profile_source(args.source, sample_rows=args.sample_rows)
        ingest_plan = build_ingest_plan(
            profile,
            args.schema,
            args.table,
            batch_target_bytes=int(args.batch_target_gib * 1024**3),
            batch_max_files=args.batch_max_files,
        )
        write_plan(ingest_plan, args.output)
        print(f"Wrote Vertica ingest plan to {args.output}")
        return 0
    if args.command == "connector-plan":
        connector_plan = build_connector_plan(
            source_type=args.source_type,
            source_table=args.source_table,
            target_schema=args.target_schema,
            target_table=args.target_table,
            output_format=args.output_format,
            incremental_column=args.incremental_column,
        )
        write_connector_plan(connector_plan, args.output)
        print(f"Wrote Vertica connector plan to {args.output}")
        return 0
    if args.command == "offload-advisor":
        assessment = build_offload_assessment(
            source_type=args.source_type,
            workload_name=args.workload_name,
            domain=args.domain,
            data_volume_tib=args.data_volume_tib,
            monthly_runs=args.monthly_runs,
            avg_runtime_minutes=args.avg_runtime_minutes,
            concurrency=args.concurrency,
            retention_days=args.retention_days,
            stable_schema=args.stable_schema,
            object_store_path=args.object_store_path,
        )
        write_offload_assessment(assessment, args.output)
        print(f"Wrote Vertica offload assessment to {args.output}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

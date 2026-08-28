# Vertica Cloud Warehouse Bridge

Open-source planning and integration tools for evaluating governed analytical workloads across Databricks, Snowflake, object storage, and Vertica.

This is an independent experimental integration for Vertica. It is not an official Rocket Software or Vertica product unless Rocket Software explicitly designates it that way.

This project does not modify Vertica internals and does not copy ClickHouse or StarRocks source. Competing open-source systems can be studied for behavior and ergonomics, but implementation here must use original code and public Vertica interfaces.

Generate reproducible connector plans, object-store handoff patterns, workload-fit assessments, and evidence for architectures where Vertica may serve as a governed high-compute analytical engine.

## What This Is Not

- Not a universal migration tool.
- Not a Databricks replacement.
- Not a Snowflake replacement.
- Not proof that Vertica is always cheaper.
- Not proof that Vertica is always faster.
- Not an official Rocket Software or Vertica product.
- Not a supported Rocket migration utility.

## First Pack: Ingest And Lake Planner

The MVP profiles a source location and generates a practical Vertica ingest plan:

- source inventory for local paths and S3-style URIs;
- lightweight CSV, JSON Lines, and Parquet metadata inference;
- draft landing-table DDL;
- draft external-table SQL where appropriate;
- draft `COPY` load SQL;
- operational notes for hot/cold materialization, rejects, and benchmark hygiene.

## Usage

```bash
python -m vpowerpacks plan \
  --source examples/sample_data/properties.csv \
  --schema powerpack_demo \
  --table properties \
  --output /tmp/vertica_power_pack_plan
```

For large object stores, use manifest mode so the planner reads an inventory instead of traversing the full bucket:

```bash
python -m vpowerpacks plan \
  --source s3://example-bucket/example-events \
  --inventory-csv s3_inventory.csv \
  --format-hint parquet \
  --schema powerpack_demo \
  --table events \
  --output /tmp/vertica_power_pack_plan
```

Inventory CSV columns:

- object key: `key`, `uri`, `path`, or `object`
- object size: `size_bytes`, `size`, or `bytes`

Manifest mode keeps only sampled object examples in the profile while preserving total object count and total known bytes.

Generated files:

- `source_profile.json`
- `vertica_create_table.sql`
- `vertica_external_table.sql`
- `vertica_copy_load.sql`
- `vertica_copy_batches.sql`
- `vertica_physical_design_advice.sql`
- `INGEST_PLAN.md`

## Connector Planning

The `connector-plan` command generates safe source-database extract templates and Vertica landing/load artifacts without connecting to any database:

```bash
python -m vpowerpacks connector-plan \
  --source-type postgres \
  --source-table public.orders \
  --target-schema powerpack_demo \
  --target-table orders \
  --incremental-column updated_at \
  --output /tmp/vertica_power_pack_connector_plan
```

Supported dry-run source templates:

- Databricks
- PostgreSQL
- Snowflake
- SQL Server

Generated connector files:

- `source_extract.sql`
- `vertica_landing_table.sql`
- `vertica_connector_copy.sql`
- `CONNECTOR_PLAN.md`

The connector planner is intentionally conservative. It produces reviewable templates, not live extracts, credential handling, replication, or destructive database changes.

## Cloud Offload Advisor

The `offload-advisor` command turns workload facts into a neutral assessment for Databricks or Snowflake offload conversations:

```bash
python -m vpowerpacks offload-advisor \
  --source-type databricks \
  --workload-name cdr_rollups \
  --domain telco \
  --data-volume-tib 75 \
  --monthly-runs 400 \
  --avg-runtime-minutes 45 \
  --concurrency 25 \
  --retention-days 730 \
  --stable-schema \
  --object-store-path s3://example-landing/telco/cdr_rollups/ \
  --output /tmp/vertica_power_pack_offload_advisor
```

Generated advisor files:

- `OFFLOAD_ADVISOR_REPORT.md`

The advisor does not assume every workload should move to Vertica. It produces one of four outcome classes: `GOOD_VERTICA_FIT`, `POSSIBLE_VERTICA_FIT`, `INSUFFICIENT_EVIDENCE`, or `KEEP_ON_CURRENT_PLATFORM`.

The report separates input facts, fit signals, counter-signals, unknown evidence, assessment, rationale, and next validation steps. It is not a savings guarantee or performance benchmark. It identifies where Vertica may deserve a measured pilot and where the current Databricks or Snowflake path may remain the better operational choice.

## Architecture Boundary

The Bridge explores a reviewed object-store handoff pattern:

1. Databricks or Snowflake remains the source platform for platform-native workloads, metadata, sampling, and curated export/unload jobs.
2. Curated outputs are written to object storage, usually Parquet for bulk analytical movement.
3. Vertica Cloud Warehouse Bridge inventories the landing layout, samples schema evidence where available, and generates draft Vertica SQL and validation notes.
4. Operators choose between external-table exploration, loaded-table performance, or rejecting the candidate until evidence improves.

The project uses public interfaces only. It does not connect to private Databricks, Snowflake, or Vertica systems by default and does not contain credentials.

## Scale Position

The MVP is not yet a 100 TB data mover. It is a planning tool that has been designed around the pattern needed for 100s-TB environments:

- manifest-driven inventory;
- bounded metadata samples;
- generated SQL and load plans;
- bounded COPY batch planning for retained file samples;
- first-pass Vertica physical-design advice from profile evidence;
- explicit external-read vs loaded-table paths;
- fail-closed behavior when schema evidence is missing.

The current proof point is a reproducible MinIO run that profiles a synthetic object-store layout, generates SQL, and records bounded planner timing and memory behavior. This validates the planner and inventory path, not end-to-end production transfer throughput.

## Publish Boundary

Safe to publish later after:

- secret scan passes;
- generated local lab artifacts are excluded unless explicitly sanitized and listed in `PUBLICATION_MANIFEST.md`;
- license review confirms dependency and reference-source boundaries;
- the maintainer explicitly approves public/private visibility and repository name.

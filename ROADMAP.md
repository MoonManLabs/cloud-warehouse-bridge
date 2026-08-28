# Roadmap

Preferred product framing: Cloud Warehouse Bridge.

Short description: Open-source planning and integration tools for evaluating governed analytical workloads across Databricks, Snowflake, object storage, and Vertica.

## Pack 1: Ingest And Lake Accelerator

Purpose: make Vertica ingestion and object-store workflows easier to plan, benchmark, and repeat without requiring Vertica source-code access.

### MVP

- Profile local CSV, JSON Lines, and Parquet samples.
- Accept S3-style URIs in safe metadata-only mode.
- Generate draft Vertica landing-table DDL.
- Generate draft Vertica external-table SQL.
- Generate draft Vertica `COPY` load SQL with reject capture.
- Generate bounded sample-based `COPY` batch SQL.
- Produce an operator-readable ingest plan.
- Generate safe PostgreSQL and SQL Server connector extract/landing templates.
- Generate safe Databricks and Snowflake export/unload-to-object-store templates.
- Generate first-pass Vertica physical-design advice from profile evidence.
- Generate neutral cloud offload advisor reports for governed high-compute Databricks/Snowflake workload conversations.

### Next Build Steps

- Add real S3 listing/profile mode through optional `boto3`.
- Add MinIO test harness against a disposable local S3-compatible endpoint.
- Expand COPY batch planning into a resumable manifest executor with retry metadata.
- Add source-specific adapters:
  - PostgreSQL snapshot extractor beyond dry-run templates.
  - SQL Server snapshot extractor beyond dry-run templates.
  - Databricks metadata/sampling connector through public drivers.
  - Snowflake metadata/sampling connector through public drivers.
  - Cloud warehouse/lakehouse offload readiness reports.
  - CSV/Parquet directory watcher.
  - Debezium/Kafka CDC plan generator.
- Add Vertica physical-design advisor:
  - workload-aware projection suggestions;
  - measured segmentation candidate validation;
  - measured partition candidate validation;
  - sort-order candidate validation;
  - hot/cold materialization recommendations.
- Add benchmark harness:
  - external read timing;
  - bulk load timing;
  - loaded-table query timing;
  - reject-rate tracking;
  - recovery/retry behavior.

## Pack 2: Semi-Structured Modernizer

Purpose: wrap Vertica Flex Tables and JSON/semi-structured workflows in a modern discovery and promotion experience.

- Raw JSON landing.
- Key discovery.
- Type drift tracking.
- Generated typed views.
- Generated typed tables for hot fields.
- Data-quality summary.

## Pack 3: Connector And API Pack

Purpose: give Vertica a cleaner application-facing surface for operational teams.

- Postgres connector.
- SQL Server connector.
- Databricks export/offload planner.
- Snowflake unload/offload planner.
- REST query/job API.
- Export API.
- Optional Arrow Flight-style result transport investigation.

## Pack 4: Cloud Warehouse Bridge Advisor

Purpose: make it easier to evaluate whether Vertica deserves a measured pilot as a governed high-compute engine for repeatable analytics currently running in Databricks or Snowflake.

- Workload-fit scoring from public/user-provided facts.
- Explicit outcome classes: `GOOD_VERTICA_FIT`, `POSSIBLE_VERTICA_FIT`, `INSUFFICIENT_EVIDENCE`, and `KEEP_ON_CURRENT_PLATFORM`.
- First-class counter-signals and missing-evidence sections.
- Databricks/Snowflake object-store handoff templates.
- Cost/offload-model inputs without making unsupported savings claims.
- Telco-style use-case narratives for CDR, telemetry, QoE/QoS, fraud, capacity planning, and billing reconciliation.
- Product-marketing translation from technical Vertica strengths to customer outcomes.
- Native-integration opportunity notes for Vertica Engineering.

## Publication Gates

- No secrets in source, examples, logs, or generated artifacts.
- No copied code from ClickHouse, StarRocks, Vertica, or other vendor repositories.
- Dependency license review.
- Replace internal lab names and paths with generic examples.
- Decide public vs private GitHub visibility.
- Add explicit open-source license only after approval.

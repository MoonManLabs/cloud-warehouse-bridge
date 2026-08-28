# Architecture Boundary

## Product Framing

Vertica Cloud Warehouse Bridge is an independent experimental planning project for evaluating governed analytical workloads across Databricks, Snowflake, object storage, and Vertica.

It generates reproducible connector plans, object-store handoff patterns, workload-fit assessments, and evidence for architectures where Vertica may serve as a governed high-compute analytical engine.

## Interfaces Used

- Databricks: public SQL/export patterns for writing curated results to object storage.
- Snowflake: public unload patterns using `COPY INTO` to external stages.
- Object storage: public S3-compatible URI and inventory concepts.
- Vertica: public SQL, `COPY`, external-table, parser, landing-table, and reject-handling patterns.

## What The Tool Does

1. Profiles local files or inventory manifests.
2. Generates draft Vertica landing/external/COPY SQL.
3. Produces safe dry-run connector templates for PostgreSQL, SQL Server, Databricks, and Snowflake.
4. Evaluates Databricks/Snowflake workload facts with neutral outcome classes.
5. Documents fit signals, counter-signals, unknowns, rationale, and next validation steps.

## What The Tool Does Not Do

- It does not run live migrations.
- It does not connect to Databricks, Snowflake, or Vertica by default.
- It does not manage credentials.
- It does not modify Vertica internals.
- It does not reproduce Vertica, Databricks, Snowflake, ClickHouse, or StarRocks behavior.
- It does not guarantee performance improvement.
- It does not guarantee cost savings.
- It does not claim that Databricks or Snowflake should be replaced.
- It does not claim official Rocket Software or Vertica endorsement.

## Evidence Standard

Generated plans and advisor reports are review artifacts. Any production decision should be based on a measured pilot that captures:

- source export or unload time;
- object-store layout and file-size evidence;
- Vertica load or external-read behavior;
- query runtime on target workloads;
- reject/reconciliation results;
- operational complexity;
- current and proposed cost model inputs.

Results from local labs are limited to their documented configuration and should not be treated as universal performance claims.

## Evidence Labels

- Generated plan: SQL, Markdown, or command templates emitted by the tool for operator review.
- Example: synthetic sample data, placeholder object paths, or illustrative CLI commands.
- Measured: timing, memory, test, or build result produced by an executed validation step.
- Observed: behavior witnessed during a lab run but not enough by itself to become a general claim.
- Inferred: interpretation drawn from measured or observed evidence.
- Hypothesized: plausible product, performance, cost, or architecture opportunity that still requires validation.

# Changelog

## 0.1.0-rc1

- Adopted Vertica Cloud Warehouse Bridge as the preferred product framing.
- Added clean-room Vertica ingest/lake planner.
- Added CSV, JSON Lines, local Parquet metadata, S3 URI, and inventory CSV profiling.
- Added manifest-driven object-store planning with bounded retained object samples.
- Added draft Vertica landing table, external table, and `COPY` SQL generation.
- Added bounded sample-based `COPY` batch SQL generation.
- Added safe PostgreSQL and SQL Server connector-plan templates.
- Added safe Databricks and Snowflake connector-plan templates for object-store export/unload workflows.
- Added neutral cloud offload advisor reports for Databricks/Snowflake high-compute workload-fit conversations.
- Added explicit offload outcome classes and counter-signal reporting so the advisor can recommend keeping a workload on the current platform when evidence does not support a Vertica pilot.
- Added architecture boundary documentation for public-interface claims and non-goals.
- Added first-pass Vertica physical-design advice for segmentation, partition, sort-order, and materialization candidates.
- Added MinIO proof helper for synthetic object-store layouts.
- Added publication gate documents for provenance, security, contribution, license recommendation, and native integration notes.
- Added target identifier validation to avoid generating unsafe schema/table SQL.

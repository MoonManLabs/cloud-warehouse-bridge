# Vertica Ingest Plan

## Source

- URI: `s3://vpowerpack-demo/vpowerpacks/e2e-copy-proof`
- Kind: `s3_inventory`
- Detected format: `csv`
- Objects: 3
- Known bytes: 4702058
- Profiled object samples retained: 3
- Sampled rows: 1000

## Target

- Schema: `vpp_e2e`
- Table: `events`

## Inferred Columns

- `event_id`: VARCHAR(1024) from string
- `event_id_num`: INT from int
- `tenant_id`: VARCHAR(1024) from string
- `event_date`: DATE from date
- `amount_cents`: INT from int

## Recommended Flow

1. Use the generated external table for smoke tests, schema validation, and cold-data exploration.
2. Use the generated `COPY` load for hot partitions and repeated analytics.
3. After load, add projections, segmentation, and partitioning based on actual workload predicates.
4. Track rejects as a first-class data-quality signal.
5. Benchmark external read, bulk load, and loaded-table query performance separately.

## COPY Batch Planning

- Planned COPY batches from retained objects: 1
- Target bytes per batch: 274877906944
- Max files per batch: 512

## Physical Design Advice

- Segmentation candidates: `event_id`, `event_id_num`, `tenant_id`
- Partition candidates: `event_date`, `amount_cents`
- Sort-order candidates: `tenant_id`, `amount_cents`, `event_date`, `event_id`, `event_id_num`
- Semi-structured/materialization candidates: none from current profile

These are first-pass hints from source-profile evidence only. Validate them against actual predicates, joins, concurrency, load cadence, and retention policy before applying in Vertica.


## Caveats

- Inventory mode is manifest-driven; sampled objects are retained in the profile, not the full object list.
- Use a sampled data file or Parquet metadata pass to infer columns before emitting executable external-table SQL.

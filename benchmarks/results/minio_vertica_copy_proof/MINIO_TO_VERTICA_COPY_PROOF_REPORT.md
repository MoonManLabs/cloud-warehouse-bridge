# MinIO To Vertica COPY Proof

## Result

PASSED

This proof uses synthetic CSV objects in MinIO, generates a Cloud Warehouse Bridge plan, loads the same objects into an isolated temporary Vertica container with `COPY`, and validates row counts, reconciliation sums, min/max identifiers, and rejected-row handling.

## Scope

- Object store: S3-compatible MinIO on the configured container network.
- Data: synthetic CSV only.
- Vertica path: public `COPY` syntax with S3 session parameters and rejected-data table.
- Database target: isolated temporary container `vpp-e2e-vertica-copy-proof`.
- Resource posture: bounded proof, container CPU-capped during load, not a throughput benchmark.

## Timings

- MinIO upload seconds: 0.510334
- MinIO recursive list seconds: 0.428756
- Power Pack plan seconds: 0.000521
- Total proof seconds: 25.813351
- Max harness RSS MB: 20.5

## Load Validation

| Dataset | Valid Rows | Load Seconds | Rows/Second | Reject Rows | Passed |
| --- | ---: | ---: | ---: | ---: | --- |
| small | 10000 | 2.207265 | 4530.493 | 0 | True |
| medium | 100000 | 2.378502 | 42043.262 | 0 | True |
| invalid | 99 | 2.175183 | 45.513 | 1 | True |

## Artifacts

- Generated plan: `benchmarks/results/minio_vertica_copy_proof/generated_plan`
- Metrics JSON: `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_proof_metrics.json`
- Metrics CSV: `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_proof_metrics.csv`
- Inventory CSV: `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_inventory.csv`

## Claim Boundary

- Proven here: bounded synthetic MinIO-to-Vertica `COPY` execution, generated-plan compatibility, row-count/reconciliation validation, and reject capture in an isolated lab container.
- Not proven here: production 100s-TB transfer throughput, customer-environment compatibility, Databricks/Snowflake live extraction, enterprise scheduler/retry behavior, or universal Vertica ingest performance.

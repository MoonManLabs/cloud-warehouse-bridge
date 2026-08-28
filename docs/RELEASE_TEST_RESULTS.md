# Release Test Results

Date: 2026-08-27, updated during final pre-publication red-team gate on 2026-08-28

Package/repository candidate: `vertica-cloud-warehouse-bridge`

## Local Package Validation

Measured:

- Editable install with development extras succeeded in a temporary virtual environment.
- Console script `vpowerpacks` generated a sample CSV ingest plan.
- Source distribution and wheel built successfully as `vertica_cloud_warehouse_bridge-0.1.0`.
- Python compile check passed for package modules and the MinIO proof helper.
- New `connector-plan` command generated PostgreSQL and SQL Server dry-run plans.
- New Databricks and Snowflake connector-plan templates generated object-store export/unload plans.
- New `offload-advisor` command generated neutral Databricks and Snowflake workload-fit reports.
- Advisor outputs now include explicit outcome classes, fit signals, counter-signals, unknown evidence, assessment, rationale, and next validation steps.
- New COPY batch artifact generation produced `vertica_copy_batches.sql`.
- Physical-design advice generation produced `vertica_physical_design_advice.sql`.
- Bounded MinIO-to-Vertica `COPY` proof generated synthetic data, generated a Power Pack plan, loaded into an isolated Vertica container, and validated rows, reconciliation sums, min/max IDs, and rejected rows.

Commands:

```bash
python3 -m venv /tmp/vpowerpacks_venv
/tmp/vpowerpacks_venv/bin/python -m pip install -e '.[dev]'
/tmp/vpowerpacks_venv/bin/python -m unittest discover -s tests -v
/tmp/vpowerpacks_venv/bin/vpowerpacks plan --source examples/sample_data/properties.csv --schema demo --table properties --output /tmp/vpowerpacks_console_script_plan
/tmp/vpowerpacks_venv/bin/python -m build --sdist --wheel --outdir /tmp/vpowerpacks_dist
```

## Unit Tests

Measured:

- 20 tests passed.
- Covered CSV profiling, JSON Lines profiling, compressed suffix detection, inventory scale summarization, schema-sampled inventory SQL generation, generated Vertica SQL artifacts, SQL source-literal escaping, COPY batch splitting, physical-design advice, connector-plan generation for PostgreSQL/SQL Server/Databricks/Snowflake, all four neutral offload-advisor outcomes, keep-current-platform counter-signal behavior, invalid source handling, and unsafe identifier rejection.

## Quickstart Validation

Measured:

- CSV quickstart plan generation passed.
- JSON Lines quickstart plan generation passed.
- PostgreSQL connector-plan dry run passed.
- SQL Server connector-plan dry run passed.
- Databricks connector-plan dry run passed.
- Snowflake connector-plan dry run passed.
- Databricks telco offload-advisor dry run passed.
- Databricks moderate-signal offload-advisor dry run passed and returned `POSSIBLE_VERTICA_FIT`.
- Snowflake insufficient-evidence offload-advisor dry run passed and returned `INSUFFICIENT_EVIDENCE`.
- Snowflake low-signal offload-advisor dry run passed and returned `KEEP_ON_CURRENT_PLATFORM`.
- Fresh editable install after package rename passed in a separate temporary virtual environment.
- Built-wheel install passed in a clean temporary virtual environment.
- Installed wheel console script generated a CSV plan, a low-signal Snowflake advisor report, and a Databricks connector plan.

## Fresh MinIO Proof

Measured against a disposable MinIO/S3-compatible lab endpoint:

- Live synthetic MinIO objects: 1,000.
- Live synthetic bytes: 109,783.
- Upload seconds: 0.822835.
- Recursive listing seconds: 0.516001.
- Power Pack live plan seconds: 0.006194.
- Synthetic inventory objects: 100,000.
- Synthetic represented size: 488.281 TiB.
- Synthetic inventory write seconds: 0.185802.
- Synthetic plan seconds: 0.121408.
- Object samples retained in scale profile: 25.
- Max RSS: 21.117 MB.

Observed:

- The benchmark helper now requires explicit MinIO environment variables instead of inspecting a running container for credentials.
- The planner retained bounded object samples while preserving total object count and known bytes.
- The generated external-table path stayed fail-closed when schema evidence was unavailable.

## Bounded MinIO-To-Vertica COPY Proof

Measured against Forge-local MinIO and an isolated temporary Vertica container:

- Live synthetic MinIO objects: 3.
- MinIO upload seconds: 0.510334.
- MinIO recursive listing seconds: 0.428756.
- Power Pack plan seconds: 0.000521.
- Harness max RSS: 20.5 MB.
- Total proof seconds: 25.813351.
- Small dataset: 10,000 valid rows loaded in 2.207265 seconds; row count, reconciliation sums, min/max IDs, and zero rejects matched expectation.
- Medium dataset: 100,000 valid rows loaded in 2.378502 seconds; row count, reconciliation sums, min/max IDs, and zero rejects matched expectation.
- Invalid dataset: 99 valid rows loaded from a 100-row file with one intentionally bad integer; one rejected row was captured as expected.

Observed:

- This proves a bounded synthetic MinIO-to-Vertica `COPY` execution path and generated-plan compatibility.
- It does not prove production 100s-TB data-transfer throughput, Databricks/Snowflake live extraction, or universal Vertica ingest performance.

## Secret/Privacy Scan

Measured:

- Proposed tracked files were scanned for private paths, private IPs, SSH keys, API keys, cloud key patterns, GitHub token patterns, MinIO root-password assignment patterns, and non-placeholder MinIO secret assignments.
- No matching secrets or private infrastructure values were found.

Observed:

- Documentation still contains placeholder environment variable names such as `MINIO_SECRET_KEY=<secret-key>`.
- Policy files still contain words such as `secret`, `customer data`, and `license`; these are not actual secrets.

## Git State

Measured:

- Private GitHub repository exists at `https://github.com/MoonManLabs/vertica-cloud-warehouse-bridge`.
- Repository visibility is private.
- Branch `main` is present locally and at `origin/main`.
- Private candidate before the bounded `COPY` proof update is `a7ca05f8c9e61eb7aece07d709ae3fe471c234b1`.
- The bounded `COPY` proof update is intended to become a new private candidate commit after this validation pass.
- Git author name is `Moon Man Labs`.
- Git author email is `Moonmanlabs@users.noreply.github.com`.

## Local Lab Safety Check

Measured after the bounded MinIO-to-Vertica `COPY` proof on the local lab host:

- CPU sensor: about 34.6 C.
- NVMe composite: about 31.9 C.
- Only pre-existing standing containers remained running.

## Limitations

- No heavy database workload was run for this release gate.
- The bounded `COPY` proof is a small-to-medium synthetic execution proof, not a production ingest benchmark.
- No dedicated commercial secret-scanning tool was installed; scans were regex/manual.
- License recommendation still requires human/legal approval.
- Public author identity is the pseudonymous `Moon Man Labs <Moonmanlabs@users.noreply.github.com>`.

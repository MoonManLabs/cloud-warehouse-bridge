# Publication Manifest

Verdict: `PUBLICATION_READY_FOR_HUMAN_REVIEW`

## Project

Cloud Warehouse Bridge

## Purpose

Independent open-source tooling for evaluating and integrating Vertica workloads with cloud data warehouses and object storage.

The release candidate demonstrates clean-room ingest/lake planning, connector-plan templates, workload-fit advisor reports, bounded object-store inventory handling, draft Vertica SQL generation, COPY batch planning, a bounded synthetic MinIO-to-Vertica `COPY` proof, and first-pass physical-design advice.

## Proposed Repository Name

`cloud-warehouse-bridge`

## Proposed Description

Independent open-source tooling for evaluating and integrating Vertica workloads with cloud data warehouses and object storage.

## Files In Private Candidate

44 tracked files are present in the private release candidate:

- `.gitignore`
- `CHANGELOG.md`
- `CLEANROOM.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `LICENSE_RECOMMENDATION.md`
- `PROVENANCE.md`
- `PUBLICATION_MANIFEST.md`
- `README.md`
- `ROADMAP.md`
- `SECURITY.md`
- `benchmarks/minio_inventory_proof.py`
- `benchmarks/minio_vertica_copy_proof.py`
- `benchmarks/results/.gitkeep`
- `benchmarks/results/MINIO_POWERPACK_PROOF_REPORT.md`
- `benchmarks/results/minio_powerpack_proof_metrics.csv`
- `benchmarks/results/minio_powerpack_proof_metrics.json`
- `benchmarks/results/minio_vertica_copy_proof/MINIO_TO_VERTICA_COPY_PROOF_REPORT.md`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/INGEST_PLAN.md`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/source_profile.json`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/vertica_copy_batches.sql`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/vertica_copy_load.sql`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/vertica_create_table.sql`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/vertica_external_table.sql`
- `benchmarks/results/minio_vertica_copy_proof/generated_plan/vertica_physical_design_advice.sql`
- `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_inventory.csv`
- `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_proof_metrics.csv`
- `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_proof_metrics.json`
- `docs/ARCHITECTURE_BOUNDARY.md`
- `docs/BENCHMARK_METHODOLOGY.md`
- `docs/NATIVE_INTEGRATION_NOTES.md`
- `docs/RELEASE_TEST_RESULTS.md`
- `examples/sample_data/events.jsonl`
- `examples/sample_data/properties.csv`
- `pyproject.toml`
- `src/vpowerpacks/__init__.py`
- `src/vpowerpacks/__main__.py`
- `src/vpowerpacks/cli.py`
- `src/vpowerpacks/connectors.py`
- `src/vpowerpacks/design.py`
- `src/vpowerpacks/offload.py`
- `src/vpowerpacks/planner.py`
- `src/vpowerpacks/profiler.py`
- `tests/test_profiler_and_planner.py`

## Interfaces Used

- Public Vertica SQL patterns: `CREATE TABLE`, `CREATE EXTERNAL TABLE ... AS COPY`, `COPY`, parser declarations, and rejected-data handling.
- Public Databricks SQL/export concepts for writing curated outputs to object storage.
- Public Snowflake unload concepts using `COPY INTO` to an external location/stage.
- Public S3-compatible URI and object-inventory concepts.
- Local filesystem metadata and synthetic test fixtures.

## Dependencies / Licenses

- Python standard library: core runtime; Python Software Foundation License.
- `boto3>=1.34`: optional S3 extra; object-store integration path; Apache-2.0; PyPI metadata reviewed.
- `pyarrow>=15`: optional Parquet extra; local Parquet metadata inspection; Apache-2.0; PyPI metadata reviewed.
- `pytest>=8`: optional development extra; test execution; MIT; PyPI metadata reviewed.
- `setuptools>=68`: build backend requirement; MIT; used only for package builds.
- `minio/mc` container image: optional benchmark helper runtime; not vendored or redistributed by this repository.

No third-party source code was copied into the implementation.

## Synthetic / Public Datasets

- `examples/sample_data/properties.csv`: synthetic property-like records.
- `examples/sample_data/events.jsonl`: synthetic event records.
- MinIO proof corpus: generated synthetic CSV objects with artificial partition keys.
- MinIO-to-Vertica `COPY` proof corpus: generated synthetic CSV files with artificial event IDs, tenants, dates, amounts, and one intentionally invalid integer row for reject capture.
- Synthetic inventory scale proof: artificial object keys and byte counts only.

## Measured Evidence

- 20 standard-library unit tests passed.
- Python compile validation passed.
- CSV input path passed.
- JSONL input path passed.
- PostgreSQL connector-plan dry run passed.
- SQL Server connector-plan dry run passed.
- Databricks connector-plan dry run passed.
- Snowflake connector-plan dry run passed.
- Positive Databricks advisor case returned `GOOD_VERTICA_FIT`.
- Moderate Databricks advisor case returned `POSSIBLE_VERTICA_FIT`.
- Insufficient Snowflake advisor case returned `INSUFFICIENT_EVIDENCE`.
- Low-signal Snowflake advisor case returned `KEEP_ON_CURRENT_PLATFORM`.
- Editable install with dev extras passed.
- Console-script test passed.
- Source distribution and wheel build passed as `cloud_warehouse_bridge-0.1.0`.
- Built wheel installed in a clean temporary environment and produced working CLI output.
- Fresh bounded MinIO proof passed with explicit connection environment variables and synthetic data only.
- Bounded MinIO-to-Vertica `COPY` proof passed with synthetic data, generated Power Pack plan output, row-count/reconciliation validation, and expected rejected-row capture.

MinIO proof measurements retained from the current release candidate:

- 1,000 synthetic MinIO objects.
- Upload: 0.822835 seconds.
- Recursive list: 0.516001 seconds.
- Live plan generation: 0.006194 seconds.
- Synthetic inventory: 100,000 objects.
- Synthetic represented size: 488.281 TiB.
- Synthetic plan generation: 0.121408 seconds.
- Samples retained: 25.
- Max RSS: 21.117 MB.
- Local lab host after proof: CPU about 34.4 C, NVMe about 31.9 C, only pre-existing standing containers remained running.

The 488.281 TiB figure is represented synthetic inventory scale. It is not 488 TiB physically stored, transferred, queried, or loaded into Vertica.

Bounded MinIO-to-Vertica `COPY` proof measurements:

- Live synthetic MinIO objects: 3.
- MinIO upload: 0.510334 seconds.
- Recursive list: 0.428756 seconds.
- Power Pack plan generation: 0.000521 seconds.
- Small load: 10,000 valid rows in 2.207265 seconds; zero rejects; validation passed.
- Medium load: 100,000 valid rows in 2.378502 seconds; zero rejects; validation passed.
- Invalid load: 99 valid rows from a 100-row file with one intentionally invalid integer; one reject captured; validation passed.
- Total proof: 25.813351 seconds.
- Harness max RSS: 20.5 MB.
- Local lab host after proof: CPU about 34.6 C, NVMe about 31.9 C, only pre-existing standing containers remained running.

## Unmeasured Hypotheses

- 100s-TB Vertica transfer throughput has not been proven.
- The bounded MinIO-to-Vertica `COPY` proof is a small-to-medium synthetic execution proof, not a production ingest benchmark.
- Live S3 listing through `boto3` has not been implemented or benchmarked.
- Live Databricks, Snowflake, PostgreSQL, SQL Server, or Vertica connections have not been implemented in this release candidate.
- Generated SQL has not been validated against every supported Vertica version or deployment model.
- Cost savings and performance advantages are hypotheses that require customer-specific measured pilots.

## Secret Scan

Best-effort regex/manual scan of proposed staged files found no actual passwords, API keys, access tokens, secret keys, SSH material, cookies, cloud credentials, MinIO credentials, GitHub credentials, or Vertica license material.

Policy files contain words such as `passwords`, `secret`, `customer data`, and `licenses` as prohibited-content language only. These are not credential findings.

## Private-Path Scan

No private local home-directory paths were found in the proposed staged files.

## Customer-Data Scan

No customer names, customer domains, customer configurations, customer data, CRM data, support cases, or customer-specific benchmark material were found in the proposed staged files.

## Confidential-Material Scan

No Rocket confidential material, Vertica internal-only material, internal URLs, private hostnames, VPN information, internal roadmap content, confidential sales material, or confidential benchmark material was found in the proposed staged files.

## Provenance Result

Implementation appears independently written. It uses public interfaces, public documentation, standard Python behavior, optional open-source dependencies, and synthetic data.

No copied/adapted snippets were identified from Vertica, Rocket Software, Databricks, Snowflake, ClickHouse, StarRocks, MinIO, customer systems, private repositories, or internal documents.

## Git Author

- Local repository `user.name`: `Moon Man Labs`.
- Global Git `user.name`: not configured.

## Git Email

- Local repository `user.email`: `Moonmanlabs@users.noreply.github.com`.
- Global Git `user.email`: not configured.

The configured email is the human-provided GitHub noreply address for the intended pseudonymous project identity.

## Tests

See `docs/RELEASE_TEST_RESULTS.md`.

Summary:

- 20/20 unit tests passed.
- Compile validation passed.
- Editable install passed.
- Built-wheel install passed.
- CLI smoke tests passed.
- Positive, ambiguous, insufficient, negative, and invalid advisor cases are covered.
- SQL source-literal escaping regression cases are covered.

## Known Limitations

- Planning/profiling tool with a bounded proof harness; not a production data-transfer engine.
- Generated SQL is draft SQL requiring operator and target-version review.
- Connector support is dry-run template generation, not live extraction.
- Advisor output is a triage aid, not a migration recommendation, benchmark, platform ranking, or savings guarantee.
- S3 listing is future work.
- License posture remains subject to human/legal review before any public visibility change.
- Public commit identity is configured to the human-provided GitHub noreply address.

## Trademark / Positioning Status

- Canonical project identity is Cloud Warehouse Bridge.
- Uses Vertica descriptively for public-interface interoperability and workload-planning context.
- Does not claim to be an official Rocket Software or Vertica product.
- Uses concise language that Vertica is a trademark of Rocket Software and that Cloud Warehouse Bridge is not affiliated with, sponsored by, or endorsed by Rocket Software.
- Does not use Rocket Software or Vertica logos.
- README includes concise independent/experimental/not-official disclaimer.
- Does not claim Databricks or Snowflake should be replaced.

## License Recommendation

Recommended and locally applied release-candidate license: MIT, subject to final human/legal review before public visibility.

Rationale: the code is a small interoperability/planning wrapper with optional permissive dependencies. MIT keeps inspection and adoption friction low for users, partners, and product teams. A standard MIT `LICENSE` file has been added using the pseudonymous project identity `Moon Man Labs`.

## Native-Integration Opportunities

See `docs/NATIVE_INTEGRATION_NOTES.md`.

Main opportunities:

- native object-store inventory planning;
- native dry-run ingest/COPY planning;
- first-class Databricks/Snowflake/object-store handoff evaluation;
- neutral workload-fit reporting with counter-signals;
- schema inference and drift preflight;
- better external-to-loaded-table promotion workflow;
- programmatic physical-design preflight APIs.

## Outstanding Human Decisions

- Review the private GitHub repository rendering, file tree, license display, package metadata, and commit identity.
- Separately approve any future public visibility change.
- Decide whether future corrective private commits should be pushed before public review.

## Public-Approval Actions Only

The private repository has already been created and pushed. After explicit human approval for public visibility, the next actions would be:

1. Re-run the final release gate against the exact private candidate.
2. Confirm the active GitHub session is the intended pseudonymous account.
3. Confirm no unpushed corrective commits remain.
4. Change repository visibility only after explicit human approval.
5. Re-check visibility, Issues/PR settings, README rendering, license display, and commit identity.

No public-visibility action has been taken.

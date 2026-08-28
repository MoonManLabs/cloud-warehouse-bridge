# Benchmark Methodology

## Scope

The included MinIO benchmark artifacts measure the planner/inventory workflow and one bounded synthetic MinIO-to-Vertica `COPY` proof. They do not measure universal S3 performance, production 100s-TB data movement, or customer-environment throughput.

## Measured

- synthetic object creation time in the benchmark helper;
- MinIO upload time for a bounded synthetic corpus;
- MinIO recursive listing time;
- planner runtime for live inventory-to-plan generation;
- planner runtime for a synthetic large-inventory representation;
- bounded synthetic Vertica `COPY` load time from MinIO;
- row-count, reconciliation-sum, min/max identifier, and rejected-row validation for the bounded `COPY` proof;
- process maximum resident memory reported by the Python process.

## Observed

- the planner preserves total object count and known bytes from inventory CSV input;
- generated profiles retain bounded object samples rather than writing every object into output JSON;
- generated external-table SQL fails closed when schema metadata is missing.
- a small-to-medium synthetic CSV path can be uploaded to MinIO, planned by the Power Pack, loaded into an isolated Vertica container, and reconciled.

## Inferred

The manifest-driven planner shape is suitable for very large object-store inventories because it can summarize inventory metadata without retaining every object in memory or generated output.

## Hypothesized

External wrappers like this could reduce Vertica ingest setup friction by making source discovery, load SQL, rejected-row handling, and hot/cold path selection more repeatable.

## Limitations

Results represent the documented laboratory configuration and should not be interpreted as universal performance claims. Failed tests and missing telemetry should be preserved as evidence.

## Reproduction

Run unit tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Run a local sample plan:

```bash
PYTHONPATH=src python -m vpowerpacks plan \
  --source examples/sample_data/properties.csv \
  --schema demo \
  --table properties \
  --output /tmp/vpowerpacks_plan
```

Run MinIO proof against a disposable S3-compatible endpoint:

```bash
MINIO_ENDPOINT=http://minio:9000 \
MINIO_ACCESS_KEY=<access-key> \
MINIO_SECRET_KEY=<secret-key> \
PYTHONPATH=src python benchmarks/minio_inventory_proof.py
```

Run the bounded MinIO-to-Vertica `COPY` proof against a disposable S3-compatible endpoint and isolated Vertica container:

```bash
MINIO_ENDPOINT=http://minio:9000 \
MINIO_ACCESS_KEY=<access-key> \
MINIO_SECRET_KEY=<secret-key> \
PYTHONPATH=src python benchmarks/minio_vertica_copy_proof.py
```

Use only disposable buckets/prefixes for this proof. Do not point it at customer data or private production storage.

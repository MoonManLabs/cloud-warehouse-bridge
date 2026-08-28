#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from vpowerpacks.planner import build_ingest_plan, write_plan
from vpowerpacks.profiler import profile_inventory_csv, profile_source


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "benchmarks" / "results" / "minio_vertica_copy_proof"
DEFAULT_BUCKET = "vpowerpack-demo"
DEFAULT_PREFIX = "vpowerpacks/e2e-copy-proof"
DEFAULT_NETWORK = "local-s3_default"
DEFAULT_VERTICA_CONTAINER = "vpp-e2e-vertica-copy-proof"
DEFAULT_VERTICA_DB = "vppcopy"
DEFAULT_VERTICA_IMAGE = "docker.io/opentext/vertica-k8s:25.4.0-0-minimal"
MINIO_MC_IMAGE = os.environ.get("MINIO_MC_IMAGE", "minio/mc:RELEASE.2025-08-13T08-35-41Z")


@dataclass
class DatasetExpectation:
    label: str
    rows: int
    amount_sum: int
    event_id_num_sum: int
    min_event_id: str
    max_event_id: str


def run(cmd: list[str], *, timeout: int | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, timeout=timeout, check=False)


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def require_env() -> None:
    missing = [name for name in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing MinIO connection environment variables: "
            + ", ".join(missing)
            + ". Example: MINIO_ENDPOINT=http://minio:9000 MINIO_ACCESS_KEY=<access-key> MINIO_SECRET_KEY=<secret-key>"
        )


def minio_shell(
    container_cli: str,
    network: str,
    script: str,
    mounts: list[str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [container_cli, "run", "--rm", "--network", network]
    for mount in mounts or []:
        cmd.extend(["-v", mount])
    cmd.extend(["-e", "MINIO_ENDPOINT", "-e", "MINIO_ACCESS_KEY", "-e", "MINIO_SECRET_KEY"])
    cmd.extend(["--entrypoint", "/bin/sh", MINIO_MC_IMAGE, "-c", script])
    return run(cmd, timeout=timeout)


def make_dataset(path: Path, *, label: str, rows: int, corrupt: bool = False) -> DatasetExpectation:
    path.parent.mkdir(parents=True, exist_ok=True)
    amount_sum = 0
    event_id_num_sum = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["event_id", "event_id_num", "tenant_id", "event_date", "amount_cents"])
        for idx in range(1, rows + 1):
            event_id = f"{label.upper()}-{idx:08d}"
            event_id_num = idx
            tenant_id = f"T{idx % 17:02d}"
            event_date = f"2026-08-{1 + (idx % 27):02d}"
            amount_cents = 1000 + (idx % 1000)
            if corrupt and idx == rows:
                writer.writerow([event_id, event_id_num, tenant_id, event_date, "not_an_int"])
            else:
                writer.writerow([event_id, event_id_num, tenant_id, event_date, amount_cents])
                amount_sum += amount_cents
                event_id_num_sum += event_id_num
    valid_rows = rows - 1 if corrupt else rows
    return DatasetExpectation(
        label=label,
        rows=valid_rows,
        amount_sum=amount_sum,
        event_id_num_sum=event_id_num_sum,
        min_event_id=f"{label.upper()}-00000001" if valid_rows else "",
        max_event_id=f"{label.upper()}-{valid_rows:08d}" if valid_rows else "",
    )


def upload_dataset(container_cli: str, network: str, data_root: Path, bucket: str, prefix: str) -> tuple[float, float, int]:
    upload_script = f"""
set -eu
mc alias set local "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null
mc mb --ignore-existing local/{bucket} >/dev/null
mc rm --recursive --force local/{bucket}/{prefix} >/dev/null 2>&1 || true
mc cp --recursive /data/ local/{bucket}/{prefix}/ >/dev/null
"""
    started = time.perf_counter()
    proc = minio_shell(container_cli, network, upload_script, [f"{data_root}:/data:ro"], timeout=900)
    upload_seconds = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

    list_script = f"""
set -eu
mc alias set local "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null
mc ls --recursive --json local/{bucket}/{prefix}/
"""
    started = time.perf_counter()
    proc = minio_shell(container_cli, network, list_script, timeout=300)
    list_seconds = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    object_count = sum(1 for line in proc.stdout.splitlines() if line.strip())
    return upload_seconds, list_seconds, object_count


def write_inventory(data_root: Path, inventory: Path) -> None:
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["key", "size_bytes"])
        writer.writeheader()
        for item in sorted(data_root.rglob("*.csv")):
            writer.writerow({"key": str(item.relative_to(data_root)), "size_bytes": item.stat().st_size})


def ensure_vertica(
    container_cli: str,
    network: str,
    container_name: str,
    image: str,
    db_name: str,
    data_dir: Path,
) -> None:
    run([container_cli, "rm", "-f", container_name], timeout=60)
    data_dir.mkdir(parents=True, exist_ok=True)
    boot_cmd = (
        "groupadd -g 995 verticadba 2>/dev/null || true; "
        "useradd -u 997 -g 995 -m -d /home/dbadmin -s /bin/bash dbadmin 2>/dev/null || true; "
        "chown -R 997:995 /home/dbadmin /data /opt/vertica/log /opt/vertica/config 2>/dev/null || true; "
        "sleep infinity"
    )
    proc = run(
        [
            container_cli,
            "run",
            "-d",
            "--name",
            container_name,
            "--network",
            network,
            "--cpus",
            "0.65",
            "--user",
            "root",
            "-v",
            f"{data_dir}:/data:U",
            "-e",
            f"APP_DB_NAME={db_name}",
            "-e",
            "APP_DB_USER=dbadmin",
            "-e",
            "APP_DB_PASSWORD=password",
            image,
            "/bin/bash",
            "-lc",
            boot_cmd,
        ],
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

    bootstrap = f"""
set -eu
groupadd -g 995 verticadba 2>/dev/null || true
useradd -u 997 -g 995 -m -d /home/dbadmin -s /bin/bash dbadmin 2>/dev/null || true
mkdir -p /data/{db_name}/v_{db_name}_node0001_catalog /data/{db_name}/v_{db_name}_node0001_data
chown -R dbadmin:verticadba /data /home/dbadmin
if [ ! -f /data/{db_name}/v_{db_name}_node0001_catalog/vertica.conf ]; then
  su - dbadmin -c "/opt/vertica/bin/bootstrap-catalog -C {db_name} -H 127.0.0.1 -s v_{db_name}_node0001 -D /data/{db_name}/v_{db_name}_node0001_catalog -S /data/{db_name}/v_{db_name}_node0001_data -p 5433 -c 127.0.0.1 -B 127.255.255.255 -L /opt/vertica/config/share/license.key -x 4803 -N -1 -T -U dbadmin -A password -a password"
fi
"""
    proc = run([container_cli, "exec", "-i", container_name, "/bin/bash", "-lc", bootstrap], timeout=240)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    proc = run(
        [
            container_cli,
            "exec",
            "-u",
            "dbadmin",
            "-d",
            container_name,
            "/opt/vertica/bin/vertica",
            "-D",
            f"/data/{db_name}/v_{db_name}_node0001_catalog",
            "-C",
            db_name,
            "-n",
            f"v_{db_name}_node0001",
            "-h",
            "127.0.0.1",
            "-p",
            "5433",
            "-P",
            "4803",
            "-Y",
            "ipv4",
        ],
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    deadline = time.time() + 240
    while time.time() < deadline:
        proc = vsql(container_cli, container_name, db_name, "SELECT 1", include_s3_config=False, timeout=10)
        if proc.returncode == 0 and proc.stdout.strip() == "1":
            return
        time.sleep(5)
    logs = run([container_cli, "logs", "--tail", "80", container_name], timeout=30)
    raise TimeoutError("Vertica did not become ready\n" + logs.stdout + logs.stderr)


def vsql(
    container_cli: str,
    container_name: str,
    db_name: str,
    sql: str,
    *,
    include_s3_config: bool = True,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    prefix = ""
    if include_s3_config:
        access_key = os.environ["MINIO_ACCESS_KEY"]
        secret_key = os.environ["MINIO_SECRET_KEY"]
        prefix = (
            f"ALTER SESSION SET AWSAuth='{access_key}:{secret_key}'; "
            "ALTER SESSION SET AWSRegion='us-east-1'; "
            "ALTER SESSION SET S3BucketConfig='["
            "{\"bucket\":\"vpowerpack-demo\",\"endpoint\":\"minio:9000\","
            "\"protocol\":\"http\",\"enableVirtualAddressing\":false}"
            "]'; "
        )
    return run(
        [
            container_cli,
            "exec",
            "-u",
            "dbadmin",
            "-i",
            container_name,
            "/opt/vertica/bin/vsql",
            "-h",
            "127.0.0.1",
            "-p",
            "5433",
            "-U",
            "dbadmin",
            "-w",
            "password",
            "-d",
            db_name,
            "-At",
            "-F",
            "|",
            "-c",
            prefix + sql,
        ],
        timeout=timeout,
    )


def assert_sql(proc: subprocess.CompletedProcess[str], context: str) -> None:
    if proc.returncode != 0:
        raise RuntimeError(f"{context} failed: {proc.stderr.strip() or proc.stdout.strip()}")


def parse_validation(stdout: str) -> dict[str, str]:
    rows = [line.split("|") for line in stdout.splitlines() if line.strip()]
    if not rows:
        raise RuntimeError("validation query returned no rows")
    labels = ["rows", "amount_sum", "event_id_num_sum", "min_event_id", "max_event_id"]
    return dict(zip(labels, rows[-1], strict=True))


def run_load(
    container_cli: str,
    container_name: str,
    db_name: str,
    bucket: str,
    prefix: str,
    label: str,
    expectation: DatasetExpectation,
    invalid: bool = False,
) -> dict[str, object]:
    schema = "vpp_e2e"
    table = f"{label}_events"
    rejects = f"{table}_rejects"
    file_name = f"{label}.csv"
    ddl = f"""
CREATE SCHEMA IF NOT EXISTS {schema};
DROP TABLE IF EXISTS {schema}.{table};
DROP TABLE IF EXISTS {schema}.{rejects};
CREATE TABLE {schema}.{table} (
  event_id VARCHAR(64),
  event_id_num INT,
  tenant_id VARCHAR(16),
  event_date DATE,
  amount_cents INT
);
"""
    assert_sql(vsql(container_cli, container_name, db_name, ddl, include_s3_config=False, timeout=120), f"{label} DDL")
    copy_sql = f"""
COPY {schema}.{table}
FROM 's3://{bucket}/{prefix}/{file_name}'
DELIMITER ',' ENCLOSED BY '"' SKIP 1
REJECTED DATA AS TABLE {schema}.{rejects}
REJECTMAX 100;
"""
    started = time.perf_counter()
    proc = vsql(container_cli, container_name, db_name, copy_sql, timeout=300)
    load_seconds = time.perf_counter() - started
    assert_sql(proc, f"{label} COPY")
    proc = vsql(
        container_cli,
        container_name,
        db_name,
        f"""
SELECT COUNT(*), COALESCE(SUM(amount_cents),0), COALESCE(SUM(event_id_num),0), MIN(event_id), MAX(event_id)
FROM {schema}.{table};
""",
        include_s3_config=False,
        timeout=120,
    )
    assert_sql(proc, f"{label} validation")
    actual = parse_validation(proc.stdout)
    reject_count = 0
    proc = vsql(
        container_cli,
        container_name,
        db_name,
        f"SELECT COUNT(*) FROM {schema}.{rejects};",
        include_s3_config=False,
        timeout=120,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        reject_count = int(proc.stdout.strip().splitlines()[-1])
    expected_rejects = 1 if invalid else 0
    checks = {
        "rows_match": int(actual["rows"]) == expectation.rows,
        "amount_sum_match": int(actual["amount_sum"]) == expectation.amount_sum,
        "event_id_num_sum_match": int(actual["event_id_num_sum"]) == expectation.event_id_num_sum,
        "min_event_id_match": actual["min_event_id"] == expectation.min_event_id,
        "max_event_id_match": actual["max_event_id"] == expectation.max_event_id,
        "reject_count_match": reject_count == expected_rejects,
    }
    return {
        "label": label,
        "source_uri": f"s3://{bucket}/{prefix}/{file_name}",
        "expected": asdict(expectation),
        "actual": actual,
        "reject_count": reject_count,
        "expected_rejects": expected_rejects,
        "load_seconds": round(load_seconds, 6),
        "rows_per_second": round(expectation.rows / load_seconds, 3) if load_seconds else None,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container-cli", default=os.environ.get("CONTAINER_CLI", "podman"))
    parser.add_argument("--network", default=os.environ.get("MINIO_NETWORK", DEFAULT_NETWORK))
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--small-rows", type=int, default=10_000)
    parser.add_argument("--medium-rows", type=int, default=100_000)
    parser.add_argument("--container-name", default=DEFAULT_VERTICA_CONTAINER)
    parser.add_argument("--vertica-image", default=os.environ.get("VERTICA_IMAGE", DEFAULT_VERTICA_IMAGE))
    parser.add_argument("--vertica-db", default=DEFAULT_VERTICA_DB)
    parser.add_argument("--keep-container", action="store_true")
    args = parser.parse_args()
    require_env()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="vpp-e2e-copy-") as tmp_name:
        tmp = Path(tmp_name)
        data = tmp / "data"
        small = make_dataset(data / "small.csv", label="small", rows=args.small_rows)
        medium = make_dataset(data / "medium.csv", label="medium", rows=args.medium_rows)
        invalid = make_dataset(data / "invalid.csv", label="invalid", rows=100, corrupt=True)

        upload_seconds, list_seconds, object_count = upload_dataset(args.container_cli, args.network, data, args.bucket, args.prefix)
        inventory = RESULT_DIR / "minio_vertica_copy_inventory.csv"
        write_inventory(data, inventory)

        profile = profile_inventory_csv(str(inventory), f"s3://{args.bucket}/{args.prefix}", format_hint="csv", sample_objects=10)
        sample_profile = profile_source(str(data / "small.csv"))
        profile.columns = sample_profile.columns
        profile.row_sample_count = sample_profile.row_sample_count
        plan_dir = RESULT_DIR / "generated_plan"
        plan_started = time.perf_counter()
        write_plan(build_ingest_plan(profile, "vpp_e2e", "events"), plan_dir)
        plan_seconds = time.perf_counter() - plan_started

    data_dir = ROOT / "tmp" / "minio_vertica_copy_proof" / "data"
    try:
        ensure_vertica(args.container_cli, args.network, args.container_name, args.vertica_image, args.vertica_db, data_dir)
        load_results = [
            run_load(args.container_cli, args.container_name, args.vertica_db, args.bucket, args.prefix, "small", small),
            run_load(args.container_cli, args.container_name, args.vertica_db, args.bucket, args.prefix, "medium", medium),
            run_load(args.container_cli, args.container_name, args.vertica_db, args.bucket, args.prefix, "invalid", invalid, invalid=True),
        ]
    finally:
        if not args.keep_container:
            run([args.container_cli, "rm", "-f", args.container_name], timeout=60)
            shutil.rmtree(data_dir.parent, ignore_errors=True)

    metrics = {
        "result": "passed" if all(item["passed"] for item in load_results) else "failed",
        "live_minio_objects": object_count,
        "minio_upload_seconds": round(upload_seconds, 6),
        "minio_list_seconds": round(list_seconds, 6),
        "powerpack_plan_seconds": round(plan_seconds, 6),
        "load_results": load_results,
        "max_rss_mb": round(rss_mb(), 3),
        "total_seconds": round(time.perf_counter() - started, 6),
    }
    (RESULT_DIR / "minio_vertica_copy_proof_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    with (RESULT_DIR / "minio_vertica_copy_proof_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["label", "rows", "load_seconds", "rows_per_second", "reject_count", "expected_rejects", "passed"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in load_results:
            writer.writerow(
                {
                    "label": item["label"],
                    "rows": item["expected"]["rows"],
                    "load_seconds": item["load_seconds"],
                    "rows_per_second": item["rows_per_second"],
                    "reject_count": item["reject_count"],
                    "expected_rejects": item["expected_rejects"],
                    "passed": item["passed"],
                }
            )
    rows = "\n".join(
        f"| {item['label']} | {item['expected']['rows']} | {item['load_seconds']} | {item['rows_per_second']} | "
        f"{item['reject_count']} | {item['passed']} |"
        for item in load_results
    )
    report = f"""# MinIO To Vertica COPY Proof

## Result

{metrics["result"].upper()}

This proof uses synthetic CSV objects in MinIO, generates a Vertica Cloud Warehouse Bridge plan, loads the same objects into an isolated temporary Vertica container with `COPY`, and validates row counts, reconciliation sums, min/max identifiers, and rejected-row handling.

## Scope

- Object store: S3-compatible MinIO on the configured container network.
- Data: synthetic CSV only.
- Vertica path: public `COPY` syntax with S3 session parameters and rejected-data table.
- Database target: isolated temporary container `{args.container_name}`.
- Resource posture: bounded proof, container CPU-capped during load, not a throughput benchmark.

## Timings

- MinIO upload seconds: {metrics["minio_upload_seconds"]}
- MinIO recursive list seconds: {metrics["minio_list_seconds"]}
- Power Pack plan seconds: {metrics["powerpack_plan_seconds"]}
- Total proof seconds: {metrics["total_seconds"]}
- Max harness RSS MB: {metrics["max_rss_mb"]}

## Load Validation

| Dataset | Valid Rows | Load Seconds | Rows/Second | Reject Rows | Passed |
| --- | ---: | ---: | ---: | ---: | --- |
{rows}

## Artifacts

- Generated plan: `benchmarks/results/minio_vertica_copy_proof/generated_plan`
- Metrics JSON: `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_proof_metrics.json`
- Metrics CSV: `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_proof_metrics.csv`
- Inventory CSV: `benchmarks/results/minio_vertica_copy_proof/minio_vertica_copy_inventory.csv`

## Claim Boundary

- Proven here: bounded synthetic MinIO-to-Vertica `COPY` execution, generated-plan compatibility, row-count/reconciliation validation, and reject capture in an isolated lab container.
- Not proven here: production 100s-TB transfer throughput, customer-environment compatibility, Databricks/Snowflake live extraction, enterprise scheduler/retry behavior, or universal Vertica ingest performance.
"""
    (RESULT_DIR / "MINIO_TO_VERTICA_COPY_PROOF_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0 if metrics["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

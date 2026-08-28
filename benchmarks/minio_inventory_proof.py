#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import subprocess
import tempfile
import time
from pathlib import Path

from vpowerpacks.planner import build_ingest_plan, write_plan
from vpowerpacks.profiler import profile_inventory_csv, profile_source


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "benchmarks" / "results"
DEFAULT_BUCKET = "vpowerpack-demo"
DEFAULT_PREFIX = "vpowerpacks/minio-proof"
MINIO_MC_IMAGE = os.environ.get("MINIO_MC_IMAGE", "minio/mc:RELEASE.2025-08-13T08-35-41Z")


def run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)


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
    cmd.extend(
        [
            "-e",
            "MINIO_ENDPOINT",
            "-e",
            "MINIO_ACCESS_KEY",
            "-e",
            "MINIO_SECRET_KEY",
        ]
    )
    cmd.extend(["--entrypoint", "/bin/sh", MINIO_MC_IMAGE, "-c", script])
    return run(cmd, timeout=timeout)


def make_live_corpus(root: Path, object_count: int, rows_per_object: int) -> Path:
    data = root / "data"
    for idx in range(object_count):
        state = f"state={idx % 50:02d}"
        month = f"month={1 + (idx % 12):02d}"
        directory = data / state / "year=2026" / month
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"part-{idx:06d}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["event_id", "state_code", "event_date", "event_score"])
            for row_idx in range(rows_per_object):
                writer.writerow([f"E-{idx:06d}-{row_idx:03d}", f"S{idx % 50:02d}", "2026-08-27", idx + row_idx])
    return data


def write_inventory_from_listing(listing_jsonl: str, inventory: Path, prefix: str) -> tuple[int, int]:
    count = 0
    bytes_total = 0
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["key", "size_bytes"])
        writer.writeheader()
        for line in listing_jsonl.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            key = payload.get("key") or payload.get("name")
            size = payload.get("size")
            if not key or size is None:
                continue
            relative_key = str(key)
            marker = prefix.rstrip("/") + "/"
            if marker in relative_key:
                relative_key = relative_key.split(marker, 1)[1]
            writer.writerow({"key": relative_key, "size_bytes": int(size)})
            count += 1
            bytes_total += int(size)
    return count, bytes_total


def write_synthetic_inventory(path: Path, object_count: int, object_size: int) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["key", "size_bytes"])
        writer.writeheader()
        for idx in range(object_count):
            writer.writerow({"key": f"state={idx % 50:02d}/year=2026/month={1 + idx % 12:02d}/part-{idx:08d}.parquet", "size_bytes": object_size})


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container-cli", default=os.environ.get("CONTAINER_CLI", "podman"))
    parser.add_argument("--network", default=os.environ.get("MINIO_NETWORK", "local-s3_default"))
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--live-objects", type=int, default=1000)
    parser.add_argument("--rows-per-object", type=int, default=2)
    parser.add_argument("--scale-objects", type=int, default=100_000)
    parser.add_argument("--scale-object-size-gib", type=int, default=5)
    args = parser.parse_args()

    missing_env = [name for name in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY") if not os.environ.get(name)]
    if missing_env:
        raise RuntimeError(
            "Missing MinIO connection environment variables: "
            + ", ".join(missing_env)
            + ". Example: MINIO_ENDPOINT=http://minio:9000 MINIO_ACCESS_KEY=<access-key> MINIO_SECRET_KEY=<secret-key>"
        )

    started = time.perf_counter()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vpp-minio-proof-") as tmp_name:
        tmp = Path(tmp_name)
        data = make_live_corpus(tmp, args.live_objects, args.rows_per_object)

        upload_script = f"""
set -eu
mc alias set local "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null
mc mb --ignore-existing local/{args.bucket} >/dev/null
mc rm --recursive --force local/{args.bucket}/{args.prefix} >/dev/null 2>&1 || true
mc cp --recursive /data/ local/{args.bucket}/{args.prefix}/ >/dev/null
"""
        upload_start = time.perf_counter()
        proc = minio_shell(args.container_cli, args.network, upload_script, [f"{data}:/data:ro"], timeout=900)
        upload_seconds = time.perf_counter() - upload_start
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

        list_script = f"""
set -eu
mc alias set local "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null
mc ls --recursive --json local/{args.bucket}/{args.prefix}/
"""
        list_start = time.perf_counter()
        proc = minio_shell(args.container_cli, args.network, list_script, timeout=300)
        list_seconds = time.perf_counter() - list_start
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

        live_inventory = RESULT_DIR / "minio_live_inventory.csv"
        live_count, live_bytes = write_inventory_from_listing(proc.stdout, live_inventory, args.prefix)

        live_plan_dir = RESULT_DIR / "minio_live_plan"
        live_plan_start = time.perf_counter()
        live_profile = profile_inventory_csv(str(live_inventory), f"s3://{args.bucket}/{args.prefix}", format_hint="csv", sample_objects=50)
        sample_profile = profile_source(str(next(data.rglob("*.csv"))))
        live_profile.columns = sample_profile.columns
        live_profile.row_sample_count = sample_profile.row_sample_count
        live_profile.caveats.append("Columns inferred from one local schema sample generated from the same MinIO corpus.")
        write_plan(build_ingest_plan(live_profile, "vpowerpacks_demo", "minio_live_events"), live_plan_dir)
        live_plan_seconds = time.perf_counter() - live_plan_start

        local_sample_plan_dir = RESULT_DIR / "local_sample_plan"
        write_plan(build_ingest_plan(sample_profile, "vpowerpacks_demo", "minio_live_events_sample"), local_sample_plan_dir)

        scale_inventory = RESULT_DIR / "synthetic_500tib_inventory.csv"
        scale_object_size = args.scale_object_size_gib * 1024**3
        scale_write_start = time.perf_counter()
        write_synthetic_inventory(scale_inventory, args.scale_objects, scale_object_size)
        scale_write_seconds = time.perf_counter() - scale_write_start

        scale_plan_dir = RESULT_DIR / "synthetic_500tib_plan"
        scale_plan_start = time.perf_counter()
        scale_profile = profile_inventory_csv(
            str(scale_inventory),
            f"s3://{args.bucket}/synthetic-500tib",
            format_hint="parquet",
            sample_objects=25,
        )
        write_plan(build_ingest_plan(scale_profile, "vpowerpacks_demo", "synthetic_500tib"), scale_plan_dir)
        scale_plan_seconds = time.perf_counter() - scale_plan_start

    metrics = {
        "live_minio_objects": live_count,
        "live_minio_bytes": live_bytes,
        "live_upload_seconds": round(upload_seconds, 6),
        "live_list_seconds": round(list_seconds, 6),
        "live_plan_seconds": round(live_plan_seconds, 6),
        "scale_inventory_objects": args.scale_objects,
        "scale_inventory_bytes": args.scale_objects * scale_object_size,
        "scale_inventory_tib": round((args.scale_objects * scale_object_size) / 1024**4, 3),
        "scale_inventory_write_seconds": round(scale_write_seconds, 6),
        "scale_plan_seconds": round(scale_plan_seconds, 6),
        "scale_profile_samples_retained": len(scale_profile.objects),
        "max_rss_mb": round(rss_mb(), 3),
        "total_seconds": round(time.perf_counter() - started, 6),
    }
    (RESULT_DIR / "minio_powerpack_proof_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (RESULT_DIR / "minio_powerpack_proof_metrics.csv").write_text(
        "metric,value\n" + "".join(f"{key},{value}\n" for key, value in metrics.items()),
        encoding="utf-8",
    )
    report = f"""# MinIO Power Pack Proof

## Result

The planner successfully profiled a live MinIO prefix through an inventory file and also handled a synthetic enterprise-scale inventory without retaining every object in the output profile.

## Live MinIO Proof

- Objects listed from MinIO: {live_count}
- Known object bytes: {live_bytes}
- Upload seconds: {metrics["live_upload_seconds"]}
- MinIO recursive list seconds: {metrics["live_list_seconds"]}
- Power Pack plan seconds: {metrics["live_plan_seconds"]}
- Plan output: `benchmarks/results/minio_live_plan`
- Local sample schema plan: `benchmarks/results/local_sample_plan`
- Schema evidence: one local sample file generated from the same MinIO corpus

## Scale Simulation

- Simulated inventory objects: {args.scale_objects}
- Simulated object size GiB: {args.scale_object_size_gib}
- Represented TiB: {metrics["scale_inventory_tib"]}
- Inventory write seconds: {metrics["scale_inventory_write_seconds"]}
- Power Pack plan seconds: {metrics["scale_plan_seconds"]}
- Object samples retained: {metrics["scale_profile_samples_retained"]}
- Plan output: `benchmarks/results/synthetic_500tib_plan`

## Claim Boundary

- Proven here: MinIO inventory-to-plan workflow, bounded profile output, and 100s-TB inventory representation.
- Not proven here: 100s-TB data transfer throughput into Vertica.
- Next proof: bounded Vertica COPY/load run from the generated MinIO layout, then scale the loader by parallel batches and record rows/sec, bytes/sec, rejects, and recovery behavior.
"""
    (RESULT_DIR / "MINIO_POWERPACK_PROOF_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import gzip
import json
import mimetypes
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


SUPPORTED_TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson"}


@dataclass
class ColumnProfile:
    name: str
    observed_types: list[str] = field(default_factory=list)
    nullable: bool = False
    sample_values: list[str] = field(default_factory=list)
    recommended_vertica_type: str = "LONG VARCHAR"


@dataclass
class SourceObject:
    uri: str
    size_bytes: int | None
    format: str
    compressed: bool = False


@dataclass
class SourceProfile:
    source_uri: str
    source_kind: str
    objects: list[SourceObject]
    total_object_count: int
    total_known_bytes: int
    detected_format: str
    columns: list[ColumnProfile]
    row_sample_count: int
    caveats: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def profile_source(source: str, sample_rows: int = 1000) -> SourceProfile:
    if source.startswith("s3://"):
        return _profile_s3_uri(source)

    path = Path(source).expanduser()
    if not path.exists():
        raise FileNotFoundError(source)

    objects = list(_iter_local_objects(path))
    if not objects:
        raise ValueError(f"No supported files found under {source}")

    first = Path(objects[0].uri)
    detected = objects[0].format
    if detected == "csv":
        columns, rows = _profile_csv(first, sample_rows)
    elif detected in {"jsonl", "json"}:
        columns, rows = _profile_jsonl(first, sample_rows)
    elif detected == "parquet":
        columns, rows = _profile_parquet(first)
    else:
        columns, rows = [], 0

    caveats: list[str] = []
    formats = sorted({obj.format for obj in objects})
    if len(formats) > 1:
        caveats.append(f"Mixed source formats detected: {', '.join(formats)}.")
    if detected == "parquet" and not columns:
        caveats.append("Parquet schema requires optional dependency pyarrow for local inspection.")
    if source.startswith("s3://"):
        caveats.append("S3 object listing requires boto3 and credentials; this profile is URI-derived only.")

    return SourceProfile(
        source_uri=str(path),
        source_kind="local",
        objects=objects,
        total_object_count=len(objects),
        total_known_bytes=sum(obj.size_bytes or 0 for obj in objects),
        detected_format=detected,
        columns=columns,
        row_sample_count=rows,
        caveats=caveats,
    )


def _iter_local_objects(path: Path) -> Iterable[SourceObject]:
    paths = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    for item in paths:
        fmt, compressed = detect_format(item.name)
        if fmt == "unknown":
            continue
        yield SourceObject(str(item), item.stat().st_size, fmt, compressed)


def _profile_s3_uri(uri: str) -> SourceProfile:
    parsed = urlparse(uri)
    name = Path(parsed.path).name or parsed.path
    fmt, compressed = detect_format(name)
    obj = SourceObject(uri=uri, size_bytes=None, format=fmt, compressed=compressed)
    return SourceProfile(
        source_uri=uri,
        source_kind="s3",
        objects=[obj],
        total_object_count=1,
        total_known_bytes=0,
        detected_format=fmt,
        columns=[],
        row_sample_count=0,
        caveats=[
            "No S3 listing was performed in the default safe mode.",
            "Provide a sampled local file to infer columns, or install the s3 extra and run with credentials in a controlled environment.",
        ],
    )


def profile_inventory_csv(
    inventory_csv: str,
    source_uri: str,
    format_hint: str = "parquet",
    sample_objects: int = 100,
) -> SourceProfile:
    path = Path(inventory_csv).expanduser()
    if not path.exists():
        raise FileNotFoundError(inventory_csv)

    objects: list[SourceObject] = []
    total_count = 0
    total_bytes = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = row.get("key") or row.get("uri") or row.get("path") or row.get("object")
            if not key:
                continue
            size = _parse_int(row.get("size_bytes") or row.get("size") or row.get("bytes"))
            total_count += 1
            total_bytes += size or 0
            if len(objects) < sample_objects:
                uri = key if key.startswith("s3://") else _join_s3_uri(source_uri, key)
                fmt, compressed = detect_format(uri)
                objects.append(SourceObject(uri=uri, size_bytes=size, format=fmt if fmt != "unknown" else format_hint, compressed=compressed))

    if total_count == 0:
        raise ValueError("Inventory file did not contain object rows with a key, uri, path, or object column.")

    formats = {obj.format for obj in objects}
    detected = formats.pop() if len(formats) == 1 else format_hint
    return SourceProfile(
        source_uri=source_uri,
        source_kind="s3_inventory",
        objects=objects,
        total_object_count=total_count,
        total_known_bytes=total_bytes,
        detected_format=detected,
        columns=[],
        row_sample_count=0,
        caveats=[
            "Inventory mode is manifest-driven; sampled objects are retained in the profile, not the full object list.",
            "Use a sampled data file or Parquet metadata pass to infer columns before emitting executable external-table SQL.",
        ],
    )


def detect_format(name: str) -> tuple[str, bool]:
    lower = name.lower()
    compressed = lower.endswith(".gz")
    if compressed:
        lower = lower[:-3]
    suffix = Path(lower).suffix
    if suffix == ".csv":
        return "csv", compressed
    if suffix in {".jsonl", ".ndjson"}:
        return "jsonl", compressed
    if suffix == ".json":
        return "json", compressed
    if suffix == ".parquet":
        return "parquet", compressed
    guessed, _ = mimetypes.guess_type(name)
    if guessed == "text/csv":
        return "csv", compressed
    return "unknown", compressed


def _open_text(path: Path):
    if path.name.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _join_s3_uri(source_uri: str, key: str) -> str:
    return source_uri.rstrip("/") + "/" + key.lstrip("/")


def _profile_csv(path: Path, sample_rows: int) -> tuple[list[ColumnProfile], int]:
    with _open_text(path) as handle:
        sample = handle.read(8192)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        accum: dict[str, list[str | None]] = {name: [] for name in (reader.fieldnames or [])}
        rows = 0
        for row in reader:
            rows += 1
            for name in accum:
                accum[name].append(row.get(name))
            if rows >= sample_rows:
                break
    return [_column_profile(name, values) for name, values in accum.items()], rows


def _profile_jsonl(path: Path, sample_rows: int) -> tuple[list[ColumnProfile], int]:
    accum: dict[str, list[Any]] = {}
    rows = 0
    with _open_text(path) as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            payload = json.loads(line)
            flat = _flatten(payload)
            for key in flat:
                accum.setdefault(key, [])
            for key, values in accum.items():
                values.append(flat.get(key))
            if rows >= sample_rows:
                break
    return [_column_profile(name, values) for name, values in sorted(accum.items())], rows


def _profile_parquet(path: Path) -> tuple[list[ColumnProfile], int]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return [], 0
    metadata = pq.read_metadata(path)
    schema = metadata.schema.to_arrow_schema()
    columns = [
        ColumnProfile(
            name=field.name,
            observed_types=[str(field.type)],
            nullable=field.nullable,
            recommended_vertica_type=_arrow_to_vertica(str(field.type)),
        )
        for field in schema
    ]
    return columns, min(metadata.num_rows, 1000)


def _flatten(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        clean_key = f"{prefix}_{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flatten(value, clean_key))
        else:
            out[clean_key] = value
    return out


def _column_profile(name: str, values: list[Any]) -> ColumnProfile:
    observed: list[str] = []
    samples: list[str] = []
    nullable = False
    for value in values:
        if value is None or value == "":
            nullable = True
            continue
        observed_type = _infer_type(value)
        if observed_type not in observed:
            observed.append(observed_type)
        text_value = str(value)
        if text_value not in samples and len(samples) < 5:
            samples.append(text_value[:120])
    return ColumnProfile(
        name=_safe_identifier(name),
        observed_types=observed or ["unknown"],
        nullable=nullable,
        sample_values=samples,
        recommended_vertica_type=_recommended_vertica_type(observed),
    )


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (list, dict)):
        return "json"
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return "bool"
    try:
        int(text)
        return "int"
    except ValueError:
        pass
    try:
        float(text)
        return "float"
    except ValueError:
        pass
    for parser in (date.fromisoformat, datetime.fromisoformat):
        try:
            parser(text.replace("Z", "+00:00"))
            return "timestamp" if "T" in text or ":" in text else "date"
        except ValueError:
            continue
    return "string"


def _recommended_vertica_type(types: list[str]) -> str:
    type_set = set(types)
    if not type_set or "json" in type_set:
        return "LONG VARCHAR"
    if type_set <= {"int"}:
        return "INT"
    if type_set <= {"int", "float"}:
        return "FLOAT"
    if type_set <= {"bool"}:
        return "BOOLEAN"
    if type_set <= {"date"}:
        return "DATE"
    if type_set <= {"date", "timestamp"} or type_set <= {"timestamp"}:
        return "TIMESTAMP"
    return "VARCHAR(1024)"


def _arrow_to_vertica(type_name: str) -> str:
    lower = type_name.lower()
    if any(token in lower for token in ["int8", "int16", "int32", "int64", "uint"]):
        return "INT"
    if any(token in lower for token in ["double", "float", "decimal"]):
        return "FLOAT"
    if "bool" in lower:
        return "BOOLEAN"
    if "timestamp" in lower:
        return "TIMESTAMP"
    if lower == "date32" or lower == "date64":
        return "DATE"
    return "LONG VARCHAR" if any(token in lower for token in ["list", "struct", "map"]) else "VARCHAR(1024)"


def _safe_identifier(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in name.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    if not cleaned:
        cleaned = "column"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned

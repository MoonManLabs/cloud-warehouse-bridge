from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SOURCE_TYPES = {"databricks", "snowflake"}
OUTCOME_CLASSES = {
    "GOOD_VERTICA_FIT",
    "POSSIBLE_VERTICA_FIT",
    "INSUFFICIENT_EVIDENCE",
    "KEEP_ON_CURRENT_PLATFORM",
}


@dataclass
class OffloadAssessment:
    source_type: str
    workload_name: str
    domain: str
    data_volume_tib: float
    monthly_runs: int
    avg_runtime_minutes: float
    concurrency: int
    retention_days: int
    stable_schema: bool
    object_store_path: str
    fit_level: str
    fit_score: int
    signals: list[str]
    counter_signals: list[str]
    unknowns: list[str]
    markdown: str


def build_offload_assessment(
    *,
    source_type: str,
    workload_name: str,
    domain: str = "general analytics",
    data_volume_tib: float,
    monthly_runs: int,
    avg_runtime_minutes: float,
    concurrency: int,
    retention_days: int,
    stable_schema: bool,
    object_store_path: str = "s3://example-landing/workload/",
) -> OffloadAssessment:
    normalized_source_type = source_type.lower()
    if normalized_source_type not in SOURCE_TYPES:
        raise ValueError("source_type must be databricks or snowflake.")
    if data_volume_tib < 0:
        raise ValueError("data_volume_tib must be non-negative.")
    if monthly_runs < 0 or avg_runtime_minutes < 0 or concurrency < 0 or retention_days < 0:
        raise ValueError("workload metrics must be non-negative.")

    score = 0
    signals: list[str] = []
    counter_signals: list[str] = []
    unknowns: list[str] = [
        "No measured Vertica pilot result was provided.",
        "No current platform cost, warehouse size, or cluster/runtime configuration was provided.",
        "No current service-level objective, concurrency trace, or query profile was provided.",
    ]

    if data_volume_tib >= 10:
        score += 2
        signals.append("Large data volume can justify a governed analytical serving layer.")
    elif data_volume_tib >= 1:
        score += 1
        signals.append("Moderate data volume may justify Vertica when query frequency or concurrency is high.")
    else:
        counter_signals.append("Small data volume alone does not justify offload complexity.")

    if monthly_runs >= 100:
        score += 2
        signals.append("High repeat frequency suggests recurring compute burn, not one-time exploration.")
    elif monthly_runs >= 20:
        score += 1
        signals.append("Repeat usage is present; evaluate whether this is now a production serving workload.")
    else:
        counter_signals.append("Low run frequency may be better left on the current platform.")

    if avg_runtime_minutes >= 30:
        score += 2
        signals.append("Long-running analytics are good candidates for workload-managed high-compute execution.")
    elif avg_runtime_minutes >= 10:
        score += 1
        signals.append("Runtime is material enough to inspect warehouse/lakehouse compute cost.")
    else:
        counter_signals.append("Short average runtime weakens the case for adding another serving engine.")

    if concurrency >= 10:
        score += 2
        signals.append("Concurrency favors a predictable governed serving engine.")
    elif concurrency >= 3:
        score += 1
        signals.append("Some concurrency exists; test whether Vertica can provide steadier response and cost.")
    else:
        counter_signals.append("Low concurrency may not need a separate governed high-compute serving tier.")

    if retention_days >= 365:
        score += 1
        signals.append("Long retention favors governed reusable data products over repeated transient compute.")
    elif retention_days < 90:
        counter_signals.append("Short retention may favor staying in the current pipeline or lakehouse workflow.")

    if stable_schema:
        score += 2
        signals.append("Stable schema is a strong Vertica fit because projections and physical design can pay back.")
    else:
        counter_signals.append(
            "Unstable schema should stay close to the source platform or land through flexible handling before typed promotion."
        )

    if score >= 8 and len(counter_signals) <= 1:
        fit_level = "GOOD_VERTICA_FIT"
    elif score >= 5:
        fit_level = "POSSIBLE_VERTICA_FIT"
    elif score >= 3:
        fit_level = "INSUFFICIENT_EVIDENCE"
    else:
        fit_level = "KEEP_ON_CURRENT_PLATFORM"

    markdown = _assessment_markdown(
        source_type=normalized_source_type,
        workload_name=workload_name,
        domain=domain,
        data_volume_tib=data_volume_tib,
        monthly_runs=monthly_runs,
        avg_runtime_minutes=avg_runtime_minutes,
        concurrency=concurrency,
        retention_days=retention_days,
        stable_schema=stable_schema,
        object_store_path=object_store_path,
        fit_level=fit_level,
        fit_score=score,
        signals=signals,
        counter_signals=counter_signals,
        unknowns=unknowns,
    )
    return OffloadAssessment(
        source_type=normalized_source_type,
        workload_name=workload_name,
        domain=domain,
        data_volume_tib=data_volume_tib,
        monthly_runs=monthly_runs,
        avg_runtime_minutes=avg_runtime_minutes,
        concurrency=concurrency,
        retention_days=retention_days,
        stable_schema=stable_schema,
        object_store_path=object_store_path,
        fit_level=fit_level,
        fit_score=score,
        signals=signals,
        counter_signals=counter_signals,
        unknowns=unknowns,
        markdown=markdown,
    )


def write_offload_assessment(assessment: OffloadAssessment, output: str | Path) -> None:
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "OFFLOAD_ADVISOR_REPORT.md").write_text(assessment.markdown, encoding="utf-8")


def _assessment_markdown(
    *,
    source_type: str,
    workload_name: str,
    domain: str,
    data_volume_tib: float,
    monthly_runs: int,
    avg_runtime_minutes: float,
    concurrency: int,
    retention_days: int,
    stable_schema: bool,
    object_store_path: str,
    fit_level: str,
    fit_score: int,
    signals: list[str],
    counter_signals: list[str],
    unknowns: list[str],
) -> str:
    source_label = "Databricks" if source_type == "databricks" else "Snowflake"
    pipeline_action = (
        "Databricks writes curated Delta/table outputs to Parquet in object storage."
        if source_type == "databricks"
        else "Snowflake unloads curated table/query outputs to an external stage with `COPY INTO`."
    )
    signal_lines = "\n".join(f"- {signal}" for signal in signals) or "- No strong offload signals from the provided metrics."
    counter_signal_lines = (
        "\n".join(f"- {counter_signal}" for counter_signal in counter_signals)
        or "- No major counter-signals from the provided metrics."
    )
    unknown_lines = "\n".join(f"- {unknown}" for unknown in unknowns)
    assessment_text = _assessment_text(fit_level)
    rationale_lines = _rationale_lines(fit_level)

    return f"""# Cloud Warehouse Bridge Offload Advisor

## Executive Result

- Source platform: `{source_label}`
- Workload: `{workload_name}`
- Domain: `{domain}`
- Outcome class: `{fit_level}`
- Fit score: `{fit_score}` out of 11

This is a planning artifact, not a benchmark, savings guarantee, migration recommendation, or proof that Vertica is faster or cheaper. Use it to decide whether a measured pilot is worth running.

## Input Facts

- Data volume: `{data_volume_tib:.3f}` TiB
- Monthly runs: `{monthly_runs}`
- Average runtime: `{avg_runtime_minutes:.3f}` minutes
- Expected concurrency: `{concurrency}`
- Retention: `{retention_days}` days
- Stable schema: `{stable_schema}`
- Landing path: `{object_store_path}`

## Fit Signals

{signal_lines}

## Counter-Signals

{counter_signal_lines}

## Unknown / Missing Evidence

{unknown_lines}

## Assessment

{assessment_text}

## Rationale

{rationale_lines}

## Next Validation Step

Run a bounded pilot that measures current-platform export/unload time, object-store listing and validation time, Vertica load or external-read behavior, query runtime, operational complexity, and total recurring cost under the customer's actual governance requirements.

## Proposed Pipeline

1. {pipeline_action}
2. Vertica Power Packs inventory the landing path and validate file size, partitioning, and schema evidence.
3. Generate Vertica landing DDL, `COPY` batch SQL, external-table SQL where appropriate, and reject capture.
4. Load into Vertica and validate row counts, rejects, and reconciliation checks.
5. Promote to governed typed tables and tune projections/resource pools for repeat analytics.

## Telco-Oriented Use Cases

- CDR/event analytics
- Network telemetry and QoE/QoS rollups
- Fraud and anomaly investigation
- Subscriber, device, and location analytics
- Capacity planning
- Mediation and billing reconciliation
- Long-retention regulatory analytics

## Commercial Positioning

Keep `{source_label}` for platform-native, efficient, exploratory, or already well-governed work. Consider a Vertica pilot only for repeatable high-compute analytics that appear durable, governed, cost-sensitive, or performance-sensitive based on measured evidence.

## Product-Marketing Translation

- Technical fact: object-store handoff plus Vertica `COPY`/external-table planning.
- Customer outcome: clearer evaluation path for moving selected recurring analytics into governed analytical serving.
- Technical fact: stable schema and recurring workloads let Vertica physical design pay back.
- Customer outcome: potential for more predictable production analytics when validated by a pilot.
- Technical fact: reject capture and staged promotion are explicit.
- Customer outcome: safer operational movement than ad hoc exports and one-off scripts.

## Native Opportunity

Vertica Engineering could make this evaluation smoother with first-class cloud-warehouse/lakehouse planning workflows: native metadata import, object-store manifest validation, unload/load orchestration, richer schema-drift handling, and built-in workload-fit reporting.
"""


def _assessment_text(fit_level: str) -> str:
    if fit_level == "GOOD_VERTICA_FIT":
        return (
            "The provided facts show multiple Vertica-fit signals and few counter-signals. "
            "This supports a measured Vertica pilot, not an automatic migration decision."
        )
    if fit_level == "POSSIBLE_VERTICA_FIT":
        return (
            "The provided facts show enough signal to investigate, but the decision depends on missing "
            "cost, operational, and measured-performance evidence."
        )
    if fit_level == "INSUFFICIENT_EVIDENCE":
        return (
            "The provided facts are not enough to justify an offload recommendation. Collect current "
            "platform cost, query, data-layout, and governance evidence before proposing a pilot."
        )
    if fit_level == "KEEP_ON_CURRENT_PLATFORM":
        return (
            "The provided facts do not currently justify adding Vertica to this workload path. Keep the "
            "workload on the current platform unless economics, governance, runtime, or concurrency changes."
        )
    raise ValueError(f"Unknown fit_level: {fit_level!r}")


def _rationale_lines(fit_level: str) -> str:
    rationale = {
        "GOOD_VERTICA_FIT": [
            "The workload appears repeatable enough for physical design and operational governance to matter.",
            "The current-platform handoff can be evaluated through object storage without claiming replacement of the source platform.",
            "The next decision should be based on measured pilot evidence.",
        ],
        "POSSIBLE_VERTICA_FIT": [
            "Some signals point toward a governed analytical serving use case.",
            "Counter-signals or missing evidence prevent a confident fit decision.",
            "A small pilot should compare effort, cost, runtime, and operational simplicity.",
        ],
        "INSUFFICIENT_EVIDENCE": [
            "The input facts do not show enough recurring high-compute pressure.",
            "Missing current-platform evidence is material.",
            "The next step is data collection, not migration planning.",
        ],
        "KEEP_ON_CURRENT_PLATFORM": [
            "The workload appears too small, infrequent, short-running, low-concurrency, or schema-fluid for offload complexity.",
            "A current-platform path may be simpler and cheaper unless new evidence emerges.",
            "Do not position Vertica without a specific measured advantage.",
        ],
    }[fit_level]
    return "\n".join(f"- {item}" for item in rationale)

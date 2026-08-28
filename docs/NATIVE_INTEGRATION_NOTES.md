# Native Integration Notes

## Purpose

These notes make the repository useful to Vertica Engineering, product management, product marketing, and technical field teams without implying that this prototype should be merged into Vertica.

The intended value is working prototype plus evidence plus lessons. A successful native product outcome may eventually make some of this external wrapper code unnecessary.

## Capability: Object-Store Inventory Planning

Current external approach: read local paths or inventory CSVs, preserve total object count and byte counts, retain bounded object samples, and generate reviewable plan artifacts.

Public interface used: filesystem metadata, S3-style URI conventions, inventory manifests, and Vertica SQL draft generation.

Friction: large object stores can be expensive or slow to traverse directly, and operators need a way to reason about file sizes, partition layout, and schema evidence before touching production systems.

What the Power Pack demonstrates: manifest-driven planning can represent 100s-TB inventory shapes without unbounded plan output.

Limitations: this does not prove transfer throughput, live S3 listing is optional/future, and generated SQL still requires human review.

Possible native product opportunity: Vertica could expose first-class object-store plan inspection, manifest validation, file-size guidance, partition discovery, and load-path recommendations.

## Capability: Vertica Ingest SQL Generation

Current external approach: generate draft landing-table DDL, external-table SQL where schema evidence is available, `COPY` SQL, rejected-data capture, and bounded COPY batch plans.

Public interface used: public Vertica SQL patterns for `CREATE TABLE`, external tables, `COPY`, parser declarations, and rejected-data handling.

Friction: teams often create ad hoc load scripts, miss reject/reconciliation handling, or skip a clean exploration-to-promotion flow.

What the Power Pack demonstrates: a small profile can produce a repeatable operator review packet before a production load.

Limitations: SQL is a draft, target-version syntax must be reviewed, and the tool does not connect to Vertica or mutate a database by default.

Possible native product opportunity: Vertica could provide built-in dry-run ingest planning with schema inference, batch suggestions, reject-table setup, and reconciliation guidance.

## Capability: Databricks And Snowflake Handoff Planning

Current external approach: generate safe dry-run templates for Databricks export and Snowflake unload patterns into object storage, then generate downstream Vertica planning artifacts.

Public interface used: documented Databricks SQL/export concepts, documented Snowflake `COPY INTO` unload concepts, public object-store conventions, and public Vertica SQL.

Friction: platform teams need a credible way to evaluate whether a recurring workload should remain where it is or be tested in a governed analytical serving engine.

What the Power Pack demonstrates: Databricks/Snowflake-to-object-store-to-Vertica can be treated as an evaluation pattern rather than a replacement claim.

Limitations: templates do not run live exports, do not manage credentials, do not inspect proprietary platform internals, and do not prove cost or runtime advantage.

Possible native product opportunity: Vertica could provide native cloud-warehouse/lakehouse workload intake planning, including metadata import, object-store layout validation, and reviewed load/external-table recommendations.

## Capability: Neutral Workload-Fit Advisor

Current external approach: score user-provided workload facts and produce one of four outcomes: `GOOD_VERTICA_FIT`, `POSSIBLE_VERTICA_FIT`, `INSUFFICIENT_EVIDENCE`, or `KEEP_ON_CURRENT_PLATFORM`.

Public interface used: user-provided workload facts and generated Markdown reports; no private APIs or hidden vendor data are required.

Friction: field and product teams need a disciplined way to separate Vertica-fit signals from unsupported sales claims.

What the Power Pack demonstrates: an advisor can show input facts, fit signals, counter-signals, unknowns, assessment, rationale, and next validation steps without forcing a Vertica-positive answer.

Limitations: the score is a triage aid, not a benchmark, cost model, migration recommendation, or platform ranking.

Possible native product opportunity: Vertica could offer workload-fit reporting that combines measured query/runtime evidence, object-store layout facts, governance requirements, and recommended pilot steps.

## Capability: Physical-Design Advice

Current external approach: generate first-pass segmentation, partition, sort-order, and materialization candidates from source-profile evidence.

Public interface used: source metadata, inferred types, and public Vertica physical-design concepts.

Friction: early pilots often fail to translate source layout and workload shape into Vertica design hypotheses quickly enough.

What the Power Pack demonstrates: even conservative profile evidence can produce a useful review checklist for Vertica specialists.

Limitations: output is not optimizer-grade advice, not a replacement for Database Designer, and not validated against production workload traces.

Possible native product opportunity: Vertica could expose richer programmatic design preflight APIs that connect ingest planning, object-store layout, and workload evidence.

## Recommendation Style

These notes are evidence and opportunity framing only. They do not claim that Vertica Engineering should adopt this implementation. They identify friction, demonstrate possible user experience, and show where native Vertica capabilities could reduce or eliminate external wrapper code.

import csv
import tempfile
import unittest
from pathlib import Path

from vpowerpacks.connectors import build_connector_plan
from vpowerpacks.offload import build_offload_assessment
from vpowerpacks.planner import build_ingest_plan
from vpowerpacks.profiler import detect_format, profile_inventory_csv, profile_source


ROOT = Path(__file__).resolve().parents[1]


class ProfilerAndPlannerTests(unittest.TestCase):
    def test_detect_format_handles_compressed_csv(self) -> None:
        self.assertEqual(detect_format("events.csv.gz"), ("csv", True))

    def test_csv_profile_infers_basic_types(self) -> None:
        profile = profile_source(str(ROOT / "examples" / "sample_data" / "properties.csv"))
        columns = {column.name: column for column in profile.columns}

        self.assertEqual(profile.detected_format, "csv")
        self.assertEqual(columns["property_id"].recommended_vertica_type, "VARCHAR(1024)")
        self.assertEqual(columns["assessed_value"].recommended_vertica_type, "INT")
        self.assertEqual(columns["last_sale_date"].recommended_vertica_type, "DATE")
        self.assertEqual(columns["is_active"].recommended_vertica_type, "BOOLEAN")
        self.assertEqual(columns["latitude"].recommended_vertica_type, "FLOAT")

    def test_jsonl_profile_flattens_nested_fields(self) -> None:
        profile = profile_source(str(ROOT / "examples" / "sample_data" / "events.jsonl"))
        columns = {column.name: column for column in profile.columns}

        self.assertEqual(profile.detected_format, "jsonl")
        self.assertEqual(columns["attrs_source"].recommended_vertica_type, "VARCHAR(1024)")
        self.assertEqual(columns["amount"].recommended_vertica_type, "INT")
        self.assertEqual(columns["event_ts"].recommended_vertica_type, "TIMESTAMP")

    def test_plan_generates_vertica_artifacts(self) -> None:
        profile = profile_source(str(ROOT / "examples" / "sample_data" / "properties.csv"))
        plan = build_ingest_plan(profile, "demo", "properties")

        self.assertIn("CREATE TABLE IF NOT EXISTS demo.properties", plan.create_table_sql)
        self.assertIn("CREATE EXTERNAL TABLE demo.properties_ext", plan.external_table_sql)
        self.assertIn("COPY demo.properties", plan.copy_sql)
        self.assertIn("COPY demo.properties", plan.copy_batches_sql)
        self.assertIn("property_id", plan.design_advice_sql)
        self.assertIn("Physical Design Advice", plan.markdown)
        self.assertIn("REJECTED DATA AS TABLE demo.properties_rejects", plan.copy_sql)

    def test_plan_rejects_unsafe_target_identifiers(self) -> None:
        profile = profile_source(str(ROOT / "examples" / "sample_data" / "properties.csv"))

        with self.assertRaises(ValueError):
            build_ingest_plan(profile, "demo;drop_schema", "properties")

        with self.assertRaises(ValueError):
            build_ingest_plan(profile, "demo", "properties;drop_table")

    def test_plan_escapes_source_uri_sql_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote'sample.csv"
            path.write_text("id,value\n1,10\n", encoding="utf-8")

            profile = profile_source(str(path))
            plan = build_ingest_plan(profile, "demo", "quoted_source")

            self.assertIn("quote''sample.csv", plan.copy_sql)
            self.assertIn("quote''sample.csv", plan.external_table_sql)

    def test_copy_batches_escape_source_uri_sql_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "part'one.csv").write_text("id,value\n1,10\n", encoding="utf-8")
            (root / "part'two.csv").write_text("id,value\n2,20\n", encoding="utf-8")

            profile = profile_source(str(root))
            plan = build_ingest_plan(profile, "demo", "quoted_batches", batch_target_bytes=1, batch_max_files=1)

            self.assertIn("part''one.csv", plan.copy_batches_sql)
            self.assertIn("part''two.csv", plan.copy_batches_sql)

    def test_inventory_profile_scales_without_retaining_all_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "inventory.csv"
            object_count = 100_000
            object_size = 5 * 1024**3
            with inventory.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["key", "size_bytes"])
                writer.writeheader()
                for idx in range(object_count):
                    writer.writerow({"key": f"year=2026/month=08/part-{idx:06d}.parquet", "size_bytes": object_size})

            profile = profile_inventory_csv(str(inventory), "s3://example-lake/example-events", sample_objects=25)
            plan = build_ingest_plan(profile, "demo", "enterprise_events")

            self.assertEqual(profile.total_object_count, object_count)
            self.assertEqual(profile.total_known_bytes, object_count * object_size)
            self.assertEqual(len(profile.objects), 25)
            self.assertIn("Objects: 100000", plan.markdown)
            self.assertIn("Profiled object samples retained: 25", plan.markdown)
            self.assertIn("External table SQL unavailable", plan.external_table_sql)

    def test_inventory_profile_with_sample_schema_generates_external_sql(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "inventory.csv"
            with inventory.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["key", "size_bytes"])
                writer.writeheader()
                writer.writerow({"key": "state=00/year=2026/month=08/part-000001.csv", "size_bytes": 128})

            profile = profile_inventory_csv(str(inventory), "s3://example-lake/example-events", format_hint="csv")
            sample = profile_source(str(ROOT / "examples" / "sample_data" / "properties.csv"))
            profile.columns = sample.columns
            profile.row_sample_count = sample.row_sample_count
            plan = build_ingest_plan(profile, "demo", "enterprise_events")

            self.assertIn("CREATE EXTERNAL TABLE demo.enterprise_events_ext", plan.external_table_sql)
            self.assertIn("property_id VARCHAR(1024)", plan.external_table_sql)
            self.assertIn("FROM 's3://example-lake/example-events/*'", plan.external_table_sql)
            self.assertNotIn("s3:/example-lake", plan.external_table_sql)

    def test_design_advice_identifies_time_and_distribution_candidates(self) -> None:
        profile = profile_source(str(ROOT / "examples" / "sample_data" / "events.jsonl"))
        plan = build_ingest_plan(profile, "demo", "events")

        self.assertIn("Partition candidates", plan.design_advice_sql)
        self.assertIn("event_ts", plan.design_advice_sql)
        self.assertIn("property_id", plan.design_advice_sql)

    def test_copy_batch_plan_splits_retained_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for idx in range(3):
                item = root / f"part-{idx}.csv"
                item.write_text("id,value\n1,10\n", encoding="utf-8")

            profile = profile_source(str(root))
            plan = build_ingest_plan(profile, "demo", "small_batches", batch_target_bytes=1, batch_max_files=1)

            self.assertIn("-- Batches: 3", plan.copy_batches_sql)
            self.assertEqual(plan.copy_batches_sql.count("COPY demo.small_batches"), 3)

    def test_connector_plan_generates_safe_postgres_template(self) -> None:
        plan = build_connector_plan(
            source_type="postgres",
            source_table="public.orders",
            target_schema="demo",
            target_table="orders",
            incremental_column="updated_at",
        )

        self.assertIn("FROM public.orders", plan.extract_sql)
        self.assertIn("updated_at >= :last_successful_watermark", plan.extract_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS demo.orders_landing", plan.landing_sql)
        self.assertIn("COPY demo.orders_landing", plan.copy_sql)

    def test_connector_plan_generates_databricks_export_template(self) -> None:
        plan = build_connector_plan(
            source_type="databricks",
            source_table="telco.curated_cdr",
            target_schema="demo",
            target_table="cdr_events",
            output_format="parquet",
            incremental_column="event_ts",
        )

        self.assertIn("CREATE OR REPLACE TEMP VIEW vertica_powerpack_export", plan.extract_sql)
        self.assertIn("FROM telco.curated_cdr", plan.extract_sql)
        self.assertIn("event_ts >= '{LAST_SUCCESSFUL_WATERMARK}'", plan.extract_sql)
        self.assertIn("USING PARQUET", plan.extract_sql)
        self.assertIn("Databricks/Spark job", plan.markdown)

    def test_connector_plan_generates_snowflake_unload_template(self) -> None:
        plan = build_connector_plan(
            source_type="snowflake",
            source_table="analytics.fact_usage",
            target_schema="demo",
            target_table="fact_usage",
            output_format="parquet",
        )

        self.assertIn("COPY INTO @example_external_stage/analytics/fact_usage/", plan.extract_sql)
        self.assertIn("FILE_FORMAT = (TYPE = PARQUET)", plan.extract_sql)
        self.assertIn("Snowflake `COPY INTO`", plan.markdown)

    def test_connector_plan_rejects_unsafe_source_table(self) -> None:
        with self.assertRaises(ValueError):
            build_connector_plan(
                source_type="sqlserver",
                source_table="dbo.orders;drop",
                target_schema="demo",
                target_table="orders",
            )

    def test_offload_advisor_scores_good_telco_candidate(self) -> None:
        assessment = build_offload_assessment(
            source_type="databricks",
            workload_name="cdr_rollups",
            domain="telco",
            data_volume_tib=75.0,
            monthly_runs=400,
            avg_runtime_minutes=45.0,
            concurrency=25,
            retention_days=730,
            stable_schema=True,
            object_store_path="s3://example-landing/telco/cdr_rollups/",
        )

        self.assertEqual(assessment.fit_level, "GOOD_VERTICA_FIT")
        self.assertIn("CDR/event analytics", assessment.markdown)
        self.assertIn("Databricks writes curated Delta/table outputs", assessment.markdown)
        self.assertIn("Counter-Signals", assessment.markdown)
        self.assertIn("Unknown / Missing Evidence", assessment.markdown)
        self.assertIn("Product-Marketing Translation", assessment.markdown)

    def test_offload_advisor_can_return_possible_fit(self) -> None:
        assessment = build_offload_assessment(
            source_type="databricks",
            workload_name="monthly_network_quality_rollup",
            domain="telco",
            data_volume_tib=4.0,
            monthly_runs=40,
            avg_runtime_minutes=18.0,
            concurrency=4,
            retention_days=180,
            stable_schema=True,
            object_store_path="s3://example-landing/telco/monthly_quality/",
        )

        self.assertEqual(assessment.fit_level, "POSSIBLE_VERTICA_FIT")
        self.assertIn("Counter-Signals", assessment.markdown)
        self.assertIn("measured-performance evidence", assessment.markdown)

    def test_offload_advisor_can_return_insufficient_evidence(self) -> None:
        assessment = build_offload_assessment(
            source_type="snowflake",
            workload_name="occasional_usage_extract",
            domain="general analytics",
            data_volume_tib=1.5,
            monthly_runs=10,
            avg_runtime_minutes=12.0,
            concurrency=1,
            retention_days=365,
            stable_schema=False,
            object_store_path="s3://example-landing/usage_extract/",
        )

        self.assertEqual(assessment.fit_level, "INSUFFICIENT_EVIDENCE")
        self.assertIn("Collect current", assessment.markdown)
        self.assertIn("The next step is data collection", assessment.markdown)

    def test_offload_advisor_can_keep_workload_on_current_platform(self) -> None:
        assessment = build_offload_assessment(
            source_type="snowflake",
            workload_name="small_native_dashboard",
            domain="department analytics",
            data_volume_tib=0.05,
            monthly_runs=4,
            avg_runtime_minutes=1.5,
            concurrency=1,
            retention_days=30,
            stable_schema=False,
            object_store_path="s3://example-landing/department/dashboard/",
        )

        self.assertEqual(assessment.fit_level, "KEEP_ON_CURRENT_PLATFORM")
        self.assertGreater(len(assessment.counter_signals), 3)
        self.assertIn("do not currently justify adding Vertica", assessment.markdown)
        self.assertIn("Do not position Vertica without a specific measured advantage", assessment.markdown)

    def test_offload_advisor_rejects_unsupported_source(self) -> None:
        with self.assertRaises(ValueError):
            build_offload_assessment(
                source_type="postgres",
                workload_name="orders",
                data_volume_tib=1.0,
                monthly_runs=10,
                avg_runtime_minutes=5.0,
                concurrency=1,
                retention_days=30,
                stable_schema=True,
            )


if __name__ == "__main__":
    unittest.main()

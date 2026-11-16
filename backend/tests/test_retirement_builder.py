from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings
from app.payroll_source import PAYROLL_QUERY_TYPE, load_payroll_source, payroll_report_query
from app.retirement_results import InvalidRun, build_report_files
from app.routers import retirement_builder as rb


def input_job(**sections):
    return rb.RetirementBuilderJobInput.model_validate(sections)


class MappingColumnOptionsTests(TestCase):
    def test_display_labels_and_formats_survive_normalized_source_names(self):
        rows = [
            {"mapping_column": "company_name", "mapping_column_desc": "Company Name", "mapping_column_dt": "varchar(120)"},
            {"mapping_column": "payroll_month", "mapping_column_desc": "Pay Date", "mapping_column_dt": "datetime"},
            {"mapping_column": "hours_worked", "mapping_column_desc": "Hours Worked", "mapping_column_dt": "decimal(6, 2)"},
        ]
        with patch.object(rb.engine, "connect") as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.mappings.return_value.all.return_value = rows
            self.assertEqual(rb._mapping_column_types(), {"Company Name": "text", "Pay Date": "date", "Hours Worked": "number"})


class FileFormatTests(TestCase):
    def test_database_delimiters_preserve_whitespace_and_resolve_legacy_jobs(self):
        connection = Mock()
        connection.execute.return_value.mappings.return_value = [
            {"filetyp": "Comma", "delimiter": ","},
            {"filetyp": "Space", "delimiter": " "},
            {"filetyp": "Tab", "delimiter": "\t"},
            {"filetyp": "Unconfigured", "delimiter": None},
        ]
        self.assertEqual(rb._file_format_delimiter(connection, "CSV"), ",")
        self.assertEqual(rb._file_format_delimiter(connection, "CSV_TAB"), "\t")
        self.assertEqual(rb._file_format_delimiter(connection, "Space"), " ")
        self.assertIsNone(rb._file_format_delimiter(connection, "Unconfigured"))


class PayrollQueryTests(TestCase):
    def test_existing_payroll_query_uses_the_procedure_from_the_current_environment(self):
        job = rb.RetirementBuilderJob.model_validate({
            "id": 31,
            "general": {"reportSource": "companyPayroll"},
            "mapping": {"rows": [{"field": "Company Name"}]},
        })
        original = Settings(_env_file=None, payroll_report_procedure="dbo.usp_CompanyPayrollReport")
        with patch("app.payroll_source.get_settings", return_value=original):
            saved_query = payroll_report_query(job)

        with patch.dict("os.environ", {"PAYROLL_REPORT_PROCEDURE": "usp_RenamedPayrollReport"}):
            updated = Settings(_env_file=None)
        for query in (saved_query, saved_query.replace("[dbo].[usp_CompanyPayrollReport]", "dbo.usp_CompanyPayrollReport")):
            with self.subTest(query=query), patch("app.payroll_source.get_settings", return_value=updated):
                job.queryConfiguration = [rb.QueryConfigurationRow(recttype=PAYROLL_QUERY_TYPE, query=query)]
                connection = Mock()
                cursor = MagicMock()
                connection.connection.cursor.return_value = cursor
                cursor.description = [("Record Type",), ("Company Name",)]
                cursor.__iter__.return_value = [("D", "Example Company")]

                source = load_payroll_source(connection, job)

                expected = saved_query.replace("[dbo].[usp_CompanyPayrollReport]", "[dbo].[usp_RenamedPayrollReport]")
                self.assertEqual(payroll_report_query(job), expected)
                cursor.execute.assert_called_once_with(expected)
                self.assertEqual(job.queryConfiguration[0].query, query)
                self.assertIn(b"Example Company", source)

    def test_procedure_configuration_rejects_sql_statements(self):
        with self.assertRaisesRegex(ValidationError, "PAYROLL_REPORT_PROCEDURE must be a procedure name"):
            Settings(_env_file=None, payroll_report_procedure="dbo.usp_Report; SELECT 1")

    def test_client_id_filenames_use_payroll_company_ids(self):
        job = rb.RetirementBuilderJob.model_validate({
            "id": 31,
            "general": {"fileFormat": "CSV", "reportSource": "companyPayroll", "outputFileNameFormat": "Client ID + Payday"},
            "mapping": {"rows": [{"field": "Employee Count"}]},
        })
        query = payroll_report_query(job)
        job.queryConfiguration = [rb.QueryConfigurationRow(recttype=PAYROLL_QUERY_TYPE, query=query)]
        connection = Mock()
        cursor = MagicMock()
        connection.connection.cursor.return_value = cursor
        connection.execute.return_value = [("Company A", 101), ("Company B", 102)]
        cursor.description = [(name,) for name in ("Record Type", "Company Name", "Pay Date", "Employee Count")]
        cursor.__iter__.return_value = [("D", "Company A", datetime(2026, 11, 11), 1),
                                        ("D", "Company B", datetime(2026, 11, 12), 2)]

        source = load_payroll_source(connection, job)
        files = build_report_files(job, source, from_payroll_procedure=True)

        cursor.execute.assert_called_once_with(query)
        self.assertIn("[Company Name]", query.split("SELECT TOP", 1)[1].split(" FROM ", 1)[0])
        self.assertEqual({file.file_name: file.csv.splitlines()[1] for file in files},
                         {"101_2026-11-11.csv": "1", "102_2026-11-12.csv": "2"})
        self.assertTrue(all(file.client_ids is None for file in files))

    def test_run_rejects_a_saved_query_that_does_not_match_the_mappings(self):
        job = rb.RetirementBuilderJob.model_validate({
            "id": 31,
            "general": {"reportSource": "companyPayroll"},
            "mapping": {"rows": [{"field": "Company Name"}]},
            "queryConfiguration": [{"recttype": PAYROLL_QUERY_TYPE, "query": "SELECT 1"}],
        })
        connection = Mock()

        with self.assertRaisesRegex(InvalidRun, "saved payroll query does not match"):
            load_payroll_source(connection, job)

        connection.connection.cursor.assert_not_called()


class JobValidationTests(TestCase):
    def test_required_create_fields_fail_before_connecting(self):
        for general, field in (({}, "fileName"), ({"fileName": "QA"}, "fileFormat")):
            with self.subTest(field=field), patch.object(rb.engine, "begin") as begin:
                with self.assertRaises(HTTPException) as error:
                    rb.create_retirement_builder_job(input_job(general=general))
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(error.exception.detail[0]["loc"], ["body", "general", field])
                begin.assert_not_called()

    def test_invalid_update_values_fail_before_connecting(self):
        cases = (
            ({"general": {"fileFormat": " "}}, ["general", "fileFormat"]),
            ({"schedule": {"startDate": "1700-01-01"}}, ["schedule", "startDate"]),
            ({"schedule": {"hour": "0"}}, ["schedule", "hour"]),
            ({"schedule": {"minute": "60"}}, ["schedule", "minute"]),
            ({"mapping": {"rows": [{"startPosition": "-1"}]}}, ["mapping", "rows", 0, "startPosition"]),
            ({"mapping": {"rows": [{"length": "abc"}]}}, ["mapping", "rows", 0, "length"]),
            ({"mapping": {"rows": [{"length": "2147483648"}]}}, ["mapping", "rows", 0, "length"]),
            ({"mapping": {"rows": []}}, ["mapping", "rows"]),
            ({"mapping": {"rows": [{"field": " "}]}}, ["mapping", "rows", 0, "field"]),
            ({"fileSettings": {"conditionalStatements": [{"mappingColumn": "Gross Pay", "condition": "contains", "value": "10"}]}},
             ["fileSettings", "conditionalStatements", 0, "condition"]),
            ({"subscriptions": {"rows": [{"client": "720", "email": "qa@example.invalid, invalid"}]}},
             ["subscriptions", "rows", 0, "email"]),
        )
        for payload, path in cases:
            with self.subTest(path=path), patch.object(rb.engine, "begin") as begin:
                with self.assertRaises(HTTPException) as error:
                    rb.update_retirement_builder_job(1, input_job(**payload))
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(error.exception.detail[0]["loc"], ["body", *path])
                begin.assert_not_called()

    def test_valid_partial_update_keeps_omitted_legacy_values(self):
        payload = input_job(general={"description": "New description"})
        original = rb.RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileName": "", "fileFormat": "CSV"},
            "schedule": {"hour": "0"},
        })
        rb._validate_payload(payload)
        merged = rb._complete_update_payload(payload, original)
        self.assertEqual(merged.general.description, "New description")
        self.assertEqual(merged.general.fileName, "")
        self.assertEqual(merged.schedule.hour, "0")

    def test_valid_edges_and_multi_email(self):
        payload = input_job(
            general={"fileName": "QA", "fileFormat": "CSV (Pipe Delimited)"},
            schedule={"startDate": "1753-01-01", "hour": "12", "minute": "59"},
            mapping={"rows": [{"field": "Pay Date", "startPosition": "0", "length": "2147483647"}]},
            subscriptions={"rows": [{"client": "720", "email": "qa+1@example.invalid, qa.2@example.invalid"}]},
        )
        rb._validate_payload(payload, creating=True)

    def test_condition_value_normalizes_at_sql_precision(self):
        for value, expected in (("123.456", "123.46"), ("-1.005", "-1.01"), ("-0.001", "0.00"),
                                ("9999999999999999.994", "9999999999999999.99")):
            with self.subTest(value=value):
                self.assertEqual(rb._condition_value(value, ["value"]), expected)
        for value in ("NaN", "Infinity", "9999999999999999.995", "invalid"):
            with self.subTest(value=value), self.assertRaises(HTTPException) as error:
                rb._condition_value(value, ["value"])
            self.assertEqual(error.exception.status_code, 422)

    def test_list_runtime_is_padded_without_changing_history_status(self):
        job = rb._api_job_from_row({"jobid": 1, "runtime": "1:5 PM", "Job_Last_Status": None, "joblastrun": "2026-11-11"})
        self.assertEqual(job["runtime"], "1:05 PM")
        self.assertEqual(job["schedule"]["minute"], "05")
        self.assertIsNone(job["Job_Last_Status"])
        self.assertIsNone(job["joblastrun"])

    def test_run_status_uses_persisted_failure_after_attempt(self):
        row = {"jobid": 83, "joblastrun": "2026-11-11", "Job_Last_Status": "Success"}
        with rb._active_report_run(83):
            self.assertEqual(rb._api_job_from_row(row)["Job_Last_Status"], "In Progress")
        failed = rb._api_job_from_row({**row, "Job_Last_Status": "Failed"})
        self.assertEqual(failed["Job_Last_Status"], "Failed")
        self.assertEqual(failed["joblastrun"], row["joblastrun"])


class JobIdempotencyTests(TestCase):
    def setUp(self):
        self.payload = input_job(general={"fileName": "QA", "fileFormat": "CSV"})
        self.key = uuid4().hex

    def test_same_key_replays_and_changed_payload_conflicts(self):
        with patch.object(rb, "_create_job", return_value=rb.RetirementBuilderJob(id=1)) as create:
            first = rb.create_retirement_builder_job(self.payload, self.key)
            retry = rb.create_retirement_builder_job(self.payload, self.key)
            self.assertEqual(first, retry)
            with self.assertRaises(HTTPException) as error:
                rb.create_retirement_builder_job(input_job(general={"fileName": "Different"}), self.key)
            self.assertEqual(error.exception.status_code, 409)
            create.assert_called_once()

    def test_concurrent_retries_share_one_insert(self):
        entered = Event()
        release = Event()

        def create(payload):
            entered.set()
            if not release.wait(timeout=3):
                raise TimeoutError("Test did not release create")
            return rb.RetirementBuilderJob(id=2)

        with patch.object(rb, "_create_job", side_effect=create) as write, ThreadPoolExecutor(2) as executor:
            first = executor.submit(rb.create_retirement_builder_job, self.payload, self.key)
            try:
                self.assertTrue(entered.wait(timeout=3))
                second = executor.submit(rb.create_retirement_builder_job, self.payload, self.key)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3), second.result(timeout=3))
            write.assert_called_once()

    def test_failures_are_not_cached_and_unkeyed_creates_still_insert(self):
        with patch.object(rb, "_create_job", side_effect=[
            HTTPException(status_code=500), rb.RetirementBuilderJob(id=3),
            rb.RetirementBuilderJob(id=4), rb.RetirementBuilderJob(id=5),
        ]) as write:
            with self.assertRaises(HTTPException):
                rb.create_retirement_builder_job(self.payload, self.key)
            self.assertEqual(rb.create_retirement_builder_job(self.payload, self.key).id, 3)
            self.assertEqual(rb.create_retirement_builder_job(self.payload).id, 4)
            self.assertEqual(rb.create_retirement_builder_job(self.payload).id, 5)
            self.assertEqual(write.call_count, 4)

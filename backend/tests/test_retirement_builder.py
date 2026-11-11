from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.payroll_source import PAYROLL_QUERY_TYPE, load_payroll_source
from app.retirement_results import InvalidRun
from app.routers import retirement_builder as rb


def input_job(**sections):
    return rb.RetirementBuilderJobInput.model_validate(sections)


class PayrollQueryTests(TestCase):
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
            mapping={"rows": [{"startPosition": "0", "length": "2147483647"}]},
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

    def test_run_status_changes_without_overwriting_saved_history(self):
        row = {"jobid": 83, "joblastrun": "2026-11-11", "Job_Last_Status": "Success"}
        with self.assertRaisesRegex(ValueError, "invalid input"), rb._active_report_run(83):
            self.assertEqual(rb._api_job_from_row(row)["Job_Last_Status"], "In Progress")
            raise ValueError("invalid input")
        failed = rb._api_job_from_row(row)
        self.assertEqual(failed["Job_Last_Status"], "Failed")
        self.assertEqual(failed["joblastrun"], row["joblastrun"])
        with rb._active_report_run(83):
            self.assertEqual(rb._api_job_from_row(row)["Job_Last_Status"], "In Progress")
        self.assertEqual(rb._api_job_from_row(row)["Job_Last_Status"], "Success")


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

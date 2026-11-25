"""Synthetic API fixtures only. Every DB/SMTP boundary is mocked or prohibited."""

from datetime import date, datetime
from decimal import Decimal
import asyncio
import json
from types import SimpleNamespace
from urllib.parse import urlsplit
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException

from app.core.config import Settings
from app.retirement_procedure import ProcedureResultSet, ProcedureSource
from app.retirement_results import ReportDateRange
from app.retirement_datasets import tag_dataset_query
from app.routers import payroll_builder as pb


def fixture_job():
    return pb.PayrollJob.model_validate({
        "id": 987654,
        "general": {"fileName": "Synthetic", "fileFormat": "CSV", "description": "Fixture",
                    "outputFileNameFormat": "FILE_NAME", "enable": True},
        "schedule": {"startDate": None},
        "mapping": {"includeHeader": True, "rows": [
            {"field": "Wages", "mappingColumn": "earnings", "recordType": "Detail", "colSeqNo": 1,
             "startPosition": "0", "length": "0"}]},
        "queryConfiguration": [
            {"recttype": "H", "query": "SELECT TOP 1 valid_flag,retnum,paydate AS sort1,'Wages' AS [Wages]"},
            {"recttype": "D", "query": "SELECT valid_flag,retnum,paydate AS sort1,earnings AS [Wages]"},
            {"recttype": "T", "query": "SELECT DISTINCT valid_flag,retnum,paydate AS sort1"},
        ],
        "subscriptions": {"rows": [{"client": "204", "email": "fixture@example.invalid"}]},
    })


CATALOG = [
    {"mapping_column": "earnings", "mapping_column_desc": "Earnings", "mapping_column_dt": "numeric", "ApplyGroup": "Yes"},
    {"mapping_column": "firstname", "mapping_column_desc": "First Name", "mapping_column_dt": "char", "ApplyGroup": "No"},
    {"mapping_column": "Default", "mapping_column_desc": "Default", "mapping_column_dt": "all", "ApplyGroup": "No"},
    {"mapping_column": "RetNum", "mapping_column_desc": "Client Id in Prism ", "mapping_column_dt": "char", "ApplyGroup": "No"},
    {"mapping_column": "paydate", "mapping_column_desc": "Pay Date", "mapping_column_dt": "date", "ApplyGroup": "No"},
]


def create_payload():
    data = fixture_job().model_dump()
    data["schedule"] = {"startDate": None}
    data["queryConfiguration"] = []
    return pb.PayrollJobInput.model_validate(data)


class InProcessClient:
    """Minimal ASGI transport; no sockets, lifespan startup, httpx or live services."""
    def __init__(self, app):
        self.app = app

    def request(self, method, url, **options):
        parts = urlsplit(url)
        content = options.get("content", b"")
        headers = []
        if "json" in options:
            content = json.dumps(options["json"]).encode()
            headers = [(b"content-type", b"application/json")]
        sent = []
        received = False
        async def receive():
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": content, "more_body": False}
            return {"type": "http.disconnect"}
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "http_version": "1.1", "method": method,
                 "path": parts.path, "raw_path": parts.path.encode(),
                 "query_string": parts.query.encode(), "headers": headers,
                 "scheme": "http", "server": ("mock", 80), "client": ("mock", 123), "root_path": ""}
        asyncio.run(self.app(scope, receive, send))
        body = b"".join(message.get("body", b"") for message in sent)
        return SimpleNamespace(status_code=sent[0]["status"], text=body.decode(), json=lambda: json.loads(body))

    def get(self, url, **options):
        return self.request("GET", url, **options)

    def put(self, url, **options):
        return self.request("PUT", url, **options)

    def post(self, url, **options):
        return self.request("POST", url, **options)


class PayrollApiTests(TestCase):
    def setUp(self):
        self.db_guard = patch("pyodbc.connect", side_effect=AssertionError("Live DB access prohibited"))
        self.db_guard.start()
        self.addCleanup(self.db_guard.stop)
        app = FastAPI()
        app.include_router(pb.router, prefix="/api/v1")
        self.client = InProcessClient(app)
        self.base = "/api/v1/payroll-builder"

    def validation(self):
        self.addCleanup(patch.stopall)
        patch.object(pb, "_catalog", return_value=CATALOG).start()
        patch.object(pb, "_rows", return_value=[{"grouping_id": "retnum", "grouping_desc": "Client ID"}]).start()
        patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}).start()
        return MagicMock()

    def test_read_options_uses_catalog_and_common_formats_without_mutation(self):
        def rows(connection, statement, params=None):
            sql = str(statement)
            if "payroll_mapping_column" in sql:
                return CATALOG
            if "payroll_master_grouping" in sql:
                return [{"grouping_id": "retnum", "grouping_desc": "Client ID"}]
            return [{"jobformat": "######.##", "jobformattype": "numeric", "jobdesc": "Number"}]
        with patch.object(pb.engine, "connect"), patch.object(pb, "_rows", side_effect=rows), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}):
            result = self.client.get(self.base + "/options")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["wageColumns"], [{"value": "earnings", "label": "Earnings"}])
        self.assertEqual(result.json()["mappingColumnTypes"]["Earnings"], "number")
        self.assertEqual(len(result.json()["outputFileNameFormats"]), 7)

    def test_pay_codes_are_scoped_by_numeric_client_and_search(self):
        rows = [{"u2_id": "000204", "pay_code": "OT", "pay_code_desc": "Overtime"},
                {"u2_id": "000719", "pay_code": "OTHER", "pay_code_desc": "Other client"},
                {"u2_id": "000204", "pay_code": "REG", "pay_code_desc": "Regular"}]
        with patch.object(pb.engine, "connect"), patch.object(pb, "_rows", return_value=rows):
            result = self.client.get(self.base + "/pay-codes?client_id=204&search=over")
        self.assertEqual(result.json(), [{"value": "OT", "label": "Overtime"}])
        self.assertEqual(self.client.get(self.base + "/pay-codes?client_id=0").status_code, 422)

    def test_invalid_filename_options_are_rejected_on_create_and_update_before_writes(self):
        self.validation()
        for value in ("UNKNOWN", "", "   ", "CLIENT_CLIENT", "FILENAME_EXTRA", "File Name-", "PAYDAY_CLIENT"):
            for method in ("POST", "PUT"):
                with self.subTest(value=value, method=method), patch.object(pb.engine, "begin"), \
                     patch.object(pb, "_read_job", return_value=fixture_job()), \
                     patch.object(pb, "_execute") as execute, \
                     patch.object(pb, "_write_details") as details, \
                     patch.object(pb.shared, "_execute_identity_query") as identity:
                    payload = create_payload().model_dump(mode="json") if method == "POST" else {"general": {}}
                    if method == "POST":
                        payload["schedule"] = {"startDate": None}
                    payload["general"]["outputFileNameFormat"] = value
                    path = self.base + "/jobs" + ("/987654" if method == "PUT" else "")
                    response = self.client.request(method, path, json=payload)
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(response.json()["detail"], "Select a configured output filename format.")
                    execute.assert_not_called()
                    details.assert_not_called()
                    identity.assert_not_called()

    def test_configured_filename_options_and_legacy_spellings_remain_valid(self):
        connection = self.validation()
        cases = (
            ("FILENAME", "File Name"), ("CLIENT", "ClientId"), ("PAYDAY", "PayDate"),
            ("FILENAME_CLIENT", "File Name-ClientId"), ("FILENAME_PAYDAY", "File Name-PayDate"),
            ("CLIENT_PAYDAY", "ClientId-PayDate"), ("FILENAME_CLIENT_PAYDAY", "File Name-ClientId-PayDate"),
            ("FILE_NAME", "File Name"),
        )
        for code, stored in cases:
            for value in (code, stored, f" {stored.lower()} "):
                with self.subTest(value=value):
                    payload = create_payload()
                    payload.general.outputFileNameFormat = value
                    normalized = pb._normalized(connection, payload)
                    self.assertEqual(pb._main_values(normalized)["fileNameFormat"], "CLIENT" if code == "CLIENT" else stored)
        connection.execute.assert_not_called()

    def test_listing_includes_disabled_jobs_without_retirement_status(self):
        rows = [{"jobid": 987654, "isEnabled": False, "jobfilename": "Fixture", "startDateTime": None}]
        with patch.object(pb.engine, "connect"), patch.object(pb, "_rows", return_value=rows), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.dict(pb.shared._active_runs, {987654: 1}):
            result = self.client.get(self.base + "/jobs")
        self.assertFalse(result.json()[0]["general"]["enable"])
        self.assertNotEqual(result.json()[0]["Job_Last_Status"], "In Progress")

    def test_get_returns_not_found(self):
        with patch.object(pb.engine, "connect"), patch.object(pb, "_read_job", return_value=None):
            self.assertEqual(self.client.get(self.base + "/jobs/987654").status_code, 404)

    def test_update_keeps_saved_queries_and_writes_only_payroll_configuration(self):
        job = fixture_job()
        self.validation()
        with patch.object(pb.engine, "begin") as begin, patch.object(pb, "_read_job", return_value=job):
            connection = begin.return_value.__enter__.return_value
            result = self.client.put(self.base + "/jobs/987654", json={"general": {"description": "Changed fixture"}})
        self.assertEqual(result.status_code, 200, result.text)
        calls = [str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertTrue(any("UPDATE [dbo].[payroll_job]" in sql for sql in calls))
        self.assertFalse(any("payroll_query" in sql for sql in calls))
        self.assertFalse(any("dbo.rjob" in sql or "[dbo].[rjob" in sql for sql in calls))
        self.assertEqual(result.json()["queryConfiguration"], job.model_dump(mode="json")["queryConfiguration"])

    def test_mapping_source_change_rebuilds_only_this_jobs_configuration(self):
        job = fixture_job()
        self.validation()
        mappings = job.mapping.model_dump()
        mappings["rows"][0]["mappingColumn"] = "firstname"
        with patch.object(pb.engine, "begin") as begin, patch.object(pb, "_read_job", return_value=job), \
             patch.object(pb, "_execute", wraps=pb._execute) as execute:
            response = self.client.put(self.base + "/jobs/987654", json={"mapping": mappings})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(begin.call_count, 1)
        deletes = [call.args[2] for call in execute.call_args_list if call.args[1] == 203]
        self.assertEqual(deletes, [{"jobid": 987654}])
        queries = [call.args[2] for call in execute.call_args_list if call.args[1] == 204]
        self.assertTrue(any("firstname" in row["Query"] for row in queries if row["recttype"] == "D"))
        self.assertFalse(response.json()["queryLocked"])

    def test_dataset_add_remove_sort_and_conditions_rebuild_together(self):
        job = fixture_job()
        connection = self.validation()
        changed = job.model_copy(deep=True)
        changed.mapping.rows.append(changed.mapping.rows[0].model_copy(update={"field": "Name", "mappingColumn": "firstname", "dataSetNo": 2}))
        changed.fileSettings = type(job.fileSettings).model_validate({
            "sortingOrder": [{"orderBy": "1", "mappingColumn": "paydate"}],
            "conditionalStatements": [{"mappingColumn": "earnings", "condition": ">", "value": "0", "valueType": "number"}]})
        for candidate in (changed, job):
            with self.subTest(datasets=len(candidate.mapping.rows)), patch.object(pb, "_execute") as execute:
                pb._write_details(connection, job.id, candidate, creating=False, rebuild_queries=True)
                self.assertEqual(sum(call.args[1] == 203 for call in execute.call_args_list), 1)
                details = [call.args[2] for call in execute.call_args_list if call.args[1] == 204 and call.args[2]["recttype"] == "D"]
                self.assertEqual(len(details), len(candidate.mapping.rows))
                if candidate is changed:
                    self.assertTrue(any("__ecs_dataset_2" in row["Query"] for row in details))
                    self.assertTrue(all("paydate" in row["sortOrder"] and "earnings" in row["conditionalStmt"] for row in details))
                    self.assertTrue(any(call.args[1] == 208 for call in execute.call_args_list))
                    self.assertTrue(any(call.args[1] == 209 for call in execute.call_args_list))

    def test_arbitrary_saved_sql_change_is_rejected(self):
        job = fixture_job()
        connection = self.validation()
        payload = pb._merged(pb.PayrollJobInput(queryConfiguration=[]), job)
        with self.assertRaises(HTTPException) as rejected:
            pb._normalized(connection, payload, job)
        self.assertEqual(rejected.exception.status_code, 422)

    def test_omitted_payroll_fields_preserve_wage_group_and_schedule_configuration(self):
        job = fixture_job()
        job.wageMappings = [pb.WageMapping(clientId=204, wageColumn="earnings", payCode="REG")]
        job.grouping = ["retnum"]
        job.schedule.monthlyDate = "27"
        effective = pb._merged(pb.PayrollJobInput(general={"description": "Changed"}), job)
        self.assertEqual(effective.wageMappings, job.wageMappings)
        self.assertEqual(effective.grouping, job.grouping)
        self.assertEqual(effective.schedule.monthlyDate, "27")

    def test_wage_mapping_rejects_other_clients_codes(self):
        connection = self.validation()
        payload = create_payload()
        payload.wageMappings = [pb.WageMapping(clientId=204, wageColumn="earnings", payCode="FOREIGN")]
        with patch.object(pb, "_pay_codes", return_value=[{"pay_code": "REG"}]), self.assertRaises(HTTPException):
            pb._normalized(connection, payload)

    def test_mapping_catalog_label_whitespace_resolves_to_unchanged_source_key(self):
        connection = self.validation()
        for value in ("Client Id in Prism ", " client id in prism ", "RetNum"):
            with self.subTest(value=value):
                payload = create_payload()
                payload.mapping.rows[0].mappingColumn = value
                normalized = pb._normalized(connection, payload)
                self.assertEqual(normalized.mapping.rows[0].mappingColumn, "RetNum")
        connection.execute.assert_not_called()

    def test_configured_schedule_requires_start_but_explicit_manual_schedule_is_valid(self):
        connection = self.validation()
        payload = create_payload()
        self.assertIsNone(pb._normalized(connection, payload).schedule.startDate)
        for settings in ({"hour": "4"}, {"buildFrequency": "Weekly"}, {"minute": "15"}):
            with self.subTest(settings=settings):
                payload = create_payload()
                payload.schedule = pb.PayrollSchedule(**settings)
                with self.assertRaises(HTTPException) as rejected:
                    pb._normalized(connection, payload)
                self.assertEqual(rejected.exception.status_code, 422)
                self.assertIn("startDate", rejected.exception.detail[0]["loc"])

    def test_invalid_schedule_codes_and_month_dates_are_rejected_before_database_access(self):
        for settings in ({"scheduleType": "INVALID"}, {"monthlyDate": "99"}, {"monthlyDate": "-1"}, {"monthlyDate": "abc"}):
            with self.subTest(settings=settings), patch.object(pb.engine, "begin") as begin:
                response = self.client.put(self.base + "/jobs/987654", json={"schedule": settings})
                self.assertEqual(response.status_code, 422)
                begin.assert_not_called()
        for value in ("", "0", "01", "31"):
            self.assertEqual(pb.PayrollSchedule(monthlyDate=value).monthlyDate, value)

    def test_schedule_type_must_match_frequency_and_monthly_legacy_code_is_retained(self):
        connection = self.validation()
        payload = create_payload()
        payload.schedule = pb.PayrollSchedule(startDate=date(2026, 11, 24), buildFrequency="Weekly", scheduleType="D")
        with self.assertRaises(HTTPException):
            pb._normalized(connection, payload)
        payload.schedule = pb.PayrollSchedule(startDate=date(2026, 11, 24), buildFrequency="Monthly", scheduleType="MD", monthlyDate="27")
        self.assertEqual(pb._normalized(connection, payload).schedule.scheduleType, "MD")

    def test_existing_manual_job_keeps_schedule_on_unrelated_edit_and_can_be_made_manual(self):
        connection = self.validation()
        original = fixture_job()
        submitted = pb.PayrollJobInput(general={"description": "Changed"})
        self.assertIsNone(pb._normalized(connection, pb._merged(submitted, original), original, submitted=submitted).schedule.startDate)
        original.schedule.startDate = date(2026, 11, 24)
        submitted = pb.PayrollJobInput(schedule={"startDate": None})
        self.assertIsNone(pb._normalized(connection, pb._merged(submitted, original), original, submitted=submitted).schedule.startDate)

    def test_edit_cannot_clear_date_while_submitting_a_configured_schedule(self):
        self.validation()
        original = fixture_job()
        original.schedule.startDate = date(2026, 11, 24)
        with patch.object(pb.engine, "begin") as begin, patch.object(pb, "_read_job", return_value=original):
            response = self.client.put(self.base + "/jobs/987654", json={"schedule": {
                "startDate": None, "buildFrequency": "Weekly", "hour": "4", "minute": "00", "meridiem": "AM", "week": "Thursday",
            }})
            connection = begin.return_value.__enter__.return_value
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(connection.execute.call_args_list), 1)  # Lock SELECT only.

    def test_frequency_change_uses_new_schedule_code_and_preserves_hidden_monthly_settings(self):
        connection = self.validation()
        original = fixture_job()
        original.schedule = pb.PayrollSchedule(startDate=date(2026, 11, 24), buildFrequency="Monthly", scheduleType="MD", monthlyDate="27")
        submitted = pb.PayrollJobInput(schedule={"buildFrequency": "Weekly"})
        payload = pb._normalized(connection, pb._merged(submitted, original), original, submitted=submitted)
        pb._write_details(connection, original.id, payload, creating=False)
        schedule = next(call.args[1] for call in connection.execute.call_args_list if "payroll_schedule_info" in str(call.args[0]) and "INSERT" in str(call.args[0]))
        self.assertEqual(schedule["ScheduleType"], "W")
        self.assertEqual(schedule["MonthlyDate"], "27")
        self.assertFalse(any("payroll_query" in str(call.args[0]) for call in connection.execute.call_args_list))

    def test_condition_types_are_checked_against_catalog(self):
        connection = self.validation()
        for column, value, kind in (("earnings", "abc", "text"), ("earnings", "2026-11-24", "number"),
                                    ("earnings", "NaN", None), ("paydate", "100", "date"),
                                    ("paydate", "2026-02-30", None), ("firstname", "100", "number")):
            with self.subTest(column=column, value=value, kind=kind):
                payload = create_payload()
                payload.fileSettings = pb.shared.FileSettingsForm(conditionalStatements=[{
                    "mappingColumn": column, "condition": "=", "value": value, "valueType": kind,
                }])
                with self.assertRaises(HTTPException) as rejected:
                    pb._normalized(connection, payload)
                self.assertEqual(rejected.exception.status_code, 422)
        connection.execute.assert_not_called()

    def test_untyped_conditions_infer_date_number_and_text_without_losing_leading_zeros(self):
        connection = self.validation()
        payload = create_payload()
        payload.fileSettings = pb.shared.FileSettingsForm(conditionalStatements=[
            {"mappingColumn": "earnings", "condition": ">=", "value": "100.125"},
            {"mappingColumn": "Pay Date", "condition": "=", "value": "2026-11-24"},
            {"mappingColumn": "firstname", "condition": "=", "value": "000012"},
        ])
        rules = pb._normalized(connection, payload).fileSettings.conditionalStatements
        self.assertEqual([(row.valueType, row.value) for row in rules], [("number", "100.13"), ("date", "2026-11-24"), ("text", "000012")])

    def test_default_is_valid_for_constant_mapping_but_not_filters_or_sorting(self):
        connection = self.validation()
        for section in ("sortingOrder", "conditionalStatements"):
            with self.subTest(section=section):
                payload = create_payload()
                row = {"orderBy": "1", "mappingColumn": "Default"} if section == "sortingOrder" else {
                    "mappingColumn": "Default", "condition": "=", "value": "x", "valueType": "text"}
                payload.fileSettings = pb.shared.FileSettingsForm(**{section: [row]})
                with self.assertRaises(HTTPException):
                    pb._normalized(connection, payload)
        payload = create_payload()
        payload.mapping.rows[0].mappingColumn = "Default"
        payload.mapping.rows[0].defaultValue = "constant"
        self.assertEqual(pb._normalized(connection, payload).mapping.rows[0].defaultValue, "constant")

    def test_multiple_datasets_store_results_are_rejected_before_procedure_or_history(self):
        job = fixture_job()
        job.general.storeResultsToTable = True
        job.mapping.rows.append(pb.shared.MappingRow(field="OT", mappingColumn="OTW", recordType="D", dataSetNo=2, colSeqNo=1))
        job.queryConfiguration.append(pb.shared.QueryConfigurationRow(recttype="D", query="SELECT valid_flag,retnum,paydate AS sort1,OTW AS [OT]"))
        with patch.object(pb.engine, "begin"), patch.object(pb, "_read_job", return_value=job), \
             patch.object(pb, "_load_source") as source, patch.object(pb, "_record_status") as history:
            with self.assertRaises(HTTPException) as rejected:
                pb._run_job(job.id, ReportDateRange(date(2026, 11, 1), date(2026, 11, 24)))
        self.assertEqual(rejected.exception.status_code, 422)
        source.assert_not_called()
        history.assert_not_called()
        self.assertNotIn(job.id, pb._running)

    def test_failed_run_rolls_back_attempt_then_commits_failure_status_before_returning_error(self):
        events = []
        transaction = MagicMock()
        connection = transaction.__enter__.return_value
        transaction.__exit__.side_effect = lambda *args: events.append("outer commit" if args[0] is None else "outer rollback") or False
        connection.begin_nested.return_value.__exit__.side_effect = lambda *args: events.append("attempt rollback" if args[0] else "attempt commit") or False
        with patch.object(pb.engine, "begin", return_value=transaction), patch.object(pb, "_read_job", return_value=fixture_job()), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(pb, "_load_source", side_effect=pb.SQLAlchemyError("synthetic private driver detail")), \
             patch.object(pb, "_record_status", side_effect=lambda c, jid, status, message: events.append(status)) as history:
            with self.assertRaises(HTTPException) as rejected:
                pb._run_job(987654, ReportDateRange(date(2026, 11, 1), date(2026, 11, 24)))
        self.assertEqual(rejected.exception.status_code, 500)
        self.assertEqual(events, ["attempt rollback", "Failed", "outer commit"])
        self.assertNotIn("private", history.call_args.args[3])
        self.assertNotIn(987654, pb._running)

    def test_failure_status_uses_existing_history_update_and_insert_contracts(self):
        connection = MagicMock()
        result = MagicMock(rowcount=0)
        with patch.object(pb, "_execute", return_value=result) as execute:
            pb._record_status(connection, 987654, "Failed", "Fixture failure")
        execute.assert_called_once_with(connection, 218, {"JOB_ID": 987654, "STATUS": "Failed", "STAT_MSG": "Fixture failure"})
        connection.execute.assert_called_once_with(pb.INSERT_HISTORY, {"jobid": 987654, "status": "Failed", "message": "Fixture failure"})

    def test_failed_savepoint_commit_removes_only_new_output_and_records_failure(self):
        job = fixture_job()
        source = ProcedureSource((
            ProcedureResultSet(("valid_flag", "retnum", "sort1", "Wages"), (("1", "204", "2026-11-24", "Wages"),)),
            ProcedureResultSet(("valid_flag", "retnum", "sort1", "Wages"), (("1", "204", "2026-11-24", "123.45"),)),
            ProcedureResultSet(("valid_flag", "retnum", "sort1"), (("1", "204", "2026-11-24"),)),
        ))
        with TemporaryDirectory() as directory, patch.object(pb.engine, "begin") as begin, \
             patch.object(pb, "_read_job", return_value=job), patch.object(pb, "_load_source", return_value=source), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(pb, "get_settings", return_value=Settings(_env_file=None, report_output_dir=Path(directory))), \
             patch.object(pb, "_record_status") as history:
            protected = Path(directory) / "existing.csv"
            protected.write_text("preserve this fixture")
            connection = begin.return_value.__enter__.return_value
            connection.begin_nested.return_value.__exit__.side_effect = pb.SQLAlchemyError("synthetic savepoint failure")
            with self.assertRaises(HTTPException) as rejected:
                pb._run_job(job.id, ReportDateRange(date(2026, 11, 1), date(2026, 11, 24)))
            self.assertEqual(rejected.exception.status_code, 500)
            self.assertEqual(list(Path(directory).rglob("*.csv")), [protected])
            self.assertEqual(protected.read_text(), "preserve this fixture")
        self.assertEqual([call.args[2] for call in history.call_args_list], ["Success", "Failed"])

    def test_validation_failure_records_failed_status_and_truncates_message(self):
        with patch.object(pb.engine, "begin"), patch.object(pb, "_read_job", return_value=fixture_job()), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(pb, "_load_source", side_effect=pb.InvalidRun("x" * 300)), \
             patch.object(pb, "_record_status") as history:
            with self.assertRaises(HTTPException) as rejected:
                pb._run_job(987654, ReportDateRange(date(2026, 11, 1), date(2026, 11, 24)))
        self.assertEqual(rejected.exception.status_code, 422)
        self.assertEqual(history.call_args.args[2:], ("Failed", "x" * 255))

    def test_multiple_datasets_export_with_store_results_off_and_keep_identities(self):
        job = fixture_job()
        job.mapping.rows.append(pb.shared.MappingRow(field="Overtime", mappingColumn="OTW", recordType="D", dataSetNo=2, colSeqNo=1))
        job.queryConfiguration[1].query = tag_dataset_query(job.queryConfiguration[1].query, 1)
        job.queryConfiguration.insert(2, pb.shared.QueryConfigurationRow(recttype="D", query=tag_dataset_query("SELECT valid_flag,retnum,paydate AS sort1,OTW AS [Overtime]", 2)))
        control = ("valid_flag", "retnum", "sort1")
        source = ProcedureSource((
            ProcedureResultSet(control + ("Wages",), (("1", "204", "2026-11-24", "Wages"),)),
            ProcedureResultSet(control + ("__ecs_dataset_2", "Overtime"), (("1", "204", "2026-11-24", "2", "12.34"),)),
            ProcedureResultSet(control + ("__ecs_dataset_1", "Wages"), (("1", "204", "2026-11-24", "1", "123.45"),)),
            ProcedureResultSet(control, (("1", "204", "2026-11-24"),)),
        ))
        with TemporaryDirectory() as directory, patch.object(pb.engine, "begin"), \
             patch.object(pb, "_read_job", return_value=job), patch.object(pb, "_load_source", return_value=source), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(pb, "get_settings", return_value=Settings(_env_file=None, report_output_dir=Path(directory), mail_enabled=False)), \
             patch.object(pb, "_record_status"):
            run = pb._run_job(job.id, ReportDateRange(date(2026, 11, 1), date(2026, 11, 24)))
        self.assertEqual(run.rowCount, 2)
        self.assertEqual(run.csv, "Wages\r\n123.45\r\n\r\nOvertime\r\n12.34\r\n")
        self.assertNotIn("__ecs_dataset_", run.csv)

    def test_run_requires_dates_and_rejects_uploads_without_touching_database(self):
        self.assertEqual(self.client.post(self.base + "/jobs/987654/run").status_code, 422)
        self.assertEqual(self.client.post(self.base + "/jobs/987654/run?start_date=2026-11-10&end_date=2026-11-01").status_code, 422)
        result = self.client.post(self.base + "/jobs/987654/run?start_date=2026-11-01&end_date=2026-11-10", content=b"data")
        self.assertEqual(result.status_code, 415)

    def test_disabled_job_cannot_invoke_procedure(self):
        job = fixture_job()
        job.general.enable = False
        with patch.object(pb.engine, "begin"), patch.object(pb, "_read_job", return_value=job), patch.object(pb, "_load_source") as source:
            with self.assertRaises(HTTPException) as rejected:
                pb._run_job(job.id, ReportDateRange(date(2026, 11, 1), date(2026, 11, 2)))
        self.assertEqual(rejected.exception.status_code, 409)
        source.assert_not_called()
        self.assertNotIn(job.id, pb._running)

    def test_mocked_run_uses_separate_output_directory_and_never_sends_mail(self):
        job = fixture_job()
        source = ProcedureSource((
            ProcedureResultSet(("valid_flag", "retnum", "sort1", "Wages"), (("1", "204", "2026-11-02", "Wages"),)),
            ProcedureResultSet(("valid_flag", "retnum", "sort1", "Wages"), (("1", "204", "2026-11-02", "123.45"),)),
            ProcedureResultSet(("valid_flag", "retnum", "sort1"), (("1", "204", "2026-11-02"),)),
        ))
        with TemporaryDirectory() as directory, patch.object(pb.engine, "begin"), \
             patch.object(pb, "_read_job", return_value=job), patch.object(pb, "_load_source", return_value=source), \
             patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(pb, "get_settings", return_value=Settings(report_output_dir=Path(directory), mail_enabled=False)), \
             patch("smtplib.SMTP", side_effect=AssertionError("SMTP prohibited")), \
             patch("smtplib.SMTP_SSL", side_effect=AssertionError("SMTP prohibited")):
            run = pb._run_job(job.id, ReportDateRange(date(2026, 11, 1), date(2026, 11, 2)))
            paths = list(Path(directory).rglob("*.csv"))
            self.assertEqual(len(paths), 1)
            self.assertIn("payroll/manual/987654/", paths[0].as_posix())
            self.assertIn("123.45", paths[0].read_text())
        self.assertEqual(run.rowCount, 1)
        self.assertFalse(run.emailDelivery.enabled)


class PayrollSourceTests(TestCase):
    def test_procedure_call_has_job_dates_manual_flag_and_drains_trailing_results(self):
        class Cursor:
            index = 0
            closed = False
            sets = [(("valid_flag", "retnum", "sort1", "Wages"), [(1, "204", date(2026, 11, 2), Decimal("1.25"))]), (None, [])]
            @property
            def description(self):
                names = self.sets[self.index][0]
                return [(name,) for name in names] if names else None
            def execute(self, *args):
                self.args = args
            def __iter__(self):
                return iter(self.sets[self.index][1])
            def nextset(self):
                self.index += 1
                return self.index < len(self.sets)
            def close(self):
                self.closed = True
        cursor = Cursor()
        connection = MagicMock()
        connection.connection.cursor.return_value = cursor
        dates = ReportDateRange(date(2026, 11, 1), date(2026, 11, 2))
        with patch.object(pb, "get_settings", return_value=Settings(_env_file=None, payroll_report_procedure="dbo.payrolljobbuilder")):
            result = pb._load_source(connection, fixture_job(), dates)
        self.assertEqual(cursor.args[1:], (987654, dates.start, dates.end, "A"))
        self.assertIn("[dbo].[payrolljobbuilder]", cursor.args[0])
        self.assertEqual(cursor.index, 2)
        self.assertTrue(cursor.closed)
        self.assertEqual(result.result_sets[0].rows[0][-1], "1.25")

    def test_legacy_null_sequences_use_saved_projection_evidence(self):
        data = {
            "READ_JOB": [{"jobid": 987654, "jobfilename": "Fixture", "filetype": "CSV", "isEnabled": False, "FileNameFormat": "File Name"}],
            "READ_SCHEDULE": [{"ScheduleType": "W", "ScheduleWeek": "4", "schedule_hr": 4, "schedule_min": 0}],
            "READ_MAPPINGS": [
                {"jobclientcolumn": "First", "jobfieldmapping": "firstname", "jobrectype": "D", "ColSeqNo": None},
                {"jobclientcolumn": "Wages", "jobfieldmapping": "earnings", "jobrectype": "D", "ColSeqNo": None}],
            "READ_QUERY_CONFIGURATION": [{"recttype": "D", "Query": "SELECT valid_flag,retnum,paydate AS sort1,earnings AS [Wages],firstname AS [First]"}],
        }
        def rows(connection, statement, params=None):
            name = next((key for key, query in pb.READS.items() if str(query) == str(statement)), None)
            return data.get(name, [])
        with patch.object(pb, "_rows", side_effect=rows), patch.object(pb.shared, "_file_formats", return_value={"CSV": ","}):
            job = pb._read_job(MagicMock(), 987654)
        order = sorted(job.mapping.rows, key=lambda row: row.colSeqNo)
        self.assertEqual([row.mappingColumn for row in order], ["earnings", "firstname"])
        self.assertEqual([row.colSeqNo for row in order], [1, 2])

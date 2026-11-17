from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings
from app.payroll_source import (
    PAYROLL_QUERY_TYPE, load_payroll_source, payroll_job_with_saved_rules, payroll_record_queries, payroll_report_query,
)
from app.retirement_results import InvalidRun, build_report_files
from app.report_mail import ReportEmailDelivery
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
        connection = Mock()
        connection.execute.return_value.mappings.return_value = rows
        self.assertEqual(rb._mapping_catalog(connection), {
            "company_name": ("Company Name", "text"),
            "payroll_month": ("Pay Date", "date"),
            "hours_worked": ("Hours Worked", "number"),
        })

    def test_mapping_writes_catalog_keys_and_record_type_codes(self):
        payload = input_job(mapping={"rows": [
            {"field": "Header Company", "mappingColumn": "Company Name", "recordType": "Header"},
            {"field": "Pay Date"},
            {"field": "Footer Company", "mappingColumn": "COMPANY_NAME", "recordType": " t "},
            {"field": "CSV Column With Spaces", "recordType": "Detail"},
        ]})
        connection = Mock()
        connection.execute.return_value.mappings.return_value = [
            {"mapping_column": "company_name", "mapping_column_desc": "Company Name", "mapping_column_dt": "text"},
            {"mapping_column": "payroll_month", "mapping_column_desc": "Pay Date", "mapping_column_dt": "date"},
        ]
        rb._write_job_details(connection, 31, payload)
        mappings = [
            (call.args[1]["jobrectype"], call.args[1]["jobfieldmapping"])
            for call in connection.execute.call_args_list
            if len(call.args) == 2 and "jobfieldmapping" in call.args[1]
        ]
        self.assertEqual(mappings, [
            ("H", "company_name"), ("D", "payroll_month"), ("T", "company_name"), ("D", "CSV Column With Spaces"),
        ])


class FileFormatTests(TestCase):
    def test_output_file_name_options_return_database_labels_and_codes_in_format_order(self):
        connection = Mock()
        connection.execute.return_value.mappings.return_value = [
            {"jobformat": "File Name + Client ID + Payday", "jobformattype": "FILENAME_CLIENT_PAYDAY"},
            {"jobformat": "By date", "jobformattype": "PAYDAY"},
            {"jobformat": "File Name + Payday", "jobformattype": "filename_payday"},
            {"jobformat": "Client ID", "jobformattype": "CLIENT"},
            {"jobformat": "Client ID + Payday", "jobformattype": "CLIENT_PAYDAY"},
            {"jobformat": "File Name + Client ID", "jobformattype": " FILENAME_CLIENT "},
            {"jobformat": "Use the job name", "jobformattype": "FILENAME"},
            {"jobformat": "Client ID", "jobformattype": "all"},
            {"jobformat": "File Name", "jobformattype": "output_file_name"},
            {"jobformat": "MM/DD/YYYY", "jobformattype": "DATE"},
        ]
        self.assertEqual([option.model_dump() for option in rb._output_file_name_formats(connection)], [
            {"label": "Use the job name", "value": "FILENAME"},
            {"label": "Client ID", "value": "CLIENT"},
            {"label": "By date", "value": "PAYDAY"},
            {"label": "File Name + Client ID", "value": "FILENAME_CLIENT"},
            {"label": "File Name + Payday", "value": "FILENAME_PAYDAY"},
            {"label": "Client ID + Payday", "value": "CLIENT_PAYDAY"},
            {"label": "File Name + Client ID + Payday", "value": "FILENAME_CLIENT_PAYDAY"},
        ])

    def test_database_delimiters_preserve_whitespace_and_resolve_legacy_jobs(self):
        connection = Mock()
        connection.execute.return_value.mappings.return_value = [
            {"filetyp": "Comma", "delimiter": ","},
            {"filetyp": "Pipe", "delimiter": "|"},
            {"filetyp": "Semicolon", "delimiter": ";"},
            {"filetyp": "Space", "delimiter": " "},
            {"filetyp": "Tab", "delimiter": "\t"},
            {"filetyp": "Unconfigured", "delimiter": None},
        ]
        formats = rb._file_formats(connection)
        self.assertEqual(rb._file_format_delimiter(formats, "CSV"), ",")
        self.assertEqual(rb._file_format_delimiter(formats, "CSV_TAB"), "\t")
        for label, delimiter in (("Comma", ","), ("Pipe", "|"), ("Semicolon", ";"), ("Space", " "), ("Tab", "\t")):
            with self.subTest(label=label):
                self.assertEqual(rb._file_format_delimiter(formats, label), delimiter)
                self.assertEqual(rb._file_format_delimiter(formats, delimiter), delimiter)
                job = rb._api_job_from_row({"jobid": 60, "filetype": delimiter}, formats)
                self.assertEqual(job["general"]["fileFormat"], label)
        self.assertIsNone(rb._file_format_delimiter(formats, "Unconfigured"))


class SortingStorageTests(TestCase):
    def test_csv_sorting_saves_positive_priorities_and_restores_directions_for_generation(self):
        columns = ("Net Salary", "Group", "Last, First]")
        payload = input_job(fileSettings={"sortingOrder": [
            {"orderBy": "5", "mappingColumn": columns[2], "direction": "DESC"},
            {"orderBy": "1", "mappingColumn": columns[0], "direction": "DESC"},
            {"orderBy": "3", "mappingColumn": columns[1], "direction": "ASC"},
        ]})
        connection = Mock()
        rb._write_job_details(connection, 33, payload)

        sorting_rows = [
            {"sort_order": values["order"], "mapping_column": values["mapping"]}
            for statement, values in (call.args for call in connection.execute.call_args_list)
            if str(statement).startswith("INSERT INTO [dbo].[rjob_file_sorting_details]")
        ]
        self.assertEqual([(row["sort_order"], row["mapping_column"]) for row in sorting_rows], list(enumerate(columns, 1)))
        saved_query, = [
            values for statement, values in (call.args for call in connection.execute.call_args_list)
            if str(statement).startswith("INSERT INTO [dbo].[rjob_query]")
        ]
        self.assertEqual(saved_query, {
            "jobid": 33, "recttype": "CSV_SORT", "Query": "", "conditionalStmt": "",
            "sortOrder": "ORDER BY [Net Salary] DESC, [Group] ASC, [Last, First]]] DESC",
        })

        def read(statement, _parameters):
            result = Mock()
            result.mappings.return_value.first.return_value = {
                "jobid": 33, "jobfilename": "Sort Test", "filetype": "Comma", "jobdesc": "", "isEnabled": True,
                "StoreResults": False, "includeHeader": True, "ismerge": False, "rbJobTypeChk": "Daily",
                "schedules_session": "AM", "ScheduleWeek": "1",
            }
            result.mappings.return_value.all.return_value = {
                rb.READ_MAPPINGS: [dict.fromkeys(("jobfieldmapping", "jobdefaultvalue", "jobformat"), "") |
                                   {"jobclientcolumn": column, "jobrectype": "Detail"} for column in columns],
                rb.READ_SORTING: sorting_rows,
                rb.READ_QUERY_CONFIGURATION: [{
                    "recttype": saved_query["recttype"], "Query": "", "Conditions": "",
                    "Sort_Order": saved_query["sortOrder"],
                }],
            }.get(statement, [])
            return result

        connection.execute.side_effect = read
        job = rb._read_full_job(connection, 33)
        self.assertEqual([row.direction for row in job.fileSettings.sortingOrder], ["DESC", "ASC", "DESC"])
        report, = build_report_files(job, b'Net Salary,Group,"Last, First]"\n100,B,Name1\n100,A,Name1\n200,B,Name1\n100,A,Name2\n')
        self.assertEqual(report.csv.splitlines()[1:], ["200,B,Name1", "100,A,Name2", "100,A,Name1", "100,B,Name1"])


class PayrollQueryTests(TestCase):
    def test_pay_date_condition_survives_storage_and_filters_at_the_calendar_boundary(self):
        payload = input_job(
            general={"fileName": "Payroll", "fileFormat": "Comma", "reportSource": "companyPayroll"},
            mapping={"rows": [{"field": "Pay Date"}]},
            fileSettings={"conditionalStatements": [
                {"mappingColumn": "Pay Date", "condition": ">=", "value": "2026-11-01"},
            ]},
        )
        rb._validate_payload(payload, creating=True)
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        connection.execute.return_value.tuples.return_value.all.return_value = [
            (kind, f"/* company payroll */ SELECT '{kind}'") for kind in ("H", "D", "T")
        ]
        rb._write_job_details(connection, 31, payload)
        condition = next(
            call.args[1] for call in connection.execute.call_args_list
            if len(call.args) == 2 and "Symbol" in call.args[1]
        )
        self.assertEqual((condition["Symbol"], condition["val"]), ("date:>=", "20261101"))
        decoded = rb._condition_from_db({
            "mapping_column": "Pay Date", "condition_symbol": condition["Symbol"],
            "condition_value": Decimal(condition["val"]),
        })
        self.assertEqual(decoded, payload.fileSettings.conditionalStatements[0].model_dump())
        queries = payroll_record_queries(connection, payload)
        self.assertEqual(queries[1]["conditions"], "[Pay Date] >= '2026-11-01'")
        job = rb.RetirementBuilderJob.model_validate({
            "id": 31, **payload.model_dump(), "fileSettings": {}, "queryConfiguration": queries,
        })
        report, = build_report_files(
            payroll_job_with_saved_rules(job),
            b"Pay Date\n2026-10-31\n11/1/2026\n2026-11-02\n",
        )
        self.assertEqual(report.csv.splitlines(), ["Pay Date", "11/1/2026", "2026-11-02"])
        with self.assertRaises(HTTPException):
            rb._condition_value("2026-02-30", ["value"])

    def test_payroll_uses_saved_record_queries_and_rules_for_the_job(self):
        payload = input_job(
            general={"fileName": "Payroll", "fileFormat": "CSV", "reportSource": "companyPayroll"},
            mapping={"rows": [{"field": "Employee Count"}]},
            fileSettings={
                "conditionalStatements": [{"mappingColumn": "Employee Count", "condition": ">=", "value": "2.00"}],
                "sortingOrder": [{"orderBy": "1", "mappingColumn": "Employee Count", "direction": "DESC"}],
            },
        )
        connection = Mock()
        connection.execute.return_value.tuples.return_value.all.return_value = [
            (kind, f"/* company payroll */ SELECT '{kind}'") for kind in ("H", "D", "T")
        ]
        settings = Settings(_env_file=None, payroll_report_procedure="reports.usp_RenamedPayroll")
        with patch("app.payroll_source.get_settings", return_value=settings):
            rows = payroll_record_queries(connection, payload)
        self.assertEqual(str(connection.execute.call_args.args[0]), "EXEC [reports].[usp_RenamedPayroll] @templates_only = 1")
        self.assertEqual([row["recttype"] for row in rows], ["H", "D", "T"])
        self.assertEqual(rows[1]["conditions"], "[Employee Count] >= 2.00")
        self.assertEqual(rows[1]["sortOrder"], "ORDER BY [Employee Count] DESC")

        job = rb.RetirementBuilderJob.model_validate({
            "id": 31, **payload.model_dump(), "fileSettings": {}, "queryConfiguration": rows,
        })
        run_job = payroll_job_with_saved_rules(job)
        cursor = MagicMock()
        connection.connection.cursor.return_value = cursor
        cursor.description = [("Record Type",), ("Employee Count",)]
        cursor.__iter__.return_value = [("D", 1), ("D", 2), ("D", 4)]
        with patch("app.payroll_source.get_settings", return_value=settings):
            source = load_payroll_source(connection, run_job)
        statement, job_id = cursor.execute.call_args.args
        self.assertIn("EXEC [reports].[usp_RenamedPayroll] @jobid = ?", statement)
        self.assertEqual(job_id, 31)
        report, = build_report_files(run_job, source, from_payroll_procedure=True)
        self.assertEqual(report.csv.splitlines(), ["Employee Count", "4", "2"])

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


class SubscriptionStorageTests(TestCase):
    def test_company_subscriptions_read_legacy_and_current_ids(self):
        for saved_id in (-2, 1):
            with self.subTest(saved_id=saved_id):
                self.assertEqual(
                    rb._subscription_from_db(saved_id, "qa@example.invalid", uses_payroll=True),
                    rb.SubscriptionRow(companyId=1, email="qa@example.invalid"),
                )
        self.assertEqual(rb._subscription_from_db(1, None, uses_payroll=False), rb.SubscriptionRow(client="1"))

    def test_subscriptions_store_the_positive_id_for_each_report_source(self):
        for source, row in (("companyPayroll", {"companyId": 1}), ("csv", {"client": "0001"})):
            with (
                self.subTest(source=source),
                patch.object(rb, "payroll_company_ids", return_value={"QA Company": 1}),
                patch.object(rb, "payroll_record_queries", return_value=[]),
            ):
                connection = Mock()
                payload = input_job(general={"reportSource": source}, subscriptions={"rows": [row]})
                rb._write_job_details(connection, 31, payload)
                ids = [call.args[1]["jobclientid"] for call in connection.execute.call_args_list
                       if len(call.args) == 2 and "jobclientid" in call.args[1]]
                self.assertEqual(ids, [1])

    def test_subscriptions_reject_zero_ids(self):
        for source, row in (("companyPayroll", {"companyId": 0}), ("csv", {"client": "0"})):
            with self.subTest(source=source), patch.object(rb, "payroll_company_ids", return_value={"QA Company": 0}):
                payload = input_job(general={"reportSource": source}, subscriptions={"rows": [row]})
                with self.assertRaises(HTTPException) as error:
                    rb._write_job_details(Mock(), 31, payload)
                self.assertEqual(error.exception.status_code, 422)


class ManualRunMailTests(TestCase):
    def test_saved_source_run_emails_after_commit_and_csv_override_skips_delivery(self):
        settings = Settings(_env_file=None)
        job = rb.RetirementBuilderJob.model_validate({
            "id": 31, "general": {"fileFormat": "Comma"}, "mapping": {"rows": [{"field": "Name"}]},
        })
        report, = build_report_files(job, b"Client ID,Name\n1,Example\n")
        run = rb.RetirementBuilderRun(
            runId="00000000-0000-0000-0000-000000000001", rowCount=1, storedRows=0,
            fileName=report.file_name, csv=report.csv, delimiter=",", files=[],
        )
        with (
            patch.object(rb, "get_settings", return_value=settings),
            patch.object(rb.engine, "begin") as begin,
            patch.object(rb, "_read_full_job", return_value=job),
            patch.object(rb, "_attempt_report_run", side_effect=lambda *_, **__: (run.model_copy(), [report])),
            patch.object(rb, "send_subscribed_reports") as send,
        ):
            transaction = begin.return_value
            transaction.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = job.id

            def deliver(*args):
                transaction.__exit__.assert_called_once_with(None, None, None)
                return ReportEmailDelivery(enabled=True, matched=1, accepted=1)

            send.side_effect = deliver
            result = rb._run_job(job.id, None)
            self.assertEqual(result.emailDelivery, ReportEmailDelivery(enabled=True, matched=1, accepted=1))
            send.assert_called_once_with(settings, job, [report])

            send.reset_mock()
            result = rb._run_job(job.id, b"Name\nOther input\n")
            self.assertIsNone(result.emailDelivery)
            send.assert_not_called()


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

    def test_job_list_hides_schedule_defaults_when_the_job_has_no_start_date(self):
        saved_defaults = {"runday": "Thursday", "runtime": "4:00 AM", "ScheduleType": "Weekly", "Job_Last_Status": "Success"}
        rows = [{"jobid": 62, **saved_defaults}, {"jobid": 63, **saved_defaults}]
        with (
            patch.object(rb.engine, "connect") as connect,
            patch.object(rb, "_job_rows", return_value=rows),
            patch.object(rb, "_file_formats", return_value={}),
        ):
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.scalars.return_value = [63]
            manual, scheduled = rb.list_retirement_builder_jobs()
            connection.execute.assert_called_once_with(rb.READ_ENABLED_SCHEDULES)
        self.assertEqual(manual["schedule"], {
            "startDate": None, "week": "", "hour": "", "minute": "", "meridiem": "", "buildFrequency": "",
        })
        self.assertEqual(manual["runtime"], "")
        self.assertEqual(manual["Job_Last_Status"], "Success")
        self.assertEqual(scheduled["schedule"]["buildFrequency"], "Weekly")
        self.assertEqual(scheduled["runtime"], "4:00 AM")

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

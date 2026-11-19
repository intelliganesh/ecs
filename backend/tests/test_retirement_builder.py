from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from threading import Event
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app import payroll_source
from app.payroll_source import (
    PAYROLL_QUERY_TYPE, load_payroll_source, payroll_job_with_saved_rules, payroll_record_queries, payroll_report_query,
)
from app.retirement_results import InvalidRun, ReportDateRange, build_report_files
from app.report_mail import ReportEmailDelivery
from app.routers import retirement_builder as rb


def input_job(**sections):
    return rb.RetirementBuilderJobInput.model_validate(sections)


class ClientOptionsTests(TestCase):
    def test_client_catalog_reads_query_43_and_keeps_labels_and_numeric_ids(self):
        with patch.object(rb.engine, "connect") as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.mappings.return_value.all.return_value = [
                {"id": Decimal(719), "client_name": "000719 - Test Client"},
                {"id": Decimal(720), "client_name": None},
                {"id": Decimal(0), "client_name": "Invalid client"},
            ]
            options = rb.list_retirement_builder_clients()

        self.assertEqual(str(connection.execute.call_args.args[0]), rb._load_query("43"))
        self.assertEqual([option.model_dump() for option in options], [
            {"id": 719, "label": "000719 - Test Client"},
            {"id": 720, "label": "720"},
        ])


class MappingColumnOptionsTests(TestCase):
    def test_mapping_format_options_use_lookup_codes_and_descriptions(self):
        rows = [
            {"jobformat": "RA", "jobformattype": "char", "jobdesc": "RA - Right Justified"},
            {"jobformat": "XXX-XX-XXXX", "jobformattype": "char", "jobdesc": "XXX-XX-XXXX - SSN"},
            {"jobformat": "MMDDYYYY", "jobformattype": "date", "jobdesc": "MMDDYYYY - Date"},
            {"jobformat": "######.##", "jobformattype": "numeric", "jobdesc": None},
            {"jobformat": "File Name", "jobformattype": "FILENAME", "jobdesc": "File Name - One file"},
        ]
        groups, labels = rb._mapping_format_options(rows)
        self.assertEqual(groups, {
            "text": ["RA"], "ssn": ["XXX-XX-XXXX"], "date": ["MMDDYYYY"], "number": ["######.##"],
        })
        self.assertEqual(labels, {
            "RA": "RA - Right Justified", "XXX-XX-XXXX": "XXX-XX-XXXX - SSN",
            "MMDDYYYY": "MMDDYYYY - Date", "######.##": "######.##",
        })

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
    def test_legacy_tab_lookup_space_exports_real_tabs_and_keeps_fixed_separate(self):
        formats = rb._file_formats_from_rows([
            {"filetyp": "CSV", "delimiter": ","},
            {"filetyp": "TAB", "delimiter": " "},
            {"filetyp": "FIXED", "delimiter": " "},
            {"filetyp": "Space", "delimiter": " "},
        ])
        report_job = rb.RetirementBuilderJob.model_validate({
            "id": 60, "general": {"fileName": "Test", "fileFormat": "TAB"},
            "mapping": {"rows": [{"field": "Name"}, {"field": "Value"}]},
        })
        report, = build_report_files(report_job, b'Name,Value\n"First, Last",123\n',
                                    delimiter=rb._file_format_delimiter(formats, "TAB"))
        self.assertEqual(report.csv, 'Name\tValue\r\nFirst, Last\t123\r\n')
        self.assertEqual(rb._file_format_delimiter(formats, "TAB"), "\t")
        self.assertEqual(rb._file_format_delimiter(formats, "FIXED"), " ")
        self.assertEqual(rb._file_format_delimiter(formats, "Space"), " ")
        self.assertEqual(rb._file_format_delimiter(formats, "CSV"), ",")

    def test_fixed_space_reopens_as_fixed_independently_of_lookup_order(self):
        for names in (("TAB", "Space", "FIXED"), ("FIXED", "TAB", "Space")):
            with self.subTest(names=names):
                formats = rb._file_formats_from_rows([{"filetyp": name, "delimiter": " "} for name in names])
                stored = rb._file_format_delimiter(formats, "fixed")
                self.assertEqual(stored, " ")
                reopened = rb._job_from_rows(
                    {"jobid": 60, "jobfilename": "Test", "jobdesc": "", "filetype": stored,
                     "isEnabled": True, "StoreResults": False, "includeHeader": True, "ismerge": False},
                    {"rbJobTypeChk": "Weekly", "schedules_session": "AM", "ScheduleWeek": "4"},
                    [], [], [], [], [], formats,
                )
                self.assertEqual(reopened.general.fileFormat, "FIXED")
                self.assertEqual(rb._file_format_label(formats, "\t"), "TAB")
                self.assertEqual(rb._file_format_label(formats, "FIXED"), "FIXED")

    def test_output_file_name_options_use_xml_when_database_is_unavailable(self):
        with patch.object(rb.engine, "connect", side_effect=SQLAlchemyError):
            options = rb.get_retirement_builder_options()
        self.assertEqual([option.model_dump() for option in options.outputFileNameFormats], [
            {"label": "File Name", "value": "FILENAME"},
            {"label": "Client ID", "value": "CLIENT"},
            {"label": "Payday", "value": "PAYDAY"},
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

    def test_configured_file_types_round_trip_with_legacy_values(self):
        formats = {"CSV": ",", "PIPE": "|", "TAB": "\t", "SEMICOLON": ";"}
        for current, legacy, delimiter in (
            ("CSV", "Comma", ","),
            ("PIPE", "CSV (Pipe Delimited)", "|"),
            ("TAB", "CSV_TAB", "\t"),
            ("SEMICOLON", "CSV_SEMI", ";"),
        ):
            with self.subTest(current=current):
                self.assertEqual(rb._file_format_delimiter(formats, current), delimiter)
                self.assertEqual(rb._file_format_delimiter(formats, legacy), delimiter)
                self.assertEqual(rb._file_format_label(formats, delimiter), current)
                self.assertEqual(rb._file_format_label(formats, legacy), current)
        self.assertEqual(rb._file_format_delimiter({"Comma": ";", "CSV": ","}, "CSV"), ",")


class SortingStorageTests(TestCase):
    def test_priority_only_csv_and_payroll_payloads_save_sequential_priorities(self):
        for source in ("csv", "companyPayroll"):
            with self.subTest(source=source):
                payload = input_job(
                    general={"fileName": "Priority test", "fileFormat": "CSV", "reportSource": source},
                    mapping={"rows": [{"field": "Company Name", "recordType": "D"}]},
                    fileSettings={"sortingOrder": [
                        {"orderBy": "3", "mappingColumn": "Employee Count"},
                        {"orderBy": "1", "mappingColumn": "Company Name"},
                    ]},
                )
                rb._validate_payload(payload, creating=True)
                connection = Mock()
                connection.execute.return_value.mappings.return_value = [
                    {"mapping_column": "company_name", "mapping_column_desc": "Company Name", "mapping_column_dt": "text"},
                    {"mapping_column": "employee_count", "mapping_column_desc": "Employee Count", "mapping_column_dt": "number"},
                ]
                rb._write_job_details(connection, 30, payload)
                values = [call.args[1] for call in connection.execute.call_args_list if len(call.args) == 2]
                self.assertEqual([(row["order"], row["mapping"]) for row in values if "order" in row],
                                 [(1, "company_name"), (2, "employee_count")])
                queries = [row for row in values if "recttype" in row]
                self.assertTrue(all(row["recttype"] in {"H", "D", "T"} for row in queries))
                detail, = [row for row in queries if row["recttype"] == "D"]
                self.assertEqual(detail["sortOrder"], (", " if source == "csv" else "") + "company_name, employee_count")

    def test_csv_sorting_saves_column_list_and_restores_priorities_for_generation(self):
        columns = ("Net Salary", "Group", "Last, First]")
        payload = input_job(fileSettings={"sortingOrder": [
            {"orderBy": "5", "mappingColumn": columns[2], "direction": "DESC"},
            {"orderBy": "1", "mappingColumn": columns[0], "direction": "DESC"},
            {"orderBy": "3", "mappingColumn": columns[1], "direction": "ASC"},
        ]})
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 33, payload)

        sorting_rows = [
            {"sort_order": values["order"], "mapping_column": values["mapping"]}
            for statement, values in (call.args for call in connection.execute.call_args_list if len(call.args) == 2)
            if str(statement).startswith("INSERT INTO [dbo].[rjob_file_sorting_details]")
        ]
        self.assertEqual([(row["sort_order"], row["mapping_column"]) for row in sorting_rows], list(enumerate(columns, 1)))
        saved_query, = [
            values for statement, values in (call.args for call in connection.execute.call_args_list if len(call.args) == 2)
            if str(statement).startswith("INSERT INTO [dbo].[rjob_query]")
        ]
        self.assertEqual(saved_query, {
            "jobid": 33, "recttype": "D", "Query": "", "conditionalStmt": "",
            "sortOrder": 'Net Salary, Group, "Last, First]"',
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
        self.assertEqual([row.direction for row in job.fileSettings.sortingOrder], ["ASC", "ASC", "ASC"])
        report, = build_report_files(job, b'Net Salary,Group,"Last, First]"\n100,B,Name1\n100,A,Name1\n200,B,Name1\n100,A,Name2\n')
        self.assertEqual(report.csv.splitlines()[1:], ["100,A,Name1", "100,A,Name2", "100,B,Name1", "200,B,Name1"])


class RecordTypeStorageTests(TestCase):
    def test_csv_save_normalizes_all_record_types_and_merges_sorting_into_detail(self):
        payload = input_job(
            mapping={"rows": [
                {"field": "Company", "recordType": "Header"},
                {"field": "Amount", "recordType": " d "},
                {"field": "Total", "recordType": "Trailer"},
            ]},
            queryConfiguration=[
                {"recttype": "Header", "query": "header query"},
                {"recttype": " detail ", "query": "detail query", "conditions": "saved condition"},
                {"recttype": "t", "query": "trailer query"},
                {"recttype": "CSV_SORT", "sortOrder": "ORDER BY [Old] ASC"},
            ],
            fileSettings={"sortingOrder": [{"orderBy": "1", "mappingColumn": "Amount", "direction": "DESC"}]},
        )
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 31, payload)
        written = [call.args[1] for call in connection.execute.call_args_list if len(call.args) == 2]
        queries = [values for values in written if "recttype" in values]
        self.assertEqual([row["recttype"] for row in queries], ["H", "D", "T"])
        self.assertEqual([row["Query"] for row in queries], [
            "SELECT TOP 1 valid_flag, retnum, paydate AS sort1, 'Amount'",
            "detail query",
            "SELECT DISTINCT valid_flag, retnum, paydate AS sort1, [Total]",
        ])
        self.assertEqual(queries[1]["conditionalStmt"], "saved condition")
        self.assertEqual(queries[1]["sortOrder"], ", Amount")
        self.assertEqual([row["jobrectype"] for row in written if "jobrectype" in row], ["H", "D", "T"])

    def test_existing_csv_sorting_is_read_and_resaved_as_detail_without_becoming_payroll(self):
        for kind in ("CSV_SORT", "D"):
            with self.subTest(kind=kind):
                original = rb._job_from_rows(
                    {"jobid": 31, "jobfilename": "CSV report", "filetype": "CSV", "jobdesc": "",
                     "isEnabled": True, "StoreResults": False, "includeHeader": True, "ismerge": False},
                    {"rbJobTypeChk": "Daily", "schedules_session": "AM", "ScheduleWeek": "1"}, [], [], [], [],
                    [{"recttype": kind, "Query": "", "Conditions": "", "Sort_Order": "ORDER BY [Amount] DESC"}], {},
                )
                self.assertEqual(original.general.reportSource, "csv")
                self.assertEqual(original.fileSettings.sortingOrder[0].direction, "DESC")
                payload = rb._complete_update_payload(input_job(general={"description": "Updated"}), original)
                connection = Mock()
                connection.execute.return_value.mappings.return_value = []
                rb._write_job_details(connection, 31, payload)
                queries = [call.args[1] for call in connection.execute.call_args_list
                           if len(call.args) == 2 and "recttype" in call.args[1]]
                self.assertEqual([row["recttype"] for row in queries], ["D"])
                self.assertEqual(queries[0]["sortOrder"], "Amount")

    def test_clearing_csv_sorting_removes_saved_directions(self):
        original = rb.RetirementBuilderJob.model_validate({
            "id": 31,
            "fileSettings": {"sortingOrder": [{"orderBy": "1", "mappingColumn": "Amount", "direction": "DESC"}]},
            "queryConfiguration": [{"recttype": "D", "query": "detail query", "sortOrder": "ORDER BY [Amount] DESC"}],
        })
        payload = rb._complete_update_payload(input_job(fileSettings={"sortingOrder": []}), original)
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 31, payload)
        queries = [call.args[1] for call in connection.execute.call_args_list
                   if len(call.args) == 2 and "recttype" in call.args[1]]
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0]["Query"], "detail query")
        self.assertEqual(queries[0]["sortOrder"], "")

    def test_payroll_save_replaces_legacy_configuration_with_only_hdt(self):
        payload = input_job(
            general={"reportSource": "companyPayroll"},
            mapping={"rows": [{"field": "Employee Count", "recordType": "Detail"}]},
            queryConfiguration=[
                {"recttype": "PAYROLL", "query": "legacy query"},
                {"recttype": "CSV_SORT", "sortOrder": "ORDER BY [Employee Count] ASC"},
                {"recttype": "D", "query": "stale detail query"},
            ],
        )
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 31, payload)
        queries = [call.args[1] for call in connection.execute.call_args_list
                   if len(call.args) == 2 and "recttype" in call.args[1]]
        self.assertEqual([row["recttype"] for row in queries], ["H", "D", "T"])
        self.assertTrue(all(payroll_source.is_payroll_record_query(row["recttype"], row["Query"]) for row in queries))

    def test_unknown_inherited_query_record_types_are_rejected_before_detail_writes(self):
        payload = input_job(queryConfiguration=[{"recttype": "CUSTOM"}])
        connection = Mock()
        with self.assertRaises(HTTPException) as error:
            rb._write_job_details(connection, 31, payload)
        self.assertEqual(error.exception.status_code, 422)
        connection.execute.assert_not_called()

    def test_switching_from_payroll_to_csv_does_not_retain_payroll_queries(self):
        payroll = input_job(
            general={"reportSource": "companyPayroll"}, mapping={"rows": [{"field": "Employee Count"}]},
        )
        payload = input_job(
            general={"reportSource": "csv"}, queryConfiguration=payroll_record_queries(payroll),
            fileSettings={"sortingOrder": [{"orderBy": "1", "mappingColumn": "Amount", "direction": "DESC"}]},
        )
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 31, payload)
        queries = [call.args[1] for call in connection.execute.call_args_list
                   if len(call.args) == 2 and "recttype" in call.args[1]]
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0]["recttype"], "D")
        self.assertEqual(queries[0]["Query"], "")
        self.assertEqual(queries[0]["sortOrder"], "Amount")


class EditJobReadTests(TestCase):
    def test_legacy_csv_detail_sort_fragment_uses_valid_saved_sorting(self):
        main = {"jobid": 60, "jobfilename": "Legacy CSV", "filetype": "CSV", "jobdesc": "",
                "isEnabled": True, "StoreResults": False, "includeHeader": True, "ismerge": False}
        schedule = {"rbJobTypeChk": "Daily", "schedules_session": "AM", "ScheduleWeek": "1"}
        detail = {"recttype": "D", "Query": "legacy detail query", "Conditions": "", "Sort_Order": ", paydate"}
        legacy_sort = {"recttype": "CSV_SORT", "Query": "", "Conditions": "", "Sort_Order": "ORDER BY [paydate] DESC"}
        expected = [{"orderBy": "1", "mappingColumn": "paydate", "direction": "DESC"}]
        for rows in ([detail, legacy_sort], [legacy_sort, detail]):
            with self.subTest(rows=rows):
                job = rb._job_from_rows(main, schedule, [], [], [], [], rows, {})
                self.assertEqual([rule.model_dump() for rule in job.fileSettings.sortingOrder], expected)
                self.assertEqual(job.general.reportSource, "csv")
                self.assertEqual(job.queryConfiguration[rows.index(detail)].sortOrder, ", paydate")
        # A canonical D row takes priority once the job has been saved in the new format.
        current_detail = {**detail, "Sort_Order": "ORDER BY [paydate] ASC"}
        job = rb._job_from_rows(main, schedule, [], [], [], [], [legacy_sort, current_detail], {})
        self.assertEqual(job.fileSettings.sortingOrder[0].direction, "ASC")

    def test_legacy_csv_detail_sort_fragment_falls_back_to_sorting_details(self):
        main = {"jobid": 60, "jobfilename": "Legacy CSV", "filetype": "CSV", "jobdesc": "",
                "isEnabled": True, "StoreResults": False, "includeHeader": True, "ismerge": False}
        schedule = {"rbJobTypeChk": "Daily", "schedules_session": "AM", "ScheduleWeek": "1"}
        queries = [{"recttype": "D", "Query": "", "Conditions": "", "Sort_Order": ", paydate"}]
        details = [{"sort_order": 1, "mapping_column": "paydate"}]
        job = rb._job_from_rows(main, schedule, [], [], iter(details), [], queries, {})
        self.assertEqual(job.fileSettings.sortingOrder[0].model_dump(), {
            "orderBy": "1", "mappingColumn": "paydate", "direction": "ASC",
        })
        without_details = rb._job_from_rows(main, schedule, [], [], [], [], queries, {})
        self.assertEqual(without_details.fileSettings.sortingOrder[0].mappingColumn, "paydate")

    def test_payroll_invalid_sorting_still_fails_instead_of_using_csv_fallback(self):
        queries = [
            {"recttype": "D", "Query": "/* company payroll */ SELECT 1", "Sort_Order": ", paydate,"},
            {"recttype": "CSV_SORT", "Query": "", "Sort_Order": "ORDER BY [paydate] ASC"},
        ]
        with self.assertRaisesRegex(InvalidRun, "saved sort order is invalid"):
            rb._job_from_rows({"jobid": 60}, {}, [], [], [], [], queries, {})

    def test_empty_result_sets_keep_later_sections_aligned(self):
        datasets = iter([
            {
                "jobid": 7, "jobfilename": "Report", "filetype": "|", "jobdesc": "", "isEnabled": True,
                "StoreResults": False, "includeHeader": True, "ismerge": False,
            },
            {"rbJobTypeChk": "Daily", "schedules_session": "AM", "ScheduleWeek": "1"},
            None,  # mappings
            {"jobclientid": 17, "jobemailind": "example@example.com"},
            None,  # sorting details
            {"mapping_column": "pay_date", "condition_symbol": "date:>=", "condition_value": Decimal(20261101)},
            {"recttype": "CSV_SORT", "Query": "", "Conditions": "", "Sort_Order": "ORDER BY [pay_date] DESC"},
            {"filetyp": "Pipe", "delimiter": "|"},
        ])
        connection = MagicMock()
        cursor = connection.execute.return_value.__enter__.return_value.cursor

        def next_dataset():
            row = next(datasets)
            cursor.description = [(key,) for key in row] if row is not None else [("jobid",)]
            cursor.fetchall.return_value = [tuple(row.values())] if row is not None else []
            return True

        next_dataset()
        cursor.nextset.side_effect = next_dataset
        job = rb._read_edit_job(connection, 7)

        connection.execute.assert_called_once_with(rb.READ_EDIT_JOB, {"jobid": 7})
        self.assertEqual(cursor.nextset.call_count, 7)
        self.assertEqual(job.general.fileFormat, "Pipe")
        self.assertIsNone(job.schedule.startDate)
        self.assertEqual(job.mapping.rows, [])
        self.assertEqual(job.subscriptions.rows[0].client, "17")
        self.assertEqual(job.fileSettings.sortingOrder[0].direction, "DESC")
        self.assertEqual(job.fileSettings.conditionalStatements[0].value, "2026-11-01")


class PayrollQueryTests(TestCase):
    def test_pay_date_condition_survives_storage_and_filters_at_the_calendar_boundary(self):
        payload = input_job(
            general={"fileName": "Payroll", "fileFormat": "Comma", "reportSource": "companyPayroll"},
            mapping={"rows": [{"field": "Pay Date"}]},
            fileSettings={
                "conditionalStatements": [
                    {"mappingColumn": "Pay Date", "condition": ">=", "value": "2026-11-01"},
                ],
                "sortingOrder": [{"orderBy": "1", "mappingColumn": "Pay Date", "direction": "DESC"}],
            },
        )
        rb._validate_payload(payload, creating=True)
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 31, payload)
        templates = json.loads(payroll_source.PAYROLL_QUERIES_FILE.read_text())
        saved_queries = [
            (str(call.args[0]), call.args[1]) for call in connection.execute.call_args_list
            if len(call.args) == 2 and "recttype" in call.args[1]
        ]
        self.assertEqual([values["recttype"] for _, values in saved_queries], ["H", "D", "T"])
        for statement, values in saved_queries:
            self.assertEqual(statement, str(rb._prepared_query(rb.QUERY_31, values)[0]))
            self.assertEqual(values["Query"], templates[values["recttype"]])
            self.assertEqual(values["jobid"], 31)
            self.assertEqual(values["conditionalStmt"], "[Pay Date] >= '2026-11-01'" if values["recttype"] == "D" else "")
            self.assertEqual(values["sortOrder"], "payroll_month" if values["recttype"] == "D" else "")
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
        queries = payroll_record_queries(payload)
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
        settings = Settings(_env_file=None, payroll_report_procedure="reports.usp_RenamedPayroll")
        with patch("app.payroll_source.get_settings", return_value=settings):
            rows = payroll_record_queries(payload)
        connection.execute.assert_not_called()
        self.assertEqual([row["recttype"] for row in rows], ["H", "D", "T"])
        self.assertEqual(rows[1]["conditions"], "[Employee Count] >= 2.00")
        self.assertEqual(rows[1]["sortOrder"], "employee_count")

        job = rb.RetirementBuilderJob.model_validate({
            "id": 31, **payload.model_dump(), "fileSettings": {}, "queryConfiguration": rows,
        })
        run_job = payroll_job_with_saved_rules(job)
        cursor = MagicMock()
        connection.connection.cursor.return_value = cursor
        cursor.description = [("Record Type",), ("Employee Count",)]
        cursor.nextset.return_value = False
        cursor.__iter__.return_value = [("D", 1), ("D", 2), ("D", 4)]
        date_range = ReportDateRange(date(2026, 11, 1), date(2026, 11, 30))
        with patch("app.payroll_source.get_settings", return_value=settings):
            source = load_payroll_source(connection, run_job, date_range)
        statement, job_id, start, end, run_type = cursor.execute.call_args.args
        self.assertIn("EXEC [reports].[usp_RenamedPayroll] @client_id = ?, @paystartdate = ?, @payenddate = ?, @runType = ?", statement)
        self.assertEqual((job_id, start, end, run_type), (31, date_range.start, date_range.end, "A"))
        report, = build_report_files(run_job, source, from_payroll_procedure=True)
        self.assertEqual(report.csv.splitlines(), ["Employee Count", "2", "4"])

    def test_query_file_matches_existing_approved_sql_and_procedure_has_three_parameters(self):
        templates = json.loads(payroll_source.PAYROLL_QUERIES_FILE.read_text())
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        for name in ("011_inline_payroll_record_queries.sql", "012_payroll_report_date_range.sql"):
            sql = (migrations / name).read_text()
            approved = {
                kind: query.replace("''", "'")
                for kind, query in re.findall(r"\('([HDT])', '((?:''|[^'])*)'\)", sql)
            }
            self.assertEqual(templates, approved)
        declaration = sql.split("\nAS\n", 1)[0]
        self.assertEqual(re.findall(r"@(\w+)", declaration), ["jobid", "start_date", "end_date"])
        self.assertNotIn("@templates_only", sql)

    def test_invalid_or_unreadable_template_file_stops_save_before_sql_is_written(self):
        payload = input_job(
            general={"reportSource": "companyPayroll"},
            mapping={"rows": [{"field": "Employee Count"}]},
        )
        invalid_files = [
            "{broken", "[]", "null", "{}",
            json.dumps({"H": "/* company payroll */ SELECT 1", "D": None, "T": 2}),
            json.dumps({"H": "SELECT 1", "D": "SELECT 2", "T": "SELECT 3"}),
        ]
        for contents in invalid_files:
            with self.subTest(contents=contents), patch.object(payroll_source, "PAYROLL_QUERIES_FILE") as file:
                file.read_text.return_value = contents
                connection = Mock()
                connection.execute.return_value.mappings.return_value = []
                with self.assertRaisesRegex(RuntimeError, "query template"):
                    rb._write_job_details(connection, 31, payload)
                self.assertEqual(connection.execute.call_count, 1)  # Only read the mapping catalog.
        with patch.object(payroll_source, "PAYROLL_QUERIES_FILE") as file:
            file.read_text.side_effect = FileNotFoundError
            with self.assertRaisesRegex(RuntimeError, "Unable to read"):
                payroll_record_queries(payload)

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
                cursor.nextset.return_value = False
                cursor.__iter__.return_value = [("D", "Example Company")]

                source = load_payroll_source(connection, job)

                expected = saved_query.replace("[dbo].[usp_CompanyPayrollReport]", "[dbo].[usp_RenamedPayrollReport]")
                self.assertEqual(payroll_report_query(job), expected)
                cursor.execute.assert_called_once_with(
                    payroll_report_query(job, for_run=True), job.id, date(1900, 1, 1), date(1900, 1, 1), "A",
                )
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
        cursor.nextset.return_value = False
        cursor.__iter__.return_value = [("D", "Company A", datetime(2026, 11, 11), 1),
                                        ("D", "Company B", datetime(2026, 11, 12), 2)]

        source = load_payroll_source(connection, job)
        files = build_report_files(job, source, from_payroll_procedure=True)

        cursor.execute.assert_called_once_with(
            payroll_report_query(job, for_run=True), job.id, date(1900, 1, 1), date(1900, 1, 1), "A",
        )
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


class ManualRunDateTests(IsolatedAsyncioTestCase):
    async def test_manual_dates_default_and_reject_a_reversed_range(self):
        async def empty_body():
            yield b""

        request = Mock(headers={}, stream=empty_body)
        with patch.object(rb, "_run_job") as run:
            await rb.run_retirement_builder_job(31, request, end_date=date(2026, 11, 30))
            run.assert_called_once_with(31, None, ReportDateRange(end=date(2026, 11, 30)))
            run.reset_mock()
            with self.assertRaises(HTTPException) as error:
                await rb.run_retirement_builder_job(31, request, date(2026, 12, 1), date(2026, 11, 30))
            self.assertEqual(error.exception.status_code, 422)
            run.assert_not_called()


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
    def test_invalid_and_duplicate_priorities_fail_before_connecting(self):
        cases = [[{"orderBy": value, "mappingColumn": "paydate"}]
                 for value in ("", "0", "-1", "1.5", "ASC", "2147483648")]
        cases.append([{"orderBy": "1", "mappingColumn": "paydate"},
                      {"orderBy": "01", "mappingColumn": "Employee_Name"}])
        for rows in cases:
            for creating in (True, False):
                with self.subTest(rows=rows, creating=creating), patch.object(rb.engine, "begin") as begin:
                    payload = input_job(
                        general={"fileName": "Priority test", "fileFormat": "CSV"},
                        mapping={"rows": [{"field": "paydate"}]}, fileSettings={"sortingOrder": rows},
                    )
                    with self.assertRaises(HTTPException) as error:
                        if creating:
                            rb.create_retirement_builder_job(payload)
                        else:
                            rb.update_retirement_builder_job(30, payload)
                    self.assertEqual(error.exception.status_code, 422)
                    self.assertEqual(error.exception.detail[0]["loc"][-1], "orderBy")
                    begin.assert_not_called()

    def test_required_create_fields_fail_before_connecting(self):
        for general, field in (({}, "fileName"), ({"fileName": "QA"}, "fileFormat")):
            with self.subTest(field=field), patch.object(rb.engine, "begin") as begin:
                with self.assertRaises(HTTPException) as error:
                    rb.create_retirement_builder_job(input_job(general=general))
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(error.exception.detail[0]["loc"], ["body", "general", field])
                begin.assert_not_called()

    def test_fixed_requires_positive_lengths_before_connecting(self):
        for length in ("", "0", "-1", "1001"):
            with self.subTest(length=length), patch.object(rb.engine, "begin") as begin:
                payload = input_job(general={"fileName": "Fixed", "fileFormat": "FIXED"},
                                    mapping={"rows": [{"field": "Name", "length": length}]})
                with self.assertRaises(HTTPException) as error:
                    rb._create_job(payload)
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(error.exception.detail[0]["loc"][-1], "length")
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
            ({"mapping": {"rows": [{"field": "Amount", "recordType": "CUSTOM"}]}}, ["mapping", "rows", 0, "recordType"]),
            ({"queryConfiguration": [{"recttype": "CUSTOM"}]}, ["queryConfiguration", 0, "recttype"]),
            ({"queryConfiguration": [{"recttype": ""}]}, ["queryConfiguration", 0, "recttype"]),
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


class ConfigurationSaveTests(TestCase):
    def test_save_updates_modified_fields_without_writing_last_run_or_history(self):
        payload = input_job(general={
            "fileName": "Unchanged name", "fileFormat": "FIXED", "description": "Edited description",
            "outputFileNameFormat": "CLIENT", "enable": True, "storeResultsToTable": False,
        })
        saved = rb.RetirementBuilderJob(id=60, **payload.model_dump())
        with (patch.object(rb.engine, "begin") as begin,
              patch.object(rb, "_read_full_job", return_value=saved),
              patch.object(rb, "_file_formats", return_value={"TAB": "\t", "FIXED": " "}),
              patch.object(rb, "_write_job_details") as details,
              patch.object(rb, "_record_run") as history):
            connection = begin.return_value.__enter__.return_value
            response = rb.update_retirement_builder_job(60, payload)
        self.assertEqual(response["id"], 60)
        statement = connection.execute.call_args_list[0].args[0]
        compiled = statement.compile(dialect=mssql.dialect())
        self.assertIn("joblastmodified=getdate()", str(compiled))
        self.assertNotIn("joblastrun", str(compiled).casefold())
        self.assertNotIn("rjob_history", str(compiled).casefold())
        self.assertEqual(compiled.params["jobdesc"], "Edited description")
        self.assertEqual(compiled.params["filetype"], " ")
        self.assertEqual(compiled.params["FileNameFormat"], "CLIENT")
        self.assertEqual(compiled.params["jobid_1"], 60)
        self.assertFalse(compiled.params["StoreResults"])
        self.assertEqual(len(connection.execute.call_args_list), 2)  # Config update + unchanged detail replacement query.
        details.assert_called_once()
        history.assert_not_called()

    def test_create_stores_a_space_for_fixed(self):
        payload = input_job(general={"fileName": "Fixed report", "fileFormat": "FIXED"},
                            mapping={"rows": [{"field": "Name", "recordType": "D", "length": "20"}]})
        saved = rb.RetirementBuilderJob(id=60, **payload.model_dump())
        with (patch.object(rb.engine, "begin"),
              patch.object(rb, "_file_formats", return_value={"TAB": "\t", "FIXED": " "}),
              patch.object(rb, "_execute_identity_query", return_value=60) as insert,
              patch.object(rb, "_write_job_details"),
              patch.object(rb, "_read_full_job", return_value=saved)):
            rb._create_job(payload)
        self.assertEqual(insert.call_args.args[2]["filetype"], " ")


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

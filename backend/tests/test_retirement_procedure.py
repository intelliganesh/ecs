from contextlib import ExitStack
import csv
from datetime import UTC, date, datetime
from pathlib import Path
from io import StringIO
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

import pyodbc

from app import payroll_source
from app.core.config import Settings
from app.payroll_source import load_payroll_source, payroll_report_query
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, build_procedure_report_files
from app.retirement_results import InvalidRun, ReportDateRange
from app.report_scheduler import _run_scheduled_job
from app.routers import retirement_builder as rb


def job(*, header=True, trailer=True, details=1, **general):
    kinds = (["H"] if header else []) + ["D"] * details + (["T"] if trailer else [])
    return rb.RetirementBuilderJob.model_validate({
        "id": 60,
        "general": {"fileName": "Retirement", "fileFormat": "Comma", **general},
        "mapping": {"includeHeader": header, "rows": [
            {"field": "Employee", "mappingColumn": "lastname"},
        ]},
        "queryConfiguration": [
            {"recttype": kind, "query": "SELECT valid_flag, retnum, paydate AS sort1, lastname"}
            for kind in kinds
        ],
    })


def result(rows, columns=("valid_flag", "retnum", "sort1", "")):
    return ProcedureResultSet(tuple(columns), tuple(tuple(str(value) for value in row) for row in rows))


class FakeCursor:
    def __init__(self, sets):
        self.sets = sets
        self.index = 0
        self.calls = []
        self.closed = False

    @property
    def description(self):
        current = self.sets[self.index] if self.index < len(self.sets) else None
        return [(name,) for name in current.columns] if current is not None else None

    def execute(self, *args):
        self.calls.append(args)

    def __iter__(self):
        return iter(self.sets[self.index].rows)

    def nextset(self):
        self.index += 1
        return self.index < len(self.sets)

    def close(self):
        self.closed = True


class ProcedureInputAndResultTests(TestCase):
    def test_dynamic_procedure_gets_job_id_dates_and_each_run_type_and_drains_results(self):
        report_job = job()
        dates = ReportDateRange(date(2026, 10, 10), date(2026, 10, 17))
        settings = Settings(_env_file=None, payroll_report_procedure="reports.rjobbuilder_renamed")
        sets = [None, result([(1, 101, "2026-10-10", "Employee")]),
                result([(1, 101, "2026-10-10", "Example")]),
                result([(1, 101, "1900-01-01", "End")]), None]
        for run_type in ("A", "S"):
            with self.subTest(run_type=run_type), patch.object(payroll_source, "get_settings", return_value=settings):
                connection = Mock()
                cursor = FakeCursor(sets)
                connection.connection.cursor.return_value = cursor
                source = load_payroll_source(connection, report_job, dates, run_type=run_type)
                self.assertEqual(cursor.calls, [(
                    "EXEC [reports].[rjobbuilder_renamed] @client_id = ?, @paystartdate = ?, @payenddate = ?, @runType = ?",
                    60, date(2026, 10, 10), date(2026, 10, 17), run_type,
                )])
                self.assertEqual(len(source.result_sets), 3)
                self.assertEqual(cursor.index, len(sets))
                self.assertTrue(cursor.closed)
                connection.execute.assert_not_called()  # No company lookup or saved-query rewrite.

    def test_manual_default_and_source_selection_use_existing_job_queries(self):
        report_job = job()
        dates = ReportDateRange(date(2026, 10, 10), date(2026, 10, 17))
        with patch.object(rb, "load_payroll_source") as load, patch.object(rb, "load_report_source") as csv:
            rb._read_report_source(Mock(), report_job, Path("unused"), dates)
            self.assertEqual(load.call_args.kwargs, {"run_type": "A"})
            rb._read_report_source(Mock(), report_job, Path("unused"), dates, scheduled=True)
            self.assertEqual(load.call_args.kwargs, {"run_type": "S"})
            csv.assert_not_called()

    def test_plain_csv_job_still_uses_file_and_csv_override_skips_procedure(self):
        report_job = job()
        report_job.queryConfiguration = []
        with patch.object(rb, "load_payroll_source") as load, patch.object(rb, "load_report_source") as csv:
            rb._read_report_source(Mock(), report_job, Path("inputs"))
            csv.assert_called_once_with(Path("inputs"), 60)
            load.assert_not_called()

    def test_invalid_run_type_is_rejected_before_database_access(self):
        connection = Mock()
        with self.assertRaises(InvalidRun):
            load_payroll_source(connection, job(), run_type="X")
        connection.connection.cursor.assert_not_called()
        connection.execute.assert_not_called()

    def test_no_result_and_trailing_sql_error_close_cursor(self):
        connection = Mock()
        cursor = FakeCursor([None])
        connection.connection.cursor.return_value = cursor
        with self.assertRaisesRegex(InvalidRun, "no result set"):
            load_payroll_source(connection, job())
        self.assertTrue(cursor.closed)
        cursor = FakeCursor([result([(1, 101, "2026-10-10", "Example")])])
        connection.connection.cursor.return_value = cursor
        cursor.nextset = Mock(side_effect=pyodbc.Error("fake trailing history error"))
        with self.assertRaisesRegex(InvalidRun, "could not be read"):
            load_payroll_source(connection, job())
        self.assertTrue(cursor.closed)

    def test_procedure_rows_and_source_bytes_are_bounded(self):
        connection = Mock()
        for field, limit, data in [("MAX_ROWS", 1, [(1, 1, "", "A"), (1, 1, "", "B")]),
                                   ("MAX_SOURCE_BYTES", 20, [(1, 1, "", "X" * 25)])]:
            with self.subTest(field=field), patch.object(payroll_source, field, limit):
                cursor = FakeCursor([result(data)])
                connection.connection.cursor.return_value = cursor
                with self.assertRaises(InvalidRun):
                    load_payroll_source(connection, job())
                self.assertTrue(cursor.closed)

    def test_procedure_name_validation_still_applies_to_the_call(self):
        settings = Settings(_env_file=None, payroll_report_procedure="rjobbuilder")
        with patch.object(payroll_source, "get_settings", return_value=settings):
            self.assertTrue(payroll_report_query(job(), for_run=True).startswith("EXEC [dbo].[rjobbuilder] "))


class ProcedureFileTests(TestCase):
    def test_name_wrappers_are_removed_without_stripping_internal_quotes_or_other_fields(self):
        report_job = job(header=False, trailer=False)
        report_job.mapping.rows = [
            rb.MappingRow(field="Employee", mappingColumn="emp_formatted_name"),
            rb.MappingRow(field="Notes", mappingColumn="notes"),
        ]
        source = ProcedureSource((result([
            (1, 719, "2026-11-10", '"Sample, Alex"', '"Keep these quotes"'),
            (1, 719, "2026-11-10", '"Sample, Sam "Ace""', 'unchanged'),
        ], ("valid_flag", "retnum", "sort1", "CFIRSTNAME", "Notes")),))
        report, = build_procedure_report_files(report_job, source, ",")
        self.assertEqual(list(csv.reader(StringIO(report.csv))), [
            ["Sample, Alex", '"Keep these quotes"'], ['Sample, Sam "Ace"', "unchanged"],
        ])
        self.assertEqual(source.result_sets[0].rows[0][3], '"Sample, Alex"')

    def test_ssn_masks_apply_to_procedure_values_and_preserve_leading_zeros(self):
        for mask, expected in (("XXXXXXXXX", "000000000"), ("XXXXXXXXX - SSN", "000000000"),
                               ("XXX-XX-XXXX", "000-00-0000"), ("XXX-XX-XXXX - SSN", "000-00-0000")):
            for value in ("000-00-0000", "000000000"):
                with self.subTest(mask=mask, source=value):
                    report_job = job(header=False, trailer=False)
                    report_job.mapping.rows = [rb.MappingRow(field="LASTNAME", mappingColumn="ssn", format=mask)]
                    source = ProcedureSource((result([(1, 719, "2026-11-10", value)]),))
                    report, = build_procedure_report_files(report_job, source, ",")
                    self.assertEqual(report.csv, expected + "\r\n")
        for value in ("", "   "):
            source = ProcedureSource((result([(1, 719, "2026-11-10", value)]),))
            report, = build_procedure_report_files(report_job, source, ",")
            self.assertEqual(list(csv.reader(StringIO(report.csv))), [[""]])
        with self.assertRaisesRegex(InvalidRun, "nine SSN digits"):
            build_procedure_report_files(report_job, ProcedureSource((result([(1, 719, "2026-11-10", "123")]),)), ",")

    def test_fixed_records_pad_each_field_without_delimiters_and_keep_excel_columns(self):
        report_job = job(fileFormat="FIXED", outputFileNameFormat="CLIENT_PAYDAY")
        report_job.mapping.rows = [
            rb.MappingRow(field="NAME", mappingColumn="emp_formatted_name", length="16", recordType="D", colSeqNo=1),
            rb.MappingRow(field="SSN", mappingColumn="ssn", format="XXXXXXXXX", length="9", recordType="D", colSeqNo=2),
            rb.MappingRow(field="HIRE", mappingColumn="last_hire_date", format="MM/DD/YYYY", length="10", recordType="D", colSeqNo=3),
            rb.MappingRow(field="COUNT", mappingColumn="count", format="RA", length="5", recordType="D", colSeqNo=4),
        ]
        next(row for row in report_job.queryConfiguration if row.recttype == "D").query = (
            "SELECT valid_flag, retnum, paydate AS sort1, emp_formatted_name, ssn, last_hire_date, count"
        )
        columns = ("valid_flag", "retnum", "sort1", "", "", "", "")
        source = ProcedureSource((result([(1, "000719", "2026-11-10", "NAME", "SSN", "HIRE", "COUNT")], columns),
                                  result([(1, "000719", "2026-11-10", '"Doe, Alex"', "000-00-0000", "2020-01-02", "7")], columns),
                                  result([(1, "000719", "1900-01-01")], ("valid_flag", "retnum", "sort1")),))
        report, = build_procedure_report_files(report_job, source, " ")
        lines = report.csv.splitlines()
        self.assertEqual([len(line) for line in lines], [40, 40])
        self.assertEqual(lines[1], "Doe, Alex       " + "000000000" + "01/02/2020" + "    7")
        self.assertEqual(lines[1][16:25], "000000000")
        self.assertEqual(report.excel_rows[1], ["Doe, Alex       ", "000000000", "01/02/2020", "    7"])
        self.assertEqual(list(report.rows[1].values.values()), report.excel_rows[1])
        self.assertEqual(report.file_name, "000719_2026-11-10.txt")
        self.assertEqual([r.record_type for r in report.rows], ["H", "D"])

    def test_fixed_configured_header_detail_and_trailer_keep_separate_widths(self):
        report_job = job(fileFormat="FIXED")
        report_job.mapping.includeHeader = False
        report_job.mapping.rows = [
            rb.MappingRow(field="Header", recordType="H", length="4"),
            rb.MappingRow(field="Name", mappingColumn="lastname", recordType="D", length="6"),
            rb.MappingRow(field="Total", recordType="T", length="3", format="RA"),
        ]
        source = ProcedureSource((result([(1, 719, "2026-11-10", "HEAD")]),
                                  result([(1, 719, "2026-11-10", '"Joe"')]),
                                  result([(1, 719, "1900-01-01", "2")]),))
        report, = build_procedure_report_files(report_job, source, " ")
        self.assertEqual(report.csv, "HEAD\r\nJoe   \r\n  2\r\n")
        self.assertEqual([row.record_type for row in report.rows], ["H", "D", "T"])

    def test_date_mapping_formats_raw_iso_dates_without_touching_header_or_filename_metadata(self):
        report_job = job(outputFileNameFormat="CLIENT_PAYDAY")
        report_job.mapping.rows = [
            rb.MappingRow(field="Name", mappingColumn="name", format="Uppercase", recordType="D", colSeqNo=2),
            rb.MappingRow(field="PAYDATE", mappingColumn="paydate", format="MM/DD/YYYY", recordType="D", colSeqNo=1),
        ]
        next(row for row in report_job.queryConfiguration if row.recttype == "D").query = (
            "SELECT valid_flag, retnum, paydate AS sort1, paydate, name"
        )
        source = ProcedureSource((
            result([(1, "000719", "2026-11-10", "PAYDATE", "Name")], ("valid_flag", "retnum", "sort1", "", "")),
            result([(1, "000719", "2026-11-10", "2026-11-10", "Mixed Case")], ("valid_flag", "retnum", "sort1", "", "")),
            result([(1, "000719", "1900-01-01")], ("valid_flag", "retnum", "sort1")),
        ))
        saved_queries = [row.model_dump() for row in report_job.queryConfiguration]
        report, = build_procedure_report_files(report_job, source, "\t")
        self.assertEqual(report.file_name, "000719_2026-11-10.csv")
        self.assertEqual(report.csv, "PAYDATE\tName\r\n11/10/2026\tMIXED CASE\r\n")
        self.assertEqual(list(report.rows[1].values.values()), ["11/10/2026", "MIXED CASE"])
        self.assertEqual([row.model_dump() for row in report_job.queryConfiguration], saved_queries)
        self.assertEqual(source.result_sets[1].rows[0][3], "2026-11-10")

    def test_selected_date_formats_are_idempotent_for_already_formatted_procedure_values(self):
        formats = {
            "MM/DD/YYYY": "11/10/2026", "MM-DD-YYYY": "11-10-2026", "MMDDYYYY": "11102026",
            "DD/MM/YYYY": "10/11/2026", "DD-MM-YYYY": "10-11-2026", "YYYY-MM-DD": "2026-11-10",
            "CCYYMMDD": "20261110", "YYYYMMDD": "20261110", "MMDDYYYY - Date": "11102026",
        }
        for name, expected in formats.items():
            for value in ("2026-11-10", expected):
                with self.subTest(format=name, value=value):
                    report_job = job(header=False, trailer=False)
                    report_job.mapping.rows = [rb.MappingRow(field="Date", format=name)]
                    report, = build_procedure_report_files(report_job, ProcedureSource((result([(1, 719, "2026-11-10", value)]),)), ",")
                    self.assertEqual(report.csv, expected + "\r\n")

    def test_configured_header_and_trailer_dates_follow_their_own_mappings(self):
        report_job = job()
        report_job.mapping.includeHeader = False  # Explicit H dataset, not automatic column labels.
        report_job.mapping.rows = [
            rb.MappingRow(field="Start", recordType="H", format="MM/DD/YYYY"),
            rb.MappingRow(field="Detail", recordType="D"),
            rb.MappingRow(field="End", recordType="T", format="MMDDYYYY"),
        ]
        source = ProcedureSource((result([(1, 719, "2026-11-10", "2026-11-10")]),
                                  result([(1, 719, "2026-11-10", "unchanged")]),
                                  result([(1, 719, "1900-01-01", "2026-11-12")]),))
        report, = build_procedure_report_files(report_job, source, ",")
        self.assertEqual(report.csv, "11/10/2026\r\nunchanged\r\n11122026\r\n")

    def test_multiple_detail_datasets_keep_their_date_format_and_order(self):
        report_job = job(header=False, trailer=False, details=2)
        report_job.mapping.rows = [
            rb.MappingRow(field="Second", dataSetNo=2, recordType="D", format="MMDDYYYY"),
            rb.MappingRow(field="First", dataSetNo=1, recordType="D", format="MM/DD/YYYY"),
        ]
        source = ProcedureSource((result([(1, 719, "2026-11-10", "2026-11-10")]),
                                  result([(1, 719, "2026-11-12", "2026-11-12")]),))
        report, = build_procedure_report_files(report_job, source, ",")
        self.assertEqual(report.csv, "11/10/2026\r\n11122026\r\n")

    def test_ambiguous_date_mapping_alignment_fails_instead_of_formatting_another_column(self):
        report_job = job(header=False, trailer=False)
        report_job.mapping.rows = [rb.MappingRow(field="Date", format="MM/DD/YYYY")]
        source = ProcedureSource((result([(1, 719, "2026-11-10", "Name", "2026-11-10")],
                                         ("valid_flag", "retnum", "sort1", "name", "paydate")),))
        with self.assertRaisesRegex(InvalidRun, "export mappings do not match"):
            build_procedure_report_files(report_job, source, ",")

    def test_returned_values_and_order_are_preserved_without_remapping_or_second_header(self):
        source = ProcedureSource((result([(1, 101, "2026-10-10", "Employee")]),
                                  result([(1, 101, "2026-10-10", "mixed Case"), (1, 101, "2026-10-10", "Second")]),
                                  result([(1, 101, "1900-01-01", "Total=2")]),))
        report, = build_procedure_report_files(job(), source, "|")
        self.assertEqual(report.csv, "Employee\r\nmixed Case\r\nSecond\r\nTotal=2\r\n")
        self.assertEqual([row.record_type for row in report.rows], ["H", "D", "D", "T"])
        self.assertEqual(report.client_ids, frozenset({"101"}))
        self.assertIsNone(report.payroll_company_ids)

    def test_multiple_detail_sets_unnamed_duplicate_columns_and_no_header(self):
        source = ProcedureSource((
            result([(1, 101, "2026-10-10", "a", "b", "c")], ("valid_flag", "retnum", "sort1", "", "same", "same")),
            result([(1, 101, "2026-10-10", "d")]),
            result([(1, 101, "1900-01-01")], ("valid_flag", "retnum", "sort1")),
        ))
        report, = build_procedure_report_files(job(header=False, details=2), source, ",")
        self.assertEqual(report.csv, "a,b,c\r\nd\r\n")
        self.assertEqual(list(report.rows[0].values.values()), ["a", "b", "c"])

    def test_client_date_grouping_uses_metadata_and_repeats_column_header(self):
        source = ProcedureSource((
            result([(1, 101, "2026-10-10", "Employee")]),
            result([(1, 101, "2026-10-10", "One"), (1, 102, "2026-10-17", "Two")]),
            result([(1, 101, "1900-01-01", "End101"), (1, 102, "1900-01-01", "End102")]),
        ))
        reports = build_procedure_report_files(job(outputFileNameFormat="CLIENT_PAYDAY"), source, ",")
        self.assertEqual({report.file_name: report.csv for report in reports}, {
            "101_2026-10-10.csv": "Employee\r\nOne\r\nEnd101\r\n",
            "102_2026-10-17.csv": "Employee\r\nTwo\r\nEnd102\r\n",
        })

    def test_zero_flag_placeholders_and_empty_details_produce_no_files(self):
        source = ProcedureSource((
            result([(101, 101)], ("retnum", "retnum1")),
            result([(0, 101, "2026-10-10", "")], ("valid_flag1", "retnum", "sort1", "lastname")),
            result([(101, 101)], ("retnum", "retnum1")),
        ))
        self.assertEqual(build_procedure_report_files(job(), source, ","), [])
        empty = ProcedureSource((result([]), result([]), result([])))
        self.assertEqual(build_procedure_report_files(job(), empty, ","), [])

    def test_bad_contracts_and_output_limit_fail_before_publishing(self):
        valid = (result([(1, 101, "2026-10-10", "Header")]), result([(1, 101, "2026-10-10", "Detail")]), result([]))
        with self.assertRaisesRegex(InvalidRun, "do not match"):
            build_procedure_report_files(job(), ProcedureSource(valid[:2]), ",")
        with self.assertRaisesRegex(InvalidRun, "must return"):
            build_procedure_report_files(job(), ProcedureSource((result([], ("wrong",)), *valid[1:])), ",")
        with patch("app.retirement_procedure.MAX_OUTPUT_BYTES", 10), self.assertRaisesRegex(InvalidRun, "10 MB"):
            build_procedure_report_files(job(), ProcedureSource(valid), ",")

    def test_pipeline_does_not_reapply_mappings_filters_storage_or_history_dates(self):
        source = ProcedureSource((result([(1, 101, "2026-10-10", "Employee")]),
                                  result([(1, 101, "2026-10-10", "mixed Case")]), result([])))
        connection = MagicMock()
        formats = Mock()
        formats.mappings.return_value = [{"filetyp": "Comma", "delimiter": ","}]
        connection.execute.return_value = formats
        with TemporaryDirectory() as directory, ExitStack() as resources, \
                patch.object(rb, "store_results") as store, patch.object(rb, "_record_run") as history, \
                patch.object(rb, "build_report_files") as remap:
            run, reports = rb._execute_report_run(connection, job(storeResultsToTable=True), lambda _: source,
                                                  Path(directory), resources)
            self.assertEqual(reports[0].csv, "Employee\r\nmixed Case\r\n")
            self.assertEqual(run.storedRows, 0)  # SP, not rjob_result, owns production result storage.
            store.assert_not_called()
            remap.assert_not_called()
            self.assertTrue(history.call_args.kwargs["dates_recorded"])

    def test_scheduled_entry_passes_s_through_to_configured_procedure_loader(self):
        report_job = job()
        now = datetime(2026, 11, 19, 10, tzinfo=UTC)
        settings = Settings(_env_file=None)
        with TemporaryDirectory() as directory, \
                patch("app.report_scheduler.report_directory", return_value=Path(directory)), \
                patch("app.report_scheduler.engine") as engine, \
                patch("app.report_scheduler._read_full_job", return_value=report_job), \
                patch("app.report_scheduler._attempt_report_run") as attempt, \
                patch("app.report_scheduler.send_subscribed_reports"), \
                patch.object(rb, "load_payroll_source") as load:
            connection = engine.begin.return_value.__enter__.return_value
            locked = Mock()
            locked.scalar_one_or_none.return_value = 60
            schedule = Mock()
            schedule.mappings.return_value.first.return_value = {
                "startDateTime": now.replace(tzinfo=None), "ScheduleType": "D", "ScheduleWeek": 4, "MonthlyDate": "",
            }
            connection.execute.side_effect = [locked, schedule]
            def execute(conn, saved_job, read_source, *args, **kwargs):
                read_source(saved_job)
                return Mock(rowCount=0), []
            attempt.side_effect = execute
            _run_scheduled_job(settings, 60, now, now)
            load.assert_called_once_with(connection, report_job, ReportDateRange(), run_type="S")


class ProcedurePresentationFormatTests(TestCase):
    def build(self, rows, values, *, delimiter=",", **general):
        report_job = job(header=False, trailer=False, **general)
        report_job.mapping.rows = rows
        columns = ("valid_flag", "retnum", "sort1") + ("",) * len(rows)
        source = ProcedureSource((result([(1, 719, "2026-11-10", *values)], columns),))
        report, = build_procedure_report_files(report_job, source, delimiter)
        return report

    def test_invalid_padding_is_not_silently_ignored_in_any_delimited_format(self):
        for delimiter in (",", "|", ";", "\t", "~"):
            for format_name in ("LA", "RA", "LA - Left Justified", "RA - Right Justified"):
                for value in ("sample text", ""):
                    with self.subTest(delimiter=delimiter, format=format_name, value=value):
                        with self.assertRaisesRegex(InvalidRun, "padding length from 0 to 1000"):
                            self.build([rb.MappingRow(field="Text", format=format_name, length="1001")], (value,), delimiter=delimiter)

    def test_padding_boundaries_preserve_empty_values_and_justify_text(self):
        for format_name in ("LA", "RA", "LA - Left Justified", "RA - Right Justified"):
            for length in ("0", "1", "1000"):
                with self.subTest(format=format_name, length=length):
                    report = self.build([rb.MappingRow(field="Text", format=format_name, length=length)], ("ABC",))
                    value = next(csv.reader(StringIO(report.csv)))[0]
                    self.assertEqual(len(value), max(3, int(length)))
                    self.assertEqual(value.strip(), "ABC")
                    self.assertTrue(value.endswith("ABC") if format_name.startswith("RA") else value.startswith("ABC"))
            report = self.build([rb.MappingRow(field="Text", format=format_name, length="1000")], ("",))
            self.assertEqual(next(csv.reader(StringIO(report.csv))), [""])

    def test_text_number_and_padding_formats_are_applied_to_returned_values(self):
        report = self.build([
            rb.MappingRow(field="Name", format="Uppercase"),
            rb.MappingRow(field="Amount", format="$######.##"),
            rb.MappingRow(field="Phone", format="RA", length="12"),
            rb.MappingRow(field="Code", format="LA", length="5"),
        ], ("mixed Case", "67500.25", "7168884838", "ab"))
        self.assertEqual(report.csv, "MIXED CASE,$67500.25,  7168884838,ab   \r\n")

    def test_numeric_masks_keep_decimal_zeros_in_procedure_output(self):
        report = self.build([
            rb.MappingRow(field="Zero", format="######.##"),
            rb.MappingRow(field="SQL formatted zero", format="######.##"),
            rb.MappingRow(field="Whole", format="######.##"),
            rb.MappingRow(field="Fraction", format="######.##"),
            rb.MappingRow(field="Negative", format="######.##"),
            rb.MappingRow(field="Blank", format="######.##"),
            rb.MappingRow(field="Default", format="######.##", defaultValue="0"),
            rb.MappingRow(field="Integer", format="########"),
        ], ("0", "0.00", "25", "25.5", "-25.5", "", "", "0"))
        self.assertEqual(report.csv, "0.00,0.00,25.00,25.50,-25.50,,0.00,0\r\n")

    def test_default_value_replaces_blank_values_only(self):
        report = self.build([
            rb.MappingRow(field="Email", defaultValue="N/A"),
            rb.MappingRow(field="Other", defaultValue="N/A"),
        ], ("", "kept"))
        self.assertEqual(report.csv, "N/A,kept\r\n")

    def test_already_formatted_numbers_are_left_as_returned(self):
        # SQL generated by the app may already have applied the mask; a second pass must not fail.
        report = self.build([rb.MappingRow(field="Amount", format="$######.##")], ("$67500.25",))
        self.assertEqual(report.csv, "$67500.25\r\n")


class ProcedureTrailerTests(TestCase):
    def test_trailer_dates_without_detail_rows_are_not_written(self):
        report_job = job(header=False, outputFileNameFormat="CLIENT")
        report_job.mapping.rows = [rb.MappingRow(field="Value")]
        source = ProcedureSource((
            result([(1, 719, "2026-10-14", "kept")]),
            result([(1, 719, "2026-10-13", "dropped trailer"), (1, 719, "2026-10-14", "trailer")]),
        ))
        report, = build_procedure_report_files(report_job, source, ",")
        self.assertEqual(report.csv, "kept\r\ntrailer\r\n")

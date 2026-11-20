"""Extension regressions using synthetic data, temporary folders and mocked I/O only."""

from datetime import UTC, datetime
import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.report_files import publish_report
from app.report_mail import send_report_email
from app.report_scheduler import _run_scheduled_job
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, build_procedure_report_files
from app.retirement_results import _output_name, build_report_files, merge_report_files, report_extension
from app.routers.retirement_builder import RetirementBuilderJob


FORMATS = (("CSV", ",", ".csv"), ("PIPE", "|", ".txt"), ("SEMICOLON", ";", ".txt"),
           ("TAB", "\t", ".tsv"), ("TILDE", "~", ".txt"), ("FIXED", " ", ".txt"))
HEADERS = ["PAYDATE", "WORK PHONE", "LASTNAME", "FIRSTNAME", "WORK EMAIL", "AMOUNT", "OTHER", "SINCE"]
VALUES = ["10/15/2026", "0000000000", "000000001", 'José, "Ace"|;~', "", "67500.00", "", "02/14/1978"]
WIDTHS = (10, 10, 9, 40, 50, 20, 30, 20)  # 189-character FIXED layout.


def sample_job(file_format, name_format="FILENAME_CLIENT_PAYDAY"):
    return RetirementBuilderJob.model_validate({
        "id": 60,
        "general": {"fileName": "Payroll.v2.CSV", "fileFormat": file_format, "outputFileNameFormat": name_format},
        "mapping": {"includeHeader": True, "rows": [
            {"field": name, "mappingColumn": name, "length": str(width) if file_format == "FIXED" else "0"}
            for name, width in zip(HEADERS, WIDTHS, strict=True)
        ]},
        "queryConfiguration": [{"recttype": kind, "query": "SELECT fixture"} for kind in ("H", "D", "T")],
    })


def source_csv():
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["clientid", "paydate", *HEADERS[1:]])
    for client in ("000204", "000719"):
        writer.writerow([client, *VALUES])
    return stream.getvalue().encode("utf-8")


def procedure_source():
    columns = ("valid_flag", "retnum", "sort1", *HEADERS)
    return ProcedureSource((
        ProcedureResultSet(columns, (("1", "000204", "2026-10-15", *HEADERS),)),
        ProcedureResultSet(columns, (("1", "000204", "2026-10-15", *VALUES),
                                     ("1", "000719", "2026-10-15", *VALUES))),
        ProcedureResultSet(("valid_flag", "retnum", "sort1"), (("1", "000204", "1900-01-01"),)),
    ))


def expected_content(delimiter, *, fixed=False, copies=1):
    if fixed:
        return "".join("".join(value.ljust(width) for value, width in zip(row, WIDTHS, strict=True)) + "\r\n"
                       for row in [HEADERS, *[VALUES] * copies])
    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerows([HEADERS, *[VALUES] * copies])
    return stream.getvalue()


class ReportExtensionTests(TestCase):
    def test_decimal_mask_keeps_zero_and_fraction_width_in_all_six_formats(self):
        for file_format, delimiter, extension in FORMATS:
            with self.subTest(file_format=file_format):
                job = sample_job(file_format)
                job.mapping.rows[5].format = "######.##"
                raw_values = [list(VALUES), list(VALUES)]
                raw_values[0][5], raw_values[1][5] = "0", "25.5"
                stream = StringIO(newline="")
                writer = csv.writer(stream)
                writer.writerow(["clientid", "paydate", *HEADERS[1:]])
                for client, values in zip(("000204", "000719"), raw_values, strict=True):
                    writer.writerow([client, *values])
                source = procedure_source()
                sets = list(source.result_sets)
                sets[1] = ProcedureResultSet(sets[1].columns, tuple(
                    ("1", client, "2026-10-15", *values)
                    for client, values in zip(("000204", "000719"), raw_values, strict=True)
                ))
                for reports in (build_report_files(job, stream.getvalue().encode(), delimiter=delimiter),
                                build_procedure_report_files(job, ProcedureSource(tuple(sets)), delimiter)):
                    self.assertEqual(len(reports), 2)
                    for report, expected in zip(reports, ("0.00", "25.50"), strict=True):
                        self.assertTrue(report.file_name.endswith(extension))
                        if file_format == "FIXED":
                            data = report.csv.splitlines()[1]
                            offset = sum(WIDTHS[:5])
                            self.assertEqual(data[offset:offset + WIDTHS[5]].strip(), expected)
                            self.assertEqual(len(data), sum(WIDTHS))
                        else:
                            rows = list(csv.reader(StringIO(report.csv), delimiter=delimiter))
                            self.assertEqual(rows[0], HEADERS)
                            self.assertEqual(rows[1][5], expected)
                            self.assertEqual(len(rows[1]), len(HEADERS))

    def test_both_writers_keep_content_and_client_names_for_all_six_formats(self):
        for file_format, delimiter, extension in FORMATS:
            with self.subTest(file_format=file_format):
                job = sample_job(file_format)
                for reports in (build_report_files(job, source_csv(), delimiter=delimiter),
                                build_procedure_report_files(job, procedure_source(), delimiter)):
                    self.assertEqual([report.file_name for report in reports], [
                        f"Payroll.v2_000204_2026-10-15{extension}", f"Payroll.v2_000719_2026-10-15{extension}",
                    ])
                    for report in reports:
                        self.assertEqual(report.csv.encode("utf-8"), expected_content(delimiter, fixed=file_format == "FIXED").encode("utf-8"))
                        if file_format == "FIXED":
                            self.assertEqual([len(line) for line in report.csv.splitlines()], [189, 189])
                        else:
                            self.assertEqual(list(csv.reader(StringIO(report.csv), delimiter=delimiter)), [HEADERS, VALUES])
                    merged = merge_report_files(job, reports)
                    self.assertEqual(merged.file_name, f"Payroll.v2_merged{extension}")
                    self.assertEqual(merged.csv, expected_content(delimiter, fixed=file_format == "FIXED", copies=2))
                    with TemporaryDirectory() as directory:
                        path = Path(directory) / merged.file_name
                        with publish_report(path, merged.csv):
                            self.assertEqual(path.read_bytes(), merged.csv.encode("utf-8"))

    def test_all_seven_name_formats_and_supported_final_suffixes(self):
        parts = {"file name": "Payroll.v2", "client id": "000204", "payday": "2026-10-15"}
        combinations = (("file name",), ("client id",), ("payday",), ("file name", "client id"),
                        ("file name", "payday"), ("client id", "payday"), tuple(parts))
        for file_format, _, extension in FORMATS:
            for combination in combinations:
                for suffix in (".csv", ".TXT", ".TsV", ""):
                    with self.subTest(file_format=file_format, combination=combination, suffix=suffix):
                        job = sample_job(file_format)
                        job.general.fileName = "Payroll.v2" + suffix
                        group = {part: parts[part] for part in combination if part != "file name"}
                        self.assertEqual(_output_name(job, combination, group), "_".join(parts[part] for part in combination) + extension)
        for legacy, extension in (("COMMA", ".csv"), ("CSV_PIPE", ".txt"), ("CSV_TAB", ".tsv"),
                                  ("CSV_SEMI", ".txt"), ("CSV (COMMA DELIMITED)", ".csv"), (" fixed ", ".txt")):
            self.assertEqual(report_extension(legacy), extension)

    def test_all_seven_grouping_formats_in_both_writers(self):
        names = {
            "FILENAME": ["Payroll.v2"],
            "CLIENT": ["000204", "000719"],
            "PAYDAY": ["2026-10-15"],
            "FILENAME_CLIENT": ["Payroll.v2_000204", "Payroll.v2_000719"],
            "FILENAME_PAYDAY": ["Payroll.v2_2026-10-15"],
            "CLIENT_PAYDAY": ["000204_2026-10-15", "000719_2026-10-15"],
            "FILENAME_CLIENT_PAYDAY": ["Payroll.v2_000204_2026-10-15", "Payroll.v2_000719_2026-10-15"],
        }
        for file_format, delimiter, extension in FORMATS:
            for name_format, stems in names.items():
                with self.subTest(file_format=file_format, name_format=name_format):
                    job = sample_job(file_format, name_format)
                    for reports in (build_report_files(job, source_csv(), delimiter=delimiter),
                                    build_procedure_report_files(job, procedure_source(), delimiter)):
                        self.assertEqual([r.file_name for r in reports], [stem + extension for stem in stems])
                        for report in reports:
                            self.assertEqual(report.csv, expected_content(
                                delimiter, fixed=file_format == "FIXED", copies=2 if len(stems) == 1 else 1))

    def test_configured_header_detail_and_trailer_content_remains_in_order(self):
        trailer = ["END"] * len(HEADERS)
        for file_format, delimiter, extension in FORMATS:
            with self.subTest(file_format=file_format):
                job = sample_job(file_format, "FILENAME")
                job.mapping.includeHeader = False
                detail = job.mapping.rows
                job.mapping.rows = [row.model_copy(update={"recordType": kind})
                                    for kind in ("H", "D", "T") for row in detail]
                stream = StringIO(newline="")
                writer = csv.writer(stream)
                writer.writerow(["Record Type", *HEADERS])
                writer.writerows([["H", *HEADERS], ["D", *VALUES], ["T", *trailer]])
                columns = ("valid_flag", "retnum", "sort1", *HEADERS)
                source = ProcedureSource(tuple(ProcedureResultSet(columns, (("1", "000204", "2026-10-15", *values),))
                                               for values in (HEADERS, VALUES, trailer)))
                for reports in (build_report_files(job, stream.getvalue().encode("utf-8"), delimiter=delimiter),
                                build_procedure_report_files(job, source, delimiter)):
                    report, = reports
                    self.assertEqual(report.file_name, "Payroll.v2" + extension)
                    self.assertEqual([row.record_type for row in report.rows], ["H", "D", "T"])
                    if file_format == "FIXED":
                        self.assertEqual(report.csv, "".join(
                            "".join(value.ljust(width) for value, width in zip(values, WIDTHS, strict=True)) + "\r\n"
                            for values in (HEADERS, VALUES, trailer)))
                    else:
                        self.assertEqual(list(csv.reader(StringIO(report.csv), delimiter=delimiter)), [HEADERS, VALUES, trailer])

    def test_collision_suffixes_preserve_extensions_for_both_writers(self):
        for file_format, delimiter, extension in FORMATS:
            job = sample_job(file_format, "CLIENT")
            csv_source = source_csv().replace(b"000204", b"A/B").replace(b"000719", b"A:B")
            source = procedure_source()
            source = ProcedureSource(tuple(ProcedureResultSet(s.columns, tuple(
                tuple("A/B" if value == "000204" else "A:B" if value == "000719" else value for value in row)
                for row in s.rows)) for s in source.result_sets))
            for reports in (build_report_files(job, csv_source, delimiter=delimiter),
                            build_procedure_report_files(job, source, delimiter)):
                with self.subTest(file_format=file_format):
                    names = [report.file_name for report in reports]
                    self.assertEqual(len(names), 2)
                    self.assertEqual(len(set(names)), 2)
                    self.assertEqual(names[0], "A_B" + extension)
                    self.assertTrue(all(name.endswith(extension) for name in names))
                    self.assertTrue(names[1].startswith("A_B_"))

    def test_completion_detection_includes_new_and_historical_extensions_without_execution(self):
        slot = datetime(2026, 10, 15, tzinfo=UTC)
        for name in ("historical.csv", "pipe.txt", "tab.tsv", "UPPER.TSV", ".complete"):
            with self.subTest(name=name), TemporaryDirectory() as directory:
                settings = Settings(_env_file=None, report_output_dir=directory, mail_enabled=False, scheduler_enabled=False)
                folder = Path(directory) / "scheduled" / "60" / slot.strftime("%Y%m%dT%H%M%SZ")
                folder.mkdir(parents=True)
                (folder / name).write_bytes(b"unchanged")
                with (patch("app.report_scheduler.engine") as engine,
                      patch("app.report_scheduler._read_full_job") as read,
                      patch("app.report_scheduler._attempt_report_run") as run,
                      patch("app.report_scheduler.send_subscribed_reports") as mail):
                    connection = engine.begin.return_value.__enter__.return_value
                    connection.execute.return_value.scalar_one_or_none.return_value = 60
                    _run_scheduled_job(settings, 60, slot, slot)
                    self.assertEqual(connection.execute.call_count, 1)
                    read.assert_not_called()
                    run.assert_not_called()
                    mail.assert_not_called()
                self.assertEqual((folder / name).read_bytes(), b"unchanged")

    def test_attachment_names_mime_and_bytes_with_smtp_mocked(self):
        # Synthetic Settings only: the project's .env stays MAIL_ENABLED=false.
        settings = Settings(_env_file=None, mail_enabled=True, scheduler_enabled=False,
                            mail_username="sender@example.invalid", mail_password="fixture",
                            mail_from_address="sender@example.invalid")
        for file_format, delimiter, extension in FORMATS:
            with self.subTest(file_format=file_format), patch("app.report_mail.open_smtp") as smtp:
                reports = build_report_files(sample_job(file_format), source_csv(), delimiter=delimiter)
                send_report_email(settings, {"qa@example.invalid": reports}, 60)
                message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
                for attachment, report in zip(message.iter_attachments(), reports, strict=True):
                    self.assertEqual(attachment.get_filename(), report.file_name)
                    self.assertTrue(attachment.get_filename().endswith(extension))
                    self.assertEqual(attachment.get_payload(decode=True), report.csv.encode("utf-8"))
                    self.assertEqual(attachment.get_content_type(), {
                        ".csv": "text/csv", ".txt": "text/plain", ".tsv": "text/tab-separated-values",
                    }[extension])
        with patch("app.report_mail.open_smtp") as smtp:
            disabled = settings.model_copy(update={"mail_enabled": False})
            self.assertEqual(send_report_email(disabled, {"qa@example.invalid": reports}, 60), 0)
            smtp.assert_not_called()

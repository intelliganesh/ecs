import csv
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, build_procedure_report_files
from app.retirement_results import InvalidRun
from app.routers.retirement_builder import RetirementBuilderJob


FORMATS = (("CSV", ",", ".csv"), ("PIPE", "|", ".txt"), ("SEMICOLON", ";", ".txt"),
           ("TAB", "\t", ".tsv"), ("TILDE", "~", ".txt"), ("FIXED", " ", ".txt"))
HEADERS = ["Employee ID", "FIRST_NAME", "MI", "LAST_NAME", "PERIOD GROSS", "YTD GROSS"]
SOURCES = ["employeeid", "firstname", "middle", "lastname", "periodgross", "ytdgross"]
ALIASES = ["ExistingEmployee", "ExistingFirst", "ExistingMiddle", "ExistingLast", "ExistingGross", "ExistingYtd"]
METADATA = ("valid_flag", "retnum", "sort1")


def fixture(file_format="CSV", name_format="FILENAME_CLIENT_PAYDAY", *, with_h=True):
    mapping_order = [0, 2, 3, 4, 5, 1]  # Intentionally differs from D SELECT order.
    job = RetirementBuilderJob.model_validate({
        "id": 60, "general": {"fileName": "Synthetic", "fileFormat": file_format,
                                "outputFileNameFormat": name_format},
        "mapping": {"includeHeader": True, "rows": [
            {"field": HEADERS[index], "mappingColumn": SOURCES[index], "recordType": "D",
             "colSeqNo": position, "length": "24" if file_format == "FIXED" else "0",
             "format": "######.##" if index >= 4 else "LA"}
            for position, index in enumerate(mapping_order, start=1)
        ]},
        "queryConfiguration": [
            *([{"recttype": "H", "query": "SELECT valid_flag, retnum, paydate AS sort1, 'STALE'"}] if with_h else []),
            {"recttype": "D", "query": "SELECT valid_flag, retnum, paydate AS sort1, " + ", ".join(
                f'{source} AS "{alias}"' for source, alias in zip(SOURCES, ALIASES, strict=True))},
            {"recttype": "T", "query": "SELECT DISTINCT valid_flag, retnum, '01/01/1900' AS sort1"},
        ],
    })
    sets = []
    if with_h:
        # A stale H can have a different count/order and repeated rows. It must
        # not control the automatic file header or field formatting.
        sets.append(ProcedureResultSet((*METADATA, ""), (("1", "000204", "2026-10-15", "STALE"),) * 2))
    sets.append(ProcedureResultSet((*METADATA, *ALIASES), tuple(
        ("1", client, payday, "ID1", "Alex", "Q", "Sample", "1922.5", "63681.39")
        for client, payday in (("000204", "2026-10-15"), ("000719", "2026-10-16"))
    )))
    sets.append(ProcedureResultSet(METADATA, (("1", "000204", "1900-01-01"),)))
    return job, ProcedureSource(tuple(sets))


def build(job, source, delimiter=",", mode="DETAIL_ALIGNED"):
    with patch("app.retirement_procedure.get_settings", return_value=Settings(
        _env_file=None, retirement_header_source=mode, mail_enabled=False, scheduler_enabled=False,
    )):
        return build_procedure_report_files(job, source, delimiter)


class DetailAlignedHeaderTests(TestCase):
    def test_actual_detail_order_drives_header_and_formatting_in_all_formats_and_names(self):
        names = ("FILENAME", "CLIENT", "PAYDAY", "FILENAME_CLIENT", "FILENAME_PAYDAY", "CLIENT_PAYDAY", "FILENAME_CLIENT_PAYDAY")
        for file_format, delimiter, extension in FORMATS:
            for name_format in names:
                with self.subTest(file_format=file_format, name_format=name_format):
                    job, source = fixture(file_format, name_format)
                    before, original = job.model_dump(), source
                    reports = build(job, source, delimiter)
                    self.assertEqual(len(reports), 1 if name_format == "FILENAME" else 2)
                    for report in reports:
                        self.assertTrue(report.file_name.endswith(extension))
                        self.assertEqual([row.record_type for row in report.rows].count("H"), 1)
                        if file_format == "FIXED":
                            rows = [[line[offset:offset + 24].rstrip() for offset in range(0, 144, 24)]
                                    for line in report.csv.splitlines()]
                            self.assertTrue(all(len(line) == 144 for line in report.csv.splitlines()))
                        else:
                            rows = list(csv.reader(StringIO(report.csv), delimiter=delimiter))
                        self.assertEqual(rows[0], HEADERS)
                        self.assertTrue(all(row == ["ID1", "Alex", "Q", "Sample", "1922.50", "63681.39"] for row in rows[1:]))
                    self.assertEqual(job.model_dump(), before)
                    self.assertEqual(source, original)

    def test_no_saved_h_still_gets_one_header_from_detail(self):
        job, source = fixture(with_h=False)
        report, = build(job.model_copy(update={"general": job.general.model_copy(update={"outputFileNameFormat": "FILENAME"})}), source)
        self.assertEqual(list(csv.reader(StringIO(report.csv)))[0], HEADERS)
        self.assertEqual([row.record_type for row in report.rows], ["H", "D", "D"])

    def test_unchecked_and_switch_back_keep_the_saved_header(self):
        for checked, mode in ((False, "DETAIL_ALIGNED"), (True, "SAVED_H")):
            with self.subTest(checked=checked, mode=mode):
                job, source = fixture(name_format="FILENAME")
                job.mapping.includeHeader = checked
                report, = build(job, source, mode=mode)
                self.assertEqual(list(csv.reader(StringIO(report.csv)))[:2], [["STALE"], ["STALE"]])

    def test_unchecked_without_h_does_not_invent_header(self):
        job, source = fixture(with_h=False, name_format="FILENAME")
        job.mapping.includeHeader = False
        report, = build(job, source)
        self.assertEqual([row.record_type for row in report.rows], ["D", "D"])

    def test_unnamed_columns_require_confirmed_expressions_and_ambiguous_sources_fail(self):
        job, source = fixture(name_format="FILENAME", with_h=False)
        detail = source.result_sets[0]
        job.queryConfiguration[0].query = "SELECT valid_flag,retnum,paydate AS sort1," + ",".join(SOURCES)
        unnamed = ProcedureSource((ProcedureResultSet((*METADATA, *[""] * 6), detail.rows), source.result_sets[1]))
        report, = build(job, unnamed)
        self.assertEqual(list(csv.reader(StringIO(report.csv)))[0], HEADERS)
        job.queryConfiguration[0].query = "SELECT unsupported"
        with self.assertRaisesRegex(InvalidRun, "unambiguously"):
            build(job, unnamed)
        job.queryConfiguration[0].query = "SELECT valid_flag,retnum,paydate AS sort1," + ",".join(["employeeid"] * 6)
        with self.assertRaisesRegex(InvalidRun, "unambiguously"):
            build(job, unnamed)

    def test_conflicting_metadata_and_query_aliases_are_rejected(self):
        job, source = fixture(with_h=False)
        detail = source.result_sets[0]
        conflicting = ProcedureSource((ProcedureResultSet((*METADATA, *reversed(ALIASES)), detail.rows), source.result_sets[1]))
        with self.assertRaisesRegex(InvalidRun, "disagree"):
            build(job, conflicting)

    def test_multiple_datasets_use_one_header_and_keep_detail_and_trailer_order(self):
        job = RetirementBuilderJob.model_validate({
            "id": 60, "general": {"fileName": "Datasets", "fileFormat": "CSV"},
            "mapping": {"includeHeader": True, "rows": [
                {"field": "Amount", "mappingColumn": "amount", "recordType": "D", "dataSetNo": dataset,
                 "format": "######.##"} for dataset in (2, 1)
            ]},
            "queryConfiguration": [
                {"recttype": "D", "query": "SELECT valid_flag,retnum,paydate AS sort1,amount"},
                {"recttype": "D", "query": "SELECT valid_flag,retnum,paydate AS sort1,amount"},
                {"recttype": "T", "query": "SELECT valid_flag,retnum,paydate AS sort1,'END'"},
            ],
        })
        source = ProcedureSource((
            ProcedureResultSet((*METADATA, "amount"), (("1", "000204", "2026-10-15", "2.5"),)),
            ProcedureResultSet((*METADATA, "amount"), (("1", "000204", "2026-10-15", "1"),)),
            ProcedureResultSet((*METADATA, ""), (("1", "000204", "1900-01-01", "END"),)),
        ))
        report, = build(job, source)
        self.assertEqual(report.csv, "Amount\r\n2.50\r\n1.00\r\nEND\r\n")
        self.assertEqual([row.record_type for row in report.rows], ["H", "D", "D", "T"])
        job.mapping.rows[0].field = "Different Header"
        with self.assertRaisesRegex(InvalidRun, "same confirmed automatic header"):
            build(job, source)

    def test_quoted_identifiers_and_generated_format_expressions_are_confirmed_without_alias_guesses(self):
        job = RetirementBuilderJob.model_validate({
            "id": 60, "general": {"fileName": "Quoted", "fileFormat": "CSV"},
            "mapping": {"includeHeader": True, "rows": [
                {"field": "Name", "mappingColumn": 'source]name', "recordType": "D"},
                {"field": "Amount", "mappingColumn": "amount", "format": "######.##", "recordType": "D"},
            ]},
            "queryConfiguration": [{"recttype": "D", "query": (
                "SELECT valid_flag, retnum, paydate AS sort1, "
                "FORMAT(ROUND(CONVERT(decimal(38,18), [amount]), 2), '0.00', 'en-US'), "
                '[source]]name] AS "Confirmed, Name"'
            )}],
        })
        source = ProcedureSource((ProcedureResultSet((*METADATA, "", "Confirmed, Name"),
                                                    (("1", "000204", "2026-10-15", "0.00", "Alex"),)),))
        report, = build(job, source)
        self.assertEqual(report.csv, "Amount,Name\r\n0.00,Alex\r\n")

    def test_metadata_alone_can_confirm_a_complex_query_but_conflicting_evidence_fails(self):
        job, source = fixture(name_format="FILENAME", with_h=False)
        job.queryConfiguration[0].query = "/* existing complex SQL */ SELECT opaque"
        detail = source.result_sets[0]
        identified = ProcedureSource((ProcedureResultSet((*METADATA, *HEADERS), detail.rows), source.result_sets[1]))
        report, = build(job, identified)
        self.assertEqual(list(csv.reader(StringIO(report.csv)))[0], HEADERS)
        job.queryConfiguration[0].query = "SELECT valid_flag,retnum,paydate AS sort1," + ",".join(reversed(SOURCES))
        with self.assertRaisesRegex(InvalidRun, "unambiguously"):
            build(job, identified)

    def test_fixed_positions_are_not_silently_rewritten_to_accommodate_query_order(self):
        job, source = fixture("FIXED")
        for index, row in enumerate(job.mapping.rows):
            row.startPosition = str(index * 24)
        with self.assertRaisesRegex(InvalidRun, "overlaps|out of order"):
            build(job, source, " ")

    def test_default_literals_and_quoted_labels_follow_the_correct_projection(self):
        job = RetirementBuilderJob.model_validate({
            "id": 60, "general": {"fileName": "Constants", "fileFormat": "CSV"},
            "mapping": {"includeHeader": True, "rows": [
                {"field": 'Label, "quoted"', "mappingColumn": "Default", "defaultValue": "x,y", "recordType": "D"},
                {"field": "Other", "mappingColumn": "Default", "defaultValue": "O'Brien", "recordType": "D"},
            ]},
            "queryConfiguration": [{"recttype": "D", "query": "SELECT valid_flag,retnum,paydate AS sort1,'O''Brien','x,y'"}],
        })
        source = ProcedureSource((ProcedureResultSet((*METADATA, "", ""), (("1", "000204", "2026-10-15", "O'Brien", "x,y"),)),))
        report, = build(job, source)
        self.assertEqual(list(csv.reader(StringIO(report.csv))), [["Other", 'Label, "quoted"'], ["O'Brien", "x,y"]])

    def test_zero_flag_or_no_details_remain_no_data(self):
        job, source = fixture()
        empty = ProcedureSource(tuple(ProcedureResultSet(s.columns, ()) for s in source.result_sets))
        self.assertEqual(build(job, empty), [])
        flagged = ProcedureSource(tuple(ProcedureResultSet(s.columns, tuple(("0", *row[1:]) for row in s.rows)) for s in source.result_sets))
        self.assertEqual(build(job, flagged), [])

    def test_invalid_switch_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, retirement_header_source="UNKNOWN")

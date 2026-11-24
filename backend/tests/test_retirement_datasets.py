"""Synthetic dataset/query/result fixtures only: never run an SP, DB job or SMTP."""

import csv
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.core.config import Settings
from app.retirement_datasets import expand_legacy_datasets, split_dataset_query, tag_dataset_query
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, build_procedure_report_files
from app.retirement_projection import replace_detail_projection
from app.retirement_query_builder import export_record_queries, ordered_mappings
from app.retirement_results import InvalidRun
from app.payroll_source import load_payroll_source
from app.routers import retirement_builder as rb


FORMATS = (("CSV", ",", ".csv"), ("PIPE", "|", ".txt"), ("SEMICOLON", ";", ".txt"),
           ("TAB", "\t", ".tsv"), ("TILDE", "~", ".txt"), ("FIXED", " ", ".txt"))
NAMES = ("FILENAME", "CLIENT", "PAYDAY", "FILENAME_CLIENT", "FILENAME_PAYDAY", "CLIENT_PAYDAY", "FILENAME_CLIENT_PAYDAY")
CONTROL = ("valid_flag", "retnum", "sort1")


def dataset_job(file_format="CSV", name_format="CLIENT", *, tagged=True, header=True):
    queries = ["SELECT valid_flag, retnum, paydate AS sort1, paydate AS SavedDate, amount AS SavedAmount",
               "SELECT valid_flag, retnum, paydate AS sort1, category AS CategoryAlias"]
    rows = [{"field": "Pay Date", "mappingColumn": "paydate", "recordType": "D", "format": "MM/DD/YYYY",
             "dataSetNo": 1, "colSeqNo": 1, "length": "10", "startPosition": "0"},
            {"field": "Amount", "mappingColumn": "amount", "recordType": "D", "format": "######.##",
             "dataSetNo": 1, "colSeqNo": 2, "length": "12", "startPosition": "10"},
            {"field": "Category", "mappingColumn": "category", "recordType": "D",
             "dataSetNo": 2, "colSeqNo": 1, "length": "20", "startPosition": "0"},
            {"field": "Total", "mappingColumn": "total", "recordType": "T", "format": "######.##",
             "dataSetNo": 1, "colSeqNo": 3, "length": "12", "startPosition": "0"}]
    return rb.RetirementBuilderJob.model_validate({
        "id": 60, "general": {"fileName": "Payroll", "fileFormat": file_format, "outputFileNameFormat": name_format},
        "mapping": {"includeHeader": header, "rows": rows},
        "queryConfiguration": [{"recttype": "H", "query": "SELECT top 1 valid_flag,retnum,paydate AS sort1,'old','header'"},
                               *[{"recttype": "D", "query": tag_dataset_query(query, i) if tagged else query}
                                 for i, query in enumerate(queries, 1)],
                               {"recttype": "T", "query": "SELECT valid_flag,retnum,paydate AS sort1,total"}],
    })


def dataset_source(*, tagged=True, empty_second=False, reverse=True):
    first = ProcedureResultSet(CONTROL + (("__ecs_dataset_1",) if tagged else ()) + ("SavedDate", "SavedAmount"), tuple(
        ("1", client, "2026-10-15") + (("1",) if tagged else ()) + ("2026-10-15", amount)
        for client, amount in (("000204", "0"), ("000719", "25.5"))))
    second = ProcedureResultSet(CONTROL + (("__ecs_dataset_2",) if tagged else ()) + ("CategoryAlias",), () if empty_second else tuple(
        ("1", client, "2026-10-15") + (("2",) if tagged else ()) + (value,)
        for client, value in (("000204", 'Team, "A"'), ("000719", "Équipe B"))))
    return ProcedureSource((ProcedureResultSet(CONTROL + ("", ""), (("1", "000204", "2026-10-15", "old", "header"),)),
                            *((second, first) if reverse else (first, second)),
                            ProcedureResultSet(CONTROL + ("total",), (("1", "000204", "1900-01-01", ""),
                                                                   ("1", "000719", "1900-01-01", "100")))))


class DatasetExportTests(TestCase):
    def test_trailers_follow_only_their_dataset_in_all_formats_and_filename_modes(self):
        for file_format, delimiter, extension in FORMATS:
            for naming in NAMES:
                for targets in ((), (1,), (2,), (1, 2)):
                    with self.subTest(file_format=file_format, naming=naming, targets=targets):
                        job = dataset_job(file_format, naming)
                        job.mapping.rows = [row for row in job.mapping.rows if row.recordType != "T"] + [
                            rb.MappingRow(field=f"Trailer {dataset}", mappingColumn=f"end{dataset}", recordType="T",
                                          dataSetNo=dataset, colSeqNo=9, length="12", startPosition="0")
                            for dataset in targets]
                        # One SP T row carries all configured trailer columns, including unformatted text.
                        job.queryConfiguration[-1].query = "SELECT valid_flag,retnum,paydate AS sort1" + "".join(
                            f",end{dataset}" for dataset in targets)
                        source = dataset_source()
                        trailers = ProcedureResultSet(CONTROL + tuple(f"end{dataset}" for dataset in targets), tuple(
                            ("1", client, "1900-01-01", *(f"T{dataset}-end" for dataset in targets))
                            for client in ("000204", "000719")))
                        source = ProcedureSource((*source.result_sets[:-1], trailers))
                        before = job.model_dump()
                        for report in build_procedure_report_files(job, source, delimiter):
                            clients = len(report.client_ids)
                            expected = ["H", *["D"] * clients, *(["T"] * clients if 1 in targets else []),
                                        "H", *["D"] * clients, *(["T"] * clients if 2 in targets else [])]
                            self.assertEqual([r.record_type for r in report.rows], expected)
                            totals = [next(iter(row.values.values())).strip() for row in report.rows if row.record_type == "T"]
                            self.assertEqual(totals, [f"T{dataset}-end" for dataset in targets for _ in range(clients)])
                            self.assertTrue(report.file_name.endswith(extension))
                            if file_format == "FIXED":
                                self.assertEqual([row for row in report.excel_rows if row],
                                                 [list(row.values.values()) for row in report.rows])
                            else:
                                parsed = list(csv.reader(StringIO(report.csv), delimiter=delimiter))
                                self.assertEqual([row for row in parsed if row],
                                                 [list(row.values.values()) for row in report.rows])
                        self.assertEqual(job.model_dump(), before)

    def test_empty_dataset_does_not_emit_its_trailer(self):
        job = dataset_job()
        job.mapping.rows[-1].dataSetNo = 2
        reports = build_procedure_report_files(job, dataset_source(empty_second=True), ",")
        self.assertTrue(reports)
        self.assertTrue(all(row.record_type != "T" for report in reports for row in report.rows))

    def test_dataset_trailer_order_also_applies_with_saved_headers(self):
        reports = build_procedure_report_files(dataset_job(header=False), dataset_source(), ",")
        for report in reports:
            # The saved H fixture belongs only to client 204; do not invent one for 719.
            header = ["H"] if "000204" in report.client_ids else []
            self.assertEqual([row.record_type for row in report.rows], [*header, "D", "T", "D"])

    def test_trailer_with_no_mapping_cannot_be_assigned_by_guessing(self):
        job = dataset_job()
        job.mapping.rows = [row for row in job.mapping.rows if row.recordType != "T"]
        with self.assertRaisesRegex(InvalidRun, "export columns"):
            build_procedure_report_files(job, dataset_source(), ",")

    def test_trailer_dates_must_belong_to_the_associated_dataset(self):
        job = dataset_job()
        source = dataset_source()
        # Dataset 2 alone has this payday; its presence must not admit a Dataset 1 trailer.
        second = source.result_sets[1]
        second = ProcedureResultSet(second.columns, tuple((*row[:2], "2026-10-16", *row[3:]) for row in second.rows))
        trailer = source.result_sets[-1]
        trailer = ProcedureResultSet(trailer.columns, tuple((*row[:2], "2026-10-16", *row[3:]) for row in trailer.rows))
        source = ProcedureSource((source.result_sets[0], second, source.result_sets[2], trailer))
        reports = build_procedure_report_files(job, source, ",")
        self.assertTrue(all(row.record_type != "T" for report in reports for row in report.rows))

    def test_all_six_formats_and_seven_names_keep_client_groups_and_dynamic_headers(self):
        for file_format, delimiter, extension in FORMATS:
            for naming in NAMES:
                with self.subTest(file_format=file_format, naming=naming):
                    reports = build_procedure_report_files(dataset_job(file_format, naming), dataset_source(), delimiter)
                    self.assertEqual(len(reports), 2 if "CLIENT" in naming else 1)
                    for report in reports:
                        self.assertTrue(report.file_name.endswith(extension))
                        self.assertNotIn("__ecs_dataset", report.csv)
                        headers = [list(row.values.values()) for row in report.rows if row.record_type == "H"]
                        self.assertEqual([[v.strip() for v in row] for row in headers], [["Pay Date", "Amount"], ["Category"]])
                        records = [row for row in report.rows if row.record_type == "D"]
                        self.assertEqual(len(records), 2 if "CLIENT" in naming else 4)
                        values = [[v.strip() for v in row.values.values()] for row in records]
                        if "000204" in report.file_name:
                            self.assertEqual(values, [["10/15/2026", "0.00"], ['Team, "A"']])
                        if "000719" in report.file_name:
                            self.assertEqual(values, [["10/15/2026", "25.50"], ["Équipe B"]])
                        self.assertIn("\r\n\r\n", report.csv)
                        kinds = [row.record_type for row in report.rows]
                        self.assertLess(kinds.index("T"), len(kinds) - 1)
                        self.assertEqual(kinds[-1], "D")
                        if file_format == "FIXED":
                            self.assertEqual(len(report.csv.splitlines()[0]), 22)
                        else:
                            parsed = list(csv.reader(StringIO(report.csv), delimiter=delimiter, strict=True))
                            self.assertEqual(parsed[0], ["Pay Date", "Amount"])
                            self.assertIn(["Category"], parsed)
                            self.assertIn([], parsed)

    def test_empty_dataset_has_identity_but_no_phantom_header_or_separator(self):
        reports = build_procedure_report_files(dataset_job(), dataset_source(empty_second=True), ",")
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertNotIn("Category", report.csv)
            self.assertNotIn("\r\n\r\n", report.csv)
            self.assertEqual(sum(row.record_type == "D" for row in report.rows), 1)

    def test_legacy_queries_match_actual_columns_instead_of_result_position(self):
        report_job = dataset_job(tagged=False)
        for reverse in (True, False):
            reports = build_procedure_report_files(report_job, dataset_source(tagged=False, reverse=reverse), ",")
            self.assertEqual(reports[0].csv, 'Pay Date,Amount\r\n10/15/2026,0.00\r\n""\r\n\r\nCategory\r\n"Team, ""A"""\r\n')

    def test_unmapped_legacy_dataset_is_derived_from_any_explicit_source_names(self):
        report_job = dataset_job(tagged=False)
        report_job.mapping.rows = [row for row in report_job.mapping.rows if row.dataSetNo != 2]
        expanded = expand_legacy_datasets(report_job)
        derived = [row for row in expanded.mapping.rows if row.dataSetNo == 2]
        self.assertEqual([(row.field, row.mappingColumn) for row in derived], [("CATEGORYALIAS", "category")])
        self.assertEqual(len(report_job.mapping.rows), 3)  # Input snapshot not mutated.
        reports = build_procedure_report_files(report_job, dataset_source(tagged=False), ",")
        self.assertIn("CATEGORYALIAS", reports[0].csv)

    def test_ambiguous_legacy_results_are_rejected_without_position_guesses(self):
        report_job = dataset_job(tagged=False)
        report_job.queryConfiguration[2].query = "SELECT valid_flag,retnum,paydate AS sort1,amount AS SavedAmount"
        report_job.mapping.rows[2].mappingColumn = "amount"
        with self.assertRaises(InvalidRun):
            build_procedure_report_files(report_job, dataset_source(tagged=False), ",")

    def test_missing_duplicate_and_wrong_marker_values_fail(self):
        source = dataset_source()
        for changed in (
            ProcedureResultSet(CONTROL + ("__ecs_dataset_99", "CategoryAlias"), source.result_sets[1].rows),
            source.result_sets[2],
            ProcedureResultSet(source.result_sets[1].columns, (("1", "000204", "2026-10-15", "9", "X"),)),
        ):
            with self.subTest(columns=changed.columns), self.assertRaises(InvalidRun):
                build_procedure_report_files(dataset_job(), ProcedureSource((source.result_sets[0], changed, *source.result_sets[2:])), ",")

    def test_unchecked_header_uses_configured_h_once_and_keeps_sections(self):
        reports = build_procedure_report_files(dataset_job(header=False), dataset_source(), ",")
        self.assertEqual(reports[0].csv.splitlines()[0], "old,header")
        self.assertEqual(sum(row.record_type == "H" for row in reports[0].rows), 1)
        self.assertNotIn("Category\r\n", reports[0].csv)

    def test_store_results_is_blocked_before_any_cursor_or_procedure_call(self):
        report_job = dataset_job()
        report_job.general.storeResultsToTable = True
        connection = Mock()
        with self.assertRaisesRegex(InvalidRun, "Store Results"):
            load_payroll_source(connection, report_job)
        connection.connection.cursor.assert_not_called()

    def test_same_returned_schema_uses_tags_not_aliases_or_result_order(self):
        report_job = dataset_job()
        details = [row for row in report_job.mapping.rows if row.recordType == "D"]
        report_job.mapping.rows = [row.model_copy(update={"field": f"Section {i}", "mappingColumn": "amount",
                                                        "format": "######.##", "dataSetNo": i, "colSeqNo": 1})
                                  for i, row in enumerate(details[:2], 1)]
        report_job.queryConfiguration[-1].query = "SELECT valid_flag,retnum,'01/01/1900' AS sort1"
        for i, query in enumerate(report_job.queryConfiguration[1:3], 1):
            query.query = tag_dataset_query("SELECT valid_flag,retnum,paydate AS sort1,amount AS SameAlias", i)
        source = ProcedureSource((dataset_source().result_sets[0],
            ProcedureResultSet(CONTROL + ("__ecs_dataset_2", "SameAlias"), (("1", "000204", "2026-10-15", "2", "20"),)),
            ProcedureResultSet(CONTROL + ("__ecs_dataset_1", "SameAlias"), (("1", "000204", "2026-10-15", "1", "10"),)),
            ProcedureResultSet(CONTROL, (("1", "000204", "1900-01-01"),))))
        report, = build_procedure_report_files(report_job, source, ",")
        self.assertTrue(report.csv.startswith('Section 1\r\n10.00\r\n\r\nSection 2\r\n20.00\r\n'))

    def test_same_legacy_schema_with_different_expressions_fails_safely(self):
        report_job = dataset_job(tagged=False)
        report_job.mapping.rows = [rb.MappingRow(field='First', mappingColumn='alpha', recordType='D', dataSetNo=1),
                                  rb.MappingRow(field='Second', mappingColumn='beta', recordType='D', dataSetNo=2)]
        report_job.queryConfiguration[1].query = 'SELECT valid_flag,retnum,paydate AS sort1,alpha AS Shared'
        report_job.queryConfiguration[2].query = 'SELECT valid_flag,retnum,paydate AS sort1,beta AS Shared'
        result = ProcedureResultSet(CONTROL + ('Shared',), (('1', '000204', '2026-10-15', 'value'),))
        source = ProcedureSource((dataset_source().result_sets[0], result, result, dataset_source().result_sets[-1]))
        with self.assertRaisesRegex(InvalidRun, 'uniquely identify'):
            build_procedure_report_files(report_job, source, ',')

    def test_saved_h_mode_is_rejected_before_procedure_execution(self):
        connection = Mock()
        settings = Settings(_env_file=None, retirement_header_source='SAVED_H', mail_enabled=False, scheduler_enabled=False)
        with patch('app.payroll_source.get_settings', return_value=settings), self.assertRaisesRegex(InvalidRun, 'DETAIL_ALIGNED'):
            load_payroll_source(connection, dataset_job())
        connection.connection.cursor.assert_not_called()


class DatasetPersistenceTests(TestCase):
    def test_generated_queries_are_h_d_d_t_and_use_existing_query_31(self):
        report_job = dataset_job()
        payload = rb.RetirementBuilderJobInput.model_validate(report_job.model_dump(exclude={"id"}))
        payload.fileSettings.sortingOrder = [rb.SortingOrderRow(orderBy="1", mappingColumn="paydate")]
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 60, payload, original_mappings=payload.mapping.rows)
        saved = [call.args[1] for call in connection.execute.call_args_list if len(call.args) == 2 and "recttype" in call.args[1]]
        self.assertEqual([row["recttype"] for row in saved], ["H", "D", "D", "T"])
        self.assertEqual([split_dataset_query(row["Query"])[0] for row in saved[1:3]], [1, 2])
        self.assertTrue(all(row["jobid"] == 60 for row in saved))
        self.assertTrue(all(row["sortOrder"] == ", paydate" for row in saved if row["recttype"] == "D"))
        self.assertIn(" AS SavedDate", saved[1]["Query"])
        self.assertIn(" AS CategoryAlias", saved[2]["Query"])

    def test_add_and_remove_fields_preserve_existing_business_aliases(self):
        old = [rb.MappingRow(field="Old", mappingColumn="old_column", dataSetNo=1, colSeqNo=1)]
        added = rb.MappingRow(field="New", mappingColumn="new_column", dataSetNo=1, colSeqNo=2)
        query = "SELECT valid_flag,retnum,paydate AS sort1,old_column AS ConfirmedAlias"
        result = replace_detail_projection(query, old, old + [added], lambda row: '[' + row.mappingColumn + ']')
        self.assertIn("old_column AS ConfirmedAlias, [new_column]", result)
        removed = replace_detail_projection(result, old + [added], [added], lambda row: '[' + row.mappingColumn + ']')
        self.assertNotIn("ConfirmedAlias", removed)
        self.assertTrue(removed.endswith("[new_column]"))

    def test_store_results_save_validation_has_no_mutation_calls(self):
        report_job = dataset_job()
        report_job.general.storeResultsToTable = True
        payload = rb.RetirementBuilderJobInput.model_validate(report_job.model_dump(exclude={"id"}))
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        with self.assertRaises(HTTPException):
            rb._write_job_details(connection, 60, payload)
        self.assertTrue(all(str(call.args[0]).lstrip().upper().startswith("SELECT") for call in connection.execute.call_args_list))

    def test_marker_is_explicit_and_removable_including_quoted_commas(self):
        query = "SELECT valid_flag,retnum,paydate AS sort1,'a,b' AS ExistingAlias"
        tagged = tag_dataset_query(query, 8)
        self.assertEqual(split_dataset_query(tagged), (8, query))
        self.assertEqual(tag_dataset_query(tagged, 9).count("__ecs_dataset_"), 1)
        with self.assertRaises(InvalidRun):
            split_dataset_query(tagged.replace("8 AS", "9 AS"))

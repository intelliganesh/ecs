"""Save-to-export regressions with synthetic SP output and mocked persistence only."""

import csv
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock

from app.retirement_datasets import tag_dataset_query
from app.retirement_headers import aligned_detail_layout
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, build_procedure_report_files
from app.retirement_query_builder import _expression, export_record_queries, ordered_mappings
from app.retirement_results import InvalidRun
from app.routers import retirement_builder as rb


CONTROL = ("valid_flag", "retnum", "sort1")
FORMATS = (("CSV", ",", ".csv"), ("PIPE", "|", ".txt"), ("SEMICOLON", ";", ".txt"),
           ("TAB", "\t", ".tsv"), ("TILDE", "~", ".txt"), ("FIXED", " ", ".txt"))
NAMES = ("FILENAME", "CLIENT", "PAYDAY", "FILENAME_CLIENT", "FILENAME_PAYDAY", "CLIENT_PAYDAY", "FILENAME_CLIENT_PAYDAY")


def saved_job(file_format="CSV", naming="CLIENT", padding="LA", width="0", alias=""):
    region = rb.MappingRow(field="Region", mappingColumn="region_name", recordType="D", format=padding,
                           length=width, startPosition="0", dataSetNo=2, colSeqNo=1)
    return rb.RetirementBuilderJob.model_validate({
        "id": 60, "general": {"fileName": "Synthetic", "fileFormat": file_format, "outputFileNameFormat": naming},
        "mapping": {"includeHeader": True, "rows": [
            {"field": "Amount", "mappingColumn": "amount", "recordType": "D", "format": "######.##",
             "length": "12", "startPosition": "0", "dataSetNo": 1, "colSeqNo": 1}, region.model_dump(),
        ]},
        "queryConfiguration": [
            {"recttype": "D", "query": tag_dataset_query("SELECT valid_flag,retnum,paydate AS sort1,amount AS AmountAlias", 1)},
            {"recttype": "D", "query": tag_dataset_query(
                "SELECT valid_flag,retnum,paydate AS sort1," + _expression(region)[0] + alias, 2)},
        ],
    })


def edited_payload(original, **patch):
    payload = rb.RetirementBuilderJobInput.model_validate(original.model_dump(exclude={"id"}))
    payload.mapping.rows[1] = payload.mapping.rows[1].model_copy(update=patch)
    return payload


def regenerate(original, payload):
    rows = ordered_mappings(payload.mapping.rows)
    return [rb.QueryConfigurationRow(**row) for row in export_record_queries(
        payload, rows, payload.queryConfiguration, original_mappings=ordered_mappings(original.mapping.rows))]


class PresentationEditTests(TestCase):
    def test_padding_edit_saves_matching_projection_and_length_through_existing_persistence(self):
        for alias in ("", ' AS "Existing Region"'):
            with self.subTest(alias=alias):
                original = saved_job(alias=alias)
                payload = edited_payload(original, length="1000")
                connection = Mock()
                connection.execute.return_value.mappings.return_value = []
                rb._write_job_details(connection, 60, payload, original_mappings=original.mapping.rows)
                parameters = [call.args[1] for call in connection.execute.call_args_list if len(call.args) == 2]
                detail = next(row for row in parameters if row.get("recttype") == "D" and "__ecs_dataset_2" in row["Query"])
                self.assertTrue(detail["Query"].endswith(_expression(payload.mapping.rows[1])[0] + alias))
                self.assertIn("< 1000 THEN 1000 -", detail["Query"])
                self.assertTrue(any(row.get("datasetNo") == 2 and row.get("field_len") == 1000 for row in parameters))
                self.assertIn(" AS AmountAlias", next(row["Query"] for row in parameters
                                                       if row.get("recttype") == "D" and "__ecs_dataset_1" in row["Query"]))

    def test_saved_padding_edit_exports_in_all_formats_and_names_for_two_clients_and_datasets(self):
        for file_format, delimiter, extension in FORMATS:
            for naming in NAMES:
                for padding in ("LA", "RA"):
                    with self.subTest(file_format=file_format, naming=naming, padding=padding):
                        original = saved_job(file_format, naming, padding)
                        payload = edited_payload(original, length="1000")
                        queries = regenerate(original, payload)
                        export_job = rb.RetirementBuilderJob(id=60, **payload.model_dump(exclude={"queryConfiguration"}),
                                                           queryConfiguration=queries)
                        source = ProcedureSource((
                            ProcedureResultSet((*CONTROL, ""), (("1", "000204", "2026-11-12", "Amount"),)),
                            # SP result order is reversed; the generated padding expression has no invented alias.
                            ProcedureResultSet((*CONTROL, "__ecs_dataset_2", ""), tuple(
                                ("1", client, "2026-11-12", "2", "East".rjust(1000) if padding == "RA" else "East".ljust(1000))
                                for client in ("000204", "000719"))),
                            ProcedureResultSet((*CONTROL, "__ecs_dataset_1", "AmountAlias"), tuple(
                                ("1", client, "2026-11-12", "1", "0") for client in ("000204", "000719"))),
                            ProcedureResultSet(CONTROL, (("1", "000204", "1900-01-01"),)),
                        ))
                        reports = build_procedure_report_files(export_job, source, delimiter)
                        self.assertEqual(len(reports), 2 if "CLIENT" in naming else 1)
                        for report in reports:
                            self.assertTrue(report.file_name.endswith(extension))
                            self.assertNotIn("__ecs_dataset", report.csv)
                            detail_values = [list(row.values.values())[0] for row in report.rows if row.record_type == "D"]
                            regions = [value for value in detail_values if "East" in value]
                            self.assertTrue(regions)
                            self.assertTrue(all(len(value) == 1000 for value in regions))
                            self.assertTrue(all(value.endswith("East") if padding == "RA" else value.startswith("East")
                                                for value in regions))
                            self.assertIn("0.00", [value.strip() for value in detail_values])
                            if file_format != "FIXED":
                                parsed = list(csv.reader(StringIO(report.csv), delimiter=delimiter))
                                self.assertIn(["Region"], parsed)
                                self.assertTrue(all([value] in parsed for value in regions))

    def test_shrinking_padding_does_not_keep_sql_padding_from_old_width(self):
        original = saved_job(width="1000")
        payload = edited_payload(original, length="12")
        detail = next(row for row in regenerate(original, payload) if row.recttype == "D" and row.dataSetNo == 2)
        self.assertNotIn("< 1000", detail.query)
        self.assertIn("< 12 THEN 12 -", detail.query)

    def test_format_edits_refresh_only_confirmed_generated_expressions(self):
        cases = (("LA", "RA"), ("Uppercase", "Lowercase"), ("MM/DD/YYYY", "YYYY-MM-DD"),
                 ("######.##", "########.####"))
        for old_format, new_format in cases:
            with self.subTest(old=old_format, new=new_format):
                original = saved_job(padding=old_format, width="12", alias=" AS KeptAlias")
                payload = edited_payload(original, format=new_format)
                detail = next(row for row in regenerate(original, payload)
                              if row.recttype == "D" and row.dataSetNo == 2)
                self.assertTrue(detail.query.endswith(_expression(payload.mapping.rows[1])[0] + " AS KeptAlias"))

    def test_restoring_length_recreates_the_original_projection(self):
        original = saved_job()
        payload = edited_payload(original, length="1000")
        changed = rb.RetirementBuilderJob(id=60, **payload.model_dump(exclude={"queryConfiguration"}),
                                         queryConfiguration=regenerate(original, payload))
        restored = next(row for row in regenerate(changed, edited_payload(changed, length="0"))
                        if row.recttype == "D" and row.dataSetNo == 2)
        self.assertEqual(restored.query, original.queryConfiguration[1].query)

    def test_invalid_padding_still_fails_generation(self):
        original = saved_job()
        with self.assertRaisesRegex(InvalidRun, "padding length"):
            regenerate(original, edited_payload(original, length="1001"))

    def test_unchanged_and_custom_business_expressions_are_preserved(self):
        original = saved_job()
        payload = edited_payload(original)
        detail = next(row for row in regenerate(original, payload) if row.recttype == "D" and row.dataSetNo == 2)
        self.assertEqual(detail.query, original.queryConfiguration[1].query)
        for expression in ("COALESCE(region_name, 'Business fallback') AS KeptAlias",
                           "region_name + ' Fixed Business Suffix' AS KeptAlias"):
            original.queryConfiguration[1].query = tag_dataset_query("SELECT valid_flag,retnum,paydate AS sort1," + expression, 2)
            detail = next(row for row in regenerate(original, edited_payload(original, length="1000"))
                          if row.recttype == "D" and row.dataSetNo == 2)
            self.assertEqual(detail.query, original.queryConfiguration[1].query)

    def test_header_matching_still_rejects_ambiguous_sources(self):
        mapping = rb.MappingRow(field="Region", mappingColumn="region_name", format="LA", length="1000")
        with self.assertRaisesRegex(InvalidRun, "unambiguously"):
            aligned_detail_layout((*CONTROL, "region_name", "region_name"),
                                  [mapping, mapping.model_copy(update={"field": "Other"})],
                                  "SELECT valid_flag,retnum,paydate AS sort1,region_name,region_name")

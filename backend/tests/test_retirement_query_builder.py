from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.retirement_query_builder import export_record_queries, ordered_mappings
from app.retirement_results import InvalidRun
from app.routers import retirement_builder as rb


def job(rows, include_header=True, **general):
    return rb.RetirementBuilderJobInput.model_validate({
        "general": {"fileName": "Production fragment test", "fileFormat": "CSV", **general},
        "mapping": {"includeHeader": include_header, "rows": rows},
    })


def generate(payload, saved=()):
    rows = [row.model_copy(update={"recordType": row.recordType or "D"}) for row in payload.mapping.rows]
    return export_record_queries(payload, ordered_mappings(rows), list(saved))


class ExportQueryGenerationTests(TestCase):
    def test_generated_numeric_formats_use_required_decimal_places_in_all_record_types(self):
        payload = job([
            {"field": "Header", "mappingColumn": "amount", "format": "######.##", "recordType": "H"},
            {"field": "Detail", "mappingColumn": "amount", "format": "$######.##", "recordType": "D"},
            {"field": "Trailer", "mappingColumn": "amount", "format": "########", "recordType": "T"},
        ], include_header=False)
        header, detail, trailer = generate(payload)
        self.assertIn(", '0.00', 'en-US')", header["query"])
        self.assertIn(", '$0.00;-$0.00;$0.00', 'en-US')", detail["query"])
        self.assertIn(", '0', 'en-US')", trailer["query"])
        self.assertNotIn("0.##", header["query"] + detail["query"])

    def test_imported_detail_names_become_header_literals_in_dataset_sequence_order(self):
        payload = job([
            {"field": "FIRSTNAME", "mappingColumn": "firstname", "recordType": "D", "dataSetNo": 2, "colSeqNo": 2},
            {"field": "WORK PHONE", "mappingColumn": "workphone", "recordType": "D", "dataSetNo": 1, "colSeqNo": 2},
            {"field": "LASTNAME", "mappingColumn": "lastname", "recordType": "D", "dataSetNo": 2, "colSeqNo": 1},
            {"field": "PAYDATE", "mappingColumn": "paydate", "recordType": "D", "dataSetNo": 1, "colSeqNo": 1},
        ])
        queries = generate(payload)
        self.assertEqual([row["recttype"] for row in queries], ["H", "D", "T"])
        self.assertEqual(queries[0]["query"], "SELECT TOP 1 valid_flag, retnum, paydate AS sort1, 'PAYDATE', 'WORK PHONE', 'LASTNAME', 'FIRSTNAME'")
        self.assertEqual(queries[1]["query"], "SELECT valid_flag, retnum, paydate AS sort1, [paydate], [workphone], [lastname], [firstname]")
        self.assertEqual(queries[2]["query"], "SELECT DISTINCT valid_flag, retnum, '01/01/1900' AS sort1")
        self.assertTrue(all(" FROM " not in row["query"] for row in queries))

    def test_configured_h_and_t_use_defaults_formats_and_safe_identifiers_without_aliases(self):
        payload = job([
            {"field": "Detail", "mappingColumn": "lastname", "recordType": "D"},
            {"field": "Header constant", "mappingColumn": "Default", "defaultValue": "O'Brien", "recordType": "H"},
            {"field": "Header source", "mappingColumn": "name]; DROP TABLE x;--", "recordType": "H"},
            {"field": "Total", "mappingColumn": "file_total_401k", "format": "0.00 - Decimal", "recordType": "T"},
            {"field": "Label", "mappingColumn": "Default", "defaultValue": "trailer", "format": "Uppercase", "recordType": "T"},
        ], include_header=False)
        header, _, trailer = generate(payload)
        self.assertIn("'O''Brien', [name]]; DROP TABLE x;--]", header["query"])
        self.assertIn("FORMAT(ROUND(CONVERT(decimal(38,18), [file_total_401k]), 2), '0.00', 'en-US')", trailer["query"])
        self.assertTrue(trailer["query"].endswith(", 'TRAILER'"))
        self.assertNotIn(" AS [", header["query"] + trailer["query"])

    def test_header_checkbox_off_without_h_mapping_omits_h_and_retains_placeholder_t(self):
        queries = generate(job([{"field": "Surname", "mappingColumn": "lastname", "recordType": "D"}], include_header=False))
        self.assertEqual([row["recttype"] for row in queries], ["D", "T"])

    def test_header_names_escape_quotes_and_do_not_apply_detail_formats(self):
        queries = generate(job([{"field": "Employee's date", "mappingColumn": "paydate", "recordType": "D", "format": "MMDDYYYY"}]))
        self.assertTrue(queries[0]["query"].endswith("'Employee''s date'"))
        self.assertIn("REPLACE(CONVERT(varchar(10), CONVERT(date, [paydate]), 101), '/', '')", queries[1]["query"])

    def test_existing_detail_sql_and_aliases_are_preserved_and_identical_duplicates_collapse(self):
        original = rb.QueryConfigurationRow(recttype="D", query="SELECT valid_flag, retnum, paydate AS sort1, lastname AS ExistingAlias", conditions="where HasActivity = 1")
        queries = generate(job([{"field": "LASTNAME", "mappingColumn": "lastname", "recordType": "D"}]), [original, original])
        detail = queries[1]
        self.assertEqual(detail["query"], original.query)
        self.assertEqual(detail["conditions"], original.conditions)
        with self.assertRaisesRegex(InvalidRun, "Multiple distinct detail queries"):
            generate(job([{"field": "LASTNAME", "mappingColumn": "lastname", "recordType": "D"}]),
                     [original, original.model_copy(update={"query": "different SQL"})])

    def test_existing_detail_uses_edited_conditions_and_explicit_clear(self):
        original = rb.QueryConfigurationRow(
            recttype="D", query="SELECT valid_flag, retnum, paydate AS sort1, lastname AS ExistingAlias",
            conditions="WHERE [paydate] >= '2026-11-01'",
        )
        payload = job([{"field": "LASTNAME", "mappingColumn": "lastname", "recordType": "D"}])
        payload.fileSettings = rb.FileSettingsForm.model_validate({"conditionalStatements": [
            {"mappingColumn": "paydate", "condition": ">=", "value": "2026-11-12"},
            {"mappingColumn": "file_total_401k", "condition": ">", "value": "100.00"},
        ]})
        detail = generate(payload, [original])[1]
        self.assertEqual(detail["query"], original.query)
        self.assertEqual(detail["conditions"], "WHERE [paydate] >= '2026-11-12' AND [file_total_401k] > 100.00")
        payload.fileSettings = rb.FileSettingsForm.model_validate({"conditionalStatements": []})
        self.assertEqual(generate(payload, [original])[1]["conditions"], "")
        self.assertEqual(original.conditions, "WHERE [paydate] >= '2026-11-01'")

    def test_unknown_alias_and_format_behavior_is_rejected_before_persistence(self):
        with self.assertRaisesRegex(InvalidRun, "confirmed aliases"):
            generate(job([{"field": "Amount", "mappingColumn": "Default", "defaultValue": "1", "recordType": "D"}], storeResultsToTable=True))
        with self.assertRaisesRegex(InvalidRun, "must be confirmed"):
            generate(job([{"field": "Surname", "mappingColumn": "lastname", "format": "CUSTOM FORMAT", "recordType": "D"}]))
        with self.assertRaisesRegex(InvalidRun, "Detail mapping"):
            generate(job([{"field": "Header", "mappingColumn": "Default", "recordType": "H"}]))

    def test_mapping_positions_round_trip_and_new_rows_append_after_saved_positions(self):
        payload = job([
            {"field": "Existing", "mappingColumn": "lastname", "recordType": "D", "DataSetNo": 3, "ColSeqNo": 7},
            {"field": "Appended", "mappingColumn": "firstname", "recordType": "D", "dataSetNo": 3},
        ])
        ordered = ordered_mappings(payload.mapping.rows)
        self.assertEqual([(row.dataSetNo, row.colSeqNo) for row in ordered], [(3, 7), (3, 8)])
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 30, payload)
        mappings = [call.args[1] for call in connection.execute.call_args_list
                    if len(call.args) == 2 and "jobfieldmapping" in call.args[1]]
        self.assertEqual([(row["datasetNo"], row["colSeqNo"]) for row in mappings], [(3, 7), (3, 8)])
        with self.assertRaisesRegex(InvalidRun, "unique column sequence"):
            ordered_mappings([ordered[0], ordered[0]])

    def test_new_detail_conditions_and_sort_fragments_fit_production_append_contract(self):
        payload = job([{"field": "DATE", "mappingColumn": "paydate", "recordType": "D"}])
        payload.fileSettings = rb.FileSettingsForm.model_validate({
            "conditionalStatements": [{"mappingColumn": "paydate", "condition": ">=", "value": "2026-11-01"}],
            "sortingOrder": [{"orderBy": "2", "mappingColumn": "lastname"},
                             {"orderBy": "1", "mappingColumn": "PayGroup"}],
        })
        connection = Mock()
        connection.execute.return_value.mappings.return_value = []
        rb._write_job_details(connection, 30, payload)
        detail = next(call.args[1] for call in connection.execute.call_args_list
                      if len(call.args) == 2 and call.args[1].get("recttype") == "D")
        self.assertEqual(detail["conditionalStmt"], "WHERE [paydate] >= '2026-11-01'")
        self.assertEqual(detail["sortOrder"], ", PayGroup, lastname")
        assembled = detail["Query"] + " from #ret_builder_info " + detail["conditionalStmt"] + " order by RetNum" + detail["sortOrder"]
        self.assertEqual(assembled, "SELECT valid_flag, retnum, paydate AS sort1, [paydate] from #ret_builder_info WHERE [paydate] >= '2026-11-01' order by RetNum, PayGroup, lastname")

    def test_edit_read_retains_dataset_and_column_sequence_in_response(self):
        original = rb._job_from_rows(
            {"jobid": 30, "jobfilename": "Test", "filetype": "CSV", "jobdesc": "",
             "isEnabled": True, "StoreResults": False, "includeHeader": True, "ismerge": False},
            {"rbJobTypeChk": "Daily", "schedules_session": "AM", "ScheduleWeek": "1"},
            [{"jobclientcolumn": "NAME", "jobfieldmapping": "lastname", "jobdefaultvalue": "",
              "jobformat": "", "jobrectype": "D", "DataSetNo": 3, "ColSeqNo": 7}],
            [], [], [], [], {},
        )
        self.assertEqual(original.mapping.rows[0].dataSetNo, 3)
        self.assertEqual(original.mapping.rows[0].colSeqNo, 7)


class ExportQueryTransactionTests(TestCase):
    def test_condition_edits_reach_query_31_without_changing_saved_select_or_aliases(self):
        rule = {"mappingColumn": "paydate", "condition": ">=", "value": "2026-11-01"}
        edited = {**rule, "value": "2026-11-12"}
        query = "SELECT valid_flag, retnum, paydate AS sort1, paydate AS ExistingPayDate"
        legacy = "where HasActivity = 1"
        cases = [
            ([], "", {"conditionalStatements": [edited]}, "WHERE [paydate] >= '2026-11-12'"),
            ([rule], "WHERE [paydate] >= '2026-11-01'", {"conditionalStatements": [edited]}, "WHERE [paydate] >= '2026-11-12'"),
            ([rule], "WHERE [paydate] >= '2026-11-01'", {"conditionalStatements": []}, ""),
            ([rule], "", {"conditionalStatements": [rule]}, "WHERE [paydate] >= '2026-11-01'"),
            ([], legacy, None, legacy),
            ([], legacy, {"conditionalStatements": []}, legacy),
            ([rule], legacy, {"sortingOrder": []}, legacy),
        ]
        for previous_rules, previous_where, submitted, expected in cases:
            with self.subTest(previous=previous_where, submitted=submitted):
                original_payload = job([{"field": "PAYDATE", "mappingColumn": "paydate", "recordType": "D"}])
                original = rb.RetirementBuilderJob(id=60, **original_payload.model_dump())
                original.fileSettings = rb.FileSettingsForm.model_validate({"conditionalStatements": previous_rules})
                original.queryConfiguration = [rb.QueryConfigurationRow(recttype="D", query=query, conditions=previous_where)]
                before = original.model_dump()
                request = {"general": {"description": "Edited"}}
                if submitted is not None:
                    request["fileSettings"] = submitted
                payload = rb.RetirementBuilderJobInput.model_validate(request)
                connection = Mock()
                connection.execute.return_value.mappings.return_value = [
                    {"mapping_column": "paydate", "mapping_column_desc": "Pay Date", "mapping_column_dt": "date"},
                ]
                with (patch.object(rb.engine, "begin") as begin,
                      patch.object(rb, "_read_edit_job", return_value=original),
                      patch.object(rb, "_execute_query_batch", side_effect=lambda conn, queries: [
                          conn.execute(*rb._prepared_query(sql, values)) for sql, values in queries
                      ]),
                      patch.object(rb, "_file_formats", return_value={"CSV": ","})):
                    begin.return_value.__enter__.return_value = connection
                    rb.update_retirement_builder_job(60, payload)
                detail = next(call.args[1] for call in connection.execute.call_args_list
                              if len(call.args) == 2 and call.args[1].get("recttype") == "D")
                self.assertEqual(detail["Query"], query)
                self.assertEqual(detail["conditionalStmt"], expected)
                self.assertEqual(original.model_dump(), before)

    def test_create_and_update_use_existing_query_31_and_one_transaction(self):
        for updating in (False, True):
            for fail_insert in (False, True):
                with self.subTest(updating=updating, fail_insert=fail_insert):
                    payload = job([{"field": "Surname", "mappingColumn": "lastname", "recordType": "D"}])
                    connection = Mock()
                    events = []
                    saved = []

                    def execute(statement, parameters=None):
                        if parameters and "recttype" in parameters:
                            self.assertEqual(str(statement), str(rb._prepared_query(rb.QUERY_31, parameters)[0]))
                            saved.append(parameters)
                            if fail_insert and len(saved) == 2:
                                raise SQLAlchemyError("Simulated insert failure")
                        result = Mock()
                        result.mappings.return_value = []
                        return result

                    connection.execute.side_effect = execute

                    @contextmanager
                    def transaction():
                        events.append("begin")
                        try:
                            yield connection
                        except Exception:
                            events.append("rollback")
                            raise
                        else:
                            events.append("commit")

                    result = rb.RetirementBuilderJob(id=30, **payload.model_dump())
                    with (patch.object(rb.engine, "begin", side_effect=transaction),
                          patch.object(rb, "_file_formats", return_value={"CSV": ","}),
                          patch.object(rb, "_execute_identity_query", return_value=30),
                          patch.object(rb, "_read_full_job", return_value=result),
                          patch.object(rb, "_read_edit_job", return_value=result),
                          patch.object(rb, "_execute_query_batch", side_effect=lambda conn, queries: [
                              conn.execute(*rb._prepared_query(sql, values)) for sql, values in queries
                          ])):
                        if fail_insert:
                            with self.assertRaises(HTTPException):
                                rb.update_retirement_builder_job(30, payload) if updating else rb._create_job(payload)
                        else:
                            rb.update_retirement_builder_job(30, payload) if updating else rb._create_job(payload)
                    self.assertEqual(events, ["begin", "rollback" if fail_insert else "commit"])
                    if not fail_insert:
                        self.assertEqual([row["recttype"] for row in saved], ["H", "D", "T"])
                        if updating:
                            calls = connection.execute.call_args_list
                            deletion = next(index for index, call in enumerate(calls) if str(call.args[0]) == str(rb._prepared_query(rb.QUERY_44, {"jobid": 30})[0]))
                            insertion = next(index for index, call in enumerate(calls) if len(call.args) == 2 and "recttype" in call.args[1])
                            self.assertLess(deletion, insertion)

from unittest import TestCase
from unittest.mock import Mock

from fastapi import HTTPException

from app.retirement_conditions import parsed_conditions
from app.retirement_query_builder import export_record_queries, ordered_mappings
from app.retirement_results import InvalidRun, build_report_files
from app.routers import retirement_builder as rb


def payload(source="workphone", default=""):
    return rb.RetirementBuilderJobInput.model_validate({
        "general": {"fileName": "Regression", "fileFormat": "CSV"},
        "mapping": {"includeHeader": True, "rows": [
            {"field": "PHONE", "mappingColumn": source, "defaultValue": default, "recordType": "D", "colSeqNo": 1},
        ]},
    })


class MappingRegressionTests(TestCase):
    def test_changed_source_and_default_replace_expression_preserving_confirmed_alias(self):
        original = payload()
        saved = rb.QueryConfigurationRow(recttype="D", query='select valid_flag, retnum,paydate as sort1,  workphone as "CWORKPHONE"')
        old = ordered_mappings(original.mapping.rows)
        changed = payload("Workemail")
        detail = export_record_queries(changed, ordered_mappings(changed.mapping.rows), [saved], original_mappings=old)[1]
        self.assertEqual(detail["query"], saved.query.replace("workphone as", "Workemail as"))
        constant = payload("Default", "O'Brien AND Sons")
        result = export_record_queries(constant, ordered_mappings(constant.mapping.rows), [saved], original_mappings=old)[1]
        self.assertIn("'O''Brien AND Sons' as \"CWORKPHONE\"", result["query"])
        restored = export_record_queries(original, old, [rb.QueryConfigurationRow(**result)],
                                         original_mappings=ordered_mappings(constant.mapping.rows))[1]
        self.assertEqual(restored["query"], saved.query)

    def test_nested_commas_escaped_quotes_and_aliases_are_not_split(self):
        original = payload()
        saved = rb.QueryConfigurationRow(recttype="D", query="SELECT valid_flag, retnum, paydate AS sort1, COALESCE(workphone, 'x, y''s') AS [Phone, AS value]]x]")
        changed = payload("Workemail")
        result = export_record_queries(changed, ordered_mappings(changed.mapping.rows), [saved],
                                       original_mappings=ordered_mappings(original.mapping.rows))[1]
        self.assertEqual(result["query"], "SELECT valid_flag, retnum, paydate AS sort1, Workemail AS [Phone, AS value]]x]")
        original.mapping.rows[0].format = "Uppercase"
        unchanged = export_record_queries(original, ordered_mappings(original.mapping.rows), [saved],
                                          original_mappings=ordered_mappings(original.mapping.rows))[1]
        self.assertEqual(unchanged["query"], saved.query)

    def test_uncertain_projection_or_layout_is_blocked_instead_of_exporting_old_values(self):
        original, changed = payload(), payload("Workemail")
        for query in ("SELECT only_one", "SELECT valid_flag,retnum,paydate,workphone implicit_alias",
                      "SELECT valid_flag,retnum,paydate,workphone FROM table1"):
            with self.subTest(query=query), self.assertRaises(InvalidRun):
                export_record_queries(changed, ordered_mappings(changed.mapping.rows),
                                      [rb.QueryConfigurationRow(recttype="D", query=query)],
                                      original_mappings=ordered_mappings(original.mapping.rows))


class TextConditionRegressionTests(TestCase):
    def test_text_round_trip_uses_existing_conditions_not_numeric_detail_column(self):
        job = payload()
        job.fileSettings = rb.FileSettingsForm.model_validate({"conditionalStatements": [
            {"mappingColumn": "Employee Name", "condition": "=", "value": "O'Brien AND Sons", "valueType": "text"},
            {"mappingColumn": "ssn", "condition": "!=", "value": "000000001", "valueType": "text"},
        ]})
        rb._validate_payload(job)
        connection = Mock()
        connection.execute.return_value.mappings.return_value = [
            {"mapping_column": "emp_name", "mapping_column_desc": "Employee Name", "mapping_column_dt": "varchar(120)"},
            {"mapping_column": "ssn", "mapping_column_desc": "SSN", "mapping_column_dt": "char(9)"},
        ]
        rb._write_job_details(connection, 60, job)
        values = [call.args[1] for call in connection.execute.call_args_list if len(call.args) == 2]
        detail = next(row for row in values if row.get("recttype") == "D")
        self.assertEqual(detail["conditionalStmt"], "WHERE [emp_name] = 'O''Brien AND Sons' AND [ssn] != '000000001'")
        self.assertFalse(any("Symbol" in row for row in values))
        restored = rb._visible_conditions([], [{"recttype": "D", "Conditions": detail["conditionalStmt"]}])
        self.assertEqual([row["value"] for row in restored], ["O'Brien AND Sons", "000000001"])
        self.assertTrue(all(row["valueType"] == "text" for row in restored))

    def test_mixed_rules_and_text_that_looks_like_a_date_reopen_without_loss(self):
        where = "WHERE [count] > 1.00 AND [name] = '2026-10-15' AND [paydate] >= '2026-10-01'"
        stored = [{"mapping_column": "count", "condition_symbol": ">", "condition_value": 1},
                  {"mapping_column": "paydate", "condition_symbol": "date:>=", "condition_value": 20261001}]
        restored = rb._visible_conditions(stored, [{"recttype": "D", "Conditions": where}])
        self.assertEqual([row["valueType"] for row in restored], ["number", "text", "date"])
        self.assertIsNone(parsed_conditions("WHERE [name] = 'x' OR 1=1"))
        self.assertIsNone(parsed_conditions("WHERE [name] = 'x' AND "))
        self.assertEqual(parsed_conditions("WHERE [na]]me] = 'x''y AND z'")[0]["value"], "x'y AND z")

    def test_text_cannot_be_used_to_bypass_numeric_column_validation(self):
        job = payload()
        job.fileSettings = rb.FileSettingsForm.model_validate({"conditionalStatements": [
            {"mappingColumn": "hours", "condition": ">", "value": "abc", "valueType": "text"},
        ]})
        connection = Mock()
        connection.execute.return_value.mappings.return_value = [
            {"mapping_column": "hours", "mapping_column_desc": "Hours", "mapping_column_dt": "numeric"},
        ]
        with self.assertRaises(HTTPException) as error:
            rb._write_job_details(connection, 60, job)
        self.assertEqual(error.exception.status_code, 422)
        self.assertFalse(any(len(call.args) == 2 for call in connection.execute.call_args_list))

    def test_csv_source_filters_strings_without_numeric_conversion(self):
        job = rb.RetirementBuilderJob(id=60, **payload("name").model_dump())
        job.fileSettings = rb.FileSettingsForm.model_validate({"conditionalStatements": [
            {"mappingColumn": "name", "condition": "=", "value": "O'Brien AND Sons", "valueType": "text"},
        ]})
        report, = build_report_files(job, b"name\nO'Brien AND Sons\nOther\n")
        self.assertEqual(report.csv.splitlines(), ["PHONE", "O'Brien AND Sons"])

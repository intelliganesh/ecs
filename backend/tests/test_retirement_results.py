from unittest import TestCase

from app.retirement_results import InvalidRun, build_report_files
from app.routers.retirement_builder import RetirementBuilderJob


def build_report(job, source):
    report, = build_report_files(job, source)
    return report.rows, report.csv


class RetirementResultsTests(TestCase):
    def test_output_formats_group_by_each_selected_field(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileName": "Payroll.csv", "fileFormat": "CSV"},
            "mapping": {"rows": [{"field": "Name"}]},
        })
        source = b"Client_ID,Payday,Name\n0002,2026-11-12,C\n0001,11/11/2026,A\n0001,2026-11-12,B\n0001,2026-11-11,D\n"
        expected = {
            "File Name": {"Payroll.csv": "CABD"},
            "Client ID": {"0001.csv": "ABD", "0002.csv": "C"},
            "Payday": {"2026-11-11.csv": "AD", "2026-11-12.csv": "CB"},
            "File Name + Client ID": {"Payroll_0001.csv": "ABD", "Payroll_0002.csv": "C"},
            "File Name + Payday": {"Payroll_2026-11-11.csv": "AD", "Payroll_2026-11-12.csv": "CB"},
            "Client ID + Payday": {"0001_2026-11-11.csv": "AD", "0001_2026-11-12.csv": "B", "0002_2026-11-12.csv": "C"},
            "File Name + Client ID + Payday": {"Payroll_0001_2026-11-11.csv": "AD", "Payroll_0001_2026-11-12.csv": "B", "Payroll_0002_2026-11-12.csv": "C"},
        }
        for name_format, names in expected.items():
            with self.subTest(name_format=name_format):
                job.general.outputFileNameFormat = name_format
                files = build_report_files(job, source)
                self.assertEqual({file.file_name: "".join(file.csv.splitlines()[1:]) for file in files}, names)

    def test_grouped_reports_share_headers_and_select_client_trailers(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV", "outputFileNameFormat": "Client ID + Payday"},
            "mapping": {"rows": [
                {"field": "Label", "recordType": "Header"},
                {"field": "Name"},
                {"field": "Pay Date", "mappingColumn": "Payroll Date", "defaultValue": "11/11/2026"},
                {"field": "Label", "recordType": "Trailer"},
            ]},
        })
        files = build_report_files(job, (
            b"Record Type,Client ID,Payroll Date,Name,Label\n"
            b"H,,,,Shared header\nD,01,,Employee One,\nD,02,11/11/2026,Employee Two,\n"
            b"T,01,,,Client one trailer\nT,02,,,Client two trailer\n"
        ))
        self.assertEqual([file.file_name for file in files], ["01_2026-11-11.csv", "02_2026-11-11.csv"])
        self.assertEqual([file.csv.splitlines()[1] for file in files], ["Shared header", "Shared header"])
        self.assertEqual([file.csv.splitlines()[-1] for file in files], ["Client one trailer", "Client two trailer"])

    def test_phone_formats_keep_country_codes_and_reject_extensions(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileFormat": "CSV"},
            "mapping": {"rows": [
                {"field": "Phone Digits", "mappingColumn": "Phone", "format": "Digits Only"},
                {"field": "Display Phone", "mappingColumn": "Phone", "format": "(XXX) XXX-XXXX"},
                {"field": "Dashed Phone", "mappingColumn": "Phone", "format": "XXX-XXX-XXXX"},
                {"field": "International Phone", "mappingColumn": "Mobile", "format": "International (+)"},
            ]},
        })
        rows, output = build_report(job, b"Phone,Mobile\n+1 (202) 555-0100,00 91 98765 43210\n")
        self.assertEqual(list(rows[0].values.values()), [
            "12025550100", "(202) 555-0100", "202-555-0100", "+919876543210",
        ])
        self.assertEqual(output.splitlines()[1], "12025550100,(202) 555-0100,202-555-0100,+919876543210")
        with self.assertRaisesRegex(InvalidRun, "invalid phone number"):
            build_report(job, b"Phone,Mobile\n202-555-0100 x12,+91 98765 43210\n")
        with self.assertRaisesRegex(InvalidRun, "explicit"):
            build_report(job, b"Phone,Mobile\n202-555-0100,98765 43210\n")

    def test_new_date_grouping_text_and_ssn_formats_in_csv(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileFormat": "CSV"},
            "mapping": {"rows": [
                {"field": "Date", "format": "DD/MM/YYYY"},
                {"field": "Pay", "format": "#,##0.00"},
                {"field": "Email", "format": "Lowercase"},
                {"field": "Name", "format": "Trim Whitespace"},
                {"field": "SSN", "format": "XXX-XX-XXXX - SSN"},
            ]},
        })
        rows, output = build_report(job, b"Date,Pay,Email,Name,SSN\n2026-11-09,12345.675,TEST@EXAMPLE.COM, Example ,000123456\n")
        self.assertEqual(list(rows[0].values.values()), [
            "09/11/2026", "12,345.68", "test@example.com", "Example", "000-12-3456",
        ])
        self.assertEqual(output.splitlines()[1], '09/11/2026,"12,345.68",test@example.com,Example,000-12-3456')

    def test_date_and_number_formats_change_the_generated_and_saved_values(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileFormat": "CSV"},
            "mapping": {"rows": [
                {"field": "Slash Date", "mappingColumn": "Pay Date", "format": "MM/DD/YYYY"},
                {"field": "ISO Date", "mappingColumn": "Pay Date", "format": "YYYY-MM-DD"},
                {"field": "Net Pay", "mappingColumn": "Amount", "format": "0.00 - Decimal"},
                {"field": "Whole Pay", "mappingColumn": "Amount", "format": "0 - Integer"},
            ]},
        })
        rows, output = build_report(job, b"Pay Date,Amount\n2/9/2026,-10.505\n")
        self.assertEqual(list(rows[0].values.values()), ["02/09/2026", "2026-02-09", "-10.51", "-11"])
        self.assertEqual(output.splitlines()[1], "02/09/2026,2026-02-09,-10.51,-11")

    def test_mapped_export_filters_and_sorts_detail_rows_and_retains_record_types(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileFormat": "CSV_PIPE"},
            "mapping": {"rows": [
                {"field": "Employer", "mappingColumn": "Company", "recordType": "Header"},
                {"field": "Amount", "mappingColumn": "Net Salary", "recordType": "Detail"},
                {"field": "Payday", "mappingColumn": "Pay Date", "format": "MMDDYYYY - Date"},
                {"field": "Count", "recordType": "Trailer"},
            ]},
            "fileSettings": {
                "sortingOrder": [{"orderBy": "1", "mappingColumn": "Net Salary"}],
                "conditionalStatements": [{"mappingColumn": "Net Salary", "condition": ">", "value": "1.00"}],
            },
        })
        rows, output = build_report(job, (
            b"Record Type,Company,Net Salary,Pay Date,Count\n"
            b"H,Example Employer,,,\n"
            b"D,,10.00,2026-11-11,\n"
            b"D,,1.00,2026-11-11,\n"
            b"D,,2.00,2026-11-11,\n"
            b"T,,,,2\n"
        ))
        self.assertEqual([row.record_type for row in rows], ["H", "D", "D", "T"])
        self.assertEqual(rows[1].values, {"Amount": "2.00", "Payday": "11112026"})
        self.assertEqual(output, "Amount|Payday\r\nExample Employer\r\n2.00|11112026\r\n10.00|11112026\r\n2\r\n")

    def test_missing_source_column_is_an_error_and_default_can_supply_it(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV"},
            "mapping": {"includeHeader": False, "rows": [{"field": "Department"}]},
        })
        with self.assertRaisesRegex(InvalidRun, "Department"):
            build_report(job, b"Name\nExample Person\n")
        job.mapping.rows[0].defaultValue = "General"
        rows, output = build_report(job, b"Name\nExample Person\n")
        self.assertEqual(rows[0].values, {"Department": "General"})
        self.assertEqual(output, "General\r\n")

    def test_report_sorts_by_priority_with_mixed_directions(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileFormat": "CSV"},
            "mapping": {"rows": [{"field": "Department"}, {"field": "Net Salary"}]},
            "fileSettings": {"sortingOrder": [
                {"orderBy": "2", "mappingColumn": "Net Salary", "direction": "DESC"},
                {"orderBy": "1", "mappingColumn": "Department"},
            ]},
        })
        _, output = build_report(job, b"Department,Net Salary\nB,20\nA,2\nA,\nA,10\nB,1\n")
        self.assertEqual(output.splitlines(), ["Department,Net Salary", "A,10", "A,2", "A,", "B,20", "B,1"])

    def test_malformed_input_cannot_be_exported(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV"},
            "mapping": {"rows": [{"field": "Name"}]},
        })
        with self.assertRaisesRegex(InvalidRun, "does not match"):
            build_report(job, b"Name\nToo,many,columns\n")
        with self.assertRaisesRegex(InvalidRun, "valid UTF-8"):
            build_report(job, b"Name\n\xff\n")

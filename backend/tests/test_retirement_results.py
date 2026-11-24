import csv
from datetime import date
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

from app.retirement_results import InvalidRun, ReportDateRange, ResultRow, build_report_files, file_name_format_code, format_sort_columns, merge_report_files, parse_sort_order, store_results
from app.routers.retirement_builder import RetirementBuilderJob


def build_report(job, source):
    report, = build_report_files(job, source)
    return report.rows, report.csv


class RetirementResultsTests(TestCase):
    def test_delimited_source_rejects_oversized_padding_even_for_empty_values(self):
        for format_name in ("LA", "RA"):
            for value in ("ABC", ""):
                with self.subTest(format=format_name, value=value):
                    job = RetirementBuilderJob.model_validate({
                        "id": 60, "general": {"fileName": "Padding", "fileFormat": "CSV"},
                        "mapping": {"includeHeader": False, "rows": [
                            {"field": "Text", "mappingColumn": "Text", "format": format_name, "length": "1001"},
                        ]},
                    })
                    with self.assertRaisesRegex(InvalidRun, "padding length from 0 to 1000"):
                        build_report_files(job, f'Text\n"{value}"\n'.encode())

    def test_fixed_fields_use_character_lengths_and_optional_zero_based_positions(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileName": "Fixed", "fileFormat": "FIXED"},
            "mapping": {"includeHeader": False, "rows": [
                {"field": "Name", "mappingColumn": "Name", "length": "10", "startPosition": "00"},
                {"field": "Code", "mappingColumn": "Code", "length": "4", "format": "RA"},
            ]},
        })
        report, = build_report_files(job, b"Name,Code\nvalue1,7\n")
        self.assertEqual(report.csv, "value1       7\r\n")
        self.assertEqual(len(report.csv.splitlines()[0]), 14)
        self.assertEqual(report.excel_rows, [["value1    ", "   7"]])
        job.mapping.rows[1].startPosition = "12"
        report, = build_report_files(job, b"Name,Code\nvalue1,7\n")
        self.assertEqual(report.csv, "value1         7\r\n")
        self.assertEqual(len(report.csv.splitlines()[0]), 16)
        job.mapping.rows[1].startPosition = "2"
        with self.assertRaisesRegex(InvalidRun, "overlaps"):
            build_report_files(job, b"Name,Code\nvalue1,7\n")

    def test_fixed_rejects_missing_lengths_overflow_and_control_characters(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "FIXED"},
            "mapping": {"includeHeader": False, "rows": [{"field": "Name", "length": "0"}]},
        })
        for length in ("", "0", "-1", "1001"):
            with self.subTest(length=length), self.assertRaisesRegex(InvalidRun, "FIXED length"):
                job.mapping.rows[0].length = length
                build_report_files(job, b"Name\nAlex\n")
        job.mapping.rows[0].length = "3"
        with self.assertRaisesRegex(InvalidRun, "exceeds its FIXED length"):
            build_report_files(job, b"Name\nAlex\n")
        job.mapping.rows[0].length = "20"
        with self.assertRaisesRegex(InvalidRun, "control character"):
            build_report_files(job, b'Name\n"A\nB"\n')

    def test_fixed_lengths_count_characters_and_keep_headers_within_their_widths(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "FIXED"},
            "mapping": {"includeHeader": True, "rows": [{"field": "Name", "length": "6"}]},
        })
        report, = build_report_files(job, "Name\nJosé\n".encode())
        self.assertEqual(report.csv, "Name  \r\nJosé  \r\n")
        self.assertEqual([len(row) for row in report.csv.splitlines()], [6, 6])
        job.mapping.rows[0].field = "Employee Name"
        job.mapping.rows[0].mappingColumn = "Name"
        with self.assertRaisesRegex(InvalidRun, "exceeds its FIXED length"):
            build_report_files(job, b"Name\nAlex\n")

    def test_fixed_merging_removes_repeated_header_and_retains_excel_field_boundaries(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileName": "Fixed", "fileFormat": "FIXED", "outputFileNameFormat": "PAYDAY"},
            "mapping": {"includeHeader": True, "rows": [{"field": "Name", "length": "8"}]},
        })
        reports = build_report_files(job, b"Payday,Name\n2026-11-10,One\n2026-11-12,Two\n")
        merged = merge_report_files(job, reports)
        self.assertEqual(merged.csv, "Name    \r\nOne     \r\nTwo     \r\n")
        self.assertEqual(merged.excel_rows, [["Name    "], ["One     "], ["Two     "]])
        job.mapping.includeHeader = False
        merged = merge_report_files(job, build_report_files(job, b"Payday,Name\n2026-11-10,One\n2026-11-12,Two\n"))
        self.assertEqual(merged.csv, "One     \r\nTwo     \r\n")

    def test_name_quote_cleanup_and_ssn_mask_also_apply_to_csv_sources(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV"},
            "mapping": {"includeHeader": False, "rows": [
                {"field": "Name", "mappingColumn": "Employee Name"},
                {"field": "SSN", "format": "XXXXXXXXX"},
            ]},
        })
        report, = build_report_files(job, b'Employee Name,SSN\n"""Doe, Alex""",000-00-0000\n')
        self.assertEqual(list(csv.reader(StringIO(report.csv))), [["Doe, Alex", "000000000"]])

    def test_column_sort_lists_use_names_in_priority_order_and_read_older_formats(self):
        names = ["PayGroup", "lastname", "firstname"]
        self.assertEqual(format_sort_columns(names), "PayGroup, lastname, firstname")
        for value in ("PayGroup, lastname, firstname", ", PayGroup , lastname , firstname"):
            self.assertEqual(parse_sort_order(value), [
                {"orderBy": str(index), "mappingColumn": name, "direction": "ASC"}
                for index, name in enumerate(names, 1)
            ])
        unusual = ['Last, First]', 'A "quoted" name']
        self.assertEqual([row["mappingColumn"] for row in parse_sort_order(format_sort_columns(unusual))], unusual)
        self.assertEqual(parse_sort_order("ORDER BY [lastname] DESC, [firstname] ASC"), [
            {"orderBy": "1", "mappingColumn": "lastname", "direction": "DESC"},
            {"orderBy": "2", "mappingColumn": "firstname", "direction": "ASC"},
        ])
        self.assertEqual(parse_sort_order(format_sort_columns([])), [])
        for value in (",", "lastname,", "lastname,,firstname", '"unclosed', "lastname\nfirstname", "ORDER BY [lastname] BAD"):
            with self.subTest(value=value), self.assertRaises(InvalidRun):
                parse_sort_order(value)

    def test_result_storage_writes_only_record_type_codes(self):
        connection = Mock()
        rows = [ResultRow(kind, {"Value": "example"}) for kind in ("Header", " d ", "T")]
        self.assertEqual(store_results(connection, 31, uuid4(), rows), 3)
        connection.execute.assert_called_once()
        values = connection.execute.call_args.args[1]
        self.assertEqual([row["record_type"] for row in values], ["H", "D", "T"])
        self.assertEqual([row["row_number"] for row in values], [1, 2, 3])

    def test_invalid_result_type_rejects_the_whole_batch_before_writing(self):
        for kind in ("CSV_SORT", "PAYROLL", "CUSTOM", ""):
            with self.subTest(kind=kind):
                connection = Mock()
                rows = [ResultRow("D", {}), ResultRow(kind, {})]
                with self.assertRaisesRegex(InvalidRun, "H, D, or T"):
                    store_results(connection, 31, uuid4(), rows)
                connection.execute.assert_not_called()

    def test_run_date_range_filters_csv_on_check_date_and_keeps_both_endpoints(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV"}, "mapping": {"rows": [{"field": "Name"}]},
        })
        source = b"Check Date,Name\n2026-11-01,Before\n2026-11-02,Start\n2026-11-03,End\n2026-11-04,After\n"
        dates = ReportDateRange(date(2026, 11, 2), date(2026, 11, 3))
        report, = build_report_files(job, source, date_range=dates)
        self.assertEqual(report.csv.splitlines(), ["Name", "Start", "End"])
        self.assertEqual(build_report_files(job, source, date_range=ReportDateRange(end=date(2026, 10, 31))), [])
        with self.assertRaisesRegex(InvalidRun, "Pay Date or Check Date"):
            build_report_files(job, b"Name\nExample\n", date_range=dates)

    def test_configured_mapping_codes_format_generated_csv(self):
        cases = [
            ("RA", "City", "   City"),
            ("LA", "City", "City   "),
            ("$######.##", "-12.345", "-$12.35"),
            ("$########", "9.8", "$10"),
            ("######.##", "12.30", "12.30"),
            ("######.##", "0", "0.00"),
            ("######.##", "0.0", "0.00"),
            ("######.##", "25", "25.00"),
            ("######.##", "25.5", "25.50"),
            ("######.##", "1.235", "1.24"),
            ("######.##", "-1.235", "-1.24"),
            ("$######.##", "0", "$0.00"),
            ("$######.##", "12.3", "$12.30"),
            ("####.####", "0", "0.0000"),
            ("######.##", "", ""),
            ("########", "0", "0"),
            ("########", "9.8", "10"),
            ("XXX-XX-XXXX", "000000000", "000-00-0000"),
            ("XXXXXXXXX", "000-00-0000", "000000000"),
            ("MM/DD/YYYY", "2025-11-30", "11/30/2025"),
            ("MM-DD-YYYY", "2025-11-30", "11-30-2025"),
            ("CCYYMMDD", "2025-11-30", "20251130"),
            ("MMDDYYYY", "2025-11-30", "11302025"),
        ]
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV"},
            "mapping": {"rows": [
                {"field": f"Output {i}", "mappingColumn": f"Input {i}", "format": code, "length": "7"}
                for i, (code, _, _) in enumerate(cases)
            ]},
        })
        header = ",".join(f"Input {i}" for i in range(len(cases)))
        row = ",".join(value for _, value, _ in cases)
        report, = build_report_files(job, f"{header}\n{row}\n".encode())
        self.assertEqual(list(csv.reader(StringIO(report.csv)))[1], [expected for _, _, expected in cases])

    def test_catalog_keys_use_exact_headings_and_fall_back_to_old_display_labels(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "general": {"fileFormat": "Comma", "outputFileNameFormat": "CLIENT_PAYDAY"},
            "mapping": {"rows": [
                {"field": "Company", "mappingColumn": "company_name", "recordType": "D"},
                {"field": "Date", "mappingColumn": "payroll_month", "recordType": "D"},
            ]},
        })
        aliases = {"company_name": "Company Name", "company_id": "Client ID", "payroll_month": "Pay Date"}
        for source in (
            b"company_name,Company Name,company_id,payroll_month\nExact Company,Other Column,008,2026-11-17\n",
            b"Company Name,Client ID,Pay Date\nExact Company,008,2026-11-17\n",
        ):
            with self.subTest(source=source):
                report, = build_report_files(job, source, source_labels=aliases)
                self.assertEqual(report.file_name, "008_2026-11-17.csv")
                self.assertEqual(report.rows[0].values, {"Company": "Exact Company", "Date": "2026-11-17"})

    def test_column_headings_and_record_types_use_the_configured_output_delimiter(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1,
            "mapping": {"includeHeader": True, "rows": [
                {"field": "Mapped Header", "mappingColumn": "Company", "recordType": "Header"},
                {"field": "Company, Name", "mappingColumn": "Company"},
                {"field": "Client Code", "mappingColumn": "Client"},
                {"field": "Amount", "recordType": "Trailer"},
            ]},
        })
        source = b'Record Type,Company,Client,Amount\nH,"Audit, Alpha",,\nD,"Audit, Alpha",0007,\nT,,,123\n'
        expected = [["Company, Name", "Client Code"], ["Audit, Alpha"], ["Audit, Alpha", "0007"], ["123"]]
        for delimiter in (",", "\t", " ", ";", "|"):
            with self.subTest(delimiter=delimiter):
                report, = build_report_files(job, source, delimiter=delimiter)
                self.assertEqual(report.delimiter, delimiter)
                self.assertEqual(list(csv.reader(StringIO(report.csv), delimiter=delimiter)), expected)

    def test_payroll_filter_keeps_only_trailers_with_a_retained_detail(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileFormat": "CSV", "reportSource": "companyPayroll"},
            "mapping": {"rows": [
                {"field": "Net Salary Total"},
                {"field": "Net Salary Total", "recordType": "Trailer"},
            ]},
            "fileSettings": {"conditionalStatements": [
                {"mappingColumn": "Net Salary Total", "condition": ">", "value": "100"},
            ]},
        })
        source = b"Record Type,Net Salary Total\nD,100\nD,200\nT,100\nT,200\n"
        report, = build_report_files(job, source, from_payroll_procedure=True)
        self.assertEqual(
            [(row.record_type, row.values["Net Salary Total"]) for row in report.rows],
            [("D", "200"), ("T", "200")],
        )
        job.fileSettings.conditionalStatements[0].value = "200"
        self.assertEqual(build_report_files(job, source, from_payroll_procedure=True), [])

    def test_merge_preserves_records_and_removes_repeated_csv_headings(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileName": "Payroll", "fileFormat": "CSV_PIPE", "outputFileNameFormat": "Payday"},
            "mapping": {"rows": [{"field": "Full\nName", "mappingColumn": "Name"}]},
        })
        source = b'Payday,Name\n2026-11-11,"A\nB"\n2026-11-12,C\n'
        reports = build_report_files(job, source)
        merged = merge_report_files(job, reports)
        self.assertEqual(merged.file_name, "Payroll_merged.txt")
        self.assertEqual(merged.csv, '"Full\nName"\r\n"A\nB"\r\nC\r\n')
        job.mapping.includeHeader = False
        merged = merge_report_files(job, build_report_files(job, source))
        self.assertEqual(merged.csv, '"A\nB"\r\nC\r\n')

    def test_output_formats_group_by_each_selected_field(self):
        job = RetirementBuilderJob.model_validate({
            "id": 1, "general": {"fileName": "Payroll.csv", "fileFormat": "CSV"},
            "mapping": {"rows": [{"field": "Name"}]},
        })
        source = b"Client_ID,Payday,Name\n0002,2026-11-12,C\n0001,11/11/2026,A\n0001,2026-11-12,B\n0001,2026-11-11,D\n"
        cases = (
            ("FILENAME", "File Name", {"Payroll.csv": "CABD"}),
            ("CLIENT", "Client ID", {"0001.csv": "ABD", "0002.csv": "C"}),
            ("PAYDAY", "Payday", {"2026-11-11.csv": "AD", "2026-11-12.csv": "CB"}),
            ("FILENAME_CLIENT", "File Name + Client ID", {"Payroll_0001.csv": "ABD", "Payroll_0002.csv": "C"}),
            ("FILENAME_PAYDAY", "File Name + Payday", {"Payroll_2026-11-11.csv": "AD", "Payroll_2026-11-12.csv": "CB"}),
            ("CLIENT_PAYDAY", "Client ID + Payday", {"0001_2026-11-11.csv": "AD", "0001_2026-11-12.csv": "B", "0002_2026-11-12.csv": "C"}),
            ("FILENAME_CLIENT_PAYDAY", "File Name + Client ID + Payday", {
                "Payroll_0001_2026-11-11.csv": "AD", "Payroll_0001_2026-11-12.csv": "B", "Payroll_0002_2026-11-12.csv": "C",
            }),
        )
        for code, label, names in cases:
            self.assertEqual(file_name_format_code(label), code)
            for name_format in (code, code.casefold(), label, label.replace("Payday", "Pay Date")):
                with self.subTest(name_format=name_format):
                    job.general.outputFileNameFormat = name_format
                    files = build_report_files(job, source)
                    self.assertEqual({file.file_name: "".join(file.csv.splitlines()[1:]) for file in files}, names)

    def test_filename_code_keeps_part_order_and_falls_back_for_unknown_values(self):
        self.assertEqual(file_name_format_code("Pay Date + Client ID"), "PAYDAY_CLIENT")
        self.assertEqual(file_name_format_code(" payday_client "), "PAYDAY_CLIENT")
        for value in ("", "Unknown", "CLIENT_CLIENT", "FILENAME_EXTRA"):
            with self.subTest(value=value):
                self.assertEqual(file_name_format_code(value), "FILENAME")

    def test_production_filename_spellings_preserve_grouping_parts(self):
        cases = {
            "File Name": "FILENAME", "FILENAME": "FILENAME", "CLIENT": "CLIENT",
            "PayDate": "PAYDAY", "File Name-ClientId": "FILENAME_CLIENT",
            "File Name-PayDate": "FILENAME_PAYDAY", "ClientId-PayDate": "CLIENT_PAYDAY",
            "File Name-ClientId-PayDate": "FILENAME_CLIENT_PAYDAY",
        }
        for stored, code in cases.items():
            with self.subTest(stored=stored):
                self.assertEqual(file_name_format_code(stored), code)
                self.assertEqual(file_name_format_code(f" {stored.lower()}  "), code)
        for invalid in ("File Name-PayDate-PayDate", "File Name-Unknown", "File Name-", "--"):
            self.assertEqual(file_name_format_code(invalid), "FILENAME")

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


class OutputExtensionTests(TestCase):
    def test_every_file_format_is_exported_with_its_configured_extension(self):
        for file_format, delimiter, extension in (("CSV", ",", ".csv"), ("TAB", "\t", ".tsv"), ("PIPE", "|", ".txt"), ("SEMICOLON", ";", ".txt"), ("TILDE", "~", ".txt"), ("FIXED", " ", ".txt")):
            job = RetirementBuilderJob.model_validate({
                "id": 1, "general": {"fileName": "Report", "fileFormat": file_format},
                "mapping": {"rows": [{"field": "Name", "mappingColumn": "Name", "length": "8"}]},
            })
            with self.subTest(file_format=file_format):
                report, = build_report_files(job, b"Name\nAlex\n", delimiter=delimiter)
                self.assertEqual(report.file_name, "Report" + extension)

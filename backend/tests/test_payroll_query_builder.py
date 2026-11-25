"""Pure generation/response tests: no database queries or SP calls."""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.payroll_query_builder import payroll_record_queries
from app.retirement_results import InvalidRun
from app.routers import payroll_builder as pb
from test_payroll_builder import CATALOG, create_payload


class PayrollQueryBuilderTests(TestCase):
    def payload(self, rows):
        payload = create_payload()
        payload.mapping.rows = [pb.shared.MappingRow.model_validate(row) for row in rows]
        return payload

    def test_metadata_source_uses_confirmed_output_label_instead_of_duplicate_retnum(self):
        payload = self.payload([{'field': 'Client Id in Prism', 'mappingColumn': 'RetNum', 'recordType': 'Detail'}])
        detail = next(row for row in payroll_record_queries(payload) if row['recttype'] == 'D')
        self.assertEqual(detail['query'], 'SELECT valid_flag, retnum, paydate AS sort1, [RetNum] AS [Client Id in Prism]')

    def test_alias_repair_keeps_other_expressions_filters_and_saved_input_untouched(self):
        payload = self.payload([
            {'field': 'Client', 'mappingColumn': 'RetNum', 'recordType': 'D'},
            {'field': 'Wages', 'mappingColumn': 'earnings', 'recordType': 'D', 'format': '######.##'},
        ])
        payload.fileSettings.conditionalStatements = [pb.shared.ConditionalStatementRow(mappingColumn='earnings', condition='>', value='0', valueType='number')]
        before = payload.model_dump()
        records = payroll_record_queries(payload)
        detail = next(row for row in records if row['recttype'] == 'D')
        self.assertIn('[RetNum] AS [Client]', detail['query'])
        self.assertIn("FORMAT(ROUND(CONVERT(decimal(38,18), [earnings]), 2), '0.00', 'en-US')", detail['query'])
        self.assertEqual(detail['conditions'], 'WHERE [earnings] > 0')
        self.assertEqual(payload.model_dump(), before)

    def test_single_arbitrary_dataset_and_multiple_dataset_markers_survive(self):
        for datasets in ((3,), (3, 7)):
            payload = self.payload([{'field': 'Client', 'mappingColumn': 'RetNum', 'recordType': 'D', 'dataSetNo': n} for n in datasets])
            details = [row for row in payroll_record_queries(payload) if row['recttype'] == 'D']
            self.assertEqual(len(details), len(datasets))
            for dataset, row in zip(datasets, details, strict=True):
                self.assertIn('[RetNum] AS [Client]', row['query'])
                if len(datasets) > 1:
                    self.assertIn(f'{dataset} AS [__ecs_dataset_{dataset}]', row['query'])

    def test_duplicate_sources_get_distinct_user_labels_and_bad_labels_are_rejected(self):
        payload = self.payload([{'field': label, 'mappingColumn': 'earnings', 'recordType': 'D'} for label in ('Base wages', 'Repeated wages')])
        detail = next(row for row in payroll_record_queries(payload) if row['recttype'] == 'D')
        self.assertIn('[earnings] AS [Base wages], [earnings] AS [Repeated wages]', detail['query'])
        payload = self.payload([{'field': 'RetNum', 'mappingColumn': 'RetNum', 'recordType': 'D'}])
        with self.assertRaisesRegex(InvalidRun, 'distinct output field label'):
            payroll_record_queries(payload)

    def test_header_trailer_collisions_are_aliased_but_ordinary_detail_stays_unchanged(self):
        payload = self.payload([
            {'field': 'Header client', 'mappingColumn': 'RetNum', 'recordType': 'H'},
            {'field': 'Wages', 'mappingColumn': 'earnings', 'recordType': 'D'},
            {'field': 'Trailer client', 'mappingColumn': 'RetNum', 'recordType': 'T'},
        ])
        payload.mapping.includeHeader = False
        records = {row['recttype']: row['query'] for row in payroll_record_queries(payload)}
        self.assertIn('[RetNum] AS [Header client]', records['H'])
        self.assertIn('[RetNum] AS [Trailer client]', records['T'])
        self.assertEqual(records['D'], 'SELECT valid_flag, retnum, paydate AS sort1, [earnings]')

    def test_reading_saved_date_conditions_returns_catalog_type_without_rewriting_sql(self):
        query = "SELECT valid_flag,retnum,paydate AS sort1,earnings AS [Wages]"
        data = {
            'READ_JOB': [{'jobid': 1, 'jobfilename': 'Fixture', 'filetype': 'CSV', 'FileNameFormat': 'File Name'}],
            'READ_MAPPINGS': [{'jobclientcolumn': 'Wages', 'jobfieldmapping': 'earnings', 'jobrectype': 'D', 'DataSetNo': 1, 'ColSeqNo': 1}],
            'READ_QUERY_CONFIGURATION': [{'recttype': 'D', 'Query': query, 'Conditions': "WHERE [paydate] >= '2026-10-01'"}],
        }
        def rows(connection, statement, params=None):
            name = next((key for key, value in pb.READS.items() if str(value) == str(statement)), None)
            return data.get(name, [])
        with patch.object(pb, '_rows', side_effect=rows), patch.object(pb, '_catalog', return_value=CATALOG), \
             patch.object(pb.shared, '_file_formats', return_value={'CSV': ','}):
            result = pb._read_job(MagicMock(), 1)
        condition, = result.fileSettings.conditionalStatements
        self.assertEqual((condition.mappingColumn, condition.value, condition.valueType), ('paydate', '2026-10-01', 'date'))
        self.assertEqual(result.queryConfiguration[0].query, query)

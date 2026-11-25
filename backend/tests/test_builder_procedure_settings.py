"""Procedure selection tests with no database connection or SP execution."""
from datetime import date
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.core.config import Settings
from app import payroll_source as retirement_source
from app.retirement_results import ReportDateRange
from app.routers import payroll_builder
from test_payroll_builder import fixture_job


class BuilderProcedureSettingsTests(TestCase):
    def test_env_file_sets_independent_names_and_normalizes_omitted_schema(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('RETIREMENT_REPORT_PROCEDURE=reports.retirement_custom\nPAYROLL_REPORT_PROCEDURE=payroll_custom\n')
            settings = Settings(_env_file=path)
        self.assertEqual(settings.retirement_report_procedure, 'reports.retirement_custom')
        self.assertEqual(settings.payroll_report_procedure, 'dbo.payroll_custom')

    def test_manual_and_scheduled_payroll_use_current_configured_name_and_bound_parameters(self):
        dates = ReportDateRange(date(2026, 11, 1), date(2026, 11, 24))
        with patch('pyodbc.connect', side_effect=AssertionError('Live DB prohibited')):
            for procedure in ('dbo.payrolljobbuilder', 'reports.renamed_payroll'):
                for scheduled in (False, True):
                    with self.subTest(procedure=procedure, scheduled=scheduled):
                        settings = Settings(_env_file=None, retirement_report_procedure='reports.retirement_only',
                                            payroll_report_procedure=procedure)
                        connection = MagicMock()
                        cursor = connection.connection.cursor.return_value
                        cursor.description = [('valid_flag',), ('retnum',), ('sort1',), ('Wages',)]
                        cursor.__iter__.return_value = iter([('1', '901', '2026-11-24', '123.45')])
                        cursor.nextset.return_value = False
                        with patch.object(payroll_builder, 'get_settings', return_value=settings):
                            payroll_builder._load_source(connection, fixture_job(), dates, scheduled=scheduled)
                        schema, name = procedure.split('.')
                        cursor.execute.assert_called_once_with(
                            f'EXEC [{schema}].[{name}] @client_id=?, @paystartdate=?, @payenddate=?, @runType=?',
                            987654, dates.start, dates.end, 'S' if scheduled else 'A',
                        )
                        cursor.close.assert_called_once()

    def test_payroll_setting_does_not_select_retirement_procedure(self):
        for payroll_name in ('dbo.payrolljobbuilder', 'reports.another_payroll'):
            settings = Settings(_env_file=None, retirement_report_procedure='reports.retirement_only',
                                payroll_report_procedure=payroll_name)
            with patch.object(retirement_source, 'get_settings', return_value=settings):
                self.assertEqual(retirement_source._payroll_procedure_name(), '[reports].[retirement_only]')

    def test_both_names_reject_invalid_identifiers_before_any_db_call(self):
        for field in ('retirement_report_procedure', 'payroll_report_procedure'):
            for invalid in ('', 'db.dbo.report', 'dbo.report; SELECT 1', 'dbo.report -- comment'):
                with self.subTest(field=field, invalid=invalid), self.assertRaisesRegex(ValidationError, field.upper()):
                    Settings(_env_file=None, **{field: invalid})

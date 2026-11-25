"""Verify environment mail control using fake reports and mocked SMTP only."""
import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.report_mail import send_subscribed_reports
from app.retirement_results import build_report_files
from test_payroll_builder import fixture_job


class MailControlTests(TestCase):
    def test_env_mail_flag_controls_both_builders_independently_of_scheduler_flag(self):
        job = fixture_job()
        reports = build_report_files(job, b'Client ID,earnings\n204,123.45\n')
        for enabled in (False, True):
            for scheduled in (False, True):
                for builder in ('Retirement Builder', 'Payroll Builder'):
                    with self.subTest(mail=enabled, scheduler=scheduled, builder=builder), \
                         TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), \
                         patch('app.report_mail.open_smtp') as smtp:
                        env = Path(directory) / '.env'
                        env.write_text(
                            f'MAIL_ENABLED={str(enabled).lower()}\nSCHEDULER_ENABLED={str(scheduled).lower()}\n'
                            'MAIL_USERNAME=sender@example.invalid\nMAIL_PASSWORD=fixture\n'
                            'MAIL_FROM_ADDRESS=sender@example.invalid\n'
                        )
                        result = send_subscribed_reports(Settings(_env_file=env), job, reports, builder_name=builder)
                        self.assertEqual(result.enabled, enabled)
                        self.assertEqual(result.accepted, int(enabled))
                        if enabled:
                            smtp.return_value.__enter__.return_value.send_message.assert_called_once()
                        else:
                            smtp.assert_not_called()

    def test_local_launcher_preserves_env_mail_flag_without_starting_a_server(self):
        script = Path(__file__).resolve().parents[1] / 'local_demo' / 'start.py'
        for enabled in ('false', 'true'):
            with self.subTest(mail=enabled), patch.dict(os.environ, {}, clear=True), \
                 patch.object(sys, 'argv', [str(script)]), patch.object(sys, 'path', list(sys.path)), \
                 patch('dotenv.dotenv_values', return_value={'DB_HOST': '127.0.0.1', 'DB_NAME': 'ecs', 'MAIL_ENABLED': enabled}), \
                 patch('uvicorn.run') as run:
                runpy.run_path(str(script), run_name='__main__')
                self.assertEqual(os.environ['MAIL_ENABLED'], enabled)
                run.assert_called_once_with('app.main:app', host='127.0.0.1', port=8001)

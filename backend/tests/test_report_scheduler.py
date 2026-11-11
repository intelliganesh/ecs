from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.report_mail import send_report_email
from app.report_scheduler import _run_scheduled_job, _scheduled_slot, _subscription_attachments
from app.retirement_results import build_report_files
from app.routers.retirement_builder import RetirementBuilderJob


class ScheduledReportTests(TestCase):
    def test_biweekly_uses_first_selected_weekday_and_midnight_grace(self):
        zone = ZoneInfo("Asia/Kolkata")
        schedule = {
            "startDateTime": datetime(2026, 11, 11),
            "ScheduleType": "B",
            "ScheduleWeek": 0,
            "MonthlyDate": None,
            "schedule_hr": "11",
            "schedule_min": "58",
            "schedules_session": "PM",
        }
        expected = datetime(2026, 11, 15, 18, 28, tzinfo=UTC)
        self.assertEqual(_scheduled_slot(schedule, datetime(2026, 11, 16, 0, 1, tzinfo=zone)), expected)
        self.assertIsNone(_scheduled_slot(schedule, datetime(2026, 11, 22, 23, 59, tzinfo=zone)))
        self.assertIsNone(_scheduled_slot(schedule, datetime(2026, 11, 16, 0, 3, tzinfo=zone)))

    def test_due_job_generates_grouped_files_and_notifies_only_once(self):
        now = datetime(2026, 11, 11, 16, 30, tzinfo=UTC)
        saved_schedule = {
            "startDateTime": now.replace(tzinfo=None),
            "ScheduleType": "D",
            "ScheduleWeek": 3,
            "MonthlyDate": "",
        }
        job = RetirementBuilderJob.model_validate({
            "id": 31,
            "general": {"fileName": "Test Report", "fileFormat": "CSV", "storeResultsToTable": True, "outputFileNameFormat": "Client ID"},
            "mapping": {"rows": [{"field": "Name"}]},
            "subscriptions": {"rows": [
                {"client": "1", "email": "qa@example.invalid, QA@example.invalid"},
                {"client": "2", "email": "other@example.invalid"},
            ]},
        })
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                _env_file=None, report_input_dir=root / "in", report_output_dir=root / "out",
                mail_enabled=True, mail_username="sender@example.invalid",
                mail_password="example-password", mail_from_address="sender@example.invalid",
            )
            settings.report_input_dir.mkdir()
            (settings.report_input_dir / "31.csv").write_text("Client ID,Name\n01,Test Person\n02,Another Person\n", encoding="utf-8")

            with (
                patch("app.report_scheduler.engine") as engine,
                patch("app.report_scheduler._read_full_job", return_value=job),
                patch("app.report_mail.open_smtp") as smtp,
                patch("app.routers.retirement_builder.store_results", return_value=2) as store,
            ):
                connection = engine.begin.return_value.__enter__.return_value
                locked_job = MagicMock()
                locked_job.scalar_one_or_none.return_value = job.id
                schedule = MagicMock()
                schedule.mappings.return_value.first.return_value = saved_schedule
                connection.execute.side_effect = [locked_job, schedule, MagicMock(), locked_job]

                _run_scheduled_job(settings, job.id, now, now)
                _run_scheduled_job(settings, job.id, now, now)

                files = sorted(settings.report_output_dir.rglob("*.csv"))
                self.assertEqual([path.name for path in files], ["01.csv", "02.csv"])
                self.assertEqual(files[0].read_bytes(), b"Name\r\nTest Person\r\n")
                self.assertEqual(files[1].read_bytes(), b"Name\r\nAnother Person\r\n")
                store.assert_called_once()
                messages = [
                    call.args[0] for call in smtp.return_value.__enter__.return_value.send_message.call_args_list
                ]
                self.assertEqual([str(message["To"]) for message in messages], ["qa@example.invalid", "other@example.invalid"])
                for message, file in zip(messages, files, strict=True):
                    (attachment,) = message.iter_attachments()
                    self.assertEqual(attachment.get_content_type(), "text/csv")
                    self.assertEqual(attachment.get_filename(), file.name)
                    self.assertEqual(attachment.get_payload(decode=True), file.read_bytes())

    def test_single_file_requires_subscription_to_every_client_in_it(self):
        job = RetirementBuilderJob.model_validate({
            "id": 31,
            "general": {"fileName": "Combined", "fileFormat": "CSV"},
            "mapping": {"rows": [{"field": "Name"}]},
            "subscriptions": {"rows": [
                {"client": "1", "email": "single@example.invalid; both@example.invalid"},
                {"client": "2", "email": "both@example.invalid"},
            ]},
        })
        reports = build_report_files(job, b"Client ID,Name\n01,Test Person\n02,Another Person\n")
        self.assertEqual(_subscription_attachments(job.subscriptions, reports), {"both@example.invalid": reports})
        unknown_client = build_report_files(job, b"Client ID,Name\n01,Test Person\n,Unknown Person\n")
        self.assertEqual(_subscription_attachments(job.subscriptions, unknown_client), {})


class ReportEmailTests(TestCase):
    def test_mail_switch_prevents_smtp_connection(self):
        job = RetirementBuilderJob.model_validate({
            "id": 31, "general": {"fileName": "Test", "fileFormat": "CSV"},
            "mapping": {"rows": [{"field": "Name"}]},
        })
        reports = build_report_files(job, b"Client ID,Name\n01,Test Person\n")
        with patch("app.report_mail.open_smtp") as connect:
            send_report_email(Settings(_env_file=None, mail_enabled=False), {"qa@example.invalid": reports}, 31)
            connect.assert_not_called()

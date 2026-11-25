"""Payroll scheduling/delivery regression tests; all external effects are mocked."""

from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app import payroll_scheduler as scheduler
from app import report_scheduler
from app.report_mail import send_subscribed_reports
from app.retirement_procedure import ProcedureResultSet, ProcedureSource
from app.retirement_results import ReportDateRange, build_report_files
from app.routers import payroll_builder as payroll
from test_payroll_builder import fixture_job


def source():
    return ProcedureSource((
        ProcedureResultSet(("valid_flag", "retnum", "sort1", "Wages"), (("1", "204", "2026-11-24", "Wages"),)),
        ProcedureResultSet(("valid_flag", "retnum", "sort1", "Wages"), (("1", "204", "2026-11-24", "123.45"),)),
        ProcedureResultSet(("valid_flag", "retnum", "sort1"), (("1", "204", "2026-11-24"),)),
    ))


class PayrollDeliveryTests(TestCase):
    def setUp(self):
        for target in ("pyodbc.connect", "smtplib.SMTP", "smtplib.SMTP_SSL"):
            guard = patch(target, side_effect=AssertionError("Live DB/SMTP access prohibited"))
            guard.start()
            self.addCleanup(guard.stop)
        self.now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        self.schedule = {"startDateTime": self.now.replace(tzinfo=None), "ScheduleType": "D",
                         "ScheduleWeek": "2", "MonthlyDate": ""}

    def test_payroll_scheduling_defaults_off_and_makes_no_connection(self):
        settings = Settings(_env_file=None)
        self.assertFalse(settings.payroll_scheduler_enabled)
        with patch.object(payroll, "engine") as engine:
            scheduler.run_due_payroll_reports(settings, ZoneInfo("UTC"))
            scheduler._run_scheduled_job(settings, 987654, self.now, self.now)
        engine.connect.assert_not_called()
        engine.begin.assert_not_called()

    def test_payroll_registration_requires_explicit_opt_in(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch.object(report_scheduler, "BackgroundScheduler") as factory:
                report_scheduler.start_scheduler(Settings(_env_file=None, payroll_scheduler_enabled=enabled))
                ids = [call.kwargs["id"] for call in factory.return_value.add_job.call_args_list]
                self.assertEqual(ids, ["retirement-reports", "payroll-reports"] if enabled else ["retirement-reports"])
                factory.return_value.start.assert_called_once()

    def test_payroll_reads_target_existing_payroll_tables(self):
        self.assertIn("FROM dbo.payroll_job\n", str(payroll.READS["READ_JOB"]))
        self.assertIn("FROM dbo.payroll_job AS j", str(scheduler.READ_ENABLED_SCHEDULES))
        self.assertIn("dbo.payroll_schedule_info", str(scheduler.READ_ENABLED_SCHEDULES))
        for query in (*payroll.READS.values(), scheduler.READ_ENABLED_SCHEDULES):
            self.assertNotIn("dbo.rjob", str(query))

    def test_scheduled_source_passes_s_flag_and_sentinel_dates_to_unchanged_sp(self):
        connection = MagicMock()
        cursor = connection.connection.cursor.return_value
        cursor.description = (("valid_flag",),)
        cursor.__iter__.return_value = iter((("1",),))
        cursor.nextset.return_value = False
        payroll._load_source(connection, fixture_job(), ReportDateRange(), scheduled=True)
        self.assertEqual(cursor.execute.call_args.args[1:], (987654, date(1900, 1, 1), date(1900, 1, 1), "S"))
        cursor.close.assert_called_once()

    def test_scheduled_output_and_delivery_follow_transaction_commit_and_run_once(self):
        events = []
        with TemporaryDirectory() as directory, patch.object(payroll, "engine") as engine, \
             patch.object(payroll, "_read_job", return_value=fixture_job()), \
             patch.object(payroll.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(payroll, "_load_source", return_value=source()) as load, \
             patch.object(payroll, "_record_status") as history, \
             patch.object(scheduler, "send_subscribed_reports", side_effect=lambda *a, **k: events.append("mail")) as mail:
            settings = Settings(_env_file=None, report_output_dir=Path(directory), scheduler_enabled=True,
                                payroll_scheduler_enabled=True)
            transaction = engine.begin.return_value
            connection = transaction.__enter__.return_value
            transaction.__exit__.side_effect = lambda *a: events.append("commit" if a[0] is None else "rollback") or False
            connection.execute.return_value.mappings.return_value.first.return_value = self.schedule
            for _ in range(2):
                scheduler._run_scheduled_job(settings, 987654, self.now, self.now)
            self.assertEqual(events, ["commit", "mail", "commit"])
            load.assert_called_once_with(connection, mail.call_args.args[1], ReportDateRange(), scheduled=True)
            self.assertEqual(history.call_args.kwargs, {"scheduled": True})
            self.assertEqual([p.relative_to(directory).as_posix() for p in Path(directory).rglob("*.csv")],
                             ["payroll/scheduled/987654/20261124T120000Z/Synthetic.csv"])
            mail.assert_called_once()
            self.assertEqual(mail.call_args.kwargs, {"builder_name": "Payroll Builder"})
            self.assertNotIn(987654, payroll._running)

    def test_scheduled_no_data_publishes_completion_marker(self):
        with TemporaryDirectory() as directory, patch.object(payroll, "engine") as engine, \
             patch.object(payroll, "_read_job", return_value=fixture_job()), \
             patch.object(payroll.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(payroll, "_load_source", return_value=source()) as load, \
             patch.object(payroll, "build_procedure_report_files", return_value=[]), \
             patch.object(payroll, "_record_status"), patch.object(scheduler, "send_subscribed_reports"):
            settings = Settings(_env_file=None, report_output_dir=Path(directory), scheduler_enabled=True,
                                payroll_scheduler_enabled=True)
            engine.begin.return_value.__enter__.return_value.execute.return_value.mappings.return_value.first.return_value = self.schedule
            scheduler._run_scheduled_job(settings, 987654, self.now, self.now)
            scheduler._run_scheduled_job(settings, 987654, self.now, self.now)
            self.assertEqual(len(list(Path(directory).rglob(".complete"))), 1)
            load.assert_called_once()

    def test_all_existing_extensions_prevent_scheduled_rerun(self):
        for suffix in (".csv", ".txt", ".tsv", ".complete"):
            with self.subTest(suffix=suffix), TemporaryDirectory() as directory, patch.object(payroll, "engine"), \
                 patch.object(payroll, "_attempt_run") as attempt:
                settings = Settings(_env_file=None, report_output_dir=Path(directory), scheduler_enabled=True,
                                    payroll_scheduler_enabled=True)
                output = Path(directory) / "payroll/scheduled/987654/20261124T120000Z"
                output.mkdir(parents=True)
                (output / ("existing" + suffix if suffix != ".complete" else suffix)).write_text("preserve")
                scheduler._run_scheduled_job(settings, 987654, self.now, self.now)
                attempt.assert_not_called()

    def test_disabled_or_changed_schedule_does_not_execute(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled), TemporaryDirectory() as directory, patch.object(payroll, "engine") as engine, \
                 patch.object(payroll, "_read_job", return_value=fixture_job()) as read, \
                 patch.object(payroll, "_attempt_run") as attempt:
                settings = Settings(_env_file=None, report_output_dir=Path(directory), scheduler_enabled=True,
                                    payroll_scheduler_enabled=True)
                read.return_value.general.enable = not disabled
                schedule = self.schedule if disabled else {**self.schedule, "startDateTime": datetime(2026, 12, 1)}
                engine.begin.return_value.__enter__.return_value.execute.return_value.mappings.return_value.first.return_value = schedule
                scheduler._run_scheduled_job(settings, 987654, self.now, self.now)
                attempt.assert_not_called()

    def test_manual_delivery_occurs_only_after_commit(self):
        events = []
        with TemporaryDirectory() as directory, patch.object(payroll, "engine") as engine, \
             patch.object(payroll, "_read_job", return_value=fixture_job()), \
             patch.object(payroll.shared, "_file_formats", return_value={"CSV": ","}), \
             patch.object(payroll, "_load_source", return_value=source()), \
             patch.object(payroll, "_record_status"), \
             patch.object(payroll, "get_settings", return_value=Settings(_env_file=None, report_output_dir=Path(directory))), \
             patch.object(payroll, "send_subscribed_reports", side_effect=lambda *a, **k: events.append("mail")):
            engine.begin.return_value.__exit__.side_effect = lambda *a: events.append("commit") or False
            payroll._run_job(987654, ReportDateRange(date(2026, 11, 1), date(2026, 11, 24)))
            self.assertEqual(events, ["commit", "mail"])

    def test_payroll_mail_merges_only_recipient_eligible_clients_for_each_format(self):
        for format_name, delimiter, extension in (("CSV", ",", "csv"), ("PIPE", "|", "txt"),
                ("SEMICOLON", ";", "txt"), ("TAB", "\t", "tsv"), ("TILDE", "~", "txt"), ("FIXED", " ", "txt")):
            with self.subTest(format=format_name), patch("app.report_mail.open_smtp") as smtp:
                settings = Settings(_env_file=None, mail_enabled=True, mail_username="sender@example.invalid",
                                    mail_password="fixture", mail_from_address="sender@example.invalid")
                job = fixture_job()
                job.general.fileFormat = format_name
                job.general.outputFileNameFormat = "Client ID"
                job.subscriptions.mergeFiles = True
                job.subscriptions.rows = [payroll.shared.SubscriptionRow(client="204", email="one@example.invalid;both@example.invalid"),
                                          payroll.shared.SubscriptionRow(client="205", email="both@example.invalid")]
                job.mapping.rows[0].length = "10"
                job.mapping.rows[0].startPosition = "1"
                reports = build_report_files(job, b"Client ID,earnings\n204,123.45\n205,456.78\n", delimiter=delimiter)
                result = send_subscribed_reports(settings, job, reports, builder_name="Payroll Builder")
                self.assertEqual((result.matched, result.accepted), (2, 2))
                messages = [call.args[0] for call in smtp.return_value.__enter__.return_value.send_message.call_args_list]
                self.assertEqual([str(m["To"]) for m in messages], ["one@example.invalid", "both@example.invalid"])
                for message in messages:
                    self.assertEqual(str(message["Subject"]), "Your Payroll Builder report is ready")
                    self.assertIn("Payroll Builder", message.get_body().get_content())
                    (attachment,) = message.iter_attachments()
                    self.assertTrue(attachment.get_filename().endswith("." + extension))
                    content = attachment.get_payload(decode=True).decode()
                    self.assertIn("123.45", content)
                    self.assertEqual("456.78" in content, str(message["To"]) == "both@example.invalid")

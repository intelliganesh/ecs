import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import StringIO
import json
import logging
from pathlib import Path
import smtplib
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import StatementError

from app.core.config import Settings
from app.core.error_logging import CentralErrorConsoleHandler, CentralErrorHandler, configure_error_logging, install_error_handlers
from app.report_mail import send_report_email


class LogFileMixin:
    def setUp(self):
        super().setUp()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log_file = Path(self.directory.name) / "logs/errors.log"
        self.settings = Settings(
            _env_file=None, error_log_file=self.log_file, mail_enabled=False,
            mail_password="fake-secret#123", db_password="fake-db-secret#456",
        )
        self.root = logging.getLogger()
        self.original_level = self.root.level
        self.original_handlers = self.root.handlers[:]
        self.original_propagation = {
            name: logging.getLogger(name).propagate for name in ("uvicorn", "uvicorn.error")
        }
        self.addCleanup(self.restore_logging)
        self.stderr_patch = patch("sys.stderr", StringIO())
        self.stderr_patch.start()
        self.addCleanup(self.stderr_patch.stop)
        configure_error_logging(self.settings)

    def restore_logging(self):
        for handler in self.root.handlers[:]:
            if isinstance(handler, (CentralErrorHandler, CentralErrorConsoleHandler)) and handler not in self.original_handlers:
                self.root.removeHandler(handler)
                handler.close()
        self.root.setLevel(self.original_level)
        for name, value in self.original_propagation.items():
            logging.getLogger(name).propagate = value
        logging.captureWarnings(False)

    def entries(self):
        return [json.loads(line) for line in self.log_file.read_text(encoding="utf-8").splitlines()]


class ErrorLoggingTests(LogFileMixin, TestCase):
    def test_shared_file_captures_app_scheduler_and_uvicorn_without_duplicate_setup(self):
        configure_error_logging(self.settings)
        for name in ("app.report_mail", "apscheduler.executors.default", "uvicorn.error"):
            logging.getLogger(name).warning("Failure from %s", name)
        logging.getLogger("app").info("This is not an error.")
        entries = self.entries()
        self.assertEqual([entry["logger"] for entry in entries], [
            "app.report_mail", "apscheduler.executors.default", "uvicorn.error",
        ])
        for entry in entries:
            self.assertEqual(entry["level"], "WARNING")
            self.assertEqual(datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).utcoffset().total_seconds(), 0)
            self.assertTrue(entry["source"]["line"])

    def test_exception_chain_keeps_stack_and_redacts_passwords_and_database_parameters(self):
        try:
            try:
                raise StatementError("failed", "SELECT private", {"ssn": "private-payroll-value"}, None)
            except StatementError as cause:
                raise RuntimeError("fake-secret#123 fake-db-secret%23456 password=other-secret") from cause
        except RuntimeError:
            logging.getLogger("app.test").exception("Operation failed.")
        text = self.log_file.read_text()
        for secret in ("fake-secret#123", "fake-db-secret%23456", "other-secret", "SELECT private", "private-payroll-value"):
            self.assertNotIn(secret, text)
        error = self.entries()[0]["exception"]
        self.assertEqual(error["type"], "RuntimeError")
        self.assertEqual(error["cause"]["type"], "StatementError")
        self.assertTrue(error["stack"])

    def test_mock_smtp_failure_records_response_and_job_without_sending(self):
        settings = self.settings.model_copy(update={"mail_enabled": True, "mail_username": "sender@example.invalid", "mail_from_address": "sender@example.invalid"})
        with patch("app.report_mail.open_smtp") as connect:
            smtp = connect.return_value.__enter__.return_value
            smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.139 Authentication blocked fake-secret#123")
            accepted = send_report_email(settings, {"recipient@example.invalid": []}, 60)
            smtp.send_message.assert_not_called()
        self.assertEqual(accepted, 0)
        entry = self.entries()[0]
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["job_id"], 60)
        self.assertEqual(entry["smtp_code"], 535)
        self.assertIn("5.7.139", entry["smtp_response"])
        self.assertEqual(entry["exception"]["type"], "SMTPAuthenticationError")
        self.assertNotIn("fake-secret#123", self.log_file.read_text())

    def test_rotation_preserves_newest_error_and_limits_backups(self):
        configure_error_logging(self.settings.model_copy(update={"error_log_max_bytes": 1024, "error_log_backup_count": 2}))
        for number in range(20):
            logging.getLogger("app.test").error("Error %s %s", number, "x" * 300)
        files = sorted(self.log_file.parent.glob("errors.log*"))
        self.assertEqual(len(files), 3)
        self.assertTrue(self.entries()[-1]["message"].startswith("Error 19 "))
        for file in files:
            for line in file.read_text().splitlines():
                json.loads(line)

    def test_threads_write_complete_json_lines_even_for_multiline_messages(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda number: logging.getLogger("app.test").error("Error %s\nsecond line", number), range(40)))
        entries = self.entries()
        self.assertEqual(len(entries), 40)
        self.assertEqual(len({entry["message"] for entry in entries}), 40)


class RequestErrorLoggingTests(LogFileMixin, IsolatedAsyncioTestCase):
    async def request(self, app, path, method="GET", body=b""):
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await app({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path,
            "query_string": b"password=do-not-log-query", "root_path": "",
            "headers": [(b"content-type", b"application/json")],
            "server": ("test", 80), "client": ("test", 123),
        }, receive, send)
        return messages

    async def test_handled_database_error_preserves_response_and_logs_cause(self):
        app = FastAPI()
        install_error_handlers(app)

        @app.get("/failure")
        def failure():
            try:
                raise StatementError("failed", "SELECT private", {"value": "private-payroll-value"}, None)
            except StatementError as cause:
                raise HTTPException(503, "Database unavailable") from cause

        messages = await self.request(app, "/failure")
        self.assertEqual(messages[0]["status"], 503)
        self.assertEqual(json.loads(messages[1]["body"]), {"detail": "Database unavailable"})
        entry = self.entries()[0]
        self.assertEqual(entry["status_code"], 503)
        self.assertEqual(entry["exception"]["cause"]["type"], "StatementError")
        self.assertEqual(entry["path"], "/failure")
        self.assertTrue(entry["request_id"])
        self.assertNotIn("do-not-log-query", self.log_file.read_text())
        self.assertNotIn("private-payroll-value", self.log_file.read_text())
        self.assertEqual(len(self.entries()), 1)

    async def test_explicit_error_response_is_also_logged(self):
        app = FastAPI()
        install_error_handlers(app)

        @app.get("/explicit-error")
        async def explicit_error():
            return JSONResponse({"detail": "Unavailable"}, status_code=503)

        messages = await self.request(app, "/explicit-error")
        self.assertEqual(messages[0]["status"], 503)
        self.assertEqual(self.entries()[0]["status_code"], 503)

    async def test_validation_does_not_log_body_and_concurrent_requests_have_separate_ids(self):
        app = FastAPI()
        install_error_handlers(app)

        @app.post("/validate")
        async def validate(count: int = Body()):
            return count

        responses = await asyncio.gather(*[
            self.request(app, "/validate", "POST", b'"private-body-value"') for _ in range(2)
        ])
        self.assertTrue(all(response[0]["status"] == 422 for response in responses))
        self.assertNotIn("private-body-value", self.log_file.read_text())
        self.assertEqual(len({entry["request_id"] for entry in self.entries()}), 2)

    async def test_unhandled_error_is_logged_and_still_raises(self):
        app = FastAPI()
        install_error_handlers(app)

        @app.get("/unhandled")
        async def unhandled():
            raise RuntimeError("Unexpected failure")

        with self.assertRaises(RuntimeError):
            await self.request(app, "/unhandled")
        entry = self.entries()[0]
        self.assertEqual(entry["exception"]["type"], "RuntimeError")
        self.assertEqual(entry["path"], "/unhandled")

"""Opt-in payroll scheduling using the existing procedure's scheduled contract."""

from contextlib import ExitStack
from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from pyodbc import Error as OdbcError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.report_files import report_directory
from app.report_mail import send_subscribed_reports
from app.report_scheduler import _scheduled_slot
from app.retirement_results import REPORT_EXTENSIONS, InvalidRun, ReportDateRange
from app.routers import payroll_builder as payroll


logger = logging.getLogger(__name__)
READ_ENABLED_SCHEDULES = text(str(payroll.shared.READ_ENABLED_SCHEDULES)
    .replace("dbo.rjob AS", "dbo.payroll_job AS")
    .replace("dbo.rjob_schedule_info", "dbo.payroll_schedule_info"))


def _run_scheduled_job(settings: Settings, job_id: int, slot: datetime, now: datetime) -> None:
    if not settings.scheduler_enabled or not settings.payroll_scheduler_enabled:
        return
    with payroll._run_lock:
        if job_id in payroll._running:
            return
        payroll._running.add(job_id)
    try:
        output = (report_directory(settings.report_output_dir) / "payroll" / "scheduled"
                  / str(job_id) / slot.strftime("%Y%m%dT%H%M%SZ"))
        with ExitStack() as resources, payroll.engine.begin() as connection:
            if connection.execute(payroll.LOCK_JOB, {"jobid": job_id}).scalar_one_or_none() is None:
                return
            if (output / ".complete").is_file() or any(
                path.is_file() and path.suffix.lower() in REPORT_EXTENSIONS for path in output.glob("*")
            ):
                return
            schedule = connection.execute(payroll.READS["READ_SCHEDULE"], {"jobid": job_id}).mappings().first()
            if schedule is None or _scheduled_slot(schedule, now) != slot:
                return
            job = payroll._read_job(connection, job_id)
            if job is None or not job.general.enable:
                return
            # The unchanged procedure computes scheduled date ranges from its S flag.
            result = payroll._attempt_run(
                connection, job, ReportDateRange(), settings, resources,
                scheduled=True, output=output,
            )
        if isinstance(result, Exception):
            raise result
        run, reports = result
        send_subscribed_reports(settings, job, reports, builder_name="Payroll Builder")
        logger.info("Scheduled payroll job %s generated %s rows.", job_id, run.rowCount)
    finally:
        with payroll._run_lock:
            payroll._running.discard(job_id)


def run_due_payroll_reports(settings: Settings, zone: ZoneInfo) -> None:
    if not settings.scheduler_enabled or not settings.payroll_scheduler_enabled:
        return
    now = datetime.now(zone)
    try:
        with payroll.engine.connect() as connection:
            schedules = connection.execute(READ_ENABLED_SCHEDULES).mappings().all()
    except (SQLAlchemyError, OdbcError):
        logger.exception("Could not read payroll schedules.")
        return
    for schedule in schedules:
        job_id = schedule["jobid"]
        try:
            slot = _scheduled_slot(schedule, now)
            if slot is not None:
                _run_scheduled_job(settings, job_id, slot, now)
        except (InvalidRun, OSError, SQLAlchemyError, OdbcError, ValueError):
            logger.exception("Scheduled payroll job %s failed.", job_id, extra={"job_id": job_id})

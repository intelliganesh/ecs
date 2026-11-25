from calendar import monthrange
from contextlib import ExitStack
from datetime import UTC, datetime, time, timedelta
import logging
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db import engine
from app.report_files import report_directory
from app.report_mail import send_subscribed_reports
from app.retirement_results import REPORT_EXTENSIONS, InvalidRun, ReportDateRange
from app.routers.retirement_builder import (
    LOCK_RUN_JOB, READ_ENABLED_SCHEDULES, READ_SCHEDULE,
    _attempt_report_run, _read_full_job, _read_report_source,
)


logger = logging.getLogger(__name__)
RUN_WINDOW = timedelta(minutes=5)


def _scheduled_slot(schedule: Mapping[str, Any], now: datetime) -> datetime | None:
    start = schedule["startDateTime"]
    if start is None:
        return None
    frequency = str(schedule["ScheduleType"]).strip().upper()
    weekday = str(schedule["ScheduleWeek"]).strip()
    selected_day = (int(weekday) - 1) % 7 if weekday in {"0", "1", "2", "3", "4", "5", "6"} else start.weekday()
    monthly_date = str(schedule["MonthlyDate"]).strip()
    month_day = int(monthly_date) if monthly_date.isdecimal() and int(monthly_date) > 0 else start.day
    hour = str(schedule.get("schedule_hr")).strip()
    minute = str(schedule.get("schedule_min")).strip()
    session = str(schedule.get("schedules_session")).strip().upper()
    run_time = start.time()
    if hour.isdecimal() and 1 <= int(hour) <= 12 and minute.isdecimal() and int(minute) < 60 and session in {"AM", "PM"}:
        run_time = time(int(hour) % 12 + (12 if session == "PM" else 0), int(minute))

    for day in (now.date(), now.date() - timedelta(days=1)):
        candidate = datetime.combine(day, run_time, tzinfo=now.tzinfo)
        utc_slot = candidate.astimezone(UTC)
        if day < start.date() or not timedelta(0) <= now.astimezone(UTC) - utc_slot < RUN_WINDOW:
            continue
        if utc_slot.astimezone(now.tzinfo).replace(tzinfo=None) != candidate.replace(tzinfo=None):
            continue  # The local time does not exist during a DST transition.
        if frequency == "D":
            return utc_slot
        if frequency == "W" and day.weekday() == selected_day:
            return utc_slot
        if frequency == "B" and day.weekday() == selected_day:
            first_day = start.date() + timedelta(days=(selected_day - start.weekday()) % 7)
            if (day - first_day).days % 14 == 0:
                return utc_slot
        if frequency in {"M", "MD"} and day.day == min(month_day, monthrange(day.year, day.month)[1]):
            return utc_slot
    return None


def _run_scheduled_job(settings: Settings, job_id: int, slot: datetime, now: datetime) -> None:
    run_dir = report_directory(settings.report_output_dir) / "scheduled" / str(job_id) / slot.strftime("%Y%m%dT%H%M%SZ")
    with ExitStack() as resources, engine.begin() as connection:
        if connection.execute(LOCK_RUN_JOB, {"jobid": job_id}).scalar_one_or_none() is None:
            return
        if (run_dir / ".complete").is_file() or any(
            path.is_file() and path.suffix.lower() in REPORT_EXTENSIONS for path in run_dir.glob("*")
        ):
            return
        saved_schedule = connection.execute(READ_SCHEDULE, {"jobid": job_id}).mappings().first()
        if saved_schedule is None or _scheduled_slot(saved_schedule, now) != slot:
            return
        job = _read_full_job(connection, job_id)
        if job is None or not job.general.enable:
            return
        date_range = ReportDateRange()
        result = _attempt_report_run(
            connection, job, lambda run_job: _read_report_source(
                connection, run_job, settings.report_input_dir, date_range, scheduled=True,
            ),
            run_dir, resources, scheduled=True,
            from_payroll_procedure=job.general.reportSource == "companyPayroll",
            date_range=date_range,
        )
    if isinstance(result, Exception):
        raise result
    run, reports = result
    send_subscribed_reports(settings, job, reports)
    logger.info("Scheduled retirement job %s generated %s rows.", job_id, run.rowCount)


def run_due_reports(settings: Settings, zone: ZoneInfo) -> None:
    now = datetime.now(zone)
    try:
        with engine.connect() as connection:
            schedules = connection.execute(READ_ENABLED_SCHEDULES).mappings().all()
    except SQLAlchemyError:
        logger.exception("Could not read retirement schedules.")
        return

    for schedule in schedules:
        job_id = schedule["jobid"]
        try:
            slot = _scheduled_slot(schedule, now)
            if slot is not None:
                _run_scheduled_job(settings, job_id, slot, now)
        except InvalidRun:
            logger.exception("Scheduled retirement job %s could not run.", job_id, extra={"job_id": job_id})
        except (OSError, SQLAlchemyError, ValueError):
            logger.exception("Scheduled retirement job %s failed.", job_id, extra={"job_id": job_id})


def start_scheduler(settings: Settings) -> BackgroundScheduler:
    zone = ZoneInfo(settings.scheduler_timezone)
    scheduler = BackgroundScheduler(timezone=zone)
    scheduler.add_job(
        run_due_reports, "interval", seconds=30, args=(settings, zone),
        next_run_time=datetime.now(UTC), id="retirement-reports", max_instances=1, coalesce=True,
    )
    if settings.payroll_scheduler_enabled:
        from app.payroll_scheduler import run_due_payroll_reports
        scheduler.add_job(
            run_due_payroll_reports, "interval", seconds=30, args=(settings, zone),
            next_run_time=datetime.now(UTC), id="payroll-reports", max_instances=1, coalesce=True,
        )
    scheduler.start()
    return scheduler

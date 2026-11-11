from calendar import monthrange
from contextlib import ExitStack
from datetime import UTC, datetime, time, timedelta
import logging
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db import engine
from app.report_files import report_directory
from app.report_mail import send_report_email
from app.retirement_results import InvalidRun, ReportFile
from app.routers.retirement_builder import (
    EMAIL_PATTERN, LOCK_RUN_JOB, READ_SCHEDULE, SubscriptionsForm, _execute_report_run, _read_full_job, _read_report_source,
)


logger = logging.getLogger(__name__)
RUN_WINDOW = timedelta(minutes=5)
READ_ENABLED_SCHEDULES = text("""
SELECT j.jobid, s.startDateTime, s.ScheduleType, s.ScheduleWeek, s.MonthlyDate,
       s.schedule_hr, s.schedule_min, s.schedules_session
FROM dbo.rjob AS j
JOIN dbo.rjob_schedule_info AS s ON j.jobid = s.jobid
WHERE j.isEnabled = 1 AND s.startDateTime IS NOT NULL
ORDER BY j.jobid
""")


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


def _client_id(value: str) -> str | None:
    value = value.strip()
    if value.isascii() and value.isdecimal():
        return value.lstrip("0") or "0"
    return None


def _subscription_attachments(subscriptions: SubscriptionsForm, reports: list[ReportFile]) -> dict[str, list[ReportFile]]:
    clients_by_recipient: dict[str, set[str]] = {}
    for subscription in subscriptions.rows:
        client = _client_id(subscription.client)
        if client is None:
            continue
        for address in re.split(r"[,;\n]", subscription.email):
            address = address.strip().lower()
            if EMAIL_PATTERN.fullmatch(address):
                clients_by_recipient.setdefault(address, set()).add(client)

    report_clients = [
        (report, {_client_id(client) for client in report.client_ids})
        for report in reports if report.client_ids
    ]
    attachments = {}
    for address, clients in clients_by_recipient.items():
        eligible = [report for report, required in report_clients if required <= clients]
        if eligible:
            attachments[address] = eligible
    return attachments


def _run_scheduled_job(settings: Settings, job_id: int, slot: datetime, now: datetime) -> None:
    run_dir = report_directory(settings.report_output_dir) / "scheduled" / str(job_id) / slot.strftime("%Y%m%dT%H%M%SZ")
    with ExitStack() as resources, engine.begin() as connection:
        if connection.execute(LOCK_RUN_JOB, {"jobid": job_id}).scalar_one_or_none() is None:
            return
        if (run_dir / ".complete").is_file() or any(run_dir.glob("*.csv")):
            return
        saved_schedule = connection.execute(READ_SCHEDULE, {"jobid": job_id}).mappings().first()
        if saved_schedule is None or _scheduled_slot(saved_schedule, now) != slot:
            return
        job = _read_full_job(connection, job_id)
        if job is None or not job.general.enable:
            return
        run, reports = _execute_report_run(
            connection, job, lambda: _read_report_source(connection, job, settings.report_input_dir),
            run_dir, resources, scheduled=True,
        )
    if settings.mail_enabled and reports and job.subscriptions.rows:
        attachments = _subscription_attachments(job.subscriptions, reports)
        if attachments:
            send_report_email(settings, attachments, job_id)
        else:
            logger.warning("No generated files matched the subscriptions for retirement job %s.", job_id)
    logger.info("Scheduled retirement job %s generated %s rows.", job_id, run.rowCount)


def run_due_reports(settings: Settings, zone: ZoneInfo) -> None:
    now = datetime.now(zone)
    try:
        with engine.connect() as connection:
            schedules = connection.execute(READ_ENABLED_SCHEDULES).mappings().all()
    except SQLAlchemyError as exc:
        logger.warning("Could not read retirement schedules (%s).", type(exc).__name__)
        return

    for schedule in schedules:
        job_id = schedule["jobid"]
        try:
            slot = _scheduled_slot(schedule, now)
            if slot is not None:
                _run_scheduled_job(settings, job_id, slot, now)
        except InvalidRun as exc:
            logger.warning("Scheduled retirement job %s could not run. %s", job_id, exc)
        except (OSError, SQLAlchemyError, ValueError) as exc:
            logger.warning("Scheduled retirement job %s failed (%s).", job_id, type(exc).__name__)


def start_scheduler(settings: Settings) -> BackgroundScheduler:
    zone = ZoneInfo(settings.scheduler_timezone)
    scheduler = BackgroundScheduler(timezone=zone)
    scheduler.add_job(
        run_due_reports, "interval", seconds=30, args=(settings, zone),
        next_run_time=datetime.now(UTC), id="retirement-reports", max_instances=1, coalesce=True,
    )
    scheduler.start()
    return scheduler

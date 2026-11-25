"""Payroll UI/API adapter. Existing SQL files, saved queries and SPs stay intact.

Normal API saves write payroll configuration only when invoked by a user. No
startup writes, migrations, data repair or live fixtures.
"""

from collections import OrderedDict
from concurrent.futures import Future
from contextlib import ExitStack
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import uuid4
import csv
import io
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pyodbc import Error as OdbcError
from sqlalchemy import column, table, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db import engine
from app.report_files import publish_report, report_directory
from app.report_mail import ReportEmailDelivery, send_subscribed_reports
from app.payroll_query_builder import payroll_record_queries
from app.retirement_datasets import multiple_datasets, query_column_names
from app.retirement_headers import aligned_detail_layout
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, build_procedure_report_files
from app.retirement_query_builder import ordered_mappings
from app.retirement_results import (
    InvalidRun, MAX_ROWS, MAX_SOURCE_BYTES, ReportDateRange, UNBOUNDED_RUN_DATE,
    file_name_format_code, record_type_code,
)
from app.routers import retirement_builder as shared


router = APIRouter(prefix="/payroll-builder", tags=["payroll-builder"])
QUERIES = {number: shared._load_query(str(number)) for number in (
    201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 217, 218, 219,
)}

# The two configuration schemas share these read contracts. Only this adapter's
# statements are adapted; the original constants and query.brl are unchanged.
READS = {
    name: text(str(getattr(shared, name)).replace("FROM dbo.rjob\n", "FROM dbo.payroll_job\n")
               .replace("dbo.rjob", "dbo.payroll"))
    for name in ("READ_JOB", "READ_SCHEDULE", "READ_MAPPINGS", "READ_SUBSCRIPTIONS",
                 "READ_SORTING", "READ_CONDITIONS", "READ_QUERY_CONFIGURATION")
}
READ_WAGES = text("SELECT job_id, client_id, wage_column, pay_code, search_word FROM dbo.payroll_wage_mapping WHERE job_id=:jobid")
READ_GROUPS = text("SELECT grouping_column FROM dbo.payroll_grouping WHERE job_id=:jobid ORDER BY grouping_column")
LOCK_JOB = text("SELECT jobid FROM dbo.payroll_job WITH (UPDLOCK, HOLDLOCK) WHERE jobid=:jobid")
READ_LIST = text("""
SELECT j.jobid,j.jobdesc,j.jobfilename,j.joblastmodified,j.filetype,j.isEnabled,
       j.ismerge,s.startDateTime,s.ScheduleType,s.ScheduleWeek,s.schedule_hr,
       s.schedule_min,s.schedules_session,h.Job_Last_Status,h.Job_Last_Message,
       h.Job_Last_Trigger_Date AS joblastrun
FROM dbo.payroll_job j
LEFT JOIN dbo.payroll_schedule_info s ON s.jobid=j.jobid
OUTER APPLY (
    SELECT TOP (1) Job_Last_Status,Job_Last_Message,Job_Last_Trigger_Date
    FROM dbo.payroll_history ph WHERE ph.Job_Id=j.jobid
    ORDER BY COALESCE(ph.Job_Update_Date,ph.Job_Create_Date) DESC,ph.Job_Last_Trigger_Date DESC
) h
ORDER BY j.isEnabled DESC,j.jobid DESC
""")
INSERT_HISTORY = text("""INSERT INTO dbo.payroll_history
    (Job_Id,Job_Create_Date,Job_Last_Trigger_Date,Job_Last_Status,Job_Last_Message,Job_Update_Date)
    VALUES (:jobid,GETDATE(),GETDATE(),:status,:message,GETDATE())""")
_create_lock = Lock()
_pending: dict[str, tuple[bytes, Future]] = {}
_completed: OrderedDict[str, tuple[bytes, Any, float]] = OrderedDict()
_run_lock = Lock()
_running: set[int] = set()


class PayrollSchedule(shared.ScheduleForm):
    dayInterval: int = Field(default=0, ge=0, le=shared.SQL_INT_MAX)
    weekInterval: int = Field(default=0, ge=0, le=shared.SQL_INT_MAX)
    monthlyWeekNo: str = Field(default="", max_length=255)
    monthlyDate: str = Field(default="", max_length=255)
    scheduleType: Literal["", "D", "W", "B", "M", "MD"] = ""

    @field_validator("monthlyDate")
    @classmethod
    def validate_monthly_date(cls, value):
        # Blank/zero are existing unset values; retain their stored spelling.
        if value in ("", "0") or (value.isascii() and value.isdecimal() and len(value) <= 2 and 1 <= int(value) <= 31):
            return value
        raise ValueError("Use a monthly date from 1 to 31, or leave it unset.")


class WageMapping(BaseModel):
    clientId: int = Field(ge=1, le=shared.SQL_INT_MAX)
    wageColumn: str = Field(min_length=1, max_length=50)
    payCode: str = Field(min_length=1, max_length=50)
    searchWord: str = Field(default="", max_length=50)


class PayrollJobInput(shared.RetirementBuilderJobInput):
    schedule: PayrollSchedule = Field(default_factory=PayrollSchedule)
    wageMappings: list[WageMapping] = Field(default_factory=list, max_length=1000)
    grouping: list[str] = Field(default_factory=list, max_length=100)


class PayrollJob(PayrollJobInput):
    id: int
    queryLocked: bool = False


def _rows(connection, statement, params=None):
    return [dict(row) for row in connection.execute(statement, params or {}).mappings().all()]


def _catalog(connection):
    return _rows(connection, text(QUERIES[210]))


def _column_type(declared):
    value = str(declared or "").lower().split("(", 1)[0]
    if value in {"numeric", "decimal", "int", "number", "money", "float"}:
        return "number"
    return "date" if value in {"date", "datetime", "datetime2"} else "text"


@router.get("/options")
def get_options():
    try:
        with engine.connect() as connection:
            catalog = _catalog(connection)
            formats = shared._file_formats(connection)
            # The established common format catalog is read, never seeded or changed.
            formatting = _rows(connection, text(shared.QUERY_53))
            groups = _rows(connection, text(QUERIES[219]))
        by_type, labels = shared._mapping_format_options(formatting)
        root = ET.parse(shared.OPTIONS_FILE).getroot()
        values = lambda name: [(node.text or "").strip() for node in root.findall(f"{name}/option")]
        columns = {str(row["mapping_column"]): str(row["mapping_column_desc"] or row["mapping_column"]).strip()
                   for row in catalog if row.get("mapping_column")}
        types = {key: _column_type(row.get("mapping_column_dt")) for row in catalog
                 if (key := row.get("mapping_column"))}
        types.update({columns[key]: value for key, value in list(types.items())})
        return {
            "fileFormats": list(formats),
            "outputFileNameFormats": [option.model_dump() for option in shared._output_file_name_formats(root)],
            "buildFrequencies": values("buildFrequencies"), "hours": values("hours"),
            "minutes": values("minutes"), "meridiems": values("meridiems"),
            "weekDays": values("weekDays"), "recordTypes": values("recordTypes"),
            "comparisonOperators": list(shared.COMPARISONS), "mappingColumns": list(columns.values()),
            "mappingColumnLabels": columns, "mappingColumnTypes": types,
            "mappingFormatsByType": by_type, "mappingFormatLabels": labels,
            "payrollMappingColumns": [], "payrollMappingColumnKeys": [], "payrollCompanies": {},
            "wageColumns": [{"value": row["mapping_column"], "label": columns[row["mapping_column"]]}
                            for row in catalog if str(row.get("ApplyGroup") or "").casefold() == "yes"],
            "groupingOptions": [{"value": row["grouping_id"], "label": row["grouping_desc"]} for row in groups],
        }
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Unable to load Payroll Builder options.") from exc


@router.get("/clients")
def get_clients():
    return shared.list_retirement_builder_clients()


def _pay_codes(connection, client_id):
    # Query 211 already supplies the client key; filter its catalog in the adapter.
    return [row for row in _rows(connection, text(QUERIES[211]))
            if str(row.get("u2_id") or "").strip().lstrip("0") == str(client_id)]


@router.get("/pay-codes")
def get_pay_codes(client_id: Annotated[int, Field(ge=1, le=shared.SQL_INT_MAX)], search: str = ""):
    try:
        with engine.connect() as connection:
            rows = _pay_codes(connection, client_id)
        found = {}
        for row in rows:
            key = str(row["pay_code"])
            label = str(row.get("pay_code_desc") or key)
            if search.casefold() in f"{key} {label}".casefold():
                found.setdefault(key, {"value": key, "label": label})
        return list(found.values())
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Unable to load client earning codes.") from exc


def _read_job(connection, job_id):
    params = {"jobid": job_id}
    sections = {key: _rows(connection, query, params) for key, query in READS.items()}
    if not sections["READ_JOB"]:
        return None
    main = sections["READ_JOB"][0]
    schedule = (sections["READ_SCHEDULE"] or [{}])[0]
    formats = shared._file_formats(connection)
    start = schedule.get("startDateTime")
    frequency = shared._schedule_label(schedule.get("ScheduleType")) or "Weekly"
    queries = [shared.QueryConfigurationRow(
        recttype=row.get("recttype") or "", query=row.get("Query") or "",
        conditions=row.get("Conditions") or "", sortOrder=row.get("Sort_Order") or "",
    ) for row in sections["READ_QUERY_CONFIGURATION"]]
    mappings = [shared.MappingRow(
        field=row.get("jobclientcolumn") or "", mappingColumn=row.get("jobfieldmapping") or "",
        defaultValue=row.get("jobdefaultvalue") or "", format=row.get("jobformat") or "",
        recordType=shared.RECORD_TYPE_LABELS.get(str(row.get("jobrectype") or "D").upper(), row.get("jobrectype") or "D"),
        startPosition=str(row.get("startposition") or 0), length=str(row.get("field_len") or 0),
        dataSetNo=row.get("DataSetNo") if row.get("DataSetNo") is not None else 1,
        colSeqNo=row.get("ColSeqNo"),
    ) for row in sections["READ_MAPPINGS"]]
    # Recover legacy NULL sequences only with unique saved-projection evidence.
    details = [row for row in mappings if record_type_code(row.recordType) == "D"]
    detail_queries = [row for row in queries if row.recttype.upper() == "D"]
    if details and len(detail_queries) == 1 and any(row.colSeqNo is None for row in details):
        try:
            aligned = aligned_detail_layout(query_column_names(detail_queries[0].query), details, detail_queries[0].query)
            replacement = {id(row): row.model_copy(update={"colSeqNo": i}) for i, row in enumerate(aligned, 1)}
            mappings = [replacement.get(id(row), row) for row in mappings]
        except InvalidRun:
            pass  # Read opaque legacy configurations without manufacturing an order.
    job = PayrollJob(
        id=job_id,
        general=shared.GeneralForm(
            fileName=main.get("jobfilename") or "", description=main.get("jobdesc") or "",
            fileFormat=shared._file_format_label(formats, main.get("filetype")),
            outputFileNameFormat=file_name_format_code(main.get("FileNameFormat") or ""),
            enable=bool(main.get("isEnabled")), storeResultsToTable=bool(main.get("StoreResults")), reportSource="csv",
        ),
        schedule=PayrollSchedule(
            startDate=start.date() if isinstance(start, datetime) else start,
            buildFrequency=frequency, hour=str(schedule.get("schedule_hr") or 4),
            minute=f"{int(schedule.get('schedule_min') or 0):02d}",
            meridiem=str(schedule.get("schedules_session") or "AM").strip(),
            week=shared._week_label(schedule.get("ScheduleWeek")) or "Thursday",
            dayInterval=schedule.get("dayInterval") or 0, weekInterval=schedule.get("weekInterval") or 0,
            monthlyWeekNo=str(schedule.get("MonthlyWeekNo") or ""), monthlyDate=str(schedule.get("MonthlyDate") or ""),
            scheduleType=str(schedule.get("ScheduleType") or ""),
        ),
        mapping={"includeHeader": bool(main.get("includeHeader")), "rows": mappings},
        subscriptions={"mergeFiles": bool(main.get("ismerge")), "rows": [
            {"client": str(row.get("jobclientid") or ""), "email": row.get("jobemailind") or ""}
            for row in sections["READ_SUBSCRIPTIONS"]]},
        fileSettings={
            "sortingOrder": [{"orderBy": str(row["sort_order"]), "mappingColumn": row["mapping_column"]}
                             for row in sections["READ_SORTING"]],
            "conditionalStatements": shared._visible_conditions(sections["READ_CONDITIONS"], sections["READ_QUERY_CONFIGURATION"]),
        },
        queryConfiguration=queries,
        wageMappings=[{"clientId": row["client_id"], "wageColumn": row["wage_column"],
                       "payCode": row["pay_code"], "searchWord": row.get("search_word") or ""}
                      for row in _rows(connection, READ_WAGES, params)],
        grouping=[row["grouping_column"] for row in _rows(connection, READ_GROUPS, params)],
    )
    if job.fileSettings.conditionalStatements:
        # A quoted ISO date is indistinguishable from text in the saved SQL.
        # Recover the UI value type from the actual payroll catalog, without
        # rewriting the stored condition or its value.
        types = {str(row["mapping_column"]).strip().casefold(): _column_type(row.get("mapping_column_dt"))
                 for row in _catalog(connection)}
        job.fileSettings.conditionalStatements = [
            row.model_copy(update={"valueType": types.get(row.mappingColumn.strip().casefold(), row.valueType)})
            for row in job.fileSettings.conditionalStatements
        ]
    return job


@router.get("/jobs")
def list_jobs():
    try:
        with engine.connect() as connection:
            rows = _rows(connection, READ_LIST)
            formats = shared._file_formats(connection)
        result = []
        for row in rows:
            # Avoid the retirement module's in-progress map: IDs can overlap.
            hour, minute = row.get("schedule_hr"), row.get("schedule_min")
            result.append({**row, "id": row["jobid"], "general": {
                "fileName": row.get("jobfilename") or "", "description": row.get("jobdesc") or "",
                "fileFormat": shared._file_format_label(formats, row.get("filetype")), "enable": bool(row.get("isEnabled")),
            }, "schedule": {"startDate": row.get("startDateTime"),
                "buildFrequency": shared._schedule_label(row.get("ScheduleType")),
                "week": shared._week_label(row.get("ScheduleWeek")),
                "hour": "" if hour is None else str(hour), "minute": "" if minute is None else f"{minute:02d}",
                "meridiem": row.get("schedules_session") or ""},
                "Job_Last_Status": "In Progress" if row["jobid"] in _running else row.get("Job_Last_Status")})
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Unable to load Payroll Builder jobs.") from exc


@router.get("/jobs/{job_id}")
def get_job(job_id: int):
    try:
        with engine.connect() as connection:
            job = _read_job(connection, job_id)
    except (SQLAlchemyError, OdbcError, ValueError) as exc:
        raise HTTPException(503, "Unable to load the Payroll Builder job.") from exc
    if job is None:
        raise HTTPException(404, "Payroll Builder job not found.")
    return {**job.model_dump(mode="json"), "schedule": {**job.schedule.model_dump(mode="json"),
            "startDateTime": shared._start_datetime(job.schedule)}}


def _merged(payload, original):
    data = original.model_dump()
    submitted = payload.model_dump(exclude_unset=True)
    for key, value in submitted.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return PayrollJobInput.model_validate(data)


def _validate_dataset_settings(job):
    if multiple_datasets(job):
        if job.general.storeResultsToTable:
            raise InvalidRun("Turn off Store Results to Table for multiple datasets.")
        if job.mapping.includeHeader and get_settings().retirement_header_source != "DETAIL_ALIGNED":
            raise InvalidRun("Multiple dataset headers require RETIREMENT_HEADER_SOURCE=DETAIL_ALIGNED.")


def _validate_schedule(payload, original=None, submitted=None):
    schedule = payload.schedule
    controls = {"buildFrequency", "hour", "minute", "meridiem", "week", "dayInterval", "weekInterval",
                "monthlyWeekNo", "monthlyDate", "scheduleType"}
    if schedule.startDate is None:
        if original is not None and submitted is None:
            configured = any(getattr(schedule, key) != getattr(original.schedule, key) for key in controls)
        else:
            incoming = submitted.schedule if submitted is not None else schedule
            configured = any(key in incoming.model_fields_set and getattr(incoming, key) not in ("", "0", 0, None)
                             for key in controls)
        if configured:
            shared._field_error(["schedule", "startDate"], "Choose a start date for a scheduled payroll job.")
    expected = shared._schedule_type(schedule.buildFrequency)
    frequency_changed = original is not None and schedule.buildFrequency != original.schedule.buildFrequency
    if frequency_changed:
        # The UI submits the frequency label and preserves hidden legacy values.
        schedule.scheduleType = ""
    elif schedule.scheduleType and schedule.scheduleType != expected and not (expected == "M" and schedule.scheduleType == "MD"):
        shared._field_error(["schedule", "scheduleType"], "Schedule type must match the selected build frequency.")


def _normalized(connection, payload, original=None, *, submitted=None):
    _validate_schedule(payload, original, submitted)
    if payload.general.reportSource != "csv":
        shared._field_error(["general", "reportSource"], "Payroll Builder uses its saved payroll procedure source.")
    catalog = _catalog(connection)
    keys = {}
    types = {}
    for row in catalog:
        key = str(row.get("mapping_column") or "")
        keys[key.strip().casefold()] = key
        keys.setdefault(str(row.get("mapping_column_desc") or "").strip().casefold(), key)
        types[key] = _column_type(row.get("mapping_column_dt"))
    def resolve(value, *, rule=False):
        key = keys.get(value.strip().casefold())
        if not key:
            raise HTTPException(422, f'Choose a configured payroll mapping column: "{value}".')
        if rule and key.strip().casefold() == "default":
            raise HTTPException(422, "Default is a constant mapping option; choose a source column for sorting or conditions.")
        return key
    normalized = []
    for row in payload.mapping.rows:
        source = resolve(row.mappingColumn or row.field)
        normalized.append(row.model_copy(update={"mappingColumn": source, "recordType": record_type_code(row.recordType or "D")}))
    mappings = ordered_mappings(normalized)
    if not any(row.recordType == "D" for row in mappings):
        raise HTTPException(422, "Add at least one Detail mapping.")
    payload = payload.model_copy(update={"mapping": payload.mapping.model_copy(update={"rows": mappings})})
    sorting = [row.model_copy(update={"mappingColumn": resolve(row.mappingColumn, rule=True)}) for row in payload.fileSettings.sortingOrder]
    conditions = []
    for index, row in enumerate(payload.fileSettings.conditionalStatements):
        source = resolve(row.mappingColumn, rule=True)
        kind = types[source]
        path = ["fileSettings", "conditionalStatements", index, "value"]
        if row.valueType is not None and row.valueType != kind:
            shared._field_error(path, f"Use a {kind} value for this payroll column.")
        if kind == "number":
            try:
                if not Decimal(row.value.strip()).is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                shared._field_error(path, "Enter a number for this payroll column.")
        elif kind == "date":
            try:
                if shared.condition_date(row.value) is None:
                    raise InvalidRun("Enter a valid date in YYYY-MM-DD format.")
            except InvalidRun as exc:
                shared._field_error(path, str(exc))
        conditions.append(row.model_copy(update={"mappingColumn": source, "valueType": kind}))
    payload.fileSettings = payload.fileSettings.model_copy(update={"sortingOrder": sorting, "conditionalStatements": conditions})
    shared._validate_payload(payload, creating=original is None)
    _validate_dataset_settings(payload)
    if original:
        if payload.queryConfiguration != original.queryConfiguration:
            raise HTTPException(422, "Report queries are generated from mappings; arbitrary SQL is not accepted.")
    elif payload.queryConfiguration:
        raise HTTPException(422, "Report queries are generated from mappings; arbitrary SQL is not accepted.")
    if shared.is_fixed_format(payload.general.fileFormat):
        for kind in ("H", "D", "T"):
            if kind == "H" and payload.mapping.includeHeader:
                continue
            for dataset in {row.dataSetNo for row in mappings if row.recordType == kind}:
                shared.fixed_layout([row for row in mappings if row.recordType == kind and row.dataSetNo == dataset])
    subscribed = set()
    for row in payload.subscriptions.rows:
        shared._check_integer(row.client, 1, shared.SQL_INT_MAX, ["subscriptions", "rows", "client"])
        if row.companyId is not None or int(row.client) in subscribed:
            raise HTTPException(422, "Use each subscribed client once.")
        subscribed.add(int(row.client))
    groupable = {row["mapping_column"] for row in catalog if str(row.get("ApplyGroup") or "").lower() == "yes"}
    codes, seen = {}, set()
    for wage in payload.wageMappings:
        key = (wage.clientId, wage.wageColumn, wage.payCode)
        if wage.clientId not in subscribed or wage.wageColumn not in groupable or key in seen:
            raise HTTPException(422, "Choose a subscribed client, an available wage field and a distinct earning-code mapping.")
        seen.add(key)
        if wage.clientId not in codes:
            codes[wage.clientId] = {str(row["pay_code"]) for row in _pay_codes(connection, wage.clientId)}
        # Unchanged historical codes remain valid even if no longer in the active catalog.
        if wage.payCode not in codes[wage.clientId] and not (original and wage in original.wageMappings):
            raise HTTPException(422, "Choose an earning code belonging to the selected client.")
    groups = {row["grouping_id"] for row in _rows(connection, text(QUERIES[219]))}
    if len(set(payload.grouping)) != len(payload.grouping) or set(payload.grouping) - groups:
        raise HTTPException(422, "Choose distinct configured grouping fields.")
    if shared._file_format_delimiter(shared._file_formats(connection), payload.general.fileFormat) is None:
        raise HTTPException(422, "Select a configured file format.")
    filename_format = payload.general.outputFileNameFormat
    # The shared reader intentionally falls back for historical saved jobs.
    # Saves must reject unknown input; FILE_NAME is the older UI's filename code.
    if shared.parse_file_name_format(filename_format) is None and filename_format.strip().upper() != "FILE_NAME":
        raise HTTPException(422, "Select a configured output filename format.")
    try:
        shared._stored_file_name_format(filename_format)
    except ValueError as exc:
        raise HTTPException(422, "Select a configured output filename format.") from exc
    return payload


def _execute(connection, number, values):
    return connection.execute(*shared._prepared_query(QUERIES[number], values))


def _clear(connection, name, job_id, key="jobid"):
    target = table(name, column(key), schema="dbo")
    connection.execute(target.delete().where(target.c[key] == job_id))


def _query_inputs(job):
    """Compare only settings that affect generated projections, filters or sorting."""
    mapping = job.mapping.model_dump()
    mapping["rows"] = [row.model_copy(update={"recordType": record_type_code(row.recordType or "D")}).model_dump()
                       for row in ordered_mappings(job.mapping.rows)]
    return mapping, job.fileSettings.model_dump()


def _write_details(connection, job_id, payload, *, creating, rebuild_queries=False):
    if creating or rebuild_queries:
        queries = payroll_record_queries(payload)
        if not creating:
            _execute(connection, 203, {"jobid": job_id})
        sort = ", " + ", ".join(shared.sql_identifier(row.mappingColumn) + (" DESC" if row.direction == "DESC" else "")
                                for row in sorted(payload.fileSettings.sortingOrder, key=lambda row: int(row.orderBy))) if payload.fileSettings.sortingOrder else ""
        for row in queries:
            _execute(connection, 204, {"jobid": job_id, "recttype": row["recttype"], "Query": row["query"],
                "conditionalStmt": row.get("conditions", ""), "sortOrder": sort if row["recttype"] == "D" else ""})
        for row in payload.fileSettings.sortingOrder:
            _execute(connection, 208, {"jobid": job_id, "order": int(row.orderBy), "mapping": row.mappingColumn})
        for row in payload.fileSettings.conditionalStatements:
            if row.valueType in ("text", "date") or shared.condition_date(row.value) is not None:
                continue  # Preserved in the varchar Conditions contract, not numeric storage.
            _execute(connection, 209, {"jobid": job_id, "mapping": row.mappingColumn, "Symbol": row.condition, "val": row.value})
    else:
        # Unrelated edits preserve existing projections, including legacy expressions.
        for name, key in (("payroll_file_detail", "jobid"), ("payroll_client_detail", "jobid"),
                          ("payroll_schedule_info", "jobid"), ("payroll_wage_mapping", "job_id"), ("payroll_grouping", "job_id")):
            _clear(connection, name, job_id, key)
    schedule = payload.schedule
    _execute(connection, 207, {"jobid": job_id, "jobName": payload.general.fileName,
        "startDateTime": shared._start_datetime(schedule), "dayInterval": schedule.dayInterval,
        "weekInterval": schedule.weekInterval, "rbJobTypeChk": schedule.buildFrequency,
        "ScheduleType": schedule.scheduleType or shared._schedule_type(schedule.buildFrequency),
        "MonthlyWeekNo": schedule.monthlyWeekNo, "MonthlyDate": schedule.monthlyDate,
        "ScheduleWeek": shared._schedule_week(schedule.week), "schedule_hr": int(schedule.hour),
        "schedule_min": int(schedule.minute), "schedule_session": schedule.meridiem})
    for row in payload.mapping.rows:
        _execute(connection, 205, {"jobid": job_id, "jobclientcolumn": row.field, "jobfieldmapping": row.mappingColumn,
            "jobdefaultvalue": row.defaultValue, "jobformat": row.format, "jobrectype": row.recordType,
            "startposition": int(row.startPosition or 0), "field_len": int(row.length or 0),
            "datasetNo": row.dataSetNo, "colSeqNo": row.colSeqNo})
    for row in payload.subscriptions.rows:
        _execute(connection, 206, {"jobid": job_id, "jobclientid": int(row.client), "jobemailind": row.email})
    for row in payload.wageMappings:
        _execute(connection, 212, {"jobid": job_id, "clientid": row.clientId, "wagecolumn": row.wageColumn,
            "paycode": row.payCode, "searchWord": row.searchWord})
    for group in payload.grouping:
        _execute(connection, 213, {"jobid": job_id, "job_grouping_column": group})


def _main_values(payload):
    return {"jobdesc": payload.general.description, "jobfilename": payload.general.fileName, "jobstatus": "Active",
        "filetype": payload.general.fileFormat, "ismerge": payload.subscriptions.mergeFiles,
        "mergeemail": ", ".join(row.email for row in payload.subscriptions.rows if row.email),
        "includeHRecord": payload.mapping.includeHeader,
        "fileNameFormat": shared._stored_file_name_format(payload.general.outputFileNameFormat),
        "isEnabled": payload.general.enable, "StoreResult": payload.general.storeResultsToTable, "enddate": None}


def _create(payload):
    try:
        with engine.begin() as connection:
            payload = _normalized(connection, payload)
            job_id = shared._execute_identity_query(connection, QUERIES[201], _main_values(payload))
            _write_details(connection, job_id, payload, creating=True)
            created = _read_job(connection, job_id)
            if created is None:
                raise HTTPException(500, "The saved Payroll Builder job could not be retrieved.")
            return created
    except (SQLAlchemyError, OdbcError) as exc:
        raise HTTPException(503, "Unable to save the Payroll Builder job.") from exc
    except InvalidRun as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/jobs", status_code=201)
def create_job(payload: PayrollJobInput,
               idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128, pattern=r"^[!-~]+$")] = None):
    if idempotency_key is None:
        return _create(payload)
    fingerprint = sha256(payload.model_dump_json(exclude_unset=True).encode()).digest()
    with _create_lock:
        for key in list(_completed):
            if _completed[key][2] <= monotonic():
                del _completed[key]
        prior = _completed.get(idempotency_key) or _pending.get(idempotency_key)
        if prior and prior[0] != fingerprint:
            raise HTTPException(409, "This Idempotency-Key was used with a different request.")
        if idempotency_key in _completed:
            return prior[1]
        if idempotency_key in _pending:
            pending = prior[1]
        else:
            pending = None
            future = Future()
            _pending[idempotency_key] = (fingerprint, future)
    if pending:
        return pending.result()
    try:
        result = _create(payload)
    except BaseException as exc:
        with _create_lock:
            del _pending[idempotency_key]
            future.set_exception(exc)
        raise
    with _create_lock:
        del _pending[idempotency_key]
        _completed[idempotency_key] = (fingerprint, result, monotonic() + shared.IDEMPOTENCY_TTL)
        if len(_completed) > shared.IDEMPOTENCY_LIMIT:
            _completed.popitem(last=False)
        future.set_result(result)
    return result


@router.put("/jobs/{job_id}")
def update_job(job_id: int, payload: PayrollJobInput):
    try:
        with engine.begin() as connection:
            if connection.execute(LOCK_JOB, {"jobid": job_id}).scalar_one_or_none() is None:
                raise HTTPException(404, "Payroll Builder job not found.")
            original = _read_job(connection, job_id)
            if original is None:
                raise HTTPException(404, "Payroll Builder job not found.")
            effective = _normalized(connection, _merged(payload, original), original, submitted=payload)
            _execute(connection, 202, {**_main_values(effective), "jobid": job_id})
            rebuild_queries = _query_inputs(effective) != _query_inputs(original)
            _write_details(connection, job_id, effective, creating=False, rebuild_queries=rebuild_queries)
            return _read_job(connection, job_id)
    except (SQLAlchemyError, OdbcError) as exc:
        raise HTTPException(503, "Unable to update the Payroll Builder job.") from exc
    except InvalidRun as exc:
        raise HTTPException(422, str(exc)) from exc


def _load_source(connection, job, dates, *, scheduled=False):
    schema, procedure = get_settings().payroll_report_procedure.split(".")
    cursor = connection.connection.cursor()
    result_sets, count = [], 0
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    try:
        cursor.execute(f"EXEC [{schema}].[{procedure}] @client_id=?, @paystartdate=?, @payenddate=?, @runType=?",
                       job.id, dates.start, dates.end, "S" if scheduled else "A")
        while True:
            if cursor.description is not None:
                columns = tuple(str(item[0] or "") for item in cursor.description)
                writer.writerow(columns)
                rows = []
                for row in cursor:
                    count += 1
                    if count > MAX_ROWS:
                        raise InvalidRun(f"The procedure can return up to {MAX_ROWS:,} rows.")
                    values = tuple("" if value is None else value.date().isoformat() if isinstance(value, datetime) else str(value) for value in row)
                    rows.append(values)
                    writer.writerow(values)
                    if buffer.tell() > MAX_SOURCE_BYTES:
                        raise InvalidRun("The payroll output exceeds the 5 MB source limit.")
                result_sets.append(ProcedureResultSet(columns, tuple(rows)))
            if not cursor.nextset():
                break  # Drain trailing history writes and surface their errors.
    finally:
        cursor.close()
    if not result_sets or len(buffer.getvalue().encode()) > MAX_SOURCE_BYTES:
        raise InvalidRun("The payroll procedure returned no usable result or exceeded the source limit.")
    return ProcedureSource(tuple(result_sets))


def _record_status(connection, job_id, status, message, *, scheduled=False):
    result = _execute(connection, 217 if scheduled else 218, {"JOB_ID": job_id, "STATUS": status, "STAT_MSG": message})
    if result.rowcount == 0:
        connection.execute(INSERT_HISTORY, {"jobid": job_id, "status": status, "message": message})


def _execute_run(connection, job, dates, settings, resources, *, scheduled=False, output=None):
    delimiter = shared._file_format_delimiter(shared._file_formats(connection), job.general.fileFormat)
    if delimiter is None:
        raise InvalidRun("Select a configured file format.")
    source = _load_source(connection, job, dates, scheduled=scheduled)
    reports = build_procedure_report_files(job, source, delimiter)
    run_id = uuid4()
    if output is None:
        output = report_directory(settings.report_output_dir) / "payroll" / "manual" / str(job.id) / str(run_id)
    for report in reports:
        resources.enter_context(publish_report(output / report.file_name, report.csv))
    count = sum(row.record_type == "D" for report in reports for row in report.rows)
    message = f"Generated {count} rows." if reports else "No matching records. No files generated."
    if scheduled and not reports:
        resources.enter_context(publish_report(output / ".complete", ""))
    _record_status(connection, job.id, "Success", message, **({"scheduled": True} if scheduled else {}))
    files = [shared.RetirementBuilderOutput(fileName=report.file_name, csv=report.csv, excelRows=report.excel_rows) for report in reports]
    run = shared.RetirementBuilderRun(runId=run_id, rowCount=count, storedRows=0, delimiter=delimiter,
        fileName=files[0].fileName if files else "", csv=files[0].csv if files else "", files=files,
        excelRows=files[0].excelRows if files else None,
        emailDelivery=ReportEmailDelivery(enabled=False))
    return run, reports


def _attempt_run(connection, job, dates, settings, resources, *, scheduled=False, output=None):
    _validate_dataset_settings(job)  # Must precede the potentially writing procedure.
    try:
        with ExitStack() as attempt:
            with connection.begin_nested():
                result = _execute_run(connection, job, dates, settings, attempt, scheduled=scheduled, output=output)
            resources.enter_context(attempt.pop_all())
        return result
    except (InvalidRun, SQLAlchemyError, OdbcError, OSError) as exc:
        message = str(exc)[:255] if isinstance(exc, InvalidRun) else "Unable to complete the payroll report."
        _record_status(connection, job.id, "Failed", message, **({"scheduled": True} if scheduled else {}))
        return exc


def _run_job(job_id, dates):
    settings = get_settings()
    with _run_lock:
        if job_id in _running:
            raise HTTPException(409, "This payroll job is already running.")
        _running.add(job_id)
    try:
        with ExitStack() as resources, engine.begin() as connection:
            if connection.execute(LOCK_JOB, {"jobid": job_id}).scalar_one_or_none() is None:
                raise HTTPException(404, "Payroll Builder job not found.")
            job = _read_job(connection, job_id)
            if job is None:
                raise HTTPException(404, "Payroll Builder job not found.")
            if not job.general.enable:
                raise HTTPException(409, "Enable the job before running it.")
            result = _attempt_run(connection, job, dates, settings, resources)
        # Raise after the outer transaction commits the failure status.
        if isinstance(result, Exception):
            raise result
        run, reports = result
        run.emailDelivery = send_subscribed_reports(settings, job, reports, builder_name="Payroll Builder")
        return run
    except InvalidRun as exc:
        raise HTTPException(422, str(exc)) from exc
    except (SQLAlchemyError, OdbcError, OSError) as exc:
        raise HTTPException(500, "The payroll job could not be completed. Report output was not saved.") from exc
    finally:
        with _run_lock:
            _running.discard(job_id)


@router.post("/jobs/{job_id}/run", response_model=shared.RetirementBuilderRun)
async def run_job(job_id: int, request: Request, start_date: date | None = None, end_date: date | None = None):
    if start_date is None or end_date is None or start_date == UNBOUNDED_RUN_DATE or end_date == UNBOUNDED_RUN_DATE:
        raise HTTPException(422, "Choose a start date and end date for the payroll report.")
    if start_date > end_date:
        raise HTTPException(422, "Start Date must be on or before End Date.")
    async for chunk in request.stream():
        if chunk:
            raise HTTPException(415, "Payroll reports use the saved procedure source; upload overrides are not supported.")
    return await run_in_threadpool(_run_job, job_id, ReportDateRange(start_date, end_date))

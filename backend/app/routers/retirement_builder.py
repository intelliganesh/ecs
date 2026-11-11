from collections import Counter, OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from contextlib import ExitStack, contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from hashlib import sha256
from pathlib import Path
import re
from threading import Lock
from time import monotonic
from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID, uuid4
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db import engine
from app.report_files import load_report_source, publish_report, report_directory
from app.retirement_results import MAPPING_FORMATS_BY_TYPE, MAX_SOURCE_BYTES, InvalidRun, ReportFile, build_report_files, store_results


router = APIRouter(prefix="/retirement-builder", tags=["retirement-builder"])


class GeneralForm(BaseModel):
    testfileName: str = ""
    fileName: str = ""
    fileFormat: str = ""
    description: str = ""
    outputFileNameFormat: str = ""
    enable: bool = True
    storeResultsToTable: bool = False
    selectedFile: str = ""


class ScheduleForm(BaseModel):
    startDate: date | None = None
    buildFrequency: Literal["Daily", "Weekly", "Bi-Weekly", "Monthly"] = "Weekly"
    hour: str = "4"
    minute: str = "00"
    meridiem: Literal["AM", "PM"] = "AM"
    week: Literal[
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ] = "Thursday"


class MappingRow(BaseModel):
    field: str = ""
    startPosition: str = ""
    length: str = ""
    recordType: str = ""
    defaultValue: str = ""
    mappingColumn: str = ""
    format: str = ""


class MappingForm(BaseModel):
    includeHeader: bool = True
    rows: list[MappingRow] = Field(default_factory=list)


class SubscriptionRow(BaseModel):
    client: str = ""
    email: str = ""


class SubscriptionsForm(BaseModel):
    mergeFiles: bool = False
    rows: list[SubscriptionRow] = Field(default_factory=list)


class SortingOrderRow(BaseModel):
    orderBy: str = ""
    mappingColumn: str = ""
    direction: Literal["ASC", "DESC"] = "ASC"


class ConditionalStatementRow(BaseModel):
    mappingColumn: str = ""
    condition: str = ""
    value: str = ""


class FileSettingsForm(BaseModel):
    sortingOrder: list[SortingOrderRow] = Field(default_factory=list)
    conditionalStatements: list[ConditionalStatementRow] = Field(default_factory=list)


class QueryConfigurationRow(BaseModel):
    recttype: str = ""
    query: str = ""
    conditions: str = ""
    sortOrder: str = ""


class RetirementBuilderJob(BaseModel):
    id: int
    general: GeneralForm = Field(default_factory=GeneralForm)
    schedule: ScheduleForm = Field(default_factory=ScheduleForm)
    mapping: MappingForm = Field(default_factory=MappingForm)
    subscriptions: SubscriptionsForm = Field(default_factory=SubscriptionsForm)
    fileSettings: FileSettingsForm = Field(default_factory=FileSettingsForm)
    queryConfiguration: list[QueryConfigurationRow] = Field(default_factory=list)


class RetirementBuilderJobInput(BaseModel):
    general: GeneralForm = Field(default_factory=GeneralForm)
    schedule: ScheduleForm = Field(default_factory=ScheduleForm)
    mapping: MappingForm = Field(default_factory=MappingForm)
    subscriptions: SubscriptionsForm = Field(default_factory=SubscriptionsForm)
    fileSettings: FileSettingsForm = Field(default_factory=FileSettingsForm)
    queryConfiguration: list[QueryConfigurationRow] = Field(default_factory=list)


class RetirementBuilderOutput(BaseModel):
    fileName: str
    csv: str


class RetirementBuilderRun(RetirementBuilderOutput):
    runId: UUID
    rowCount: int
    storedRows: int
    files: list[RetirementBuilderOutput]


class RetirementBuilderOptions(BaseModel):
    fileFormats: list[str]
    outputFileNameFormats: list[str]
    buildFrequencies: list[str]
    hours: list[str]
    minutes: list[str]
    meridiems: list[str]
    weekDays: list[str]
    recordTypes: list[str]
    sortDirections: list[Literal["ASC", "DESC"]]
    mappingColumns: list[str]
    mappingFormats: list[str]
    mappingColumnTypes: dict[str, str]
    mappingFormatsByType: dict[str, list[str]]


SQL_INT_MAX = 2_147_483_647
SQL_DATETIME_MIN = date(1753, 1, 1)
CONDITION_MAX = Decimal("9999999999999999.99")
EMAIL_PATTERN = re.compile(
    r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*",
    re.IGNORECASE | re.ASCII,
)
IDEMPOTENCY_TTL = 3600
IDEMPOTENCY_LIMIT = 1024
_idempotency_lock = Lock()
_active_runs_lock = Lock()
_active_runs: Counter[int] = Counter()
_failed_runs: set[int] = set()
_pending_creates: dict[str, tuple[bytes, Future[RetirementBuilderJob]]] = {}
_completed_creates: OrderedDict[str, tuple[bytes, RetirementBuilderJob, float]] = OrderedDict()


def _load_query(sql_id: str) -> str:
    query_file = Path(__file__).resolve().parents[2] / "query.brl"
    root = ET.parse(query_file).getroot()
    for statement in root.findall("sql"):
        if statement.get("sqlid") == sql_id:
            query = (statement.text or "").strip()
            if query:
                return query
    raise RuntimeError(f"SQL query {sql_id} was not found in {query_file}")


QUERY_42 = _load_query("42")
QUERY_30 = _load_query("30")
QUERY_44 = _load_query("44")
QUERY_45 = _load_query("45")
QUERY_31 = _load_query("31")
QUERY_35 = _load_query("35")
QUERY_36 = _load_query("36")
QUERY_37 = _load_query("37")
QUERY_38 = _load_query("38")
QUERY_52 = _load_query("52")
QUERY_54 = _load_query("54")
QUERY_55 = _load_query("55")
OPTIONS_FILE = Path(__file__).resolve().parents[2] / "config" / "options.xml"

READ_JOB = text("""
SELECT jobid, jobdesc, jobfilename, jobstatus, joblastmodified, joblastrun,
       filetype, ismerge, mergeemail, includeHeader, FileNameFormat,
       isEnabled, StoreResults, enddate
FROM dbo.rjob
WHERE jobid = :jobid
""")
READ_SCHEDULE = text("""
SELECT jobid, jobName, startDateTime, dayInterval, weekInterval,
       rbJobTypeChk, ScheduleType, MonthlyWeekNo, ScheduleWeek, MonthlyDate,
       schedule_hr, schedule_min, schedules_session
FROM dbo.rjob_schedule_info
WHERE jobid = :jobid
""")
READ_MAPPINGS = text("""
SELECT jobid, jobclientcolumn, jobfieldmapping, jobdefaultvalue, jobformat,
       jobrectype, startposition, field_len, DataSetNo, ColSeqNo
FROM dbo.rjob_file_detail
WHERE jobid = :jobid
ORDER BY DataSetNo, ColSeqNo
""")
READ_SUBSCRIPTIONS = text("""
SELECT jobid, jobclientid, jobemailind
FROM dbo.rjob_client_detail
WHERE jobid = :jobid
ORDER BY jobclientid
""")
READ_SORTING = text("""
SELECT job_id, sort_order, mapping_column
FROM dbo.rjob_file_sorting_details
WHERE job_id = :jobid
ORDER BY sort_order
""")
READ_CONDITIONS = text("""
SELECT job_id, mapping_column, condition_symbol, condition_value
FROM dbo.rjob_file_condition_details
WHERE job_id = :jobid
ORDER BY mapping_column
""")
READ_QUERY_CONFIGURATION = text("""
SELECT jobid, recttype, Query, Conditions, Sort_Order
FROM dbo.rjob_query
WHERE jobid = :jobid
ORDER BY Sort_Order, recttype
""")

LOCK_RUN_JOB = text("SELECT jobid FROM dbo.rjob WITH (UPDLOCK, HOLDLOCK) WHERE jobid = :jobid")
INSERT_RUN_HISTORY = text("""
INSERT INTO dbo.rjob_history
    (Job_Id, Job_Create_Date, Job_Last_Trigger_Date, Job_Last_Status, Job_Last_Message, Job_Update_Date)
VALUES (:jobid, GETDATE(), GETDATE(), :run_status, :message, GETDATE())
""")


def _mapping_column_types(root: ET.Element) -> dict[str, str]:
    columns = {
        option.text.strip(): option.attrib["type"]
        for option in root.findall("mappingColumns/option")
        if option.text and option.text.strip()
    }
    try:
        with engine.connect() as connection:
            configured = connection.execute(text(QUERY_30)).mappings().all()
    except SQLAlchemyError:
        return columns

    fallback_names = {column.casefold(): column for column in columns}
    for row in configured:
        name = str(row["mapping_column"] or "").strip()
        if not name:
            continue
        fallback_name = fallback_names.get(name.casefold(), name)
        declared = str(row["mapping_column_dt"] or "").strip().casefold().split("(", 1)[0].strip()
        fallback_type = columns.get(fallback_name, "text")
        if declared in ("phone", "email", "ssn"):
            column_type = declared
        elif fallback_type in ("phone", "email", "ssn"):
            column_type = fallback_type
        elif declared in ("d", "date", "datetime", "datetime2", "smalldatetime", "datetimeoffset"):
            column_type = "date"
        elif declared in ("n", "number", "numeric", "decimal", "money", "smallmoney",
                          "int", "integer", "bigint", "smallint", "tinyint", "float", "real"):
            column_type = "number"
        else:
            column_type = fallback_type
        if fallback_name != name:
            columns.pop(fallback_name, None)
        columns[name] = column_type
        fallback_names[name.casefold()] = name
    return columns


def _options_from_xml() -> RetirementBuilderOptions:
    root = ET.parse(OPTIONS_FILE).getroot()
    column_types = _mapping_column_types(root)

    def values(name: str) -> list[str]:
        section = root.find(name)
        return [str(option.text or "").strip() for option in section.findall("option")] if section is not None else []

    return RetirementBuilderOptions(
        fileFormats=values("fileFormats"),
        outputFileNameFormats=values("outputFileNameFormats"),
        buildFrequencies=values("buildFrequencies"),
        hours=values("hours"),
        minutes=values("minutes"),
        meridiems=values("meridiems"),
        weekDays=values("weekDays"),
        recordTypes=values("recordTypes"),
        sortDirections=values("sortDirections"),
        mappingColumns=sorted(column_types, key=str.casefold),
        mappingFormats=list(dict.fromkeys(item for formats in MAPPING_FORMATS_BY_TYPE.values() for item in formats)),
        mappingColumnTypes=column_types,
        mappingFormatsByType=MAPPING_FORMATS_BY_TYPE,
    )


def _prepared_query(query: str, parameters: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    for name in sorted(parameters, key=len, reverse=True):
        query = query.replace(f"'@{name}'", f":{name}").replace(f"@{name}", f":{name}")
    return text(query), parameters


def _schedule_type(build_frequency: str) -> str:
    return {"Daily": "D", "Weekly": "W", "Bi-Weekly": "B", "Monthly": "M"}.get(build_frequency, "")


def _schedule_week(week: str) -> int:
    return {day: index for index, day in enumerate(("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"))}.get(week, 0)


def _start_datetime(schedule: ScheduleForm) -> str | None:
    if schedule.startDate is None:
        return None
    hour = _integer(schedule.hour) % 12
    if schedule.meridiem == "PM":
        hour += 12
    return f"{schedule.startDate.isoformat()} {hour:02d}:{_integer(schedule.minute):02d}:00"


def _field_error(path: list[str | int], message: str) -> NoReturn:
    raise HTTPException(status_code=422, detail=[{"loc": ["body", *path], "msg": message, "type": "value_error"}])


def _check_length(value: str, maximum: int, path: list[str | int]) -> None:
    if len(value) > maximum:
        _field_error(path, f"Use at most {maximum} characters.")


def _integer(value: str) -> int:
    return int(value.strip().lstrip("0") or "0")


def _check_integer(value: str, minimum: int, maximum: int, path: list[str | int]) -> None:
    digits = value.strip()
    significant = digits.lstrip("0") or "0"
    if (
        not re.fullmatch(r"[0-9]+", digits)
        or len(significant) > len(str(maximum))
        or not minimum <= int(significant) <= maximum
    ):
        _field_error(path, f"Enter a whole number from {minimum} to {maximum}.")


def _condition_value(value: str, path: list[str | int]) -> str:
    try:
        decimal = Decimal(value.strip())
        if not decimal.is_finite() or decimal.copy_abs() >= CONDITION_MAX + 1:
            raise InvalidOperation
        with localcontext() as context:
            context.prec = 20
            rounded = decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if abs(rounded) > CONDITION_MAX:
            raise InvalidOperation
    except InvalidOperation:
        _field_error(path, "Enter a decimal that fits 16 whole digits and two decimal places after rounding.")
    return format(rounded.copy_abs() if not rounded else rounded, "f")


def _validate_payload(payload: RetirementBuilderJobInput, *, creating: bool = False) -> None:
    # Validate supplied fields on PUT so an unrelated edit remains possible for legacy records.
    general = payload.general
    for field, maximum in (("fileName", 255), ("fileFormat", 20), ("description", 300), ("outputFileNameFormat", 55)):
        if creating or field in general.model_fields_set:
            value = getattr(general, field)
            if field in ("fileName", "fileFormat") and not value.strip():
                _field_error(["general", field], "This field is required.")
            _check_length(value, maximum, ["general", field])

    schedule = payload.schedule
    if schedule.startDate is not None and schedule.startDate < SQL_DATETIME_MIN:
        _field_error(["schedule", "startDate"], "Choose a start date on or after 1753-01-01.")
    for field, minimum, maximum in (("hour", 1, 12), ("minute", 0, 59)):
        if creating or field in schedule.model_fields_set:
            _check_integer(getattr(schedule, field), minimum, maximum, ["schedule", field])

    for index, row in enumerate(payload.mapping.rows):
        path = ["mapping", "rows", index]
        for field in ("startPosition", "length"):
            if field in row.model_fields_set:
                _check_integer(getattr(row, field), 0, SQL_INT_MAX, [*path, field])
        for field, maximum in (("field", 255), ("defaultValue", 255), ("mappingColumn", 255), ("format", 20), ("recordType", 20)):
            _check_length(getattr(row, field), maximum, [*path, field])

    for index, row in enumerate(payload.subscriptions.rows):
        path = ["subscriptions", "rows", index]
        _check_integer(row.client, 0, SQL_INT_MAX, [*path, "client"])
        addresses = [part.strip() for part in re.split(r"[,;\n]", row.email) if part.strip()]
        if any(len(address) > 254 or len(address.partition("@")[0]) > 64 or not EMAIL_PATTERN.fullmatch(address) for address in addresses):
            _field_error([*path, "email"], "Enter valid email addresses separated by commas.")
    _check_length(", ".join(row.email for row in payload.subscriptions.rows if row.email), 255, ["subscriptions", "rows"])

    for index, row in enumerate(payload.fileSettings.sortingOrder):
        path = ["fileSettings", "sortingOrder", index]
        if row.orderBy != "":
            _check_integer(row.orderBy, 0, SQL_INT_MAX, [*path, "orderBy"])
        _check_length(row.mappingColumn, 255, [*path, "mappingColumn"])
    for index, row in enumerate(payload.fileSettings.conditionalStatements):
        path = ["fileSettings", "conditionalStatements", index]
        _check_length(row.mappingColumn, 255, [*path, "mappingColumn"])
        _check_length(row.condition, 50, [*path, "condition"])
        row.value = _condition_value(row.value, [*path, "value"])
    for index, row in enumerate(payload.queryConfiguration):
        _check_length(row.recttype, 10, ["queryConfiguration", index, "recttype"])


def _execute_identity_query(connection: Any, query: str, parameters: dict[str, Any]) -> int:
    statement, values = _prepared_query(query, parameters)
    compiled = statement.compile(dialect=connection.dialect)
    ordered_values = [values[name] for name in compiled.positiontup]
    cursor = connection.connection.cursor()
    try:
        cursor.execute(compiled.string, ordered_values)
        while True:
            try:
                row = cursor.fetchone()
            except Exception:
                row = None
            if row is not None:
                try:
                    identity = int(row[0])
                except (IndexError, TypeError, ValueError) as exc:
                    raise RuntimeError("SQL Server returned an invalid Retirement Builder job ID") from exc
                if identity <= 0:
                    raise RuntimeError("SQL Server returned an invalid Retirement Builder job ID")
                return identity
            if not cursor.nextset():
                raise RuntimeError("SQL Server did not return a Retirement Builder job ID")
    finally:
        cursor.close()


def _api_job_from_row(row: dict[str, Any]) -> dict[str, Any]:
    job_id = int(row["jobid"])
    runtime = str(row.get("runtime") or "")
    time_parts = runtime.split()
    hour_minute = time_parts[0].split(":", 1) if time_parts else []
    meridiem = time_parts[1] if len(time_parts) > 1 else None
    minute = hour_minute[1].zfill(2) if len(hour_minute) > 1 else ""
    response = dict(row)
    if not row.get("Job_Last_Status"):
        # The legacy insert initializes joblastrun even before the first run.
        response["joblastrun"] = None
    with _active_runs_lock:
        if _active_runs[job_id]:
            response["Job_Last_Status"] = "In Progress"
        elif job_id in _failed_runs:
            response["Job_Last_Status"] = "Failed"
    if minute:
        response["runtime"] = " ".join(filter(None, [f"{hour_minute[0]}:{minute}", meridiem]))
    response.update({
        "id": job_id,
        "general": {
            "fileName": row.get("jobfilename") or "",
            "fileFormat": row.get("filetype") or "",
            "description": row.get("jobdesc") or "",
            "enable": bool(row.get("isEnabled")),
        },
        "schedule": {
            "week": row.get("runday") or "",
            "hour": hour_minute[0] if hour_minute else "",
            "minute": minute,
            "meridiem": meridiem or "AM",
            "buildFrequency": row.get("ScheduleType") or "",
        },
    })
    return response


def _job_rows(connection: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(QUERY_42)).mappings().all()]


def _schedule_label(value: Any) -> str:
    return {
        "D": "Daily",
        "W": "Weekly",
        "B": "Bi-Weekly",
        "M": "Monthly",
        "MD": "Monthly",
    }.get(str(value or ""), str(value or ""))


def _week_label(value: Any) -> str:
    text_value = str(value) if value is not None else ""
    if text_value.isdecimal() and 0 <= int(text_value) <= 6:
        return ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")[int(text_value)]
    return text_value


def _sort_priority(stored_order: int) -> int:
    return stored_order if stored_order >= 0 else -stored_order - 1


def _read_full_job(connection: Any, job_id: int) -> RetirementBuilderJob | None:
    main = connection.execute(READ_JOB, {"jobid": job_id}).mappings().first()
    if main is None:
        return None
    schedule = connection.execute(READ_SCHEDULE, {"jobid": job_id}).mappings().first()
    mappings = connection.execute(READ_MAPPINGS, {"jobid": job_id}).mappings().all()
    subscriptions = connection.execute(READ_SUBSCRIPTIONS, {"jobid": job_id}).mappings().all()
    sorting = connection.execute(READ_SORTING, {"jobid": job_id}).mappings().all()
    conditions = connection.execute(READ_CONDITIONS, {"jobid": job_id}).mappings().all()
    query_configuration = connection.execute(READ_QUERY_CONFIGURATION, {"jobid": job_id}).mappings().all()
    schedule = dict(schedule) if schedule is not None else {}
    return RetirementBuilderJob.model_validate({
        "id": int(main["jobid"]),
        "general": {
            "fileName": main.get("jobfilename"),
            "fileFormat": main.get("filetype"),
            "description": main.get("jobdesc"),
            "outputFileNameFormat": main.get("FileNameFormat"),
            "enable": main.get("isEnabled"),
            "storeResultsToTable": main.get("StoreResults"),
        },
        "schedule": {
            "startDate": (
                schedule.get("startDateTime").date()
                if schedule.get("startDateTime") is not None
                else None
            ),
            "buildFrequency": schedule.get("rbJobTypeChk") or _schedule_label(schedule.get("ScheduleType")),
            "hour": "" if schedule.get("schedule_hr") is None else str(schedule.get("schedule_hr")),
            "minute": "" if schedule.get("schedule_min") is None else f"{int(schedule['schedule_min']):02d}",
            "meridiem": schedule.get("schedules_session"),
            "week": _week_label(schedule.get("ScheduleWeek")),
        },
        "mapping": {
            "includeHeader": main.get("includeHeader"),
            "rows": [{
                "field": row.get("jobclientcolumn"),
                "startPosition": "" if row.get("startposition") is None else str(row.get("startposition")),
                "length": "" if row.get("field_len") is None else str(row.get("field_len")),
                "recordType": row.get("jobrectype"),
                "defaultValue": row.get("jobdefaultvalue"),
                "mappingColumn": row.get("jobfieldmapping"),
                "format": row.get("jobformat"),
            } for row in mappings],
        },
        "subscriptions": {
            "mergeFiles": main.get("ismerge"),
            "rows": [{
                "client": "" if row.get("jobclientid") is None else str(row.get("jobclientid")),
                "email": row.get("jobemailind"),
            } for row in subscriptions],
        },
        "fileSettings": {
            "sortingOrder": [{
                "orderBy": str(_sort_priority(row["sort_order"])),
                "mappingColumn": row["mapping_column"],
                "direction": "DESC" if row["sort_order"] < 0 else "ASC",
            } for row in sorted(sorting, key=lambda rule: _sort_priority(rule["sort_order"]))],
            "conditionalStatements": [{
                "mappingColumn": row.get("mapping_column"),
                "condition": row.get("condition_symbol"),
                "value": "" if row.get("condition_value") is None else str(row.get("condition_value")),
            } for row in conditions],
        },
        "queryConfiguration": [{
            "recttype": row.get("recttype"),
            "query": row.get("Query"),
            "conditions": row.get("Conditions"),
            "sortOrder": row.get("Sort_Order"),
        } for row in query_configuration],
    })


def _merge_missing_fields(current: BaseModel, original: BaseModel, fields: tuple[str, ...]) -> BaseModel:
    updates = {field: getattr(original, field) for field in fields if field not in current.model_fields_set}
    return current.model_copy(update=updates) if updates else current


def _complete_update_payload(payload: RetirementBuilderJobInput, original: RetirementBuilderJob) -> RetirementBuilderJobInput:
    sections = {
        "general": _merge_missing_fields(payload.general, original.general, ("testfileName", "fileName", "fileFormat", "description", "outputFileNameFormat", "enable", "storeResultsToTable", "selectedFile")),
        "schedule": _merge_missing_fields(payload.schedule, original.schedule, ("startDate", "buildFrequency", "hour", "minute", "meridiem", "week")),
        "mapping": _merge_missing_fields(payload.mapping, original.mapping, ("includeHeader", "rows")),
        "subscriptions": _merge_missing_fields(payload.subscriptions, original.subscriptions, ("mergeFiles", "rows")),
        "fileSettings": _merge_missing_fields(payload.fileSettings, original.fileSettings, ("sortingOrder", "conditionalStatements")),
        "queryConfiguration": payload.queryConfiguration if "queryConfiguration" in payload.model_fields_set else original.queryConfiguration,
    }
    return payload.model_copy(update=sections)


def _write_job_details(connection: Any, job_id: int, payload: RetirementBuilderJobInput) -> None:
    schedule = payload.schedule
    subscriptions = payload.subscriptions
    file_settings = payload.fileSettings
    general = payload.general
    for row in payload.queryConfiguration:
        connection.execute(*_prepared_query(QUERY_31, {
            "jobid": job_id,
            "recttype": row.recttype,
            "Query": row.query,
            "conditionalStmt": row.conditions,
            "sortOrder": row.sortOrder,
        }))
    connection.execute(*_prepared_query(QUERY_38, {
        "jobid": job_id,
        "jobName": general.fileName,
        "startDateTime": _start_datetime(schedule),
        "dayInterval": 0,
        "weekInterval": 0,
        "rbJobTypeChk": schedule.buildFrequency,
        "ScheduleType": _schedule_type(schedule.buildFrequency),
        "MonthlyWeekNo": "",
        "ScheduleWeek": _schedule_week(schedule.week),
        "MonthlyDate": "",
        "schedule_hr": _integer(schedule.hour),
        "schedule_min": _integer(schedule.minute),
        "schedule_session": schedule.meridiem,
    }))
    for index, row in enumerate(payload.mapping.rows, start=1):
        connection.execute(*_prepared_query(QUERY_35, {
            "jobid": job_id,
            "jobclientcolumn": row.field,
            "jobfieldmapping": row.mappingColumn,
            "jobdefaultvalue": row.defaultValue,
            "jobformat": row.format,
            "jobrectype": row.recordType,
            "startposition": _integer(row.startPosition),
            "field_len": _integer(row.length),
            "datasetNo": 1,
            "colSeqNo": index,
        }))
    for row in subscriptions.rows:
        connection.execute(*_prepared_query(QUERY_37, {
            "jobid": job_id,
            "jobclientid": _integer(row.client),
            "jobemailind": row.email,
        }))
    for row in file_settings.sortingOrder:
        priority = _integer(row.orderBy)
        # Nonnegative values retain legacy ascending priority. Negative values encode descending.
        stored_order = -priority - 1 if row.direction == "DESC" else priority
        connection.execute(*_prepared_query(QUERY_54, {
            "jobid": job_id,
            "order": stored_order,
            "mapping": row.mappingColumn,
        }))
    for row in file_settings.conditionalStatements:
        connection.execute(*_prepared_query(QUERY_55, {
            "jobid": job_id,
            "mapping": row.mappingColumn,
            "Symbol": row.condition,
            "val": row.value,
        }))


@router.get("/options", response_model=RetirementBuilderOptions)
def get_retirement_builder_options() -> RetirementBuilderOptions:
    return _options_from_xml()


@router.get("/jobs", response_model=list[dict[str, object]])
def list_retirement_builder_jobs() -> list[dict[str, object]]:
    try:
        with engine.connect() as connection:
            rows = _job_rows(connection)
        return [_api_job_from_row(row) for row in rows]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to load Retirement Builder jobs from the database") from exc


def _create_job(payload: RetirementBuilderJobInput) -> RetirementBuilderJob:
    _validate_payload(payload, creating=True)
    general = payload.general
    subscriptions = payload.subscriptions
    try:
        with engine.begin() as connection:
            job_id = _execute_identity_query(connection, QUERY_36, {
                "jobdesc": general.description,
                "jobfilename": general.fileName,
                "jobstatus": "Active",
                "filetype": general.fileFormat,
                "ismerge": subscriptions.mergeFiles,
                "mergeemail": ", ".join(row.email for row in subscriptions.rows if row.email),
                "includeHRecord": payload.mapping.includeHeader,
                "fileNameFormat": general.outputFileNameFormat,
                "isEnabled": general.enable,
                "StoreResult": general.storeResultsToTable,
                "enddate": payload.schedule.startDate,
            })
            _write_job_details(connection, job_id, payload)
            job = _read_full_job(connection, job_id)
            if job is None:
                raise RuntimeError("The inserted job could not be retrieved")
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to save Retirement Builder job to the database") from exc
    return job


@router.post(
    "/jobs",
    response_model=RetirementBuilderJob,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Idempotency key already used with a different request"}},
)
def create_retirement_builder_job(
    payload: RetirementBuilderJobInput,
    idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128, pattern=r"^[!-~]+$")] = None,
) -> RetirementBuilderJob:
    if idempotency_key is None:
        return _create_job(payload)

    fingerprint = sha256(payload.model_dump_json(exclude_unset=True).encode()).digest()
    with _idempotency_lock:
        now = monotonic()
        while _completed_creates and next(iter(_completed_creates.values()))[2] <= now:
            _completed_creates.popitem(last=False)
        completed = _completed_creates.get(idempotency_key)
        pending = _pending_creates.get(idempotency_key)
        if (completed and completed[0] != fingerprint) or (pending and pending[0] != fingerprint):
            raise HTTPException(status_code=409, detail="This Idempotency-Key was used with a different request.")
        if completed:
            return completed[1]
        if pending is None:
            future: Future[RetirementBuilderJob] = Future()
            _pending_creates[idempotency_key] = (fingerprint, future)

    if pending:
        return pending[1].result()

    try:
        job = _create_job(payload)
    except BaseException as exc:
        with _idempotency_lock:
            del _pending_creates[idempotency_key]
            future.set_exception(exc)
        raise

    with _idempotency_lock:
        del _pending_creates[idempotency_key]
        _completed_creates[idempotency_key] = (fingerprint, job, monotonic() + IDEMPOTENCY_TTL)
        if len(_completed_creates) > IDEMPOTENCY_LIMIT:
            _completed_creates.popitem(last=False)
        future.set_result(job)
    return job


@router.get("/jobs/{job_id}", response_model=dict[str, object])
def get_retirement_builder_job(job_id: int) -> dict[str, object]:
    try:
        with engine.connect() as connection:
            job = _read_full_job(connection, job_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to load Retirement Builder job from the database") from exc
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
    return job.model_dump()


@router.put("/jobs/{job_id}", response_model=dict[str, object])
def update_retirement_builder_job(job_id: int, payload: RetirementBuilderJobInput) -> dict[str, object]:
    _validate_payload(payload)
    try:
        with engine.begin() as connection:
            existing = _read_full_job(connection, job_id)
            if existing is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
            effective_payload = _complete_update_payload(payload, existing)
            general = effective_payload.general
            subscriptions = effective_payload.subscriptions
            connection.execute(*_prepared_query(QUERY_45, {
                "jobid": job_id,
                "jobdesc": general.description,
                "jobfilename": general.fileName,
                "jobstatus": "Active",
                "filetype": general.fileFormat,
                "ismerge": subscriptions.mergeFiles,
                "mergeemail": ", ".join(row.email for row in subscriptions.rows if row.email),
                "includeHRecord": effective_payload.mapping.includeHeader,
                "fileNameFormat": general.outputFileNameFormat,
                "isEnabled": general.enable,
                "StoreResult": general.storeResultsToTable,
            }))
            connection.execute(*_prepared_query(QUERY_44, {"jobid": job_id}))
            _write_job_details(connection, job_id, effective_payload)
            updated = _read_full_job(connection, job_id)
    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to update Retirement Builder job in the database") from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
    return updated.model_dump()




def _record_run(connection, job_id: int, run_status: str, message: str) -> None:
    result = connection.execute(*_prepared_query(QUERY_52, {
        "JOB_ID": job_id, "STATUS": run_status, "STAT_MSG": message,
    }))
    if result.rowcount == 0:
        connection.execute(INSERT_RUN_HISTORY, {
            "jobid": job_id, "run_status": run_status, "message": message,
        })


@contextmanager
def _active_report_run(job_id: int):
    with _active_runs_lock:
        _active_runs[job_id] += 1
    completed = False
    try:
        yield
        completed = True
    finally:
        with _active_runs_lock:
            _active_runs[job_id] -= 1
            if not _active_runs[job_id]:
                del _active_runs[job_id]
            if completed:
                _failed_runs.discard(job_id)
            else:
                _failed_runs.add(job_id)


def _execute_report_run(
    connection, job: RetirementBuilderJob, read_source: Callable[[], bytes], output: Path,
    resources: ExitStack, *, scheduled: bool = False,
) -> tuple[RetirementBuilderRun, list[ReportFile]]:
    resources.enter_context(_active_report_run(job.id))
    run_id = uuid4()
    run_dir = output if scheduled else output / str(run_id)
    reports = build_report_files(job, read_source())
    for report in reports:
        resources.enter_context(publish_report(run_dir / report.file_name, report.csv))
    if scheduled and not reports:
        resources.enter_context(publish_report(run_dir / ".complete", ""))

    rows = [row for report in reports for row in report.rows]
    outputs = [RetirementBuilderOutput(fileName=report.file_name, csv=report.csv) for report in reports]
    stored_rows = store_results(connection, job.id, run_id, rows) if job.general.storeResultsToTable else 0
    _record_run(connection, job.id, "Success", f"Generated {len(rows)} rows. Stored {stored_rows} rows.")
    run = RetirementBuilderRun(
        runId=run_id, rowCount=len(rows), storedRows=stored_rows,
        fileName=outputs[0].fileName if outputs else "", csv=outputs[0].csv if outputs else "", files=outputs,
    )
    return run, reports


def _run_job(job_id: int, source: bytes | None) -> RetirementBuilderRun:
    settings = get_settings()
    output = report_directory(settings.report_output_dir)
    try:
        with ExitStack() as resources, engine.begin() as connection:
            if connection.execute(LOCK_RUN_JOB, {"jobid": job_id}).scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Retirement Builder job not found")
            job = _read_full_job(connection, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Retirement Builder job not found")
            if not job.general.enable:
                raise HTTPException(status_code=409, detail="Enable the job before running it.")
            def read_source() -> bytes:
                return source if source is not None else load_report_source(settings.report_input_dir, job_id)

            run, _ = _execute_report_run(connection, job, read_source, output / "manual" / str(job_id), resources)
    except InvalidRun as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="The job could not be completed. No results were saved.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="The generated file could not be saved. Check REPORT_OUTPUT_DIR.") from exc
    return run


@router.post(
    "/jobs/{job_id}/run",
    response_model=RetirementBuilderRun,
    openapi_extra={"requestBody": {
        "description": "Omit the body to use the job's configured source CSV.",
        "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
    }},
)
async def run_retirement_builder_job(job_id: int, request: Request) -> RetirementBuilderRun:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    source = bytearray()
    async for chunk in request.stream():
        if chunk and content_type != "text/csv":
            raise HTTPException(status_code=415, detail="Send a CSV file with Content-Type text/csv.")
        if len(source) + len(chunk) > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail="The source CSV can be up to 5 MB.")
        source.extend(chunk)
    return await run_in_threadpool(_run_job, job_id, bytes(source) if source else None)

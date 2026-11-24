from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import Future
from contextlib import ExitStack, contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from hashlib import sha256
import logging
from pathlib import Path
import re
from threading import Lock
from time import monotonic
from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID, uuid4
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Header, HTTPException, Request, status
from pyodbc import Error as OdbcError
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy import column, func, table, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db import engine
from app.payroll_source import (
    PAYROLL_COLUMNS, PAYROLL_MAPPING_FIELDS, PAYROLL_QUERY_TYPE, is_payroll_record_query,
    load_payroll_source, payroll_company_ids, payroll_job_with_saved_rules, payroll_record_queries,
)
from app.report_files import load_report_source, publish_report, report_directory
from app.report_mail import EMAIL_PATTERN, ReportEmailDelivery, send_subscribed_reports
from app.retirement_procedure import ProcedureSource, build_procedure_report_files, uses_retirement_queries
from app.retirement_query_builder import export_record_queries, ordered_mappings, sql_identifier
from app.retirement_conditions import parsed_conditions
from app.retirement_listing import READ_ALL_JOBS
from app.retirement_datasets import expand_legacy_datasets, split_dataset_query
from app.retirement_results import (
    COMPARISONS, FILE_NAME_FORMAT_CODES, MAX_SOURCE_BYTES, MAX_PADDING_LENGTH, PADDING_FORMATS, RECORD_TYPES, SSN_FORMATS,
    InvalidRun, ReportDateRange, ReportFile, UNBOUNDED_RUN_DATE, build_report_files, condition_date, file_format_name,
    file_name_format_code, fixed_layout, format_sort_columns, is_fixed_format,
    parse_file_name_format, parse_sort_order, record_type_code, store_results,
)


router = APIRouter(prefix="/retirement-builder", tags=["retirement-builder"])
logger = logging.getLogger(__name__)


class GeneralForm(BaseModel):
    testfileName: str = ""
    fileName: str = ""
    fileFormat: str = ""
    description: str = ""
    outputFileNameFormat: str = ""
    enable: bool = True
    storeResultsToTable: bool = False
    selectedFile: str = ""
    reportSource: Literal["csv", "companyPayroll"] = "csv"


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
    dataSetNo: int = Field(default=1, ge=0, le=2_147_483_647, validation_alias=AliasChoices("dataSetNo", "DataSetNo", "datasetNo"))
    colSeqNo: int | None = Field(default=None, ge=0, le=2_147_483_647, validation_alias=AliasChoices("colSeqNo", "ColSeqNo"))


class MappingForm(BaseModel):
    includeHeader: bool = True
    rows: list[MappingRow] = Field(default_factory=list)


class SubscriptionRow(BaseModel):
    client: str = ""
    email: str = ""
    companyId: Annotated[int, Field(ge=0, le=2_147_483_647)] | None = None


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
    valueType: Literal["text", "date", "number"] | None = None


class FileSettingsForm(BaseModel):
    sortingOrder: list[SortingOrderRow] = Field(default_factory=list)
    conditionalStatements: list[ConditionalStatementRow] = Field(default_factory=list)


class QueryConfigurationRow(BaseModel):
    recttype: str = ""
    query: str = ""
    conditions: str = ""
    sortOrder: str = ""
    dataSetNo: int | None = Field(default=None, ge=0, le=2_147_483_647)


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
    excelRows: list[list[str]] | None = None


class RetirementBuilderRun(RetirementBuilderOutput):
    runId: UUID
    rowCount: int
    storedRows: int
    delimiter: str
    files: list[RetirementBuilderOutput]
    emailDelivery: ReportEmailDelivery | None = None


class OutputFileNameFormatOption(BaseModel):
    label: str
    value: str


class RetirementBuilderClient(BaseModel):
    id: int
    label: str


class RetirementBuilderOptions(BaseModel):
    fileFormats: list[str]
    outputFileNameFormats: list[OutputFileNameFormatOption]
    buildFrequencies: list[str]
    hours: list[str]
    minutes: list[str]
    meridiems: list[str]
    weekDays: list[str]
    recordTypes: list[str]
    sortDirections: list[Literal["ASC", "DESC"]]
    comparisonOperators: list[str]
    mappingColumns: list[str]
    payrollMappingColumns: list[str]
    payrollMappingColumnKeys: list[str]
    mappingColumnLabels: dict[str, str]
    payrollCompanies: dict[int, str]
    mappingFormats: list[str]
    mappingFormatLabels: dict[str, str]
    mappingColumnTypes: dict[str, str]
    mappingFormatsByType: dict[str, list[str]]


SQL_INT_MAX = 2_147_483_647
SQL_DATETIME_MIN = date(1753, 1, 1)
CONDITION_MAX = Decimal("9999999999999999.99")
DATE_CONDITION_PREFIX = "date:"
RECORD_TYPE_LABELS = {"H": "Header", "D": "Detail", "T": "Trailer"}
LEGACY_CSV_SORT_QUERY_TYPE = "CSV_SORT"
MAPPING_FORMAT_TYPES = {
    "char": "text", "text": "text", "date": "date", "numeric": "number", "number": "number",
    "int": "number", "phone": "phone", "email": "email", "ssn": "ssn",
}
IDEMPOTENCY_TTL = 3600
IDEMPOTENCY_LIMIT = 1024
_idempotency_lock = Lock()
_active_runs_lock = Lock()
_active_runs: Counter[int] = Counter()
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
QUERY_43 = _load_query("43")
QUERY_30 = _load_query("30")
QUERY_44 = _load_query("44")
QUERY_45 = _load_query("45")
QUERY_31 = _load_query("31")
QUERY_32 = _load_query("32")
QUERY_35 = _load_query("35")
QUERY_36 = _load_query("36")
QUERY_37 = _load_query("37")
QUERY_38 = _load_query("38")
QUERY_52 = _load_query("52")
QUERY_53 = _load_query("53")
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
READ_ENABLED_SCHEDULES = text("""
SELECT j.jobid, s.startDateTime, s.ScheduleType, s.ScheduleWeek, s.MonthlyDate,
       s.schedule_hr, s.schedule_min, s.schedules_session
FROM dbo.rjob AS j
JOIN dbo.rjob_schedule_info AS s ON j.jobid = s.jobid
WHERE j.isEnabled = 1 AND s.startDateTime IS NOT NULL
ORDER BY j.jobid
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
# Send the existing SELECTs together for the edit GET to avoid a round trip per result set.
_EDIT_JOB_READS = (
    READ_JOB, READ_SCHEDULE, READ_MAPPINGS, READ_SUBSCRIPTIONS,
    READ_SORTING, READ_CONDITIONS, READ_QUERY_CONFIGURATION, text(QUERY_32),
)
READ_EDIT_JOB = text(";\n".join(str(statement).strip() for statement in _EDIT_JOB_READS))

# Query 45 is retained unchanged for legacy consumers. Its GETDATE() assignment
# to joblastrun must not be used when editing a job's configuration.
JOB_CONFIGURATION = table(
    "rjob",
    *(column(name) for name in (
        "jobid", "jobdesc", "jobfilename", "jobstatus", "joblastmodified", "filetype",
        "ismerge", "mergeemail", "includeHeader", "FileNameFormat", "isEnabled", "StoreResults",
    )),
    schema="dbo",
)

LOCK_RUN_JOB = text("SELECT jobid FROM dbo.rjob WITH (UPDLOCK, HOLDLOCK) WHERE jobid = :jobid")
INSERT_RUN_HISTORY = text("""
INSERT INTO dbo.rjob_history
    (Job_Id, Job_Create_Date, Job_Last_Trigger_Date, Job_Last_Status, Job_Last_Message, Job_Update_Date)
VALUES (:jobid, GETDATE(), GETDATE(), :run_status, :message, GETDATE())
""")
INSERT_RUN_DATES = text("""
INSERT INTO dbo.rjob_history_details (Job_Id, Flag, Start_Date, End_Date)
VALUES (:jobid, :flag, :start_date, :end_date)
""")


def _mapping_catalog(connection: Any) -> dict[str, tuple[str, str]]:
    configured = connection.execute(text(QUERY_30)).mappings()
    columns: dict[str, tuple[str, str]] = {}
    for row in configured:
        key = str(row["mapping_column"] or "").strip()
        name = str(row["mapping_column_desc"] or "").strip() or key
        if not key:
            continue
        declared = str(row["mapping_column_dt"] or "").strip().casefold().split("(", 1)[0].strip()
        if declared in MAPPING_FORMAT_TYPES:
            column_type = MAPPING_FORMAT_TYPES[declared]
        elif declared in ("d", "datetime", "datetime2", "smalldatetime", "datetimeoffset"):
            column_type = "date"
        elif declared in ("n", "numeric", "decimal", "money", "smallmoney",
                          "int", "integer", "bigint", "smallint", "tinyint", "float", "real"):
            column_type = "number"
        else:
            column_type = "text"
        columns[key] = (name, column_type)
    return columns


def _file_formats(connection: Any) -> dict[str, str]:
    return _file_formats_from_rows(connection.execute(text(QUERY_32)).mappings())


def _file_formats_from_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    formats = {}
    for row in rows:
        name = str(row["filetyp"] or "").strip()
        delimiter = row["delimiter"]
        if 0 < len(name) <= 20 and isinstance(delimiter, str) and len(delimiter) == 1 and delimiter not in '\x00\r\n"':
            # Some legacy TAB rows contain a space. Interpret the named format
            # in code without rewriting the lookup table or the saved jobs.
            if file_format_name(name).casefold() == "tab":
                delimiter = "\t"
            formats[name] = delimiter
    return formats


def _configured_file_format(formats: dict[str, str], file_format: str) -> str | None:
    requested = file_format.strip().casefold()
    exact = next((name for name in formats if name.casefold() == requested), None)
    if exact is not None:
        return exact
    legacy_name = file_format_name(file_format).casefold()
    return next((name for name in formats if file_format_name(name).casefold() == legacy_name), None)


def _file_format_delimiter(formats: dict[str, str], file_format: str) -> str | None:
    # Check literal delimiters first so normalization does not strip spaces or tabs.
    if file_format in formats.values():
        return file_format
    name = _configured_file_format(formats, file_format)
    return formats[name] if name is not None else None


def _file_format_label(formats: dict[str, str] | None, file_format: str | None) -> str:
    if not formats or file_format is None:
        return file_format or ""
    # A stored space represents FIXED when that format is configured. TAB is
    # normalized to an actual tab, so lookup order cannot turn FIXED into TAB.
    if file_format == " ":
        fixed = next((name for name, delimiter in formats.items() if name.casefold() == "fixed" and delimiter == " "), None)
        if fixed is not None:
            return fixed
    delimiter_label = next((name for name, delimiter in formats.items() if delimiter == file_format), None)
    return delimiter_label or _configured_file_format(formats, file_format) or file_format


def _output_file_name_formats(root: ET.Element) -> list[OutputFileNameFormatOption]:
    formats = []
    for option in root.findall("outputFileNameFormats/option"):
        code = file_name_format_code(option.get("value", "")) if parse_file_name_format(option.get("value", "")) else ""
        label = (option.text or "").strip()
        if code in FILE_NAME_FORMAT_CODES and label:
            formats.append(OutputFileNameFormatOption(label=label, value=code))
    return formats


def _stored_file_name_format(value: str) -> str:
    """Keep API codes stable while saving the production spelling from XML."""
    code = file_name_format_code(value)
    root = ET.parse(OPTIONS_FILE).getroot()
    for option in root.findall("outputFileNameFormats/option"):
        stored = option.get("value", "").strip()
        if parse_file_name_format(stored) and file_name_format_code(stored) == code:
            return stored
    raise ValueError(f"Output filename format {code} is not configured in options.xml")


def _mapping_format_options(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, list[str]], dict[str, str]]:
    formats: dict[str, list[str]] = {}
    labels: dict[str, str] = {}
    for row in rows:
        code = str(row["jobformat"] or "").strip()
        category = str(row["jobformattype"] or "").strip().casefold()
        if category == "all" and not parse_file_name_format(code):
            kind = "all"
        else:
            kind = MAPPING_FORMAT_TYPES.get(category)
        if not code or kind is None:
            continue
        if kind == "text" and code in SSN_FORMATS:
            kind = "ssn"
        options = formats.setdefault(kind, [])
        if code not in options:
            options.append(code)
        labels[code] = str(row["jobdesc"] or "").strip() or code
    return formats, labels


def _options_from_xml() -> RetirementBuilderOptions:
    root = ET.parse(OPTIONS_FILE).getroot()
    try:
        with engine.connect() as connection:
            catalog = _mapping_catalog(connection)
    except SQLAlchemyError:
        logger.exception("Could not load the mapping catalog; using fallback options.")
        catalog = {}
    column_types = {}
    seen_names = set()
    for name, kind in catalog.values():
        if name.casefold() not in seen_names:
            column_types[name] = kind
            seen_names.add(name.casefold())
    file_formats: list[str] = []
    mapping_formats: dict[str, list[str]] = {}
    mapping_format_labels: dict[str, str] = {}
    try:
        with engine.connect() as connection:
            file_formats = sorted(_file_formats(connection), key=str.casefold)
            format_rows = connection.execute(text(QUERY_53)).mappings().all()
            mapping_formats, mapping_format_labels = _mapping_format_options(format_rows)
            companies = {
                company_id: name for name, company_id in payroll_company_ids(connection).items()
                if company_id is not None and company_id > 0
            }
    except SQLAlchemyError:
        logger.exception("Could not load database-backed dropdown options; using fallback options.")
        companies = {}

    def values(name: str) -> list[str]:
        section = root.find(name)
        return [str(option.text or "").strip() for option in section.findall("option")] if section is not None else []

    return RetirementBuilderOptions(
        fileFormats=file_formats,
        outputFileNameFormats=_output_file_name_formats(root),
        buildFrequencies=values("buildFrequencies"),
        hours=values("hours"),
        minutes=values("minutes"),
        meridiems=values("meridiems"),
        weekDays=values("weekDays"),
        recordTypes=values("recordTypes"),
        sortDirections=values("sortDirections"),
        comparisonOperators=list(COMPARISONS),
        mappingColumns=sorted(column_types, key=str.casefold),
        payrollMappingColumns=sorted(PAYROLL_COLUMNS, key=str.casefold),
        payrollMappingColumnKeys=list(PAYROLL_MAPPING_FIELDS),
        mappingColumnLabels={key: name for key, (name, _) in catalog.items()},
        payrollCompanies=companies,
        mappingFormats=list(mapping_format_labels),
        mappingFormatLabels=mapping_format_labels,
        mappingColumnTypes=column_types,
        mappingFormatsByType=mapping_formats,
    )


def _prepared_query(query: str, parameters: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    for name in sorted(parameters, key=len, reverse=True):
        query = query.replace(f"'@{name}'", f":{name}").replace(f"@{name}", f":{name}")
    return text(query), parameters


def _execute_query_batch(connection: Any, queries: list[tuple[str, dict[str, Any]]]) -> None:
    # Execute the existing statements in order on the caller's transaction.
    # Compile each separately so repeated bind names keep their own values.
    statements: list[str] = []
    values: list[Any] = []
    cursor = connection.connection.cursor()
    try:
        def flush() -> None:
            if not statements:
                return
            cursor.execute(";\n".join(statements), list(values))
            # Surface errors in later statements before the transaction commits.
            while cursor.nextset():
                pass
            statements.clear()
            values.clear()

        for query, parameters in queries:
            statement, bindings = _prepared_query(query, parameters)
            compiled = statement.compile(dialect=connection.dialect)
            ordered = [bindings[name] for name in compiled.positiontup]
            # Stay below SQL Server's 2,100 parameter limit for large mappings.
            if statements and len(values) + len(ordered) > 2000:
                flush()
            statements.append(compiled.string)
            values.extend(ordered)
        flush()
    finally:
        cursor.close()


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
        date_value = condition_date(value)
    except InvalidRun as exc:
        _field_error(path, str(exc))
    if date_value is not None:
        return date_value.isoformat()
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
            if field == "fileName" and re.search(r'[\\/:*?"<>|\x00-\x1f]', value):
                _field_error(["general", field], 'File Name cannot contain \\ / : * ? " < > | or control characters.')
            _check_length(value, maximum, ["general", field])

    schedule = payload.schedule
    if schedule.startDate is not None and schedule.startDate < SQL_DATETIME_MIN:
        _field_error(["schedule", "startDate"], "Choose a start date on or after 1753-01-01.")
    for field, minimum, maximum in (("hour", 1, 12), ("minute", 0, 59)):
        if creating or field in schedule.model_fields_set:
            _check_integer(getattr(schedule, field), minimum, maximum, ["schedule", field])

    if (creating or "rows" in payload.mapping.model_fields_set) and not payload.mapping.rows:
        _field_error(["mapping", "rows"], "Add at least one dataset mapping.")
    for index, row in enumerate(payload.mapping.rows):
        path = ["mapping", "rows", index]
        for field in ("startPosition", "length"):
            if field in row.model_fields_set:
                _check_integer(getattr(row, field), 0, SQL_INT_MAX, [*path, field])
        for field, maximum in (("field", 255), ("defaultValue", 255), ("mappingColumn", 255), ("format", 20), ("recordType", 20)):
            _check_length(getattr(row, field), maximum, [*path, field])
        if not row.field.strip():
            _field_error([*path, "field"], "Enter a field name for this mapping.")
        if row.recordType.strip() and row.recordType.strip().casefold() not in RECORD_TYPES:
            _field_error([*path, "recordType"], "Choose Header, Detail, or Trailer.")
        if row.format.strip() in PADDING_FORMATS and row.length.strip():
            _check_integer(row.length, 0, MAX_PADDING_LENGTH, [*path, "length"])
        if is_fixed_format(general.fileFormat) and not (
            payload.mapping.includeHeader and RECORD_TYPES.get(row.recordType.strip().casefold()) == "H"
        ):
            _check_integer(row.length, 1, 1_000, [*path, "length"])

    for index, row in enumerate(payload.subscriptions.rows):
        path = ["subscriptions", "rows", index]
        if row.companyId is not None and row.client.strip():
            _field_error([*path, "client"], "Choose one client or payroll company for the subscription.")
        addresses = [part.strip() for part in re.split(r"[,;\n]", row.email) if part.strip()]
        if any(len(address) > 254 or len(address.partition("@")[0]) > 64 or not EMAIL_PATTERN.fullmatch(address) for address in addresses):
            _field_error([*path, "email"], "Enter valid email addresses separated by commas.")
    _check_length(", ".join(row.email for row in payload.subscriptions.rows if row.email), 255, ["subscriptions", "rows"])

    priorities = set()
    for index, row in enumerate(payload.fileSettings.sortingOrder):
        path = ["fileSettings", "sortingOrder", index]
        _check_integer(row.orderBy, 1, SQL_INT_MAX, [*path, "orderBy"])
        priority = _integer(row.orderBy)
        if priority in priorities:
            _field_error([*path, "orderBy"], "Use a different priority for each sort rule.")
        priorities.add(priority)
        _check_length(row.mappingColumn, 255, [*path, "mappingColumn"])
        if not row.mappingColumn.strip():
            _field_error([*path, "mappingColumn"], "Choose a mapping column for each sort rule.")
    for index, row in enumerate(payload.fileSettings.conditionalStatements):
        path = ["fileSettings", "conditionalStatements", index]
        _check_length(row.mappingColumn, 255, [*path, "mappingColumn"])
        _check_length(row.condition, 50, [*path, "condition"])
        if not row.mappingColumn.strip():
            _field_error([*path, "mappingColumn"], "Choose a mapping column for each condition.")
        row.condition = row.condition.strip()
        if row.condition not in COMPARISONS:
            _field_error([*path, "condition"], "Choose a supported comparison operator.")
        if row.valueType == "text":
            _check_length(row.value, 4000, [*path, "value"])
            if not row.value.strip() or "\x00" in row.value:
                _field_error([*path, "value"], "Enter a text value for this condition.")
        else:
            row.value = _condition_value(row.value, [*path, "value"])
    for index, row in enumerate(payload.queryConfiguration):
        _check_length(row.recttype, 10, ["queryConfiguration", index, "recttype"])
        if (
            row.recttype.strip().upper() not in (PAYROLL_QUERY_TYPE, LEGACY_CSV_SORT_QUERY_TYPE)
            and row.recttype.strip().casefold() not in RECORD_TYPES
        ):
            _field_error(["queryConfiguration", index, "recttype"], "Choose H, D, or T as the record type.")


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


def _api_job_from_row(
    row: dict[str, Any], file_formats: dict[str, str] | None = None, *, manual_only: bool = False,
) -> dict[str, Any]:
    job_id = int(row["jobid"])
    response = dict(row)
    if "schedule_hr" in row:
        hour, minute = row.get("schedule_hr"), row.get("schedule_min")
        session = str(row.get("schedules_session") or "").strip()
        response.update(
            runtime=f"{hour}:{int(minute):02d} {session}".strip() if hour is not None and minute is not None else "",
            runday=_week_label(row.get("ScheduleWeek")),
            ScheduleType=_schedule_label(str(row.get("ScheduleType") or "").strip()),
        )
    if manual_only:
        response.update(runday="", runtime="", ScheduleType="")
    runtime = str(response.get("runtime") or "")
    time_parts = runtime.split()
    hour_minute = time_parts[0].split(":", 1) if time_parts else []
    meridiem = time_parts[1] if len(time_parts) > 1 else None
    minute = hour_minute[1].zfill(2) if len(hour_minute) > 1 else ""
    if not row.get("Job_Last_Status"):
        # The legacy insert initializes joblastrun even before the first run.
        response["joblastrun"] = None
    with _active_runs_lock:
        if _active_runs[job_id]:
            response["Job_Last_Status"] = "In Progress"
    if minute:
        response["runtime"] = " ".join(filter(None, [f"{hour_minute[0]}:{minute}", meridiem]))
    response.update({
        "id": job_id,
        # The stored value is the delimiter character; expose the configured format name instead.
        "filetype": _file_format_label(file_formats, row.get("filetype")),
        "general": {
            "fileName": row.get("jobfilename") or "",
            "fileFormat": _file_format_label(file_formats, row.get("filetype")),
            "description": row.get("jobdesc") or "",
            "enable": bool(row.get("isEnabled")),
        },
        "schedule": {
            "week": response.get("runday") or "",
            "hour": hour_minute[0] if hour_minute else "",
            "minute": minute,
            "meridiem": meridiem or ("" if manual_only else "AM"),
            "buildFrequency": response.get("ScheduleType") or "",
            **({"startDate": None} if manual_only else {}),
        },
    })
    return response


def _job_rows(connection: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(READ_ALL_JOBS).mappings().all()]


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


def _subscription_from_db(client_id: int | None, email: str | None, *, uses_payroll: bool) -> SubscriptionRow:
    # Keep reading the old negative encoding until each existing job is saved again.
    if client_id is not None and client_id < 0:
        return SubscriptionRow(companyId=-client_id - 1, email=email or "")
    if uses_payroll:
        return SubscriptionRow(companyId=client_id, email=email or "")
    return SubscriptionRow(client="" if client_id is None else str(client_id), email=email or "")


def _condition_from_db(row: dict[str, Any]) -> dict[str, str]:
    symbol = row.get("condition_symbol") or ""
    stored = row.get("condition_value")
    value = "" if stored is None else str(stored)
    if symbol.startswith(DATE_CONDITION_PREFIX):
        symbol = symbol.removeprefix(DATE_CONDITION_PREFIX)
        if stored is not None:
            compact = f"{stored:08.0f}"
            value = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    return {"mappingColumn": row["mapping_column"], "condition": symbol, "value": value, "valueType": None}


def _visible_conditions(conditions, query_configuration):
    stored = [_condition_from_db(row) for row in conditions]
    # The existing condition-detail value column is numeric. Text predicates
    # round-trip through the existing varchar Conditions fragment instead.
    detail = next((row for row in query_configuration if str(row.get("recttype") or "").strip().upper() == "D"), None)
    if detail is None:
        return stored
    parsed = parsed_conditions(detail.get("Conditions") or "")
    if parsed is None:
        return stored
    numeric_columns = {(row["mappingColumn"].casefold(), row["condition"].replace("==", "=")) for row in stored}
    extra = [row for row in parsed if row["valueType"] in {"text", "date"}
             and (row["mappingColumn"].casefold(), row["condition"]) not in numeric_columns]
    if not extra:
        return stored
    return [dict(row, valueType="text") if row in extra else row for row in parsed]


def _read_full_job(connection: Any, job_id: int, *, file_formats: dict[str, str] | None = None) -> RetirementBuilderJob | None:
    main = connection.execute(READ_JOB, {"jobid": job_id}).mappings().first()
    if main is None:
        return None
    schedule = connection.execute(READ_SCHEDULE, {"jobid": job_id}).mappings().first()
    mappings = connection.execute(READ_MAPPINGS, {"jobid": job_id}).mappings().all()
    subscriptions = connection.execute(READ_SUBSCRIPTIONS, {"jobid": job_id}).mappings().all()
    sorting = connection.execute(READ_SORTING, {"jobid": job_id}).mappings().all()
    conditions = connection.execute(READ_CONDITIONS, {"jobid": job_id}).mappings().all()
    query_configuration = connection.execute(READ_QUERY_CONFIGURATION, {"jobid": job_id}).mappings().all()
    return _job_from_rows(main, schedule or {}, mappings, subscriptions, sorting, conditions, query_configuration, file_formats)


def _read_edit_job(connection: Any, job_id: int) -> RetirementBuilderJob | None:
    result_sets = []
    with connection.execute(READ_EDIT_JOB, {"jobid": job_id}) as result:
        cursor = result.cursor
        for index in range(len(_EDIT_JOB_READS)):
            if cursor is None or (index > 0 and not cursor.nextset()) or cursor.description is None:
                raise SQLAlchemyError("Missing result set while reading Retirement Builder job details")
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            if index == 0 and not rows:
                return None
            result_sets.append(rows)

    main, schedule, mappings, subscriptions, sorting, conditions, query_configuration, file_formats = result_sets
    return _job_from_rows(
        main[0], schedule[0] if schedule else {}, mappings, subscriptions, sorting, conditions,
        query_configuration, _file_formats_from_rows(file_formats),
    )


def _job_from_rows(
    main: Mapping[str, Any],
    schedule: Mapping[str, Any],
    mappings: Iterable[Mapping[str, Any]],
    subscriptions: Iterable[Mapping[str, Any]],
    sorting: Iterable[Mapping[str, Any]],
    conditions: Iterable[Mapping[str, Any]],
    query_configuration: list[Mapping[str, Any]],
    file_formats: dict[str, str] | None,
) -> RetirementBuilderJob:
    uses_payroll = any(
        row.get("recttype") == PAYROLL_QUERY_TYPE or is_payroll_record_query(row.get("recttype"), row.get("Query"))
        for row in query_configuration
    )
    sort_record_types = ("D",) if uses_payroll else ("D", LEGACY_CSV_SORT_QUERY_TYPE)
    sorting_order = None
    sort_error = None
    for kind in sort_record_types:
        for row in query_configuration:
            if str(row.get("recttype") or "").strip().upper() != kind or not row.get("Sort_Order"):
                continue
            if uses_payroll and not is_payroll_record_query(row.get("recttype"), row.get("Query")):
                continue
            if not uses_payroll and kind == "D" and row["Sort_Order"].lstrip().startswith(",") and any(
                str(legacy.get("recttype") or "").strip().upper() == LEGACY_CSV_SORT_QUERY_TYPE
                and legacy.get("Sort_Order") for legacy in query_configuration
            ):
                # The dedicated legacy row retains directions absent from an older D fragment.
                continue
            try:
                sorting_order = parse_sort_order(row["Sort_Order"])
            except InvalidRun as exc:
                if uses_payroll or kind != "D":
                    raise
                # Older CSV D rows can contain SQL fragments, rather than saved UI sorting.
                # Keep reading the dedicated legacy row or sorting details without rewriting them.
                sort_error = exc
                continue
            break
        if sorting_order is not None:
            break
    if sorting_order is None:
        sorting = list(sorting)
        if sort_error is not None and not sorting:
            raise sort_error
        sorting_order = [{
            "orderBy": str(_sort_priority(row["sort_order"])),
            "mappingColumn": row["mapping_column"],
            "direction": "DESC" if row["sort_order"] < 0 else "ASC",
        } for row in sorted(sorting, key=lambda rule: _sort_priority(rule["sort_order"]))]
    job = RetirementBuilderJob.model_validate({
        "id": int(main["jobid"]),
        "general": {
            "fileName": main.get("jobfilename"),
            "fileFormat": _file_format_label(file_formats, main.get("filetype")),
            "description": main.get("jobdesc"),
            "outputFileNameFormat": file_name_format_code(main.get("FileNameFormat") or ""),
            "enable": main.get("isEnabled"),
            "storeResultsToTable": main.get("StoreResults"),
            "reportSource": "companyPayroll" if uses_payroll else "csv",
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
                "recordType": RECORD_TYPE_LABELS.get(
                    str(row.get("jobrectype") or "").strip().upper(), row.get("jobrectype"),
                ),
                "defaultValue": row.get("jobdefaultvalue"),
                "mappingColumn": row.get("jobfieldmapping"),
                "format": row.get("jobformat"),
                "dataSetNo": row.get("DataSetNo") if row.get("DataSetNo") is not None else 1,
                "colSeqNo": row.get("ColSeqNo"),
            } for row in mappings],
        },
        "subscriptions": {
            "mergeFiles": main.get("ismerge"),
            "rows": [
                _subscription_from_db(row.get("jobclientid"), row.get("jobemailind"), uses_payroll=uses_payroll)
                for row in subscriptions
            ],
        },
        "fileSettings": {
            "sortingOrder": sorting_order,
            "conditionalStatements": _visible_conditions(conditions, query_configuration),
        },
        "queryConfiguration": [{
            "recttype": row.get("recttype"),
            "query": row.get("Query"),
            "conditions": row.get("Conditions"),
            "sortOrder": row.get("Sort_Order"),
        } for row in query_configuration],
    })
    return expand_legacy_datasets(job)


def _merge_missing_fields(current: BaseModel, original: BaseModel, fields: tuple[str, ...]) -> BaseModel:
    updates = {field: getattr(original, field) for field in fields if field not in current.model_fields_set}
    return current.model_copy(update=updates) if updates else current


def _complete_update_payload(payload: RetirementBuilderJobInput, original: RetirementBuilderJob) -> RetirementBuilderJobInput:
    sections = {
        "general": _merge_missing_fields(payload.general, original.general, ("testfileName", "fileName", "fileFormat", "description", "outputFileNameFormat", "enable", "storeResultsToTable", "selectedFile", "reportSource")),
        "schedule": _merge_missing_fields(payload.schedule, original.schedule, ("startDate", "buildFrequency", "hour", "minute", "meridiem", "week")),
        "mapping": _merge_missing_fields(payload.mapping, original.mapping, ("includeHeader", "rows")),
        "subscriptions": _merge_missing_fields(payload.subscriptions, original.subscriptions, ("mergeFiles", "rows")),
        "fileSettings": _merge_missing_fields(payload.fileSettings, original.fileSettings, ("sortingOrder", "conditionalStatements")),
        "queryConfiguration": payload.queryConfiguration if "queryConfiguration" in payload.model_fields_set else original.queryConfiguration,
    }
    return payload.model_copy(update=sections)


def _write_job_details(connection: Any, job_id: int, payload: RetirementBuilderJobInput, *,
                       replace_conditions: bool | None = None, batch: bool = False,
                       original_mappings: list[MappingRow] | None = None) -> None:
    schedule = payload.schedule
    subscriptions = payload.subscriptions
    file_settings = payload.fileSettings
    submitted_conditions = "conditionalStatements" in file_settings.model_fields_set
    general = payload.general
    uses_payroll = general.reportSource == "companyPayroll"
    catalog = _mapping_catalog(connection) if payload.mapping.rows or file_settings.sortingOrder or file_settings.conditionalStatements else {}
    keys = {key.casefold(): key for key in catalog}
    for key, (label, _) in catalog.items():
        keys.setdefault(label.casefold(), key)
    normalized_conditions = []
    payroll_types = {"record type": "text", "company name": "text", "pay date": "date",
                     "employee count": "number", "net salary total": "number"}
    for index, row in enumerate(file_settings.conditionalStatements):
        source = keys.get(row.mappingColumn.strip().casefold(), row.mappingColumn.strip())
        kind = payroll_types.get(row.mappingColumn.strip().casefold()) if uses_payroll else catalog.get(source, ("", None))[1]
        if row.valueType == "text" and kind not in {"text", "phone", "email", "ssn"}:
            _field_error(["fileSettings", "conditionalStatements", index, "value"],
                         "Choose a text column for a text condition.")
        normalized_conditions.append(row.model_copy(update={"mappingColumn": source}))
    file_settings = file_settings.model_copy(update={"conditionalStatements": normalized_conditions})
    mappings = []
    for index, row in enumerate(payload.mapping.rows):
        record_type = RECORD_TYPES.get(row.recordType.strip().casefold() or "d")
        if record_type is None:
            _field_error(["mapping", "rows", index, "recordType"], "Choose Header, Detail, or Trailer.")
        source = row.mappingColumn.strip() or row.field.strip()
        mappings.append(row.model_copy(update={
            "recordType": record_type, "mappingColumn": keys.get(source.casefold(), source),
        }))
    try:
        mappings = ordered_mappings(mappings)
        dataset_numbers = sorted({row.dataSetNo for row in mappings if row.recordType == "D"})
        if len(dataset_numbers) > 1:
            if general.storeResultsToTable:
                raise InvalidRun("Turn off Store Results to Table for multiple datasets.")
            if uses_payroll:
                raise InvalidRun("Multiple dataset cards require the rjobbuilder report source.")
            if payload.mapping.includeHeader and get_settings().retirement_header_source != "DETAIL_ALIGNED":
                raise InvalidRun("Multiple dataset headers require RETIREMENT_HEADER_SOURCE=DETAIL_ALIGNED.")
        if is_fixed_format(general.fileFormat):
            for kind in ("H", "D", "T"):
                for dataset in (dataset_numbers if kind == "D" else [None]):
                    layout = [row for row in mappings if row.recordType == kind and (dataset is None or row.dataSetNo == dataset)]
                    if layout and not (kind == "H" and payload.mapping.includeHeader):
                        widths = fixed_layout(layout)
                        if kind == "D" and payload.mapping.includeHeader:
                            for row, (_, width) in zip(layout, widths, strict=True):
                                if len(row.field.strip()) > width:
                                    raise InvalidRun(
                                        f'Column "{row.field}" needs a FIXED length of at least {len(row.field.strip())} '
                                        "characters to fit its header name.")
    except InvalidRun as exc:
        _field_error(["mapping"], str(exc))
    sorting = [row.model_copy(update={
        "mappingColumn": keys.get(row.mappingColumn.strip().casefold(), row.mappingColumn.strip()),
    }) for row in sorted(file_settings.sortingOrder, key=lambda row: _integer(row.orderBy))]
    company_ids = set(payroll_company_ids(connection).values()) if uses_payroll and subscriptions.rows else set()
    subscription_ids = []
    for index, row in enumerate(subscriptions.rows):
        path = ["subscriptions", "rows", index]
        if uses_payroll:
            if row.companyId is None or row.companyId < 1 or row.companyId not in company_ids:
                _field_error([*path, "companyId"], "Choose a payroll company from the list.")
            subscription_ids.append(row.companyId)
        else:
            if row.companyId is not None:
                _field_error([*path, "companyId"], "Payroll company subscriptions require the Company Payroll Report source.")
            _check_integer(row.client, 1, SQL_INT_MAX, [*path, "client"])
            subscription_ids.append(_integer(row.client))
    queries = []
    for index, row in enumerate(payload.queryConfiguration):
        if row.recttype.strip().upper() in (PAYROLL_QUERY_TYPE, LEGACY_CSV_SORT_QUERY_TYPE):
            continue
        try:
            kind = record_type_code(row.recttype)
        except InvalidRun as exc:
            _field_error(["queryConfiguration", index, "recttype"], str(exc))
        if not uses_payroll and not is_payroll_record_query(kind, row.query):
            queries.append(row.model_copy(update={"recttype": kind}))
    if uses_payroll:
        try:
            payroll_payload = payload.model_copy(update={
                "mapping": payload.mapping.model_copy(update={"rows": mappings}),
                "fileSettings": file_settings.model_copy(update={"sortingOrder": sorting}),
            })
            queries.extend(QueryConfigurationRow(**row) for row in payroll_record_queries(payroll_payload))
        except InvalidRun as exc:
            _field_error(["mapping"], str(exc))
    else:
        if mappings:
            try:
                export_payload = payload.model_copy(update={"fileSettings": file_settings.model_copy(update={
                    "conditionalStatements": [row.model_copy(update={
                        "mappingColumn": keys.get(row.mappingColumn.strip().casefold(), row.mappingColumn.strip()),
                    }) for row in file_settings.conditionalStatements],
                })})
                queries = [QueryConfigurationRow(**row) for row in export_record_queries(
                    export_payload, mappings, queries,
                    replace_conditions=(submitted_conditions
                                        if replace_conditions is None else replace_conditions),
                    original_mappings=ordered_mappings([
                        row.model_copy(update={
                            "recordType": RECORD_TYPES.get(row.recordType.strip().casefold() or "d"),
                            "mappingColumn": keys.get((row.mappingColumn.strip() or row.field.strip()).casefold(),
                                                      row.mappingColumn.strip() or row.field.strip()),
                        }) for row in original_mappings
                    ]) if original_mappings is not None else None,
                )]
            except InvalidRun as exc:
                _field_error(["mapping"], str(exc))
        # rjobbuilder_new appends this fragment directly after 'order by RetNum'.
        production_export = bool(mappings) or any(row.query.strip() for row in queries)
        try:
            sort_clause = ", " + ", ".join(
                row.mappingColumn if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", row.mappingColumn)
                else sql_identifier(row.mappingColumn) for row in sorting
            ) if sorting and production_export else format_sort_columns(row.mappingColumn for row in sorting)
        except InvalidRun as exc:
            _field_error(["fileSettings", "sortingOrder"], str(exc))
        queries = [
            row.model_copy(update={"sortOrder": sort_clause}) if row.recttype == "D" else row
            for row in queries
        ]
        if sorting and not any(row.recttype == "D" for row in queries):
            queries.append(QueryConfigurationRow(recttype="D", sortOrder=sort_clause))
    unique_queries = {}
    for row in queries:
        dataset = split_dataset_query(row.query)[0] if row.recttype == "D" else None
        key = (row.recttype, dataset)
        if key in unique_queries and row != unique_queries[key]:
            _field_error(["queryConfiguration"], "Keep one H/T query and one D query per dataset.")
        unique_queries[key] = row
    if ("D", None) in unique_queries and sum(kind == "D" for kind, _ in unique_queries) > 1:
        _field_error(["queryConfiguration"], "Multiple D queries need explicit dataset identities.")
    pending: list[tuple[str, dict[str, Any]]] = []

    def write(query: str, parameters: dict[str, Any]) -> None:
        if batch:
            pending.append((query, parameters))
        else:
            connection.execute(*_prepared_query(query, parameters))

    for kind in ("H", "D", "T"):
        for row in sorted((row for row in unique_queries.values() if row.recttype == kind),
                          key=lambda row: row.dataSetNo if row.dataSetNo is not None else -1):
            write(QUERY_31, {
                "jobid": job_id,
                "recttype": row.recttype,
                "Query": row.query,
                "conditionalStmt": row.conditions,
                "sortOrder": row.sortOrder,
            })
    write(QUERY_38, {
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
    })
    for row in mappings:
        write(QUERY_35, {
            "jobid": job_id,
            "jobclientcolumn": row.field,
            "jobfieldmapping": row.mappingColumn,
            "jobdefaultvalue": row.defaultValue,
            "jobformat": row.format,
            "jobrectype": row.recordType,
            "startposition": _integer(row.startPosition),
            "field_len": _integer(row.length),
            "datasetNo": row.dataSetNo,
            "colSeqNo": row.colSeqNo,
        })
    for row, client_id in zip(subscriptions.rows, subscription_ids, strict=True):
        write(QUERY_37, {
            "jobid": job_id,
            "jobclientid": client_id,
            "jobemailind": row.email,
        })
    for priority, row in enumerate(sorting, start=1):
        write(QUERY_54, {
            "jobid": job_id,
            "order": priority,
            "mapping": row.mappingColumn.strip(),
        })
    for row in file_settings.conditionalStatements:
        if row.valueType == "text":
            continue  # Saved in rjob_query.Conditions; query 55 accepts numbers only.
        date_value = condition_date(row.value)
        write(QUERY_55, {
            "jobid": job_id,
            "mapping": row.mappingColumn,
            # Keep the numeric storage contract and distinguish dates from numeric thresholds.
            "Symbol": f"{DATE_CONDITION_PREFIX}{row.condition}" if date_value else row.condition,
            "val": date_value.isoformat().replace("-", "") if date_value else row.value,
        })
    if batch:
        _execute_query_batch(connection, pending)


@router.get("/options", response_model=RetirementBuilderOptions)
def get_retirement_builder_options() -> RetirementBuilderOptions:
    return _options_from_xml()


@router.get("/clients", response_model=list[RetirementBuilderClient])
def list_retirement_builder_clients() -> list[RetirementBuilderClient]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(QUERY_43)).mappings().all()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Unable to load the client list.") from exc

    clients: dict[int, str] = {}
    for row in rows:
        client_id = row["id"]
        if client_id is not None and 1 <= client_id <= SQL_INT_MAX:
            label = (row["client_name"] or "").strip()
            clients.setdefault(int(client_id), label or str(client_id))
    return [RetirementBuilderClient(id=client_id, label=label) for client_id, label in clients.items()]


@router.get("/jobs", response_model=list[dict[str, object]])
def list_retirement_builder_jobs() -> list[dict[str, object]]:
    try:
        with engine.connect() as connection:
            rows = _job_rows(connection)
            file_formats = _file_formats(connection)
        return [_api_job_from_row(row, file_formats, manual_only=row.get("startDateTime") is None) for row in rows]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Unable to load Retirement Builder jobs from the database") from exc


def _create_job(payload: RetirementBuilderJobInput) -> RetirementBuilderJob:
    _validate_payload(payload, creating=True)
    general = payload.general
    subscriptions = payload.subscriptions
    try:
        with engine.begin() as connection:
            file_formats = _file_formats(connection)
            delimiter = _file_format_delimiter(file_formats, general.fileFormat)
            if delimiter is None:
                _field_error(["general", "fileFormat"], "Select a configured file format.")
            job_id = _execute_identity_query(connection, QUERY_36, {
                "jobdesc": general.description,
                "jobfilename": general.fileName,
                "jobstatus": "Active",
                "filetype": delimiter,
                "ismerge": subscriptions.mergeFiles,
                "mergeemail": ", ".join(row.email for row in subscriptions.rows if row.email),
                "includeHRecord": payload.mapping.includeHeader,
                "fileNameFormat": _stored_file_name_format(general.outputFileNameFormat),
                "isEnabled": general.enable,
                "StoreResult": general.storeResultsToTable,
                "enddate": None,
            })
            _write_job_details(connection, job_id, payload)
            job = _read_full_job(connection, job_id, file_formats=file_formats)
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
            job = _read_edit_job(connection, job_id)
    except (SQLAlchemyError, OdbcError) as exc:
        raise HTTPException(status_code=500, detail="Unable to load Retirement Builder job from the database") from exc
    except InvalidRun as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
    return job.model_dump()


@router.put("/jobs/{job_id}", response_model=dict[str, object])
def update_retirement_builder_job(job_id: int, payload: RetirementBuilderJobInput) -> dict[str, object]:
    _validate_payload(payload)
    try:
        with engine.begin() as connection:
            existing = _read_edit_job(connection, job_id)
            if existing is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
            effective_payload = _complete_update_payload(payload, existing)
            general = effective_payload.general
            file_formats = _file_formats(connection)
            delimiter = _file_format_delimiter(file_formats, general.fileFormat)
            if delimiter is None and "fileFormat" in payload.general.model_fields_set:
                _field_error(["general", "fileFormat"], "Select a configured file format.")
            subscriptions = effective_payload.subscriptions
            connection.execute(JOB_CONFIGURATION.update().where(JOB_CONFIGURATION.c.jobid == job_id).values(
                jobdesc=general.description,
                jobfilename=general.fileName,
                jobstatus="Active",
                joblastmodified=func.getdate(),
                filetype=delimiter if delimiter is not None else general.fileFormat,
                ismerge=subscriptions.mergeFiles,
                mergeemail=", ".join(row.email for row in subscriptions.rows if row.email),
                includeHeader=effective_payload.mapping.includeHeader,
                FileNameFormat=_stored_file_name_format(general.outputFileNameFormat),
                isEnabled=general.enable,
                StoreResults=general.storeResultsToTable,
            ))
            connection.execute(*_prepared_query(QUERY_44, {"jobid": job_id}))
            # A full form submits an empty list even for legacy SQL-only filters.
            # Preserve those on unrelated edits, but rebuild submitted visible
            # rules and clear the WHERE fragment when the last rule is removed.
            replace_conditions = "conditionalStatements" in payload.fileSettings.model_fields_set and bool(
                effective_payload.fileSettings.conditionalStatements or existing.fileSettings.conditionalStatements
            )
            _write_job_details(connection, job_id, effective_payload, replace_conditions=replace_conditions, batch=True,
                               original_mappings=existing.mapping.rows)
            updated = _read_edit_job(connection, job_id)
    except HTTPException:
        raise
    except (SQLAlchemyError, OdbcError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to update Retirement Builder job in the database") from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
    return updated.model_dump()




def _record_run(
    connection, job_id: int, run_status: str, message: str, date_range: ReportDateRange, *, scheduled: bool,
    dates_recorded: bool = False,
) -> None:
    result = connection.execute(*_prepared_query(QUERY_52, {
        "JOB_ID": job_id, "STATUS": run_status, "STAT_MSG": message,
    }))
    if result.rowcount == 0:
        connection.execute(INSERT_RUN_HISTORY, {
            "jobid": job_id, "run_status": run_status, "message": message,
        })
    if not dates_recorded:
        connection.execute(INSERT_RUN_DATES, {
            "jobid": job_id, "flag": "S" if scheduled else "A",
            "start_date": date_range.start, "end_date": date_range.end,
        })


@contextmanager
def _active_report_run(job_id: int):
    with _active_runs_lock:
        _active_runs[job_id] += 1
    try:
        yield
    finally:
        with _active_runs_lock:
            _active_runs[job_id] -= 1
            if not _active_runs[job_id]:
                del _active_runs[job_id]


def _execute_report_run(
    connection, job: RetirementBuilderJob, read_source: Callable[[RetirementBuilderJob], bytes | ProcedureSource], output: Path,
    resources: ExitStack, *, scheduled: bool = False, from_payroll_procedure: bool = False,
    date_range: ReportDateRange = ReportDateRange(),
) -> tuple[RetirementBuilderRun, list[ReportFile]]:
    run_id = uuid4()
    run_dir = output if scheduled else output / str(run_id)
    formats = _file_formats(connection)
    delimiter = _file_format_delimiter(formats, job.general.fileFormat)
    if delimiter is None:
        raise InvalidRun("Select a configured file format for this job.")
    # The stored filetype is the delimiter. A FIXED job is stored as a space, so map it
    # back to its configured name or it would be written as a space-delimited CSV.
    file_format = _file_format_label(formats, job.general.fileFormat)
    if file_format != job.general.fileFormat:
        job = job.model_copy(update={"general": job.general.model_copy(update={"fileFormat": file_format})})
    source = read_source(job)
    procedure_output = isinstance(source, ProcedureSource)
    if procedure_output:
        reports = build_procedure_report_files(job, source, delimiter)
    else:
        if from_payroll_procedure:
            job = payroll_job_with_saved_rules(job)
        source_labels = {key: label for key, (label, _) in _mapping_catalog(connection).items()}
        if from_payroll_procedure:
            source_labels.update(PAYROLL_MAPPING_FIELDS)
        reports = build_report_files(
            job, source, from_payroll_procedure=from_payroll_procedure, delimiter=delimiter,
            source_labels=source_labels, date_range=date_range,
        )
    for report in reports:
        resources.enter_context(publish_report(run_dir / report.file_name, report.csv))
    if scheduled and not reports:
        resources.enter_context(publish_report(run_dir / ".complete", ""))

    rows = [row for report in reports for row in report.rows]
    # Header and trailer lines are not data rows; report only the Detail count.
    detail_rows = sum(1 for row in rows if row.record_type == "D")
    outputs = [RetirementBuilderOutput(fileName=report.file_name, csv=report.csv, excelRows=report.excel_rows) for report in reports]
    # rjobbuilder manages its own configured result table and history dates.
    # Do not duplicate those writes in the application's CSV storage path.
    stored_rows = store_results(connection, job.id, run_id, rows) if job.general.storeResultsToTable and not procedure_output else 0
    message = f"Generated {detail_rows} rows. Stored {stored_rows} rows." if reports else "No matching records. No files generated."
    _record_run(connection, job.id, "Success", message, date_range, scheduled=scheduled, dates_recorded=procedure_output)
    run = RetirementBuilderRun(
        runId=run_id, rowCount=detail_rows, storedRows=stored_rows, delimiter=delimiter,
        fileName=outputs[0].fileName if outputs else "", csv=outputs[0].csv if outputs else "", files=outputs,
        excelRows=outputs[0].excelRows if outputs else None,
    )
    return run, reports


def _attempt_report_run(
    connection, job: RetirementBuilderJob, read_source: Callable[[RetirementBuilderJob], bytes | ProcedureSource], output: Path,
    resources: ExitStack, *, scheduled: bool = False, from_payroll_procedure: bool = False,
    date_range: ReportDateRange = ReportDateRange(),
) -> tuple[RetirementBuilderRun, list[ReportFile]] | Exception:
    resources.enter_context(_active_report_run(job.id))
    try:
        with ExitStack() as attempt:
            with connection.begin_nested():
                result = _execute_report_run(
                    connection, job, read_source, output, attempt, scheduled=scheduled,
                    from_payroll_procedure=from_payroll_procedure, date_range=date_range,
                )
            resources.enter_context(attempt.pop_all())
        return result
    except (InvalidRun, OSError, SQLAlchemyError) as exc:
        # The savepoint rolls back partial results while the job lock still serializes attempts.
        message = str(exc)[:255] if isinstance(exc, InvalidRun) else "Unable to complete the report."
        try:
            _record_run(connection, job.id, "Failed", message, date_range, scheduled=scheduled)
        except SQLAlchemyError:
            logger.exception("Could not record failure for retirement job %s.", job.id, extra={"job_id": job.id})
            raise exc
        # Let the caller commit the failure before returning the original error.
        return exc


def _read_report_source(
    connection, job: RetirementBuilderJob, input_dir: Path, date_range: ReportDateRange = ReportDateRange(),
    *, scheduled: bool = False,
) -> bytes | ProcedureSource:
    if job.general.reportSource == "companyPayroll" or uses_retirement_queries(job):
        return load_payroll_source(connection, job, date_range, run_type="S" if scheduled else "A")
    return load_report_source(input_dir, job.id)


def _run_job(job_id: int, source: bytes | None, date_range: ReportDateRange = ReportDateRange()) -> RetirementBuilderRun:
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
            def read_source(run_job: RetirementBuilderJob) -> bytes | ProcedureSource:
                return source if source is not None else _read_report_source(connection, run_job, settings.report_input_dir, date_range)

            result = _attempt_report_run(
                connection, job, read_source, output / "manual" / str(job_id), resources,
                from_payroll_procedure=source is None and job.general.reportSource == "companyPayroll",
                date_range=date_range,
            )
        if isinstance(result, Exception):
            raise result
        run, reports = result
    except InvalidRun as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="The job could not be completed. No results were saved.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="The generated file could not be saved. Check REPORT_OUTPUT_DIR.") from exc
    if source is None and reports:
        run.emailDelivery = send_subscribed_reports(settings, job, reports)
    return run


@router.post(
    "/jobs/{job_id}/run",
    response_model=RetirementBuilderRun,
    openapi_extra={"requestBody": {
        "description": "Omit the body to use the job's saved report source.",
        "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
    }},
)
async def run_retirement_builder_job(
    job_id: int, request: Request, start_date: date | None = None, end_date: date | None = None,
) -> RetirementBuilderRun:
    if start_date not in (None, UNBOUNDED_RUN_DATE) and end_date not in (None, UNBOUNDED_RUN_DATE) and start_date > end_date:
        raise HTTPException(status_code=422, detail="Start Date must be on or before End Date.")
    date_range = ReportDateRange(start_date or UNBOUNDED_RUN_DATE, end_date or UNBOUNDED_RUN_DATE)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    source = bytearray()
    async for chunk in request.stream():
        if chunk and content_type != "text/csv":
            raise HTTPException(status_code=415, detail="Send a CSV file with Content-Type text/csv.")
        if len(source) + len(chunk) > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail="The source CSV can be up to 5 MB.")
        source.extend(chunk)
    return await run_in_threadpool(_run_job, job_id, bytes(source) if source else None, date_range)

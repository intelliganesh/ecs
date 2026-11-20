import csv
from datetime import datetime
from io import StringIO
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Literal

import pyodbc
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.config import SQL_IDENTIFIER, get_settings
from app.retirement_procedure import ProcedureResultSet, ProcedureSource, uses_retirement_queries
from app.retirement_conditions import condition_fragment, parsed_conditions
from app.retirement_results import (
    MAX_ROWS, MAX_SOURCE_BYTES, RECORD_TYPES, InvalidRun, ReportDateRange, _name_format, _source_key,
    condition_date, format_sort_columns, parse_sort_order,
)

if TYPE_CHECKING:
    from app.routers.retirement_builder import QueryConfigurationRow, RetirementBuilderJob, RetirementBuilderJobInput


PAYROLL_QUERY_TYPE = "PAYROLL"
PAYROLL_RECORD_TYPES = ("H", "D", "T")
_PAYROLL_RECORD_MARKER = "/* company payroll */"
PAYROLL_QUERIES_FILE = Path(__file__).resolve().parents[1] / "config" / "payroll_record_queries.json"
PAYROLL_MAPPING_FIELDS = {
    "rectype": "Record Type",
    "company_name": "Company Name",
    "payroll_month": "Pay Date",
    "employee_count": "Employee Count",
    "net_salary_total": "Net Salary Total",
}
PAYROLL_COLUMNS = tuple(PAYROLL_MAPPING_FIELDS.values())
_COLUMNS_BY_KEY = {column.casefold(): column for column in PAYROLL_COLUMNS}
PAYROLL_COLUMN_KEYS = frozenset(_COLUMNS_BY_KEY)
_PAYROLL_KEYS_BY_LABEL = {label.casefold(): key for key, label in PAYROLL_MAPPING_FIELDS.items()}
_PROCEDURE_CALL = re.compile(
    rf"^INSERT INTO @payroll EXEC (?:{SQL_IDENTIFIER}\.{SQL_IDENTIFIER}|\[{SQL_IDENTIFIER}\]\.\[{SQL_IDENTIFIER}\]);$",
    re.MULTILINE,
)
READ_PAYROLL_COMPANY_IDS = text("""
SELECT company_name, CASE WHEN COUNT_BIG(*) = 1 THEN MIN(id) END
FROM dbo.companies WITH (HOLDLOCK)
GROUP BY company_name
""")


def payroll_company_ids(connection: Connection) -> dict[str, int | None]:
    return {name: company_id for name, company_id in connection.execute(READ_PAYROLL_COMPANY_IDS)}


def _needs_company_ids(job: "RetirementBuilderJob | RetirementBuilderJobInput") -> bool:
    return "client id" in _name_format(job.general.outputFileNameFormat) or any(
        row.companyId is not None for row in job.subscriptions.rows
    )


def is_payroll_record_query(recttype: str | None, query: str | None) -> bool:
    return bool(recttype and recttype.strip().upper() in PAYROLL_RECORD_TYPES and query and query.startswith(_PAYROLL_RECORD_MARKER))


def _payroll_procedure_name() -> str:
    schema, procedure = get_settings().payroll_report_procedure.split(".")
    return f"[{schema}].[{procedure}]"


def _payroll_column(value: str) -> str | None:
    key = value.strip().casefold()
    return PAYROLL_MAPPING_FIELDS.get(key) or _COLUMNS_BY_KEY.get(key)


def payroll_record_queries(job: "RetirementBuilderJobInput") -> list[dict[str, str]]:
    payroll_report_query(job)  # Validate the configured mappings and source columns before writing the rows.
    settings = job.fileSettings
    conditions = condition_fragment([
        rule.model_copy(update={"mappingColumn": _payroll_column(rule.mappingColumn)})
        for rule in settings.conditionalStatements
    ], where=False)
    sorting = format_sort_columns(
        rule.mappingColumn.strip() if rule.mappingColumn.strip().casefold() in PAYROLL_MAPPING_FIELDS
        else _PAYROLL_KEYS_BY_LABEL[rule.mappingColumn.strip().casefold()]
        for rule in sorted(settings.sortingOrder, key=lambda row: int(row.orderBy or "0"))
    )

    try:
        templates = json.loads(PAYROLL_QUERIES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Unable to read the payroll H, D, and T query template file.") from exc
    if not isinstance(templates, dict) or set(templates) != set(PAYROLL_RECORD_TYPES) or any(
        not isinstance(query, str) or not is_payroll_record_query(recttype, query)
        for recttype, query in templates.items()
    ):
        raise RuntimeError("The payroll query template file must contain one valid H, D, and T query.")
    return [
        {
            "recttype": kind,
            "query": templates[kind],
            "conditions": conditions if kind == "D" else "",
            "sortOrder": sorting if kind == "D" else "",
        }
        for kind in PAYROLL_RECORD_TYPES
    ]


def _saved_record_queries(job: "RetirementBuilderJob") -> dict[str, "QueryConfigurationRow"]:
    rows = [row for row in job.queryConfiguration if is_payroll_record_query(row.recttype, row.query)]
    records = {row.recttype.strip().upper(): row for row in rows}
    if records and (len(rows) != 3 or set(records) != set(PAYROLL_RECORD_TYPES)):
        raise InvalidRun("This payroll job needs one saved H, D, and T query. Save the job again before running it.")
    return records


def payroll_job_with_saved_rules(job: "RetirementBuilderJob") -> "RetirementBuilderJob":
    detail = _saved_record_queries(job).get("D")
    if detail is None:
        return job

    conditions = parsed_conditions(detail.conditions)
    if conditions is None or any(rule["mappingColumn"].casefold() not in PAYROLL_COLUMN_KEYS for rule in conditions):
        raise InvalidRun("The saved payroll condition is invalid. Save the job again before running it.")
    for rule in conditions:
        column = rule["mappingColumn"].casefold()
        if column in {"company name", "record type"}:
            rule["valueType"] = "text"
        elif rule["valueType"] == "text":
            raise InvalidRun("The saved payroll condition value does not match its column type.")

    sorting = parse_sort_order(detail.sortOrder)
    if any(_payroll_column(rule["mappingColumn"]) is None for rule in sorting):
        raise InvalidRun("The saved payroll sort order is invalid. Save the job again before running it.")
    sorting = [{**rule, "mappingColumn": _payroll_column(rule["mappingColumn"])} for rule in sorting]

    settings = type(job.fileSettings).model_validate({"conditionalStatements": conditions, "sortingOrder": sorting})
    return job.model_copy(update={"fileSettings": settings})


def payroll_report_query(job: "RetirementBuilderJob | RetirementBuilderJobInput", *, for_run: bool = False) -> str:
    if for_run:
        return (
            f"EXEC {_payroll_procedure_name()} "
            "@client_id = ?, @paystartdate = ?, @payenddate = ?, @runType = ?"
        )
    columns = {"Record Type"}
    kinds = set()
    for mapping in job.mapping.rows:
        kind = RECORD_TYPES.get(mapping.recordType.strip().casefold() or "detail")
        if kind is None or not mapping.field.strip():
            raise InvalidRun("Every mapping needs an output field and a supported record type.")
        kinds.add(kind)
        source = _source_key(mapping)
        column = PAYROLL_MAPPING_FIELDS.get(source) or _COLUMNS_BY_KEY.get(source)
        if column:
            columns.add(column)
        elif not mapping.defaultValue:
            raise InvalidRun(f'The Company Payroll Report does not supply "{mapping.mappingColumn or mapping.field}".')
    if not kinds:
        raise InvalidRun("Add at least one mapping for the Company Payroll Report.")

    name_format = _name_format(job.general.outputFileNameFormat)
    if _needs_company_ids(job):
        columns.add("Company Name")
    if "payday" in name_format:
        columns.add("Pay Date")
    rules = [*job.fileSettings.sortingOrder, *job.fileSettings.conditionalStatements]
    for rule in rules:
        column = _payroll_column(rule.mappingColumn)
        if column is None:
            raise InvalidRun(f'The Company Payroll Report cannot sort or filter by "{rule.mappingColumn}".')
        columns.add(column)
    for rule in job.fileSettings.conditionalStatements:
        if rule.valueType != "text" and condition_date(rule.value) is not None and _payroll_column(rule.mappingColumn) != "Pay Date":
            raise InvalidRun("Use Pay Date for a payroll date condition.")

    projection = ", ".join(
        "CASE WHEN [Record Type] = 'H' THEN NULL ELSE [Pay Date] END AS [Pay Date]"
        if column == "Pay Date" else f"[{column}]"
        for column in PAYROLL_COLUMNS if column in columns
    )
    record_types = ", ".join(f"'{kind}'" for kind in sorted(kinds))
    return (
        "DECLARE @payroll TABLE ([Record Sequence] int, [Record Type] varchar(1), [Company Name] varchar(120), "
        "[Pay Date] datetime, [Employee Count] int, [Net Salary Total] numeric(38,2));\n"
        f"INSERT INTO @payroll EXEC {_payroll_procedure_name()};\n"
        f"SELECT TOP ({MAX_ROWS + 1}) {projection} FROM @payroll WHERE [Record Type] IN ({record_types}) "
        "ORDER BY [Record Sequence], [Company Name] DESC, [Pay Date];"
    )


def load_payroll_source(
    connection: Connection, job: "RetirementBuilderJob", date_range: ReportDateRange = ReportDateRange(),
    *, run_type: Literal["A", "S"] = "A",
) -> bytes | ProcedureSource:
    if run_type not in ("A", "S"):
        raise InvalidRun("Choose A for a manual run or S for a scheduled run.")
    production_queries = uses_retirement_queries(job)
    use_saved_records = bool(_saved_record_queries(job)) if not production_queries else False
    if not production_queries and not use_saved_records:
        saved = [row.query for row in job.queryConfiguration if row.recttype == PAYROLL_QUERY_TYPE]
        # Legacy jobs can still run with a changed procedure name during the database upgrade.
        expected = payroll_report_query(job)
        if len(saved) != 1 or _PROCEDURE_CALL.subn("", saved[0]) != (_PROCEDURE_CALL.sub("", expected), 1):
            raise InvalidRun("The saved payroll query does not match this job. Save the job again before running it.")

    cursor = connection.connection.cursor()
    result_sets = []
    row_count = 0
    size_check = StringIO(newline="")
    size_writer = csv.writer(size_check)
    try:
        # The procedure's client_id parameter identifies the report job, not a subscribed client.
        cursor.execute(payroll_report_query(job, for_run=True), job.id, date_range.start, date_range.end, run_type)
        while True:
            if cursor.description is not None:
                columns = tuple(str(column[0] or "") for column in cursor.description)
                rows = []
                size_writer.writerow(columns)
                for row in cursor:
                    row_count += 1
                    if row_count > MAX_ROWS:
                        raise InvalidRun(f"The procedure can return up to {MAX_ROWS:,} rows.")
                    values = tuple(
                        value.date().isoformat() if isinstance(value, datetime)
                        else "" if value is None else str(value)
                        for value in row
                    )
                    if len(values) != len(columns):
                        raise InvalidRun("A procedure row does not match its result-set columns.")
                    rows.append(values)
                    size_writer.writerow(values)
                    if size_check.tell() > MAX_SOURCE_BYTES:
                        raise InvalidRun("The procedure output exceeds the 5 MB source limit.")
                result_sets.append(ProcedureResultSet(columns, tuple(rows)))
            # Advance through every result set and trailing statements. In the
            # supplied procedure, history is written after its last SELECT.
            if not cursor.nextset():
                break
    except pyodbc.Error as exc:
        raise InvalidRun("The Company Payroll Report could not be read from the database.") from exc
    finally:
        cursor.close()

    if not result_sets:
        raise InvalidRun("The report procedure returned no result set.")
    if len(size_check.getvalue().encode("utf-8")) > MAX_SOURCE_BYTES:
        raise InvalidRun("The procedure output exceeds the 5 MB source limit.")
    if production_queries or len(result_sets) != 1 or "Record Type" not in result_sets[0].columns:
        return ProcedureSource(tuple(result_sets))

    # Retain compatibility with procedures returning the older single, typed
    # payroll table. The runtime call still uses the same four-input contract.
    result, = result_sets
    needs_company_ids = _needs_company_ids(job)
    company_ids = payroll_company_ids(connection) if needs_company_ids else {}
    headings = list(result.columns)
    if needs_company_ids and "Company Name" not in headings:
        raise InvalidRun("The payroll output needs Company Name to resolve company subscriptions.")
    company_column = headings.index("Company Name") if needs_company_ids else None
    if needs_company_ids:
        headings.append("Client ID")
    csv_output = StringIO(newline="")
    writer = csv.writer(csv_output)
    writer.writerow(headings)
    configured_kinds = {RECORD_TYPES.get(row.recordType.strip().casefold() or "detail") for row in job.mapping.rows}
    type_index = headings.index("Record Type")
    date_index = headings.index("Pay Date") if "Pay Date" in headings else None
    for row in result.rows:
        values = list(row)
        kind = RECORD_TYPES.get(values[type_index].strip().casefold())
        if kind not in configured_kinds:
            continue
        if kind == "H" and date_index is not None:
            values[date_index] = ""
        if company_column is not None:
            company_id = company_ids.get(row[company_column])
            if company_id is None:
                raise InvalidRun("The payroll company name must match exactly one company ID for file grouping or email subscriptions.")
            values.append(company_id)
        writer.writerow(values)
    source = csv_output.getvalue().encode("utf-8")
    if len(source) > MAX_SOURCE_BYTES:
        raise InvalidRun("The Company Payroll Report exceeds the 5 MB source limit.")
    return source

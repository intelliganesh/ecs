import csv
from datetime import datetime
from io import StringIO
import re
from typing import TYPE_CHECKING

import pyodbc
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.config import SQL_IDENTIFIER, get_settings
from app.retirement_results import (
    MAX_ROWS, MAX_SOURCE_BYTES, RECORD_TYPES, InvalidRun, _name_format, _source_key, format_sort_order, parse_sort_order,
)

if TYPE_CHECKING:
    from app.routers.retirement_builder import QueryConfigurationRow, RetirementBuilderJob, RetirementBuilderJobInput


PAYROLL_QUERY_TYPE = "PAYROLL"
PAYROLL_RECORD_TYPES = ("H", "D", "T")
_PAYROLL_RECORD_MARKER = "/* company payroll */"
PAYROLL_COLUMNS = ("Record Type", "Company Name", "Pay Date", "Employee Count", "Net Salary Total")
_COLUMNS_BY_KEY = {column.casefold(): column for column in PAYROLL_COLUMNS}
PAYROLL_COLUMN_KEYS = frozenset(_COLUMNS_BY_KEY)
_PROCEDURE_CALL = re.compile(
    rf"^INSERT INTO @payroll EXEC (?:{SQL_IDENTIFIER}\.{SQL_IDENTIFIER}|\[{SQL_IDENTIFIER}\]\.\[{SQL_IDENTIFIER}\]);$",
    re.MULTILINE,
)
_SAVED_CONDITION = re.compile(r"\[([^\[\]]+)\] (<=|>=|!=|<>|[=<>]) (-?[0-9]{1,16}(?:\.[0-9]{1,2})?)")
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


def payroll_record_queries(connection: Connection, job: "RetirementBuilderJobInput") -> list[dict[str, str]]:
    payroll_report_query(job)  # Validate the configured mappings and source columns before writing the rows.
    settings = job.fileSettings
    conditions = []
    for rule in settings.conditionalStatements:
        column = _COLUMNS_BY_KEY[rule.mappingColumn.strip().casefold()]
        operator = "=" if rule.condition == "==" else rule.condition
        conditions.append(f"[{column}] {operator} {rule.value}")
    sorting = format_sort_order(
        (_COLUMNS_BY_KEY[rule.mappingColumn.strip().casefold()], rule.direction)
        for rule in sorted(settings.sortingOrder, key=lambda row: int(row.orderBy or "0"))
    )

    template_rows = connection.execute(text(f"EXEC {_payroll_procedure_name()} @templates_only = 1")).tuples().all()
    templates = dict(template_rows)
    if len(template_rows) != len(PAYROLL_RECORD_TYPES) or set(templates) != set(PAYROLL_RECORD_TYPES) or any(
        not is_payroll_record_query(recttype, query) for recttype, query in templates.items()
    ):
        raise RuntimeError("The payroll H, D, and T query templates are missing or invalid.")
    return [
        {
            "recttype": kind,
            "query": templates[kind],
            "conditions": " AND ".join(conditions) if kind == "D" else "",
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

    conditions = []
    for clause in detail.conditions.split(" AND ") if detail.conditions else []:
        match = _SAVED_CONDITION.fullmatch(clause)
        if match is None or match[1].casefold() not in PAYROLL_COLUMN_KEYS:
            raise InvalidRun("The saved payroll condition is invalid. Save the job again before running it.")
        conditions.append({"mappingColumn": match[1], "condition": match[2], "value": match[3]})

    sorting = parse_sort_order(detail.sortOrder)
    if any(rule["mappingColumn"].casefold() not in PAYROLL_COLUMN_KEYS for rule in sorting):
        raise InvalidRun("The saved payroll sort order is invalid. Save the job again before running it.")

    settings = type(job.fileSettings).model_validate({"conditionalStatements": conditions, "sortingOrder": sorting})
    return job.model_copy(update={"fileSettings": settings})


def payroll_report_query(job: "RetirementBuilderJob | RetirementBuilderJobInput", *, use_saved_records: bool = False) -> str:
    columns = {"Record Type"}
    kinds = set()
    for mapping in job.mapping.rows:
        kind = RECORD_TYPES.get(mapping.recordType.strip().casefold() or "detail")
        if kind is None or not mapping.field.strip():
            raise InvalidRun("Every mapping needs an output field and a supported record type.")
        kinds.add(kind)
        column = _COLUMNS_BY_KEY.get(_source_key(mapping))
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
        column = _COLUMNS_BY_KEY.get(rule.mappingColumn.strip().casefold())
        if column is None:
            raise InvalidRun(f'The Company Payroll Report cannot sort or filter by "{rule.mappingColumn}".')
        columns.add(column)

    projection = ", ".join(
        "CASE WHEN [Record Type] = 'H' THEN NULL ELSE [Pay Date] END AS [Pay Date]"
        if column == "Pay Date" else f"[{column}]"
        for column in PAYROLL_COLUMNS if column in columns
    )
    record_types = ", ".join(f"'{kind}'" for kind in sorted(kinds))
    job_parameter = " @jobid = ?" if use_saved_records else ""
    return (
        "DECLARE @payroll TABLE ([Record Sequence] int, [Record Type] varchar(1), [Company Name] varchar(120), "
        "[Pay Date] datetime, [Employee Count] int, [Net Salary Total] numeric(38,2));\n"
        f"INSERT INTO @payroll EXEC {_payroll_procedure_name()}{job_parameter};\n"
        f"SELECT TOP ({MAX_ROWS + 1}) {projection} FROM @payroll WHERE [Record Type] IN ({record_types}) "
        "ORDER BY [Record Sequence], [Company Name] DESC, [Pay Date];"
    )


def load_payroll_source(connection: Connection, job: "RetirementBuilderJob") -> bytes:
    use_saved_records = bool(_saved_record_queries(job))
    expected = payroll_report_query(job, use_saved_records=use_saved_records)
    if not use_saved_records:
        saved = [row.query for row in job.queryConfiguration if row.recttype == PAYROLL_QUERY_TYPE]
        # Legacy jobs can still run with a changed procedure name during the database upgrade.
        if len(saved) != 1 or _PROCEDURE_CALL.subn("", saved[0]) != (_PROCEDURE_CALL.sub("", expected), 1):
            raise InvalidRun("The saved payroll query does not match this job. Save the job again before running it.")

    needs_company_ids = _needs_company_ids(job)
    company_ids = payroll_company_ids(connection) if needs_company_ids else {}

    csv_output = StringIO(newline="")
    writer = csv.writer(csv_output)
    cursor = connection.connection.cursor()
    try:
        if use_saved_records:
            cursor.execute(expected, job.id)
        else:
            cursor.execute(expected)
        while cursor.description is None:
            if not cursor.nextset():
                raise InvalidRun("The Company Payroll Report returned no result set.")
        headings = [column[0] for column in cursor.description]
        company_column = headings.index("Company Name") if needs_company_ids else None
        if needs_company_ids:
            headings.append("Client ID")
        writer.writerow(headings)
        for row_number, row in enumerate(cursor, start=1):
            if row_number > MAX_ROWS:
                raise InvalidRun(f"The Company Payroll Report can contain up to {MAX_ROWS:,} rows.")
            values = [value.date().isoformat() if isinstance(value, datetime) else value for value in row]
            if company_column is not None:
                company_id = company_ids.get(row[company_column])
                if company_id is None:
                    raise InvalidRun("The payroll company name must match exactly one company ID for file grouping or email subscriptions.")
                values.append(company_id)
            writer.writerow(values)
            if csv_output.tell() > MAX_SOURCE_BYTES:
                raise InvalidRun("The Company Payroll Report exceeds the 5 MB source limit.")
    except pyodbc.Error as exc:
        raise InvalidRun("The Company Payroll Report could not be read from the database.") from exc
    finally:
        cursor.close()
    source = csv_output.getvalue().encode("utf-8")
    if len(source) > MAX_SOURCE_BYTES:
        raise InvalidRun("The Company Payroll Report exceeds the 5 MB source limit.")
    return source

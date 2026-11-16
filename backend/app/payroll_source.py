import csv
from datetime import datetime
from io import StringIO
import re
from typing import TYPE_CHECKING

import pyodbc
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.config import SQL_IDENTIFIER, get_settings
from app.retirement_results import MAX_ROWS, MAX_SOURCE_BYTES, RECORD_TYPES, InvalidRun, _name_format, _source_key

if TYPE_CHECKING:
    from app.routers.retirement_builder import RetirementBuilderJob, RetirementBuilderJobInput


PAYROLL_QUERY_TYPE = "PAYROLL"
PAYROLL_COLUMNS = ("Record Type", "Company Name", "Pay Date", "Employee Count", "Net Salary Total")
_COLUMNS_BY_KEY = {column.casefold(): column for column in PAYROLL_COLUMNS}
PAYROLL_COLUMN_KEYS = frozenset(_COLUMNS_BY_KEY)
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


def payroll_report_query(job: "RetirementBuilderJob | RetirementBuilderJobInput") -> str:
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
    schema, procedure = get_settings().payroll_report_procedure.split(".")
    return (
        "DECLARE @payroll TABLE ([Record Sequence] int, [Record Type] varchar(1), [Company Name] varchar(120), "
        "[Pay Date] datetime, [Employee Count] int, [Net Salary Total] numeric(38,2));\n"
        f"INSERT INTO @payroll EXEC [{schema}].[{procedure}];\n"
        f"SELECT TOP ({MAX_ROWS + 1}) {projection} FROM @payroll WHERE [Record Type] IN ({record_types}) "
        "ORDER BY [Record Sequence], [Company Name] DESC, [Pay Date];"
    )


def load_payroll_source(connection: Connection, job: "RetirementBuilderJob") -> bytes:
    expected = payroll_report_query(job)
    saved = [row.query for row in job.queryConfiguration if row.recttype == PAYROLL_QUERY_TYPE]
    # Compare the approved query shape so a configured name change also applies to existing jobs.
    if len(saved) != 1 or _PROCEDURE_CALL.subn("", saved[0]) != (_PROCEDURE_CALL.sub("", expected), 1):
        raise InvalidRun("The saved payroll query does not match this job. Save the job again before running it.")

    needs_company_ids = _needs_company_ids(job)
    company_ids = payroll_company_ids(connection) if needs_company_ids else {}

    csv_output = StringIO(newline="")
    writer = csv.writer(csv_output)
    cursor = connection.connection.cursor()
    try:
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

import csv
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING

import pyodbc
from sqlalchemy.engine import Connection

from app.retirement_results import MAX_ROWS, MAX_SOURCE_BYTES, RECORD_TYPES, InvalidRun, _name_format, _source_key

if TYPE_CHECKING:
    from app.routers.retirement_builder import RetirementBuilderJob, RetirementBuilderJobInput


PAYROLL_QUERY_TYPE = "PAYROLL"
PAYROLL_COLUMNS = ("Record Type", "Company Name", "Pay Date", "Employee Count", "Net Salary Total")
_COLUMNS_BY_KEY = {column.casefold(): column for column in PAYROLL_COLUMNS}
PAYROLL_COLUMN_KEYS = frozenset(_COLUMNS_BY_KEY)


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
    if "client id" in name_format:
        raise InvalidRun("Choose a file name format without Client ID for the Company Payroll Report.")
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
    return (
        "DECLARE @payroll TABLE ([Record Sequence] int, [Record Type] varchar(1), [Company Name] varchar(120), "
        "[Pay Date] datetime, [Employee Count] int, [Net Salary Total] numeric(38,2));\n"
        "INSERT INTO @payroll EXEC dbo.usp_CompanyPayrollReport;\n"
        f"SELECT TOP ({MAX_ROWS + 1}) {projection} FROM @payroll WHERE [Record Type] IN ({record_types}) "
        "ORDER BY [Record Sequence], [Company Name] DESC, [Pay Date];"
    )


def load_payroll_source(connection: Connection, job: "RetirementBuilderJob") -> bytes:
    expected = payroll_report_query(job)
    saved = [row.query for row in job.queryConfiguration if row.recttype == PAYROLL_QUERY_TYPE]
    if saved != [expected]:
        raise InvalidRun("The saved payroll query does not match this job. Save the job again before running it.")

    csv_output = StringIO(newline="")
    writer = csv.writer(csv_output)
    cursor = connection.connection.cursor()
    try:
        cursor.execute(saved[0])
        while cursor.description is None:
            if not cursor.nextset():
                raise InvalidRun("The Company Payroll Report returned no result set.")
        writer.writerow(column[0] for column in cursor.description)
        for row_number, row in enumerate(cursor, start=1):
            if row_number > MAX_ROWS:
                raise InvalidRun(f"The Company Payroll Report can contain up to {MAX_ROWS:,} rows.")
            writer.writerow(value.date().isoformat() if isinstance(value, datetime) else value for value in row)
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

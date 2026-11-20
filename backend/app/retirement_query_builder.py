"""Build SELECT fragments consumed by the production rjobbuilder_new procedure.

The procedure supplies FROM, WHERE and ORDER BY separately. These fragments must
not contain a FROM clause or fabricated output aliases. This module never runs SQL.
"""

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
import re
from typing import TYPE_CHECKING

from app.retirement_results import COMPARISONS, DATE_FORMATS, NUMBER_FORMATS, NUMERIC_MASK_PATTERN, SSN_FORMATS, InvalidRun, _format_value, condition_date
from app.retirement_projection import replace_detail_projection

if TYPE_CHECKING:
    from app.routers.retirement_builder import MappingRow, QueryConfigurationRow, RetirementBuilderJobInput


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    if not value or "\x00" in value or len(value) > 128:
        raise InvalidRun("Choose a mapping column with a valid SQL Server identifier.")
    return "[" + value.replace("]", "]]") + "]"


def ordered_mappings(rows: Iterable["MappingRow"]) -> list["MappingRow"]:
    rows = list(rows)
    sequences: dict[int, int] = {}
    for row in rows:
        if row.colSeqNo is not None:
            sequences[row.dataSetNo] = max(sequences.get(row.dataSetNo, 0), row.colSeqNo)
    ordered = []
    positions = set()
    for row in rows:
        sequence = row.colSeqNo
        if sequence is None:
            sequence = sequences.get(row.dataSetNo, 0) + 1
            sequences[row.dataSetNo] = sequence
        if sequence > 2_147_483_647:
            raise InvalidRun("The mapping column sequence exceeds the SQL Server integer limit.")
        position = (row.recordType, row.dataSetNo, sequence)
        if position in positions:
            raise InvalidRun("Use a unique column sequence within each record type and dataset.")
        positions.add(position)
        ordered.append(row.model_copy(update={"colSeqNo": sequence}))
    return sorted(ordered, key=lambda row: (row.dataSetNo, row.colSeqNo))


def _expression(row: "MappingRow") -> tuple[str, bool]:
    """Return an unaliased expression and whether it retains its source name."""
    source = row.mappingColumn.strip()
    if not source or source.casefold() == "default":
        return sql_literal(_format_value(row.defaultValue, row)), False
    expression = sql_identifier(source)
    named = True
    if row.defaultValue:
        expression = f"COALESCE(NULLIF(CONVERT(varchar(max), {expression}), ''), {sql_literal(row.defaultValue)})"
        named = False
    name = row.format.strip()
    if not name:
        return expression, named
    if name in DATE_FORMATS:
        pattern = DATE_FORMATS[name]
        style = {"YYYYMMDD": 112, "MMDDYYYY": 101, "MM/DD/YYYY": 101, "MM-DD-YYYY": 110,
                 "YYYY-MM-DD": 23, "DD/MM/YYYY": 103, "DD-MM-YYYY": 105}[pattern]
        expression = f"CONVERT(varchar(10), CONVERT(date, {expression}), {style})"
        if pattern == "MMDDYYYY":
            expression = f"REPLACE({expression}, '/', '')"
    elif name in {"Trim Whitespace", "Uppercase", "Lowercase"}:
        expression = f"CONVERT(varchar(max), {expression})"
        expression = f"LTRIM(RTRIM({expression}))" if name == "Trim Whitespace" else f"{'UPPER' if name == 'Uppercase' else 'LOWER'}({expression})"
    elif name in {"LA", "LA - Left Justified", "RA", "RA - Right Justified"}:
        width = int(row.length or "0")
        if not 0 <= width <= 1_000:
            raise InvalidRun("Use a padding length between 0 and 1,000 characters.")
        text = f"CONVERT(varchar(max), {expression})"
        spaces = f"REPLICATE(' ', CASE WHEN LEN({text}) < {width} THEN {width} - LEN({text}) ELSE 0 END)"
        expression = f"{spaces} + {text}" if name.startswith("RA") else f"{text} + {spaces}"
    elif name in SSN_FORMATS:
        expression = f"REPLACE(LTRIM(RTRIM(CONVERT(varchar(max), {expression}))), '-', '')"
        if name.startswith("XXX-"):
            expression = f"STUFF(STUFF({expression}, 4, 0, '-'), 7, 0, '-')"
    elif name in NUMBER_FORMATS or NUMERIC_MASK_PATTERN.fullmatch(name):
        mask = NUMERIC_MASK_PATTERN.fullmatch(name)
        places, grouping = NUMBER_FORMATS[name] if mask is None else (len(mask[2] or ""), "")
        if places > 18:
            raise InvalidRun("SQL export numeric formats support at most 18 decimal places.")
        pattern = ("#,##0" if grouping else "0") + ("." + ("#" if mask else "0") * places if places else "")
        if mask and mask[1]:
            pattern = f"${pattern};-${pattern};${pattern}"
        expression = f"FORMAT(ROUND(CONVERT(decimal(38,18), {expression}), {places}), {sql_literal(pattern)}, 'en-US')"
    else:
        raise InvalidRun(f'SQL export formatting for "{name}" is not supported; its SQL behavior must be confirmed first.')
    return expression, False


def _conditions(job: "RetirementBuilderJobInput") -> str:
    clauses = []
    for rule in job.fileSettings.conditionalStatements:
        operator = rule.condition.strip()
        if operator not in COMPARISONS:
            raise InvalidRun("Choose a supported comparison operator.")
        date = condition_date(rule.value) if rule.valueType != "text" else None
        if rule.valueType == "text":
            value = sql_literal(rule.value)
        elif date is not None:
            value = sql_literal(date.isoformat())
        else:
            try:
                number = Decimal(rule.value)
                if not number.is_finite():
                    raise InvalidOperation
            except InvalidOperation as exc:
                raise InvalidRun("Enter a numeric or date condition value.") from exc
            value = format(number, "f")
        clauses.append(f"{sql_identifier(rule.mappingColumn)} {'=' if operator == '==' else operator} {value}")
    return "WHERE " + " AND ".join(clauses) if clauses else ""


def export_record_queries(job: "RetirementBuilderJobInput", mappings: list["MappingRow"],
                          saved: list["QueryConfigurationRow"], *,
                          replace_conditions: bool | None = None,
                          original_mappings: list["MappingRow"] | None = None) -> list[dict[str, str]]:
    if replace_conditions is None:
        replace_conditions = "conditionalStatements" in job.fileSettings.model_fields_set
    layouts = {kind: [row for row in mappings if row.recordType == kind] for kind in ("H", "D", "T")}
    details = [row for row in saved if row.recttype == "D" and row.query.strip()]
    distinct_details = {(row.query, row.conditions) for row in details}
    if len(distinct_details) > 1:
        raise InvalidRun("Multiple distinct detail queries cannot be merged without confirmed dataset and alias rules.")
    records = []
    if job.mapping.includeHeader:
        if not layouts["D"]:
            raise InvalidRun("Include Header Row requires at least one Detail mapping.")
        header = "SELECT TOP 1 valid_flag, retnum, paydate AS sort1, " + ", ".join(sql_literal(row.field) for row in layouts["D"])
    elif layouts["H"]:
        header = "SELECT TOP 1 valid_flag, retnum, paydate AS sort1, " + ", ".join(_expression(row)[0] for row in layouts["H"])
    else:
        header = None
    if header is not None:
        records.append({"recttype": "H", "query": header})
    if details:
        query = details[0].query
        if original_mappings is not None:
            def detail_expression(row):
                # Report serialization applies the configured field format.
                # Retain existing aliases; never infer one from an output label.
                source = row.mappingColumn.strip()
                if source.casefold() == "default" or not source:
                    return sql_literal(row.defaultValue)
                value = source if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source) else sql_identifier(source)
                if row.defaultValue:
                    value = f"COALESCE(NULLIF(CONVERT(varchar(max), {value}), ''), {sql_literal(row.defaultValue)})"
                return value
            query = replace_detail_projection(query, [row for row in original_mappings if row.recordType == "D"],
                                              layouts["D"], detail_expression)
        detail = {"recttype": "D", "query": query,
                  "conditions": _conditions(job) if replace_conditions else details[0].conditions}
    elif layouts["D"]:
        expressions = [_expression(row) for row in layouts["D"]]
        names = [row.mappingColumn.casefold() for row in layouts["D"]]
        if job.general.storeResultsToTable and (
            any(not named for _, named in expressions) or len(set(names)) != len(names)
            or set(names) & {"valid_flag", "retnum", "sort1"}
        ):
            raise InvalidRun("Store Results to Table requires confirmed aliases for calculated, constant, or duplicate Detail columns.")
        detail = {"recttype": "D", "query": "SELECT valid_flag, retnum, paydate AS sort1, " + ", ".join(expr for expr, _ in expressions),
                  "conditions": _conditions(job)}
    else:
        raise InvalidRun("Add a Detail mapping or retain the existing Detail query.")
    records.append(detail)
    trailer = (
        "SELECT DISTINCT valid_flag, retnum, paydate AS sort1, " + ", ".join(_expression(row)[0] for row in layouts["T"])
        if layouts["T"] else "SELECT DISTINCT valid_flag, retnum, '01/01/1900' AS sort1"
    )
    records.append({"recttype": "T", "query": trailer})
    return records

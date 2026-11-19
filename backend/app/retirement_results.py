from collections.abc import Iterable
import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from hashlib import sha256
from io import StringIO
from itertools import product
import json
import operator
import re
from typing import TYPE_CHECKING
from unicodedata import normalize
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

if TYPE_CHECKING:
    from app.routers.retirement_builder import MappingRow, RetirementBuilderJob


MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 100
UNBOUNDED_RUN_DATE = date(1900, 1, 1)
RECORD_TYPES = {"h": "H", "header": "H", "d": "D", "detail": "D", "t": "T", "trailer": "T"}
DATE_FORMATS = {
    "MMDDYYYY": "MMDDYYYY",
    "MMDDYYYY - Date": "MMDDYYYY",
    "MM/DD/YYYY": "MM/DD/YYYY",
    "MM-DD-YYYY": "MM-DD-YYYY",
    "CCYYMMDD": "YYYYMMDD",
    "YYYY-MM-DD": "YYYY-MM-DD",
    "YYYYMMDD": "YYYYMMDD",
    "DD/MM/YYYY": "DD/MM/YYYY",
    "DD-MM-YYYY": "DD-MM-YYYY",
}
NUMBER_FORMATS = {
    "0 - Integer": (0, ""),
    "0.00 - Decimal": (2, ""),
    "0.0000 - Decimal": (4, ""),
    "#,##0": (0, ","),
    "#,##0.00": (2, ","),
}
PHONE_FORMATS = ("Digits Only", "(XXX) XXX-XXXX", "XXX-XXX-XXXX", "International (+)")
TEXT_FORMATS = {
    "Trim Whitespace": str.strip,
    "Uppercase": str.upper,
    "Lowercase": str.lower,
}
SSN_FORMATS = {"XXXXXXXXX", "XXX-XX-XXXX", "XXXXXXXXX - SSN", "XXX-XX-XXXX - SSN"}
NUMERIC_MASK_PATTERN = re.compile(r"(\$)?#+(?:\.(#+))?")
_LEGACY_DELIMITERS = {
    "Comma": ",",
    "Pipe": "|",
    "Tab": "\t",
    "Semicolon": ";",
}
_LEGACY_FILE_FORMAT_NAMES = {
    "CSV": "Comma",
    "CSV (COMMA DELIMITED)": "Comma",
    "CSV_PIPE": "Pipe",
    "CSV (PIPE DELIMITED)": "Pipe",
    "CSV_TAB": "Tab",
    "CSV (TAB DELIMITED)": "Tab",
    "CSV_SEMI": "Semicolon",
    "CSV (SEMICOLON DELIMITED)": "Semicolon",
}
COMPARISONS = {
    "=": operator.eq, "==": operator.eq, "!=": operator.ne, "<>": operator.ne,
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
}
ISO_DATE_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
INSERT_RESULT = text("""
    INSERT INTO dbo.rjob_result (run_id, job_id, row_number, record_type, row_values)
    VALUES (:run_id, :job_id, :row_number, :record_type, :row_values)
""")


class InvalidRun(ValueError):
    pass


def record_type_code(value: str) -> str:
    code = RECORD_TYPES.get(value.strip().casefold())
    if code is None:
        raise InvalidRun("Choose H, D, or T as the record type.")
    return code


@dataclass(frozen=True)
class ReportDateRange:
    start: date = UNBOUNDED_RUN_DATE
    end: date = UNBOUNDED_RUN_DATE

    @property
    def bounded(self) -> bool:
        return self.start != UNBOUNDED_RUN_DATE or self.end != UNBOUNDED_RUN_DATE

    def includes(self, value: date) -> bool:
        return (self.start == UNBOUNDED_RUN_DATE or self.start <= value) and (
            self.end == UNBOUNDED_RUN_DATE or value <= self.end
        )


_SAVED_SORT_RULE = re.compile(r"\[((?:[^\]]|\]\])*)\] (ASC|DESC)")


def format_sort_order(rules: Iterable[tuple[str, str]]) -> str:
    parts = [f"[{column.replace(']', ']]')}] {direction}" for column, direction in rules]
    return "ORDER BY " + ", ".join(parts) if parts else ""


def format_sort_columns(columns: Iterable[str]) -> str:
    parts = []
    for name in columns:
        output = StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerow([name])
        parts.append(output.getvalue().removesuffix("\n"))
    return ", ".join(parts)


def parse_sort_order(clause: str) -> list[dict[str, str]]:
    if not clause:
        return []
    if clause.startswith("ORDER BY "):
        rules = [(column.replace("]]", "]"), direction) for column, direction in _SAVED_SORT_RULE.findall(clause)]
        if format_sort_order(rules) != clause:
            raise InvalidRun("The saved sort order is invalid. Save the job again before running it.")
    else:
        # Legacy lists may start with a comma because they were appended to a base sort.
        value = clause.strip().removeprefix(",").lstrip()
        try:
            rows = list(csv.reader(StringIO(value), skipinitialspace=True, strict=True))
        except csv.Error as exc:
            raise InvalidRun("The saved sort order is invalid. Save the job again before running it.") from exc
        if len(rows) != 1 or not rows[0] or any(not name.strip() for name in rows[0]):
            raise InvalidRun("The saved sort order is invalid. Save the job again before running it.")
        rules = [(column.strip(), "ASC") for column in rows[0]]
    return [
        {"orderBy": str(index), "mappingColumn": column, "direction": direction}
        for index, (column, direction) in enumerate(rules, start=1)
    ]


@dataclass(frozen=True)
class ResultRow:
    record_type: str
    values: dict[str, str]


@dataclass(frozen=True)
class ReportFile:
    file_name: str
    rows: list[ResultRow]
    csv: str
    client_ids: frozenset[str] | None
    payroll_company_ids: frozenset[str] | None = None
    delimiter: str = ","
    # FIXED output has no delimiter; retain its fields for Excel conversion.
    excel_rows: list[list[str]] | None = None


GROUP_COLUMNS = {"client id": ("clientid",), "payday": ("paydate", "payday")}
FILE_NAME_FORMAT_PARTS = ("file name", *GROUP_COLUMNS)
FILE_NAME_FORMAT_CODES = frozenset({
    "FILENAME", "CLIENT", "PAYDAY", "FILENAME_CLIENT", "FILENAME_PAYDAY", "CLIENT_PAYDAY", "FILENAME_CLIENT_PAYDAY",
})
_FILE_NAME_CODE_PARTS = {"FILENAME": "file name", "CLIENT": "client id", "PAYDAY": "payday"}
_FILE_NAME_PART_CODES = {part: code for code, part in _FILE_NAME_CODE_PARTS.items()}
SourceRows = dict[str, list[dict[str, str]]]


def parse_file_name_format(value: str) -> tuple[str, ...] | None:
    if "+" in value or value.strip().casefold() in ("file name", "client id", "pay date"):
        parts = tuple(part.strip().casefold().replace("pay date", "payday") for part in value.split("+"))
    else:
        parts = tuple(_FILE_NAME_CODE_PARTS.get(code.strip().upper(), "") for code in value.split("_"))
    if len(parts) == len(set(parts)) and all(part in FILE_NAME_FORMAT_PARTS for part in parts):
        return parts
    return None


def _name_format(value: str) -> tuple[str, ...]:
    return parse_file_name_format(value) or ("file name",)


def file_name_format_code(value: str) -> str:
    return "_".join(_FILE_NAME_PART_CODES[part] for part in _name_format(value))


def _safe_name_part(value: str, byte_limit: int) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value).strip(". ")
    return normalize("NFC", cleaned).encode("utf-8")[:byte_limit].decode("utf-8", errors="ignore").rstrip(". ")


def _output_name(job: "RetirementBuilderJob", name_format: tuple[str, ...], group: dict[str, str]) -> str:
    base = re.sub(r"\.csv$", "", job.general.fileName.strip(". "), flags=re.IGNORECASE)
    group_parts = {part: _safe_name_part(value, 75) or "_" for part, value in group.items()}
    base_limit = 200 - sum(len(value.encode("utf-8")) + 1 for value in group_parts.values())
    group_parts["file name"] = _safe_name_part(base, base_limit) or f"job-{job.id}"
    name = "_".join(group_parts[part] for part in name_format)
    if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", name.split(".")[0]):
        name = f"_{name}"
    return f"{name}.csv"


def _source_key(mapping: "MappingRow") -> str:
    return (mapping.mappingColumn.strip() or mapping.field.strip()).casefold()


def _find_group_source(
    dimension: str, headings: list[str], detail_layout: list["MappingRow"], source_aliases: dict[str, str],
) -> tuple[str | None, str]:
    def key(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.casefold())

    columns = {key(heading): heading for heading in headings}
    for heading in headings:
        if heading in source_aliases:
            columns.setdefault(key(source_aliases[heading]), heading)
    aliases = GROUP_COLUMNS[dimension]
    source = next((columns[alias] for alias in aliases if alias in columns), None)
    if source is None:
        source = next((_source_key(mapping) for mapping in detail_layout if key(mapping.field) in aliases), None)
    default = next((mapping.defaultValue for mapping in detail_layout if _source_key(mapping) == source and mapping.defaultValue), "")
    return source, default


def _group_source_columns(
    dimensions: tuple[str, ...], headings: list[str], detail_layout: list["MappingRow"], source_aliases: dict[str, str],
) -> list[tuple[str, str, str]]:
    sources = []
    for dimension in dimensions:
        source, default = _find_group_source(dimension, headings, detail_layout, source_aliases)
        if source is None or (source not in headings and not default):
            label = "Client ID" if dimension == "client id" else "Pay Date"
            raise InvalidRun(f'Add a "{label}" source column for the selected output file name format.')
        sources.append((dimension, source, default))
    return sources


def _report_clients(rows: SourceRows, source: str | None) -> frozenset[str] | None:
    if source is None or not rows["D"]:
        return None
    details = {row.get(source, "").strip() for row in rows["D"]}
    if "" in details:
        return None
    explicit = {row.get(source, "").strip() for kind in ("H", "T") for row in rows[kind]}
    return frozenset(details | (explicit - {""}))


def _group_rows(source_rows: SourceRows, sources: list[tuple[str, str, str]]):
    if not sources:
        yield {}, source_rows
        return

    def group_key(row: dict[str, str], detail: bool) -> tuple[str | None, ...]:
        values = []
        for dimension, source, default in sources:
            value = row.get(source, "").strip()
            if detail:
                value = value or default.strip()
                if not value:
                    label = "Client ID" if dimension == "client id" else "Pay Date"
                    raise InvalidRun(f'Every included detail row needs a "{label}" for the selected output file name format.')
            values.append(_parse_date(value, "Pay Date").isoformat() if value and dimension == "payday" else value or None)
        return tuple(values)

    details = {}
    for row in source_rows["D"]:
        details.setdefault(group_key(row, detail=True), []).append(row)
    templates = {}
    for kind in ("H", "T"):
        templates[kind] = {}
        for index, row in enumerate(source_rows[kind]):
            templates[kind].setdefault(group_key(row, detail=False), []).append((index, row))

    for group, records in sorted(details.items()):
        patterns = list(product(*((value, None) for value in group)))
        group_rows = {"H": [], "D": records, "T": []}
        for kind in ("H", "T"):
            matched = [entry for pattern in patterns for entry in templates[kind].get(pattern, [])]
            if source_rows[kind] and not matched:
                label = "header" if kind == "H" else "trailer"
                raise InvalidRun(f"An output group has no matching {label} source row.")
            group_rows[kind] = [row for _, row in sorted(matched, key=lambda entry: entry[0])]
        yield {dimension: value for (dimension, _, _), value in zip(sources, group)}, group_rows


def _decimal(value: str) -> Decimal:
    try:
        number = Decimal(value.strip())
    except InvalidOperation as exc:
        raise InvalidRun("A condition uses a value that is not a number.") from exc
    if not number.is_finite():
        raise InvalidRun("A condition uses a value that is not a finite number.")
    return number


def condition_date(value: str) -> date | None:
    if not re.fullmatch(ISO_DATE_PATTERN, value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise InvalidRun("Enter a valid date in YYYY-MM-DD format.") from exc


def _parse_date(value: str, field: str) -> date:
    for pattern, parts in (
        (r"(\d{4})-(\d{2})-(\d{2})", (1, 2, 3)),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", (3, 1, 2)),
        (r"(\d{2})(\d{2})(\d{4})", (3, 1, 2)),
    ):
        match = re.fullmatch(pattern, value.strip())
        if match:
            try:
                year, month, day = (int(match[index]) for index in parts)
                return date(year, month, day)
            except ValueError:
                break
    raise InvalidRun(f'Column "{field}" contains an invalid date.')


def _format_phone(value: str, format_name: str, field: str) -> str:
    source = value.strip()
    digits = re.sub(r"[^0-9]", "", source)
    if not re.fullmatch(r"\+?[0-9().\s-]+", source) or not digits:
        raise InvalidRun(f'Column "{field}" contains an invalid phone number.')
    if format_name == "Digits Only":
        return digits

    international = source.startswith("+") or digits.startswith("00")
    if digits.startswith("00") and not source.startswith("+"):
        digits = digits[2:]
    if format_name == "International (+)":
        if not international or not re.fullmatch(r"[1-9][0-9]{1,14}", digits):
            raise InvalidRun(f'Column "{field}" needs a phone number with an explicit + or 00 country code prefix.')
        return f"+{digits}"

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    elif international:
        raise InvalidRun(f'Column "{field}" needs a North American phone number for this format.')
    if len(digits) != 10:
        raise InvalidRun(f'Column "{field}" needs ten phone digits for this format.')
    area, exchange, line = digits[:3], digits[3:6], digits[6:]
    if format_name == "(XXX) XXX-XXXX":
        return f"({area}) {exchange}-{line}"
    return f"{area}-{exchange}-{line}"


def _format_value(value: str, mapping: "MappingRow") -> str:
    name = mapping.format.strip()
    if not value or not name:
        return value
    if name in DATE_FORMATS:
        parsed = _parse_date(value, mapping.field)
        return (DATE_FORMATS[name].replace("YYYY", f"{parsed.year:04d}")
                .replace("MM", f"{parsed.month:02d}").replace("DD", f"{parsed.day:02d}"))
    mask = NUMERIC_MASK_PATTERN.fullmatch(name)
    if name in NUMBER_FORMATS or mask:
        places, grouping = NUMBER_FORMATS[name] if mask is None else (len(mask[2] or ""), "")
        try:
            number = _decimal(value)
            if number.adjusted() >= 1_000:
                raise InvalidOperation
            with localcontext() as context:
                context.prec = max(28, number.adjusted() + places + 2)
                rounded = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        except (InvalidOperation, InvalidRun) as exc:
            raise InvalidRun(f'Column "{mapping.field}" contains a value that cannot be formatted as a number.') from exc
        formatted = format(rounded, f"{grouping}.{places}f")
        if mask and places:
            formatted = formatted.rstrip("0").rstrip(".")
        if mask and mask[1]:
            return f"-${formatted[1:]}" if formatted.startswith("-") else f"${formatted}"
        return formatted
    if name in PHONE_FORMATS:
        return _format_phone(value, name, mapping.field)
    if name in SSN_FORMATS:
        digits = value.strip().replace("-", "")
        if not re.fullmatch(r"[0-9]{9}", digits):
            raise InvalidRun(f'Column "{mapping.field}" requires nine SSN digits.')
        if name.startswith("XXX-"):
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return digits
    if name in TEXT_FORMATS:
        return TEXT_FORMATS[name](value)
    if name in {"LA", "LA - Left Justified", "RA", "RA - Right Justified"}:
        width = int(mapping.length or "0")
        if width > 1_000:
            raise InvalidRun(f'Column "{mapping.field}" exceeds the 1,000-character padding limit.')
        return value.rjust(width) if name.startswith("RA") else value.ljust(width)
    raise InvalidRun(f'Column "{mapping.field}" uses an unsupported format.')


def file_format_name(value: str) -> str:
    name = value.strip()
    return _LEGACY_FILE_FORMAT_NAMES.get(name.upper(), name)


def is_fixed_format(value: str) -> bool:
    return value.strip().casefold() == "fixed"


def _is_name_mapping(mapping: "MappingRow") -> bool:
    source = re.sub(r"[^a-z0-9]", "", _source_key(mapping))
    return source in {"name", "fullname", "employeename", "empformattedname", "empname", "companyname", "clientname",
                      "firstname", "lastname", "middlename", "firstlast", "lastfirst"}


def _clean_name_value(value: str, mapping: "MappingRow") -> str:
    # The retirement procedure wraps formatted names in literal quotes. Remove
    # that wrapper only for mapped name sources; preserve meaningful inner quotes.
    if _is_name_mapping(mapping):
        stripped = value.strip()
        if len(stripped) >= 2 and stripped.startswith('"') and stripped.endswith('"'):
            return stripped[1:-1]
    return value


def fixed_layout(layout: list["MappingRow"]) -> list[tuple[int, int]]:
    """Return zero-based offsets and character widths in configured column order."""
    try:
        positions = [int(row.startPosition or "0") for row in layout]
    except ValueError as exc:
        raise InvalidRun("FIXED start positions must be whole numbers.") from exc
    explicit_positions = any(position != 0 for position in positions)
    fields = []
    end = 0
    for row, position in zip(layout, positions, strict=True):
        try:
            width = int(row.length or "0")
            start = position if explicit_positions else end
        except ValueError as exc:
            raise InvalidRun(f'Column "{row.field}" needs whole-number FIXED positions and lengths.') from exc
        if not 1 <= width <= 1_000:
            raise InvalidRun(f'Column "{row.field}" needs a FIXED length from 1 to 1,000 characters.')
        if start < end:
            raise InvalidRun(f'Column "{row.field}" overlaps another FIXED field or is out of order.')
        if start + width > MAX_OUTPUT_BYTES:
            raise InvalidRun("The FIXED record exceeds the 10 MB output limit.")
        fields.append((start, width))
        end = start + width
    if not fields:
        raise InvalidRun("FIXED output requires configured fields and positive lengths.")
    return fields


def _fixed_record(values: list[str] | tuple[str, ...], layout: list["MappingRow"]) -> tuple[str, list[str]]:
    if len(values) != len(layout):
        raise InvalidRun("The FIXED mappings do not match the export columns.")
    chunks, padded = [], []
    end = 0
    for value, mapping, (start, width) in zip(values, layout, fixed_layout(layout), strict=True):
        value = value.strip(" ")  # Replace existing SQL padding with the configured alignment.
        if any(char in value for char in "\r\n\t\x00"):
            raise InvalidRun(f'Column "{mapping.field}" contains a control character that cannot be written in FIXED output.')
        if len(value) > width:
            raise InvalidRun(f'Column "{mapping.field}" exceeds its FIXED length of {width} characters.')
        field = value.rjust(width) if mapping.format.strip() in {"RA", "RA - Right Justified"} else value.ljust(width)
        chunks.extend((" " * (start - end), field))
        padded.append(field)
        end = start + width
    return "".join(chunks) + "\r\n", padded


def build_report_files(
    job: "RetirementBuilderJob", source: bytes, *, from_payroll_procedure: bool = False, delimiter: str | None = None,
    source_labels: dict[str, str] | None = None, date_range: ReportDateRange = ReportDateRange(),
) -> list[ReportFile]:
    fixed = is_fixed_format(job.general.fileFormat)
    if delimiter is None:
        delimiter = " " if fixed else _LEGACY_DELIMITERS.get(file_format_name(job.general.fileFormat))
    if delimiter is None:
        raise InvalidRun("Select a supported CSV file format for this job.")
    layouts: dict[str, list[MappingRow]] = {}
    for mapping in job.mapping.rows:
        kind = RECORD_TYPES.get(mapping.recordType.strip().casefold() or "detail")
        if kind is None or not mapping.field.strip():
            raise InvalidRun("Every mapping needs an output field and a supported record type.")
        layout = layouts.setdefault(kind, [])
        if len(layout) >= MAX_COLUMNS or any(column.field.casefold() == mapping.field.casefold() for column in layout):
            raise InvalidRun(f"Use unique output fields and at most {MAX_COLUMNS} columns per record type.")
        layout.append(mapping)
    if not layouts:
        raise InvalidRun("Add at least one dataset mapping before running this job.")
    name_format = _name_format(job.general.outputFileNameFormat)
    dimensions = tuple(part for part in name_format if part != "file name")

    try:
        reader = csv.reader(StringIO(source.decode("utf-8-sig"), newline=""), strict=True)
        headings = [heading.strip().casefold() for heading in next(reader, [])]
        if not headings or not all(headings) or len(set(headings)) != len(headings) or len(headings) > MAX_COLUMNS:
            raise InvalidRun("Use a CSV header with distinct, nonempty column names.")
        heading_set = set(headings)
        source_aliases = {key.casefold(): label.casefold() for key, label in (source_labels or {}).items()}
        for key, label in tuple(source_aliases.items()):
            source_aliases.setdefault(label, key)

        def resolve_heading(key: str) -> str:
            alias = source_aliases.get(key)
            return alias if key not in heading_set and alias in heading_set else key

        record_type_heading = resolve_heading("record type")
        typed_source = record_type_heading in heading_set
        if not typed_source and layouts.keys() != {"D"}:
            raise InvalidRun("Add a Record Type column with H, D, or T values for jobs with header or trailer mappings.")
        for kind, layout in layouts.items():
            resolved = []
            for mapping in layout:
                source_key = resolve_heading(_source_key(mapping))
                if source_key not in heading_set and not mapping.defaultValue:
                    raise InvalidRun(f'Source column "{mapping.mappingColumn.strip() or mapping.field.strip()}" is missing.')
                resolved.append(mapping.model_copy(update={"mappingColumn": source_key}))
            layouts[kind] = resolved
        group_sources = _group_source_columns(dimensions, headings, layouts.get("D", []), source_aliases)
        if from_payroll_procedure:
            # The payroll source adds this column after resolving the company IDs.
            client_source = "client id" if "client id" in headings else None
        else:
            client_source, _ = _find_group_source("client id", headings, layouts.get("D", []), source_aliases)

        range_column = None
        if date_range.bounded and not from_payroll_procedure:
            range_column, _ = _find_group_source("payday", headings, layouts.get("D", []), source_aliases)
            if range_column not in heading_set:
                range_column = next((key for key in headings if re.sub(r"[^a-z0-9]", "", key) == "checkdate"), None)
            if range_column is None:
                raise InvalidRun('Add a Pay Date or Check Date source column to run this report for a date range.')

        conditions = []
        for rule in job.fileSettings.conditionalStatements:
            key = resolve_heading(rule.mappingColumn.strip().casefold())
            compare = COMPARISONS.get(rule.condition.strip())
            if key not in headings or compare is None:
                raise InvalidRun("Check the source column and comparison operator in File Settings.")
            threshold = condition_date(rule.value)
            if threshold is None:
                conditions.append((key, compare, _decimal(rule.value)))
            else:
                conditions.append((key, compare, threshold))

        sort_rules = [
            (resolve_heading(rule.mappingColumn.strip().casefold()), rule.direction == "DESC")
            for rule in sorted(job.fileSettings.sortingOrder, key=lambda rule: int(rule.orderBy))
        ]
        if any(key not in headings for key, _ in sort_rules):
            raise InvalidRun("A sorting column in File Settings is missing from the source CSV.")

        source_rows: dict[str, list[dict[str, str]]] = {"H": [], "D": [], "T": []}
        seen_kinds: set[str] = set()
        retained_details: list[bool] = []
        for number, values in enumerate(reader, start=2):
            if number > MAX_ROWS + 1:
                raise InvalidRun(f"The source CSV can contain up to {MAX_ROWS:,} data rows.")
            if not values:
                continue
            if len(values) != len(headings):
                raise InvalidRun(f"Source row {number} does not match the CSV header.")
            row = dict(zip(headings, values))
            kind = RECORD_TYPES.get(row[record_type_heading].strip().casefold()) if typed_source else "D"
            if kind not in layouts:
                raise InvalidRun(f"Source row {number} has a record type with no matching layout.")
            seen_kinds.add(kind)
            if range_column and kind in {"D", "T"} and not date_range.includes(_parse_date(row[range_column], range_column)):
                continue
            retained = kind != "D" or all(
                compare(_parse_date(row[key], key) if isinstance(threshold, date) else _decimal(row[key]), threshold)
                for key, compare, threshold in conditions
            )
            if kind == "D":
                retained_details.append(retained)
            if retained:
                source_rows[kind].append(row)
        if from_payroll_procedure and date_range.bounded and not seen_kinds:
            return []
        if layouts.keys() - seen_kinds:
            raise InvalidRun("Include source rows for each record type configured in Mapping.")
    except (UnicodeDecodeError, csv.Error) as exc:
        raise InvalidRun("Upload a valid UTF-8, comma-delimited CSV.") from exc

    details = source_rows["D"]
    if date_range.bounded and not details and "D" in layouts:
        return []
    if from_payroll_procedure and not all(retained_details):
        if not details:
            return []
        trailers = source_rows["T"]
        if trailers:
            # The procedure returns one detail and trailer per company and month.
            # The saved query orders both sets by the same company and month keys.
            if len(trailers) != len(retained_details):
                raise InvalidRun("Payroll detail and trailer records could not be matched.")
            source_rows["T"] = [row for row, keep in zip(trailers, retained_details, strict=True) if keep]
    for key, descending in reversed(sort_rules):
        try:
            numbers = {row[key]: _decimal(row[key]) for row in details if row[key].strip()}
        except InvalidRun:
            details.sort(key=lambda row: row[key].casefold(), reverse=descending)
        else:
            if descending:
                numbers = {value: number.copy_negate() for value, number in numbers.items()}
            details.sort(key=lambda row: (row[key] not in numbers, numbers.get(row[key], Decimal(0))))

    files = []
    filenames = set()
    remaining_bytes = MAX_OUTPUT_BYTES
    for group, rows in _group_rows(source_rows, group_sources):
        filename = _output_name(job, name_format, group)
        if filename.casefold() in filenames:
            group_hash = sha256(json.dumps(group, sort_keys=True).encode("utf-8")).hexdigest()[:12]
            base = filename.removesuffix(".csv")
            filename = f"{base}_{group_hash}.csv"
            number = 2
            while filename.casefold() in filenames:
                filename = f"{base}_{group_hash}_{number}.csv"
                number += 1
        filenames.add(filename.casefold())
        results, output, excel_rows = _render_csv(rows, layouts, delimiter, job.mapping.includeHeader, remaining_bytes, fixed=fixed)
        remaining_bytes -= len(output.encode("utf-8"))
        source_ids = _report_clients(rows, client_source)
        files.append(ReportFile(
            filename, results, output,
            client_ids=None if from_payroll_procedure else source_ids,
            payroll_company_ids=source_ids if from_payroll_procedure else None,
            delimiter=delimiter,
            excel_rows=excel_rows,
        ))
    return files


def _render_csv(
    source_rows: SourceRows, layouts: dict[str, list["MappingRow"]], delimiter: str, include_header: bool, remaining_bytes: int,
    *, fixed: bool = False,
) -> tuple[list[ResultRow], str, list[list[str]] | None]:
    results = []
    excel_rows = [] if fixed else None
    csv_output = StringIO(newline="")
    writer = csv.writer(csv_output, delimiter=delimiter)
    def write(values: list[str], layout: list["MappingRow"]) -> list[str]:
        if fixed:
            record, fields = _fixed_record(values, layout)
            csv_output.write(record)
            excel_rows.append(fields)
            return fields
        writer.writerow(values)
        return values
    if include_header:
        layout = layouts.get("D") or next(iter(layouts.values()))
        write([mapping.field for mapping in layout], layout)
    for kind, records in source_rows.items():
        for row in records:
            values = {}
            for mapping in layouts[kind]:
                key = _source_key(mapping)
                value = row.get(key) or mapping.defaultValue
                value = _clean_name_value(value, mapping)
                if mapping.format.strip() in SSN_FORMATS:
                    value = value.strip()
                values[mapping.field] = _format_value(value, mapping)
            fields = write(list(values.values()), layouts[kind])
            if fixed:
                values = dict(zip(values, fields, strict=True))
            if csv_output.tell() > remaining_bytes:
                raise InvalidRun("The generated report exceeds the 10 MB limit.")
            results.append(ResultRow(kind, values))
    output = csv_output.getvalue()
    if len(output.encode("utf-8")) > remaining_bytes:
        raise InvalidRun("The generated report exceeds the 10 MB limit.")
    return results, output, excel_rows


def merge_report_files(job: "RetirementBuilderJob", reports: list[ReportFile]) -> ReportFile:
    contents = [reports[0].csv]
    excel_rows = list(reports[0].excel_rows) if reports[0].excel_rows is not None else None
    for report in reports[1:]:
        if excel_rows is not None:
            if report.excel_rows is None:
                raise InvalidRun("Cannot merge FIXED and delimited reports together.")
            skip = 1 if job.mapping.includeHeader else 0
            contents.append("".join(report.csv.splitlines(keepends=True)[skip:]))
            excel_rows.extend(report.excel_rows[skip:])
            continue
        if not job.mapping.includeHeader:
            contents.append(report.csv)
            continue
        stream = StringIO(report.csv, newline="")
        next(csv.reader(stream, delimiter=report.delimiter))
        contents.append(stream.read())
    return ReportFile(
        _output_name(job, ("file name",), {}).removesuffix(".csv") + "_merged.csv",
        [row for report in reports for row in report.rows],
        "".join(contents),
        frozenset(client for report in reports for client in report.client_ids or ()),
        frozenset(company for report in reports for company in report.payroll_company_ids or ()),
        delimiter=reports[0].delimiter,
        excel_rows=excel_rows,
    )


def store_results(connection: Connection, job_id: int, run_id: UUID, rows: list[ResultRow]) -> int:
    if rows:
        connection.execute(INSERT_RESULT, [
            {
                "run_id": str(run_id),
                "job_id": job_id,
                "row_number": number,
                "record_type": record_type_code(row.record_type),
                "row_values": json.dumps(row.values, ensure_ascii=False),
            }
            for number, row in enumerate(rows, start=1)
        ])
    return len(rows)

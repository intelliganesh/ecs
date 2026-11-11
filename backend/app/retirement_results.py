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
RECORD_TYPES = {"h": "H", "header": "H", "d": "D", "detail": "D", "t": "T", "trailer": "T"}
DATE_FORMATS = {
    "MMDDYYYY - Date": "MMDDYYYY",
    "MM/DD/YYYY": "MM/DD/YYYY",
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
MAPPING_FORMATS_BY_TYPE = {
    "text": ["LA - Left Justified", *TEXT_FORMATS],
    "date": list(DATE_FORMATS),
    "number": list(NUMBER_FORMATS),
    "phone": list(PHONE_FORMATS),
    "email": ["Trim Whitespace", "Lowercase"],
    "ssn": ["XXXXXXXXX - SSN", "XXX-XX-XXXX - SSN"],
}
DELIMITERS = {
    "CSV": ",",
    "CSV (Comma Delimited)": ",",
    "CSV_PIPE": "|",
    "CSV (Pipe Delimited)": "|",
    "CSV_TAB": "\t",
    "CSV (Tab Delimited)": "\t",
    "CSV_SEMI": ";",
    "CSV (Semicolon Delimited)": ";",
}
COMPARISONS = {
    "=": operator.eq, "==": operator.eq, "!=": operator.ne, "<>": operator.ne,
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
}
INSERT_RESULT = text("""
    INSERT INTO dbo.rjob_result (run_id, job_id, row_number, record_type, row_values)
    VALUES (:run_id, :job_id, :row_number, :record_type, :row_values)
""")


class InvalidRun(ValueError):
    pass


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


GROUP_COLUMNS = {"client id": ("clientid",), "payday": ("paydate", "payday")}
SourceRows = dict[str, list[dict[str, str]]]


def _name_format(value: str) -> tuple[str, ...]:
    parts = tuple(part.strip().casefold().replace("pay date", "payday") for part in value.split("+"))
    valid = {"file name", *GROUP_COLUMNS}
    return parts if set(parts) <= valid and len(parts) == len(set(parts)) else ("file name",)


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


def _find_group_source(dimension: str, headings: list[str], detail_layout: list["MappingRow"]) -> tuple[str | None, str]:
    def key(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.casefold())

    columns = {key(heading): heading for heading in headings}
    aliases = GROUP_COLUMNS[dimension]
    source = next((columns[alias] for alias in aliases if alias in columns), None)
    if source is None:
        source = next((_source_key(mapping) for mapping in detail_layout if key(mapping.field) in aliases), None)
    default = next((mapping.defaultValue for mapping in detail_layout if _source_key(mapping) == source and mapping.defaultValue), "")
    return source, default


def _group_source_columns(
    dimensions: tuple[str, ...], headings: list[str], detail_layout: list["MappingRow"],
) -> list[tuple[str, str, str]]:
    sources = []
    for dimension in dimensions:
        source, default = _find_group_source(dimension, headings, detail_layout)
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
    if not value or not mapping.format:
        return value
    if mapping.format in DATE_FORMATS:
        parsed = _parse_date(value, mapping.field)
        return (DATE_FORMATS[mapping.format].replace("YYYY", f"{parsed.year:04d}")
                .replace("MM", f"{parsed.month:02d}").replace("DD", f"{parsed.day:02d}"))
    if mapping.format in NUMBER_FORMATS:
        places, grouping = NUMBER_FORMATS[mapping.format]
        try:
            number = _decimal(value)
            if number.adjusted() >= 1_000:
                raise InvalidOperation
            with localcontext() as context:
                context.prec = max(28, number.adjusted() + places + 2)
                rounded = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        except (InvalidOperation, InvalidRun) as exc:
            raise InvalidRun(f'Column "{mapping.field}" contains a value that cannot be formatted as a number.') from exc
        return format(rounded, f"{grouping}.{places}f")
    if mapping.format in PHONE_FORMATS:
        return _format_phone(value, mapping.format, mapping.field)
    if mapping.format in MAPPING_FORMATS_BY_TYPE["ssn"]:
        digits = value.strip().replace("-", "")
        if not re.fullmatch(r"[0-9]{9}", digits):
            raise InvalidRun(f'Column "{mapping.field}" requires nine SSN digits.')
        if mapping.format == "XXX-XX-XXXX - SSN":
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return digits
    if mapping.format in TEXT_FORMATS:
        return TEXT_FORMATS[mapping.format](value)
    if mapping.format == "LA - Left Justified":
        width = int(mapping.length or "0")
        if width > 1_000:
            raise InvalidRun(f'Column "{mapping.field}" exceeds the 1,000-character padding limit.')
        return value.ljust(width)
    raise InvalidRun(f'Column "{mapping.field}" uses an unsupported format.')


def build_report_files(job: "RetirementBuilderJob", source: bytes) -> list[ReportFile]:
    delimiter = DELIMITERS.get(job.general.fileFormat)
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
        typed_source = "record type" in headings
        if not typed_source and layouts.keys() != {"D"}:
            raise InvalidRun("Add a Record Type column with H, D, or T values for jobs with header or trailer mappings.")
        for layout in layouts.values():
            for mapping in layout:
                source_column = mapping.mappingColumn.strip() or mapping.field.strip()
                if _source_key(mapping) not in headings and not mapping.defaultValue:
                    raise InvalidRun(f'Source column "{source_column}" is missing.')
        group_sources = _group_source_columns(dimensions, headings, layouts.get("D", []))
        client_source, _ = _find_group_source("client id", headings, layouts.get("D", []))

        conditions = []
        for rule in job.fileSettings.conditionalStatements:
            key = rule.mappingColumn.strip().casefold()
            compare = COMPARISONS.get(rule.condition.strip())
            if key not in headings or compare is None:
                raise InvalidRun("Check the source column and comparison operator in File Settings.")
            conditions.append((key, compare, _decimal(rule.value)))

        sort_rules = [
            (rule.mappingColumn.strip().casefold(), rule.direction == "DESC")
            for rule in sorted(job.fileSettings.sortingOrder, key=lambda rule: int(rule.orderBy))
        ]
        if any(key not in headings for key, _ in sort_rules):
            raise InvalidRun("A sorting column in File Settings is missing from the source CSV.")

        source_rows: dict[str, list[dict[str, str]]] = {"H": [], "D": [], "T": []}
        seen_kinds: set[str] = set()
        for number, values in enumerate(reader, start=2):
            if number > MAX_ROWS + 1:
                raise InvalidRun(f"The source CSV can contain up to {MAX_ROWS:,} data rows.")
            if not values:
                continue
            if len(values) != len(headings):
                raise InvalidRun(f"Source row {number} does not match the CSV header.")
            row = dict(zip(headings, values))
            kind = RECORD_TYPES.get(row["record type"].strip().casefold()) if typed_source else "D"
            if kind not in layouts:
                raise InvalidRun(f"Source row {number} has a record type with no matching layout.")
            seen_kinds.add(kind)
            if kind != "D" or all(compare(_decimal(row[key]), threshold) for key, compare, threshold in conditions):
                source_rows[kind].append(row)
        if layouts.keys() - seen_kinds:
            raise InvalidRun("Include source rows for each record type configured in Mapping.")
    except (UnicodeDecodeError, csv.Error) as exc:
        raise InvalidRun("Upload a valid UTF-8, comma-delimited CSV.") from exc

    details = source_rows["D"]
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
        results, output = _render_csv(rows, layouts, delimiter, job.mapping.includeHeader, remaining_bytes)
        remaining_bytes -= len(output.encode("utf-8"))
        files.append(ReportFile(filename, results, output, _report_clients(rows, client_source)))
    return files


def _render_csv(
    source_rows: SourceRows, layouts: dict[str, list["MappingRow"]], delimiter: str, include_header: bool, remaining_bytes: int,
) -> tuple[list[ResultRow], str]:
    results = []
    csv_output = StringIO(newline="")
    writer = csv.writer(csv_output, delimiter=delimiter)
    if include_header:
        writer.writerow([mapping.field for mapping in (layouts.get("D") or next(iter(layouts.values())))])
    for kind, records in source_rows.items():
        for row in records:
            values = {}
            for mapping in layouts[kind]:
                key = _source_key(mapping)
                value = row.get(key) or mapping.defaultValue
                values[mapping.field] = _format_value(value, mapping)
            writer.writerow(values.values())
            if csv_output.tell() > remaining_bytes:
                raise InvalidRun("The generated report exceeds the 10 MB limit.")
            results.append(ResultRow(kind, values))
    output = csv_output.getvalue()
    if len(output.encode("utf-8")) > remaining_bytes:
        raise InvalidRun("The generated report exceeds the 10 MB limit.")
    return results, output


def store_results(connection: Connection, job_id: int, run_id: UUID, rows: list[ResultRow]) -> int:
    if rows:
        connection.execute(INSERT_RESULT, [
            {
                "run_id": str(run_id),
                "job_id": job_id,
                "row_number": number,
                "record_type": row.record_type,
                "row_values": json.dumps(row.values, ensure_ascii=False),
            }
            for number, row in enumerate(rows, start=1)
        ])
    return len(rows)

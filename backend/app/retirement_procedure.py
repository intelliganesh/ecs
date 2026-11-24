"""Read-only conversion of rjobbuilder's already-mapped result sets to files.

The procedure returns H, then one or more D result sets, then T. Its leading
valid_flag/retnum/sort1 columns control inclusion and file grouping; they are not
export fields. Presentation is applied after retrieval without rewriting
saved SQL, aliases, filters, sorting, or grouping metadata.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.retirement_headers import aligned_detail_layout
from app.retirement_results import (
    DATE_FORMATS, NUMBER_FORMATS, NUMERIC_MASK_PATTERN, PHONE_FORMATS, SSN_FORMATS, TEXT_FORMATS,
    MAX_COLUMNS, MAX_OUTPUT_BYTES, InvalidRun, ReportFile, ResultRow,
    _clean_name_value, _fixed_record, _format_value, _is_name_mapping, _name_format,
    _output_name, _parse_date, is_fixed_format, record_type_code,
)
from app.retirement_query_builder import ordered_mappings
from app.retirement_datasets import ordered_dataset_source

if TYPE_CHECKING:
    from app.routers.retirement_builder import MappingRow, RetirementBuilderJob


@dataclass(frozen=True)
class ProcedureResultSet:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class ProcedureSource:
    result_sets: tuple[ProcedureResultSet, ...]


def uses_retirement_queries(job: "RetirementBuilderJob") -> bool:
    return any(
        row.recttype.strip().upper() in {"H", "D", "T"}
        and row.query.strip()
        and not row.query.startswith("/* company payroll */")
        for row in job.queryConfiguration
    )


_PADDING_FORMATS = {"LA", "LA - Left Justified", "RA", "RA - Right Justified"}


def _is_value_format(name: str) -> bool:
    """Presentation formats applied to returned values: number masks, phone, text case and padding."""
    return (
        name in NUMBER_FORMATS or bool(NUMERIC_MASK_PATTERN.fullmatch(name)) or name in PHONE_FORMATS
        or name in TEXT_FORMATS or name in _PADDING_FORMATS
    )


def _is_presentational(row: "MappingRow") -> bool:
    return _is_name_mapping(row) or bool(row.defaultValue) or _is_value_format(row.format.strip())


def _payday(value: str) -> str:
    return _parse_date(value, "sort1").isoformat() if value.strip() else ""


def _export_layouts(job: "RetirementBuilderJob", kinds: list[str], source: ProcedureSource, *,
                    detail_headers: bool = False) -> list[list["MappingRow"]]:
    """Align configured columns by dataset/sequence, without assuming SQL aliases."""
    layouts: list[list[MappingRow]] = [[] for _ in kinds]
    fixed = is_fixed_format(job.general.fileFormat)
    if not fixed and not any(row.format.strip() in DATE_FORMATS or row.format.strip() in SSN_FORMATS
                             or _is_presentational(row) for row in job.mapping.rows):
        return layouts
    mappings = ordered_mappings(
        row.model_copy(update={"recordType": record_type_code(row.recordType or "D")})
        for row in job.mapping.rows
    )
    for kind in ("H", "D", "T"):
        # An automatic header contains literal column labels, not dates.
        auto_header = kind == "H" and job.mapping.includeHeader
        if auto_header and (detail_headers or not fixed):
            continue
        columns = [row for row in mappings if row.recordType == ("D" if auto_header else kind)]
        strict = fixed or any(row.format.strip() in DATE_FORMATS or row.format.strip() in SSN_FORMATS for row in columns)
        if not strict and not any(_is_presentational(row) for row in columns):
            continue
        positions = [index for index, value in enumerate(kinds) if value == kind]
        datasets: dict[int, list[MappingRow]] = {}
        for row in columns:
            datasets.setdefault(row.dataSetNo, []).append(row)
        groups = [columns] if len(positions) == 1 else list(datasets.values())
        if len(groups) != len(positions):
            if strict:
                raise InvalidRun("The export mappings do not match the procedure's record datasets.")
            continue
        for index, layout in zip(positions, groups, strict=True):
            count = len(source.result_sets[index].columns) - 3
            if count == 0:  # The metadata-only T placeholder is never an export row.
                continue
            if len(layout) != count:
                if strict:
                    raise InvalidRun("The export mappings do not match the procedure's export columns.")
                continue
            layouts[index] = layout
    return layouts


def _apply_value_format(value: str, mapping: "MappingRow") -> str:
    try:
        return _format_value(value, mapping)
    except InvalidRun:
        # The saved SQL may already have applied this presentation (for example a number mask),
        # which cannot be parsed a second time. Keep the returned value instead of failing the run.
        return value


def _format_values(values: tuple[str, ...], layout: list["MappingRow"]) -> tuple[str, ...]:
    if not layout:
        return values
    formatted = list(values)
    for index, mapping in enumerate(layout):
        name = mapping.format.strip()
        value = _clean_name_value(values[index], mapping)
        if not value.strip() and mapping.defaultValue:
            value = mapping.defaultValue
        if name in SSN_FORMATS:
            formatted[index] = _format_value(value.strip(), mapping)
            continue
        pattern = DATE_FORMATS.get(name)
        if pattern is None:
            formatted[index] = _apply_value_format(value, mapping) if value and _is_value_format(name) else value
            continue
        if not value:
            formatted[index] = value
            continue
        # Existing SQL can already return the selected display format. Parse it
        # as that format first so DD/MM/YYYY is not swapped a second time.
        python_pattern = pattern.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
        try:
            value = datetime.strptime(value.strip(), python_pattern).date().isoformat()
        except ValueError:
            pass  # Native SQL dates arrive as ISO strings and use the shared formatter.
        formatted[index] = _format_value(value, mapping)
    return tuple(formatted)


def build_procedure_report_files(
    job: "RetirementBuilderJob", source: ProcedureSource, delimiter: str,
) -> list[ReportFile]:
    if len(delimiter) != 1 or delimiter in '\x00\r\n"':
        raise InvalidRun("Select a configured file format for this job.")

    # The procedure's no-data branch returns placeholder rows, including a
    # valid_flag1 column in the Detail set. These must never become report data.
    flagged = [
        row[index].strip() for result in source.result_sets
        for index, name in enumerate(result.columns)
        if name.casefold() in {"valid_flag", "valid_flag1"}
        for row in result.rows
    ]
    if flagged and all(flag in {"0", "0.0", "False", ""} for flag in flagged):
        return []

    job, source, dataset_sections = ordered_dataset_source(job, source)

    queries = [row.recttype.strip().upper() for row in job.queryConfiguration if row.query.strip()]
    kinds = (["H"] if "H" in queries else []) + ["D"] * queries.count("D") + (["T"] if "T" in queries else [])
    if not kinds or "D" not in kinds or len(kinds) != len(source.result_sets):
        raise InvalidRun("The procedure result sets do not match the saved H, D and T queries.")

    detail_headers = job.mapping.includeHeader and get_settings().retirement_header_source == "DETAIL_ALIGNED"
    if dataset_sections and job.mapping.includeHeader and not detail_headers:
        raise InvalidRun("Multiple dataset headers require RETIREMENT_HEADER_SOURCE=DETAIL_ALIGNED.")
    if detail_headers and not any(
        row[0].strip() in {"1", "1.0", "True"} and len(row) > 3
        for kind, result in zip(kinds, source.result_sets, strict=True) if kind == "D" for row in result.rows
    ):
        return []

    # Keep values positional: SQL permits unnamed and duplicate output columns.
    records: dict[str, list[tuple[str, str, list[MappingRow], tuple[str, ...]]]] = {"H": [], "D": [], "T": []}
    layouts = _export_layouts(job, kinds, source, detail_headers=detail_headers)
    if detail_headers or dataset_sections:
        mappings = ordered_mappings(row.model_copy(update={"recordType": record_type_code(row.recordType or "D")})
                                    for row in job.mapping.rows)
        detail_mappings = [row for row in mappings if row.recordType == "D"]
        datasets = {}
        for row in detail_mappings:
            datasets.setdefault(row.dataSetNo, []).append(row)
        positions = [index for index, kind in enumerate(kinds) if kind == "D"]
        groups = [detail_mappings] if len(positions) == 1 else list(datasets.values())
        detail_queries = [row.query for row in job.queryConfiguration if row.recttype.strip().upper() == "D" and row.query.strip()]
        if len(groups) != len(positions):
            raise InvalidRun("The Detail datasets do not match the mappings needed for automatic headers.")
        for index, group, query in zip(positions, groups, detail_queries, strict=True):
            layouts[index] = aligned_detail_layout(source.result_sets[index].columns, group, query)
    fixed = is_fixed_format(job.general.fileFormat)
    for kind, result, layout in zip(kinds, source.result_sets, layouts, strict=True):
        names = tuple(name.casefold() for name in result.columns[:3])
        if len(names) != 3 or names[0] not in {"valid_flag", "valid_flag1"} or names[1:] != ("retnum", "sort1"):
            raise InvalidRun("The procedure must return valid_flag, retnum and sort1 before the export columns.")
        if len(result.columns) - 3 > MAX_COLUMNS:
            raise InvalidRun(f"Use at most {MAX_COLUMNS} export columns per procedure result set.")
        if detail_headers and kind == "H":
            continue  # Drain/validate the SP's H set, but derive the file header from D.
        for row in result.rows:
            if row[0].strip() not in {"1", "1.0", "True"}:
                continue
            if len(row) > 3:
                values = row[3:] if kind == "H" and job.mapping.includeHeader else _format_values(row[3:], layout)
                records[kind].append((row[1].strip(), row[2].strip(), layout, values))

    if not records["D"]:
        return []

    name_format = _name_format(job.general.outputFileNameFormat)
    dimensions = tuple(part for part in name_format if part != "file name")
    groups: dict[tuple[str, ...], list] = {}
    for record in records["D"]:
        client, payday, _, _ = record
        values = {"client id": client}
        if "payday" in dimensions:
            values["payday"] = _payday(payday)
        if any(not values[dimension] for dimension in dimensions):
            raise InvalidRun("Every Detail row needs the client and date selected for file grouping.")
        groups.setdefault(tuple(values[dimension] for dimension in dimensions), []).append(record)

    reports = []
    filenames = set()
    remaining = MAX_OUTPUT_BYTES
    for key, details in groups.items():
        group = dict(zip(dimensions, key, strict=True))
        clients = frozenset(record[0] for record in details if record[0])

        # A client's file may span several pay dates; only keep header/trailer rows for
        # pay dates that still have Detail rows (a condition can remove a whole date).
        detail_dates = {_payday(record[1]) for record in details if record[1]}

        def belongs(record) -> bool:
            client, payday, _, _ = record
            if client and client not in clients:
                return False
            if not payday:
                return True
            date = _payday(payday)
            if "payday" in group:
                return date in {"1900-01-01", group["payday"]}
            return date == "1900-01-01" or date in detail_dates

        selected = {
            "H": records["H"] if job.mapping.includeHeader else [row for row in records["H"] if belongs(row)],
            "D": details,
            "T": [row for row in records["T"] if belongs(row)],
        }
        if detail_headers:
            layout = details[0][2]
            header = tuple(row.field for row in layout)
            signature = lambda rows: [(row.field, row.startPosition, row.length,
                                       row.format.startswith("RA")) for row in rows]
            if not dataset_sections and any(tuple(row.field for row in record[2]) != header or
                   (fixed and signature(record[2]) != signature(layout)) for record in details):
                raise InvalidRun("Detail datasets in one file need the same confirmed automatic header and field layout.")
            selected["H"] = [] if dataset_sections else [("", "", layout, header)]
        output = StringIO(newline="")
        writer = csv.writer(output, delimiter=delimiter)
        rows = []
        excel_rows = [] if fixed else None
        def write_entry(kind, layout, values):
            if fixed:
                record, fields = _fixed_record(values, layout)
                output.write(record)
                excel_rows.append(fields)
                values = tuple(fields)
            else:
                writer.writerow(values)
            if output.tell() > remaining:
                raise InvalidRun("The generated report exceeds the 10 MB limit.")
            rows.append(ResultRow(kind, {str(index): value for index, value in enumerate(values, 1)}))

        previous_dataset = None
        for kind, entries in selected.items():
            for _, _, layout, values in entries:
                if kind == "D" and dataset_sections:
                    dataset = layout[0].dataSetNo
                    if previous_dataset is not None and dataset != previous_dataset:
                        output.write("\r\n")
                        if fixed:
                            excel_rows.append([])
                    if dataset != previous_dataset and detail_headers:
                        write_entry("H", layout, tuple(row.field for row in layout))
                    previous_dataset = dataset
                write_entry(kind, layout, values)
        csv_text = output.getvalue()
        remaining -= len(csv_text.encode("utf-8"))
        if remaining < 0:
            raise InvalidRun("The generated report exceeds the 10 MB limit.")
        filename = _output_name(job, name_format, group)
        if filename.casefold() in filenames:
            # Distinct client IDs can sanitize to the same filename. Never
            # overwrite another group's file.
            base, extension = filename.rsplit(".", 1)
            suffix = 2
            while filename.casefold() in filenames:
                filename = f"{base}_{suffix}.{extension}"
                suffix += 1
        filenames.add(filename.casefold())
        reports.append(ReportFile(filename, rows, csv_text, clients or None, delimiter=delimiter, excel_rows=excel_rows))
    return reports

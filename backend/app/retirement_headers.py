"""Confirm automatic header labels against the actual Detail projection order.

No aliases are generated. Unsupported/ambiguous SQL needs explicit mapping
evidence rather than a positional guess based on a separate H result set.
"""

import re
from typing import TYPE_CHECKING

from app.retirement_projection import _top_level_tokens
from app.retirement_query_builder import _expression
from app.retirement_results import InvalidRun

if TYPE_CHECKING:
    from app.routers.retirement_builder import MappingRow


_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|\[(?:[^\]]|\]\])+\]|"(?:[^"]|"")+"')
_SELECT = re.compile(r"\s*SELECT\s+(?:DISTINCT\s+)?(?:TOP\s+(?:\d+|\(\s*\d+\s*\))\s+)?", re.IGNORECASE)


def _identifier(value: str) -> str | None:
    value = value.strip()
    if not _IDENTIFIER.fullmatch(value):
        return None
    if value.startswith("["):
        value = value[1:-1].replace("]]", "]")
    elif value.startswith('"'):
        value = value[1:-1].replace('""', '"')
    return value.casefold()


def _canonical(expression: str) -> str:
    # Ignore SQL token case/spacing, preserving literal contents and identifier
    # boundaries. Never remove spaces or apostrophes inside a string value.
    parts = re.findall(r"'(?:[^']|'')*'|\[(?:[^\]]|\]\])*\]|\"(?:[^\"]|\"\")*\"|\s+|[^\s'\[\"]+", expression)
    return "".join(part if part.startswith("'") else part.casefold() for part in parts if not part.isspace())


def _projections(query: str, count: int) -> list[tuple[str, str | None]] | None:
    prefix = _SELECT.match(query)
    if prefix is None:
        return None
    try:
        tokens = list(_top_level_tokens(query))
        end = next((start for word, start, _ in tokens if word == "FROM"), len(query))
        commas = [start for word, start, _ in tokens if word == "," and prefix.end() <= start < end]
        starts, ends = [prefix.end(), *[pos + 1 for pos in commas]], [*commas, end]
        if len(starts) != count:
            return None
        projections = []
        for start, finish in zip(starts, ends, strict=True):
            part = query[start:finish].strip().removesuffix(";").rstrip()
            aliases = [start for word, start, _ in _top_level_tokens(part) if word == "AS"]
            alias = _identifier(part[aliases[-1] + 2:]) if aliases else None
            if alias is not None:
                part = part[:aliases[-1]].rstrip()
            projections.append((part, alias))
        return projections[3:]
    except InvalidRun:
        # Metadata can still conclusively identify columns in a complex legacy
        # query. Otherwise the caller rejects it; it never guesses aliases.
        return None


def aligned_detail_layout(columns: tuple[str, ...], mappings: list["MappingRow"], query: str) -> list["MappingRow"]:
    if len(columns) - 3 != len(mappings) or not mappings:
        raise InvalidRun("The Detail output columns do not match the mappings needed for an automatic header.")
    projections = _projections(query, len(columns))
    expressions = []
    for row in mappings:
        known = set()
        for mapping in (row, row.model_copy(update={"format": ""})):
            try:
                known.add(_canonical(_expression(mapping)[0]))
            except InvalidRun:
                pass
        expressions.append(known)
    result, used = [], set()
    for position, name in enumerate(columns[3:]):
        evidence = []
        if name.strip():
            matches = {index for index, row in enumerate(mappings)
                       if name.strip().casefold() in {row.field.strip().casefold(),
                                                     (row.mappingColumn.strip() or row.field.strip()).casefold()}}
            if matches:
                evidence.append(matches)
        if projections is not None:
            expression, alias = projections[position]
            if alias is not None and name.strip().casefold() != alias:
                raise InvalidRun("The Detail result columns disagree with the saved query aliases; review the automatic header mapping.")
            source = _identifier(expression)
            matches = {index for index, row in enumerate(mappings)
                       if (source is not None and source == (row.mappingColumn.strip() or row.field.strip()).casefold())
                       or _canonical(expression) in expressions[index]}
            if matches:
                evidence.append(matches)
        candidates = set.intersection(*evidence) if evidence else set()
        if len(candidates) != 1 or next(iter(candidates)) in used:
            raise InvalidRun(
                f"Cannot unambiguously match Detail column {position + 1} to an automatic header label. "
                "Review the mapping and confirmed query aliases."
            )
        index = candidates.pop()
        if not mappings[index].field.strip():
            raise InvalidRun("Every automatic header needs a nonempty Detail field name.")
        used.add(index)
        result.append(mappings[index])
    return result

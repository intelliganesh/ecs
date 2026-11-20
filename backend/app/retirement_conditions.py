"""Round-trip generated condition fragments without changing legacy SQL storage."""

import re

from app.retirement_results import condition_date


_CLAUSE = re.compile(
    r"\s*\[(?P<column>(?:[^\]]|\]\])+)\]\s*(?P<operator><=|>=|!=|<>|=|<|>)\s*"
    r"(?P<value>'(?:[^']|'')*'|[+-]?[0-9]+(?:\.[0-9]+)?)", re.DOTALL,
)


def condition_fragment(rules, *, where: bool = True) -> str:
    clauses = []
    for rule in rules:
        column = rule.mappingColumn.replace("]", "]]")
        value = rule.value
        if rule.valueType == "text" or condition_date(value) is not None:
            value = "'" + value.replace("'", "''") + "'"
        clauses.append(f"[{column}] {'=' if rule.condition == '==' else rule.condition} {value}")
    return ("WHERE " if where and clauses else "") + " AND ".join(clauses)


def parsed_conditions(fragment: str) -> list[dict[str, str]] | None:
    """Read only our bracketed comparisons; leave opaque legacy predicates alone.

    In particular, AND/apostrophes inside a quoted literal are not separators.
    This parser never executes SQL and requires full consumption of the fragment.
    """
    remaining = re.sub(r"^\s*WHERE\b", "", fragment, count=1, flags=re.IGNORECASE)
    rules = []
    while remaining.strip():
        match = _CLAUSE.match(remaining)
        if match is None:
            return None
        token = match["value"]
        quoted = token.startswith("'")
        value = token[1:-1].replace("''", "'") if quoted else token
        try:
            date_value = condition_date(value) if quoted else None
        except ValueError:
            date_value = None
        rules.append({"mappingColumn": match["column"].replace("]]", "]"),
                      "condition": match["operator"], "value": value,
                      "valueType": "date" if date_value else "text" if quoted else "number"})
        remaining = remaining[match.end():]
        if not remaining.strip():
            break
        separator = re.match(r"\s+AND\s+", remaining, re.IGNORECASE)
        if separator is None or not remaining[separator.end():].strip():
            return None
        remaining = remaining[separator.end():]
    return rules

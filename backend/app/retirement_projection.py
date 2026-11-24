"""Update changed Detail projections while retaining confirmed legacy aliases."""

import re

from app.retirement_results import InvalidRun


def _canonical(expression: str) -> str:
    # Ignore SQL token case/spacing, preserving literal contents and identifier
    # boundaries. Never remove spaces or apostrophes inside a string value.
    parts = re.findall(r"'(?:[^']|'')*'|\[(?:[^\]]|\]\])*\]|\"(?:[^\"]|\"\")*\"|\s+|[^\s'\[\"]+", expression)
    return "".join(part if part.startswith("'") else part.casefold() for part in parts if not part.isspace())


def _top_level_tokens(sql: str):
    depth, index = 0, 0
    while index < len(sql):
        char = sql[index]
        if char in "'\"[":
            closing = "]" if char == "[" else char
            index += 1
            while index < len(sql):
                if sql[index] == closing:
                    index += 1
                    if index < len(sql) and sql[index] == closing:
                        index += 1
                        continue
                    break
                index += 1
            else:
                raise InvalidRun("The saved Detail query has an unterminated quoted value.")
            continue
        if sql.startswith("--", index) or sql.startswith("/*", index):
            # Do not reinterpret comments/unknown SQL as a simple projection.
            raise InvalidRun("The saved Detail query needs review before changing its mappings.")
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise InvalidRun("The saved Detail query has unbalanced parentheses.")
        elif depth == 0:
            word = re.match(r"[A-Za-z_][A-Za-z0-9_]*", sql[index:])
            if word:
                yield (word[0].upper(), index, index + len(word[0]))
                index += len(word[0])
                continue
            if char == ",":
                yield (",", index, index + 1)
        index += 1
    if depth:
        raise InvalidRun("The saved Detail query has unbalanced parentheses.")


def _refresh_presentation(query, old_rows, new_positions, formatted_expression):
    """Refresh only confirmed generated formatting, retaining aliases and custom SQL."""
    changed = []
    for index, old in enumerate(old_rows, start=3):
        row = new_positions.get((old.dataSetNo, old.colSeqNo))
        if row is not None and (old.mappingColumn.strip().casefold(), old.defaultValue) == (
            row.mappingColumn.strip().casefold(), row.defaultValue
        ) and (old.format.strip(), old.length.strip()) != (row.format.strip(), row.length.strip()):
            changed.append((index, old, row))
    if not changed:
        return query
    try:
        tokens = list(_top_level_tokens(query))
        prefix = re.match(r"\s*SELECT\s+(?:DISTINCT\s+)?(?:TOP\s+(?:\d+|\(\s*\d+\s*\))\s+)?", query, re.IGNORECASE)
        if prefix is None or any(word in {"FROM", "UNION", "INTO"} for word, _, _ in tokens):
            return query  # Preserve opaque/custom SQL, including its business calculations.
        commas = [start for word, start, _ in tokens if word == ","]
        starts, ends = [prefix.end(), *[pos + 1 for pos in commas]], [*commas, len(query)]
        if len(starts) != 3 + len(old_rows):
            return query
    except InvalidRun:
        return query
    replacements = []
    for index, old, row in changed:
        start, end = starts[index], ends[index]
        part = query[start:end]
        aliases = [a for word, a, _ in _top_level_tokens(part) if word == "AS"]
        body_end = len(part[:aliases[-1]].rstrip()) if aliases else len(part.rstrip())
        body_start = len(part) - len(part.lstrip())
        try:
            confirmed = _canonical(part[body_start:body_end]) == _canonical(formatted_expression(old))
        except InvalidRun:
            confirmed = False
        if confirmed:
            replacements.append((start + body_start, start + body_end, formatted_expression(row)))
    for start, end, value in reversed(replacements):
        query = query[:start] + value + query[end:]
    return query


def replace_detail_projection(query: str, old_rows, new_rows, expression, *, formatted_expression=None) -> str:
    def signature(row):
        return (row.mappingColumn.strip().casefold(), row.defaultValue)

    old_positions = {(row.dataSetNo, row.colSeqNo): row for row in old_rows}
    new_positions = {(row.dataSetNo, row.colSeqNo): row for row in new_rows}
    if formatted_expression is not None:
        # Source/default identity can stay the same while an old generated SQL
        # format becomes stale. Refresh it before the source-only shortcut.
        query = _refresh_presentation(query, old_rows, new_positions, formatted_expression)
    if old_positions.keys() == new_positions.keys() and all(
        signature(old_positions[key]) == signature(row) for key, row in new_positions.items()
    ):
        return query
    # Changing the layout of an opaque legacy SELECT could silently pair the
    # wrong source/alias with an output field. Reject instead of exporting stale data.
    tokens = list(_top_level_tokens(query))
    prefix = re.match(r"\s*SELECT\s+(?:DISTINCT\s+)?(?:TOP\s+(?:\d+|\(\s*\d+\s*\))\s+)?", query, re.IGNORECASE)
    if prefix is None or any(word in {"FROM", "UNION", "INTO"} for word, _, _ in tokens):
        raise InvalidRun("The saved Detail query needs review before changing its mappings.")
    commas = [start for word, start, _ in tokens if word == ","]
    starts, ends = [prefix.end(), *[pos + 1 for pos in commas]], [*commas, len(query)]
    if len(starts) != 3 + len(old_rows):
        raise InvalidRun("The saved Detail query columns do not match its mappings; review it before saving changes.")
    if old_positions.keys() != new_positions.keys():
        previous = {(row.dataSetNo, row.colSeqNo): (row, query[start:end].strip())
                    for row, start, end in zip(old_rows, starts[3:], ends[3:], strict=True)}
        fields = []
        for row in new_rows:
            old = previous.get((row.dataSetNo, row.colSeqNo))
            if old is None:
                fields.append(expression(row))
            elif signature(old[0]) == signature(row):
                fields.append(old[1])
            else:
                part = old[1]
                aliases = [start for word, start, _ in _top_level_tokens(part) if word == "AS"]
                if not aliases and not re.fullmatch(r'\s*(?:[A-Za-z_][A-Za-z0-9_]*|\[(?:[^\]]|\]\])+\]|"(?:[^"]|"")+"|\x27(?:[^\x27]|\x27\x27)*\x27)\s*', part):
                    raise InvalidRun("The changed Detail column needs a confirmed alias before saving.")
                fields.append(expression(row) + (" " + part[aliases[-1]:] if aliases else ""))
        return query[:starts[3]] + " " + ", ".join(fields)
    replacements = []
    for index, (old, row) in enumerate(zip(old_rows, new_rows, strict=True), start=3):
        if signature(old) == signature(row):
            continue
        start, end = starts[index], ends[index]
        part = query[start:end]
        aliases = [(a, b) for word, a, b in _top_level_tokens(part) if word == "AS"]
        if aliases:
            alias_start = aliases[-1][0]
            body_end = len(part[:alias_start].rstrip())
        else:
            body_end = len(part.rstrip())
            if not re.fullmatch(r'\s*(?:[A-Za-z_][A-Za-z0-9_]*|\[(?:[^\]]|\]\])+\]|"(?:[^"]|"")+"|\x27(?:[^\x27]|\x27\x27)*\x27)\s*', part):
                raise InvalidRun("The changed Detail column needs a confirmed alias before saving.")
        body_start = len(part) - len(part.lstrip())
        replacements.append((start + body_start, start + body_end, expression(row)))
    for start, end, value in reversed(replacements):
        query = query[:start] + value + query[end:]
    return query

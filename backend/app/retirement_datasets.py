"""Dataset identities in generated SELECT metadata; no database or SP changes.

Business aliases are preserved. The reserved fourth projection identifies new
datasets even when their result is empty. Legacy queries are matched only when
their returned column names and configured expressions provide unique evidence.
"""

import re

from app.retirement_results import InvalidRun, record_type_code

DATASET_COLUMN = re.compile(r"__ecs_dataset_(\d+)\Z", re.IGNORECASE)


def split_dataset_query(query: str) -> tuple[int | None, str]:
    if "__ecs_dataset_" not in query.casefold():
        return None, query
    from app.retirement_projection import _top_level_tokens
    commas = [start for word, start, _ in _top_level_tokens(query) if word == ","]
    if len(commas) < 4:
        raise InvalidRun("Invalid dataset metadata in the saved Detail query.")
    marker = query[commas[2] + 1:commas[3]].strip()
    match = re.fullmatch(r"(\d+)\s+AS\s+\[__ecs_dataset_(\d+)\]", marker, re.IGNORECASE)
    if not match or match[1] != match[2] or int(match[1]) > 2_147_483_647:
        raise InvalidRun("Invalid dataset metadata in the saved Detail query.")
    return int(match[1]), query[:commas[2] + 1] + query[commas[3] + 1:]


def tag_dataset_query(query: str, dataset: int) -> str:
    from app.retirement_projection import _top_level_tokens
    _, query = split_dataset_query(query)
    commas = [start for word, start, _ in _top_level_tokens(query) if word == ","]
    if len(commas) < 3:
        raise InvalidRun("A dataset needs at least one Detail field.")
    position = commas[2] + 1
    return query[:position] + f" {dataset} AS [__ecs_dataset_{dataset}]," + query[position:]


def query_projections(query: str):
    from app.retirement_headers import _projections
    from app.retirement_projection import _top_level_tokens
    _, query = split_dataset_query(query)
    tokens = list(_top_level_tokens(query))
    if any(word in {"FROM", "UNION", "INTO"} for word, _, _ in tokens):
        raise InvalidRun("The legacy dataset query needs explicit mapping review.")
    count = 1 + sum(word == "," for word, _, _ in tokens)
    fields = _projections(query, count)
    if not fields:
        raise InvalidRun("The legacy dataset query needs explicit mapping review.")
    return fields


def query_column_names(query: str) -> tuple[str, ...]:
    from app.retirement_headers import _identifier
    return ("valid_flag", "retnum", "sort1", *(
        alias or _identifier(expression) or "" for expression, alias in query_projections(query)
    ))


def distinct_details(job):
    unique = {}
    for row in job.queryConfiguration:
        if row.recttype.strip().upper() == "D" and row.query.strip():
            unique.setdefault((row.query, row.conditions, row.sortOrder), row)
    return list(unique.values())


def multiple_datasets(job) -> bool:
    return len(distinct_details(job)) > 1 or len({row.dataSetNo for row in job.mapping.rows
                                                if record_type_code(row.recordType or "D") == "D"}) > 1


def expand_legacy_datasets(job):
    """Build a read-only view of confirmed legacy dataset mappings, never save it."""
    from app.retirement_headers import _identifier, aligned_detail_layout
    from app.retirement_query_builder import ordered_mappings
    from app.routers.retirement_builder import MappingRow
    details = distinct_details(job)
    if len(details) < 2 and not any(split_dataset_query(row.query)[0] is not None for row in details):
        return job
    mappings = ordered_mappings([row.model_copy(update={"recordType": record_type_code(row.recordType or "D")})
                                 for row in job.mapping.rows])
    groups = {}
    for row in mappings:
        if row.recordType == "D":
            groups.setdefault(row.dataSetNo, []).append(row)
    assigned, derived = {}, []
    # Match explicit identities before trying untagged legacy projections.
    details.sort(key=lambda row: (split_dataset_query(row.query)[0] is None,
                                  row.query.casefold(), row.conditions, row.sortOrder))
    next_number = max([0, *[row.dataSetNo for row in mappings]]) + 1
    resolved = []
    for row in details:
        tagged, clean = split_dataset_query(row.query)
        dataset = tagged if tagged is not None else row.dataSetNo
        if dataset is None:
            candidates = []
            columns = query_column_names(clean)
            for number, layout in groups.items():
                try:
                    aligned_detail_layout(columns, layout, clean)
                except InvalidRun:
                    continue
                candidates.append(number)
            if len(candidates) > 1:
                raise InvalidRun("Legacy Detail datasets have ambiguous mappings; review dataset identities.")
            if candidates:
                dataset = candidates[0]
            else:
                # Only confirmed source identifiers can supply missing legacy
                # labels. Do not fabricate names for calculated/unnamed fields.
                sources = [_identifier(expression) for expression, _ in query_projections(clean)]
                if not all(sources) or len(set(sources)) != len(sources):
                    raise InvalidRun("Add explicit mappings for the legacy dataset's calculated or duplicate columns.")
                if next_number > 2_147_483_647:
                    raise InvalidRun("The dataset number exceeds the SQL Server integer limit.")
                dataset = next_number
                next_number += 1
                layout = [MappingRow(field=(alias or source).upper(), mappingColumn=source,
                                     recordType="Detail", startPosition="0", length="0", dataSetNo=dataset, colSeqNo=index)
                          for index, ((_, alias), source) in enumerate(zip(query_projections(clean), sources, strict=True), 1)]
                groups[dataset] = layout
                derived.extend(layout)
        if dataset in assigned or dataset not in groups:
            raise InvalidRun("Each Detail query needs its own confirmed dataset mapping.")
        assigned[dataset] = row
        resolved.append(row.model_copy(update={"dataSetNo": dataset}))
    if set(groups) != set(assigned):
        raise InvalidRun("The saved Detail queries do not cover all configured datasets.")
    other = [row for row in job.queryConfiguration if row.recttype.strip().upper() != "D"]
    return job.model_copy(update={
        "mapping": job.mapping.model_copy(update={"rows": job.mapping.rows + derived}),
        "queryConfiguration": other + sorted(resolved, key=lambda row: row.dataSetNo),
    })


def ordered_dataset_source(job, source):
    from app.retirement_procedure import ProcedureResultSet, ProcedureSource
    job = expand_legacy_datasets(job)
    details = distinct_details(job)
    if len(details) < 2 and not any(split_dataset_query(row.query)[0] is not None for row in details):
        return job, source, False
    if job.general.storeResultsToTable:
        raise InvalidRun("Turn off Store Results to Table for multiple datasets.")
    headers = [row for row in job.queryConfiguration if row.recttype == "H" and row.query.strip()]
    trailers = [row for row in job.queryConfiguration if row.recttype == "T" and row.query.strip()]
    if len(headers) > 1 or len(trailers) > 1 or len(source.result_sets) != len(headers) + len(details) + len(trailers):
        raise InvalidRun("The procedure result sets do not match the saved dataset queries.")
    queries = {row.dataSetNo: row for row in details}
    matched = {}
    for result in source.result_sets[len(headers):len(source.result_sets) - len(trailers)]:
        marker = DATASET_COLUMN.fullmatch(result.columns[3]) if len(result.columns) > 3 else None
        if marker:
            dataset = int(marker[1])
            if dataset not in queries or split_dataset_query(queries[dataset].query)[0] != dataset:
                raise InvalidRun("Unknown dataset identifier in the procedure result.")
            if any(len(row) != len(result.columns) or row[3] != str(dataset) for row in result.rows):
                raise InvalidRun("The returned dataset identifier is inconsistent.")
            result = ProcedureResultSet(result.columns[:3] + result.columns[4:],
                                        tuple(row[:3] + row[4:] for row in result.rows))
        else:
            candidates = [number for number, query in queries.items()
                          if split_dataset_query(query.query)[0] is None
                          and tuple(name.casefold() for name in result.columns) == query_column_names(query.query)]
            if len(candidates) != 1:
                raise InvalidRun("Cannot uniquely identify a legacy dataset result; save explicit dataset mappings first.")
            dataset = candidates[0]
        if dataset in matched:
            raise InvalidRun("The procedure returned the same dataset more than once.")
        matched[dataset] = result
    if set(matched) != set(queries):
        raise InvalidRun("A Detail dataset is missing from the procedure results.")
    numbers = sorted(queries)
    clean = [queries[number].model_copy(update={"query": split_dataset_query(queries[number].query)[1]}) for number in numbers]
    job = job.model_copy(update={"queryConfiguration": headers + clean + trailers})
    result_sets = source.result_sets[:len(headers)] + tuple(matched[number] for number in numbers)
    if trailers:
        result_sets += source.result_sets[-1:]
    return job, ProcedureSource(result_sets), len(numbers) > 1

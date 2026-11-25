"""Generate new payroll projections without duplicating SP metadata names.

Existing saved queries are never passed to or changed by this generator.
Aliases come only from the user's configured output labels.
"""
from collections import Counter

from app.retirement_datasets import tag_dataset_query
from app.retirement_query_builder import _expression, export_record_queries, ordered_mappings, sql_identifier
from app.retirement_results import InvalidRun, record_type_code


def payroll_record_queries(job):
    rows = ordered_mappings(row.model_copy(update={'recordType': record_type_code(row.recordType)})
                            for row in job.mapping.rows)
    records = export_record_queries(job, rows, [])
    default_dataset = next((row.dataSetNo for row in rows if record_type_code(row.recordType) == 'D'), 1)
    for record in records:
        kind = record['recttype']
        if kind == 'H' and job.mapping.includeHeader:
            continue  # Header labels are literals, not source projections.
        selected = [row for row in rows if record_type_code(row.recordType) == kind
                    and (kind != 'D' or row.dataSetNo == record.get('dataSetNo', default_dataset))]
        if not selected:
            continue
        projections = [_expression(row) for row in selected]
        names = Counter(row.mappingColumn.strip().casefold() for row, (_, named) in zip(selected, projections, strict=True) if named)
        reserved = {'valid_flag', 'retnum', 'sort1'}
        collisions = reserved | {name for name, count in names.items() if count > 1}
        used = reserved | {name for name, count in names.items() if count == 1 and name not in reserved}
        expressions = []
        changed = False
        for row, (expression, named) in zip(selected, projections, strict=True):
            if named and row.mappingColumn.strip().casefold() in collisions:
                alias = row.field.strip()
                if alias.casefold() in used:
                    raise InvalidRun('Use a distinct output field label for a payroll column that duplicates a metadata or source name.')
                expression += ' AS ' + sql_identifier(alias)
                used.add(alias.casefold())
                changed = True
            expressions.append(expression)
        if changed:
            prefix = 'SELECT TOP 1' if kind == 'H' else 'SELECT DISTINCT' if kind == 'T' else 'SELECT'
            query = prefix + ' valid_flag, retnum, paydate AS sort1, ' + ', '.join(expressions)
            if kind == 'D' and 'dataSetNo' in record:
                query = tag_dataset_query(query, record['dataSetNo'])
            record['query'] = query
    return records

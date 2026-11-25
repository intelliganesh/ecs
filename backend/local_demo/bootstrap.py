"""Create-only local builder sandbox from a metadata/catalog snapshot.

Never connects to the source server. Existing local objects and rows are retained.
No report procedure, job, scheduler or mail delivery is executed by this script.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

import pyodbc
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent


def quote(value):
    return '[' + value.replace(']', ']]') + ']'


def group_columns(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['table_name']].append(row)
    return groups


def column_sql(row):
    result = quote(row['column_name'])
    if row['is_computed']:
        return result + ' AS ' + row['computed_definition']
    kind = row['type_name']
    result += ' ' + kind
    if kind in ('varchar', 'nvarchar', 'char', 'nchar', 'varbinary', 'binary'):
        size = row['max_length']
        result += '(' + ('max' if size == -1 else str(size // 2 if kind in ('nvarchar', 'nchar') else size)) + ')'
    elif kind in ('numeric', 'decimal'):
        result += f"({row['precision']},{row['scale']})"
    elif kind in ('datetime2', 'datetimeoffset', 'time'):
        result += f"({row['scale']})"
    if row['collation_name']:
        result += ' COLLATE ' + row['collation_name']
    if row['is_identity']:
        result += f" IDENTITY({row['identity_seed']},{row['identity_increment']})"
    result += ' NULL' if row['is_nullable'] else ' NOT NULL'
    if row['default_definition']:
        result += ' DEFAULT ' + row['default_definition']
    return result


def create_table(schema, name, rows, keys):
    definitions = [column_sql(row) for row in rows]
    grouped = defaultdict(list)
    for key in keys:
        if key['table_name'] == name:
            grouped[key['constraint_name']].append(key)
    for constraint, columns in grouped.items():
        kind = 'PRIMARY KEY' if columns[0]['type_desc'] == 'PRIMARY_KEY_CONSTRAINT' else 'UNIQUE'
        ordering = ','.join(quote(c['column_name']) + (' DESC' if c['is_descending_key'] else ' ASC') for c in columns)
        definitions.append(f"CONSTRAINT {quote(constraint)} {kind} {columns[0]['index_type']} ({ordering})")
    return f"CREATE TABLE {quote(schema)}.{quote(name)} (\n" + ',\n'.join(definitions) + '\n)'


def fingerprint(connection, database, table):
    cursor = connection.cursor()
    cursor.execute(f'SELECT * FROM {quote(database)}.dbo.{quote(table)}')
    rows = sorted(json.dumps(list(row), default=str, separators=(',', ':')) for row in cursor.fetchall())
    return {'rows': len(rows), 'sha256': sha256('\n'.join(rows).encode()).hexdigest()}


def existing_objects(connection, database):
    cursor = connection.cursor()
    cursor.execute(f'SELECT s.name,o.name,o.type FROM {quote(database)}.sys.objects o JOIN {quote(database)}.sys.schemas s ON s.schema_id=o.schema_id WHERE o.is_ms_shipped=0')
    return {(s.lower(), n.lower()): kind for s, n, kind in cursor.fetchall()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--add-payroll-register-alias', action='store_true',
                        help='Explicit local-only compatibility column; does not change the copied SP.')
    args = parser.parse_args()
    config = dotenv_values(ROOT / '.env')
    if config.get('DB_HOST') != '127.0.0.1' or config.get('DB_NAME') != 'ecs':
        raise SystemExit('Only the explicitly configured loopback ecs target is allowed.')
    password = config['DB_PASSWORD'].replace('}', '}}')
    connection = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;DATABASE=ecs;UID=sa;'
        f'PWD={{{password}}};TrustServerCertificate=yes', timeout=10, autocommit=True,
    )
    cursor = connection.cursor()
    server = cursor.execute("SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(128))").fetchval()
    if server != args.expected_server or server.upper() == 'ESC-SQL02':
        raise SystemExit('Local server identity did not match; no changes made.')
    snapshot = args.snapshot
    read = lambda name: json.loads((snapshot / name).read_text())
    configs = group_columns(read('config-columns.json'))
    sources = group_columns(read('prism-columns.json'))
    keys = read('config-keys.json')
    source_keys = read('prism-keys.json')
    modules = read('modules.json')
    functions = read('functions.json')
    # Only current flow procedures; historical *_old procedures are intentionally excluded.
    modules = [m for m in modules if not m['name'].endswith('_old')]
    original = existing_objects(connection, 'ecs')
    before = {name: fingerprint(connection, 'ecs', name) for (schema, name), kind in original.items() if schema == 'dbo' and kind == 'U'}
    report = {'server': server, 'created': [], 'preserved': [], 'catalogs': {}, 'conflicts': [], 'blocked_modules': []}
    actions = []
    database_names = {r[0].lower() for r in cursor.execute('SELECT name FROM sys.databases').fetchall()}

    def execute(database, sql, params=()):
        if not args.apply:
            return
        cursor.execute('USE ' + quote(database))
        cursor.execute(sql, params) if params else cursor.execute(sql)

    def ensure_database(name):
        if name.lower() not in database_names:
            actions.append('CREATE DATABASE ' + quote(name))
            execute('master', actions[-1])
            database_names.add(name.lower())
            report['created'].append(name + ' database')

    def ensure_tables(database, schema, tables, table_keys):
        objects = existing_objects(connection, database) if args.apply or database.lower() in initial_databases else {}
        if schema != 'dbo' and not any(s == schema.lower() for s, _ in objects):
            # Query schemas separately, since an empty schema has no objects.
            schema_exists = False
            if args.apply or database.lower() in initial_databases:
                schema_exists = cursor.execute(f'SELECT 1 FROM {quote(database)}.sys.schemas WHERE name=?', schema).fetchone() is not None
            if not schema_exists:
                sql = 'CREATE SCHEMA ' + quote(schema)
                actions.append(sql)
                execute(database, sql)
        for name, rows in tables.items():
            if (schema.lower(), name.lower()) in objects:
                report['preserved'].append(f'{database}.{schema}.{name}')
                actual = cursor.execute(f"SELECT c.name,t.name,c.max_length,c.precision,c.scale,c.is_nullable FROM {quote(database)}.sys.columns c JOIN {quote(database)}.sys.types t ON t.user_type_id=c.user_type_id WHERE c.object_id=OBJECT_ID(?) ORDER BY c.column_id", f'{database}.{schema}.{name}').fetchall()
                by_name = {r[0].lower(): tuple(r[1:]) for r in actual}
                for row in rows:
                    expected = tuple(row[k] for k in ('type_name', 'max_length', 'precision', 'scale', 'is_nullable'))
                    if by_name.get(row['column_name'].lower()) != expected:
                        report['conflicts'].append(f"{database}.{schema}.{name}.{row['column_name']}: existing definition differs; preserved")
                continue
            sql = create_table(schema, name, rows, table_keys)
            actions.append(sql)
            execute(database, sql)
            report['created'].append(f'{database}.{schema}.{name}')

    initial_databases = database_names.copy()
    ensure_database('prism')
    ensure_tables('prism', 'export', sources, source_keys)
    ensure_tables('ecs', 'dbo', configs, keys)
    if args.add_payroll_register_alias:
        present = cursor.execute("SELECT name FROM prism.sys.columns WHERE object_id=OBJECT_ID('prism.export.EMPLOYEE_PAYROLL_REGISTER') AND name='R_Gross_Earn'").fetchone() if args.apply or 'prism' in initial_databases else None
        if present is None:
            sql = 'ALTER TABLE [prism].[export].[EMPLOYEE_PAYROLL_REGISTER] ADD [R_Gross_Earn] AS ([GROSS_EARN])'
            actions.append(sql)
            execute('prism', sql)
            report['created'].append('prism.export.EMPLOYEE_PAYROLL_REGISTER.R_Gross_Earn computed alias (explicitly authorized)')

    # Preserve hardcoded database references in the original SPs with LOCAL aliases.
    for database in ('Syd', 'Syd_Testing'):
        ensure_database(database)
        objects = existing_objects(connection, database) if args.apply or database.lower() in initial_databases else {}
        for name in configs:
            if ('dbo', name.lower()) not in objects:
                sql = f'CREATE SYNONYM dbo.{quote(name)} FOR [ecs].dbo.{quote(name)}'
                actions.append(sql)
                execute(database, sql)
                report['created'].append(f'{database}.dbo.{name} synonym')

    for database, definitions in (('ecs', functions), ('Syd_Testing', functions), ('ecs', sorted(modules, key=lambda m: m['name'] != 'payroll_wage_data_wcsumm'))):
        objects = existing_objects(connection, database) if args.apply or database.lower() in initial_databases else {}
        for module in definitions:
            name = module['name']
            if ('dbo', name.lower()) in objects:
                report['preserved'].append(f'{database}.dbo.{name}')
                continue
            sql = module['definition']
            significant = re.sub(r'(?m)^\s*--[^\n]*(?:\n|$)', '', sql)
            if not re.match(r'\s*CREATE\s+(?:PROC(?:EDURE)?|VIEW|FUNCTION)\b', significant, re.I):
                raise RuntimeError('Expected an unmodified CREATE definition: ' + name)
            actions.append(sql)
            execute(database, 'SET ANSI_NULLS ' + ('ON' if module['uses_ansi_nulls'] else 'OFF'))
            execute(database, 'SET QUOTED_IDENTIFIER ' + ('ON' if module['uses_quoted_identifier'] else 'OFF'))
            try:
                execute(database, sql)
            except pyodbc.Error as exc:
                report['blocked_modules'].append({'name': name, 'database': database, 'error': str(exc)})
                continue
            report['created'].append(f'{database}.dbo.{name}')

    catalogs = read('catalogs.json')
    natural_keys = {'rjob_file_typ': ['filetyp'], 'rjobformat': ['jobformat', 'jobformattype'], 'rjob_mapping_column': ['mapping_column'],
                    'payroll_mapping_column': ['mapping_column'], 'payrollformat': ['jobformat', 'jobformattype'], 'payroll_master_grouping': ['grouping_id']}
    for name, rows in catalogs.items():
        actual_columns = {r[0].lower() for r in cursor.execute("SELECT name FROM ecs.sys.columns WHERE object_id=OBJECT_ID(?)", 'ecs.dbo.' + name).fetchall()} if args.apply or ('dbo', name.lower()) in original else {c['column_name'].lower() for c in configs[name]}
        identity = {r['column_name'].lower() for r in configs[name] if r['is_identity']}
        added = 0
        for row in rows:
            values = {k: v for k, v in row.items() if k.lower() in actual_columns and k.lower() not in identity and k.lower() != 'msrepl_tran_version'}
            key_names = natural_keys[name]
            if not all(k in values for k in key_names):
                # Discover the source's actual formatting key instead of assuming one.
                key_names = [next(k for k in values if k.lower() in ('format', 'formatcode', 'format_code', 'jobformat'))] if name in ('rjobformat', 'payrollformat') else key_names
            where = ' AND '.join(quote(k) + '=?' for k in key_names)
            existing = None
            if args.apply or ('dbo', name.lower()) in original:
                existing = cursor.execute(f'SELECT * FROM ecs.dbo.{quote(name)} WHERE ' + where, tuple(values[k] for k in key_names)).fetchone()
            if existing is not None:
                existing_values = dict(zip((c[0] for c in cursor.description), existing))
                if any(str(existing_values.get(k)) != str(v) for k, v in values.items()):
                    report['conflicts'].append(f'{name} catalog entry {tuple(values[k] for k in key_names)} differs; preserved')
                continue
            sql = f'INSERT INTO dbo.{quote(name)} (' + ','.join(quote(k) for k in values) + ') VALUES (' + ','.join('?' for _ in values) + ')'
            execute('ecs', sql, tuple(values.values()))
            added += 1
        report['catalogs'][name] = {'source_rows': len(rows), 'missing_rows_added' if args.apply else 'missing_rows_planned': added}

    # Original records must remain present and unchanged, including catalog rows.
    for name, baseline in before.items():
        current = fingerprint(connection, 'ecs', name)
        if name not in catalogs and current != baseline:
            raise RuntimeError('Existing local table changed unexpectedly: ' + name)
    report['existing_non_catalog_tables_unchanged'] = True
    report['mode'] = 'applied' if args.apply else 'plan only'
    (snapshot / ('local-apply-report.json' if args.apply else 'local-plan.json')).write_text(json.dumps(report, indent=2))
    (snapshot / 'local-create-only.sql').write_text('\nGO\n'.join(actions))
    print(json.dumps(report, indent=2))
    connection.close()


if __name__ == '__main__':
    main()

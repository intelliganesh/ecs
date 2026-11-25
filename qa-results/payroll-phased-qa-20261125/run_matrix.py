"""Authorized local job-2 QA only; API saves/runs, SELECT-only DB verification.

No job creation, source-data writes, schema/SP/query.brl edits or email enabling.
Baseline configuration is restored using the normal API even after a failure.
"""
import copy
import csv
import io
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8001/api/v1/payroll-builder'
BASELINE = json.loads((ROOT / 'job-2-baseline.json').read_text())
RESULTS = []


def api(method, path, data=None):
    request = urllib.request.Request(BASE + path, method=method,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def save(job):
    payload = {k: v for k, v in job.items() if k not in ('id', 'queryLocked', 'queryConfiguration')}
    saved = api('PUT', '/jobs/2', payload)
    reopened = api('GET', '/jobs/2')
    # GET includes a derived DB timestamp omitted by the PUT response model.
    comparable = copy.deepcopy(reopened)
    comparable['schedule'].pop('startDateTime', None)
    assert saved == comparable, 'Save/reopen mismatch in persisted fields'
    return reopened


def run(label, start='2026-10-01', end='2026-11-30'):
    result = api('POST', f'/jobs/2/run?start_date={start}&end_date={end}')
    assert result['emailDelivery']['enabled'] is False, 'MAIL MUST REMAIN DISABLED'
    assert result['storedRows'] == 0
    (ROOT / (label + '.json')).write_text(json.dumps(result, indent=2))
    folder = Path('/Users/apple/Desktop/ecs/backend/report-output/local-demo/payroll/manual/2') / result['runId']
    for file in result['files']:
        assert (folder / file['fileName']).read_bytes() == file['csv'].encode(), 'Published bytes differ'
        assert '__ecs_dataset_' not in file['csv'] and 'valid_flag' not in file['csv']
    return result


def restore():
    restored = save(BASELINE)
    differences = [key for key in ('general', 'schedule', 'mapping', 'subscriptions', 'fileSettings', 'wageMappings', 'grouping')
                   if restored[key] != BASELINE[key]]
    (ROOT / 'job-2-restored.json').write_text(json.dumps(restored, indent=2))
    assert not differences, f'Restoration differs: {differences}'
    assert api('GET', '/jobs/1') == json.loads((ROOT / 'job-1-baseline.json').read_text()), 'Job 1 changed'


def matrix():
    formats = {'Comma': (',', '.csv'), 'CSV': (',', '.csv'), 'Pipe': ('|', '.txt'),
        'Tab': ('\t', '.tsv'), 'Semicolon': (';', '.txt'), 'TILDE': ('~', '.txt'),
        'FIXED': (' ', '.txt'), 'Space': (' ', '.csv')}
    options = api('GET', '/options')
    assert set(formats) == set(options['fileFormats'])
    dates = ['2026-10-15', '2026-11-13', '2026-11-20', '2026-11-24']
    for fmt, (delimiter, suffix) in formats.items():
        for name in options['outputFileNameFormats']:
            code = name['value']
            job = copy.deepcopy(BASELINE)
            job['general'].update(fileFormat=fmt, outputFileNameFormat=code)
            if fmt == 'FIXED':
                for row in job['mapping']['rows']:
                    row.update(startPosition=str((row['colSeqNo'] - 1) * 36), length='36')
            save(job)
            result = run(f'matrix-{fmt}-{code}')
            assert result['rowCount'] == 24
            assert result['delimiter'] == delimiter
            expected = set()
            for client in (['000901', '000902'] if 'CLIENT' in code else ['']):
                for day in (dates if 'PAYDAY' in code else ['']):
                    pieces = {'FILENAME': BASELINE['general']['fileName'], 'CLIENT': client, 'PAYDAY': day}
                    expected.add('_'.join(pieces[p] for p in code.split('_')) + suffix)
            assert {f['fileName'] for f in result['files']} == expected
            detail_count = 0
            for file in result['files']:
                if fmt == 'FIXED':
                    lines = file['csv'].splitlines()
                    assert all(not line or len(line) == 108 for line in lines)
                    rows = [[line[i:i+36].strip() for i in (0,36,72)] if line else [] for line in lines]
                    assert file['excelRows'] is not None
                else:
                    rows = list(csv.reader(io.StringIO(file['csv']), delimiter=delimiter))
                nonempty = [row for row in rows if row]
                assert all(len(row) == 3 for row in nonempty)
                assert nonempty[0] == ['Client ID', 'Employee ID', 'Earnings']
                assert nonempty.count(['Employee Name', 'Pay Date', 'Paid Hours']) == 1
                detail_count += len(nonempty) - 2
            assert detail_count == 24
            RESULTS.append({'scenario': f'{fmt}/{code}', 'status': 'PASS', 'runId': result['runId'],
                            'files': len(result['files']), 'detailRows': result['rowCount']})
        print(f'{fmt}: 7/7 local Save/Run/file checks passed', flush=True)


if __name__ == '__main__':
    try:
        matrix()
    except Exception as error:
        RESULTS.append({'status': 'FAIL', 'error': str(error)})
        raise
    finally:
        try:
            restore()
            RESULTS.append({'scenario': 'Restore job 2 and preserve job 1', 'status': 'PASS'})
        finally:
            (ROOT / 'matrix-summary.json').write_text(json.dumps(RESULTS, indent=2))

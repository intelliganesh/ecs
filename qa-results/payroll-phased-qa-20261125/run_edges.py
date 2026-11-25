"""Phase 3 local-only API acceptance checks; restores job 2 via normal Save."""
import copy
import csv
import io
import json
import operator
import urllib.error
from run_matrix import ROOT, BASELINE, api, save, run, restore

results = []


def check(name, action):
    try:
        action()
        results.append({'scenario': name, 'status': 'PASS'})
    except Exception as error:
        results.append({'scenario': name, 'status': 'FAIL', 'error': str(error)})
    print(results[-1], flush=True)
    (ROOT / 'edges-summary.json').write_text(json.dumps(results, indent=2))


def condition_test(symbol, function):
    job = copy.deepcopy(BASELINE)
    job['fileSettings']['conditionalStatements'][0].update(condition=symbol, value='1000')
    save(job)
    result = run('condition-' + {'=':'eq','==':'eq2','!=':'ne','<>':'ne2','<':'lt','<=':'le','>':'gt','>=':'ge'}[symbol])
    baseline = json.loads((ROOT / 'matrix-CSV-FILENAME.json').read_text())['files'][0]['csv']
    rows = list(csv.reader(io.StringIO(baseline)))
    split = rows.index(['Employee Name', 'Pay Date', 'Paid Hours'])
    earnings = [float(r[2]) for r in rows[1:split] if r]
    expected = sum(function(value, 1000) for value in earnings) * 2
    assert result['rowCount'] == expected, (result['rowCount'], expected)


def range_test():
    save(BASELINE)
    assert run('restricted-dates','2026-11-20','2026-11-24')['rowCount'] == 12
    result = run('empty-dates','2000-01-01','2000-01-02')
    assert result['rowCount'] == 0 and result['files'] == []


def typed_filters():
    job = copy.deepcopy(BASELINE)
    job['fileSettings']['conditionalStatements'] = [
        {'mappingColumn':'paydate','condition':'>=','value':'2026-11-20','valueType':'date'},
        {'mappingColumn':'emplstatus','condition':'=','value':'A','valueType':'text'}]
    save(job)
    assert run('date-text-filters')['rowCount'] == 12
    job['fileSettings']['conditionalStatements'][1]['value'] = 'ZZ_NO_MATCH'
    save(job)
    assert run('text-exclusion')['rowCount'] == 0


def headers_trailers():
    for header in (False, True):
        job = copy.deepcopy(BASELINE)
        job['mapping']['includeHeader'] = header
        for dataset in (1,2):
            job['mapping']['rows'].append({'field':f'Dataset {dataset} End','mappingColumn':'Default',
                'recordType':'Trailer','defaultValue':f'END{dataset}','dataSetNo':dataset,'colSeqNo':1,
                'startPosition':'0','length':'0','format':''})
        saved = save(job)
        assert sum(q['recttype']=='T' for q in saved['queryConfiguration']) == 1
        result = run(f'headers-{header}-trailers')
        assert result['rowCount'] == 24
        for file in result['files']:
            rows = list(csv.reader(io.StringIO(file['csv'])))
            separator = rows.index([])
            assert rows[separator-1] == ['END1'] and rows[-1] == ['END2']
            assert (rows[0] == ['Client ID','Employee ID','Earnings']) is header


def merge_flag():
    original = None
    for merge in (False,True):
        job = copy.deepcopy(BASELINE)
        job['subscriptions']['mergeFiles'] = merge
        assert save(job)['subscriptions']['mergeFiles'] is merge
        result = run(f'merge-{merge}')
        # This setting merges emailed attachments only; normal report files stay separate.
        files = [(f['fileName'], f['csv']) for f in result['files']]
        assert len(files) == 2
        if original is None:
            original = files
        else:
            assert files == original


def rejected(name, patch, method='PUT', path='/jobs/2'):
    before = api('GET','/jobs/2')
    try:
        api(method,path,patch)
    except urllib.error.HTTPError as error:
        assert error.code == 422, error.code
    else:
        raise AssertionError('Invalid request was accepted')
    assert api('GET','/jobs/2') == before, 'Rejected request changed saved configuration'


def formatting():
    options = api('GET','/options')
    for kind, index in (('number',2),('date',4),('text',1)):
        for mask in options['mappingFormatsByType'][kind]:
            job = copy.deepcopy(BASELINE)
            job['mapping']['rows'][index].update(format=mask, length='24' if kind=='text' else '0')
            save(job)
            assert run('format-'+str(index)+'-'+mask.replace('/','-').replace('$','dollar'))['rowCount'] == 24


try:
    for symbol, function in [('=',operator.eq),('==',operator.eq),('!=',operator.ne),('<>',operator.ne),
                              ('<',operator.lt),('<=',operator.le),('>',operator.gt),('>=',operator.ge)]:
        check('Numeric boundary '+symbol, lambda s=symbol,f=function:condition_test(s,f))
    check('Restricted and empty manual date ranges',range_test)
    check('Date and text filters, including exclusion',typed_filters)
    check('Header ON/OFF and dataset-specific trailers',headers_trailers)
    check('Merge flag persists; normal files remain separate',merge_flag)
    check('All numeric/date/text formatting masks execute',formatting)
    save(BASELINE)
    invalid = [
        ('Blank filename',{'general':{'fileName':''}}),
        ('Unknown format',{'general':{'fileFormat':'UNKNOWN'}}),
        ('Unknown filename choice',{'general':{'outputFileNameFormat':'UNKNOWN'}}),
        ('Missing Detail mappings',{'mapping':{'rows':[]}}),
        ('Invalid recipient',{'subscriptions':{'rows':[{'client':'901','email':'bad-mail'}]}}),
        ('Duplicate clients',{'subscriptions':{'rows':[{'client':'901','email':'x@example.invalid'}]*2}}),
        ('Invalid monthly date',{'schedule':{'monthlyDate':'32'}}),
        ('Invalid hour',{'schedule':{'hour':'13'}}),
        ('Unknown grouping',{'grouping':['UNKNOWN']}),
        ('SQL override rejected',{'queryConfiguration':[]}),
    ]
    for name, payload in invalid:
        check('Validation: '+name,lambda n=name,p=payload:rejected(n,p))
    check('Validation: reversed dates',lambda:rejected('dates',None,'POST','/jobs/2/run?start_date=2026-11-30&end_date=2026-10-01'))
    check('Validation: missing dates',lambda:rejected('dates',None,'POST','/jobs/2/run'))
finally:
    restore()
    (ROOT / 'edges-summary.json').write_text(json.dumps(results,indent=2))

"""Local catalog/dropdown round trips and output field checks for existing job 2."""
import copy
import csv
import io
import json
from urllib.parse import quote
from run_matrix import ROOT, BASELINE, api, save, run, restore

results = []
try:
    options = api('GET','/options')
    job = copy.deepcopy(BASELINE)
    job['mapping']['rows'] = [{'field':label,'mappingColumn':key,'recordType':'Detail',
        'startPosition':'0','length':'0','defaultValue':'DEMO_CONSTANT' if key=='Default' else '',
        'format':'','dataSetNo':1,'colSeqNo':i} for i,(key,label) in enumerate(options['mappingColumnLabels'].items(),1)]
    save(job)
    result = run('all-56-mapping-fields')
    assert result['rowCount'] == 12
    blank = set()
    for file in result['files']:
        rows = list(csv.reader(io.StringIO(file['csv'])))
        assert rows[0] == list(options['mappingColumnLabels'].values())
        assert all(len(row)==56 for row in rows)
        blank.update(rows[0][i] for i in range(56) if all(not row[i] for row in rows[1:]))
        index = rows[0].index('Default')
        assert all(row[index]=='DEMO_CONSTANT' for row in rows[1:])
    results.append({'scenario':'All 56 mapping catalog choices; source fields plus Default constant',
        'status':'PASS','unpopulatedFields':sorted(blank)})
    for mask in options['mappingFormatsByType']['date']:
        job = copy.deepcopy(BASELINE)
        job['mapping']['rows'][4]['format'] = mask
        save(job)
        result = run('date-mask-'+quote(mask,safe=''))
        rows=list(csv.reader(io.StringIO(result['files'][0]['csv'])))
        index=rows.index(['Employee Name','Pay Date','Paid Hours'])
        expected={'MM/DD/YYYY':'10/15/2026','MM-DD-YYYY':'10-15-2026','CCYYMMDD':'20261015','MMDDYYYY':'10152026'}[mask]
        assert rows[index+1][1]==expected
    results.append({'scenario':'All four date mask values checked','status':'PASS'})
    for mask in options['mappingFormatsByType']['ssn']:
        job = copy.deepcopy(BASELINE)
        row=job['mapping']['rows'][1]
        row.update(field='Demo SSN',mappingColumn='ssn',format=mask)
        save(job)
        result=run('ssn-mask-'+mask)
        assert result['rowCount']==24
    results.append({'scenario':'Both SSN masks execute with fictional local placeholders','status':'PASS'})
    codes=api('GET','/pay-codes?client_id=901')
    assert codes
    for column in options['wageColumns']:
        job=copy.deepcopy(BASELINE)
        job['wageMappings']=[{'clientId':901,'wageColumn':column['value'],'payCode':codes[0]['value'],'searchWord':'Demo search'}]
        assert save(job)['wageMappings']==job['wageMappings']
    results.append({'scenario':'All six wage field choices Save/reopen (storage, not calculation proof)','status':'PASS'})
    job=copy.deepcopy(BASELINE)
    job['grouping']=[group['value'] for group in options['groupingOptions']]
    assert set(save(job)['grouping'])==set(job['grouping'])
    results.append({'scenario':'All four grouping choices Save/reopen (storage only)','status':'PASS'})
    literal='O\'Brien,pipe|semi;tab\t~"quoted"'
    for fmt,delimiter in [('CSV',','),('Pipe','|'),('Tab','\t'),('Semicolon',';'),('TILDE','~'),('Space',' ')]:
        job=copy.deepcopy(BASELINE)
        job['general']['fileFormat']=fmt
        job['mapping']['rows'][1].update(mappingColumn='Default',defaultValue=literal)
        save(job)
        result=run('escaped-literal-'+fmt)
        for file in result['files']:
            rows=list(csv.reader(io.StringIO(file['csv']),delimiter=delimiter))
            split=rows.index(['Employee Name','Pay Date','Paid Hours'])
            assert all(row[1]==literal for row in rows[1:split] if row)
    results.append({'scenario':'Quotes/apostrophes/all delimiters inside a constant round trip correctly','status':'PASS'})
    print(json.dumps(results,indent=2))
finally:
    restore()
    (ROOT/'catalog-summary.json').write_text(json.dumps(results,indent=2))

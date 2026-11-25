"""Isolated real-clock scheduled worker for local job 2; no background scheduler."""
import copy
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, '/Users/apple/Desktop/ecs/backend')
from dotenv import dotenv_values
os.environ.update({k:v for k,v in dotenv_values('/Users/apple/Desktop/ecs/backend/local_demo/.env').items() if v is not None})
os.environ['SCHEDULER_ENABLED'] = 'false'
os.environ['PAYROLL_SCHEDULER_ENABLED'] = 'false'
from app.core.config import get_settings
from app import payroll_scheduler as scheduler
from app.report_scheduler import _scheduled_slot
from run_matrix import ROOT, BASELINE, save, restore

settings = get_settings()
assert (settings.db_host, settings.db_name, settings.mail_enabled) == ('127.0.0.1','ecs',False)
results = []
try:
    for frequency in ('Daily','Weekly','Bi-Weekly','Monthly'):
        job = copy.deepcopy(BASELINE)
        job['schedule']['buildFrequency'] = frequency
        assert save(job)['schedule']['buildFrequency'] == frequency
        results.append({'scenario':frequency+' schedule Save/reopen','status':'PASS'})
    now = datetime.now(UTC)
    job = copy.deepcopy(BASELINE)
    job['schedule'].update(startDate=now.date().isoformat(), buildFrequency='Daily',
        hour=str(now.hour % 12 or 12), minute=f'{now.minute:02}', meridiem='PM' if now.hour>=12 else 'AM')
    save(job)
    with scheduler.payroll.engine.connect() as connection:
        row = connection.execute(scheduler.payroll.READS['READ_SCHEDULE'], {'jobid':2}).mappings().one()
    slot = _scheduled_slot(row, now)
    assert slot is not None
    isolated = settings.model_copy(update={'scheduler_enabled':True,'payroll_scheduler_enabled':True,
        'report_output_dir':Path('/Users/apple/Desktop/ecs/backend/report-output/local-demo-phased-qa-20261125')})
    output = isolated.report_output_dir/'payroll'/'scheduled'/'2'/slot.strftime('%Y%m%dT%H%M%SZ')
    assert not output.exists(), 'Existing evidence must not be overwritten'
    # Guard delivery even if the worker ever regresses past MAIL_ENABLED=false.
    with patch('smtplib.SMTP',side_effect=AssertionError('Real mail prohibited')), \
         patch('smtplib.SMTP_SSL',side_effect=AssertionError('Real mail prohibited')):
        scheduler._run_scheduled_job(isolated,2,slot,now)
        files = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*') if p.is_file()}
        assert files, 'Worker produced neither reports nor completion marker'
        scheduler._run_scheduled_job(isolated,2,slot,now)
        assert files == {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*') if p.is_file()}
    results.append({'scenario':'Real-clock targeted scheduled worker; unchanged SP S flag; mail disabled; second invocation skips completed slot',
        'status':'PASS','slot':slot.isoformat(),'files':files,'output':str(output)})
    print(json.dumps(results,indent=2))
finally:
    restore()
    (ROOT/'schedule-summary.json').write_text(json.dumps(results,indent=2))

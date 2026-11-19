# Verification record — 18 November 2026

## Scope and preservation

User requested investigation and Markdown output only. The investigation did not edit application source, execute migrations, write database rows, start a backend/scheduler, submit Finish, submit Run, or send messages/emails. Existing local processes remained running independently. New analysis files are under docs/retirement-builder-analysis; existing dirty files were left untouched.

The initial git status already showed edits to README.md, backend/app/payroll_source.py, backend/app/report_scheduler.py, backend/app/retirement_results.py, backend/app/routers/retirement_builder.py, backend/config/options.xml, three backend test files, frontend/src/App.tsx, frontend/src/retirementBuilder.ts, frontend/src/styles.css and frontend/tests/retirementBuilder.test.mjs, plus untracked backend/config/payroll_record_queries.json and backend/migrations/012_payroll_report_date_range.sql. These documents describe that working-tree implementation, not only committed HEAD.

## Executed tests

Backend invocation used Python from backend/.venv, unittest discovery of backend/tests, and unittest.mock.patch on the actual engine.connect and engine.begin to raise on any unmocked live database access. PYTHONDONTWRITEBYTECODE=1 prevented .pyc generation for this invocation.

```python
suite = unittest.defaultTestLoader.discover('backend/tests')
with patch.object(engine, 'connect', side_effect=AssertionError('Live DB disabled during analysis tests')), \
     patch.object(engine, 'begin', side_effect=AssertionError('Live DB disabled during analysis tests')):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
```

Observed: `Ran 54 tests in 0.125s`, `OK`, process exit0. Passing assertions include mapping/catalog behavior, write parameter construction with mocked connections, date/range validation, idempotency, rendering/grouping/formatting, email eligibility and scheduler timing. They do not prove actual SQL writes or external mail delivery.

Frontend command from frontend directory:

```text
node --test tests/retirementBuilder.test.mjs
```

Observed: tests9, pass9, fail0, skipped0, process exit0. This suite creates/removes its temporary Vite cache and uses in-memory workbook data. No application source was changed.

## Live read-only evidence

[read-only-http.json](read-only-http.json) contains sanitized GET status/shape metadata. It intentionally omits company names, job names/configuration, client names/IDs, emails, report data and credentials. An existing numeric job ID is included in its request path only to identify the observed GET route.

[read-only-database.json](read-only-database.json) contains column metadata, noncustomer lookup definitions, configured payroll procedure name, signature, and normalized-definition comparison. All SQL issued during metadata inspection was SELECT-only. No current employee, salary, company contact, report result or subscription values were exported. Full connection configuration and environment files were not reproduced.

The procedure comparison normalized CREATE OR ALTER/ALTER to CREATE and whitespace. It matched migration012. This proves the visible installed definition at inspection time, not that every prior migration ran.

Other observations: localhost5174/retirement-builder HTTP200; backend8000/health/db returned connected. Clients GET repeated to confirm failure status503; reason was not investigated by reading potentially sensitive server logs.

## Browser observations

A temporary background in-app browser was opened at the requested localhost route. It initially redirected to Login. The prefilled demo login opened Dashboard. An unsaved fake job name was entered, Comma chosen, and all four wizard steps visited. Required-name/format messages, five separator options, blank schedule acceptance, empty mapping state, Add Dataset, numeric Format showing No format only, empty File Settings and Cancel, and empty subscriptions were observed. Refresh on Subscriptions followed by Back showed the retained Employee Count mapping. Cancel returned to Dashboard. No database-save/run action occurred.

Browser observations are recorded as narrative evidence; no screenshot containing existing job or personal data was saved. They do not verify completed submission, live report output, SMTP or scheduled execution.

## Known gaps

- Product-owner intent, target provider schema and user roles: NOT VERIFIED.
- Cause of clients503/upstream metadata or permissions: NOT VERIFIED.
- Live POST/PUT/run, actual report numbers, schedule execution, SMTP acceptance/inbox delivery: NOT VERIFIED.
- Running scheduler timezone/enabled config, external executable internals and multiworker deployment: NOT VERIFIED.
- Crash recovery/large-data behavior outside covered tests: NOT VERIFIED.
- Unexpected unhandled errors outside explicitly caught exception types: NOT VERIFIED; documented behavior should not be read as a blanket error guarantee.

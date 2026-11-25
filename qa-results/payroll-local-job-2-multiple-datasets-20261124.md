# Payroll job 2 — multiple datasets

Verified on 24 November 2026 through the local Payroll Builder UI at
`http://127.0.0.1:5175/payroll-builder`.

- Database target verified before Save/Run: `127.0.0.1:1433/ecs`, server
  `3fc1a6c70746`. `MAIL_ENABLED=false`; both schedulers disabled during QA.
- Created exactly one additional job: **2**, `Payroll_MultiDataset_QA_20261124`.
- CSV, File Name + Client ID, automatic headers ON, Store Results to Table OFF.
- Dataset 1: Client ID (`RetNum`), Employee ID (`PrismID`), Earnings (`earnings`).
- Dataset 2: Employee Name (`Employee_Name`), Pay Date (`paydate`), Paid Hours
  (`hours_worked`). Three Detail mappings per dataset, sequences 1–3.
- Job-level sorting: `paydate`, priority 1. Condition: `earnings > 0`.
- Subscribed only demo clients 901 and 902, with placeholder `.invalid` emails.
  No wage mappings or grouping overrides were needed for these six fields.
- Saved schedule: Wednesday, 25 November 2026, 04:00 AM, weekly. No scheduled
  execution was triggered.
- Manual Run dates: **2026-10-01 through 2026-11-30**. Procedure:
  `dbo.payrolljobbuilder`, job ID 2, manual run type `A`.
- UI outcome: **Success**, 24 Detail rows generated, zero result rows stored to
  a report table, email delivery disabled. Normal job/history bookkeeping applies.
- Client 901 CSV: 8 Detail rows in each dataset (16 total).
- Client 902 CSV: 4 Detail rows in each dataset (8 total).
- Inspected actual CSVs: correct three-column headers per section, blank section
  separator, positive earnings, matching client IDs, sorted pay dates, no internal
  dataset markers or SP metadata in exported cells. Browser downloads match server
  file bytes exactly.

Artifacts are preserved under
`backend/report-output/local-demo/payroll/manual/2/b37d3edc-e65c-44e2-afed-9a8215fe40f6/`,
with matching CSVs in the user's Downloads directory.

The associated code change removes Payroll Builder's edit controls lock and
rebuilds generated queries, mappings, sorting and conditions atomically when
query-dependent settings change. Unrelated edits preserve saved projections;
arbitrary supplied SQL remains rejected. Verified with 255 mocked backend tests,
28 frontend tests, TypeScript lint/build and `git diff --check`. Both local APIs
return `queryLocked=false` for job 2 after restart. Live Edit/Save regeneration
was not exercised in this creation/Run test; that path is covered by mocked tests.

No edits to `backend/query.brl`, SP definitions, schema or production data were
made. Job 1 was not edited or run during this test.

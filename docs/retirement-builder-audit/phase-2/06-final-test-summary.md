# Retirement Builder Phase 2 test summary

| Metric | Total |
| --- | --- |
| Features | 95 |
| Planned scenarios | 171 |
| Passed | 152 |
| Failed | 10 |
| Blocked | 1 |
| Not Tested | 8 |
| Confirmed bugs | 10 |
| Critical bugs | 0 |
| High-priority bugs | 6 |
| Feature coverage | 92/95 (96.8%) |
| Conclusive scenario execution | 162/171 (94.7%) |
| Calculation outcomes | 25 passed, 4 failed |
| Existing automated suites | 37 backend tests and 6 frontend tests passed |


Coverage percentage counts features with at least one conclusive executed test. The feature inventory breaks this down into 76 verified, 6 partially verified, 10 with a failed assertion and 3 with no conclusive run. [Coverage details](05-coverage-report.md)

## Verified behavior

Add/Edit and reload persisted the tested job configuration. Header/Detail/Trailer workbook mapping, compatible field formats, normalized sort priorities, numeric filters, subscription data and result-storage flags worked on the fixtures. Manual SQL-backed payroll and CSV generation, seven naming and grouping modes, five delimiters, exact download bytes, actual result row counts and rollback on an injected failure passed. Schedule recurrence, slot duplicate detection and scheduled attachment eligibility/merging passed with a controlled clock and loopback SMTP. [Test execution](01-test-execution-report.md) · [Calculations](03-calculation-test-results.md) · [API report](04-api-test-results.md)

## Defects and recommended Phase 3 order

| Order | Bug | Priority | Affected behavior |
| --- | --- | --- | --- |
| 1 | RET-B001 | P1 | Hidden selected job can still run or be edited |
| 2 | RET-B005 | P1 | Payroll filter saves a text operand and fails when run |
| 3 | RET-B009 | P1 | A partially configured schedule silently becomes manual-only |
| 4 | RET-B003 | P1 | Editing changes Last Run Date without execution |
| 5 | RET-B004 | P1 | Disabled job is unrecoverable from the standard UI |
| 6 | RET-B010 | P1 | Create retry can insert a duplicate across HTTP workers |
| 7 | RET-B006 | P2 | Edit detail failure produces no visible feedback |
| 8 | RET-B002 | P2 | Browser Back restores a canceled Add draft |
| 9 | RET-B008 | P2 | Tab skips nearby settings controls when a picker is open |
| 10 | RET-B007 | P2 | Run Time sort reverses midnight and early morning |


The first three items can trigger the wrong report, cause an accepted report configuration to fail, or cause a scheduled run to be missed. Complete those before a live demo that depends on job selection, payroll filters or scheduling. Verify historical status and disable/re-enable next. The duplicate-create issue has greater impact when multiple backend workers serve retries; move it earlier for a multiworker demo. [Reproduction steps, evidence and fix suggestions](02-bug-report.md)

## Remaining testing gaps

- [RET-T007](01-test-execution-report.md#ret-t007) — The 430 px wizard and modal were inspected and normal-size keyboard interactions ran in T079 and T094. The combination of browser zoom, a narrow viewport and a complete keyboard traversal was not executed.
- [RET-T010](01-test-execution-report.md#ret-t010) — Initial refresh, visible five-second polls, failure recovery and navigation away were observed. The hidden → visible transition and in-flight cancellation under that transition were not instrumented.
- [RET-T033](01-test-execution-report.md#ret-t033) — The four-step journey preserved values on Back and Next. The workbook load settled before the disabled Next state could be observed.
- [RET-T037](01-test-execution-report.md#ret-t037) — Add/Edit refresh and browser history ran under working storage. Storage denial, malformed stored state and same-tab draft contention were not injected.
- [RET-T054](01-test-execution-report.md#ret-t054) — Normal, invalid and replacement workbook imports ran. No deterministic overlapping file reads or Cancel during parsing were created.
- [RET-T080](01-test-execution-report.md#ret-t080) — Picker and custom search ran in other browser scenarios and partial catalog responses were observed at the API. Catalog removal of a selected value and loading/error UI together were not exercised.
- [RET-T082](01-test-execution-report.md#ret-t082) — Add/Edit initial rule directions and saved positive priorities were checked separately. Adding, saving and reopening two newly added rows in both modes was not completed.
- [RET-T114](01-test-execution-report.md#ret-t114) — Run and Edit error states and API validation/persistence errors were exercised. The complete set of injected create failures followed by retry through Finish was not run.
- [RET-T126](01-test-execution-report.md#ret-t126) — The duplicate employee-plus-month insert and NULL net salary update returned SQL integrity errors. These input rows cannot be represented with the existing UNIQUE and NOT NULL constraints. Normal-group counts and sums were verified in T124/T135 and C08/C09.

The next/back basic journey passed, but its in-progress import guard remains open. Import race handling and the multi-fault Finish recovery journey have no conclusive feature-level result. The real scheduled service cadence and external inbox delivery were outside the isolated test evidence.

## Change and cleanup verification

Changes are confined to audit documentation and evidence. Application code, existing SQL queries, existing database tables/schema, stored procedures and original local job/payroll data were left intact. Loopback SMTP received synthetic messages only. The temporary database was removed and temporary services were stopped. Original local row counts matched the starting snapshot, and the original dashboard still returned HTTP 200. [Cleanup evidence](evidence/cleanup.json) · [Backend suite](evidence/backend-suite.log) · [Frontend suite](evidence/frontend-suite.log)

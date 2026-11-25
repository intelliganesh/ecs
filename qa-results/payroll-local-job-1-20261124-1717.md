# Local Payroll Builder job 1 test — 24 November 2026

Final result: **Save passed; manual Run passed after an authorized local job-data
repair. CSV and Excel download checks passed. Mail remained disabled.**

## Scope and isolation

- Target: local `127.0.0.1:1433/ecs`, SQL Server `3fc1a6c70746`.
- UI/API: `http://127.0.0.1:5175` → `http://127.0.0.1:8001`.
- `MAIL_ENABLED=false`; both schedulers disabled by the local launcher.
- Exactly one new local payroll job was created. No production connection,
  production mutation, email delivery, scheduled execution or cleanup was used.

## Saved job

- ID: 1; filename: `Payroll_Local_QA_20261124_1717`; CSV with client-specific names.
- Schedule: November 25, 2026, weekly Wednesday, 4:00 AM (stored only).
- 55 Detail mappings; automatic headers; date and numeric formatting.
- Clients 901 and 902; placeholder recipient `payroll-qa@example.invalid`.
- Overtime wage mapping for client 901, `OTW`, earning code `O/T`.
- Grouping selections: Client ID and Pay Date. Saving these selections does not
  establish that the existing SP performs aggregation; no SP behavior was changed.
- Sort priorities: Pay Date, then Last Name.
- Conditions: Earnings > 0; Pay Date >= 2026-10-01; Employment Status = A.
- Store Results to Table OFF; Merge Files OFF.

## Initial Run and finding

The UI invoked `dbo.payrolljobbuilder` for job 1 with manual dates October 1–
November 30, 2026. The API returned HTTP 500 and recorded Failed status.
SQL Server reported error 209: ambiguous column name `RetNum`.

The generated Detail projection contains both the required metadata `retnum`
and the exported `[RetNum]` source field without a distinct output alias. The
existing SP appends `ORDER BY RetNum`, which becomes ambiguous. No files were
generated. The failed procedure attempt was rolled back before failure status
was committed.

## Corrections and clarified boundary

New Payroll Builder query generation now aliases metadata/duplicate source
collisions using the configured output labels. Existing saved queries are never
rewritten by this generator. Payroll condition reads also recover catalog data
types, so the saved date condition reopens as a date instead of text.

The user clarified that the query restriction applies to `backend/query.brl`,
while permitting local test-job data changes. Exactly one generated Detail
query in local `ecs.dbo.payroll_query`, for job 1, was repaired using the corrected
generator: the exported `[RetNum]` now has its configured `[Client Id in Prism]`
alias. H/T queries, Conditions and Sort_Order were preserved. No other job was
created or changed; no SP code, `query.brl`, schema or production data was changed
for this repair.

Verification confirmed:

- Before the clarified authorization, job 1's query rows matched the post-Save
  baseline. Before/after snapshots of the subsequently approved one-row repair
  are retained in the temporary evidence directory.
- Both local report SP definitions still exactly match their copied originals.
- The original SELECT reproduces error 209 in a read-only local test; the
  corrected in-memory projection succeeds against synthetic inline data.
- The date condition API type is `date`.
- 252 backend tests pass with real DB and SMTP connections prohibited.

## Successful retry and actual file checks

The same job was run again through the UI, for October 1–November 30, 2026.
The SP completed and the dashboard/history show Success: 12 Detail records,
0 application result-table rows, and email delivery disabled. This was a manual
Run; the stored schedule was not executed.

| Client | File | Detail rows | Columns |
| --- | --- | ---: | ---: |
| 000901 | Payroll_Local_QA_20261124_1717_000901.csv | 8 | 55 |
| 000902 | Payroll_Local_QA_20261124_1717_000902.csv | 4 | 55 |

- Every exported header matches its saved mapping label/order. Each file contains
  only its intended client's records.
- Actual file rows are ordered by Pay Date, then Last Name.
- Demo regular wages, regular/OT hours, overtime wages and base+OT+tips match
  fixture amounts for all 12 rows. Date and numeric formatting are correct.
- All exported records satisfy the configured conditions. These fixture records
  all qualify; this run does not independently establish exclusion behavior for
  every possible condition boundary.
- Both CSV download buttons were used; downloaded bytes match server files.
- Download Excel was used for client 000901. Its 8 data rows and 55 columns match
  the CSV cell values. Native Excel application behavior was not tested.
- Seven columns are blank in these files: Earnings +OT23, Deduction Code,
  Voucher Count, Address 2, YTD Gross Amount, YTD Hours and Location Name.
  These are limitations of the present fixture/SP output; they were not filled
  with invented values or addressed by changing SP logic. Thus 55 columns were
  exported, with 48 populated columns in this test.
- Both local report SP definitions still exactly match their original copies;
  Git reports no changes to `backend/query.brl` or existing SQL/config sources.

Server files are preserved under
`backend/report-output/local-demo/payroll/manual/1/566314c8-5f29-4722-adb2-f2d766c4d810/`.
The CSVs and client 000901 Excel download are also in the user's Downloads folder.
The UI remains available at `http://127.0.0.1:5175/payroll-builder`, backed by the
mail-disabled local API on port 8001. Source snapshots, one-row repair evidence,
file hashes and history are retained in the directory recorded by
`/tmp/ecs-payroll-local-run-path`. The original failed attempt evidence is retained.

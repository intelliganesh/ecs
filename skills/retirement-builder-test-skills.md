# Retirement Builder job 60 — reusable test workflow

Read the project-wide [AGENTS.md](../AGENTS.md) first. The rules below apply
only to an explicitly requested job 60 testing task; opening this guide does not
authorize Save/Run. A newer user instruction, including read-only analysis,
controls the scope. This is a project workflow document, not an installed Codex
skill.

## Scope and permitted actions

Automatic-header design note: with Include Header Row checked, the default
`RETIREMENT_HEADER_SOURCE=DETAIL_ALIGNED` uses confirmed D output order for labels
and field formatting. We chose D to prevent a separately ordered/stale H query
from placing the wrong label above a Detail value. Ambiguous associations fail
validation; aliases are not invented. Unchecked keeps configured H output.
`SAVED_H` restores H-result behavior after backend restart, without changing saved
H queries, DB data or the procedure contract.

- Test the existing **job 60 only** at
  `http://localhost:5174/retirement-builder`. Confirm the job ID before editing
  or running; its filename can change and is not a reliable identifier.
- When UI Save/Run testing is requested, normal UI edits, Finish/Save, and manual
  Run for job 60 are allowed. Do not ask again for permission already supplied.
- Do not create a new job, clone a job, delete a job, or modify/run another job.
- Perform mutations through the normal application UI only. Do not use SQL,
  scripts, API PUT/POST/DELETE calls, hidden browser state, or direct file edits
  to change job settings or restore them.
- Read-only code inspection, API GETs, logs, generated files and database SELECTs
  may be used to verify behavior. Do not invoke a report procedure as a
  supposedly read-only check: it may write data.
- A read-only task permits inspection and unsaved form exploration only. Do not
  click Finish/Save or Run in that mode.
- Excel workbooks are mapping-upload inputs in the user's normal workflow.
  Routine report QA checks the generated `.csv`, `.txt` and TAB `.tsv` files and
  their data. Do not verify generated Excel files, Download Excel, native Excel
  opening or configured Excel import unless the user explicitly requests those
  checks. See [the testing action notes](../action.md).

## Strict restrictions

1. Keep **`MAIL_ENABLED=false`**. Verify the effective backend setting before
   any Run, not just an unchecked assumption about `.env`. Do not enable mail or
   send test mail. If mail is enabled or its effective state cannot be verified,
   do not run; report the blocker. Do not edit configuration to bypass this rule.
2. Do not change production code, DB schema, stored procedures, existing SQL
   queries or `backend/query.brl`. Do not change DB values manually. Do not fix
   issues found during testing unless the user separately requests a fix.
3. Do not manually delete, truncate, clean up or reseed any database records.
   Normal authorized UI Save may internally replace related rows using the
   application's existing behavior; that is different from manual DB deletion.
   Save/Run can leave normal application history/log/run writes. Never claim
   that the entire database remained byte-for-byte unchanged after these actions.
4. Do not trigger the automatic scheduler or alter other jobs. Check for possible
   background execution before changing job 60's schedule. If an edit could cause
   an uncontrolled scheduled run and cannot be isolated within the authorized
   workflow, leave it unsaved and mark the live scenario blocked.
5. Keep **Store Results to Table OFF** during live Runs under the no-schema-change
   restriction: that path can create/drop result tables. Inspect or validate it
   without saving/running, or mark it blocked. If the fresh baseline is ON, do not
   run with it ON; preserve the baseline for restoration.
6. Preserve existing and newly generated report files and evidence.
   Do not delete them as cleanup. CSV uses `.csv`, TAB uses `.tsv`, and PIPE,
   SEMICOLON, TILDE and FIXED use `.txt`. Historical files may still use `.csv`;
   determine the actual format from content and configuration, not the extension.
7. Use `annagiri.raghunath@agilehealthtech.com` for temporary subscription test
   entries unless the user specifies otherwise. Mail still stays disabled.
8. Keep credentials and payroll/SSN data out of chat, screenshots shared in chat,
   and public locations. Keep detailed evidence local; report redacted examples.

## Baseline and restoration are mandatory

- Capture a **fresh baseline before the first mutation**. Do not restore settings
  copied from a previous test session, old screenshots or a sample payload.
- Capture General, Schedule, all mappings/datasets and their order, Include
  Header Row, all formats/defaults/positions/lengths, subscriptions/emails, Merge
  Files, sort priorities, conditions and saved query configuration.
- Use read-only snapshots and file hashes to establish which protected source,
  config/SQL files, other jobs and existing reports must remain unchanged.
- Restore all editable settings through the UI, even after a failed scenario,
  timeout or browser interruption. Reserve time for restoration. After a stop
  request, stop new scenarios and explain any restoration still required; follow
  the user's latest instruction if they prohibit further actions.
- Reopen job 60 and compare fresh API/SELECT snapshots with the baseline,
  including H/D/T queries. A successful Save toast alone does not prove restoration.
- Do not repair a restoration mismatch manually in the DB. Report any restoration
  failure clearly and identify the remaining differences.

## Evidence and completion rules

- Maintain a scenario checklist with **PASS, FAIL, BLOCKED, NOT TESTED** and
  evidence. A selected dropdown value, successful Save, successful Run and correct
  report content are four separate checks.
- Inspect the generated file for every completed Run. A 200 response or a
  “Generated rows” message does not prove correct data or mappings.
- Do not treat testing one Mapping Column or Format as testing all its options.
  Inventory live options and explicitly account for each applicable value.
- Test all **six File Formats** and **seven Output File Name Formats** when full
  coverage is requested. Do not call a representative subset exhaustive.
- Test single/multiple clients and verify report content for each client, not
  only dropdown selections or filenames.
- Record actual API network duration separately from UI observation/wait time.
  Never describe a coarse UI wait as precise PUT latency.
- List reproducible issues with expected/actual behavior, severity, scenario and
  evidence. Separate confirmed defects from suspicions and test-tool failures.
- Do not carry forward an old issue as a current failure without a fresh retest.
  A prior finding was that a Mapping Column edit persisted while the old D SELECT
  still supplied the export value; explicitly regression-test this behavior.
- Give progress updates and disclose blockers promptly. For a time limit, stop
  starting new scenarios early enough to restore and report. Do not promise that
  every combination fits ten minutes, or silently exceed the limit.
- Final reporting must identify completed and untested coverage, issues,
  generated-file results, effective mail-disabled status, restoration results,
  elapsed time, and local evidence/report links.

## Testing workflow

## 1. Establish a recoverable test session

1. Confirm the current task permits UI Save/Run for job 60. For read-only requests,
   limit the workflow to inspection/unsaved forms and label live tests NOT TESTED.
2. Check app/backend/DB reachability and effective `MAIL_ENABLED=false` without
   changing code, configuration, queries or DB state. Consider scheduler safety.
3. Record a fresh baseline as defined in the rules above. Note existing validation
   errors or unusual/legacy settings; do not silently normalize them.
4. Create a timestamped local evidence folder and a coverage checklist. Save
   baseline snapshots, screenshots and protected-file/report hashes there.
5. Inventory current dropdown values and operators from the UI/backend. Read code
   and `backend/query.brl` as needed to understand expectations; do not edit them.
   Compare expectations with the current procedure contract. Do not assume the
   configured production procedure behaves like an older reference file.
6. Choose data-backed date ranges and clients using read-only inspection. Record
   expected counts and independently verifiable values before running. Historical
   clients 204 and 719 are useful examples, not guaranteed future fixtures.

## 2. Coverage matrix

Track each option/scenario explicitly. Combine compatible cases to reduce Runs,
but do not claim all combinations were tested unless each has evidence.

| Area | Required scenarios and observable checks |
| --- | --- |
| General | Filename, description, File Format, Output File Name Format, enabled state and navigation. Verify saved values after reopening and dashboard refresh. Explore disabled-state behavior without losing access to job 60. |
| File Format | CSV, FIXED, PIPE, SEMICOLON, TAB, TILDE. Save, reopen, Run and inspect content for every format. Check raw stored value read-only and round-trip label consistency. |
| Output File Name Format | File Name; Client ID; Payday; File Name + Client ID; File Name + Payday; Client ID + Payday; File Name + Client ID + Payday. Verify names, client ID zero-padding, date source, grouping, file count and possible collisions with multiple clients/paydays. |
| Mapping Column | Inventory every live option. Exercise each applicable source against independently known values; verify Save/reopen, generated D query and exported data actually change. Include “Same as Field Name” and Default choices if offered. Do not count selecting an option alone as a pass. |
| Mapping Format | Inventory every live option from `rjobformat`/backend. Test suitable char/date/numeric/SSN fields, No format, LA/RA alignment, supported date masks, numeric masks, leading-zero SSNs, and unsupported value/type validation. Mark unavailable data fixtures BLOCKED rather than inventing data. |
| Mapping fields | Field Name, Start Position, Length, Default Value, record type, dataset number and column sequence. Check field order, blanks/defaults, min/max/invalid widths and non-overlap for FIXED. Use temporary UI edits only; never add a new job. Account for add/remove-row/dataset controls if included in the requested edit scope. |
| Headers/trailers | Include Header Row ON/OFF; configured H/D/T mappings; no H mapping; configured T and placeholder T. Verify output order and saved query behavior without inventing header/trailer business values. |
| Multiple datasets | Add Dataset creates another card; Add Row changes only that card and opens it. Verify independent collapse/expand controls and visible field counts while closed. Verify dynamic fields, repeated column names across datasets, Save/reopen identities, one D query per dataset, reversed/empty SP result sets, per-section headers and blank separators, all six file formats and seven filename choices with single/multiple clients. Reserved dataset metadata must never appear in exports. Match legacy results only with unique evidence. Verify ambiguous legacy layouts, Store Results ON, SAVED_H automatic headers and direct CSV Run uploads are rejected safely. Use isolated mocks for SP outcomes when live Run is not authorized. |
| Sorting | One and multiple priorities 1,2,3; reordered priorities; missing/duplicate/invalid priorities; removing/clearing rules. Verify save/reopen and actual multi-key output order, including tied keys. The UI label is Order By; numbers represent priority, not ASC/DESC direction. |
| Conditions | Every offered comparison operator with valid string/number/date values; multiple rules; boundary matches; no-match results; edit/reopen; remove/clear; blank/incomplete/invalid rules. Confirm actual row inclusion/exclusion and saved Conditions; identify how multiple rules combine from current code. |
| Subscriptions | One client; multiple distinct clients; same email for multiple clients; multiple email tags if supported; invalid/empty/duplicate inputs; changing/removing temporary rows. Verify each client's output is correct with no data leakage or unintended duplicates. |
| Merge Files | ON/OFF Save/reopen and generated-report behavior. Actual email delivery/attachment merging is BLOCKED while mail is disabled; do not mark SMTP behavior passed. |
| Manual Run | Select job 60 only; date modal appears; populated, blank/sentinel, invalid, reversed, boundary and no-data ranges as applicable. Verify confirmed Run payload, procedure arguments, status, download links and error handling. Validate no-selection behavior without running other jobs. |
| Schedule | Inspect and test unsaved/authorized safe edits for start date, frequency, time, weekday and conditional schedule fields. Verify displayed DB time is not unexpectedly shifted. Verify scheduled parameter/run-type contracts by read-only code/log evidence; no automatic trigger unless separately authorized. |
| Other controls | Edit/navigation/Cancel, File Settings Save & Continue/Clear/Cancel, mapping template/download/import controls where requested. Use unsaved forms for create-only behavior. Do not save a new job. |
| Performance | Measure dashboard GET frequency, edit load, PUT Save and Run timings. Record request duration/status/payload size separately from total UI time. Do not add tracing code or change queries. |

Every applicable live Mapping Column and Format must have its own checklist row.
When a value cannot be safely exercised with job 60's existing data/configuration,
document why. Incompatible field/format pairings should produce validation, not be
reported as successful export coverage. Store Results to Table live execution is
blocked by the no-schema-change rule.

## 3. Execute each scenario through the UI

1. Start from the recorded baseline or explicitly documented previous state.
   Make controlled changes and record exactly what changed.
2. Exercise validation without submitting an unintended valid mutation. Capture
   errors and expected behavior; do not “fix” application validation code.
3. Click Finish once. Capture the actual request/response and timing when
   available. Avoid duplicate Save/Run clicks while an operation is pending.
4. Reopen and verify persistence, selected labels, file settings, subscriptions
   and dashboard values. Read saved query rows as needed.
5. Select only job 60 and open manual Run. Set the scenario's dates and confirm
   the job/date payload. Verify mail remains disabled before execution.
6. Capture Run status, run ID, file links, filenames and row counts. Preserve all
   generated files. Inspect every output as described below.
7. Record PASS/FAIL with evidence. If Run is unsafe or blocked, retain separate
   Save/reopen results and mark Run/content verification BLOCKED.

## 4. Inspect actual reports and query behavior

### Serialization and file naming

The selected File Format determines the filename extension without changing the
content. Use this required matrix; record each format separately:

| File Format | Expected extension | Expected content |
| --- | --- | --- |
| CSV / COMMA | `.csv` | Comma-separated, quote-aware fields |
| PIPE | `.txt` | Pipe-separated fields (`\|`) |
| SEMICOLON | `.txt` | Semicolon-separated fields (`;`) |
| TAB | `.tsv` | Actual U+0009 tab-separated fields |
| TILDE | `.txt` | Tilde-separated fields (`~`) |
| FIXED | `.txt` | Configured field positions, lengths and padding |

For **each** format, verify the generated filename/extension, download link and
downloaded bytes, readability/encoding, field positions/order, headers and data,
blank middle/trailing fields, special characters, leading zeros, numeric precision
and date formatting. Do not count selecting/saving the format as file coverage.

- Exercise all seven Output File Name Format choices in the coverage matrix.
  Check single/multiple-client filenames, client/date components, grouping and
  counts; preserve the same components across extensions. Cover merged names and
  collision suffixes without overwriting another report. Check that replacing a
  supported final suffix does not produce `.csv.txt` or `.tsv.xlsx` names.
- Preserve historical `.csv` reports and verify existing access/download behavior
  where available; do not rename them. The change does not migrate old reports.
- CSV uses comma, PIPE `|`, SEMICOLON `;`, TAB actual U+0009, and TILDE `~`.
  Parse each with its selected delimiter using a proper quote-aware parser.
- FIXED has no separator. Recover fields using configured positions/lengths;
  verify padding, alignment, record width, overlaps, overflow and header widths.
  Do not split FIXED on arbitrary spaces or assume one space between fields.
  Verify a 189-character layout when that is the configured scenario; do not
  change a job's field widths merely to force that historical fixture.
- Confirm headers and data follow the same layout and field order. Check embedded
  commas/quotes, intentional spaces, blank middle/trailing values, Unicode if
  present and consistent column counts. Consecutive delimiters can correctly
  represent empty fields; check parsed positions before declaring a defect.
- Validate formatting after parsing: date masks, SSN leading zeros/masks,
  precision/rounding, defaults, names without added literal quote wrappers, and
  LA/RA/width behavior. Do not remove legitimate CSV quoting in expected results.
- Verify filename components and grouping independently. Client ID is not job ID.
  Do not infer file count solely from the number of subscription rows.

### Downloads, attachments and completion detection

- Normal Download Report must use the backend filename, including `.csv`, `.txt`
  or `.tsv`, with unchanged report content. Check MIME metadata: `text/csv`,
  `text/plain` and `text/tab-separated-values`, respectively, with UTF-8 encoding.
  Historical FIXED output with structured fields keeps `text/plain` metadata.
- Inspect attachment names/MIME/content through code or isolated mocked SMTP
  tests when authorized. Cover individual and merged attachments for all six
  formats. Actual delivery and recipient-specific live merging remain BLOCKED
  while `MAIL_ENABLED=false`; never enable mail to satisfy this checklist.
- Verify scheduler completion detection accepts existing `.csv`, `.txt`, `.tsv`
  reports and `.complete`, including historical `.csv`, preventing a duplicate
  completed-slot attempt. Use source inspection, existing evidence or isolated
  mocks only; do not trigger the automatic scheduler or create completion files
  in actual report folders.
- This matrix grants no additional Save/Run, database-write, mail or scheduler
  permission. A prohibition on all DB writes means no UI Save/Run either; normal
  application writes are permitted only within the task's explicit UI scope.
  If a live case needs new source records or unsafe changes, mark it BLOCKED;
  do not seed data or bypass the restrictions.

### Text report validation and Excel scope

The default report deliverables under test are **`.csv`, `.txt` and `.tsv`**.
Inspect their actual bytes and data using the configured delimiter or FIXED
positions/lengths. Verify columns, row counts, headers/trailers, source accuracy,
sorting, conditions, blanks, quotes, Unicode, leading zeros, dates and numeric
precision. These checks do not require Microsoft Excel.

Excel `.xlsx`/`.xls` files are used to **upload mapping columns**, not as the
report-delivery target for this testing workflow. Test workbook import controls
and the resulting mappings only within the authorized job 60 scope. Do not
confuse a mapping-upload workbook with a generated report.

Do not open Microsoft Excel, set up an add-in, test Text to Columns/configured
import, or verify the optional Download Excel output during routine report QA.
The existence of that button does not expand the user's requested test scope.
Do not mark text-report testing BLOCKED or FAIL because Excel is unavailable.
Leave existing Excel functionality unchanged.

Only if the user **explicitly asks for Excel compatibility testing**, assess it
separately from text-file correctness. In that case, distinguish direct Excel
opening, configured import and downloaded `.xlsx` behavior, and do not claim a
native Excel PASS from programmatic parsing or file generation alone. Otherwise
record Excel output/native checks as **OUT OF SCOPE**, not pending requirements.

### Existing automated evidence

Review current source and tests before relying on prior results:
[extension regressions](../backend/tests/test_report_extensions.py),
[serialization tests](../backend/tests/test_retirement_results.py),
[procedure-output tests](../backend/tests/test_retirement_procedure.py) and
[frontend helpers](../frontend/tests/retirementBuilder.test.mjs).

The extension implementation previously reported **142 backend tests, 18
frontend tests, lint and build passing**. These are historical results, not tests
executed for this documentation update. Live UI downloads, actual email delivery
and live scheduled execution were not tested. Mocked attachment/completion checks
and file parsing do not establish those live outcomes or native Excel behavior.
Run tests only when the current task authorizes them and dependencies are safely
isolated; reading this evidence does not authorize a new test execution.

### Source data and queries

- Compare client/date membership, counts, selected source values, sorting and
  conditions against an independent read-only source sample or snapshot. Avoid a
  circular check that merely reruns the same export logic to obtain expectations.
- A Mapping Column change must change the corresponding exported source value.
  Matching the old D SELECT is not a pass for the changed mapping. Regression-test
  the previously observed stale-D-query issue without assuming it still exists.
- Verify new/regenerated record types are H/D/T; do not migrate legacy values.
  Inspect `rjob_file_detail` and `rjob_query` without manual edits. Check query
  duplication and whether existing rows update correctly through normal Save.
- Include Header Row ON should derive literal headers from ordered D field names.
  OFF should use configured H mappings if present; do not invent a missing H row.
  Verify DataSetNo/ColSeqNo ordering and current configured formatting behavior.
- A placeholder T query returning only control fields is not a totals trailer;
  do not require an empty business row in the report. Check configured T content
  when present and within the authorized test scope.
- Sort priority is stored in `rjob_file_sorting_details.sort_order`; verify actual
  priority and mapping names. Inspect `rjob_query.Sort_Order` for the ordered
  column-list fragment expected by the current procedure, rather than assuming
  the values 1/2 mean ASC/DESC or adding SQL keywords to the stored fragment.
- Check the current procedure is called with job ID, start date and end date.
  Manual dates should come from the modal; unset/manual sentinel and scheduled
  dates should follow the agreed 1900-01-01 contract. Verify runType A for manual
  and S for scheduled from current code/payloads/logs; report any mismatch instead
  of treating the desired contract as verified fact. Do not run the scheduler.

## 5. Restore and report

Restore the fresh baseline through the UI. Reopen and compare all editable
sections, saved queries and relevant related rows with the baseline. Verify
protected files/other jobs and pre-existing reports remain unchanged. Record
normal authorized run-history/log effects separately; do not delete them.

Deliver a concise report containing:

- Coverage matrix and counts, including each of the six/seven dropdown choices.
- Each scenario's changed values, client/date range, Save/reopen result, Run ID,
  filenames/counts and generated-file/source comparison result.
- Confirmed issues: severity, reproducible steps, expected versus actual, evidence
  and code location if established. Do not fix during testing.
- Performance measurements with their measurement method and limitations.
- NOT TESTED/BLOCKED scenarios and reasons, including remaining option combinations.
- Mail-disabled evidence, restoration comparison, preserved report paths and any
  unresolved settings differences. Do not claim completion while restoration is
  unverified. Include elapsed time and disclose any exceeded time limit.

## Reusable request

> Read the root AGENTS.md and skills/retirement-builder-test-skills.md. Test Retirement
> Builder edit and manual Run flows for existing job 60 only. UI Save/Run is
> allowed; no new job, code changes, manual DB mutations, schema/SP changes or
> existing query changes. Keep MAIL_ENABLED=false and send no mail. Cover all six
> File Formats, all seven Output File Name Formats, applicable Mapping Columns
> and Formats, field/default/width edits, headers/trailers, multiple sort
> priorities and conditions, and single/multiple clients. Inspect every generated
> file and verify source data. List issues without fixing them. Preserve reports.
> Excel workbooks are mapping-upload inputs only; validate generated .csv, .txt
> and .tsv reports and their data. Do not test generated Excel files or native
> Excel unless separately requested.
> Capture a fresh baseline and restore/verify original settings afterward. Mark
> untested or blocked scenarios honestly. If time-limited, reserve restoration
> time and report remaining coverage instead of claiming everything was tested.

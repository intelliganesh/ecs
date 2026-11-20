# Retirement Builder – UI Edit & Run Test (Job 60)

Scope: Job 60 (`DEMO_999999_1`) only, through the UI (Edit → Save → reopen → Run → inspect generated files).
Run date range: 10/10/2026 – 17/10/2026. Clients on the job: 204 and 719.
Mail: `MAIL_ENABLED=false`; UI banner on every run said "Email delivery is disabled."
No code, DB rows, tables or other jobs were touched. No jobs were created or deleted.
Job 60 was restored to its original values through the UI; a field-by-field diff against the pre-test snapshot showed 0 differences (including stored queries).
Generated files live in `backend/report-output/manual/60/<runId>/` (22 manual runs by this session).

## Scenarios executed (report data verified, not just screen behaviour)

| # | Settings | Result |
|---|----------|--------|
| 1 | TAB + File Name, 2 clients, Merge off (baseline) | 1 file, 198 data rows – see B3/B4/B5 |
| 2 | PIPE + Client ID + Payday | 3 files (204/10-15, 719/10-13, 719/10-14), 198 rows total, delimiter correct |
| 3 | CSV + File Name + Client ID | 2 files, names with commas correctly quoted |
| 4 | FIXED + Payday (start/length set for all 8 rows) | 3 files – **FAIL, see B2** |
| 5 | SEMICOLON + File Name + Payday | 3 files, correct |
| 6 | TILDE + Client ID | 2 files, correct |
| 7 | TAB + File Name + Client ID + Payday | 3 files, correct |
| 8 | Same as 7 with Merge Files ON | identical output to Merge OFF – see B3 |
| 9 | Merge ON + File Name | byte-identical to scenario 1 (199 lines, 18787 bytes) |
| 10 | Single client (204 only) + File Name + Client ID | 1 file, 71 rows, identical to the 204 file from the multi-client run |
| 11 | Header off, PAYDATE → CCYYMMDD, WORK PHONE column → Last Name (RA) | header and date format applied; column change **ignored** – see B1 |
| 12 | Sort 1 = paydate, 2 = SSN; condition YTD Eligible earnings >= 100000 | PASS: 8 rows, min value 110039, SSN ascending; stored `WHERE [ytd_ret_elig_earn] >= 100000.00`, sort `, paydate, ssn` |

All 6 File Format options and all 7 Output File Name Format options were exercised at least once.

## Bugs

### High

**B1 – Changing a Mapping Column (and likely Default Value) has no effect on the report.**
Steps: Mapping tab → WORK PHONE → Mapping Column = Last Name → Finish → reopen (shows Last Name, API returns `lastname`) → Run.
Expected: column 2 contains last names. Actual: column 2 still contains the phone number (`7166811600`).
Cause: `export_record_queries` in `backend/app/retirement_query_builder.py` keeps the saved Detail query's SELECT list when one exists ("Keep the SELECT/aliases intact"), so the mapping rows are saved but the SQL is not regenerated. Stored D query still selects `workphone as "CWORKPHONE"`. Header on/off and date format still work because they are applied outside the SELECT. Default Value was not run-tested; by the same code path it is likely ignored too.

**B2 – FIXED file format does not produce a fixed-width file.**
Output is space-separated with CSV-style quotes (`PAYDATE "WORK PHONE" LASTNAME ...`) and ignores Start Position and Length (no padding, no truncation). The UI forces valid Length 1–1000 for FIXED, so users believe they are configuring widths.

**B3 – "Merge Files" checkbox has no effect.**
Merge ON and OFF give byte-identical output with the same Output File Name Format, both with File Name (single combined file) and with Client ID formats (split per client). Merge also stays ticked and enabled after removing the second client.

**B4 – Combined file is not globally sorted by Sort Priority 1.**
With File Name format and 2 clients the single file is ordered 71 rows of 10/15, then 1 row of 10/13, then 126 rows of 10/14 (sort = paydate ASC). Each client is sorted separately and then concatenated.

### Medium

**B5 – Output extension is always `.csv`** for TAB, PIPE, TILDE, SEMICOLON and FIXED (e.g. `DEMO_999999_1.csv` containing tabs).

**B6 – Row count in the result banner includes header lines.** Baseline: "Generated 199 rows" for 198 data rows; 3-file run: "Generated 201 rows" for 198 data rows. Also "Saved 0 rows" wording when Store Results is off.

**B7 – File Settings dialog inconsistency.** A saved sort column displays the raw key (`paydate`, `ssn`) after reopening, while a newly added one shows the label ("Social Security Number"). API stores sort columns as keys but condition columns as labels (`YTD Eligible earnings`).

**B8 – Save is slow with no feedback.** Finish takes roughly 7–10 s (PUT pending >6 s every time) with no spinner or success message; users can double-click or navigate away.

**B9 – No sort-direction control.** API supports ASC/DESC but the File Settings dialog only has Order By + Mapping Column, so DESC cannot be set from the UI (confirm whether intended).

### Low

- **B10** Edit page loads in stages: Output File Name Format briefly shows "Select Format"; client dropdowns show raw `204` before the label ("000204 – Kulback's, Inc.") loads. The first jobs-list fetch is also aborted/duplicated and the grid is empty for a moment after login.
- **B11** New subscription row's Client dropdown placeholder reads "Select Format" instead of "Select client".
- **B12** Deleting a subscription row has no confirmation.
- **B13** Condition value is rewritten on save (`100000` → `100000.00`).
- **B14** Run result banner pushes the grid down, shifting the Edit/row click targets after every run.
- **B15** Output values keep trailing spaces (`"Anstett, Arthur "`) from the source name column.
- **B16** Jobs API returns `filetype` as a raw tab character for TAB jobs; check how the File Type column renders it.
- **B17** Job 60's original mappings look inconsistent (field `LASTNAME` → ssn, `FIRSTNAME` → formatted name, `OFFICER YES/NO` → last hire date). Likely data, related to B1; confirm with the job owner.
- **B18** Filenames zero-pad client IDs to six digits (`000204`); confirm this is intended.
- **B19 (unconfirmed)** After rapid wizard navigation the stepper once highlighted step 1 while showing the Subscriptions page; could not reproduce.

## Not covered in this pass
Validation matrix (duplicate/blank/zero/negative/fractional priorities, invalid condition values), operators other than `>=`, Cancel behaviour mid-edit, Store Results to Table, Browse Files import, Template download, Header/Trailer record types, Default Value effect, schedule fields, empty-result runs, Company Payroll report source. The earlier agency test already listed several of these as passing.

## Fix status (code-only; no DB, data or stored-query changes)

| Bug | Status |
|-----|--------|
| B2 FIXED not fixed-width | **Fixed** in `_execute_report_run` (`retirement_builder.py`): the run path read the raw stored filetype (a space), which was not recognised as FIXED. It now maps it back to the configured name in memory. Regression test `FixedRunFormatTests` fails without the fix. |
| B3 Merge Files | **Correction – not a functional bug.** `Merge Files` only merges emailed attachments (`report_mail.py:78`), and email is disabled, so no file difference is expected. UI label now says "(emailed attachments only)". |
| B7 sort column shows raw key | **Fixed** in `FileSettingsModal` (`App.tsx`): saved sort columns now display labels like newly added rows. |
| B11 "Select Format" on client dropdown | **Fixed** (`placeholder` prop; "Select client" / "Select company"). |
| B1 mapping column ignored | **Not fixed, needs a decision.** The only fix rewrites the stored Detail query in `rjob_query` when a user edits a mapping column, which conflicts with "existing queries must remain unchanged". |
| B4, B15, B17, B18 and the SP defects | Left as is (SP/data side). |
| B5 `.csv` extension, B6 row count, B8–B10, B12–B14, B16, B19 | Left as is (behaviour/product decisions or low priority). |

**B2 verified in the running app:** job 60 saved as FIXED and run for 10/10–17/10. First attempt was rejected with "Column 'HIGHLY COMPENSATED' exceeds its FIXED length of 12 characters." (correct: the header field name is 18 characters), proving FIXED is now enforced. After widening three columns the run succeeded: 199 lines, all exactly 151 characters, no quotes, no tabs, columns aligned. Job 60 was then restored through the UI (0 differences vs the original snapshot).

New observations from this check (not fixed):
- **Start Position is zero-based in the code** (`fixed_layout`): Start Position `1` puts the field at the second character, so a 1-based user gets a leading space. Confirm the intended base and label it in the UI.
- The UI accepts FIXED lengths shorter than the header field names; the problem only appears at run time (the error message itself is clear).

## Root-cause analysis against `dbo.rjobbuilder` (read-only, code reading only – nothing executed)

| Bug | Where it comes from | Why |
|-----|---------------------|-----|
| B1 mapping column ignored | **App (+SP design)** | The SP runs the stored `rjob_query` D text verbatim: `@sqlstmt + ' from #ret_builder_info ' + @sqlcon + ' order by RetNum' + @sqlord`. It never reads the mapping rows, so only a regenerated D query can change columns. The app keeps the old D query (`export_record_queries`). |
| B2 FIXED not fixed-width | App | The SP returns raw column values; all padding/width logic is in Python. |
| B3 Merge Files no effect | App | The SP has no merge concept. It always returns every subscribed client in one result set; splitting into files is done by the app from the filename format. |
| B4 not globally sorted | **SP** | Hard-coded `order by RetNum` comes before the user's sort (`@sqlord` = `, paydate, ssn`). Effective order is RetNum → paydate → ssn, which exactly matches the output (client 204's 10/15 rows, then client 719's 10/13 and 10/14). The app keeps the SP order when it writes one combined file. |
| B5 `.csv` extension, B6 row count | App | The SP does not name files or count rows. |
| B15 trailing space in names | **SP** | `emp_formatted_name = '"'+last+', '+first+' '+case when len(middle)>0 then middle else '' end+'"'` leaves a trailing space when there is no middle initial. |
| B18 `000204` | SP/data | `RetNum` is Prism `Client_ID` (`'000'+jobclientid`), already zero-padded. |
| B17 odd mappings | Data + SP naming | `workphone` in the SP is the *client's* phone (`client_details.client_phone_no`), identical on every row of a client. `Highly_Comp`, `Officer_YD`, `PERCENT_OWNERSHIP` (hard-coded 0) exist as columns, but job 60 maps those headers to `ytd_ret_elig_earn`, `formatted_phone` and `last_hire_date`. |

### Additional defects spotted in the SP (not reproduced; job 60 is Weekly and was run manually)
1. **Wrong database in the scheduled Daily branch:** `syd.dbo.rjob_schedule_info` while every other branch uses `syd_testing.dbo.rjob_schedule_info`. All `syd_testing.` names are hard-coded.
2. **Monthly schedule dates are broken:** start is the 1st of the *current* month, end is built from `month(getdate())-1` with a day of 28 or 30. This gives start after end, a month of 12 when run in February, month 0 in January, and ignores the 31st and leap years.
3. **Manual run on a Bi-Weekly job writes state:** the Bi-Weekly block runs before the `@runtype='A'` override, with `@startdate` still NULL. When `rjob.enddate` is the 1900 default it executes `update rjob set enddate=@startdate` and sets `enddate` to NULL.
4. **Hard-coded year:** `ytdGross` uses `u2_id like '%2026'` and `2026 ytdyear`. `ytd_ret_elig_earn` uses `year(getdate())` instead of the pay-date year.
5. **Loan data can attach to the wrong client:** the loan update joins on EE_ID and pay date only (`--and info.retnum=ld1.clientid` is commented out). In a multi-client job such as 204 + 719, an EE_ID shared by two clients mixes the loan columns.
6. **Trailer totals only cover 4 legacy filename formats:** `File Name`, `-PayDate`, `-ClientId`, `-ClientId-PayDate`. The app also offers Client ID, Payday and Client ID + Payday without a File Name, which match none of the branches, so `file_total_*` stay NULL.
7. **NULL concatenation:** if `Conditions` or `Sort_Order` is NULL for a D row, `@sqlstmt + ... + @sqlord` is NULL and `exec(NULL)` returns no detail rows with no error.
8. **Store Results drops the output table first:** `drop table [<jobfilename>]` runs before any data check, so a run with no data still drops it. `jobfilename` is concatenated into dynamic SQL; a name containing `]` would break out of the brackets.
9. **Hard-coded job id:** `@client_id=98` is baked into the employee filter.

## Round 3 – app-side fixes (code only; no SP, SQL, stored-query or DB changes)

| ID | Fix | Verified |
|----|-----|----------|
| B5 | **Withdrawn – business rule.** The export file is always `.csv` whatever the delimiter or FIXED layout. An earlier change to `.txt` was reverted; `OutputExtensionTests` now locks the rule in. | Unit test |
| B6 | Banner and run message count Detail rows only | App: "Generated 197 rows" |
| N1 | Procedure path now applies number masks, RA/LA padding, text formats and Default Value; a value already formatted by SQL is left as returned | App: RA 12, `N/A`, `$44475.73` |
| N2 | Header/trailer rows only for pay dates that still have Detail rows | App: client 719 file has 1 trailer (was 2) |
| B16 | Jobs list `filetype` shows the format name | Unit test |
| – | FIXED length shorter than its header name is rejected on save | Unit test |
| N7 | File Name rejects `\ / : * ? " < > |` and control characters (backend and frontend) | App |
| N3 | RA/LA are selectable for number and date columns, so a saved `LA` survives a column change | App: restored job 60 HC `LA` |
| N4 | AM/PM, Hour, Minute use placeholders instead of a selectable "AM/PM" entry; API list order kept | App |
| N5 | Enable label no longer flips to "Disable" | App |
| N6 | First invalid field scrolled into view | App |
| B8 | Finish button shows "Saving…" while the slow save runs (server speed unchanged) | App |
| N8 | "+" icon tooltip says it opens File Settings | Code |
| – | Start Position header tooltip: zero-based, FIXED only | Code |

**Not changed (by instruction or because the fix would touch SQL):** B1/B17 (stored Detail query), B4/B15/B18 and all SP issues, B9 DESC (needs the stored sort text), B13 (numeric DB column returns `100000.00`), B10/B12/B14 (cosmetic, not done).

**B17 test on job 60:** corrected LASTNAME → Last Name, FIRSTNAME → First Name, HIGHLY COMPENSATED → Employee Highly Compensated, OFFICER → Is Officer. All saved correctly, but the report did not change (still SSN / hire date), confirming that mapping columns only take effect through the stored query (B1). Original values restored; 0 differences.

## Round 2 retest (after fixes) – consolidated issue list

Scope: job 60 only, via UI. 5 edit/run cycles (CSV, PIPE, TILDE, FIXED multi-client, structure change), plus validation, Cancel, schedule, Merge, email, Description/File Name edits and run-dialog date cases. No code, DB or query changes in this round. Job 60 restored; the only remaining difference from the original is HIGHLY COMPENSATED format `LA` → blank (see N3).

**Open – High**
- B1 Mapping Column change ignored (reconfirmed: FIRSTNAME → Last Name still outputs the formatted name).
- N1 Only date formats and the SSN mask are applied to non-FIXED output. `$######.##` leaves `67500.00`; RA width 12 on WORK PHONE leaves 10 digits; Default Value `N/A` leaves blank emails blank.
- B4 Combined single file is not globally sorted by Sort Priority 1 (SP `order by RetNum` first).

**Open – Medium**
- N2 Trailer rows are emitted for pay dates whose detail rows were all removed by a condition (client 719 file got 2 trailer rows, one for 10/13).
- B5 Extension is always `.csv` for every file format.
- B6 Row count in the banner includes header/trailer lines (199, 201, 202).
- B8 Save takes ~7–10 s with no spinner or confirmation.
- B9 No sort-direction (DESC) control in the UI.
- N3 A saved format that the UI cannot re-select: job 60 had `LA` on a number column. Changing the mapping column silently resets the format to blank, and the number-column list offers no LA, so it cannot be restored from the UI.
- N4 Schedule meridiem dropdown lists "AM/PM" as selectable; typing "PM" selects the placeholder and clears the value. The list also puts the selected value first (PM above AM).
- N5 Unticked Enable shows the label "Disable"; the list shows enabled jobs only, so a disabled job disappears from the list (not saved or tested, to avoid losing access).
- N6 Validation errors above the fold are not scrolled into view (blank File Name).

**Open – Low**
- N7 File Name accepts `bad/name:*?.csv` in the wizard (server-side result not tested).
- N8 The "+" icon next to the gear opens File Settings, not "add mapping row" (Add Dataset adds the row).
- N9 Empty-range run takes ~15–20 s.
- B10 load-order flashes, B12 no delete confirmation, B13 condition value rewritten (`100000` → `100000.00`), B14 result banner shifts the grid, B15 trailing spaces (SP), B16 raw delimiter in `filetype` (API), B17 odd job 60 mappings, B18 six-digit client IDs, zero-based Start Position, FIXED lengths shorter than header names accepted on save.

**Fixed in code (verified)** B2 FIXED output; B7 sort labels; B3 label ("emailed attachments only"). B11 placeholder fixed but not re-checked visually.

**Passed** all 6 file formats and 7 filename formats; per-client/per-payday splitting; date, SSN mask, header on/off, Trailer mapping, sort + date condition, date-range run (10/14–10/15), empty range message, start-after-end validation, priority validation (duplicate/0/-1/1.5/blank), incomplete/invalid/blank condition validation, invalid email, Cancel (no leakage), schedule save/reopen, Merge on/off (email only), FIXED multi-client with RA/LA.


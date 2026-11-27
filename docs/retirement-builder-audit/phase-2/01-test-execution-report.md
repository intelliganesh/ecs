# Retirement Builder Phase 2 test execution

## Scope and environment

The original [Retirement Builder dashboard](http://localhost:5174/retirement-builder) responded HTTP 200. Its options endpoint exposed five file formats, seven filename formats, 35 CSV mapping entries and five payroll mapping entries. The tested flows match the audited six routed screens and File Settings modal. Demo sign-in and the shell are entry prerequisites. Health endpoints are included as runtime dependencies. Other sidebar modules are outside this audit.

The original application remained available. Write tests used a second browser instance on port 5184, SQL-backed API processes on 8084 and 8086, and a fault-only instance on 8085. The isolated SQL Server database cloned the necessary structure and constraints, copied only lookup catalogs and loaded synthetic payroll. An existing disabled job, a payroll job, a four-group CSV job, a future schedule, a missing-source job and a zero-result job were prepared for browser testing. Normal API and browser instances had mail and scheduler disabled so that controlled tests owned all triggers. The scheduler was tested at fixed times against isolated SQL Server, and SMTP used local-only SSL and STARTTLS capture with synthetic addresses.

Browser layouts were checked at 1280 × 720, 768 × 900, 767 × 900, 520 × 820 and 430 × 850. Source files and report outputs used scratch folders. Screenshots and request logs contain synthetic job data. The synthetic workbook has seven H/D/T mapping rows. [Fixture workbook](evidence/7-mappings.xlsx) · [Environment and synthetic payroll](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/environment.json) · [Browser request trace](evidence/browser-http.ndjson)

Two companies were used: Audit Alpha (ID 1, employees A1/A2) and Audit Beta (ID 2, employee B1). September/October payroll net amounts were A1 100/115, A2 200/210 and B1 180/320. CSV grouping used client IDs 1 and 2 over September 1 and October 1, 2026. All addresses used the reserved example.invalid domain. For fixture-based checks, recorded data overrides the common fixture where stated.

**Audit discrepancies.** T126 requests duplicate employee/month and NULL net salary fixture data that the real schema rules prevent. T015 distinguishes natural ordering as implemented from chronological ordering expected by the UI. The Phase 1 definitions remain as written. The existing coverage matrix records execution status only.

**Reading outcomes.** A PASS requires a verified executable result. A FAIL records an observed mismatch. BLOCKED identifies a test precondition the current schema prevents. NOT TESTED includes partial exercises whose remaining planned variants did not run. The evidence can include narrowly scoped SQL seed/verification steps, HTTP fault injection, or direct calls to scheduler/mail business logic with a controlled clock. Inconclusive runner attempts are omitted from the scenario tables and retained in the raw log where useful.

## Scenario results

### RET-T001

**RET-F001 · Entry · Sign-in route guard · PASS**

**Scenario** — Open a protected route without the demo session; confirm redirect, sign-in and dashboard landing.

**Preconditions** — Isolated browser session with demo sign-in available.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Fresh session; synthetic demo credentials redacted; blank, incorrect, malformed, case-altered and padded uppercase account variants. | Visit protected route, exercise four invalid variants, then sign in with padded uppercase demo email. | Redirect to login, four rejections, accepted login opens dashboard. | {"entry": [{"variant": "blank", "path": "/login", "emailValid": true, "error": true}, {"variant": "wrong password", "path": "/login", "emailValid": true, "error": true}, {"variant": "malformed email", "path": "/login", "emailValid": false, "error": false}, {"variant": "changed password case", "path": "/login", "emailValid": true, "error": true}], "landing": "/retirement-builder"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:2) | — |



### RET-T002

**RET-F002 · Entry · Demo credentials and error · PASS**

**Scenario** — Submit accepted demo inputs, blank email/password, wrong password and invalid email syntax; verify route and error handling.

**Preconditions** — Isolated browser session with demo sign-in available.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Fresh session; synthetic demo credentials redacted; blank, incorrect, malformed, case-altered and padded uppercase account variants. | Visit protected route, exercise four invalid variants, then sign in with padded uppercase demo email. | Redirect to login, four rejections, accepted login opens dashboard. | {"entry": [{"variant": "blank", "path": "/login", "emailValid": true, "error": true}, {"variant": "wrong password", "path": "/login", "emailValid": true, "error": true}, {"variant": "malformed email", "path": "/login", "emailValid": false, "error": false}, {"variant": "changed password case", "path": "/login", "emailValid": true, "error": true}], "landing": "/retirement-builder"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:3) | — |



### RET-T003

**RET-F002 · Entry · Demo credentials and error · PASS**

**Scenario** — Use different email case and leading/trailing spaces with the exact password, then case-altered password.

**Preconditions** — Isolated browser session with demo sign-in available.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Fresh session; synthetic demo credentials redacted; blank, incorrect, malformed, case-altered and padded uppercase account variants. | Visit protected route, exercise four invalid variants, then sign in with padded uppercase demo email. | Redirect to login, four rejections, accepted login opens dashboard. | {"entry": [{"variant": "blank", "path": "/login", "emailValid": true, "error": true}, {"variant": "wrong password", "path": "/login", "emailValid": true, "error": true}, {"variant": "malformed email", "path": "/login", "emailValid": false, "error": false}, {"variant": "changed password case", "path": "/login", "emailValid": true, "error": true}], "landing": "/retirement-builder"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:4) | — |



### RET-T004

**RET-F003 · Entry · Password visibility · PASS**

**Scenario** — Toggle password visibility twice and confirm input text, mask and accessible name.

**Preconditions** — Isolated browser session with demo sign-in available.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Prefilled demo password (redacted). | Toggle Show and Hide password and inspect control type. | Text then password with same field value. | type=text then type=password; value preserved. | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:1) | — |



### RET-T005

**RET-F004 · Shell · Shell navigation · PASS**

**Scenario** — Use menu toggle, Retirement Builder sidebar button and SYD from wizard and list.

**Preconditions** — Isolated browser with Retirement Builder available and the stated viewport.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Isolated dashboard and two unsaved wizard entries. | Toggle sidebar twice, navigate from wizard by SYD and sidebar Retirement Builder. | Both navigation entry points return to dashboard. | {"landing": "/retirement-builder"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:7) | — |



### RET-T006

**RET-F005 · Shell · Responsive layout · PASS**

**Scenario** — Inspect list, wizard, modal and picker at desktop, 767/768, 520 and 430 px widths; verify scroll and no clipped actions.

**Preconditions** — Isolated browser with Retirement Builder available and the stated viewport.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Desktop 1280×720 and overrides at 768×900, 767×900, 520×820, 430×850. Close mobile navigation drawer after resize. | Inspect Dashboard, Edit General, Mapping, File Settings/dropdown and Subscriptions at each size. | No document overflow; forms and modal clipped checks pass; intended grid horizontal scroll allowed. | {"measurements": [{"dim": {"document": 1280, "h": 720, "main": 1032, "w": 1280}, "dashboard": {"bottom": 739, "client": 916, "right": 1223, "scroll": 1513, "x": 305, "y": 239}, "gen": {"bottom": 431, "client": 407, "right": 752, "scroll": 407, "x": 317, "y": 383}, "grid": {"bottom": 653, "client": 892, "right": 1211, "scroll": 1180, "x": 317, "y": 513}, "dialog": {"bottom": 660, "client": 1178, "right": 1230, "scroll": 1178, "x": 50, "y": 60}, "list": {"bottom": 619, "client": 485, "right": 1095, "scroll": 485, "x": 607, "y": 349}}, {"dim": {"document": 768, "h": 900, "main": 533, "w": 768}, "dashboard": {"bottom": 821, "client": 417, "right": 711, "scroll": 1513, "x": 292, "y": 267}, "gen": {"bottom": 431, "client": 158, "right": 490, "scroll": 158, "x": 304, "y": 383}, "grid": {"bottom": 728, "client": 393, "right": 699, "scroll": 1180, "x": 304, "y": 555}, "dialog": {"bottom": 761, "client": 718, "right": 744, "scroll": 718, "x": 24, "y": 139}, "list": {"bottom": 698, "client": 318, "right": 672, "scroll": 318, "x": 352, "y": 428}}, {"dim": {"document": 767, "h": 900, "main": 767, "w": 767}, "dashboard": {"bottom": 829, "client": 719, "right": 744, "scroll": 1513, "x": 23, "y": 247}, "gen": {"bottom": 428, "client": 681, "right": 738, "scroll": 681, "x": 29, "y": 380}, "grid": {"bottom": 732, "client": 707, "right": 738, "scroll": 1180, "x": 29, "y": 551}, "dialog": {"bottom": 768, "client": 733, "right": 751, "scroll": 733, "x": 16, "y": 132}, "list": {"bottom": 734, "client": 318, "right": 671, "scroll": 318, "x": 351, "y": 464}, "drawerClosed": true}, {"dim": {"document": 520, "h": 820, "main": 520, "w": 520}, "dashboard": {"bottom": 749, "client": 472, "right": 497, "scroll": 1513, "x": 23, "y": 288}, "gen": {"bottom": 428, "client": 434, "right": 491, "scroll": 434, "x": 29, "y": 380}, "grid": {"bottom": 691, "client": 460, "right": 491, "scroll": 1180, "x": 29, "y": 551}, "dialog": {"bottom": 742, "client": 486, "right": 504, "scroll": 486, "x": 16, "y": 78}, "list": {"bottom": 688, "client": 318, "right": 512, "scroll": 318, "x": 192, "y": 418}, "drawerClosed": false}, {"dim": {"document": 430, "h": 850, "main": 430, "w": 430}, "dashboard": {"bottom": 779, "client": 382, "right": 407, "scroll": 1513, "x": 23, "y": 288}, "gen": {"bottom": 428, "client": 344, "right": 401, "scroll": 344, "x": 29, "y": 380}, "grid": {"bottom": 691, "client": 370, "right": 401, "scroll": 1180, "x": 29, "y": 551}, "dialog": {"bottom": 776, "client": 396, "right": 414, "scroll": 396, "x": 16, "y": 74}, "list": {"bottom": 703, "client": 318, "right": 422, "scroll": 318, "x": 102, "y": 433}, "drawerClosed": false}], "overflowCount": 0} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:68) | — |



### RET-T007

**RET-F005 · Shell · Responsive layout · NOT TESTED**

**Scenario** — Open later wizard tabs, mapping grid and modal at small width and zoom with real keyboard; inspect reachable last buttons.

**Preconditions** — Isolated browser with the relevant wizard, dashboard or modal available.

**Test data and actions** — See the planned variants above. These were not executed as a complete scenario.

**Expected** — The documented control, guard or recovery behavior holds for each planned variant.

**Actual and evidence** — No direct result recorded for this scenario.

**Remaining gap** — The 430 px wizard and modal were inspected and normal-size keyboard interactions ran in T079 and T094. The combination of browser zoom, a narrow viewport and a complete keyboard traversal was not executed.


### RET-T008

**RET-F006 · Dashboard · Enabled job list · PASS**

**Scenario** — Load enabled/manual-only/scheduled fixtures; verify normalized list columns, and disabled fixture invisibility.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Seeded job IDs 1–6, including disabled ID 4 and date sentinel on ID 3. | GET list and inspect fixture entries. | Correct enabled/scheduled/manual projections and suppressed date without history. | {"manual": {"week": "", "hour": "", "minute": "", "meridiem": "", "buildFrequency": "", "startDate": null}, "scheduled": {"week": "Tuesday", "hour": "12", "minute": "05", "meridiem": "PM", "buildFrequency": "Weekly"}, "disabledListed": false, "sentinelLastRun": null} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:2) | — |
| isolated browser | Fixtures UX Payroll 2, UX CSV 10, UX Later 20 and disabled UX Disabled. Sentinel date on UX Later 20. | Observe dashboard and compare row cells to seeded fixtures. | Manual-only row omits time/day; scheduled row shows Weekly; sentinel/post-create last-run blank; disabled not listed. | {"manual": ["2026-11-17", "", "", "", "Manual only", "Pipe", "Yes", "Pending"], "scheduled": ["2026-11-17", "", "Tuesday", "12:05 PM", "Weekly", "Comma", "Yes", "Pending"], "sentinel": "", "disabled": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:5) | — |



### RET-T009

**RET-F006 · Dashboard · Enabled job list · PASS**

**Scenario** — Verify Job Last Run blank for new/no history, with legacy sentinel date, and retained when manual-only.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Seeded job IDs 1–6, including disabled ID 4 and date sentinel on ID 3. | GET list and inspect fixture entries. | Correct enabled/scheduled/manual projections and suppressed date without history. | {"manual": {"week": "", "hour": "", "minute": "", "meridiem": "", "buildFrequency": "", "startDate": null}, "scheduled": {"week": "Tuesday", "hour": "12", "minute": "05", "meridiem": "PM", "buildFrequency": "Weekly"}, "disabledListed": false, "sentinelLastRun": null} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:3) | — |
| isolated browser | Fixtures UX Payroll 2, UX CSV 10, UX Later 20 and disabled UX Disabled. Sentinel date on UX Later 20. | Observe dashboard and compare row cells to seeded fixtures. | Manual-only row omits time/day; scheduled row shows Weekly; sentinel/post-create last-run blank; disabled not listed. | {"manual": ["2026-11-17", "", "", "", "Manual only", "Pipe", "Yes", "Pending"], "scheduled": ["2026-11-17", "", "Tuesday", "12:05 PM", "Weekly", "Comma", "Yes", "Pending"], "sentinel": "", "disabled": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:6) | — |



### RET-T010

**RET-F007 · Dashboard · Background list refresh · NOT TESTED**

**Scenario** — Observe initial fetch, five-second visible refresh, background pause, resumed updates and cancellation on route change.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Visible test tab then Add wizard. | Count request trace before/after polling tick, then wait 5.9s on General. | Refresh while visible and stops when leaving list. | {"visibility": "visible", "visibleRefresh": true, "wizardRefresh": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:63) | — |


**Remaining gap** — Initial refresh, visible five-second polls, failure recovery and navigation away were observed. The hidden → visible transition and in-flight cancellation under that transition were not instrumented.


### RET-T011

**RET-F007 · Dashboard · Background list refresh · PASS**

**Scenario** — Simulate polling failure after good data and check retained rows versus initial-error display.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Known populated list then injected HTTP 500 during poll and initial reload. | Observe a failed poll without reload; then reload with same fault. | Existing rows stay after poll failure but fresh load shows error. | {"afterPoll": "retained", "reload": "Unable to load Retirement Builder jobs. Please try again.", "failedTrace": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:61) | — |



### RET-T012

**RET-F008 · Dashboard · Loading, empty and error rows · PASS**

**Scenario** — Compare slow load, empty dataset, no filtered match, and initial HTTP failure states.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | 800 ms initial load, isolated [] and 500 responses, and impossible user filter. | Observe each UI list branch. | Loading, no matches (two paths), populated and load-error states. | {"loading": true, "empty": true, "filteredEmpty": true, "error": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:62) | — |



### RET-T013

**RET-F009 · Dashboard · Column filters · PASS**

**Scenario** — Exercise all ten filter inputs individually, then intersection, case, trim and clearing.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | {"filters": ["File Name", "Description", "Modified On", "Last Run Date", "Run Day", "Run Time", "Schedule Type", "File Type", "Is Active", "Status"], "selectedFixture": "UX CSV 10", "values": ["UX CSV 10", "Synthetic only", "2026-11-17", "2026-11-17", "Tuesday", "12:05 PM", "Weekly", "Comma", "Yes", "Success"]} | Match each field with trimmed uppercase, replace with impossible term, clear; test intersection. | Target appears for matches, disappears for mismatches and incompatible intersection. | {"checked": 10, "intersection": "no rows"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:18) | — |



### RET-T014

**RET-F010 · Dashboard · Column sorting · PASS**

**Scenario** — Click each header twice and switch columns; verify asc/desc, numeric-aware text, tie behavior and aria-sort.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Five UX fixtures and all ten columns. | Click each heading twice and inspect aria-sort on column header. | Every column toggles ascending and descending. | {"checked": ["File Name", "Description", "Modified On", "Last Run Date", "Run Day", "Run Time", "Schedule Type", "File Type", "Is Active", "Status"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:8) | — |



### RET-T015

**RET-F010 · Dashboard · Column sorting · FAIL**

**Scenario** — Use records whose time strings differ in hour width and AM/PM; compare actual natural-text order with time-of-day semantics.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | 2:05 AM and 12:05 PM fixture times. | Click Run Time ascending and compare positions. | 2:05 AM precedes noon for these inputs. | {"timeOrder": ["UX Later 20", "UX CSV 10"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:9) | — |
| isolated browser | Midnight (12:05 AM) and 1:05 AM on the same future schedule. | Filter to the two Timing sort data jobs, sort Run Time ascending. | 12:05 AM sorts before 1:05 AM. | ["Timing sort data twoSynthetic only2026-11-17Tuesday1:05 AMWeeklyCommaYesPending", "Timing sort data oneSynthetic only2026-11-17Tuesday12:05 AMWeeklyCommaYesPending"] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:19) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B007-time-sort.jpg) | RET-B007 |



### RET-T016

**RET-F011 · Dashboard · Row selection · PASS**

**Scenario** — Select/deselect row and verify transient run result or error is cleared.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | One successful isolated run and selected job 1. | Uncheck row after success. | Result status/download feedback clears. | {"resultVisible": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:15) | — |



### RET-T017

**RET-F012 · Dashboard · Select all visible · PASS**

**Scenario** — Select all visible, apply a narrower filter, deselect visible and compare retained hidden row IDs.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | UX Payroll 2 selected then hidden; UX CSV 10 visible. | Select all visible, then deselect all visible. | Only visible selection changes; hidden selection persists. | {"twoSelectionRunEnabled": false, "hiddenSelectionRetained": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:11) | — |



### RET-T018

**RET-F013 · Dashboard · Edit and Run availability · FAIL**

**Scenario** — Compare zero, one and multiple selected; include filtered-out selected row and inspect enabled actions.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | UX Payroll 2 selected, then File Name filter No-such-qa-name. | Compare enabled actions with no selection, select row, filter it away. | Edit and Run disable when selected job is no longer visible. | {"visibleRows": 0, "editEnabled": true, "runEnabled": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:10) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B001-hidden-selection.jpg) | RET-B001 |



### RET-T019

**RET-F013 · Dashboard · Edit and Run availability · PASS**

**Scenario** — While running, examine checkbox lock and whether Edit/Add remains available; compare with requests and server job lock.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Seed 1 run with 650 ms delay. | Inspect controller enablement while request is active. | Selection and Run disabled; observe other controls independently. | {"selection": false, "edit": true, "add": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:14) | — |



### RET-T020

**RET-F014 · Dashboard · Template download · PASS**

**Scenario** — Download Template, verify filename and open an unmodified copy as supported mapping workbook.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Packaged mapped_payroll_columns_HDT.xlsx. | Click Template, compare downloaded bytes with static package, upload unmodified copy into unsaved wizard. | Exact workbook downloaded and accepted by import. | {"savedFile": "mapped_payroll_columns_HDT (3).xlsx", "bytes": 7926, "imported": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:58) | — |



### RET-T021

**RET-F015 · Dashboard · Start new job · PASS**

**Scenario** — Open Add after an Edit/canceled draft; confirm required fields blank, flags unchecked and no stale rows or key.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Previously canceled UI Cancel Draft. | Click Cancel then Add; inspect fields and flags. | Add clears draft; no Cancel confirmation. | {"name": "", "checked": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:25) | — |



### RET-T022

**RET-F016 · Dashboard · Open existing job by Edit · PASS**

**Scenario** — Select an enabled job and click Edit; compare all persisted sections with hydrated fields.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Saved UI Field Checks with company, mapping, rules and no start date. | Select one job and Edit, inspect hydrated General, Schedule, Mapping, File Settings and Subscriptions. | Saved values available on each step. | {"file": "UI Field Checks", "schedule": "blank", "mappingRows": 7, "rules": 1, "subscriptions": 1} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:57) | — |



### RET-T023

**RET-F017 · Dashboard · Open existing job by name · PASS**

**Scenario** — Click the file-name cell with no selection and confirm equivalent Edit path.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Saved isolated job 1, no selected checkbox. | Click job name cell. | Loads edit wizard without selecting checkbox. | {"mode": "Edit", "file": "UX Payroll 2"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:22) | — |



### RET-T024

**RET-F018 · Dashboard · Job-detail fetch failure · FAIL**

**Scenario** — Simulate detail GET 404 and network failure; compare dashboard feedback with developer console-only failure.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | GET /jobs/1 injected 404 and network disconnect. | Click job name and remain on dashboard. | Dashboard displays job detail error. | [{"fault": {"status": 404}, "alerts": []}, {"fault": {"disconnect": true}, "alerts": []}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:12) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B006-hidden-edit-error.jpg) | RET-B006 |



### RET-T025

**RET-F019 · Dashboard · Manual run request · PASS**

**Scenario** — Run one enabled manual-only job in an isolated fixture and verify one POST, pending UI state then observed result.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | UX Payroll 2 ID 1, 650 ms test response delay, 10 synthetic H/D/T rows. | Select, click Run once, observe Running/Success and inspect HTTP trace. | One successful POST and known generated/stored counts. | {"busy": {"selection": false, "edit": true, "add": true}, "post": [{"method": "POST", "path": "/api/v1/retirement-builder/jobs/1/run", "status": 200, "ms": 706}], "success": ["", "UX Payroll 2", "Synthetic only", "2026-11-17", "2026-11-17", "", "", "Manual only", "Pipe", "Yes", "Success"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:13) | — |



### RET-T026

**RET-F020 · Dashboard · Manual run failure feedback · PASS**

**Scenario** — Trigger missing input, malformed source and network failure separately; compare result banner and persisted history.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Missing job-ID 5 file and simulated network disconnect. | Click Run, then disconnect response and rerun; inspect alerts. | Readable missing source and network feedback. | {"missing": "  - alert: Source CSV missing. Place 5.csv in the configured report input folder.", "networkAlert": "Unable to reach the Retirement Builder service."} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:17) | — |
| isolated browser | UX Missing CSV, 5.csv with two headers and one value; separate missing and disconnected attempts | Run the three variants from dashboard and inspect banner; check execution history in SQL-backed case | Actionable errors, history for execution failures and no history for disconnect | Missing and malformed input each displayed source-specific banner; disconnected request displayed generic run failure. SQL checks recorded source error history. | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:80) | — |



### RET-T027

**RET-F021 · Dashboard · Manual run result feedback · PASS**

**Scenario** — Run fixtures with 0, 1 or multiple result files; verify counts, status text and link visibility.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Zero-match payroll job 6, single payroll job 1, split CSV job 2. | Run each from dashboard and inspect text/download links. | Zero, one and four links with corresponding feedback. | [["  - status: No matching records. No files generated."], ["    - text: Generated 10 rows. Saved 10 rows to the database.", "    - link \"Download CSV\":"], ["    - text: Generated 12 rows. Saved 12 rows to the database.", "    - link \"UX CSV 10_1_2026-09-01.csv\":", "    - link \"UX CSV 10_1_2026-10-01.csv\":", "    - link \"UX CSV 10_2_2026-09-01.csv\":", "    - link \"UX CSV 10_2_2026-10-01.csv\":"]] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:16) | — |



### RET-T028

**RET-F021 · Dashboard · Manual run result feedback · PASS**

**Scenario** — Compare no-match payroll success (zero files) to no-match ungrouped legacy CSV still rendering a configured file.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Employee Count=99 synthetic payroll; Amount=99 on Amount=1 CSV. | Run both fixtures via real backend and inspect response/history. | Payroll produces no file; ungrouped CSV produces headings-only file. | {"payrollFiles": 0, "ungroupedCsvFiles": 1, "bothCount": 0} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:20) | — |



### RET-T029

**RET-F022 · Dashboard · Download generated files · PASS**

**Scenario** — Download single/multiple CSVs, compare bytes to server result and disk, re-run and check old links replaced.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Single payroll output and four CSV groups. | Run and download each file; byte-compare with filesystem; rerun and compare Blob link URI. | Downloaded bytes are identical to published file and rerun replaces link. | {"downloads": [{"filename": "UX Payroll 2.csv", "bytes": 250, "diskMatches": ["1f5bd3ea-dee6-481c-8ce5-481e09b39151", "ee59835a-f694-4b1c-8a3f-f930a6f55d9d", "ffab1ca0-4d8d-42df-8110-0121c67b3647"]}, {"filename": "UX CSV 10_1_2026-09-01.csv", "bytes": 50, "diskMatches": ["0bf0f671-fc42-4146-9d12-2b2aa07786ef", "bc137237-5688-4ca8-9673-56274af1c4cd"]}, {"filename": "UX CSV 10_1_2026-10-01.csv", "bytes": 50, "diskMatches": ["0bf0f671-fc42-4146-9d12-2b2aa07786ef", "bc137237-5688-4ca8-9673-56274af1c4cd"]}, {"filename": "UX CSV 10_2_2026-09-01.csv", "bytes": 49, "diskMatches": ["0bf0f671-fc42-4146-9d12-2b2aa07786ef", "bc137237-5688-4ca8-9673-56274af1c4cd"]}, {"filename": "UX CSV 10_2_2026-10-01.csv", "bytes": 49, "diskMatches": ["0bf0f671-fc42-4146-9d12-2b2aa07786ef", "bc137237-5688-4ca8-9673-56274af1c4cd"]}], "blobReplaced": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:59) | — |



### RET-T030

**RET-F022 · Dashboard · Download generated files · PASS**

**Scenario** — Reload after a successful run and check whether earlier links remain available.

**Preconditions** — Isolated job list with the named fixture or injected response.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Completed prior run and downloads. | Reload dashboard. | Transient result links clear; status remains available in list. | {"linksAfter": 0, "status": "Success"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:60) | — |



### RET-T031

**RET-F023 · Wizard · Step tabs and validation · PASS**

**Scenario** — Try jumping from blank General, incomplete Schedule and invalid Mapping to later tabs; confirm first guarded step.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Earlier blank General, incomplete Weekly, and anonymous Mapping Row 8. | Click later step tabs across the three invalid states. | Each first invalid guard appears. | {"generalGuard": true, "scheduleAlerts": ["    - alert: Select an hour from 1 to 12.", "    - alert: Select a minute from 00 to 59.", "    - alert: Select AM or PM.", "  - alert: Select a day of the week."], "mappingGuard": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:35) | — |



### RET-T032

**RET-F023 · Wizard · Step tabs and validation · PASS**

**Scenario** — Bypass normal tabs via direct later route with valid General but incomplete earlier fields; verify Finish blocks.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Valid General fields, blank Schedule, empty Mapping, direct /jobs/new/subscriptions. | Navigate directly then use Finish. | Direct link can open Subscriptions but Finish returns to invalid Mapping. | {"routeBlockedAt": "Mapping", "alert": "Add at least one dataset mapping."} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:64) | — |



### RET-T033

**RET-F024 · Wizard · Next and Back navigation · NOT TESTED**

**Scenario** — Move Next/Back between all four steps with unsaved inputs and compare values; observe Next disabled during import.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Valid general and three imported mapping rows. | Go Next through wizard and back to Mapping/General; inspect retained values. | Normal navigation preserves data. Import loading behavior examined separately. | {"moved": ["General", "Schedule", "Mapping", "Subscriptions", "Mapping"], "retained": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:66) | — |


**Remaining gap** — The four-step journey preserved values on Back and Next. The workbook load settled before the disabled Next state could be observed.


### RET-T034

**RET-F025 · Wizard · Cancel and draft reset · PASS**

**Scenario** — Cancel with edited data, enter Add again, confirm reset and inspect whether a warning appears.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Previously canceled UI Cancel Draft. | Click Cancel then Add; inspect fields and flags. | Add clears draft; no Cancel confirmation. | {"name": "", "checked": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:26) | — |



### RET-T035

**RET-F025 · Wizard · Cancel and draft reset · PASS**

**Scenario** — Cancel a modal with unapplied settings, then reopen; compare persisted job rules and wizard draft.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Applied nonempty sort/condition modal rows. | Clear and Cancel; reopen; Clear and Save & Continue; reopen. | Cancel preserves prior draft; Apply commits empty sets. | {"cancelPreserved": true, "applyCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:42) | — |



### RET-T036

**RET-F026 · Wizard · Refresh and draft restore · PASS**

**Scenario** — Reload a draft in Add and Edit; check saved form values and that unapplied modal changes are gone.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | UI Field Checks Add draft on Subscriptions, merged flag and tagged synthetic addresses. | Reload while draft survives. | Same route, tags and rows restored. | {"restored": true, "blankRowRestored": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:50) | — |
| isolated browser | Edit saved payroll mapping and modal, add/applied second condition 0.50, then unapplied removal of first. Add variant covered separately. | Reload from Edit Mapping and re-open modal. | Applied parent draft survives, modal local edits disappear. | {"firstValue": 1, "secondValue": 0.5, "modalClosedAfterReload": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:76) | — |



### RET-T037

**RET-F026 · Wizard · Refresh and draft restore · NOT TESTED**

**Scenario** — Simulate sessionStorage unavailable/malformed and concurrent same-tab flow; verify safe fallback and key restoration.

**Preconditions** — Isolated browser with the relevant wizard, dashboard or modal available.

**Test data and actions** — See the planned variants above. These were not executed as a complete scenario.

**Expected** — The documented control, guard or recovery behavior holds for each planned variant.

**Actual and evidence** — No direct result recorded for this scenario.

**Remaining gap** — Add/Edit refresh and browser history ran under working storage. Storage denial, malformed stored state and same-tab draft contention were not injected.


### RET-T038

**RET-F027 · Wizard · History and direct route · FAIL**

**Scenario** — Use Back/Forward after Cancel and open direct step routes with no, matching and wrong-mode drafts.

**Preconditions** — Isolated Add or Edit draft with any preceding fields completed as needed.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Unsaved Add job name UI Cancel Draft; Cancel while on Schedule. | Cancel, use browser Back, then return to General tab. | Canceled draft is not recoverable through browser history. | {"reopenedName": "UI Cancel Draft"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:24) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B002-cancel-history.jpg) | RET-B002 |



### RET-T039

**RET-F028 · General · File Name · PASS**

**Scenario** — Enter blank, whitespace-only and regular File Name; inspect field-level UI and API checks.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Empty/spaces/255/256 name, multiline Description 300/301, format 20/21 and naming 55/56 bounds. | POST valid and invalid payloads, GET accepted job. | Reject missing/over-limit and preserve accepted values. | {"422": [["fileName", 0, 422], ["fileName", 3, 422], ["fileName", 256, 422], ["description", 301, 422], ["outputFileNameFormat", 56, 422], ["fileFormat", 21, 422]], "accepted": [255, 300], "lineBreakRetained": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:7) | — |
| isolated browser | Empty and whitespace file names plus Comma format, then UI Cancel Draft. | Try advancing from General; replace invalid text with regular file name. | Field errors shown for blank/whitespace; valid name advances. | {"invalidBlank": true, "invalidWhitespace": true, "validLands": "Schedule"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:23) | — |



### RET-T040

**RET-F028 · General · File Name · PASS**

**Scenario** — Try 255 and 256 characters and Unicode near filename byte limit with significant whitespace and path characters.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Empty/spaces/255/256 name, multiline Description 300/301, format 20/21 and naming 55/56 bounds. | POST valid and invalid payloads, GET accepted job. | Reject missing/over-limit and preserve accepted values. | {"422": [["fileName", 0, 422], ["fileName", 3, 422], ["fileName", 256, 422], ["description", 301, 422], ["outputFileNameFormat", 56, 422], ["fileFormat", 21, 422]], "accepted": [255, 300], "lineBreakRetained": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:8) | — |
| isolated HTTP API and files | 255 and 256 ASCII; two spaces + 120 é + :?* + two spaces | Create/GET and Run accepted inputs; independently count UTF-8 file name bytes; submit 256 characters | 255 accepted, 256 rejected; safe output uses at most 200 base bytes and strips significant leading/trailing whitespace at generation | {"savedLeadingSpaces": true, "unicodeBytesIncludingExtension": 204, "asciiBytesIncludingExtension": 204, "256HTTP": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:135) | — |
| isolated browser | 256 characters plus shorter Unicode/path-character draft. API separately tests 255 and output sanitization. | Advance from General with each value. | Inline max error, allowed Unicode/punctuation proceed. | {"overLimitBlocked": true, "unicodeAccepted": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:34) | — |



### RET-T041

**RET-F029 · General · File Format · PASS**

**Scenario** — Choose each configured delimiter label and verify shown label, saved byte and rendered file delimiter.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | All five labels; CSV Amount,Code with one data row 12,Z. | Create, GET, Run, read DB and parse using expected separator. | Label roundtrips and one exact delimiter byte is stored/used. | {"Comma": [7, 44, 1], "Pipe": [8, 124, 1], "Semicolon": [9, 59, 1], "Space": [10, 32, 1], "Tab": [11, 9, 1]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:4) | — |
| isolated HTTP API and SQL Server | All five labels; CSV Amount,Code with one data row 12,Z. | Create, GET, Run, read DB and parse using expected separator. | Label roundtrips and one exact delimiter byte is stored/used. | {"Comma": [123, 44, 1], "Pipe": [124, 124, 1], "Semicolon": [125, 59, 1], "Space": [126, 32, 1], "Tab": [127, 9, 1]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:116) | — |



### RET-T042

**RET-F029 · General · File Format · PASS**

**Scenario** — Test legacy CSV/CSV_PIPE/CSV_TAB/CSV_SEMI aliases, unknown labels and unsupported catalog values.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | CSV, CSV_PIPE, CSV_TAB, CSV_SEMI, Tilde, newline catalog delimiter. | Submit labels; exercise old DB values without conversion, Run, then PUT; check invalid catalog. | Legacy run works, normal save writes byte, invalid settings are rejected or excluded. | {"CSV": 44, "CSV_PIPE": 124, "CSV_TAB": 9, "CSV_SEMI": 59, "unknown": 422, "newlineCatalogEntry": "excluded"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:5) | — |



### RET-T043

**RET-F030 · General · Description · PASS**

**Scenario** — Persist multiline Description and try 300 vs 301 characters.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Empty/spaces/255/256 name, multiline Description 300/301, format 20/21 and naming 55/56 bounds. | POST valid and invalid payloads, GET accepted job. | Reject missing/over-limit and preserve accepted values. | {"422": [["fileName", 0, 422], ["fileName", 3, 422], ["fileName", 256, 422], ["description", 301, 422], ["outputFileNameFormat", 56, 422], ["fileFormat", 21, 422]], "accepted": [255, 300], "lineBreakRetained": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:9) | — |
| isolated HTTP API and SQL Server | Description 'first\nsecond' plus 288 a characters and an additional b for 301 | Create and GET 300 characters; create 301 | Exact multiline round trip, 422 at 301 | {"savedLength": 300, "newline": true, "oversizeStatus": 422, "detail": [{"loc": ["body", "general", "description"], "msg": "Use at most 300 characters.", "type": "value_error"}]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:132) | — |



### RET-T044

**RET-F031 · General · Output File Name Format · PASS**

**Scenario** — Choose blank/new naming codes and open Edit to check code label rehydration.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | New naming option omitted; then set Payday and update. | Save blank format, reopen edit and verify File Name fallback; set Payday and verify after a second reopen. | Default File Name and selected Payday both rehydrate correctly. | {"blankShownAs": "File Name", "resavedShownAs": "Payday"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:73) | — |



### RET-T045

**RET-F031 · General · Output File Name Format · PASS**

**Scenario** — Submit unknown, duplicate-token and reordered valid codes in API fixture; compare fallback and dropdown behavior.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Blank/unknown/duplicate/reordered/legacy naming codes. | Create and re-read each job. | Fallback FILENAME for blank/unknown/duplicate, valid part orders preserved. | {"": "FILENAME", "UNKNOWN": "FILENAME", "CLIENT_CLIENT": "FILENAME", "PAYDAY_FILENAME": "PAYDAY_FILENAME", "Client ID + Pay Date": "CLIENT_PAYDAY", "pay date": "PAYDAY"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:10) | — |



### RET-T046

**RET-F032 · General · Payroll Client ID help · PASS**

**Scenario** — Choose payroll output formats containing Client ID and change to Payday only; check contextual hint.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Company Payroll Add; select Client ID then Payday. | Switch output format between grouping modes. | Hint appears only for a Client ID-containing payroll option. | {"clientHint": true, "paydayHint": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:27) | — |



### RET-T047

**RET-F033 · General Edit · Enable/Disable toggle · PASS**

**Scenario** — Toggle checkbox in Edit, save disabled fixture, confirm disappearance and verify disabled run response using job ID.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | New synthetic CSV job. | Disable with PUT; list, read, run and restore via API. | Disabled job hidden/nonrunnable; direct API can restore. | {"id": 23, "listDisabled": false, "runDisabled": 409, "apiRestore": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:11) | — |
| isolated HTTP API and SQL Server | New synthetic CSV job. | Disable with PUT; list, read, run and restore via API. | Disabled job hidden/nonrunnable; direct API can restore. | {"id": 139, "listDisabled": false, "runDisabled": 409, "apiRestore": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:117) | — |
| isolated browser | Isolated future scheduled job UX Later 20 (ID 3). | Open Edit, set Disable, Finish, list filtered job; API disabled Run covered separately. | Disabled job is absent from enabled list and not runnable. | {"rowVisible": false, "editEnabled": false, "runEnabled": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:20) | — |



### RET-T048

**RET-F033 · General Edit · Enable/Disable toggle · FAIL**

**Scenario** — Check disabled job recovery through normal dashboard and direct API read/update on disposable job.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | New synthetic CSV job. | Disable with PUT; list, read, run and restore via API. | Disabled job hidden/nonrunnable; direct API can restore. | {"id": 23, "listDisabled": false, "runDisabled": 409, "apiRestore": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:12) | — |
| isolated HTTP API and SQL Server | New synthetic CSV job. | Disable with PUT; list, read, run and restore via API. | Disabled job hidden/nonrunnable; direct API can restore. | {"id": 139, "listDisabled": false, "runDisabled": 409, "apiRestore": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:118) | — |
| isolated browser | UX Later 20 ID 3 disabled in UI. | Return to list with exact name filter; search actions and disabled-row toggle. | A standard UI recovery path should allow re-enable. | {"visibleRows": 0, "editEnabled": false, "restoreButtonCount": 0} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:21) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B004-disabled-job.jpg) | RET-B004 |



### RET-T049

**RET-F034 · General · Store Results to Table · PASS**

**Scenario** — Run equivalents with storage off/on; confirm the same generated bytes and storedRows 0/N respectively.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Amount=2, Store Results off then on. | POST/Run/PUT/Run, query result table and compare file. | Same CSV, storedRows 0 then 1. | {"off": 0, "on": 1, "dataRows": 1, "fileEqual": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:19) | — |



### RET-T050

**RET-F035 · General · Browse and workbook import · PASS**

**Scenario** — Import seven-row workbook, compare field names and H/D/T order with first sheet and verify it replaces the grid.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | 7-mappings.xlsx, first worksheet with H/D/T shorthand and seven names. | Browse Files, choose workbook, open Mapping and read ordered fields. | Seven fields, correct declared record types and order. | {"fields": ["Header Company", "Company Name", "Pay Date", "Employee Count", "Net Salary Total", "Trailer Record Type", "Trailer Net Salary"], "H": true, "T": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:28) | — |



### RET-T051

**RET-F035 · General · Browse and workbook import · PASS**

**Scenario** — Import XLS, XLSX, headers-only alternate layout, H/D/T shorthand, duplicate exact/case-variant and blank fields.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | short-records.xls contains Mail/H, Mail/D, mail/d, blank/D, Summary/T. headers-only.xlsx contains Amount, Label, Company Name. | Import XLS and XLSX fixtures consecutively. | Exact duplicate and blank removed; case variant preserved; raw header mode works. | {"xls": ["Mail", "mail", "Summary"], "xlsx": ["Amount", "Label", "Company Name"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:29) | — |



### RET-T052

**RET-F036 · General · Workbook validation and loading · PASS**

**Scenario** — Import unsupported extension, bad signature, and empty first sheet; record distinct messages and unchanged mappings.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Unsupported .txt, .xlsx with plain text, empty first worksheet after valid seven-row workbook. | Import each bad fixture; read error; check prior mapped fields. | Distinct messages and old mappings retained. | {"rejected": ["unsupported.txt", "bad.xlsx", "empty-sheet.xlsx"], "retained": 7} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:30) | — |



### RET-T053

**RET-F036 · General · Workbook validation and loading · PASS**

**Scenario** — Inspect large workbook and slow parse behavior in an isolated browser. Verify absence or presence of a size error without compromising responsiveness.

**Preconditions** — Isolated General step or equivalent isolated API draft.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | large-mapping.xlsx with 4,000 mapping rows. | Import on General and wait for completion; do not duplicate state by saving. | Record whether size handling permits the file. | {"importCompleted": true, "rowsInFixture": 4000, "frontendMessage": "Mapping fields imported."} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:31) | — |



### RET-T054

**RET-F037 · General · Import replacement and stale reads · NOT TESTED**

**Scenario** — Choose a second workbook before first parse resolves or cancel during import; confirm stale result is ignored.

**Preconditions** — Isolated browser with the relevant wizard, dashboard or modal available.

**Test data and actions** — See the planned variants above. These were not executed as a complete scenario.

**Expected** — The documented control, guard or recovery behavior holds for each planned variant.

**Actual and evidence** — No direct result recorded for this scenario.

**Remaining gap** — Normal, invalid and replacement workbook imports ran. No deterministic overlapping file reads or Cancel during parsing were created.


### RET-T055

**RET-F038 · Schedule · Start Date and manual-only mode · PASS**

**Scenario** — Save wholly blank Schedule and reopen; confirm Manual only, null start, blank Edit and manual Run.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | All six schedule inputs empty, one valid Pay Date mapping, sandbox payroll with four Detail rows. | Save via UI, verify Manual only, run manually and reopen Edit Schedule. | Saved manual-only, Run succeeds with 4 records, Edit values stay blank. | {"schedule": ["", "", "Manual only"], "manualRun": "Generated 4 rows.", "editStartDate": ""} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:72) | — |



### RET-T056

**RET-F038 · Schedule · Start Date and manual-only mode · PASS**

**Scenario** — Compare 1752-12-31, 1753-01-01, 9999-12-31 and invalid calendar dates via UI/API; retain null case.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | 1752-12-31, 1753-01-01, 9999-12-31, 2026-02-30, null. | POST each date then GET accepted jobs. | Only valid dates at/above the floor or null accepted. | {"1752-12-31": 422, "1753-01-01": 201, "9999-12-31": 201, "2026-02-30": 422, "None": 201} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:17) | — |
| isolated browser | Start Date 1752-12-31, 1753-01-01, 9999-12-31; weekly varieties vs Daily/Monthly with no weekday; 12:59 AM. | Set each frequency and boundary, click Next, inspect result. | 1752 blocked; both valid endpoints advance. Weekly/Bi-Weekly require day, Daily/Monthly do not. | {"weekdayRequired": ["Weekly", "Bi-Weekly"], "weekdayOptional": ["Daily", "Monthly"], "dateFloorRejected": true, "minAndMaxAccepted": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:32) | — |



### RET-T057

**RET-F038 · Schedule · Start Date and manual-only mode · FAIL**

**Scenario** — Enter frequency/time but omit Start Date; inspect saved Manual only and whether user gets clear feedback.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Monthly, 12:59 AM, Start Date blank. | Finish job and inspect Dashboard schedule classification. | Intent to schedule receives validation or explicit manual-only warning before save. | {"before": "No date required message after choosing time", "after": ["", "", "Manual only"], "createdHTTP": 201} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:52) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B009-schedule-no-date.jpg) | RET-B009 |



### RET-T058

**RET-F039 · Schedule · Frequency selection · PASS**

**Scenario** — Compare Daily, Weekly, Bi-Weekly and Monthly persistence and options.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Daily/Weekly/Bi-Weekly/Monthly, Sunday/Monday/Tuesday/Saturday, 12AM/12PM/1AM/11PM. | POST four schedules and manual job, compare DB fields and timestamp. | D/W/B/M, weekday 0/1/2/6, times 00:00/12:59/01:05/23:08. | [{"frequency": "Daily", "stored": "D", "week": 0, "time": "00:00:00"}, {"frequency": "Weekly", "stored": "W", "week": 1, "time": "12:59:00"}, {"frequency": "Bi-Weekly", "stored": "B", "week": 2, "time": "01:05:00"}, {"frequency": "Monthly", "stored": "M", "week": 6, "time": "23:08:00"}, {"manual": 28, "date": null, "lowercase": 422}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:14) | — |
| isolated HTTP API and SQL Server | Daily/Weekly/Bi-Weekly/Monthly, Sunday/Monday/Tuesday/Saturday, 12AM/12PM/1AM/11PM. | POST four schedules and manual job, compare DB fields and timestamp. | D/W/B/M, weekday 0/1/2/6, times 00:00/12:59/01:05/23:08. | [{"frequency": "Daily", "stored": "D", "week": 0, "time": "00:00:00"}, {"frequency": "Weekly", "stored": "W", "week": 1, "time": "12:59:00"}, {"frequency": "Bi-Weekly", "stored": "B", "week": 2, "time": "01:05:00"}, {"frequency": "Monthly", "stored": "M", "week": 6, "time": "23:08:00"}, {"manual": 144, "date": null, "lowercase": 422}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:119) | — |



### RET-T059

**RET-F040 · Schedule · Hour, Minute, AM/PM · PASS**

**Scenario** — Exercise hour/minute/meridiem endpoints, including 12:00 AM and 12:00 PM conversion.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Daily/Weekly/Bi-Weekly/Monthly, Sunday/Monday/Tuesday/Saturday, 12AM/12PM/1AM/11PM. | POST four schedules and manual job, compare DB fields and timestamp. | D/W/B/M, weekday 0/1/2/6, times 00:00/12:59/01:05/23:08. | [{"frequency": "Daily", "stored": "D", "week": 0, "time": "00:00:00"}, {"frequency": "Weekly", "stored": "W", "week": 1, "time": "12:59:00"}, {"frequency": "Bi-Weekly", "stored": "B", "week": 2, "time": "01:05:00"}, {"frequency": "Monthly", "stored": "M", "week": 6, "time": "23:08:00"}, {"manual": 28, "date": null, "lowercase": 422}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:15) | — |
| isolated HTTP API and SQL Server | Daily/Weekly/Bi-Weekly/Monthly, Sunday/Monday/Tuesday/Saturday, 12AM/12PM/1AM/11PM. | POST four schedules and manual job, compare DB fields and timestamp. | D/W/B/M, weekday 0/1/2/6, times 00:00/12:59/01:05/23:08. | [{"frequency": "Daily", "stored": "D", "week": 0, "time": "00:00:00"}, {"frequency": "Weekly", "stored": "W", "week": 1, "time": "12:59:00"}, {"frequency": "Bi-Weekly", "stored": "B", "week": 2, "time": "01:05:00"}, {"frequency": "Monthly", "stored": "M", "week": 6, "time": "23:08:00"}, {"manual": 144, "date": null, "lowercase": 422}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:120) | — |



### RET-T060

**RET-F040 · Schedule · Hour, Minute, AM/PM · PASS**

**Scenario** — API boundary fixtures include hours 0, 1, 12, 13 and minutes 0, 59, 60, negatives, fractions and signed plus.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Hour 0/1/12/13 and minute 0/59/60 with negative/decimal/plus/empty. | POST each option on isolated schema. | Only permitted unsigned whole-number bounds accepted. | [["hour", "0", 422], ["hour", "1", 201], ["hour", "12", 201], ["hour", "13", 422], ["hour", "-1", 422], ["hour", "1.5", 422], ["hour", "+1", 422], ["hour", "", 422], ["minute", "0", 201], ["minute", "59", 201], ["minute", "60", 422], ["minute", "-1", 422], ["minute", "1.5", 422], ["minute", "+1", 422], ["minute", "", 422]] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:18) | — |



### RET-T061

**RET-F041 · Schedule · Week selector · PASS**

**Scenario** — With time entered, compare blank Week under weekly variants and Daily/Monthly.

**Preconditions** — Isolated schedule draft or saved job, and a controlled clock when recorded.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Start Date 1752-12-31, 1753-01-01, 9999-12-31; weekly varieties vs Daily/Monthly with no weekday; 12:59 AM. | Set each frequency and boundary, click Next, inspect result. | 1752 blocked; both valid endpoints advance. Weekly/Bi-Weekly require day, Daily/Monthly do not. | {"weekdayRequired": ["Weekly", "Bi-Weekly"], "weekdayOptional": ["Daily", "Monthly"], "dateFloorRejected": true, "minAndMaxAccepted": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:33) | — |



### RET-T062

**RET-F042 · Mapping · Add Dataset and empty state · PASS**

**Scenario** — Add blank mapping row and compare General import, Add row, and Edit row numeric defaults.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Fresh UI Add workbook rows and Add Dataset row 8. | Add new row, inspect all editable fields. | New Add fields are blank. | {"values": ["", "", "", ""]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:36) | — |
| isolated browser | 7-row XLSX imported in Add and Edit, then Add Dataset to Edit. | Compare new rows and imported numeric positions. | Add has blanks, Edit uses 0 for start/length. | {"EditImported": ["Header Company", "0", "0", ""], "EditAdded": ["", "0", "0", ""], "AddPreviously": ["", "", "", ""]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:74) | — |



### RET-T063

**RET-F043 · Mapping · Delete mapping row · PASS**

**Scenario** — Delete middle and final mapping row and verify actual array/validation/sequence.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Amount, Label, Company Name imported; delete Label in the middle, then delete remaining rows. | Inspect row positions, visit Subscriptions/back, try Next with empty grid. | Remaining order Amount/Company Name; no onward progression with none. | {"remainingAfterMiddle": ["Amount", "Company Name"], "minimumGuard": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:65) | — |



### RET-T064

**RET-F043 · Mapping · Delete mapping row · PASS**

**Scenario** — Delete then import a replacement, refresh and verify expected row identities and no stale settings.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Previously removed three fields and imported distinct seven-row workbook. | Re-import, reload Mapping and inspect its rules and field labels. | Only replacement rows remain and settings reflect current draft. | {"rows": 7, "last": "Trailer Net Salary", "settingsEmpty": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:67) | — |



### RET-T065

**RET-F044 · Mapping · Include Header Row · PASS**

**Scenario** — Run with Include Header Row on/off, keeping actual H layout, and compare file rows vs result counts.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic two-company payroll and seven mappings; includeHeader on/off. | POST, run, PUT, rerun, compare generated values and storage. | 10 data rows per run including H/D/T, optional heading only changes first output line. | {"hdtQueries": ["D", "H", "T"], "firstWithoutHeading": ["Audit Beta"], "runCounts": [10, 10], "storedAcrossRuns": 20} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:23) | — |



### RET-T066

**RET-F045 · Mapping · Mapping field identity · PASS**

**Scenario** — Set Field Name that matches source and one sourced via Mapping Column; inspect headings and stored keys.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Amount and Alias; 0/INT_MAX; -1,1.5,NaN,INT_MAX+1,empty; pad 1000/1001. | Send payloads, GET accepted config, render fixtures and compare exact output. | Accepted bounds saved, aliases used, invalid input rejected, padding cap enforced. | {"apiIntBoundary": "0 and 2147483647 persisted", "badVariantsPerField": 5, "padding": [[1000, 200], [1001, 422]]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:26) | — |



### RET-T067

**RET-F045 · Mapping · Mapping field identity · PASS**

**Scenario** — Try blank field, 255/256 characters, duplicate case-varied names in one type, same name across different types and 100/101 mapping columns.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Field blank/255/256, x/X duplicate, duplicate across H/D, 100/101 layouts. | Create and run every fixture. | Only valid IDs/layout reach output. | {"saveLengths": [422, 201, 422], "caseDuplicate": 422, "crossType": 200, "100vs101": [200, 422]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:87) | — |



### RET-T068

**RET-F046 · Mapping · Mapping positions and lengths · PASS**

**Scenario** — Save blanks, 0 and SQL int max in Start Position/Length; check persisted fields and runtime padding independence.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Amount and Alias; 0/INT_MAX; -1,1.5,NaN,INT_MAX+1,empty; pad 1000/1001. | Send payloads, GET accepted config, render fixtures and compare exact output. | Accepted bounds saved, aliases used, invalid input rejected, padding cap enforced. | {"apiIntBoundary": "0 and 2147483647 persisted", "badVariantsPerField": 5, "padding": [[1000, 200], [1001, 422]]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:27) | — |



### RET-T069

**RET-F046 · Mapping · Mapping positions and lengths · PASS**

**Scenario** — Try negative, decimal, nonnumeric and above SQL int for both numeric fields; verify Length 1000/1001 in left-padding run.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Amount and Alias; 0/INT_MAX; -1,1.5,NaN,INT_MAX+1,empty; pad 1000/1001. | Send payloads, GET accepted config, render fixtures and compare exact output. | Accepted bounds saved, aliases used, invalid input rejected, padding cap enforced. | {"apiIntBoundary": "0 and 2147483647 persisted", "badVariantsPerField": 5, "padding": [[1000, 200], [1001, 422]]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:28) | — |



### RET-T070

**RET-F047 · Mapping · Record Type selector · PASS**

**Scenario** — Configure H, D, T and blank record type across CSV and payroll fixtures; verify generated layouts.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic two-company payroll and seven mappings; includeHeader on/off. | POST, run, PUT, rerun, compare generated values and storage. | 10 data rows per run including H/D/T, optional heading only changes first output line. | {"hdtQueries": ["D", "H", "T"], "firstWithoutHeading": ["Audit Beta"], "runCounts": [10, 10], "storedAcrossRuns": 20} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:24) | — |



### RET-T071

**RET-F047 · Mapping · Record Type selector · PASS**

**Scenario** — API inject unsupported type to disposable payroll/CSV fixtures; note save vs run validation, blank default and mixed shape.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Record Type=unsupported and blank in payroll/CSV. | POST and Run the appropriate data. | Payroll rejects on save, CSV rejects on run, blank acts as D. | {"payrollInvalidSave": 422, "csvInvalidRun": 422, "blankInterpreted": "Detail"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:31) | — |



### RET-T072

**RET-F048 · Mapping · Mapping fallback value · PASS**

**Scenario** — Use missing/blank source with a provided fallback, then whitespace and numeric zero; compare formatted values.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Missing column fallback F; empty/space/zero raw Amount; 255/256 fallback length. | POST and Run valid and invalid mappings. | Render fallback only for missing/empty, format error at run, reject oversize at save. | {"rows": [["Missing", "Amount"], ["F", "D"], ["F", " "], ["F", "0"]], "fallback255": "saved; rejected by numeric formatter on run", "fallback256": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:29) | — |



### RET-T073

**RET-F048 · Mapping · Mapping fallback value · PASS**

**Scenario** — Test optional defaults with lengths 255/256 and a default that cannot parse under selected Format.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Missing column fallback F; empty/space/zero raw Amount; 255/256 fallback length. | POST and Run valid and invalid mappings. | Render fallback only for missing/empty, format error at run, reject oversize at save. | {"rows": [["Missing", "Amount"], ["F", "D"], ["F", " "], ["F", "0"]], "fallback255": "saved; rejected by numeric formatter on run", "fallback256": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:30) | — |



### RET-T074

**RET-F049 · Mapping · Source column selector · PASS**

**Scenario** — Inspect catalog options for current payroll and legacy CSV, and select Same as Field Name.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Saved payroll and legacy CSV jobs. | Observe both Mapping Column options and select Same as Field Name. | Payroll catalog narrower than CSV, fallback selection works. | {"payroll": ["Same as Field Name", "Company Name", "Employee Count", "Net Salary Total", "Pay Date", "Record Type"], "csvCount": 36} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:77) | — |



### RET-T075

**RET-F049 · Mapping · Source column selector · PASS**

**Scenario** — Verify option labels derive from DB description/key, dedupe and inferred type; try source with different case.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Temporary XML with hours only, duplicate mapping description Pay Date and newline delimiter in scratch. | Call real options function with temporary file; compare and remove synthetic catalog rows. | Empty missing sections; duplicate label once; invalid delimiter excluded; normalized dates. | {"missingMinutesSection": [], "hoursOverride": ["7"], "payDateType": "date", "payDateLookupOccurrences": 1, "invalidDelimiterFiltered": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:98) | — |



### RET-T076

**RET-F050 · Mapping · Field format selector · PASS**

**Scenario** — Choose number/date/text type switches and verify compatible formats remain while incompatible clears.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Pay Date / YYYY-MM-DD; change to Net Salary Total then Same as Field Name. | Switch source between date and numeric while format chosen. | Incompatible old format clears and date/numeric names are available. | {"dateCleared": true, "numericCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:37) | — |



### RET-T077

**RET-F050 · Mapping · Field format selector · PASS**

**Scenario** — Verify all listed formats for text, date, number, phone, email and SSN across mapped and inferred types.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Company Name, Pay Date, Net Salary Total selections; Employee Work Email, Phone, SSN inferred from field labels | Open each row Format, compare option labels, Escape back to grid | Text/date/number/email/phone/SSN show type-specific options and No format | {"Company Name":["No format","LA - Left Justified","Trim Whitespace","Uppercase","Lowercase"],"Pay Date":["No format","MMDDYYYY - Date","MM/DD/YYYY","YYYY-MM-DD","YYYYMMDD","DD/MM/YYYY","DD-MM-YYYY"],"Net Salary Total":["No format","0 - Integer","0.00 - Decimal","0.0000 - Decimal","#,##0","#,##0.00"],"Employee Work Email":["No format","Trim Whitespace","Lowercase"],"Phone":["No format","Digits Only","(XXX) XXX-XXXX","XXX-XXX-XXXX","International (+)"],"SSN":["No format","XXXXXXXXX - SSN","XXX-XX-XXXX - SSN"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:81) | — |



### RET-T078

**RET-F051 · Mapping · File Settings entry points · PASS**

**Scenario** — From Mapping click gear and separate plus; confirm both open the same modal and do not modify mapping rows.

**Preconditions** — Isolated draft with the stated rows and a synthetic payroll or CSV source.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Mapping with seven imported inputs. | Open gear and plus, cancel both before mapping edits. | Both open File Settings; mapping count unchanged. | {"controls": ["Manage dataset settings", "Add mapping rule"], "count": 7} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:38) | — |



### RET-T079

**RET-F052 · Shared · Searchable picker interactions · PASS**

**Scenario** — Exercise search, no match, click, Arrow Up/Down, Enter, Escape, click-outside and scroll positioning for picker.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Standard Build Frequency choices Weekly and Bi-Weekly, impossible query and click outside. | Keyboard open, filter, arrow selection, Enter and Escape; inspect responsive positioning from viewport evidence. | No matches state, keyboard selection and dismissal function. | {"chosen": "Bi-Weekly", "outOfMatch": true, "escapeCloses": true, "outsideCloses": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:71) | — |



### RET-T080

**RET-F052 · Shared · Searchable picker interactions · NOT TESTED**

**Scenario** — Exercise option loading/error, remove a previously saved catalog value, and check specialized client/custom placeholders.

**Preconditions** — Isolated browser with the relevant wizard, dashboard or modal available.

**Test data and actions** — See the planned variants above. These were not executed as a complete scenario.

**Expected** — The documented control, guard or recovery behavior holds for each planned variant.

**Actual and evidence** — No direct result recorded for this scenario.

**Remaining gap** — Picker and custom search ran in other browser scenarios and partial catalog responses were observed at the API. Catalog removal of a selected value and loading/error UI together were not exercised.


### RET-T081

**RET-F053 · Settings · Open saved settings · PASS**

**Scenario** — Reopen settings on saved job and compare displayed rule rows, positions and normalized decimals.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Saved UI Field Checks sort Company Name ASC and Employee Count >=1. | Open saved Edit modal and inspect rule state. | Saved source/direction and normalized value display. | {"criteria": "Employee Count >= 1.00", "sorting": "Company Name ASC"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:53) | — |



### RET-T082

**RET-F054 · Settings · Add sorting rule · NOT TESTED**

**Scenario** — Add two sort rules in Add and Edit; compare initial direction, sequence and saved priorities.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | New rule placeholders in previous Add test; two new rules in Edit. | Add two new sort rows in each context, compare directions. | Blank in Add, ASC in Edit. | {"Add": ["", ""], "Edit": ["ASC", "ASC"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:54) | — |


**Remaining gap** — Add/Edit initial rule directions and saved positive priorities were checked separately. Adding, saving and reopening two newly added rows in both modes was not completed.


### RET-T083

**RET-F054 · Settings · Add sorting rule · PASS**

**Scenario** — Save sparse or legacy signed sort priorities and verify edit shows canonical direction and re-save renumbers positively.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Raw legacy priorities -2/2 and no CSV_SORT metadata. | Seed scratch config, GET, Run, re-save, compare actual persisted priorities. | Read DESC/ASC then convert to positive ranks without changing directions. | {"job": 107, "beforeRaw": [-2, 2], "read": [{"orderBy": "1", "mappingColumn": "Amount", "direction": "DESC"}, {"orderBy": "2", "mappingColumn": "Label", "direction": "ASC"}], "afterRaw": [1, 2]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:88) | — |



### RET-T084

**RET-F055 · Settings · Change/delete sorting rule · PASS**

**Scenario** — Change both direction and column, delete first rule, apply, and check remaining sort order.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Pay Date DESC and Company Name DESC sorting; delete first and set remaining ASC. | Edit column, direction, delete first rule and apply. | Only Company Name ASC remains. | {"remaining": "Company Name ASC"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:48) | — |



### RET-T085

**RET-F056 · Settings · Add conditional rule · PASS**

**Scenario** — Add a condition and verify empty source/operator/value and accessible label indexes.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | One Add conditional rule in otherwise blank modal. | Inspect label index and initially unselected source/operator/value. | Empty values in first row. | {"operator": "", "value": "", "mapping": "Select a column\n⌄"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:39) | — |



### RET-T086

**RET-F056 · Settings · Add conditional rule · PASS**

**Scenario** — Select each supported comparison operator and verify enum and metadata write.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | CSV Amount=-1.5,0,0.5,1.50,2; threshold .50; AND variant with invalid Other only after a false first comparison. | PUT each operator, inspect saved threshold and compare runs with hand-listed outputs. | Exact eight comparison results and left-to-right AND short-circuit. | {"threshold": "0.50", "operatorRows": {"=": ["0.5"], "==": ["0.5"], "!=": ["-1.5", "0", "1.50", "2"], "<>": ["-1.5", "0", "1.50", "2"], "<": ["-1.5", "0"], "<=": ["-1.5", "0", "0.5"], ">": ["1.50", "2"], ">=": ["0.5", "1.50", "2"]}, "AND_shortCircuit": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:53) | — |



### RET-T087

**RET-F057 · Settings · Change/delete conditional rule · PASS**

**Scenario** — Change each condition value, delete a condition and verify unrelated sort rules are unchanged.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Two conditions, existing Pay Date DESC rule. Change source/operator/value and delete first condition. | Apply added rule, edit/delete through modal; compare remaining condition and unchanged sort. | Only condition rows change; remaining criteria retain values and sort unaffected. | {"remaining": "0.50", "sortDirection": "DESC"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:75) | — |



### RET-T088

**RET-F057 · Settings · Change/delete conditional rule · PASS**

**Scenario** — Use an unsupported saved operator and verify its disabled display and application validation.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Legacy CSV condition Amount badop 2 with synthetic fixture. | Insert in scratch DB and GET; browser opens it separately. | Server returns unsupported saved condition for the UI. | {"job": 108, "condition": [{"mappingColumn": "Amount", "condition": "badop", "value": "2.00"}]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:89) | — |
| isolated browser | Scratch legacy CSV fixture with badop condition. | Open settings, inspect unsupported option, attempt Apply. | Unsupported saved option disabled and rejected by Apply. | {"option": "badop (unsupported)", "enabled": false, "applyRejected": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:79) | — |



### RET-T089

**RET-F058 · Settings · Custom rule column search · PASS**

**Scenario** — Try custom CSV rule name and noncatalog payroll name. Verify offered custom selection and save/run validation.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | ExternalAuditColumn missing from catalog but in CSV with 2,0,3; same custom name for payroll | POST Run CSV after save; submit payroll invalid custom | CSV saves and uses sort/filter, payroll custom source fails validation | {"csvSortedAndFiltered": [["Amount"], ["22"], ["11"]], "csvSortRows": [{"sort_order": 1, "mapping_column": "ExternalAuditColumn"}], "payrollSaveStatus": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:134) | — |
| isolated browser | Payroll custom sort source UnlistedAuditQ; valid company and email tags. | Select Use custom column, Apply modal, Finish. | Payroll unsupported source rejected on save. | {"uiOffered": true, "server422": true, "message": "  - alert: mapping — The Company Payroll Report cannot sort or filter by \"UnlistedAuditQ\"."} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:47) | — |



### RET-T090

**RET-F059 · Settings · Apply settings · PASS**

**Scenario** — Apply valid and incomplete sort and conditional rows separately; check closure and exact alert.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Direction/column missing; initially blank condition; not numeric, -.5 and 1e0. | Apply after each invalid/current value and inspect modal closure. | Incomplete/invalid rejected. Signed fraction/exponent accepted as draft. | {"sortGuard": true, "conditionGuard": true, "invalidNumericRejected": true, "accepted": ["-.5", "1e0"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:40) | — |



### RET-T091

**RET-F059 · Settings · Apply settings · PASS**

**Scenario** — Apply invalid value, exponent form, blank and signed fraction such as -.5; confirm API precision separately.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Direction/column missing; initially blank condition; not numeric, -.5 and 1e0. | Apply after each invalid/current value and inspect modal closure. | Incomplete/invalid rejected. Signed fraction/exponent accepted as draft. | {"sortGuard": true, "conditionGuard": true, "invalidNumericRejected": true, "accepted": ["-.5", "1e0"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:41) | — |



### RET-T092

**RET-F060 · Settings · Clear settings draft · PASS**

**Scenario** — Clear settings and Cancel, reopen then Clear and Apply; compare resulting parent draft lists.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Applied nonempty sort/condition modal rows. | Clear and Cancel; reopen; Clear and Save & Continue; reopen. | Cancel preserves prior draft; Apply commits empty sets. | {"cancelPreserved": true, "applyCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:43) | — |



### RET-T093

**RET-F061 · Settings · Close settings without applying · PASS**

**Scenario** — Close dialog by Cancel, backdrop and Escape, then verify draft discard and focus restoration.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Edit File Settings with two existing sorts and unsaved third. | Close with Cancel, Escape and backdrop; reopen after dismissal and inspect focus. | Unapplied row discarded; parent control focus restored. | {"cancelFocus": {"label": "Manage dataset settings", "tag": "BUTTON", "text": ""}, "escapeFocus": {"label": "Manage dataset settings", "tag": "BUTTON", "text": ""}, "backdropDismiss": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:70) | — |



### RET-T094

**RET-F061 · Settings · Close settings without applying · FAIL**

**Scenario** — Use Tab/Shift+Tab with a portalled mapping selector open, Escape at nested levels and verify focus return.

**Preconditions** — Isolated mapping draft with File Settings available or corresponding saved job.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Edit File Settings with two sorts and one condition; search input of first sort picker. | Focus portalled picker search, then press Tab. | Focus proceeds to the adjacent logical control, not an unrelated end-of-dialog action. | {"from": {"label": "Search Sorting Order: Mapping Column 1", "tag": "INPUT", "text": ""}, "to": {"label": "Delete Conditional Statements: row 1", "tag": "BUTTON", "text": ""}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:69) · [Screenshot](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/RET-B008-picker-focus.jpg) | RET-B008 |



### RET-T095

**RET-F062 · Subscriptions · Merge Files checkbox · PASS**

**Scenario** — Toggle Merge Files in subscribed fixture; compare flag storage and manual output before and after.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | UI Field Checks job created in isolated browser; one real draft target and one completely blank row; controlled email tags. | Compare UI-created DB data; flip merge flag via partial PUT then compare manual CSV bytes. | Target ID encoded -2 and one persisted row; email tags preserved; manual bytes unchanged by Merge Files. | {"uiCreatedJob": 101, "subscriptionIdRaw": -2, "companyId": 1, "blankRowOmitted": true, "mailTags": "enter@example.invalid, comma@example.invalid, new@example.invalid, line@example.invalid", "manuallyGeneratedEqual": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:100) | — |



### RET-T096

**RET-F063 · Subscriptions · Add/Delete subscription row · PASS**

**Scenario** — Add, delete and reorder-by-deleting subscription drafts; verify no empty row persisted.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | UI Field Checks job created in isolated browser; one real draft target and one completely blank row; controlled email tags. | Compare UI-created DB data; flip merge flag via partial PUT then compare manual CSV bytes. | Target ID encoded -2 and one persisted row; email tags preserved; manual bytes unchanged by Merge Files. | {"uiCreatedJob": 101, "subscriptionIdRaw": -2, "companyId": 1, "blankRowOmitted": true, "mailTags": "enter@example.invalid, comma@example.invalid, new@example.invalid, line@example.invalid", "manuallyGeneratedEqual": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:101) | — |
| isolated browser | Saved synthetic company 1/email row; two added blank rows and one removed before save. | Create, delete draft row, save, reopen subscriptions and inspect rows. | Blank omitted and chosen company persisted. | {"emailCount": 1, "secondRowExists": 0, "company": "1 - Audit Alpha\n⌄", "merged": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:55) | — |



### RET-T097

**RET-F064 · Subscriptions · Payroll company picker · PASS**

**Scenario** — Choose visible payroll company, save, and compare signed DB value and rehydrated company display.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | UI Field Checks job created in isolated browser; one real draft target and one completely blank row; controlled email tags. | Compare UI-created DB data; flip merge flag via partial PUT then compare manual CSV bytes. | Target ID encoded -2 and one persisted row; email tags preserved; manual bytes unchanged by Merge Files. | {"uiCreatedJob": 101, "subscriptionIdRaw": -2, "companyId": 1, "blankRowOmitted": true, "mailTags": "enter@example.invalid, comma@example.invalid, new@example.invalid, line@example.invalid", "manuallyGeneratedEqual": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:102) | — |
| isolated browser | Saved synthetic company 1/email row; two added blank rows and one removed before save. | Create, delete draft row, save, reopen subscriptions and inspect rows. | Blank omitted and chosen company persisted. | {"emailCount": 1, "secondRowExists": 0, "company": "1 - Audit Alpha\n⌄", "merged": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:56) | — |



### RET-T098

**RET-F064 · Subscriptions · Payroll company picker · PASS**

**Scenario** — Use missing, duplicate company name and unknown ID conditions in disposable data. Verify catalog and grouping/mail errors.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Payroll CLIENT format, unknown company 999, duplicate Audit Alpha name in scratch DB. | Compare options and Run before/after catalog duplicate, then remove synthetic duplicate. | Unknown company rejected; duplicate removed from picker and run fails resolution. | {"uniquePickerAfterDuplicate": {"2": "Audit Beta"}, "missingOrUnknownIdAtSave": 422, "ambiguousAtRun": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:90) | — |



### RET-T099

**RET-F065 · Subscriptions · CSV Clients picker · PASS**

**Scenario** — Use CSV mode with saved/default/custom client options; verify integer conversion and leading zeros.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Saved CSV subscription 720 and added custom 000031 plus client@example.invalid. | Open CSV mode, add custom numeric client, save, reopen. | Legacy and typed client IDs display; zero padding is normalized after save. | ["31⌄", "720⌄"] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:78) | — |



### RET-T100

**RET-F065 · Subscriptions · CSV Clients picker · PASS**

**Scenario** — Try IDs 0, INT_MAX, excess, decimal, negative, nonnumeric, leading zeroes and displayed selected-client text.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Leading-zero client, INT_MAX, six invalid strings, payroll company 2. | POST, GET and inspect client-detail rows. | Normalize digits, reject invalid API IDs, encode company 2 as -3. | {"clientIds": [0, 2147483647], "invalidVariants": 6, "companyEncoding": [2, -3], "email": "b@example.invalid"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:32) | — |



### RET-T101

**RET-F066 · Subscriptions · Email entry and commit · PASS**

**Scenario** — Commit email with Enter, comma, semicolon and blur; invalid text stays editable and blocks save.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Synthetic .invalid addresses and malformed bad-address. | Commit with Enter, comma, semicolon and blur, then try Finish with malformed address. | Four valid tags and inline rejection; no successful save with malformed input. | {"validTags": 4, "invalidAlert": true, "sameStep": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:44) | — |



### RET-T102

**RET-F066 · Subscriptions · Email entry and commit · PASS**

**Scenario** — Try 64/65 local-part and 254/255 complete-address boundaries, malformed syntax and case variants.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic addresses with exact character lengths and both target keys. | POST variants and read target-only job. | Accept 254 individual/255 total, reject 255 individual/256 total, 65 local part and dual target. | {"singleMax": 254, "combinedAccepted": 255, "combinedRejected": 256, "localRejected": 65, "bothTargetTypes": 422, "targetOnly": "accepted"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:34) | — |



### RET-T103

**RET-F067 · Subscriptions · Paste and deduplicate email · PASS**

**Scenario** — Paste comma/semicolon/newline-separated addresses into selected text and compare deduped tags.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Selected text replace me; pasted comma@example.invalid; new@example.invalid [newline] line@example.invalid, comma@example.invalid. | Paste multivalued text into selected input. | Selected text replaced, repeated tag deduped, new tags created. | {"uniqueComma": 1, "new": 1, "line": 1, "draft": ""} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:46) | — |



### RET-T104

**RET-F067 · Subscriptions · Paste and deduplicate email · PASS**

**Scenario** — Compare exact-string UI dedupe with case-insensitive scheduled delivery behavior; no real email addresses.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | CASE@example.invalid entered twice, then case@example.invalid | Commit each by Enter and inspect chips; compare with the independently executed deduplication tests in the SMTP harness | Exact duplicate collapses in the UI, mixed-case variants collapse during scheduler delivery | Two UI tags retained, one for each case; scheduler recipient normalization sent one message per mailbox in local capture. | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:82) | — |



### RET-T105

**RET-F068 · Subscriptions · Remove email tag · PASS**

**Scenario** — Remove one email by X and last by Backspace on empty input without affecting remaining text.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated browser | Four tagged recipients, all example.invalid. | Remove semi tag through X and blur tag using Backspace on empty input. | Two chosen tags disappear and rest remain. | ["          - button \"Remove enter@example.invalid\":", "          - button \"Remove comma@example.invalid\":"] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:45) | — |



### RET-T106

**RET-F069 · Subscriptions · Subscription save guards · PASS**

**Scenario** — Compare no rows, empty rows, target only, email only and missing/unknown company during Finish.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | UI Field Checks job created in isolated browser; one real draft target and one completely blank row; controlled email tags. | Compare UI-created DB data; flip merge flag via partial PUT then compare manual CSV bytes. | Target ID encoded -2 and one persisted row; email tags preserved; manual bytes unchanged by Merge Files. | {"uiCreatedJob": 101, "subscriptionIdRaw": -2, "companyId": 1, "blankRowOmitted": true, "mailTags": "enter@example.invalid, comma@example.invalid, new@example.invalid, line@example.invalid", "manuallyGeneratedEqual": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:103) | — |
| isolated browser | Populated row 1; row 2 has email but no company, then made fully blank. | Try Finish and observe client guard; clear email and retain blank row. | Email-only row blocks until resolved or empty. | {"missingCompanyGuard": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:49) | — |



### RET-T107

**RET-F069 · Subscriptions · Subscription save guards · PASS**

**Scenario** — Use combined emails at 255/256 characters, blank target-plus-empty mail, and both companyId and client API values.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic addresses with exact character lengths and both target keys. | POST variants and read target-only job. | Accept 254 individual/255 total, reject 255 individual/256 total, 65 local part and dual target. | {"singleMax": 254, "combinedAccepted": 255, "combinedRejected": 256, "localRejected": 65, "bothTargetTypes": 422, "targetOnly": "accepted"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:35) | — |



### RET-T108

**RET-F070 · Subscriptions · Finish new job · PASS**

**Scenario** — Complete new payroll job with all sections in disposable data; verify 201, job ID and transactional rows.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 55, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:36) | — |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 171, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:124) | — |



### RET-T109

**RET-F071 · Subscriptions · Finish existing job · PASS**

**Scenario** — Update existing job with changed configuration; verify same ID, actual child replacement and existing history.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 55, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:37) | — |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 171, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:125) | — |



### RET-T110

**RET-F071 · Subscriptions · Finish existing job · PASS**

**Scenario** — Use PUT with omitted sections versus explicit empty values; check preservation, validation and clear behavior.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 55, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:38) | — |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 171, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:126) | — |



### RET-T111

**RET-F071 · Subscriptions · Finish existing job · FAIL**

**Scenario** — Edit a previously run fixture without running it; observe Last Run Date given SQL 45 timestamp and list derivation.

**Preconditions** — Isolated subscriptions step or API draft with synthetic recipients.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"job": 38, "oldDate": "2026-10-01", "description": "Edited without running"} | GET list; PUT description only; GET list and SELECT history without running again. | Displayed Last Run Date remains 2026-10-01. | {"displayBefore": "2026-10-01T09:00:00", "displayAfter": "2026-11-17T00:00:00", "historyStill": "2026-10-01 09:00:00"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:21) | RET-B003 |
| isolated HTTP API and SQL Server | {"job": 154, "oldDate": "2026-10-01", "description": "Edited without running"} | GET list; PUT description only; GET list and SELECT history without running again. | Displayed Last Run Date remains 2026-10-01. | {"displayBefore": "2026-10-01T09:00:00", "displayAfter": "2026-11-17T00:00:00", "historyStill": "2026-10-01 09:00:00"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:122) | RET-B003 |



### RET-T112

**RET-F072 · Save · Create retry and concurrent guard · PASS**

**Scenario** — Double-click Finish and simulate retry with same key/body; verify one insert and one returned job ID.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Identical JSON with concurrent requests and same key; changed body and 129-character key. | POST twice concurrently, inspect DB; retry changed/invalid header. | One insert and same ID; 409 changed body and 422 invalid key. | {"job": 56, "identicalConcurrentCountInDb": 1, "changed": 409, "header129": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:40) | — |
| isolated browser | Double-click Finish on synthetic QA job and 650 ms delay. API separately exercises identical concurrent retry. | Double-click Finish and inspect proxy trace. | Exactly one creation POST and 201. | [{"method": "POST", "path": "/api/v1/retirement-builder/jobs", "status": 201, "ms": 754}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:51) | — |



### RET-T113

**RET-F072 · Save · Create retry and concurrent guard · FAIL**

**Scenario** — Send same key with changed payload, near-boundary invalid key, restart/expiry or concurrent worker requests.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Identical JSON with concurrent requests and same key; changed body and 129-character key. | POST twice concurrently, inspect DB; retry changed/invalid header. | One insert and same ID; 409 changed body and 422 invalid key. | {"job": 56, "identicalConcurrentCountInDb": 1, "changed": 409, "header129": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:41) | — |
| isolated API, SQL and controlled execution | Same idempotency header and JSON to two production-code backend processes with same isolated DB. | POST to process 8084; replay exact request to independent process 8086; inspect rows. | Replay across serving processes returns existing ID without duplicate. | {"worker8084": 116, "worker8086": 117, "sqlMatches": 2, "bothHTTP": 201} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:108) | RET-B010 |



### RET-T114

**RET-F073 · Save · Save failure handling · NOT TESTED**

**Scenario** — Simulate 422 field detail, non-JSON error, network error and DB error; inspect usable UI recovery.

**Preconditions** — Isolated browser with the relevant wizard, dashboard or modal available.

**Test data and actions** — See the planned variants above. These were not executed as a complete scenario.

**Expected** — The documented control, guard or recovery behavior holds for each planned variant.

**Actual and evidence** — No direct result recorded for this scenario.

**Remaining gap** — Run and Edit error states and API validation/persistence errors were exercised. The complete set of injected create failures followed by retry through Finish was not run.


### RET-T115

**RET-F074 · Save · Persist file type and job metadata · PASS**

**Scenario** — Verify labels vs literal delimiters in the DB including legacy labels before re-save and file naming codes.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | CSV, CSV_PIPE, CSV_TAB, CSV_SEMI, Tilde, newline catalog delimiter. | Submit labels; exercise old DB values without conversion, Run, then PUT; check invalid catalog. | Legacy run works, normal save writes byte, invalid settings are rejected or excluded. | {"CSV": 44, "CSV_PIPE": 124, "CSV_TAB": 9, "CSV_SEMI": 59, "unknown": 422, "newlineCatalogEntry": "excluded"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:6) | — |



### RET-T116

**RET-F075 · Save · Persist schedule and mappings · PASS**

**Scenario** — Check saved schedule row, null datetime manual defaults and 1-based mapping sequences in dataset 1.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 55, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:39) | — |
| isolated HTTP API and SQL Server | Full payroll job, Tab, seven mappings, two sort rules, conditional, company subscriber; partial PUT and explicit empty arrays. | POST→Run→GET→PUT→GET/SQL and reject empty mappings. | 201, update same ID, omitted sections preserved, subscriptions cleared, history retained. | {"job": 171, "sameID": true, "HDT": 3, "mappings": 7, "storedHistory": 10, "subscriptionsCleared": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:127) | — |



### RET-T117

**RET-F075 · Save · Persist schedule and mappings · PASS**

**Scenario** — Verify uppercase/lowercase frequency mapping, weekday persisted indexes, data row sequences and null/blank legacy fields.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Daily/Weekly/Bi-Weekly/Monthly, Sunday/Monday/Tuesday/Saturday, 12AM/12PM/1AM/11PM. | POST four schedules and manual job, compare DB fields and timestamp. | D/W/B/M, weekday 0/1/2/6, times 00:00/12:59/01:05/23:08. | [{"frequency": "Daily", "stored": "D", "week": 0, "time": "00:00:00"}, {"frequency": "Weekly", "stored": "W", "week": 1, "time": "12:59:00"}, {"frequency": "Bi-Weekly", "stored": "B", "week": 2, "time": "01:05:00"}, {"frequency": "Monthly", "stored": "M", "week": 6, "time": "23:08:00"}, {"manual": 28, "date": null, "lowercase": 422}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:16) | — |
| isolated HTTP API and SQL Server | Daily/Weekly/Bi-Weekly/Monthly, Sunday/Monday/Tuesday/Saturday, 12AM/12PM/1AM/11PM. | POST four schedules and manual job, compare DB fields and timestamp. | D/W/B/M, weekday 0/1/2/6, times 00:00/12:59/01:05/23:08. | [{"frequency": "Daily", "stored": "D", "week": 0, "time": "00:00:00"}, {"frequency": "Weekly", "stored": "W", "week": 1, "time": "12:59:00"}, {"frequency": "Bi-Weekly", "stored": "B", "week": 2, "time": "01:05:00"}, {"frequency": "Monthly", "stored": "M", "week": 6, "time": "23:08:00"}, {"manual": 144, "date": null, "lowercase": 422}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:121) | — |



### RET-T118

**RET-F076 · Save · Persist subscriptions · PASS**

**Scenario** — Check saved client ID versus payroll signed-company key and combined email text length.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Leading-zero client, INT_MAX, six invalid strings, payroll company 2. | POST, GET and inspect client-detail rows. | Normalize digits, reject invalid API IDs, encode company 2 as -3. | {"clientIds": [0, 2147483647], "invalidVariants": 6, "companyEncoding": [2, -3], "email": "b@example.invalid"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:33) | — |



### RET-T119

**RET-F077 · Save · Persist sort, condition, and queries · PASS**

**Scenario** — Check saved three payroll queries/Detail rule text, CSV_SORT, positive sort rows and normalized condition rows.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Sparse sort priorities 7/2, 1.005 equality threshold, CSV heading with bracket and comma. | POST jobs, inspect rjob_query and sorted-rule rows, GET. | Three H/D/T templates, normalized payroll rules and exact CSV quote roundtrip. | {"payroll": [57, "[Employee Count] = 1.01", "ORDER BY [Company Name] ASC, [Pay Date] DESC"], "csv": [58, "CSV_SORT", "ORDER BY [A]],B] DESC"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:42) | — |
| isolated HTTP API and SQL Server | Sparse sort priorities 7/2, 1.005 equality threshold, CSV heading with bracket and comma. | POST jobs, inspect rjob_query and sorted-rule rows, GET. | Three H/D/T templates, normalized payroll rules and exact CSV quote roundtrip. | {"payroll": [173, "[Employee Count] = 1.01", "ORDER BY [Company Name] ASC, [Pay Date] DESC"], "csv": [174, "CSV_SORT", "ORDER BY [A]],B] DESC"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:130) | — |



### RET-T120

**RET-F077 · Save · Persist sort, condition, and queries · PASS**

**Scenario** — Test finite Decimal threshold boundaries, midpoint rounding, negative zero, signed exponent, 16+2 overflow and invalid finite checks.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Signed/zero/exponent, half ties, SQL boundary and nonfinite decimal strings. | PUT each rule and compare persisted values/rejections. | Round half-up to two digits, reject overflow/nonfinite. | {"-1.005": "-1.01", "1.005": "1.01", "-0.001": "0.00", "1e3": "1000.00", "9999999999999999.994": "9999999999999999.99", "9999999999999999.995": 422, "NaN": 422, "Infinity": 422, "-1e30": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:44) | — |



### RET-T121

**RET-F077 · Save · Persist sort, condition, and queries · PASS**

**Scenario** — Use bracket/comma in CSV source sort labels and compare stored quote escaping and exact parse round trip.

**Preconditions** — Isolated API/draft and synthetic configuration; use seeded job when specified.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Sparse sort priorities 7/2, 1.005 equality threshold, CSV heading with bracket and comma. | POST jobs, inspect rjob_query and sorted-rule rows, GET. | Three H/D/T templates, normalized payroll rules and exact CSV quote roundtrip. | {"payroll": [57, "[Employee Count] = 1.01", "ORDER BY [Company Name] ASC, [Pay Date] DESC"], "csv": [58, "CSV_SORT", "ORDER BY [A]],B] DESC"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:43) | — |
| isolated HTTP API and SQL Server | Sparse sort priorities 7/2, 1.005 equality threshold, CSV heading with bracket and comma. | POST jobs, inspect rjob_query and sorted-rule rows, GET. | Three H/D/T templates, normalized payroll rules and exact CSV quote roundtrip. | {"payroll": [173, "[Employee Count] = 1.01", "ORDER BY [Company Name] ASC, [Pay Date] DESC"], "csv": [174, "CSV_SORT", "ORDER BY [A]],B] DESC"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:131) | — |



### RET-T122

**RET-F078 · Integration · API options/catalog loading · PASS**

**Scenario** — Compare options response values to SQL/XML and dropdowns. Record partial lookup failures and default messages.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic companies and copied lookup catalogs; 1–12 hour and 00–59 minute options. | GET options and compare catalog, code and XML values with expected options. | Five file formats, seven naming options, correct enums and two synthetic companies. | {"fileFormats": ["Comma", "Pipe", "Semicolon", "Space", "Tab"], "outputFileNameFormats": [{"label": "File Name", "value": "FILENAME"}, {"label": "Client ID", "value": "CLIENT"}, {"label": "Payday", "value": "PAYDAY"}, {"label": "File Name + Client ID", "value": "FILENAME_CLIENT"}, {"label": "File Name + Payday", "value": "FILENAME_PAYDAY"}, {"label": "Client ID + Payday", "value": "CLIENT_PAYDAY"}, {"label": "File Name + Client ID + Payday", "value": "FILENAME_CLIENT_PAYDAY"}], "recordTypes": ["Header", "Detail", "Trailer"], "buildFrequencies": ["Daily", "Weekly", "Bi-Weekly", "Monthly"], "payrollCompanies": {"1": "Audit Alpha", "2": "Audit Beta"}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:1) | — |
| isolated API, SQL and controlled execution | Healthy test API on 8084 and fault-only API on 8085 with synthetic SQL connection exception. | GET health, db health, jobs and options on both test instances. | Healthy vs degraded; outage health 200 with degraded JSON; list fails and options return XML-only partial values. | {"degradedHealthHTTP": 200, "body": {"status": "degraded", "database": "unavailable"}, "dbGETJobs": 500, "dbGETOptions": 200, "catalogCounts": [0, 0, 12], "listResponse": {"detail": "Unable to load Retirement Builder jobs from the database"}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:105) | — |



### RET-T123

**RET-F078 · Integration · API options/catalog loading · PASS**

**Scenario** — Inspect missing XML section, duplicate mapping names/types, invalid delimiters and unconfigured catalogs in isolated fixture.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Temporary XML with hours only, duplicate mapping description Pay Date and newline delimiter in scratch. | Call real options function with temporary file; compare and remove synthetic catalog rows. | Empty missing sections; duplicate label once; invalid delimiter excluded; normalized dates. | {"missingMinutesSection": [], "hoursOverride": ["7"], "payDateType": "date", "payDateLookupOccurrences": 1, "invalidDelimiterFiltered": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:99) | — |



### RET-T124

**RET-F079 · Execution · Payroll procedure source · PASS**

**Scenario** — Observe procedure template call on save then job-id execution, outputs and representative mapped projection.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic two-company payroll and seven mappings; includeHeader on/off. | POST, run, PUT, rerun, compare generated values and storage. | 10 data rows per run including H/D/T, optional heading only changes first output line. | {"hdtQueries": ["D", "H", "T"], "firstWithoutHeading": ["Audit Beta"], "runCounts": [10, 10], "storedAcrossRuns": 20} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:25) | — |



### RET-T125

**RET-F079 · Execution · Payroll procedure source · PASS**

**Scenario** — Use duplicate/missing/altered payroll query records in controlled fixtures; verify exact H/D/T guard and legacy PAYROLL path.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Append one space to synthetic Detail template, then remove Detail record after normal re-save. | Run tampered and missing template fixtures; verify proper re-save restores output. | 422 safeguards, restored valid config runs. | {"alteredTemplate": 422, "missingTemplate": 422, "saveRepairs": 10} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:76) | — |
| isolated API, SQL, or direct function fixture | Historical PAYROLL query built from current legacy contract plus duplicate persisted D fixture. | Run legacy, normal PUT upgrade, duplicate D and rerun. | Legacy source works; duplicate approved marker set rejected. | {"legacyPAYROLL": 200, "duplicateDetail": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:97) | — |



### RET-T126

**RET-F079 · Execution · Payroll procedure source · BLOCKED**

**Scenario** — Fix a group with duplicate employee payroll records and NULL salary values; compare SQL COUNT(*) and SUM outcomes.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Six synthetic payroll rows, attempted repeated employee/month and NULL salary. | Calculate sums/counts independently and run; try to insert/update rows against cloned existing schema constraints. | Correct observed totals; requested duplicate/NULL input fixture may be prohibited. | {"handCalculatedDetails": [["Audit Beta", "2026-09-01", 1, "180.00"], ["Audit Beta", "2026-10-01", 1, "320.00"], ["Audit Alpha", "2026-09-01", 2, "300.00"], ["Audit Alpha", "2026-10-01", 2, "325.00"]], "constraints": {"duplicate": "IntegrityError", "nullNetSalary": "IntegrityError"}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:77) | — |


**Remaining gap** — The duplicate employee-plus-month insert and NULL net salary update returned SQL integrity errors. These input rows cannot be represented with the existing UNIQUE and NOT NULL constraints. Normal-group counts and sums were verified in T124/T135 and C08/C09.


### RET-T127

**RET-F080 · Execution · Legacy CSV file source · PASS**

**Scenario** — Run a CSV-mode fixture with job ID input file; check configured directory, encoding and missing file message.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Configured BOM CSV Amount=11, override=99, missing and oversized input. | Run with body/without, remove/replace fixture file, test media. | Correct source selected and input errors returned. | {"BOMConfigured": 11, "HTTPOverride": 99, "wrongMedia": 415, "missing": 422, "oversizeConfigured": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:45) | — |
| isolated API, SQL, or direct function fixture | BOM-enabled isolated job-ID source file with Amount 41. | Run without HTTP body, delete fixture, re-run. | Correct content then 422 missing file. | {"configured": 41, "removed": 422, "job": 112} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:94) | — |



### RET-T128

**RET-F080 · Execution · Legacy CSV file source · PASS**

**Scenario** — Compare missing, unreadable and oversized configured source files and verify error text, history and no output.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Configured BOM CSV Amount=11, override=99, missing and oversized input. | Run with body/without, remove/replace fixture file, test media. | Correct source selected and input errors returned. | {"BOMConfigured": 11, "HTTPOverride": 99, "wrongMedia": 415, "missing": 422, "oversizeConfigured": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:46) | — |
| isolated API, SQL and controlled execution | Directory at configured CSV path, HTTP payroll source override, 4.5 MB CSV grows above 10 MiB in 2 groups. | Run each using the production backend, inspect failure history and filesystem. | Unreadable source rejection, override wins, aggregate output rejected with no files. | {"unreadable": {"detail": "Could not read 118.csv in the configured report input folder."}, "history": "Failed", "override": "Synthetic Override", "aggregateInputBytes": 4500197, "outputOverCap": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:110) | — |



### RET-T129

**RET-F081 · Execution · Manual API CSV override · PASS**

**Scenario** — POST text/csv override plus empty, wrong media type and over-limit bodies; confirm chosen source and errors.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Configured BOM CSV Amount=11, override=99, missing and oversized input. | Run with body/without, remove/replace fixture file, test media. | Correct source selected and input errors returned. | {"BOMConfigured": 11, "HTTPOverride": 99, "wrongMedia": 415, "missing": 422, "oversizeConfigured": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:47) | — |
| isolated API, SQL and controlled execution | Directory at configured CSV path, HTTP payroll source override, 4.5 MB CSV grows above 10 MiB in 2 groups. | Run each using the production backend, inspect failure history and filesystem. | Unreadable source rejection, override wins, aggregate output rejected with no files. | {"unreadable": {"detail": "Could not read 118.csv in the configured report input folder."}, "history": "Failed", "override": "Synthetic Override", "aggregateInputBytes": 4500197, "outputOverCap": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:111) | — |



### RET-T130

**RET-F081 · Execution · Manual API CSV override · PASS**

**Scenario** — Test exactly 5 MiB and 5 MiB+1 with correct and incorrect request content types, including charset.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | 5 MiB exact, plus one, charset parameter, and wrong media type. | POST with HTTP and record responses. | 200 at exact, 413 over, 415 wrong media. | {"size": 5242880, "expectedCount": 59, "actualCount": 59, "overPlusOne": 413, "binaryType": 415} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:48) | — |



### RET-T131

**RET-F082 · Execution · Parent-job run eligibility · PASS**

**Scenario** — Attempt absent/disabled job and compare 404/409, no generated outputs and no orphan history rows.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Missing ID 2147483647 and seed disabled job 4. | POST Run on both and query rows/disk. | 404, 409 and no output or history. | {"missing": 404, "disabled": 409, "disabledFileOrHistory": false} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:13) | — |



### RET-T132

**RET-F083 · Execution · Source and layout validation · PASS**

**Scenario** — Use missing/duplicate headings, wrong width, missing H/T layout and missing mapped fields against correct controls.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | 9 malformed/valid CSV variants, 100/101 columns, H layout without/with incompatible record type. | POST runs using each data source. | Accept valid BOM and max limits, reject malformed/invalid/missing record types. | {"inputVariants": [422, 422, 422, 422, 422, 422, 200, 200, 422], "headingLimits": [100, 101], "typeGuard": [422, 422]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:49) | — |



### RET-T133

**RET-F083 · Execution · Source and layout validation · PASS**

**Scenario** — Test 100/101 headings and 10,000/10,001 source rows, BOM, malformed UTF-8, strict quoting and blank lines.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | 9 malformed/valid CSV variants, 100/101 columns, H layout without/with incompatible record type. | POST runs using each data source. | Accept valid BOM and max limits, reject malformed/invalid/missing record types. | {"inputVariants": [422, 422, 422, 422, 422, 422, 200, 200, 422], "headingLimits": [100, 101], "typeGuard": [422, 422]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:50) | — |



### RET-T134

**RET-F083 · Execution · Source and layout validation · FAIL**

**Scenario** — Test numeric condition source missing, unsupported record type, missing expected H/D/T kind and source field with fallback.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"job": 39, "condition": "Company Name = 3", "data": "Audit Alpha/Audit Beta"} | POST payroll job; read its condition; POST Run. | Rule is rejected before save or supports the chosen column during execution. | {"createStatus": 201, "runStatus": 422, "response": {"detail": "A condition uses a value that is not a number."}, "history": "Failed"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:22) | RET-B005 |
| isolated HTTP API and SQL Server | {"job": 155, "condition": "Company Name = 3", "data": "Audit Alpha/Audit Beta"} | POST payroll job; read its condition; POST Run. | Rule is rejected before save or supports the chosen column during execution. | {"createStatus": 201, "runStatus": 422, "response": {"detail": "A condition uses a value that is not a number."}, "history": "Failed"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:123) | RET-B005 |



### RET-T135

**RET-F084 · Execution · Detail filtering · PASS**

**Scenario** — Run filtered payroll and CSV fixtures with exact numeric threshold; compare raw criteria, D rows and payroll T rows.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Alpha Sep 100+200=300, Alpha Oct 115+210=325; Beta has one per month; payroll count=2; CSV 1,2,4,5 with 2<=Amount<5. | POST, Run, apply impossible filter and Run again. | Six payroll records with date-desc details and original matching trailer order; CSV two retained rows; empty payroll no files. | {"payroll": [["Company Name", "Pay Date", "Employee Count", "Net Salary Total"], ["Audit Beta"], ["Audit Alpha"], ["Audit Alpha", "2026-10-01", "2", "325.00"], ["Audit Alpha", "2026-09-01", "2", "300.00"], ["T", "300.00"], ["T", "325.00"]], "csvRetained": [2, 4], "payrollNoMatches": 0, "rowCount": 6} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:51) | — |
| isolated API, SQL, or direct function fixture | Two synthetic companies, Alpha count 2, exact CSV Amount 2; direct controlled replacement output D=2,T=1. | Run real payroll and CSV; feed deliberate source mismatch to renderer. | Expected D/T rows and matching mismatched-count exception. | {"matchedDetails": [["Audit Alpha", "2026-10-01", "2", "325.00"], ["Audit Alpha", "2026-09-01", "2", "300.00"]], "prunedTrailers": [["T", "300.00"], ["T", "325.00"]], "csvMatch": [2], "mismatchedDT": "rejected"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:95) | — |



### RET-T136

**RET-F084 · Execution · Detail filtering · PASS**

**Scenario** — Evaluate all equality/inequality/relational operators and AND short-circuit with negative/zero/decimal operands. Check input and stored thresholds.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | CSV Amount=-1.5,0,0.5,1.50,2; threshold .50; AND variant with invalid Other only after a false first comparison. | PUT each operator, inspect saved threshold and compare runs with hand-listed outputs. | Exact eight comparison results and left-to-right AND short-circuit. | {"threshold": "0.50", "operatorRows": {"=": ["0.5"], "==": ["0.5"], "!=": ["-1.5", "0", "1.50", "2"], "<>": ["-1.5", "0", "1.50", "2"], "<": ["-1.5", "0"], "<=": ["-1.5", "0", "0.5"], ">": ["1.50", "2"], ">=": ["0.5", "1.50", "2"]}, "AND_shortCircuit": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:54) | — |



### RET-T137

**RET-F084 · Execution · Detail filtering · PASS**

**Scenario** — Filter some/all detail rows with H/T, compare aligned trailers, and test mismatch guard for payroll D/T record counts.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Alpha Sep 100+200=300, Alpha Oct 115+210=325; Beta has one per month; payroll count=2; CSV 1,2,4,5 with 2<=Amount<5. | POST, Run, apply impossible filter and Run again. | Six payroll records with date-desc details and original matching trailer order; CSV two retained rows; empty payroll no files. | {"payroll": [["Company Name", "Pay Date", "Employee Count", "Net Salary Total"], ["Audit Beta"], ["Audit Alpha"], ["Audit Alpha", "2026-10-01", "2", "325.00"], ["Audit Alpha", "2026-09-01", "2", "300.00"], ["T", "300.00"], ["T", "325.00"]], "csvRetained": [2, 4], "payrollNoMatches": 0, "rowCount": 6} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:52) | — |
| isolated API, SQL, or direct function fixture | Two synthetic companies, Alpha count 2, exact CSV Amount 2; direct controlled replacement output D=2,T=1. | Run real payroll and CSV; feed deliberate source mismatch to renderer. | Expected D/T rows and matching mismatched-count exception. | {"matchedDetails": [["Audit Alpha", "2026-10-01", "2", "325.00"], ["Audit Alpha", "2026-09-01", "2", "300.00"]], "prunedTrailers": [["T", "300.00"], ["T", "325.00"]], "csvMatch": [2], "mismatchedDT": "rejected"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:96) | — |



### RET-T138

**RET-F085 · Execution · Detail sort priority · PASS**

**Scenario** — Sort multi-key fixture with a true tie in first key; compare ASC/DESC priority, numeric vs text and source H/T order.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Tied numeric D rows with secondary ranks, blank and mixed values, US-style dates. | Set sorting, POST CSV variants and compare row IDs with an independent expected sequence. | Stable ASC/DESC; numeric blanks last, mixed uses text, non-ISO looks lexical. | {"numericDescSecondaryAsc": ["A", "B", "C", "D"], "mixedText": ["D", "A", "B", "C"], "allBlankStable": ["B", "A"], "nonISOLexical": ["Oct", "Feb"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:55) | — |



### RET-T139

**RET-F085 · Execution · Detail sort priority · PASS**

**Scenario** — Use numeric, all-blank, mixed text/numeric, case ties and ISO/non-ISO dates. Confirm treatment of numeric blanks and lexical fallback.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Tied numeric D rows with secondary ranks, blank and mixed values, US-style dates. | Set sorting, POST CSV variants and compare row IDs with an independent expected sequence. | Stable ASC/DESC; numeric blanks last, mixed uses text, non-ISO looks lexical. | {"numericDescSecondaryAsc": ["A", "B", "C", "D"], "mixedText": ["D", "A", "B", "C"], "allBlankStable": ["B", "A"], "nonISOLexical": ["Oct", "Feb"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:56) | — |



### RET-T140

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — Group by each filename code and verify filenames, group counts, detail membership and associated H/T.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Same four D rows in 2 clients × 2 dates and H/T; all seven naming codes; storage on (also off/on in T049). | Compare outputs using explicit name and membership oracle; check persisted row numbers, files and generated/stored counts. | All seven codes produce expected groups and DB counts; copied H/T count per file. | {"FILENAME": {"fileNames": ["GroupOracle.csv"], "rows": 7, "job": 70}, "CLIENT": {"fileNames": ["1.csv", "2.csv"], "rows": 8, "job": 71}, "PAYDAY": {"fileNames": ["2026-09-01.csv", "2026-10-01.csv"], "rows": 10, "job": 72}, "FILENAME_CLIENT": {"fileNames": ["GroupOracle_1.csv", "GroupOracle_2.csv"], "rows": 8, "job": 73}, "FILENAME_PAYDAY": {"fileNames": ["GroupOracle_2026-09-01.csv", "GroupOracle_2026-10-01.csv"], "rows": 10, "job": 74}, "CLIENT_PAYDAY": {"fileNames": ["1_2026-09-01.csv", "1_2026-10-01.csv", "2_2026-09-01.csv", "2_2026-10-01.csv"], "rows": 12, "job": 75}, "FILENAME_CLIENT_PAYDAY": {"fileNames": ["GroupOracle_1_2026-09-01.csv", "GroupOracle_1_2026-10-01.csv", "GroupOracle_2_2026-09-01.csv", "GroupOracle_2_2026-10-01.csv"], "rows": 12, "job": 76}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:64) | — |



### RET-T141

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — File Name only fixture should produce one consolidated file with generic plus matched H/T.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "FILENAME", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 70, "expectedRowsAndActual": {"GroupOracle.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"], ["T"], ["T"]]}, "savedRows": 7} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:57) | — |



### RET-T142

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — Client ID fixture with two IDs and two dates should produce one file per client.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "CLIENT", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 71, "expectedRowsAndActual": {"1.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["T"]], "2.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["2", "2026-10-01", "5"], ["T"]]}, "savedRows": 8} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:58) | — |



### RET-T143

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — Payday fixture with two clients on each date should produce one file per date.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "PAYDAY", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 72, "expectedRowsAndActual": {"2026-09-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["1", "2026-09-01", "20"], ["T"], ["T"]], "2026-10-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-10-01", "15"], ["2", "2026-10-01", "5"], ["T"], ["T"]]}, "savedRows": 10} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:59) | — |



### RET-T144

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — File Name + Client ID fixture should use the base prefix and split per client.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "FILENAME_CLIENT", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 73, "expectedRowsAndActual": {"GroupOracle_1.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["T"]], "GroupOracle_2.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["2", "2026-10-01", "5"], ["T"]]}, "savedRows": 8} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:60) | — |



### RET-T145

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — File Name + Payday fixture should use the base prefix and split per date.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "FILENAME_PAYDAY", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 74, "expectedRowsAndActual": {"GroupOracle_2026-09-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["1", "2026-09-01", "20"], ["T"], ["T"]], "GroupOracle_2026-10-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-10-01", "15"], ["2", "2026-10-01", "5"], ["T"], ["T"]]}, "savedRows": 10} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:61) | — |



### RET-T146

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — Client ID + Payday fixture should produce one file for each client-date pair.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "CLIENT_PAYDAY", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 75, "expectedRowsAndActual": {"1_2026-09-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-09-01", "20"], ["T"]], "1_2026-10-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-10-01", "15"], ["T"]], "2_2026-09-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["T"]], "2_2026-10-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-10-01", "5"], ["T"]]}, "savedRows": 12} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:62) | — |



### RET-T147

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — File Name + Client ID + Payday fixture should use the base prefix and both keys.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | {"code": "FILENAME_CLIENT_PAYDAY", "detailInput": [["2", "2026-09-01", "4"], ["1", "2026-10-01", "15"], ["1", "2026-09-01", "20"], ["2", "2026-10-01", "5"]], "genericHeader": true, "clientTrailers": [1, 2]} | Create, POST controlled H/D/T CSV, compare filenames/membership, DB counts and disk. | Exact names, expected detail groups, generic H and matching T. | {"job": 76, "expectedRowsAndActual": {"GroupOracle_1_2026-09-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-09-01", "20"], ["T"]], "GroupOracle_1_2026-10-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["1", "2026-10-01", "15"], ["T"]], "GroupOracle_2_2026-09-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-09-01", "4"], ["T"]], "GroupOracle_2_2026-10-01.csv": [["Client ID", "Pay Date", "Amount"], ["H"], ["2", "2026-10-01", "5"], ["T"]]}, "savedRows": 12} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:63) | — |



### RET-T148

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — Check missing grouping source/value, default group fallback, wildcard H/T and explicit unmatched layouts.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Missing/blank Client ID; default fallback; generic H and unmatched T. | Run grouped CSV variants. | Distinct missing grouping errors, fallback file and unmatched trailer error. | {"missingHeading": 422, "blankValue": 422, "defaultGroup": "fallback.csv", "trailerMismatch": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:67) | — |



### RET-T149

**RET-F086 · Execution · Output name and grouping · PASS**

**Scenario** — Check reserved Windows names, Unicode truncation, filename sanitization, stable casefold collisions and hash suffixes.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | CON, Qa:?* é.csv, 125 é characters, and case collision with group IDs A/a. | Save and run each, compare exact names and repeat collision run. | Reserved name prefix, scrubbed chars, 200 base bytes, predictable per-group hash. | {"reserved": "_CON.csv", "sanitized": "Qa___ é.csv", "unicodeBytes": 204, "collision": ["A.csv", "a_466097201c69.csv"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:68) | — |



### RET-T150

**RET-F087 · Execution · Value formatting and CSV output · PASS**

**Scenario** — Render number/date/text/phone/SSN/padding fixtures and compare exact file and JSON values.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | 02/29/2024, -1.005, 00441234567890, synthetic SSN 123456789, text with leading space. | Configure six mapped formats and compare file plus result JSON. | Exact format output list and one stored data row. | {"expectedAndActual": ["2024-02-29", "-1.01", "+441234567890", "123-45-6789", " ABC", " abc    "], "storedRows": 1} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:69) | — |



### RET-T151

**RET-F087 · Execution · Value formatting and CSV output · PASS**

**Scenario** — Verify six date output formats, three input representations, leap year handling and invalid date errors.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Leap date in three input representations, six output patterns, 2023-02-29 invalid. | PUT each format, Run each source spelling and compare known dates. | 18 correct outputs plus 422 for nonexistent leap date. | {"patterns": {"MMDDYYYY - Date": ["02292024", "02292024", "02292024"], "MM/DD/YYYY": ["02/29/2024", "02/29/2024", "02/29/2024"], "YYYY-MM-DD": ["2024-02-29", "2024-02-29", "2024-02-29"], "YYYYMMDD": ["20240229", "20240229", "20240229"], "DD/MM/YYYY": ["29/02/2024", "29/02/2024", "29/02/2024"], "DD-MM-YYYY": ["29-02-2024", "29-02-2024", "29-02-2024"]}, "leapRejected": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:70) | — |



### RET-T152

**RET-F087 · Execution · Value formatting and CSV output · PASS**

**Scenario** — Verify 0/2/4-place decimal, thousands separators, positive/negative half rounding, nonfinite and extreme magnitude.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | 1234.56785, -1.005, 1.5; positive/negative ties, infinity and 1e1000. | Run each numeric format and invalid values. | Hand-enumerated half-up values and rejects for nonfinite/large. | {"0 - Integer": ["1235", "-1", "2"], "0.00 - Decimal": ["1234.57", "-1.01", "1.50"], "0.0000 - Decimal": ["1234.5679", "-1.0050", "1.5000"], "#,##0": ["1,235", "-1", "2"], "#,##0.00": ["1,234.57", "-1.01", "1.50"]} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:71) | — |



### RET-T153

**RET-F087 · Execution · Value formatting and CSV output · PASS**

**Scenario** — Verify all phone formats and required prefixes, SSN masks and invalid length, whitespace and case transforms.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Synthetic +1 phone, known invalid numbers, synthetic 123-45-6789, mixed case text. | Run supported and invalid format variants. | All supported outputs and rule-specific errors. | {"phone": {"Digits Only": ["12025550123"], "(XXX) XXX-XXXX": ["(202) 555-0123"], "XXX-XXX-XXXX": ["202-555-0123"], "International (+)": ["+12025550123"]}, "ssn": {"XXX-XX-XXXX - SSN": ["123-45-6789"], "XXXXXXXXX - SSN": ["123456789"]}, "transforms": {"Uppercase": [" MIXED "], "Lowercase": [" mixed "], "Trim Whitespace": ["Mixed"]}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:72) | — |



### RET-T154

**RET-F087 · Execution · Value formatting and CSV output · PASS**

**Scenario** — Verify CSV delimiter escaping, embedded newline/quotes, heading selection without D, and byte cap across multiple groups.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Pipe and source containing literal pipe/double quote/newline, plus H-only heading. | Run and parse output bytes. | Escaped value roundtrips and heading from H-only layout. | {"quotedValue": "alpha&#124;beta\"\nline", "noDetailHeading": "Header value"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:73) | — |
| isolated API, SQL and controlled execution | Directory at configured CSV path, HTTP payroll source override, 4.5 MB CSV grows above 10 MiB in 2 groups. | Run each using the production backend, inspect failure history and filesystem. | Unreadable source rejection, override wins, aggregate output rejected with no files. | {"unreadable": {"detail": "Could not read 118.csv in the configured report input folder."}, "history": "Failed", "override": "Synthetic Override", "aggregateInputBytes": 4500197, "outputOverCap": 422} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:112) | — |



### RET-T155

**RET-F088 · Execution · Publish and store results · PASS**

**Scenario** — Compare successful publish, result storage on/off and multi-file counts with expected DB rows and disk path.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Same four D rows in 2 clients × 2 dates and H/T; all seven naming codes; storage on (also off/on in T049). | Compare outputs using explicit name and membership oracle; check persisted row numbers, files and generated/stored counts. | All seven codes produce expected groups and DB counts; copied H/T count per file. | {"FILENAME": {"fileNames": ["GroupOracle.csv"], "rows": 7, "job": 70}, "CLIENT": {"fileNames": ["1.csv", "2.csv"], "rows": 8, "job": 71}, "PAYDAY": {"fileNames": ["2026-09-01.csv", "2026-10-01.csv"], "rows": 10, "job": 72}, "FILENAME_CLIENT": {"fileNames": ["GroupOracle_1.csv", "GroupOracle_2.csv"], "rows": 8, "job": 73}, "FILENAME_PAYDAY": {"fileNames": ["GroupOracle_2026-09-01.csv", "GroupOracle_2026-10-01.csv"], "rows": 10, "job": 74}, "CLIENT_PAYDAY": {"fileNames": ["1_2026-09-01.csv", "1_2026-10-01.csv", "2_2026-09-01.csv", "2_2026-10-01.csv"], "rows": 12, "job": 75}, "FILENAME_CLIENT_PAYDAY": {"fileNames": ["GroupOracle_1_2026-09-01.csv", "GroupOracle_1_2026-10-01.csv", "GroupOracle_2_2026-09-01.csv", "GroupOracle_2_2026-10-01.csv"], "rows": 12, "job": 76}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:65) | — |



### RET-T156

**RET-F088 · Execution · Publish and store results · PASS**

**Scenario** — Check stored JSON row numbers and UUID boundaries with duplicated H/T across grouped outputs and no inserts for heading-only row.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Same four D rows in 2 clients × 2 dates and H/T; all seven naming codes; storage on (also off/on in T049). | Compare outputs using explicit name and membership oracle; check persisted row numbers, files and generated/stored counts. | All seven codes produce expected groups and DB counts; copied H/T count per file. | {"FILENAME": {"fileNames": ["GroupOracle.csv"], "rows": 7, "job": 70}, "CLIENT": {"fileNames": ["1.csv", "2.csv"], "rows": 8, "job": 71}, "PAYDAY": {"fileNames": ["2026-09-01.csv", "2026-10-01.csv"], "rows": 10, "job": 72}, "FILENAME_CLIENT": {"fileNames": ["GroupOracle_1.csv", "GroupOracle_2.csv"], "rows": 8, "job": 73}, "FILENAME_PAYDAY": {"fileNames": ["GroupOracle_2026-09-01.csv", "GroupOracle_2026-10-01.csv"], "rows": 10, "job": 74}, "CLIENT_PAYDAY": {"fileNames": ["1_2026-09-01.csv", "1_2026-10-01.csv", "2_2026-09-01.csv", "2_2026-10-01.csv"], "rows": 12, "job": 75}, "FILENAME_CLIENT_PAYDAY": {"fileNames": ["GroupOracle_1_2026-09-01.csv", "GroupOracle_1_2026-10-01.csv", "GroupOracle_2_2026-09-01.csv", "GroupOracle_2_2026-10-01.csv"], "rows": 12, "job": 76}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:66) | — |



### RET-T157

**RET-F089 · Execution · History and rollback · PASS**

**Scenario** — Trigger failure after output begins and verify transaction/file rollback and Failed history.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Disposable results CHECK rejects second group after both output files publish. | Apply fixture-only test constraint then run two groups; inspect disk, result rows, history; drop constraint. | 500, no report files or stored rows, Failed history persisted. | {"http": 500, "results": 0, "reports": 0, "history": "Failed", "message": {"detail": "The job could not be completed. No results were saved."}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:74) | — |



### RET-T158

**RET-F089 · Execution · History and rollback · PASS**

**Scenario** — Compare Success/Failed/Pending/In Progress across manual runs, DB errors, poll refresh and process restart.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL and controlled execution | Historical success/failure from browser runs; new worker 8086 with same isolated database. In-progress captured separately. | GET list from independent process, compare status values persisted by earlier runs. | Success/Failed persist across service process start; unrun records remain pending. | {"newProcessStatuses": {"payroll": "Success", "missing": "Failed"}, "pendingRows": 36} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:109) | — |



### RET-T159

**RET-F090 · Automation · Scheduler lifecycle and slot · PASS**

**Scenario** — Exercise scheduler start flag, date eligibility, UTC slot and each recurrence using controlled clock fixtures.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Fixed timestamps around recurring dates, 5-minute inclusive/exclusive window, month end and U.S. DST. | Execute production slot function with constructed schedule rows and independent expected UTC constants. | Matching slots at documented local recurrence points; gaps/outside windows return None. | {"daily at slot": "2026-10-10T04:00:00+00:00", "at pos +4m59s": "2026-10-10T04:00:00+00:00", "at +5m": null, "before slot": null, "start future": null, "weekly on Tuesday": "2026-10-06T04:00:00+00:00", "weekly wed off": null, "biweekly first Tuesday": "2026-10-06T04:00:00+00:00", "biweekly mid cadence": null, "biweekly +14 days": "2026-10-20T04:00:00+00:00", "month end": "2026-02-28T04:00:00+00:00", "manual": null, "DST forward nonexistent": null, "DST first repeated occurrence": "2026-11-01T05:30:00+00:00", "DST second repeated occurrence": null} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:78) | — |



### RET-T160

**RET-F090 · Automation · Scheduler lifecycle and slot · PASS**

**Scenario** — Compare start-date future/past, selected time, weekday, bi-weekly anchor, last day of month, DST gap/overlap and outside five-minute window.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Fixed timestamps around recurring dates, 5-minute inclusive/exclusive window, month end and U.S. DST. | Execute production slot function with constructed schedule rows and independent expected UTC constants. | Matching slots at documented local recurrence points; gaps/outside windows return None. | {"daily at slot": "2026-10-10T04:00:00+00:00", "at pos +4m59s": "2026-10-10T04:00:00+00:00", "at +5m": null, "before slot": null, "start future": null, "weekly on Tuesday": "2026-10-06T04:00:00+00:00", "weekly wed off": null, "biweekly first Tuesday": "2026-10-06T04:00:00+00:00", "biweekly mid cadence": null, "biweekly +14 days": "2026-10-20T04:00:00+00:00", "month end": "2026-02-28T04:00:00+00:00", "manual": null, "DST forward nonexistent": null, "DST first repeated occurrence": "2026-11-01T05:30:00+00:00", "DST second repeated occurrence": null} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:79) | — |



### RET-T161

**RET-F090 · Automation · Scheduler lifecycle and slot · PASS**

**Scenario** — Check scheduler disabled, invalid timezone startup, and recovery after outage longer than execution window.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Scheduler flags off/on; invalid/test-zone; outside 5-minute recovery covered by slot cases. | Enter/exit actual FastAPI lifespan with fake background runner and test invalid zone. | Disable skips start, enable starts/shuts down, invalid timezone rejected. | {"lifespanStartCalls": [[false, 0], [true, 1]], "invalidTimezone": "ZoneInfoNotFoundError", "outsideWindow": "verified separately in T160"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:80) | — |



### RET-T162

**RET-F091 · Automation · Scheduled duplicate suppression · PASS**

**Scenario** — Poll same scheduled slot twice with present file or .complete; verify one effective run; inspect lock behavior.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Two separate SQL connections via two concurrent threads; slot 2026-10-06T04:00Z; 4 payroll groups; zero-result job. | Call actual _run_scheduled_job twice and re-poll, inspect disk, UUIDs and .complete. | One effective run per same-slot lock, four outputs, zero result writes .complete. | {"scheduledJobs": [95, 96], "firstResultUuids": 1, "files": ["1_2026-09-01.csv", "1_2026-10-01.csv", "2_2026-09-01.csv", "2_2026-10-01.csv"], "storedRows": 12, "zeroMarker": true, "concurrentCalls": 2} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:81) | — |



### RET-T163

**RET-F091 · Automation · Scheduled duplicate suppression · PASS**

**Scenario** — Run scheduled zero reports and check .complete duplicate skip; test another scheduler process against job row lock.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Two separate SQL connections via two concurrent threads; slot 2026-10-06T04:00Z; 4 payroll groups; zero-result job. | Call actual _run_scheduled_job twice and re-poll, inspect disk, UUIDs and .complete. | One effective run per same-slot lock, four outputs, zero result writes .complete. | {"scheduledJobs": [95, 96], "firstResultUuids": 1, "files": ["1_2026-09-01.csv", "1_2026-10-01.csv", "2_2026-09-01.csv", "2_2026-10-01.csv"], "storedRows": 12, "zeroMarker": true, "concurrentCalls": 2} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:82) | — |



### RET-T164

**RET-F092 · Automation · Subscription delivery eligibility · PASS**

**Scenario** — Verify each recipient receives only reports whose entire company/client set is covered.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Local SSL and STARTTLS sink, synthetic .invalid addresses, two company groups/date outputs; one RCPT rejection. | Run approved Uvicorn API manually (mail disabled), then actual scheduler at fixed time with loopback SMTP; compare message attachments to expected disk files. | Separate recipient scoping, byte-equal attachment or per-recipient merge, rejection isolated, successful history. | [{"job": 97, "transport": "ssl", "merge": false, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [2, 2], "rejectedRecipientNotCaptured": true}, {"job": 98, "transport": "tls", "merge": true, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}, {"job": 99, "transport": "ssl", "merge": true, "heading": false, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:83) | — |



### RET-T165

**RET-F092 · Automation · Subscription delivery eligibility · PASS**

**Scenario** — Check no recipients, disabled mail, unmatched/ambiguous IDs, multiple subscriptions per normalized address and manual run silence.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL, or direct function fixture | Synthetic group requires clients 1 and 2; mixed-case recipient entries and empty subscriptions. | Execute production attachment logic and mail guard with no-network patch; manual silence tested via sink. | Only normalized recipient with both targets receives one report; disabled mail does not connect. | {"empty": 0, "unmatched": 0, "allGroupsCaseFolded": "test@example.invalid", "mailDisabledConnections": 0} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:104) | — |



### RET-T166

**RET-F093 · Automation · Scheduled mail attachment merge · PASS**

**Scenario** — Verify scheduled merge on/off with two eligible files and Include Header Row on/off; compare disk outputs.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Local SSL and STARTTLS sink, synthetic .invalid addresses, two company groups/date outputs; one RCPT rejection. | Run approved Uvicorn API manually (mail disabled), then actual scheduler at fixed time with loopback SMTP; compare message attachments to expected disk files. | Separate recipient scoping, byte-equal attachment or per-recipient merge, rejection isolated, successful history. | [{"job": 97, "transport": "ssl", "merge": false, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [2, 2], "rejectedRecipientNotCaptured": true}, {"job": 98, "transport": "tls", "merge": true, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}, {"job": 99, "transport": "ssl", "merge": true, "heading": false, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:84) | — |



### RET-T167

**RET-F093 · Automation · Scheduled mail attachment merge · PASS**

**Scenario** — Check filenames, byte concatenation, one heading across merged attachments, delimiters preserved and one-file no-op.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL and controlled execution | Merge Files enabled, one eligible company 1 report after filter, Pipe. Multi-file SSL/STARTTLS observed separately. | Invoke scheduled job at fixed time with mock mail function; compare one attachment and bytes to file. | One eligible attachment remains unrenamed and delimiter unchanged. | {"attachment": "1.csv", "sameBytesOnDisk": true, "separator": "&#124;", "oneFileNoOp": true} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:113) | — |



### RET-T168

**RET-F094 · Automation · SMTP send and error recording · PASS**

**Scenario** — Use a controlled test SMTP sink for SSL/TLS, matching attachment and reject/connection errors; verify no real recipients.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Local SSL and STARTTLS sink, synthetic .invalid addresses, two company groups/date outputs; one RCPT rejection. | Run approved Uvicorn API manually (mail disabled), then actual scheduler at fixed time with loopback SMTP; compare message attachments to expected disk files. | Separate recipient scoping, byte-equal attachment or per-recipient merge, rejection isolated, successful history. | [{"job": 97, "transport": "ssl", "merge": false, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [2, 2], "rejectedRecipientNotCaptured": true}, {"job": 98, "transport": "tls", "merge": true, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}, {"job": 99, "transport": "ssl", "merge": true, "heading": false, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:85) | — |



### RET-T169

**RET-F094 · Automation · SMTP send and error recording · PASS**

**Scenario** — Compare mail success transport-only, delivery failure and Generate Success state. Verify downloaded CSV equals attachment bytes.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated scheduler / local SMTP sink | Local SSL and STARTTLS sink, synthetic .invalid addresses, two company groups/date outputs; one RCPT rejection. | Run approved Uvicorn API manually (mail disabled), then actual scheduler at fixed time with loopback SMTP; compare message attachments to expected disk files. | Separate recipient scoping, byte-equal attachment or per-recipient merge, rejection isolated, successful history. | [{"job": 97, "transport": "ssl", "merge": false, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [2, 2], "rejectedRecipientNotCaptured": true}, {"job": 98, "transport": "tls", "merge": true, "heading": true, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}, {"job": 99, "transport": "ssl", "merge": true, "heading": false, "diskFiles": 4, "recipients": [["beta@example.invalid"], ["alpha@example.invalid"]], "counts": [1, 1], "rejectedRecipientNotCaptured": true}] | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:86) | — |



### RET-T170

**RET-F095 · Integration · Operational health endpoints · PASS**

**Scenario** — Check service health in up/degraded conditions and distinguish HTTP status from JSON payload.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated HTTP API and SQL Server | Healthy isolated backend with SQL Server. | GET /health and /health/db. | Both 200 with documented payloads. | {"health": 200, "databaseHealth": 200, "database": "connected"} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:75) | — |
| isolated API, SQL and controlled execution | Healthy test API on 8084 and fault-only API on 8085 with synthetic SQL connection exception. | GET health, db health, jobs and options on both test instances. | Healthy vs degraded; outage health 200 with degraded JSON; list fails and options return XML-only partial values. | {"degradedHealthHTTP": 200, "body": {"status": "degraded", "database": "unavailable"}, "dbGETJobs": 500, "dbGETOptions": 200, "catalogCounts": [0, 0, 12], "listResponse": {"detail": "Unable to load Retirement Builder jobs from the database"}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:106) | — |



### RET-T171

**RET-F095 · Integration · Operational health endpoints · PASS**

**Scenario** — Simulate SQL connection failure and validate health API response status/JSON and list/catalog UI differences.

**Preconditions** — Isolated SQL-backed API, process or local file fixture as identified in the evidence.

| Layer | Test data | Actions | Expected | Actual | Evidence | Bug |
| --- | --- | --- | --- | --- | --- | --- |
| isolated API, SQL and controlled execution | Healthy test API on 8084 and fault-only API on 8085 with synthetic SQL connection exception. | GET health, db health, jobs and options on both test instances. | Healthy vs degraded; outage health 200 with degraded JSON; list fails and options return XML-only partial values. | {"degradedHealthHTTP": 200, "body": {"status": "degraded", "database": "unavailable"}, "dbGETJobs": 500, "dbGETOptions": 200, "catalogCounts": [0, 0, 12], "listResponse": {"detail": "Unable to load Retirement Builder jobs from the database"}} | [Run log](/Users/apple/Desktop/ESC/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:107) | — |

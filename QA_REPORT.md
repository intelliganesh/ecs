# Retirement Builder — Consolidated QA Report

Audit date: 2026-11-06 · Method: read-only code audit + controlled browser/API testing against the already-running servers (frontend :5173, backend :8000). No application code, UI, API contract, DB config or dependency was changed.

Conventions: `App.tsx:N` refers to `frontend/src/App.tsx` (the file is 73 very long lines, so a line number points to a whole component or function). Screenshots are in `qa-evidence/`.

---

## 1. Executive Summary

**Overall quality:** the app looks finished but most of the wizard does not actually persist user input. The Schedule step, most of the Mapping step, the Subscriptions client dropdown and the File Settings modal are decorative: what the user enters is discarded and hardcoded defaults are sent to the API. An unchanged "Edit then Finish" silently resets a job's schedule, mapping and file settings.

| Metric | Value |
|---|---|
| Distinct defects (de-duplicated by root cause) | **36** |
| P0 / P1 / P2 / P3 / P4 | **0 / 4 / 12 / 11 / 9** |
| Confirmed by browser/API reproduction | **27** |
| Code-confirmed | **4** |
| Requirement clarification needed | **4** |
| Intentional stub / production risk | **1** |
| Suspected (unreproduced) | **0** |
| Screens tested | 9 (Login, Dashboard, Add General, Edit General, Schedule, Mapping, Subscriptions, File Settings modal, placeholder menu page) |
| End-to-end flows run | 15 of 15 requested (1 partial, see §8) |
| API endpoints tested | 8 (+ `/docs`, CORS preflight, an unsupported PATCH) |

**Major data-integrity risks:** (1) schedule never saved; (2) mapping position/length/record type/default/column/format never saved; (3) every UI save wipes the job's stored File Settings; (4) refreshing an edit page and clicking Finish creates a blank new job instead of updating; (5) the literal string `"Select Format"` is persisted as a mapping format.

**Release readiness: NOT READY** (see §11).

---

## 2. Critical Bug Report

| ID | Screen | Issue | Sev | Verification | Root cause | User impact |
|---|---|---|---|---|---|---|
| BR-001 | Schedule | Start Date, Frequency, Time, Week never saved or restored | P1 | CONFIRMED | Uncontrolled inputs (`defaultValue`) + hardcoded payload `App.tsx:49,69` | Every job is saved as Weekly Thu 4:00 AM from 2022-02-09; editing a job overwrites its real schedule |
| BR-002 | Mapping | Start Position, Length, Record Type, Default Value, Mapping Column, Format edits are lost; stored values not shown on reopen | P1 | CONFIRMED | Only `field` is controlled; payload hardcodes `'0'`,`'0'`,`'Detail'`,`''` `App.tsx:49,70` | File layout silently reset to zeros on any save |
| BR-005 | Edit / any wizard route | Refresh on `/jobs/edit/*` empties the form; Finish then POSTs a new blank job | P1 | CONFIRMED | `isEditFlow` from URL, `selectedJobId` only in memory `App.tsx:45,49` | Duplicate/blank jobs, original not updated |
| BR-009 | File Settings modal / save | Sorting and Conditional rows are discarded on close; every save sends `[]`, erasing previously stored settings | P1 | CONFIRMED | Modal state is local and never lifted `App.tsx:72`; payload hardcoded `App.tsx:49` | Data loss on existing jobs; feature unusable |
| BR-003 | Subscriptions | Selected Client is never saved or changeable | P2 | CONFIRMED | No change handler on client select `App.tsx:71,58` | Subscription has an email but no client |
| BR-004 | Mapping / Subscriptions | After deleting a row, remaining rows show another row's values | P2 | CONFIRMED | Index keys + uncontrolled `defaultValue` `App.tsx:70,71` | User sees wrong mapping next to a field name |
| BR-006 | Subscriptions | Double-click Finish creates duplicate jobs | P2 | CONFIRMED | No in-flight guard; stale closure; backend accepts duplicates `App.tsx:49,59` | Duplicate jobs |
| BR-007 | General (Edit) | Unsaved edits overwritten when route returns to `/jobs/edit/general` | P2 | CONFIRMED | Effect on `[activeJob, screen]` re-fills form `App.tsx:48` | Lost edits |
| BR-008 | All wizard steps | Edit-mode Back and "General" stepper go to `/jobs/new`; Add mode uses `/jobs/edit/*` URLs | P2 | CONFIRMED | `onBack` and stepper use `'general'` screen `App.tsx:22,56,66` | Inconsistent URLs; "Edit Job" heading on the Add route |
| BR-010 | Mapping | `"Select Format"` placeholder saved as a real format value | P2 | CONFIRMED | Seed row literal `App.tsx:20` | Corrupt data in stored mapping |
| BR-015 | Dashboard | File Type=CSV, Is Active=Yes, Status=Success hardcoded; Modified On and Last Run Date always blank | P2 | CONFIRMED | `valueFor` / `toDashboardJob` `App.tsx:18,67` | Misleading dashboard (a Pipe job shows CSV; never-run jobs show Success) |
| BR-016 | Dashboard | API failure (network or HTTP 500) shows "No matching records found" and clears the list; no loading or error state | P2 | CONFIRMED | `.catch(() => setRetirementJobs([]))` `App.tsx:46` | Outage looks like "no jobs" |
| BR-017 | General | Upload accepts any file (incl. `.exe`), sends no request, keeps only the name, says "File selected and ready to use." | P2 | CONFIRMED | `App.tsx:55,68`; no upload endpoint | Users believe a file was uploaded |
| BR-018 | General / API | No required-field validation anywhere; empty job saves; names untrimmed | P2 | CONFIRMED | No validation in UI or models | Blank/garbage jobs |
| BR-025 | Backend | Jobs stored in an in-memory dict; lost on restart or reload; the DB is configured but unused | P2 | INTENTIONAL STUB (production risk) | `retirement_builder.py:110` | All data lost on restart |
| BR-026 | Frontend | API base URL hardcoded to `http://localhost:8000` | P2 | CODE-CONFIRMED | `App.tsx:17` | Breaks behind the IIS rewrite in `public/web.config` or from any other host |

P3 and P4 items are in §3 (short form) and §10.

---

## 3. Detailed Reproduction Report (confirmed P1 and key P2)

### BR-001 — Schedule values not saved (previously C1)
- **Preconditions:** logged in; dashboard loaded.
- **Steps:** Add → name → Next → set Frequency=Monthly, Hour=9, Week=Monday → Next, Next, Finish → read `GET /jobs`.
- **Expected:** saved schedule = Monthly / 9 / Monday.
- **Actual:** saved `startDate 2022-02-09, Weekly, 4, 00, AM, Thursday`. Also confirmed: going Next then Back inside the wizard resets Hour 11→4 and date 2030-01-02→2022-02-09 without saving; reopening a job stored as Monthly / 9:45 PM / Monday / 2024-03-15 shows Weekly / 4:00 AM / Thursday / 2022-02-09.
- **Evidence:** POST body captured (`schedule` block); seed job reopened.
- **Root cause:** `ScheduleStep` uses `defaultValue` with no state `App.tsx:69`; `saveJob` hardcodes the object `App.tsx:49`.
- **Fix (description):** hold schedule values in state, load them on edit, send them in the payload.

### BR-002 — Mapping edits lost / round trip (previously C2, H5)
- **Steps:** Edit seed job (ALPHA start 5, length 12, Header, default `DV1`; BETA 20/9/Trailer) → Next ×3 → Finish with no changes → `GET /jobs/2`.
- **Expected:** values identical to before.
- **Actual:** stored `startPosition "5"→"0"`, `length "12"→"0"`, `recordType Header/Trailer→Detail`, `defaultValue DV1→""`. UI on reopen already showed `0|0|Detail|`. Typing `-5`, `abc`, `DEFVAL` into a row and saving sent `"0"`, `"0"`, `""`.
- **Root cause:** `normalizeMappingRows` drops those fields `App.tsx:19`; `MappingStep` inputs are uncontrolled `App.tsx:70`; payload hardcoded `App.tsx:49`.

### BR-005 — Refresh on edit page creates a new job (previously C5)
- **Steps:** Select job → Edit → reload on `/jobs/edit/general` → Next ×3 → Finish.
- **Actual:** form empty, heading "Edit Job", job count 2→3 with a blank name (`POST`, not `PUT`). Same reload in Add mode also shows "Edit Job".
- **Root cause:** `isEditFlow` initialised from the URL, `selectedJobId` initialised to `null` `App.tsx:45`; `saveJob` chooses POST when `selectedJobId === null` `App.tsx:49`.

### BR-009 — File Settings never persisted; existing settings wiped
- **Steps:** seed job with `sortingOrder` and `conditionalStatements` → Edit → Finish unchanged → `GET`.
- **Actual:** both arrays `[]`. In the modal: add a sorting row, type values, "Save & Continue", reopen → 0 rows. Modal Cancel and Save & Continue behave identically.
- **Root cause:** `FileSettingsModal` keeps rows in local state `App.tsx:72`; `fileSettings: {sortingOrder: [], conditionalStatements: []}` hardcoded `App.tsx:49`.

### BR-003 — Client not saved
- **Steps:** Subscriptions → pick "000720 - UBMD Pediatrics" → Finish. **Actual:** dropdown shows it, payload `client:""`. A client already stored round-trips only if never touched. **Root cause:** `SearchableSelect` has no `onValueChange` wired `App.tsx:71`.

### BR-004 — Wrong values after row delete
- **Steps:** Mapping → delete the first row (PAYDATE). **Actual:** WORK PHONE row shows `Employee Work Email / MMDDYYYY - Date` (PAYDATE's), LASTNAME shows WORK PHONE's mapping, etc. Saved payload still has the original pairs, so screen and data disagree. **Root cause:** `key=mapping-row-${index}` plus `defaultValue` `App.tsx:70`; `key={client-index}` in Subscriptions `App.tsx:71`.

### BR-006 — Duplicate submit
- **Steps:** Subscriptions → click Finish twice in the same tick. **Actual:** two identical jobs (ids 1 and 2). **Root cause:** no disabled/in-flight state `App.tsx:71`; closure still has `selectedJobId=null` `App.tsx:49,59`; backend has no idempotency or duplicate check.

### BR-007 — Unsaved edits overwritten
- **Steps:** Edit seed job → change name/description → Next, Next, Next → use browser Back until `/jobs/edit/general`. **Actual:** `UNSAVED-NAME` replaced by `QAAUDIT-seed`. **Root cause:** effect `[activeJob, screen]` `App.tsx:48`.

### BR-008 — Add/Edit route mix
- **Steps:** Edit job → Schedule → Back; or click the "General" stepper tab. **Actual:** URL `/jobs/new`, heading still "Edit Job", `selectedJobId` retained (a later Finish does `PUT`). In Add mode Next from General goes to `/jobs/edit/schedule`. **Root cause:** `screenPaths` has a single `general` entry for Add; `ScheduleStep onBack={() => navigate('general')}` `App.tsx:22,56,66`.

### BR-010 — Placeholder persisted
- **Evidence:** POST body of a fresh Add flow contains `{"field":"HIGHLY COMPENSATED",...,"format":"Select Format"}`; the same value exists in stored job 1. Empty new rows send `""` (correct). Related display defect BR-035.

### BR-015 / BR-016 — Dashboard
- Pipe-delimited job shows `CSV`; filter "pipe" on File Type returns nothing, filter "csv" returns every job. `Is Active`/`Status` constant. With `fetch` forced to reject or return 500 the table shows "No matching records found", no alert. A delayed response showed stale rows (no loading indicator); on a cold load the initial `[]` produces the same empty message (code-confirmed).

### BR-017 — Upload
- Selected `malware.exe`, then `ok.csv`: no `accept` attribute, no request fired (fetch spy), text "File selected and ready to use.", only `selectedFile` (name) is posted and stored. Clearing the picker resets the label.

### BR-018 / BR-019 / BR-020 — Validation and error handling (UI + API)
- Empty job accepted (UI and `POST {}` → 201). Name `"  QAAUDIT-flow  "` stored untrimmed. 300-char field name and 1 MB description accepted.
- Emails `not-an-email`, `bad` accepted; `A@x.test` and `a@x.test` both kept (case-sensitive de-dup); duplicates and blanks dropped silently.
- Failed saves: network error shows raw `Failed to fetch`; HTTP 422/500 show a generic message (server `detail` discarded); malformed 201 body shows the raw JS exception; the error stays when you leave and return to the step. Form data is retained after failure (pass).

---

## 4. Field-Level Data Integrity Report

Pipeline: UI input → React state → request → backend → stored → reopened UI.

| Screen | Field | UI Input | Request Value | Stored Value | Reopened Value | Status |
|---|---|---|---|---|---|---|
| General | File Name | `  QAAUDIT-flow  ` | same (untrimmed) | same | same | PASS (no trim) |
| General | File Format | Pipe | Pipe | Pipe | Pipe | PASS |
| General | Description | text | text | text | text | PASS |
| General | Output File Name Format | File Name + Payday | same | same | same | PASS |
| General | Store Results to Table | checked | true | true | true | PASS |
| General | Upload File | `ok.csv` / `malware.exe` | file name only, no upload | name | name label | FAIL (BR-017) |
| General | enable (no UI control) | n/a | always `true` | true | n/a | CODE-CONFIRMED: a stored `false` would be overwritten by any UI save |
| Schedule | Start Date | 2030-01-02 | `2022-02-09` | `2022-02-09` | `2022-02-09` | FAIL |
| Schedule | Build Frequency | Monthly | `Weekly` | Weekly | Weekly | FAIL |
| Schedule | Hour | 9 / 11 | `4` | 4 | 4 | FAIL |
| Schedule | Minute | no UI change tested | `00` | 00 | 00 | FAIL (code-confirmed, same mechanism) |
| Schedule | AM/PM | no UI change tested | `AM` | AM | AM | FAIL (code-confirmed, same mechanism) |
| Schedule | Week | Monday | `Thursday` | Thursday | Thursday | FAIL |
| Mapping | Include Header Row | unchecked (via seed) | false | false | false | PASS |
| Mapping | Field Name | edited, 300 chars | same | same | same | PASS |
| Mapping | Start Position | `-5` | `"0"` | 0 | 0 | FAIL |
| Mapping | Length | `abc` | `"0"` | 0 | 0 | FAIL |
| Mapping | Record Type | Header / Trailer (seed) | `Detail` | Detail | Detail | FAIL |
| Mapping | Default Value | `DEFVAL` / `DV1` | `""` | "" | "" | FAIL |
| Mapping | Mapping Column | changed to Employee Work Email | original value | original | original (shifted after delete) | FAIL |
| Mapping | Format | seed placeholder | `Select Format` | Select Format | placeholder shown | FAIL (BR-010) |
| Mapping | New row start/length | blank in UI | `"0"` | 0 | 0 | FAIL (UI blank, payload zero) |
| Subscriptions | Merge Files | checked | true | true | true | PASS |
| Subscriptions | Client | UBMD Pediatrics selected | `""` | "" | "" | FAIL (BR-003) |
| Subscriptions | Email | tags | comma-joined string | same | same tags | PASS (invalid emails accepted) |
| File Settings | Sorting Order | row typed in modal | `[]` | [] | none | FAIL (BR-009) |
| File Settings | Conditional Statements | none entered in UI; seeded via API | `[]` | [] (seed wiped) | none | FAIL (BR-009) |

---

## 5. API Stub Audit

| Endpoint | Expected | Observed | Issue | Sev | Status |
|---|---|---|---|---|---|
| `GET /options` | Lists options used by UI | 200 with 10 lists | Frontend never calls it; UI hardcodes its own lists, which have drifted: backend `mappingColumns` has 2 entries, UI seeds others; backend `mappingFormats` has SSN, UI row dropdown does not offer it | P3 (BR-024) | CODE-CONFIRMED |
| `GET /jobs` | List | 200, full jobs incl. 5000-row job | No pagination, no filtering | P4 | OK for stub |
| `GET /jobs/{id}` | One job | 200; 404 for missing/0/-1/huge; 422 for `abc` | Consistent | | PASS |
| `POST /jobs` | Create with validation | 201 for `{}`; invalid frequency, meridiem, date, bad types, null body, malformed JSON all 422 | Accepts empty job; hour `99`/minute `77`; email `not-an-email`; startPosition `-5`; length `abc`; fileFormat `XLSX`; startDate `0001-01-01`; 1 MB string; 5000 rows; duplicates; unknown fields silently ignored; client `id` ignored; `enable:"yes"` coerced | P3 (BR-023) | Missing documented validation |
| `PUT /jobs/{id}` | Update | 200 full replace; 404 missing; 422 invalid body leaves record unchanged; body `id` ignored | Full-replace semantics make the UI's partial/hardcoded payloads destructive | (see BR-001/002/009) | PASS (API) |
| `PATCH` | not implemented | 405; CORS preflight advertises PATCH | Cosmetic | P4 | |
| `DELETE /jobs/{id}` | Remove | 204; second delete 404 | No UI uses it | | PASS / REQUIREMENT CLARIFICATION |
| `GET /health` | ok | 200 | | | PASS |
| `GET /health/db` | DB status | 200 `connected` | Code returns 200 even when degraded `main.py:28` | P4 | CODE-CONFIRMED (degraded path not triggered) |
| `/docs` | dev only | 200 | Exposed unauthenticated | P4 (BR-040) | CONFIRMED |
| CORS | allow-list | `localhost:5173` and `127.0.0.1:5173` allowed; `evil.example` preflight 400 | `allow_credentials=True` with `*` methods/headers `main.py:15` | P4 | PASS |
| Error responses | consistent | 404 `{"detail": str}`; 422 FastAPI list; no stack traces or 5xx seen | | | PASS |
| Auth | n/a | No authentication on any endpoint | Production risk | P3 | REQUIREMENT CLARIFICATION |

**Intentional-stub items:** in-memory store, no persistence, ids not reused (counter keeps advancing after deletes), no concurrency control.

---

## 6. UI and Accessibility Report

**Visual / responsive (CONFIRMED)**
- BR-027 (P3): at 375px the sidebar is open by default and covers about two thirds of the page; collapsed, a 76px rail still overlaps content. The page title reads "ement Builder", field labels are clipped ("ame", "ormat"), the Template button is cut off, and the stepper paints over the rail. See `qa-evidence/mobile-375-*.jpg`.
- BR-033 (P4): at 768px the layout holds, but the mapping table shows 3 of 8 columns (horizontal scroll inside the card) and the 4th stepper tab is clipped. See `qa-evidence/tablet-768-mapping-table-3-of-8-columns.jpg`.
- Desktop: no overflow or clipping observed; dropdown menus position correctly.

**Usability**
- BR-035 (P4): the "Select Format" placeholder is shown on every empty dropdown (Output File Name Format, Record Type, Mapping Column, Client, Hour etc. when empty).
- BR-030 (P4): no sidebar item is highlighted on any wizard screen; unknown URLs while logged in render a blank page, not a 404 (code-confirmed `screenFromPath`).
- BR-029 (P4): the File Settings modal stays open after browser Back moves to another route.
- BR-014 (P4): the "+" button labelled "Add mapping rule" opens "File Settings".
- BR-021 (P4): login error says "Use the sample credentials shown below" but nothing is shown below; the credentials are only prefilled.
- BR-031 (P4): brand reads "ESC" in the topbar and login but "ECS" in the page title, API name and README.

**Accessibility**
- BR-028 (P3): SearchableSelect: Enter opens the menu and focus moves to the search box, but Escape does not close it and Up/Down do not move through options (Enter after arrows does nothing). No `aria-activedescendant`.
- BR-034 (P4): wizard stepper has no `aria-current`; no `required`/`aria-required` anywhere.
- Passed: all inputs and buttons have accessible names; one `h1`; `lang="en"`; global `:focus-visible` outline is defined (the programmatic-focus "no outline" reading was a test artifact, NOT REPRODUCIBLE); no console errors or warnings during the whole session.
- Not measured: colour contrast ratios, screen-reader output (BLOCKED, no tooling).

---

## 7. Test Coverage Matrix

| Screen | Functional | Validation | API | Navigation | Responsive | Status |
|---|---|---|---|---|---|---|
| Login | Yes | Yes (wrong password, blank email) | n/a (client-only) | Yes (route guard) | Not tested | Tested |
| Dashboard | Yes (filter, sort, select, Run, Template, Edit, Add) | n/a | Yes (list, error states) | Yes | 375 / 768 | Tested; sort exercised on File Name only |
| General (Add) | Yes | Yes | Yes | Yes | 375 | Tested |
| General (Edit) | Yes | Partial | Yes | Yes | No | Tested |
| Schedule | Yes | Boundary date only | Yes | Yes | No | Tested |
| Mapping | Yes | Yes | Yes | Yes | 768 | Tested |
| Subscriptions | Yes | Yes | Yes | Yes | No | Tested |
| File Settings modal | Yes | n/a | Yes | Yes (Back with modal open) | No | Tested |
| Placeholder pages (`/services`) | Reached via sidebar | n/a | n/a | Yes | No | Smoke only |

---

## 8. Regression Results

| # | Flow | Result | Notes |
|---|---|---|---|
| 1 | Login → Dashboard | PASS | Prefilled demo credentials |
| 2 | Add → all steps → Finish | FAIL | BR-001/002/003/009 data not saved |
| 3 | Edit → change values → Save | PARTIAL | Saved unchanged through the UI (FAIL, BR-001/002/009). A save with a changed General field was not run separately; General fields round-tripped correctly in the unchanged save. |
| 4 | Add → Previous → Next → Finish | FAIL | Schedule/mapping inputs reset when navigating |
| 5 | Edit → Previous → Next → Finish | FAIL | BR-007, BR-008 |
| 6 | Add → Refresh → resume | FAIL | Not supported; heading becomes "Edit Job" (BR-005) |
| 7 | Edit → Refresh → continue | FAIL | BR-005 |
| 8 | Mapping add/edit/delete/save | FAIL | BR-002, BR-004 |
| 9 | Subscriptions add/delete/save | FAIL | Email PASS; client BR-003 |
| 10 | Reopen saved job, compare every field | FAIL | §4 matrix |
| 11 | Empty / invalid submit | FAIL | BR-018, BR-019 |
| 12 | Repeated Finish | FAIL | BR-006 |
| 13 | Browser Back / Forward | FAIL | BR-007, BR-008, BR-029 |
| 14 | Failed API request | PASS with defects | No crash, data retained; BR-020 |
| 15 | Reload dashboard after create/edit | PASS | List refetches; displayed values wrong (BR-015) |

**Blocked / not tested:** `npm audit` / dependency CVE scan (would send the dependency list to an external registry; not run); inspection or execution of `service/SchedulerAppBackend.exe` (untracked binary, not run); real SQL Server failure path of `/health/db`; true concurrent-request race tests; LAN-IP origin from another device (CORS rejection is shown by the `evil.example` preflight); screen-reader and contrast measurement; Playwright (not installed, built-in browser used instead).

**Other checks run:** `tsc --noEmit` passes (exit 0); Python `compileall` passes; there are no automated tests in the repo; no `console.*`, `dangerouslySetInnerHTML` or `localStorage` use; HTML in a job name (`<img onerror>`) rendered as text (XSS NOT REPRODUCIBLE); unauthenticated access redirects to `/login` (PASS).

---

## 9. Previously Reported vs Newly Discovered

**Previously confirmed (browser):** C1→BR-001, C2→BR-002, C3→BR-003, C4→BR-004, C5→BR-005, H1→BR-006.

**Previously suspected, now confirmed this round:** H2→BR-007, H3→BR-008, H5→BR-002 and BR-009, H6→BR-010, H7→BR-009/011/012/013/014, H8→BR-015/016, H9→BR-017, H4→BR-018.

**Newly discovered this round:**
- BR-009 effect on stored data: every UI save erases File Settings that already exist.
- BR-001/002 also reset inside the wizard on plain Next/Back, before any save.
- BR-012 "Run requested for …" message with no request sent.
- BR-016 failed fetch indistinguishable from empty.
- BR-019, BR-020 details, BR-023 API gaps, BR-024 options drift, BR-026 hardcoded API base (matters because `frontend/public/web.config` proxies `/api` for IIS), BR-027/028/029/030/033/034/035, BR-040, forgeable client-side login (BR-022).

**Duplicates sharing one root cause (counted once):**
- Uncontrolled inputs plus hardcoded payload: schedule not saved, mapping not saved, schedule/mapping reset on Back/Next, reopened values wrong, dashboard Run Day/Time/Type wrong.
- `selectedJobId`/`isEditFlow` state: C5, refresh in Add mode shows "Edit Job".
- Index keys with uncontrolled inputs: C4 in Mapping and in Subscriptions.

**Unverified:** none left from the first audit.

---

## 10. Prioritized Developer Fix Backlog

### Fix immediately
| Item | File | Functionality |
|---|---|---|
| BR-001 Schedule state + payload + load on edit | `frontend/src/App.tsx` (`ScheduleStep`, `saveJob`, edit effect) | Schedule |
| BR-002 Mapping fields controlled, keep all row fields in `normalizeMappingRows` and payload | `App.tsx` (`MappingStep`, `normalizeMappingRows`, `saveJob`) | Mapping |
| BR-009 Lift File Settings state, send it, load it on edit | `App.tsx` (`FileSettingsModal`, `saveJob`) | File Settings |
| BR-005 Restore selected job id from the route (id in URL) or block Finish without it | `App.tsx` (state init, `saveJob`, routes) | Edit workflow |

### Fix before release
| Item | File | Functionality |
|---|---|---|
| BR-003 Client change handler | `App.tsx` `SubscriptionsStep` | Subscriptions |
| BR-004 Stable row keys, controlled values | `App.tsx` `MappingStep`/`SubscriptionsStep` | Mapping / Subscriptions |
| BR-006 Disable Finish while saving | `App.tsx` `saveJob`, `SubscriptionsStep` | Save |
| BR-007 / BR-008 Single Add/Edit route scheme; effect only on job load | `App.tsx` `screenPaths`, edit effect, `WizardCard` | Navigation |
| BR-010 Do not use a placeholder string as data | `App.tsx` `initialMappings` | Mapping |
| BR-015 / BR-016 Real dashboard fields; loading/error states | `App.tsx` `Dashboard`, list effect | Dashboard |
| BR-017 Real upload or clear "not uploaded" copy; restrict file types | `App.tsx` `GeneralStep`; backend endpoint | Upload |
| BR-018 / BR-019 / BR-023 Validation (UI and models) per product rules | `App.tsx`; `backend/app/routers/retirement_builder.py` | Validation |
| BR-025 / BR-026 Persistence; relative `/api/v1` base URL | `retirement_builder.py`, `db.py`; `App.tsx:17` | Deployment |

### Fix in next iteration
BR-020 error messages (use server `detail`), BR-022 real authentication and logout, BR-024 consume `/options`, BR-027 mobile sidebar, BR-028 dropdown keyboard support, BR-032 pin dependencies and add tests, BR-013/029/030/033/034/035/040 cosmetic and low-risk items.

### Requires product clarification
- BR-011 Template button: a template file `frontend/public/mapped_payroll_columns_HDT.xlsx` exists but nothing links to it.
- BR-012 Run: should it call an API, and what should the dashboard Status and Last Run Date show?
- BR-014 "Add mapping rule" vs "File Settings" naming, and what the trash "Manage dataset settings" button should do.
- BR-022 Is the demo login final? BR-025 Is in-memory storage final?
- Is there meant to be a Delete job control (the API supports it, the UI has none)?
- Should the `enable` flag be editable (the API has it, the UI always sends true)?

---

## 11. Release Readiness Verdict

**NOT READY.**

Evidence: four P1 defects each reproduced in the browser and at the API. Core save paths (schedule, mapping, file settings) discard user input, an unchanged edit overwrites stored configuration, and a refresh on an edit page creates a blank job. Twelve more P2 defects include duplicate submission, wrong dashboard values, a misleading upload, and a hardcoded `localhost` API URL that will not work behind the included IIS config. Backend persistence is in-memory. There are no automated tests. Type-check and Python compile pass, there are no console errors, and the pages render without crashes, so the problems are missing wiring, not instability.

---

## Appendix — Test data and side effects

- Records created by this audit: job ids 2–14 (names `QAAUDIT-*` or blank), all deleted afterwards. Job 1 (`QA_ADD_JOB`, 6 mapping rows) was never modified and was re-read before and after cleanup.
- The backend id counter advanced (next id is 15); in-memory counters cannot be reset without restarting the server, which was not done.
- I did not start or stop any server in this round; the servers that were already running were reused. Browser viewport and sessionStorage were restored.
- New untracked files from this audit: `QA_REPORT.md`, `qa-evidence/` (4 screenshots). No existing file was edited.

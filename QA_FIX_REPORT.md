# Retirement Builder — Fix Report

Scope: the 36 findings in `QA_REPORT.md`. Fields, labels, dropdown options, layout, styling and the backend API stub were left unchanged. No backend file was touched. All testing used the already-running servers (frontend :5173, backend :8000) and isolated `QAFIX-*` records.

## Root causes fixed (one change each, many symptoms)

| Root cause | Symptoms it removes |
|---|---|
| Schedule inputs were uncontrolled and the payload hardcoded | BR-001, schedule reset on Back/Next, wrong Run Day / Run Time / Schedule Type on the dashboard |
| Mapping inputs were uncontrolled, rows keyed by index, payload hardcoded | BR-002, BR-004 (mapping), BR-010 |
| Subscription client had no handler, rows keyed by index | BR-003, BR-004 (subscriptions) |
| File Settings modal state was local and the payload hardcoded `[]` | BR-009 |
| Job identity and mode lived only in memory, and the Add and Edit routes were mixed | BR-005, BR-007, BR-008 |
| No in-flight guard on Finish | BR-006 |

## A. Fix Summary

| Bug ID | Original issue | Fix applied | Files | Verification | Status |
|---|---|---|---|---|---|
| BR-001 | Schedule not saved/restored | Schedule held in state, loaded on edit, sent in payload | `App.tsx` | Browser: Monthly/9:45 PM/Monday/2030-01-02 survived Back/Next, saved and reopened identically | FIXED |
| BR-002 | Mapping edits lost, round trip reset | All row fields held in state; payload sends them; row ids replace index keys; unchanged edit saves identical data | `App.tsx` | Browser: start 5, length 12, Header, DV1, changed column/format stored exactly; unchanged Edit→Finish left job byte-identical | FIXED |
| BR-003 | Client not saved | `onClientChange` wired; value sent and reloaded | `App.tsx` | Browser: client stored on two rows and reloaded after a row delete | FIXED |
| BR-004 | Wrong values after row delete | Stable `id` keys and controlled inputs | `App.tsx` | Browser: deleting LASTNAME and FIRSTNAME left the other rows' values intact | FIXED |
| BR-005 | Refresh on edit created a new job | Wizard draft kept in sessionStorage (job id and form). Edit routes with no job context redirect to the dashboard; an edit can never POST | `App.tsx` | Browser: refresh mid-edit then Finish gave one `PUT /jobs/15` and the count stayed 2; direct `/jobs/edit/subscriptions` redirected, 0 requests | FIXED |
| BR-006 | Double-click created duplicates | `useRef` guard plus `disabled` Finish while saving | `App.tsx` | Browser: 3 rapid clicks gave 1 POST; button disabled during save | FIXED |
| BR-007 | Unsaved edits overwritten | Removed the effect that re-filled the form; job is loaded once when Edit is clicked | `App.tsx` | Browser: edit, Back, Forward, Back kept the unsaved text | FIXED |
| BR-008 | Add/Edit route mix | Separate `/jobs/new*` and `/jobs/edit/*` path sets; mode derived from the URL; Back and stepper stay in the same mode | `App.tsx` | Browser: Edit Back/stepper stayed on `/jobs/edit/*`; Add uses `/jobs/new/*`; headings match | FIXED |
| BR-009 | File Settings discarded and wiped | State lifted into `App`; Save & Continue commits, Cancel/Escape/backdrop discard; sent in payload; loaded on edit | `App.tsx` | Browser: saved rows reopened; Cancel and Escape did not commit; stored in the job | FIXED |
| BR-010 | `Select Format` saved as data | Seed row format set to empty (placeholder still displays); legacy `Select Format` values normalised to empty on load | `App.tsx` | Browser: POST body has `"format":""` | FIXED |
| BR-015 | Dashboard hardcoded values | Is Active now from `general.enable`; Run Day/Time/Type correct via BR-001. File Type, Status, Modified On and Last Run Date stay as demo values (the stub exposes no such properties) | `App.tsx` | Browser: dashboard shows Monday / 9:45 PM / Monthly for the test job | PARTIAL (rest intentional) |
| BR-016 | API failure shown as empty | `loading` / `ready` / `error` status; error row with `role="alert"` | `App.tsx` | Browser (forced network failure): "Unable to load…"; (forced pending request): "Loading…"; filter with no match still "No matching records found" | FIXED |
| BR-017 | Misleading upload text | Message now "File name saved with this job (upload is simulated)." Real upload not built | `App.tsx` | Browser: text verified | PARTIAL (stub kept) |
| BR-012 | Run message implied execution | Message states the run is simulated | `App.tsx` | Browser: message verified | FIXED (copy only; stub kept) |
| BR-020 | Raw/lost error messages | Network, 404, 422, non-JSON and 5xx cases each give a clear message; server `detail` shown when it is a string; error clears when the route changes | `App.tsx` | Browser (forced failures): all five messages verified | FIXED |
| BR-021 | Login message pointed to nothing | "Incorrect email or password." | `LoginPage.tsx` | Code change only; typecheck passes; not re-run in the browser | FIXED (not browser-verified) |
| BR-027 | Mobile sidebar overlapped content | Sidebar starts closed at ≤767px; collapsed state hidden on mobile (drawer still opens) | `App.tsx`, `styles.css` | Browser at 375px: no clipping, no horizontal scroll; menu button opens the 248px drawer | FIXED |
| BR-028 | Dropdown keyboard support | Arrow Up/Down, Enter, Escape, focus returned to trigger, `aria-activedescendant`; modal: role=dialog, focus on open, Tab trap, Escape closes | `App.tsx`, `styles.css` | Browser with real key presses: Enter opens, Down×2 + Enter selects, Escape closes | FIXED |
| BR-029 | Modal stayed open after browser Back | Modal closes on route change | `App.tsx` | Browser: modal closed after Back | FIXED |
| BR-030 | No sidebar highlight in wizard | "Retirement Builder" highlighted on every wizard screen | `App.tsx` | Browser: active item present at `/jobs/new` | PARTIAL (blank unknown-route page left as is) |
| BR-034 | No `aria-current` on stepper | `aria-current="step"` on the active step | `App.tsx` | Typecheck only; not re-inspected in the browser | FIXED (not browser-verified) |

## B. Remaining Issues

| ID | Classification | Note |
|---|---|---|
| BR-011 Template button does nothing | NEEDS PRODUCT DECISION | `frontend/public/mapped_payroll_columns_HDT.xlsx` exists but its intended use is undocumented |
| BR-013 Trash "Manage dataset settings" no-op | NEEDS PRODUCT DECISION | Intended action unknown |
| BR-014 "+" labelled "Add mapping rule" opens File Settings | NEEDS PRODUCT DECISION | Label vs behaviour |
| BR-018, BR-019 Required fields, trimming, email format | NEEDS PRODUCT DECISION | No documented rules, so none added |
| BR-023 Backend accepts values like hour 99 | KEEP AS STUB | Stub validation unchanged by request |
| BR-017 (rest) Any file type is accepted by the picker | NEEDS PRODUCT DECISION | No file-type rule documented |
| BR-015 (rest) File Type, Status, Modified On, Last Run Date | KEEP AS STUB | Not part of the stub contract |
| BR-024 `/options` not used by UI | KEEP AS STUB | Duplicated lists left as approved |
| BR-025 In-memory store | KEEP AS STUB | Intentional |
| BR-022 Client-side login, no logout | DEFER | Production authentication |
| BR-026 Hardcoded `localhost:8000` | DEFER | Deployment configuration |
| BR-032 `latest` dependency ranges, no automated tests | DEFER | No dependency changes allowed |
| BR-040 `/docs` exposed, `/health/db` status code | DEFER | Production hardening |
| BR-031 "ESC" vs "ECS" naming | NEEDS PRODUCT DECISION | "ESC" may be the Employer Services Corporation acronym |
| BR-033 Mapping table shows 3 of 8 columns at 768px | KEEP AS DEFINED | Already scrolls horizontally inside its card |
| BR-035 "Select Format" shown on every empty dropdown | NEEDS PRODUCT DECISION | Predefined placeholder text |
| BR-030 (rest) Unknown routes render a blank page | NEEDS PRODUCT DECISION | Placeholder pages are intentional |

**Unresolved implementation bugs:** none known. Items not checked in a browser: BR-021 (login text) and BR-034 (`aria-current`).

## C. Data Integrity Regression

Each run used the real UI against the live stub. "Reopen" means a fresh Edit load compared with the stored record.

| Section | Create | Save | Edit | Refresh | Reopen | Result |
|---|---|---|---|---|---|---|
| General | PASS | PASS | PASS | PASS (Add and Edit) | PASS | PASS |
| Schedule | PASS | PASS | PASS | PASS (Add) | PASS | PASS |
| Mapping | PASS | PASS | PASS (delete one row: only that row changed) | PASS (Add) | PASS | PASS |
| File Settings | PASS | PASS | PASS (reopened with saved rows; Cancel and Escape do not commit) | PASS (Add) | PASS | PASS |
| Subscriptions | PASS | PASS | PASS (row deleted; remaining row correct) | PASS | PASS | PASS |

Additional checks: an unchanged Edit→Finish left the stored job identical (deep-equal). Editing three things changed only those three (description, one mapping row, one subscription row).

## D. Automated Test Results

| Check | Result |
|---|---|
| TypeScript (`tsc --noEmit`, also the project's `lint` script) | PASS (exit 0), run after the final edit |
| Frontend build (`npm run build`) | PASS (2062 modules). Note: it regenerates the git-ignored `frontend/dist/`. It was run before the last small `aria-current` edit, so the final tree is type-checked but not rebuilt |
| Python compile (`compileall`) | PASS |
| API stub direct test (create/get/put/delete round trip incl. schedule, mapping, subscriptions, file settings) | PASS (run in-process, not against the live server) |
| Browser regression (live UI) | Executed: create with non-default values in every section, reopen, unchanged save, multi-field edit, Back/Next, Back/Forward, Add refresh, Edit refresh, direct edit URL, mapping and subscription add/delete, File Settings save/cancel/Escape, triple-click Finish, forced network/404/422/500/bad-JSON failures, dashboard error/loading/empty, keyboard dropdown, 375px mobile |
| Existing automated tests | None exist in the repo |
| Failed tests | None observed |
| Skipped / limits | Tablet (768px) and login screen were not re-tested after the changes; Playwright is not installed (built-in browser used); `service/` binaries not touched; no dependency installed |

## E. Files Modified

| File | Change |
|---|---|
| `frontend/src/App.tsx` | Controlled schedule, mapping, subscription and file-settings state; stable row ids; payload built from state; Add/Edit route sets with mode from the URL; sessionStorage draft for refresh; redirect when an edit has no job; save guard and disabled Finish; clearer save errors; dashboard loading/error states and Is Active; Run and upload message wording; dropdown and modal keyboard handling; modal commit/cancel; sidebar default and highlight; `aria-current` |
| `frontend/src/LoginPage.tsx` | Error message text only |
| `frontend/src/styles.css` | Two appended rules: active dropdown option highlight; hide the collapsed sidebar at ≤767px |
| `QA_FIX_REPORT.md` | This report |

Not modified: all backend files, `package.json`, lockfile, `public/`, `service/`. Nothing is committed. `frontend/dist/` was regenerated by the build (ignored by git).

The working tree already contained your uncommitted edits to `App.tsx` and `styles.css` (the tab/UI work). My changes sit on top of them. Backups of the original `App.tsx`, `styles.css` and `LoginPage.tsx` are in the session scratchpad.

## F. Final Application Status

**FUNCTIONALLY STABLE FOR STUB-BASED DEVELOPMENT**

Evidence: all four P1 data-loss defects and the duplicate-submit, navigation and state-reset defects were reproduced before and are gone in the live regression. Create, save, reopen, unchanged re-save, edit, refresh and failure paths all round-trip through the existing stub without data loss or duplicate jobs. What remains is product decisions and intentionally deferred production work, listed in section B.

Test data: records created (ids 15, 16) were deleted. Job 1 (`QA_ADD_JOB`, 6 mapping rows) was never modified. The backend id counter has advanced past 16.

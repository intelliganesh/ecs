# Retirement Builder Phase 2 bug report

Ten distinct defects were confirmed by browser or SQL-backed API execution. P1 identifies incorrect job actions, scheduling, execution, history or multiworker persistence. P2 identifies a usability, history-navigation or accessibility defect with a narrower immediate impact. No Critical defect was confirmed.

## RET-B001 · Hidden selected job can still run or be edited

**High severity · P1 · RET-F013 · [RET-T018](01-test-execution-report.md#ret-t018)**

**Test data and reproduction** — Select UX Payroll 2, then enter No-such-qa-name in Filter File Name.

**Expected** — When the selected row is hidden, clear the selection or show the selected job explicitly and prevent ambiguous actions.

**Actual** — No rows remained visible. Both Edit and Run stayed enabled. No run was needed to establish the unsafe affordance.

**Suggested fix** — Clear selection on filtering out the selected row, or resolve the action target from visible rows.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:10) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B001-hidden-selection.jpg) · [frontend/src/App.tsx:482](/Users/apple/Desktop/ecs/frontend/src/App.tsx:482)

## RET-B002 · Browser Back restores a canceled Add draft

**Medium severity · P2 · RET-F027 · [RET-T038](01-test-execution-report.md#ret-t038)**

**Test data and reproduction** — Enter UI Cancel Draft in Add General, advance to Schedule, click Cancel, then use browser Back and open General.

**Expected** — Back cannot revive explicitly discarded input.

**Actual** — General showed UI Cancel Draft again. A fresh Add click reset the draft in the other tested path.

**Suggested fix** — Clear mounted draft state on cancel and invalidate the canceled navigation context.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:24) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B002-cancel-history.jpg) · [frontend/src/App.tsx:276](/Users/apple/Desktop/ecs/frontend/src/App.tsx:276) · [frontend/src/App.tsx:459](/Users/apple/Desktop/ecs/frontend/src/App.tsx:459)

## RET-B003 · Editing changes Last Run Date without execution

**High severity · P1 · RET-F071 · [RET-T111](01-test-execution-report.md#ret-t111)**

**Test data and reproduction** — Use job 38 with real history at 2026-10-01 09:00. Read dashboard list, PUT only description, reload the list, and read the history transaction.

**Expected** — Last Run Date reflects the last actual execution, 2026-10-01.

**Actual** — List changed to 2026-11-17 after PUT. History stayed at 2026-10-01 09:00. No Run request occurred.

**Suggested fix** — Derive the dashboard field from execution history. Keep modification timestamps independent and retain any legitimate legacy fallback.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:21) · [backend/query.brl:701](/Users/apple/Desktop/ecs/backend/query.brl:701) · [backend/query.brl:772](/Users/apple/Desktop/ecs/backend/query.brl:772) · [backend/app/routers/retirement_builder.py:535](/Users/apple/Desktop/ecs/backend/app/routers/retirement_builder.py:535)

## RET-B004 · Disabled job is unrecoverable from the standard UI

**High severity · P1 · RET-F033 · [RET-T048](01-test-execution-report.md#ret-t048)**

**Test data and reproduction** — Edit UX Later 20 (ID 3), turn Enable off, save, then search for the job or a disabled-jobs view.

**Expected** — A supported UI flow lets an authorized user locate and re-enable the job.

**Actual** — Search showed no job and there was no restore control. In separate API verification, the ID could still be enabled with a PUT.

**Suggested fix** — Provide a supported disabled job listing with a re-enable action.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:21) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B004-disabled-job.jpg) · [frontend/src/App.tsx:561](/Users/apple/Desktop/ecs/frontend/src/App.tsx:561) · [backend/app/routers/retirement_builder.py:795](/Users/apple/Desktop/ecs/backend/app/routers/retirement_builder.py:795) · [backend/query.brl:698](/Users/apple/Desktop/ecs/backend/query.brl:698)

## RET-B005 · Payroll filter saves a text operand and fails when run

**High severity · P1 · RET-F083 · [RET-T134](01-test-execution-report.md#ret-t134)**

**Test data and reproduction** — Create a Company Payroll job with the condition Company Name = 3, using Audit Alpha and Audit Beta. Inspect the saved rule and use the Run endpoint.

**Expected** — The application rejects an incompatible operand at configuration time or executes the supported comparison.

**Actual** — POST returned 201. Run returned 422 with “A condition uses a value that is not a number.” History recorded Failed.

**Suggested fix** — Expose only numeric payroll columns for numeric conditions and validate that compatibility on save.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:22) · [backend/app/routers/retirement_builder.py:703](/Users/apple/Desktop/ecs/backend/app/routers/retirement_builder.py:703) · [backend/app/retirement_results.py:247](/Users/apple/Desktop/ecs/backend/app/retirement_results.py:247)

## RET-B006 · Edit detail failure produces no visible feedback

**Medium severity · P2 · RET-F018 · [RET-T024](01-test-execution-report.md#ret-t024)**

**Test data and reproduction** — In the isolated proxy return 404 for GET /jobs/1. Click the name in the dashboard. Repeat with a disconnected response.

**Expected** — Show a visible error and usable retry path while retaining list context.

**Actual** — Both faults left the user on the dashboard without an alert or an explanation.

**Suggested fix** — Render the detail-load error on the dashboard and preserve the selected row for retry.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:12) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B006-hidden-edit-error.jpg) · [frontend/src/App.tsx:353](/Users/apple/Desktop/ecs/frontend/src/App.tsx:353) · [frontend/src/App.tsx:575](/Users/apple/Desktop/ecs/frontend/src/App.tsx:575)

## RET-B007 · Run Time sort reverses midnight and early morning

**Medium severity · P2 · RET-F010 · [RET-T015](01-test-execution-report.md#ret-t015)**

**Test data and reproduction** — Filter Timing sort data one/two, scheduled at 12:05 AM and 1:05 AM. Click Run Time ascending.

**Expected** — Midnight sorts before 1:05 AM.

**Actual** — Natural comparison of displayed text put 1:05 AM first.

**Suggested fix** — Compare a normalized time-of-day key and define where blank times appear.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:19) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B007-time-sort.jpg) · [frontend/src/App.tsx:489](/Users/apple/Desktop/ecs/frontend/src/App.tsx:489)

## RET-B008 · Tab skips nearby settings controls when a picker is open

**Medium severity · P2 · RET-F061 · [RET-T094](01-test-execution-report.md#ret-t094)**

**Test data and reproduction** — Open File Settings for a job with two sorts and one condition. Focus the first Sorting Order Mapping Column search. Press Tab.

**Expected** — Keyboard focus advances in logical dialog order from the open picker.

**Actual** — Focus jumped to Delete Conditional Statements: row 1. The skipped controls are reachable separately.

**Suggested fix** — Include the portalled picker in the modal focus strategy, with explicit next/previous and Escape return behavior.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:69) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B008-picker-focus.jpg) · [frontend/src/App.tsx:907](/Users/apple/Desktop/ecs/frontend/src/App.tsx:907)

## RET-B009 · A partially configured schedule silently becomes manual-only

**High severity · P1 · RET-F038 · [RET-T057](01-test-execution-report.md#ret-t057)**

**Test data and reproduction** — Create a job with Monthly, 12:59 AM and blank Start Date. Finish and inspect the dashboard.

**Expected** — Require a Start Date for the populated schedule or surface an explicit manual-only choice before save.

**Actual** — Create returned 201 and the dashboard showed Manual only. The wizard had no specific missing-date prompt.

**Suggested fix** — Treat completely blank scheduling as manual. Require a date when schedule fields are entered, and show that error at the input.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/browser-cases.ndjson:52) · [Screenshot](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/RET-B009-schedule-no-date.jpg) · [frontend/src/App.tsx:234](/Users/apple/Desktop/ecs/frontend/src/App.tsx:234) · [frontend/src/App.tsx:375](/Users/apple/Desktop/ecs/frontend/src/App.tsx:375)

## RET-B010 · Create retry can insert a duplicate across HTTP workers

**High severity · P1 · RET-F072 · [RET-T113](01-test-execution-report.md#ret-t113)**

**Test data and reproduction** — Send the same JSON and Idempotency-Key to two independent test backend processes using one isolated DB. Compare both responses and the saved rows.

**Expected** — Identical retries for a create request return the original job.

**Actual** — Both returned 201. First ID 116, second ID 117, and SQL found two rows. Same-process retry passed separately.

**Suggested fix** — Persist replay identity in a shared transactional store when multiworker routing or restart resilience is required.

[Execution evidence](/Users/apple/Desktop/ecs/docs/retirement-builder-audit/phase-2/evidence/api-results.ndjson:108) · [backend/app/routers/retirement_builder.py:187](/Users/apple/Desktop/ecs/backend/app/routers/retirement_builder.py:187) · [backend/app/routers/retirement_builder.py:847](/Users/apple/Desktop/ecs/backend/app/routers/retirement_builder.py:847)

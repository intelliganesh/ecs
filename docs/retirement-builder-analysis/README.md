# Retirement Builder investigation and learning guide

**Investigated: 18 November 2026.** Target: `http://localhost:5174/retirement-builder`. Scope: actual frontend → FastAPI → SQL Server → report files/email → frontend. Only analysis documents were added; no application code or database data was modified by this investigation. Existing uncommitted application edits were preserved and are part of the analyzed snapshot.

**Main finding:** this feature builds and runs configurable payroll/CSV report jobs. It does not calculate an individual's retirement savings. Finish saves configuration; a separate Run or scheduler execution creates outputs. [frontend/src/App.tsx:449](/Users/apple/Desktop/ECS/frontend/src/App.tsx:449), [backend/app/routers/retirement_builder.py:1199](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1199).

## Read in this order

1. [Product overview and simple example](01-product-overview.md)
2. [Complete user flow, routes, refresh and failure behavior](02-complete-user-flow.md)
3. [Every UI control, checkbox and condition](03-ui-controls-and-conditions.md)
4. [Every dropdown and its actual data source](04-dropdown-data-sources.md)
5. [All APIs, payloads, errors and request sequence](05-api-and-request-flow.md)
6. [Stored procedure, exact SQL batches and table map](06-stored-procedures-and-sql.md)
7. [Actual calculations, formatting and business rules](07-calculations-and-business-rules.md)
8. [React state, draft persistence, saving and editing](08-state-and-data-persistence.md)
9. [Complete manual test checklist and executed-test limits](09-complete-test-scenarios.md)
10. [Technical questions, simple answers and traceability](10-technical-questions-and-answers.md)

## Counts and convention

| Item | Count | Meaning |
|---|---|---|
| Core screens | **5** | Dashboard + General/Schedule/Mapping/Subscriptions |
| Additional dialogs | **2** | File Settings and Run job; Login is1 adjacent screen,8 views including it |
| Fields and control definitions | **108** | Inventory rows; repeated runtime data rows count once per definition; includes shell/actions/shared menu behavior; excludes4 adjacent Login controls |
| Dropdown definitions | **16** | Includes both alternative company/client branches; repeated rows count once |
| Checkbox definitions | **6** | Select all, select job, enable, store results, include header, merge files |
| Radio groups | **0** | No source-selection radios or retirement-age radio/dropdown |
| Feature HTTP operations | **7** | Method/path pairs over5 path templates |
| Application stored procedures | **1** | dbo.usp_CompanyPayrollReport; plus1 SQL Server system helper sys.sp_executesql inside it |
| SQL units identified | **32** | 15 query.brl batches +13 direct constants +1 generated wrapper +3 H/D/T templates; reused edit batch, procedure internals, health and migration SQL not counted again |
| Referenced persistent data tables | **17** |16 dbo tables inspected through metadata;1 cross-database client table referenced by failing API |
| Existing automated tests passed | **63** |54 backend +9 frontend utility tests; isolated/mocked behavior, not live write verification |
| Manual checklist scenarios | **114** |Each labeled actual browser/HTTP observation or expected from source |

Control-count inventory: [control-inventory.json](evidence/control-inventory.json). Counts include alternative and conditional definitions, not an assertion that all108 appear on one page.

## VERIFIED versus NOT VERIFIED

| Evidence level | What is established |
|---|---|
| VERIFIED — source | Current route components, controls, defaults/validation, effects/state, fetch paths, JSON models, SQL definitions/call sites, approved templates, Python transforms, scheduler/mail code. File+line references accompany findings. |
| VERIFIED — live read-only | Frontend200; DB health connected; jobs/options/detail GET200; clients GET503; schema columns and lookup metadata; installed procedure name/signature/definition matching migration012. |
| VERIFIED — browser | Demo entry, General mandatory messages,5 separator options, blank manual schedule, four wizard steps, mapping add/defaults, empty Format availability, settings Cancel, same-tab draft refresh recovery, Cancel return. |
| VERIFIED — existing tests |54 backend +9 frontend tests passed; DB guard prevented unmocked connections during backend tests. This verifies assertions with fake/local data. |
| NOT VERIFIED — product intent | Actual user roles, original business requirements, vendor retirement specification and acceptance of exports by downstream provider. |
| NOT VERIFIED — live write/external |Create/update/run success against current DB, live report calculations/output, scheduler execution/timezone, email acceptance/inbox delivery and failure/crash recovery. No writes or emails were performed. |
| NOT VERIFIED — client API root cause |503 observed; source query depends on prism.export.Client_Details, but exact server error/permissions/table availability not established. |

[Verification record](evidence/verification.md), [sanitized HTTP snapshot](evidence/read-only-http.json), [sanitized DB snapshot](evidence/read-only-database.json), [source snapshot hashes](evidence/source-snapshot.json).

## Important conditional flows

- Add defaults to companyPayroll; existing CSV jobs use Clients catalog and server input files. No source-selector UI. [frontend/src/App.tsx:258](/Users/apple/Desktop/ECS/frontend/src/App.tsx:258), [frontend/src/App.tsx:1070](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1070).
- Blank entire schedule is manual-only. Filling time/frequency while leaving Start Date blank can still save a manual-only job. [frontend/src/App.tsx:273](/Users/apple/Desktop/ECS/frontend/src/App.tsx:273), [backend/app/routers/retirement_builder.py:467](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:467).
- Enable exists only on Edit; disabled records disappear from enabled-only dashboard. [frontend/src/App.tsx:871](/Users/apple/Desktop/ECS/frontend/src/App.tsx:871), [backend/query.brl:693](/Users/apple/Desktop/ECS/backend/query.brl:693).
- Unsupported payroll mapping needs Default Value; Format filters by source type, and source changes can clear incompatible selection. [frontend/src/App.tsx:284](/Users/apple/Desktop/ECS/frontend/src/App.tsx:284), [frontend/src/App.tsx:1010](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1010).
- Store Results applies on run; Include Header controls heading line; Merge Files affects recipient attachments. [backend/app/routers/retirement_builder.py:1154](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1154), [backend/app/retirement_results.py:544](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:544), [backend/app/report_mail.py:78](/Users/apple/Desktop/ECS/backend/app/report_mail.py:78).
- Run dates are optional/inclusive;1900-01-01 is the unbounded sentinel. CSV override is API-only and skips email. [backend/app/routers/retirement_builder.py:1241](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1241), [backend/app/routers/retirement_builder.py:1228](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1228).

## Important calculations and surprises

- SQL COUNT(*)/SUM(net_salary) per company_name/payroll_month; Pay Date label means payroll_month, not payroll.pay_date. [backend/config/payroll_record_queries.json:3](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:3).
- Detail filters and numeric/text sorting happen in Python after SQL aggregation; conditions round to2 decimal places; selected numeric output formats use Decimal ROUND_HALF_UP. [backend/app/routers/retirement_builder.py:500](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:500), [backend/app/retirement_results.py:474](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:474), [backend/app/retirement_results.py:502](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:502).
- Date grouping/naming, H/D/T mapping, numeric/date/phone/SSN/text transforms, optional result row counts and recipient subset matching are actual business rules; no investment-growth formula is used. [backend/app/retirement_results.py:325](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:325), [backend/app/retirement_results.py:515](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:515), [backend/app/report_mail.py:40](/Users/apple/Desktop/ECS/backend/app/report_mail.py:40).
- Current Format options are empty because live lookup rows are naming categories; code-supported transforms are not automatically dropdown choices. Clients endpoint currently503. [backend/app/routers/retirement_builder.py:377](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:377), [HTTP evidence](evidence/read-only-http.json).
- Start Position is not used to slice output. Last-run date can be affected by editing; query42's latest range subquery is global rather than per-job. [backend/app/retirement_results.py:550](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:550), [backend/query.brl:765](/Users/apple/Desktop/ECS/backend/query.brl:765), [backend/query.brl:693](/Users/apple/Desktop/ECS/backend/query.brl:693).

## How to verify missing information

Use the scenario IDs in document09 in an isolated writable test environment for save/run/mail/scheduler checks. Ask the product owner for provider format and role requirements. For client503, inspect authorized SQL metadata/permissions and run query43 read-only while recording a sanitized error category. Compare running scheduler settings and observed time slots against the code; do not infer live timezone from the browser. All such work remains outside this read-only investigation.

## Source references

Links use absolute workspace paths plus1-based line numbers as supported by the desktop app. They describe the inspected working tree; source edits can shift lines later. [source-snapshot.json](evidence/source-snapshot.json) records SHA-256 hashes. For a portable copy, preserve the repository tree and use each link's file label/line to navigate in an editor.

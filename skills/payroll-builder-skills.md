# Payroll Builder — analysis and implementation planning reference

Read the project-wide [AGENTS.md](../AGENTS.md) first. Use this document when
analysing the existing Payroll Builder database/SQL contract, comparing it with
Retirement Builder, or planning an explicitly requested implementation.

This is a project reference document, not an installed Codex skill. It preserves
the read-only investigation discussed with the user on **24 November 2026**.
It is not an instruction to build, repair, migrate, enable or run anything.
Retirement job 60 testing permissions do not apply to payroll jobs.

## Scope, evidence and freshness

- The investigation used SELECT-only inspection of the connected `Syd_Testing`
  database, SQL Server object/column/parameter metadata, installed procedure and
  view definitions, configuration catalogs and saved payroll query structures.
  Application source and `backend/query.brl` were inspected as well.
- No report procedure was executed. No jobs were saved/run, no scheduler was
  triggered, no mail was sent and no application/database changes were made for
  that investigation. Individual employee payroll records were not inspected.
- Database counts, settings and implementation status below are a **dated
  snapshot**, not permanent fixtures. Reconfirm only when the current task
  authorizes the necessary inspection. A documentation-only task does not require
  a fresh database connection, service startup or report execution.
- Findings established from SQL definitions are distinguished from actual Run
  behavior. The listed defects/risks were not reproduced through live Runs.
- Temporary SQL/metadata snapshots were used during the investigation. They are
  not durable repository evidence and this guide does not depend on `/tmp`
  files. Reinspect installed definitions under an authorized analysis task when
  exact current SQL is needed; do not execute a procedure to obtain its definition.
- Older documents under `docs/retirement-builder-analysis/` describe a sample
  database/procedure in places. They must not override the connected database's
  current contract without verification.

For read-only work, inspect files, logs, API GETs or DB SELECTs only. A report
procedure can write history, change state and create/drop tables even when its
main output looks like a SELECT. Do not run migrations or modify schema, source
data, existing queries or stored procedures without explicit task authorization.
Keep credentials and personal/payroll/SSN values out of shared evidence.

## Three components that must remain distinct

| Component | Observed role/status |
| --- | --- |
| Retirement Builder application | Implemented UI/API using `rjob*` configuration tables. Effective configured report procedure was `dbo.rjobbuilder`. |
| Legacy Payroll Builder | Separate `payroll_*` configuration, mapping catalog, wage mappings, grouping catalog and `dbo.payrolljobbuilder` procedure. |
| Company Payroll sample source | Compatibility/sample path inside Retirement Builder using `payroll_source.py` and approved H/D/T templates. It is not the full legacy Payroll Builder. |

The `/payroll-builder` page was a blank placeholder and the backend registered
only the Retirement Builder router. Changing the shared procedure setting to
`payrolljobbuilder` alone would leave persistence and scheduling wired to
retirement tables. The default setting in source is not proof of its effective
configured value.

Relevant source:

- [Frontend screens and navigation](../frontend/src/App.tsx)
- [Backend router registration](../backend/app/main.py)
- [Settings definitions](../backend/app/core/config.py)
- [Retirement request models and persistence](../backend/app/routers/retirement_builder.py)
- [Company Payroll compatibility source](../backend/app/payroll_source.py)
- [Sample templates](../backend/config/payroll_record_queries.json)

## Purpose and expected end-to-end flow

The inspected Payroll Builder is a configurable export of **existing** payroll,
especially wages, overtime, tips, employer identification and workers'
compensation classifications. It does not establish a complete payroll engine
for tax withholding, net-pay calculation, payments or payslip creation.

Expected integration flow, subject to confirmed business requirements:

1. Select or create a payroll export job within the current task's permissions.
2. Configure filename, description, file format, filename convention and flags.
3. Configure schedule and H/D/T output mappings.
4. Select client subscriptions, recipient settings and optional file merging.
5. Configure optional client earning-code-to-wage-field mappings.
6. Configure grouping only after its execution contract is resolved.
7. Save into payroll configuration tables through the application's normal path.
8. For an explicitly authorized Run, obtain source records for the job's clients
   and date range, calculate export values and execute saved projections.
9. Serialize/group files, record history and perform only authorized delivery.

This flow describes intended integration; it does not imply that the modern
Payroll Builder screens/API already exist or authorize these actions.

## Database snapshot

| Entity | Observed count |
| --- | ---: |
| Payroll jobs | 14 |
| Retirement jobs | 67 |
| Payroll field mappings | 168 |
| Payroll saved queries | 42 |
| Payroll mapping catalog entries | 56 |
| Retirement mapping catalog entries | 105 |
| Payroll wage mappings | 31 |
| Saved payroll grouping selections | 0 |

All 14 payroll jobs were disabled, had Store Results OFF and selected CSV.
Each had one H, one D and one T saved query. Two had merging enabled. No orphan
query/mapping rows or jobs without schedules were found in the specific checks
performed. These checks do not establish all possible configuration integrity.

All 31 wage mappings belonged to one job and targeted `OT13`, `OT23` or `OTW`.
All existing field mappings used one dataset number; 142 of 168 rows had NULL
`ColSeqNo`. Do not infer output order from these incomplete sequences.

## Configuration tables and SQL definitions

| Table | Purpose |
| --- | --- |
| `payroll_job` | Main job metadata, filename/format, enable/merge/header flags, result storage and biweekly state. |
| `payroll_schedule_info` | Start datetime, frequency, weekday/monthly settings, intervals, hour/minute/session. |
| `payroll_file_detail` | Output labels, source mappings, defaults/formats, H/D/T type, positions/widths, dataset and sequence. |
| `payroll_query` | Saved H/D/T SELECT fragments, Conditions and Sort_Order. |
| `payroll_client_detail` | Client subscriptions and email configuration. |
| `payroll_file_sorting_details` | Sort priority and source column. |
| `payroll_file_condition_details` | Source column, comparison symbol and numeric comparison value. |
| `payroll_mapping_column` | Mapping keys, labels, types and ApplyGroup flag. |
| `payroll_wage_mapping` | Job/client-specific earning-code mappings to wage fields. |
| `payroll_grouping` | Saved grouping selections. |
| `payroll_master_grouping` | Available grouping dimensions. |
| `payroll_history` | Latest status and trigger information. |
| `payroll_history_details` | Run flag and execution date ranges. |
| `payrollformat` | Payroll formatting catalog; observed empty. |

`payroll_detail` and `payroll_job_schd_master` also exist as legacy tables; their
presence alone does not establish a requirement to use them in the new module.

Legacy SQL definitions are principally IDs **200–219** in
[query.brl](../backend/query.brl):

| SQL ID | Purpose |
| --- | --- |
| 200 | List enabled payroll jobs with schedule/history. |
| 201 / 202 | Insert / update main job settings. |
| 203 | Delete related configuration rows for replacement; not a read-only operation. |
| 204 / 205 / 206 / 207 | Save queries / field mappings / subscriptions / schedules. |
| 208 / 209 / 210 | Save sorting / save conditions / read mapping catalog. |
| 211 / 214 | Earning-code catalog / earning-code search. |
| 212 / 213 | Save wage mapping / save grouping selection. |
| 216 / 217 / 218 | Replace/update execution history. |
| 219 | Read grouping catalog. |

The existing edit procedure is `dbo.Get_payroll_file_info_byjobid`. Its result
sets cover job, query, subscriptions, mappings, schedule, sorting, conditions,
wage mappings, grouping selections and grouping catalog. It contains hardcoded
database references and does not provide reliable column ordering by itself.

## User-facing configuration fields

| Area | Fields/controls |
| --- | --- |
| General | File name, description, File Format, Output File Name Format, enabled, Store Results. |
| Schedule | Start date/time, frequency, hour/minute, AM/PM, weekday; storage additionally supports intervals and monthly settings. |
| Output mapping | Output label, source column, default value, format, H/D/T, start position, length, DataSetNo, ColSeqNo. |
| Subscriptions | Client, email recipients, Merge Files; main storage also includes mergeemail. |
| Sorting | Priority/order and source column; confirm direction behavior for the SQL path. |
| Conditions | Source column, operator, value and type; account for storage limitations. |
| Wage mappings | Client, target wage field, earning/pay code and saved search term. |
| Grouping | Selected dimensions and intended numeric aggregation behavior. |
| Manual Run | Start/end dates. |
| Dashboard/history | Job status, last execution, messages, schedule and execution date range. |

Most shared fields have models in the Retirement Builder router. Full payroll
wage-mapping and grouping forms are additional work. Do not present a storage
column as a finished UI feature without inspecting the implementation.

## Complete payroll mapping catalog: 56 entries

Use exact keys for SQL/persistence and catalog descriptions for labels. Do not
substitute a display label, saved alias, job ID or client ID for a source key.

| Category | Source keys |
| --- | --- |
| Identifiers | `PrismID`, `RetNum`, `emplid`, `ID_NUM` |
| Voucher information | `voucherid`, `VchrNo`, `VchCount` |
| Names and SSN | `firstname`, `middle`, `lastname`, `Employee_Name`, `ssn` |
| Payroll dates | `paydate`, `perstart`, `perend` |
| Employment dates/status | `statusdate`, `emplstatus`, `birthdate`, `hiredate`, `termdate` |
| Organization | `division`, `deptcode`, `PayGroup`, `HomeLoc`, `LocName`, `JobCode` |
| Personal/contact | `gender`, `marStat`, `address1`, `address2`, `city`, `state`, `zip`, `email`, `phone` |
| Hours | `reghours`, `othours`, `total_hours_worked`, `hours_worked`, `ytdHours`, `ytdallhours` |
| Earnings/rates | `earnings`, `grosswage_minus_reimb`, `ytdGross`, `annPayRate`, `TIPS`, `OTW`, `OT23`, `OT13`, `TOTAL_AMT`, `total_earning` |
| Employer/WC | `federal_id`, `wc_code`, `wc_code1` |
| Other | `dedid`, `Default` |

Catalog types were 30 char, 7 date, 2 int, 16 numeric and 1 all (`Default`).

- `PrismID` comes from the employee identifier; `RetNum` is the client identifier.
- `emplid` is populated from `EMPLOYEE_COM.ee_No`; the catalog label "Employer
  Id" should not be treated as a verified business meaning.
- `wc_code` is voucher-related WC class; `wc_code1` comes from current job/class
  information. They are not interchangeable.
- `Default` is a constant-value mapping choice, not a physical source column.
- `valid_flag` is an additional procedure control field, not a catalog option.
- Catalog membership does not prove a field is populated or calculated correctly.

## Source tables and relationships

The following objects were confirmed in `prism.export`:

| Source | Purpose |
| --- | --- |
| `EMPLOYEE_COM` | Employee/client relationship, employment/job information. |
| `EMPLOYEE_PER` | Names, demographics and contact information. |
| `EMPLOYEE_PAY` | SSN and pay attributes. |
| `CLIENT_DETAILS` | Client/employer information including federal ID. |
| `EPV` | Payroll vouchers, pay dates/periods, earnings and void information. |
| `EPV_EARNINGS` | Earning codes/amounts/hours and WC class. |
| `EPV_OTHER_EARNINGS` | Additional amounts used by the wage-mapping view. |
| `EARNING_CODES` | Code descriptions and earning classifications. |
| `CLIENT_DETAILS_PAY_CODES` | Client-specific earning-code availability. |
| `EMPLOYEE_PAYROLL_REGISTER` | YTD amounts/hours. |
| `LOCATION_CODESS` | Location labels. |
| `JOB_CODES`, `JOB_CODE_MASTER`, `JOB_CODE_MASTER_WC` | Current WC classification. |

The base population joins employee/client, personal and pay records, then payroll
vouchers aggregated by client, employee and pay date. Later updates enrich the
temporary rows; do not assume they preserve voucher/WC granularity correctly.
Initial voucher selection excludes voids, but subsequent calculations do not
uniformly repeat that exclusion. Client-specific exceptions exist in the SQL;
confirm their intended applicability rather than generalizing or removing them.

## Stored-procedure contract and side effects

`dbo.payrolljobbuilder` accepts:

| Parameter | Meaning |
| --- | --- |
| `@client_id int` | **Payroll job ID**, used to read configuration; not the subscribed client ID. |
| `@paystartdate date` | Manual start date. |
| `@payenddate date` | Manual end date. |
| `@runType varchar(1)` | `A` manual, `S` scheduled. |

Actual clients come from `payroll_client_detail`. Manual dates restrict pay date;
scheduled dates are computed in the procedure using schedule/current-date logic.
Do not assume a modern runner's sentinel behavior is safe for every legacy path.

The procedure creates a temporary `#ret_builder_info` table, loads/enriches source
records, applies wage overrides, then executes saved H, each D, and T fragments.
It appends FROM/conditions/order expressions around those saved SELECT fragments.
Detail cursor order is not an explicit dataset identity.

Normal saved projections begin with:

```text
valid_flag, retnum, sort1
```

These control validity/client/date grouping and must be removed before export.
Metadata-only trailer projections are not totals rows. No-data results use
placeholder shapes, including `valid_flag1`, which must not become report data.

Persistent effects include `payroll_history_details` insertion, biweekly
`payroll_job.enddate` updates, and possible output-table DROP/CREATE/INSERT when
Store Results is enabled. H/D/T SELECT output does not make invocation read-only.

## Payroll calculations found in the procedure

| Field | Inspected logic |
| --- | --- |
| `grosswage_minus_reimb` | Initially cash earnings minus reimbursement; subsequently updated from earning amounts whose bill code is not EXPS. |
| `reghours` | Hours for exact earning code REG. |
| `othours` | Hours for exact earning code O/T. |
| `total_hours_worked` | Sum of TS_Hours_Worked_Amt. |
| `hours_worked` | Sum of TS_Hours_Units under the applicable earning-code rules. |
| `TIPS` | Amounts for TIPS% codes under surrounding eligibility rules, including client-specific exceptions. |
| `OTW` | Amounts for O/T% codes under surrounding eligibility rules. |
| `OT23` | ROUND(overtime amount * 2 / 3, 2). |
| `OT13` | Overtime amount minus the rounded two-thirds portion. |
| `earnings` | grosswage_minus_reimb - ISNULL(TIPS,0) - ISNULL(OTW,0). |
| `total_earning` | earnings + ISNULL(TIPS,0) + ISNULL(OTW,0). |
| YTD fields | Register/earning information selected using the server's current year. |
| `TOTAL_AMT` | Catalog says Earnings + OT23, but no explicit assignment implements that formula. |

The fractions split an existing overtime amount; they do not calculate overtime
eligibility or derive pay from hours/rates. Treat them as an export contract
requiring business confirmation, not a general payroll/legal rule.

The common key `earnings` has different semantics in retirement and payroll.
The configured retirement procedure uses retirement-base earnings logic;
payroll ultimately excludes tips and overtime from its wage field.

## Wage mapping and grouping

`payroll_wage_mapping` stores job, client, wage_column, pay_code and search_word.
The selected pay code is meaningful to the calculation; search_word is not used
as a calculation rule in the inspected procedure/view.

`dbo.payroll_wage_data_wcsumm` joins vouchers, earning rows, wage mappings and
other earnings, grouping by job/client/employee/target/pay date/WC class. The
procedure applies those totals to target wage fields, with special fractions
for OT23 and OT13. Client-specific pay-code lookup must remain client-scoped.
The view's join cardinality and additional-earnings coverage need validation.

Grouping catalog:

| Stored identifier | Label |
| --- | --- |
| `federal_id` | Federal ID |
| `retnum` | Client ID |
| `pay_date` | Pay Date |
| `wc_code` | Worker Comp Code |

ApplyGroup is Yes for `earnings`, `OT23`, `OT13`, `TOTAL_AMT`, `OTW` and
`total_earning`. This flag describes intended groupable fields, not working
aggregation. The procedure reads grouping selections but assigns an unused
string; the inspected saved D projections contain no aggregation. Also,
`pay_date` differs from the temporary source key `paydate`. Resolve these
contracts before promising a working grouping feature.

## Comparison with Retirement Builder

| Area | Retirement | Payroll |
| --- | --- | --- |
| Purpose | Retirement contribution/census export. | Wage, overtime, tips and WC-oriented export. |
| Persistence | rjob* tables. | payroll_* tables. |
| Procedure | Effective setting was dbo.rjobbuilder; rjobbuilder_new also exists. | dbo.payrolljobbuilder. |
| Catalog | 105 entries. | 56 entries. |
| Business values | Pretax/Roth/catch-up, loans, employer contributions, retirement totals. | Tips, overtime/fractions, employer/WC information and wage totals. |
| Earning-code mappings | No equivalent in current builder models. | Additional client-specific feature. |
| Explicit grouping selections | No equivalent in current builder models. | Stored, but execution unresolved. |
| Shared UI | General, schedule, mappings, subscriptions, settings, downloads. | Strong component reuse potential; still requires its own integration. |
| Multi-dataset exports | Modern application identity/alignment safeguards exist. | Must be integrated and verified; cursor order alone is insufficient. |

47 catalog names are shared, including Default: about 84% of payroll's entries.
This is **name overlap**, not code-reuse percentage or calculation equivalence.
Payroll-only keys are `federal_id`, `wc_code`, `wc_code1`, `TIPS`, `OTW`, `OT23`,
`OT13`, `TOTAL_AMT`, `total_earning`. Retirement has 58 entries absent from payroll,
principally contributions, loans, eligibility/ownership and retirement totals.

## Findings and unresolved risks before implementation

These are definition/configuration findings from the dated investigation. Do not
claim runtime reproduction, or fix them without a task authorizing that work.

| Finding | Impact / required decision |
| --- | --- |
| TOTAL_AMT has no explicit formula assignment. | Two saved jobs map it; no observed wage mapping targets it. Resolve its promised value. |
| Wage override UPDATE omits wc.job_id = current job. | Cursor targets are job-scoped, but the UPDATE can match another job's amounts sharing other keys. |
| Grouping string is unused. | Saved grouping choices do not establish actual aggregated output. |
| 142/168 mapping rows lack ColSeqNo. | Recover order from uniquely confirmed saved projections, not guessed database row order. |
| Voucher enrichment joins employee/client without pay date. | Multiple vouchers/dates can ambiguously assign period/voucher-related fields. |
| WC calculations group by class without splitting base rows by class. | Multi-class employees may not receive a complete, deterministic breakdown. |
| Monthly date arithmetic is faulty. | Scheduled ranges can be reversed or invalid. |
| Weekly/biweekly uses weekday numbers without SET DATEFIRST. | SQL session settings affect date-window interpretation. |
| YTD uses GETDATE(). | Historical runs may receive current-year YTD values. |
| Some catalog fields are unpopulated. | dedid and VchCount have no assignments; division is initially a blank constant. |
| No-data SQL mixes Syd and Syd_Testing. | Empty-result behavior can depend on another database's configuration. |
| payrollformat is empty. | Choose an explicit supported format source; do not invent catalog values. |
| SQL 200 lists enabled jobs only. | Direct reuse hides all currently disabled payroll jobs. |
| SQL 200 uses global TOP 1 history detail. | It does not find the latest execution dates per job. |
| SQL 202 updates joblastrun on edit. | Configuration saving can falsely appear to be a Run. |
| Edit procedure orders mappings by DataSetNo only. | It is insufficient evidence for within-dataset field order. |
| condition_value is numeric(18,2). | Text/date conditions require deliberate compatible handling; no implicit schema change. |
| No payroll child foreign keys were declared in the inspected schema. | Application validation and transactional consistency are important. |

## Suggested implementation boundaries

These are planning recommendations, not approved edits:

- Add a dedicated payroll UI route/API and persistence layer using payroll tables.
- Give payroll a distinct procedure setting; keep retirement configuration intact.
- Reuse shared form controls, formatting, filename and serialization helpers
  where confirmed contracts match; avoid copying retirement calculations.
- Add payroll wage-mapping models and validation; resolve grouping semantics.
- Preserve existing aliases/defaults/query intent and recover legacy ordering
  only with unique query/column evidence.
- Keep payroll/retirement locks, schedules, history, directories and run identity
  separate. Equal numeric job IDs in two modules do not identify the same job.
- The current scheduler reads rjob schedules and uses retirement-specific locks
  and history. It needs explicit payroll integration, not a procedure-name swap.
- The current email subject/body says Retirement Builder. Make module labels
  deliberate when delivery work is requested; preserve recipients/attachments.
- Preserve multi-dataset identities, H/D/T controls, per-section headers and
  supported Store Results restrictions. Do not generalize retirement totals to
  payroll or assume all legacy multi-D paths are safe.
- Shared source limits currently include 10,000 rows, 5 MB source, 10 MB output
  and 100 export columns per result set. Assess intended payroll scale before
  promising that the existing runner fits it; changes need their own scope.

Useful implementation sources:
[query generation](../backend/app/retirement_query_builder.py),
[procedure serialization](../backend/app/retirement_procedure.py),
[dataset identity](../backend/app/retirement_datasets.py),
[report serialization](../backend/app/retirement_results.py),
[scheduler](../backend/app/report_scheduler.py),
[mail](../backend/app/report_mail.py),
[frontend helpers](../frontend/src/retirementBuilder.ts).

## Export contract to preserve when sharing infrastructure

Use the centralized REPORT_FORMAT_EXTENSIONS mapping rather than hardcoded
filename assumptions:

| Format | Extension | Content |
| --- | --- | --- |
| CSV / COMMA | .csv | Comma-separated. |
| PIPE | .txt | Pipe-separated. |
| SEMICOLON | .txt | Semicolon-separated. |
| TAB | .tsv | Actual U+0009 tab-separated. |
| TILDE | .txt | Tilde-separated. |
| FIXED | .txt | Configured positions/widths/padding. |

Support the seven existing filename combinations only through confirmed shared
behavior: File Name; Client ID; Payday; File Name + Client ID; File Name + Payday;
Client ID + Payday; File Name + Client ID + Payday. Preserve grouping, client
formatting, merged names, collision suffixes and historical-file access.

Normal downloads use backend filenames. Keep attachment MIME types/UTF-8
metadata correct and Excel conversion separate. Existing payroll jobs use CSV;
the other formats' actual payroll compatibility was not verified by live Runs.

## Decisions and verification before delivery

Confirm these requirements before implementing the affected behavior:

1. Existing wage/WC export scope versus a broader payroll reporting product.
2. Exact meanings of base/gross/subject wages, tips and overtime.
3. Intended TOTAL_AMT formula, including whether it is earnings + OT23.
4. Output grain: employee/payday, voucher, or employee/payday/WC class.
5. Actual grouping dimensions, aggregation and totals/trailer behavior.
6. Historical-year YTD and consistent void/reversal handling.
7. Display/access for disabled jobs and legacy mapping-order preservation.
8. Which SQL issues require separately authorized procedure/query/schema edits.

For an authorized implementation, prefer isolated DB/SMTP/scheduler mocks.
Verify wage overrides across different jobs, multiple pay codes/vouchers/WC
classes, all applicable calculation boundaries, historical years, schedule
month/year/leap-day boundaries, no-data placeholders, text/date/numeric filters,
aliases and legacy order, H/D/T/dataset identities, defaults and formatting.
Cover all six formats/seven filename choices, single/multiple clients, merges,
collisions, historical files and payroll/retirement isolation where affected.

Live Save/Run, scheduler triggers, email, new source fixtures or schema/procedure
changes each remain subject to the current task's authorization. Keep mail
disabled for local QA, preserve reports/evidence and clearly separate static
inspection, mocked tests, UI checks, live DB verification and generated files.
This guide grants no standing payroll mutation or execution permissions.

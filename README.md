# ECS Applications

ECS is a React web application with a FastAPI backend and a Microsoft SQL Server
database. The implemented business flow in this checkout is **Retirement Builder**:
configure export jobs, map fields, define sorting/conditions, run reports manually
or on a schedule, download CSV/Excel output, and optionally email reports to
matching subscriptions.

This guide describes the **current source code**, reviewed on 20 November 2026.
It does not certify the configuration or procedures installed on a live database.
Historical migrations and audit reports may describe older behavior.

## Contents

- [Scope and architecture](#scope-and-architecture)
- [Repository map](#repository-map)
- [Requirements and setup](#requirements-and-setup)
- [Configuration](#configuration)
- [Retirement Builder screens](#retirement-builder-screens)
- [Database and query reference](#database-and-query-reference)
- [Create and update lifecycle](#create-and-update-lifecycle)
- [Query generation and execution](#query-generation-and-execution)
- [Report formats and filenames](#report-formats-and-filenames)
- [Scheduling, email and storage](#scheduling-email-and-storage)
- [API reference](#api-reference)
- [Testing and project rules](#testing-and-project-rules)
- [Deployment and network access](#deployment-and-network-access)
- [Troubleshooting and limitations](#troubleshooting-and-limitations)

## Scope and architecture

The sidebar contains Benefits, Mass Mutual Files, Process Validator, Retirement
Builder, Prism, Services, Swipe Clock, Payroll Builder, NYS-45 and Reports.
**Retirement Builder has the implemented dashboard/wizard/API flow.** Other sidebar
routes currently render placeholder pages. Legacy SQL for those areas does not
mean their full UI/API workflows are implemented.

```text
Browser: React + TypeScript
    |
    | /api/v1/... through Vite's development proxy
    v
FastAPI
    |-- Job/options APIs ---- SQLAlchemy + pyodbc ---- SQL Server
    |-- Report runner ------ saved CSV input OR configured report procedure
    |-- Serializer --------- CSV/delimited/FIXED output and Excel row metadata
    |-- Output files ------- backend/report-output (configurable)
    |-- SMTP --------------- only when MAIL_ENABLED=true
    `-- APScheduler -------- only when SCHEDULER_ENABLED=true
```

Login is a **frontend demo login**, using constants in
[`LoginPage.tsx`](frontend/src/LoginPage.tsx) and browser session storage. It is
prefilled for local demonstration. The current FastAPI setup has no corresponding
backend authentication/authorization layer. This is not a production identity system.

## Repository map

| Path | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Project-wide instructions and change boundaries. |
| [frontend/src/App.tsx](frontend/src/App.tsx) | Dashboard, wizard, controls, API calls and application-shell routing. |
| [frontend/src/retirementBuilder.ts](frontend/src/retirementBuilder.ts) | Validation/helpers, mapping import and Excel conversion. |
| [frontend/src/main.tsx](frontend/src/main.tsx) | React bootstrap, demo login routing and session state. |
| [frontend/src/styles.css](frontend/src/styles.css) | Styling and responsive layouts. |
| [frontend/public/](frontend/public/) | Mapping template and IIS frontend configuration. |
| [frontend/tests/](frontend/tests/) | Node-based helper tests. |
| [backend/app/main.py](backend/app/main.py) | FastAPI startup, CORS, health endpoints, errors and scheduler lifecycle. |
| [backend/app/core/config.py](backend/app/core/config.py) | Environment settings, validation and defaults. |
| [backend/app/db.py](backend/app/db.py) | SQLAlchemy engine, pyodbc connection and DB health check. |
| [backend/app/routers/retirement_builder.py](backend/app/routers/retirement_builder.py) | Endpoints, validation, transactions, persistence and Run orchestration. |
| [backend/app/retirement_query_builder.py](backend/app/retirement_query_builder.py) | Retirement H/D/T SQL-fragment generation. |
| [backend/app/payroll_source.py](backend/app/payroll_source.py) | Payroll templates, source compatibility and procedure invocation. |
| [backend/app/retirement_procedure.py](backend/app/retirement_procedure.py) | Procedure result-set conversion to reports. |
| [backend/app/retirement_results.py](backend/app/retirement_results.py) | CSV-source processing, formatting, grouping, FIXED layout and result inserts. |
| [backend/app/report_scheduler.py](backend/app/report_scheduler.py) | Scheduled job discovery/execution. |
| [backend/app/report_mail.py](backend/app/report_mail.py) | Subscription matching, attachment merging and SMTP. |
| [backend/app/report_files.py](backend/app/report_files.py) | Source loading and atomic output publication. |
| [backend/app/core/error_logging.py](backend/app/core/error_logging.py) | Structured rotating logs and redaction. |
| [backend/query.brl](backend/query.brl) | XML SQL catalog, including unrelated legacy modules. |
| [backend/config/options.xml](backend/config/options.xml) | Filename formats, schedule choices and record-type labels. |
| [backend/config/payroll_record_queries.json](backend/config/payroll_record_queries.json) | Approved H/D/T templates for the Company Payroll sample path. |
| [backend/migrations/](backend/migrations/) | Historical schema/data/procedure scripts; review individually. |
| [backend/tests/](backend/tests/) | Python unittest suites. |
| [docs/](docs/) | Product analysis, technical explanations, audits and testing guides. |
| [qa-results/](qa-results/), [qa-evidence/](qa-evidence/) | QA results and evidence. |
| [service/SchedulerAppBackend.xml](service/SchedulerAppBackend.xml) | Windows backend service template. |
| [server.sh](server.sh) | Development bootstrap/start script. |

## Requirements and setup

### Prerequisites

- Python **3.11+**; the backend uses `datetime.UTC` and modern Python syntax.
- Node.js/npm compatible with the lockfile. The currently locked Vite requires
  Node **20.19+ on the Node 20 line, or 22.12+**.
- Reachable Microsoft SQL Server, a compatible ECS schema and operation-appropriate
  permissions. Some lookups also depend on `prism.export` data.
- Microsoft **ODBC Driver 18 for SQL Server** and the platform ODBC runtime.
- SMTP credentials only for separately authorized mail-enabled operation.

Backend dependencies are pinned in [requirements.txt](backend/requirements.txt).
Frontend scripts/dependencies are in [package.json](frontend/package.json), with
resolved versions in [package-lock.json](frontend/package-lock.json).

### Backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For a **new local setup only**, copy `backend/.env.example` to `backend/.env` if
the latter is absent. Do not overwrite an existing environment file. Supply the
correct DB configuration; keep `MAIL_ENABLED=false`. For isolated manual QA,
also keep `SCHEDULER_ENABLED=false`.

Start from `backend/`, after reviewing configuration:

```bash
MAIL_ENABLED=false SCHEDULER_ENABLED=false .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

These process overrides do not edit `.env`. Without the scheduler override, the
configured setting applies; its code/example default is `true`, so startup can
begin scheduled work.

### Frontend

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Vite defaults to **5173** and proxies `/api` to `http://127.0.0.1:8000`. If the
port is occupied, inspect Vite's printed URL; this project has also used **5174**.
To request it explicitly, run `npm run dev -- --port 5174` from `frontend/`.

| Service | Default URL |
| --- | --- |
| Login | `http://localhost:5173/login` |
| Retirement Builder | `http://localhost:5173/retirement-builder` |
| API docs / schema | `http://localhost:8000/docs` / `http://localhost:8000/openapi.json` |
| Process health | `http://localhost:8000/health` |
| DB health | `http://localhost:8000/health/db` |

`/health` does not need the DB. `/health/db` attempts `SELECT 1` and returns JSON
status `ok` or `degraded`; check its body, not only HTTP 200.

### Combined startup

```bash
./server.sh
```

The script installs missing frontend dependencies, creates the backend virtual
environment if needed, installs backend requirements, copies `.env.example` only
if `.env` is absent, then starts both servers bound to `0.0.0.0`. It does not apply
migrations or override mail/scheduler settings. Review configuration before using
it against a shared database.

### Database provisioning

The repository is not a complete database bootstrap for all legacy tables and the
external `prism.export` schema. Existing deployments need compatible tables,
lookup data and a compatible configured report procedure.

Migration files `001`–`012` cover result storage, mapping catalogs, sample payroll
data/contacts, file formats, filename formats/codes and sample query/date contracts.
They can change data, schema and procedures. **Do not apply the directory blindly
to an existing/shared DB.** Review each script against the deployment and obtain
authorization. Migration `012` defines an older three-parameter sample procedure;
it does not match the current four-input runtime contract below.

## Configuration

Pydantic Settings loads `backend/.env` with process environment overrides. Names
are case-insensitive; extra fields are ignored. Settings are cached per process:
restart the backend after changing environment values. Do not commit real secrets.

### Application and database settings

| Variable | Purpose / code default |
| --- | --- |
| `APP_NAME` | FastAPI title; `ECS API`. |
| `ENVIRONMENT` | Environment label; `development`. |
| `API_V1_PREFIX` | `/api/v1`; frontend currently uses that prefix directly, so changing the backend alone breaks the pairing. |
| `CORS_ORIGINS` | Comma-separated origins for direct API access. Code default is `http://localhost:5173`; example also includes `127.0.0.1:5173`. |
| `DB_HOST`, `DB_PORT` | SQL Server address/port; defaults `127.0.0.1`, `1433`. |
| `DB_NAME` | Database name; `ecs`. |
| `DB_USER`, `DB_PASSWORD` | SQL Server credentials; example values are placeholders, not deployment credentials. |
| `MSSQL_DRIVER` | `ODBC Driver 18 for SQL Server`. |
| `MSSQL_TRUST_SERVER_CERTIFICATE` | Connection-string `TrustServerCertificate`; default `true`. Configure for the target deployment. |
| `DB_DIALECT` | Compatibility field; the current URL builder still constructs `mssql+pyodbc`. This alone does not switch DB engines. |

There is no built-in DB administration website or universal “DB link.” Use a SQL
Server client with the configured host/port/database and separately shared
credentials. Database access is separate from frontend access.

### Reports, scheduler and logs

| Variable | Purpose / code default |
| --- | --- |
| `RETIREMENT_REPORT_PROCEDURE` | Retirement Builder procedure. The compatibility code default remains `dbo.usp_CompanyPayrollReport`; current deployment/example selects `dbo.rjobbuilder`. Accepts `procedure` or `schema.procedure`; omitted schema becomes `dbo`. |
| `PAYROLL_REPORT_PROCEDURE` | Payroll Builder procedure; default `dbo.payrolljobbuilder`. Used by manual and scheduled payroll runs. The signature/result contract must match the runner. |
| `RETIREMENT_HEADER_SOURCE` | Automatic procedure-output header policy; `DETAIL_ALIGNED` by default. `SAVED_H` restores the previous H-result behavior. Restart the backend after changing it. |
| `SCHEDULER_ENABLED` | Start scheduler with API; `true`. Use false for isolated manual QA. |
| `SCHEDULER_TIMEZONE` | IANA timezone for due-slot evaluation; `UTC`. |
| `REPORT_INPUT_DIR` | Source CSV folder; `report-input`. |
| `REPORT_OUTPUT_DIR` | Generated reports; `report-output`. |
| `ERROR_LOG_FILE` | Structured log; `logs/errors.log`. |
| `ERROR_LOG_MAX_BYTES` | Rotation threshold; `10485760` (10 MiB). |
| `ERROR_LOG_BACKUP_COUNT` | Rotated backups; `5`. |

Relative report/log paths resolve against `backend/`; absolute paths also work.
Default reports, logs, `.env`, virtual environments, dependencies and builds are
excluded by `.gitignore`.

### Email

| Variable | Purpose / code default |
| --- | --- |
| `MAIL_ENABLED` | Master switch; **false**. Keep false for QA. |
| `MAIL_MAILER` | Supported transport: `smtp`. |
| `MAIL_HOST`, `MAIL_PORT` | SMTP endpoint; `smtp.gmail.com`, `465`. |
| `MAIL_ENCRYPTION` | `ssl` or `tls` (STARTTLS); `ssl`. |
| `MAIL_USERNAME`, `MAIL_PASSWORD` | SMTP credentials; blank by default. |
| `MAIL_FROM_ADDRESS`, `MAIL_FROM_NAME` | Sender; name defaults to `ECS Retirement Builder`. |

Enabling mail requires nonblank host, username, password and sender address.
Successful file generation is separate from subscription matching, SMTP acceptance
and inbox delivery. “Run succeeded” alone does not prove mail was received.

## Retirement Builder screens

### Dashboard

The enabled-job table shows File Name, Description, Modified On, Last Run Date,
Run Day, Run Time, Schedule Type, File Type, Is Active and Status. It has column
filters/sorting and **client-side pagination with 10 jobs per page**. The API still
returns the full enabled-job list; pagination is not server-side.

- **Template:** downloads [the mapping workbook](frontend/public/mapped_payroll_columns_HDT.xlsx).
- **Add:** opens a new job wizard.
- **Edit / filename click:** loads the selected job into the edit wizard.
- **Run:** opens Start Date / End Date for one selected job.

The current frontend loads jobs on dashboard entry and updates/refreshes state
around operations; it does not use a two-second jobs-list polling interval. This
is separate from the backend scheduler. React StrictMode can cause extra effect
setup/cleanup in development; inspect actual completed requests before diagnosing
periodic polling.

### General

Sets filename, description, File Format, Output File Name Format, enabled state,
Store Results to Table and mapping-workbook selection. A job ID identifies a job;
a subscription client ID identifies whose report data is included.

The Add UI starts text/select fields and mapping/subscription rows empty, with UI
defaults for boolean controls. Backend model defaults are separate. New UI jobs
use `companyPayroll`; legacy jobs can retain a `csv` report-source flag.

### Schedule

Sets start date, Daily/Weekly/Bi-Weekly/Monthly frequency, hour/minute/AM-PM and
weekday where applicable. A completely blank schedule is manual-only. An enabled
job can run manually without having a schedule.

Schedule date/time fields are returned from DB values without browser local-time
conversion. Automatic due-slot evaluation still uses `SCHEDULER_TIMEZONE`; the
stored clock display and the scheduler's timezone interpretation are distinct.

### Mapping and File Settings

Mappings define output Field Name, source Mapping Column, Record Type, Default
Value, Format, Start Position, Length, DataSetNo and ColSeqNo. Source keys and
display labels are distinct; saves use source keys. A blank Mapping Column
resolves to the field name when saved.

Excel import accepts `.xlsx`/`.xls`, reads the **first worksheet in the browser**,
and creates mapping definitions, not payroll data. A field/column-name list may
include Record Type, DataSetNo and ColSeqNo. Otherwise its header row becomes
Detail mappings. Selecting the workbook does not upload a report-source CSV or
run a job; the filename is retained as form state.

Header/Detail/Trailer labels persist as **H/D/T**. Include Header Row persists in
`rjob.includeHeader`. ON derives column-header values from D output field names;
this differs from a manually configured business H record.

**Why automatic headers follow D:** an H query can retain a different column order
from the D SELECT. Its labels can then describe the wrong values even when both
sets have the same number of columns. With the default
`RETIREMENT_HEADER_SOURCE=DETAIL_ALIGNED`, the file writer confirms the association
between actual D output columns and mapping labels using returned names and
supported saved SELECT expressions/explicit aliases. It emits one aligned header
per file and applies field formats in that same D order. It does not guess alias
conventions or trust column counts alone; ambiguous/unsupported associations
produce validation instead of a silently mislabeled report. Detail datasets in
one file must share a compatible header/layout. Plain source-CSV exports already
derive their labels and values from the same mapping layout.

When the checkbox is OFF, configured H output remains unchanged. H queries are
still saved/read for procedure compatibility; no DB or SP migration is needed.
To restore the previous checked-header behavior, set
`RETIREMENT_HEADER_SOURCE=SAVED_H` and restart the backend. This changes the file
writer's policy only; it does not rewrite saved H/D/T queries or existing reports.

File Settings contains numeric **Order By** priorities 1,2,3 and Mapping Columns.
These numbers are precedence, not ASC/DESC choices. Priorities are sorted and
normalized on save. Conditions contain a column, comparison and value. Current
form processing supports numeric thresholds and ISO dates (`YYYY-MM-DD`), not
arbitrary text predicates or raw SQL. Multiple rules combine with AND; incomplete
rules fail validation.

### Subscriptions and drafts

Subscriptions contain client/company IDs and email tags. Supported custom numeric
client inputs must be positive. Sample payroll company IDs are modeled separately.
Merge Files combines a recipient's eligible **emailed attachments**, not generated
report files/downloads. With mail disabled, Save/reopen tests persistence only.

Wizard drafts use browser `sessionStorage` for refresh recovery. Open edit from
the dashboard with a selected job; `/jobs/edit/general` alone does not identify
the job without navigation/draft context.

## Database and query reference

### Active tables

| Table | Data / notable columns |
| --- | --- |
| `dbo.rjob` | Job ID/name/description, `filetype`, `includeHeader`, `FileNameFormat`, enabled/merge/store flags and timestamps. |
| `dbo.rjob_schedule_info` | Start date/time, frequency, weekday, hour/minute/session and schedule metadata. |
| `dbo.rjob_file_detail` | Output `jobclientcolumn`, source `jobfieldmapping`, defaults/formats, `jobrectype`, position/width, DataSetNo/ColSeqNo. |
| `dbo.rjob_client_detail` | `jobclientid` / `jobemailind` subscriptions. |
| `dbo.rjob_file_sorting_details` | Priority `sort_order` and `mapping_column`. |
| `dbo.rjob_file_condition_details` | Column, comparison and threshold/date representation. |
| `dbo.rjob_query` | `jobid`, H/D/T `recttype`, `Query`, `Conditions`, `Sort_Order`. |
| `dbo.rjob_history` | Trigger status/message/timestamps. |
| `dbo.rjob_history_details` | Run type/date ranges and procedure-owned date details where applicable. |
| `dbo.rjob_result` | Optional application-managed CSV/typed-source result rows. |
| `dbo.rjob_file_typ` | File-format labels and delimiters. |
| `dbo.rjob_mapping_column` | Source keys, descriptions and declared types. |
| `dbo.rjobformat` | Format codes, categories and descriptions. |
| `prism.export.Client_Details` | Active client lookup used by query 43. |
| `dbo.companies`, `dbo.employees`, `dbo.payroll` | Sample Company Payroll source/company catalog. |

This is an application reference, not the full schema of external procedures or
all legacy catalog entries. Application job saves do not populate
`msrepl_tran_version` explicitly.

### Dropdown sources

| UI choice | Source |
| --- | --- |
| File Format | Query 32, `rjob_file_typ`. |
| Mapping Column | Query 30, `rjob_mapping_column`; sample payroll keys also exist in `payroll_source.py`. |
| Mapping Format | Query 53, `rjobformat`, grouped by supported type. Query 33 remains in the catalog but is not the current all-format loader. |
| Clients | Query 43, nonterminated `prism.export.Client_Details` entries. |
| Output File Name Format | Seven choices in `backend/config/options.xml`. |
| Frequencies, time, weekdays, record labels | `backend/config/options.xml`. |
| Comparison operators | `COMPARISONS` in `retirement_results.py`. |

Some options lookups fall back to empty collections on DB errors. Empty choices
can indicate a failed lookup rather than missing UI options. The separate Clients
endpoint reports 503 when its DB read fails.

### Important query IDs

| ID | Purpose |
| --- | --- |
| 30 / 32 / 43 / 53 | Mapping catalog, file types, clients, formats. |
| 31 | Insert H/D/T configuration in `rjob_query`. |
| 35 / 36 | Insert mapping details / create main job and return its identity. |
| 37 / 38 | Insert subscriptions / schedule. |
| 42 | Legacy enabled-only job listing, retained unchanged. The dashboard uses the read-only `READ_ALL_JOBS` query in `retirement_listing.py` to include disabled jobs and jobs without schedules. |
| 44 | Delete related configuration before normal update reinserts it; does not delete the main job. |
| 45 | Legacy main-row update, retained unchanged. Current PUT uses SQLAlchemy configuration update to avoid its `joblastrun=GETDATE()` assignment. |
| 52 | Update Run history status. |
| 54 / 55 | Insert sort priorities / conditions. |

The router also defines SELECTs for full edit details and due schedules, plus run
locks/history statements. Not all executed SQL has a `query.brl` ID.

## Create and update lifecycle

### Create

1. UI validates the wizard and sends sections to POST jobs.
2. Backend validates/normalizes values and opens one transaction.
3. Query 36 creates `rjob`; `filetype` receives the resolved delimiter.
4. Query generation and detail writes save H/D/T queries, schedule, mappings,
   subscriptions, sort priorities and conditions.
5. The saved job is read back and committed. Failure rolls back the transaction.

Create supports `Idempotency-Key`: reuse with a different payload returns 409.
The bounded one-hour cache is in-memory, not durable across workers/restarts.

### Update

1. PUT reads the existing job and preserves omitted fields.
2. Main configuration and `joblastmodified` are updated; saving configuration does
   not deliberately advance `joblastrun`.
3. Existing query 44 removes related configuration for the same job.
4. Validated/generated rows are reinserted, using batched statements to reduce
   DB round trips; the updated job is read back.
5. All changes share a transaction and roll back on failure.

Normal UI Save **writes/replaces configuration data**, even without manual SQL.
It does not execute a report or send mail. Legacy creation/query behavior can
affect timestamp values already present; do not repair those during analysis.

## Query generation and execution

### Query families

**Company Payroll sample** uses approved H/D/T templates from
`backend/config/payroll_record_queries.json`, marked `/* company payroll */`.
Conditions/sort-column lists are saved with D.

**Retirement export fragments** come from `retirement_query_builder.py`. They are
SELECT fragments without FROM for a compatible production-style procedure to
attach to its staging source. New output aliases are not invented beyond `sort1`.

- Include Header Row ON builds H from ordered D names as escaped literals.
- OFF uses H mappings; if none exist, H is omitted.
- D is generated from mappings if no saved D SELECT exists. **Current code
  preserves an existing D SELECT and its aliases.** A source-mapping edit can
  persist without changing that SELECT, so verify exported source values.
- T comes from configured T mappings. Without them, the fallback is
  `SELECT DISTINCT valid_flag, retnum, '01/01/1900' AS sort1`: metadata placeholder,
  not business totals.
- Query rows are saved once per type in H/D/T order; mappings follow DataSetNo and
  ColSeqNo. SQL literals and identifiers are escaped/quoted.

For production-style D sorting, `Sort_Order` starts with a comma, for example
`, paydate, lastname, firstname`, because the procedure appends it after its own
initial ordering. It is not form-generated `ORDER BY ... ASC`. Identifiers needing
quoting are quoted. Separate detail rows store normalized priorities 1,2,3.
Date conditions use a `date:` symbol prefix and compact stored date, decoded on read.

### Current procedure contract: four inputs

Retirement Builder calls `RETIREMENT_REPORT_PROCEDURE`; Payroll Builder calls
`PAYROLL_REPORT_PROCEDURE`. Both manual and scheduled SP paths use these settings:

When upgrading an older environment, rename its former retirement
`PAYROLL_REPORT_PROCEDURE` key to `RETIREMENT_REPORT_PROCEDURE`, then add the
payroll key separately. Restart the backend after editing either setting.
Changing a procedure name does not rewrite existing saved query rows.

The runtime calls the selected name as:

```sql
EXEC [schema].[procedure]
    @client_id = ?, @paystartdate = ?, @payenddate = ?, @runType = ?
```

| Parameter | Meaning |
| --- | --- |
| `@client_id` | **Job ID**, despite the name; not subscription client ID. |
| `@paystartdate` | Manual start date or `1900-01-01` sentinel. |
| `@payenddate` | Manual end date or `1900-01-01` sentinel. |
| `@runType` | `A` manual/ad hoc; `S` scheduled. |

`@templates_only` is not sent. The older three-input sample migration does not
match this runner. Changing the environment procedure name takes effect after
reload/restart; it does not adapt incompatible signatures, query fragments or
result shapes automatically.

### Manual execution and source selection

1. Select one enabled job, open Run and enter optional dates.
2. UI sends POST Run with `start_date`/`end_date` query parameters. Blank sides
   become sentinel dates; reversed bounded ranges return 422.
3. Backend locks the job, reads configuration and resolves the output delimiter.
4. With no request body, `companyPayroll` jobs **or jobs with production H/D/T
   queries** use the configured procedure. A legacy `csv` flag alone does not
   prove file input is used.
5. Other saved-source jobs read `REPORT_INPUT_DIR/<job-id>.csv`. An explicit
   `text/csv` body overrides the source for that Run.
6. Reports and eligible history/result writes are committed. Saved-source Runs
   then attempt subscribed mail only when enabled.
7. Response includes run ID, Detail count, app-stored count, delimiter,
   filenames/content and optional email status.

CSV **input** is UTF-8 comma-delimited regardless of output format. It needs source
column headers; a Record Type column distinguishes supplied H/D/T rows. The
CSV-source renderer applies mappings, formatting, filters, dates and sorting.

### Procedure results

The cursor drains all result sets/trailing statements. Production-style H/D/T
sets lead with `valid_flag`, `retnum`, `sort1`: eligibility/client/paydate metadata,
not business output fields. Invalid placeholders are ignored. Multiple D sets are
supported. A set without business fields does not invent an empty trailer row.

The procedure determines returned source columns, filtering and ordering. The
application aligns output with mapping layouts and applies supported presentation,
defaults, dates/SSNs/name cleanup and width handling before serialization. It does
not rebuild a saved procedure SELECT merely because a UI mapping changed. The
older single typed-payroll result shape remains readable with the same current
four-input call contract.

## Report formats and filenames

### Six formats

| Selection | Extension | Content | Configured `rjob.filetype` |
| --- | --- | --- | --- |
| CSV / COMMA | `.csv` | Quote-aware comma-separated fields | `,` |
| PIPE | `.txt` | Pipe-separated fields | Pipe character, U+007C |
| SEMICOLON | `.txt` | Semicolon-separated fields | `;` |
| TAB | `.tsv` | Tab-separated fields | Actual U+0009, not four spaces |
| TILDE | `.txt` | Tilde-separated fields | `~` |
| FIXED | `.txt` | Fixed-position/width records, no separator | One space when configured as FIXED in the lookup |

The selected File Format determines the extension, using the centralized
`REPORT_FORMAT_EXTENSIONS` mapping in
[retirement_results.py](backend/app/retirement_results.py). This applies to
single-client, multiple-client and merged reports, including email attachments.
Delimiters, quoting, UTF-8 content, field order, values and FIXED layouts are
unchanged. Historical `.csv` reports retain their filenames and existing access
paths; no renaming, migration or deletion is required.

Legacy labels are recognized. Named TAB lookup rows historically containing a
space are interpreted as tabs; a stored space resolves to configured FIXED. This
does not migrate DB data.

Proper CSV quoting preserves embedded commas/quotes and blank fields. `a,,,d`
contains two empty fields; deleting delimiters shifts columns. `"Last, First"`
is one CSV field. The normal **Download Report** link uses the backend's filename
and extension without converting the content. Download MIME types are `text/csv`
for `.csv`, `text/tab-separated-values` for `.tsv`, and `text/plain` for `.txt`,
with UTF-8 encoding. Historical FIXED output with structured fields uses
`text/plain` even when its filename ends in `.csv`.

Text exports do not automatically convert all six formats into Excel columns.
Some require configured Excel import: select the matching delimiter for delimited
files and the configured field boundaries for FIXED. Direct opening also depends
on Excel/locale settings and can convert identifiers, dates or numbers. File-format
correctness does not prove native Excel compatibility.

The separate **Download Excel** button continues to generate `.xlsx` using
frontend SheetJS conversion with the returned delimiter. FIXED uses returned
field arrays, avoiding arbitrary space splitting. The filename helper replaces a
final `.csv`, `.txt` or `.tsv` suffix with `.xlsx`; it does not change the original
report. Native Excel direct opening, configured import and `.xlsx` opening need
separate evidence from actual Excel testing.

### FIXED layout

Length is the reserved **character width**, including padding; allowed widths are
1–1,000. If all Start Positions are zero, fields are sequential. If any is nonzero,
all positions are explicit zero-based offsets and must not overlap/move backwards.
Gaps are spaces. LA pads right; RA pads left. Overflow is rejected, not truncated.
Automatic header names must fit their widths too.

Example: PAYDATE length 10 starts at 0 and occupies offsets 0–9. WORK PHONE length
15 starts at 10 and occupies 10–24. It does not start inside the date's reserved
region. FIXED is not “one space between every value.”

### Seven filename formats

Examples use CSV format, filename `Payroll`, client `000204`, paydate `2026-10-15`.
Other formats retain the same components and use the extension listed above:

| Label | Stored value (from options.xml) | Example |
| --- | --- | --- |
| File Name | `File Name` | `Payroll.csv` |
| Client ID | `CLIENT` | `000204.csv` |
| Payday | `PayDate` | `2026-10-15.csv` |
| File Name + Client ID | `File Name-ClientId` | `Payroll_000204.csv` |
| File Name + Payday | `File Name-PayDate` | `Payroll_2026-10-15.csv` |
| Client ID + Payday | `ClientId-PayDate` | `000204_2026-10-15.csv` |
| File Name + Client ID + Payday | `File Name-ClientId-PayDate` | `Payroll_000204_2026-10-15.csv` |

Create/update saves use the production spelling in the XML `value` attribute.
API/dropdown values remain normalized codes (such as `FILENAME_PAYDAY`). Reading
and rendering also accept existing local codes, production hyphenated values,
and labels with `+` separators. Existing records need no migration; a later
authorized Save uses the configured spelling. These setting values do not change
the underscores between components in actual downloaded filenames.

FILENAME alone creates one report from included data. CLIENT/PAYDAY group by the
distinct included values/combinations. File count is not necessarily subscription
count. H/T rows with blank group metadata can apply to multiple matching groups.
All seven naming combinations retain their existing components and grouping.
Only the final supported `.csv`/`.txt`/`.tsv` suffix is replaced when forming the
report name, so a base such as `Payroll.csv` does not become `Payroll.csv.txt`.
Filename sanitization and collision suffixes remain supported in both report
writers, as do single-client, multiple-client and merged report names.

### Multiple Detail datasets

**Add Dataset** creates a separate mapping card. **Add Row** adds a field only to
that card and opens it if collapsed. Click a dataset heading to collapse or expand
its fields; the field count remains visible while closed. Dataset/column order is
retained through `DataSetNo` and `ColSeqNo`.
Include Header Row, configured H/T mappings, sorting and conditions remain
job-level settings. With automatic headers enabled, each Detail section gets its
own confirmed field labels, with a blank line between populated sections. Fields
are dynamic; there are no job-specific or hardcoded business column names.

Normal Save generates one `D` SELECT per dataset using existing query 31, retaining
one H and one T query. Each new D SELECT includes a reserved technical fourth
projection, for example `2 AS [__ecs_dataset_2]`. This identifies even empty
results without depending on the unchanged `rjobbuilder` cursor order. The
application removes the marker before header alignment, formatting and export;
it never appears as a report field. Business aliases are preserved, not invented.

Legacy multiple D queries are matched by confirmed query/result-column metadata.
An unmapped legacy dataset can be shown read-only when all its source identifiers
are explicit and unique. Calculated, duplicate or indistinguishable legacy output
requires mapping review rather than positional guesses. Viewing a job does not
persist derived mappings or migrate its queries; an authorized Save does.

Multiple datasets use `rjobbuilder` result sets. Store Results to Table is blocked
for this flow because the unchanged SP inserts into one target table; direct CSV
Run uploads and the legacy Company Payroll template source are not supported for
multiple dataset cards. Automatic multi-dataset headers require
`RETIREMENT_HEADER_SOURCE=DETAIL_ALIGNED`; `SAVED_H` remains available for existing
single-dataset jobs. Existing row/byte limits still apply across the procedure
output. No SP, schema or existing `query.brl` definition change is required.

## Scheduling, email and storage

### Automatic execution

APScheduler checks enabled nonblank schedules every **30 seconds**, with a
**five-minute due window**. Daily, weekly, biweekly and monthly slots are supported;
monthly dates clamp to the last day of shorter months. Timezone/DST handling uses
`SCHEDULER_TIMEZONE`. Automatic calls send S plus sentinel start/end dates; a
compatible procedure determines its own business date range.

The runner locks the job and checks its UTC-slot output folder. Existing `.csv`,
`.txt` or `.tsv` files (case-insensitive suffixes), or a `.complete` marker, prevent
another completed-slot Run. Historical `.csv` files still satisfy this check.
Run only one scheduler against the same DB/output location. Frontend GET refresh behavior does
not enable/disable this backend timer.

### Subscription delivery

Each file is matched to the client/company IDs it contains. A multi-client file
is eligible only when a recipient is subscribed to **all** represented clients.
Use CLIENT-based naming for separate client files. Leading-zero IDs are normalized
for matching. Merge Files combines the recipient's eligible attachments afterward.
Merged attachment names retain the configured format's extension and the existing
`_merged` naming convention. Attachments use the generated backend filename and
the same content and MIME rules described above; extension selection does not
change recipient eligibility, subscriptions or delivery behavior.

`emailDelivery` contains `enabled`, `matched`, `accepted`. SMTP acceptance is not
inbox confirmation. Disabled mail, no matching recipients and SMTP rejection are
different outcomes. Explicit CSV-body override Runs do not send subscribed mail.

### Files and DB effects

```text
backend/report-input/<job-id>.csv
backend/report-output/manual/<job-id>/<run-uuid>/<filename>.<csv|txt|tsv>
backend/report-output/scheduled/<job-id>/<UTC-slot>/<filename>.<csv|txt|tsv>
```

UTC-slot folder format is `YYYYMMDDTHHMMSSZ`. Files are atomically published from
temporary files. Failed attempts can roll back newly published output. Preserve
completed reports during QA; do not manually delete old reports as cleanup.

For CSV/typed-source output, Store Results inserts application-managed rows into
`rjob_result`. For `ProcedureSource` output, the application does not duplicate
those inserts; the procedure owns its result-table/date-detail behavior. The app
still records Run status and avoids duplicating procedure-owned date details.
`storedRows=0` reports app inserts, not proof that a procedure made no DB writes.

Attempts use transactions/savepoints and record failures when possible. Mail
disabled does not mean read-only. Procedure Store Results behavior can create/drop
tables; keep it outside no-schema-change QA.

### Limits and logs

The report code defines 5 MiB source/procedure-output limits, 10,000 source rows,
100 columns and a 10 MiB output budget; specific enforcement depends on the source
path. FIXED widths are at most 1,000 characters. SQL Server datetime schedules
must fit its range, starting 1753-01-01.

Warnings/errors are JSON lines in `backend/logs/errors.log`: UTC time, severity,
logger/source, message and available exceptions. HTTP failures add request context
and IDs; SMTP failures include available server codes. Rotation defaults to 10 MiB
with five backups. Configured DB/SMTP passwords are redacted; error handlers do
not automatically include request bodies, SQL or bound parameters. Keep logs private.

## API reference

Default prefix: **`/api/v1/retirement-builder`**. The health paths below are outside
that prefix. FastAPI `/docs` and `/openapi.json` describe detailed schemas.

| Method / path | Purpose / effects |
| --- | --- |
| `GET /health` | Process health, outside prefix. |
| `GET /health/db` | DB SELECT health check, outside prefix. |
| `GET /options` | DB/XML choices and labels. |
| `GET /clients` | Query 43 client catalog. |
| `GET /jobs` | All jobs, enabled and disabled; no server pagination parameters. The dashboard separates Active Jobs and Disabled Jobs tabs, with Active Jobs selected initially. Disabled jobs remain available for editing/re-enabling and retain their configured schedule display. Scheduler eligibility still requires enabled jobs. |
| `POST /jobs` | Create configuration; optional `Idempotency-Key`. |
| `GET /jobs/{job_id}` | Full edit configuration; 404 if absent. |
| `PUT /jobs/{job_id}` | Transactional configuration update/replacement. |
| `POST /jobs/{job_id}/run?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Manual Run; writes reports/history and can call a writing procedure/email path. |

There is no job DELETE or backend mapping-upload endpoint in this router. Mapping
template download/import is frontend functionality.

Payload sections are `general`, `schedule`, `mapping`, `subscriptions`,
`fileSettings` and optional `queryConfiguration`. PUT preserves omitted fields;
the wizard normally sends a full editable form. Run uses an empty body for saved
source or `text/csv` for an override. Other nonempty content types return 415;
oversized input returns 413.

Other common statuses: 422 invalid form/run data, 404 missing job, 409 disabled
job/idempotency conflict, 503 unavailable client list, 500 DB/file-output failure.
Read response `detail` and the corresponding structured log.

## Testing and project rules

Read [AGENTS.md](AGENTS.md) for project-wide boundaries and
[retirement-builder-test-skills.md](skills/retirement-builder-test-skills.md) for job 60 QA. The latter requires:

- Existing job 60 only; no new job or manual DB/SQL/schema changes.
- UI Save/Run only when authorized; `MAIL_ENABLED=false`, no email.
- Fresh baseline and verified restoration of original editable settings.
- All six formats/seven names, applicable mappings/formats, sorting/conditions,
  single/multiple clients and actual generated-file checks.
- Honest PASS/FAIL/BLOCKED/NOT TESTED reporting and report preservation.

Relevant automated checks, only when authorized and safe:

```bash
# From backend/; inspect tests and keep external dependencies mocked.
MAIL_ENABLED=false SCHEDULER_ENABLED=false .venv/bin/python -m unittest discover -s tests
```

```bash
# From frontend/
npm run lint
npm run build
node --test tests/*.test.mjs
```

`lint` is TypeScript checking, not ESLint. Build runs TypeScript/Vite and writes
`frontend/dist`. Suites cover helpers, validation, query generation, procedure
handling, serialization, scheduler/mail mocks and logging. Unit success does not
prove live procedure execution, mail delivery or native Excel import. Tests were
not executed merely to write this README.

Previously reported verification for the file-extension implementation: **142
backend tests and 18 frontend tests passed; lint and build passed**. These are
prior results, not checks rerun for this documentation update. Coverage is defined
in [test_report_extensions.py](backend/tests/test_report_extensions.py),
[test_retirement_results.py](backend/tests/test_retirement_results.py),
[test_retirement_procedure.py](backend/tests/test_retirement_procedure.py) and
[retirementBuilder.test.mjs](frontend/tests/retirementBuilder.test.mjs). It includes
all six formats, seven filename combinations, content/189-character FIXED layout,
grouping/merging/collisions, mocked completion detection and attachment metadata,
and download/Excel filename helpers. Live UI downloads, actual SMTP delivery and
live scheduled execution were not tested. Native Excel compatibility was not
established by these automated checks.

## Deployment and network access

### Same Wi-Fi

For an authorized trusted-network session, bind the frontend to `0.0.0.0`
(`server.sh` does this). A colleague opens
`http://<host-wifi-ip>:<actual-vite-port>/retirement-builder`, not `localhost`,
which points to their own machine. The host must allow incoming traffic and the
devices must be reachable on the network. Through Vite's proxy the browser need
not connect directly to SQL Server.

Direct cross-origin API requests additionally require appropriate backend binding
and `CORS_ORIGINS`. CORS is not authentication. Do not expose this demo-auth app
publicly as if it had production access controls.

### Static frontend / Windows service

`npm run build` produces static assets. The hosting server must handle SPA routes
and forward `/api` to FastAPI; Vite's proxy is not bundled into static output.
[frontend/public/web.config](frontend/public/web.config) is an IIS template.

[service/SchedulerAppBackend.xml](service/SchedulerAppBackend.xml) uses absolute
`C:\projects\scheduler_app\backend` paths, virtual-environment Python, Uvicorn on
`127.0.0.1:8000`, **one worker**, automatic startup and restart/log settings. Adapt
paths for the target machine. This template is not proof the service is installed.

Production use also needs real authentication/authorization, deployment TLS and
routing, appropriate DB permissions/secret management, compatible procedures and
a deliberate single-scheduler setup. Do not enable mail or apply historical
migrations automatically during deployment verification.

## Troubleshooting and limitations

| Symptom | Check |
| --- | --- |
| Frontend works, API fails | Backend/port, Vite `/api` proxy, configured prefix, network. |
| DB unavailable | `/health/db` body; host/port, ODBC driver, credentials, certificates and network. |
| Empty dropdown / No matches | `/options` or `/clients`, DB lookup data/query 43, XML and logs. |
| Edit redirects / missing job | Open from dashboard with job context; check GET ID and browser draft. |
| Save rejected | 422 detail fields, lookup values, positive IDs, widths, defaults and supported mappings. |
| Slow Save | Actual PUT timing, DB latency/locks, batch execution and response reads. UI wait is not precise API time. |
| Mapping edit exports old source | Compare mapping row and saved D SELECT; current generator preserves D expressions/aliases. |
| Excel shows one column | Match import settings to actual bytes; extensions do not guarantee automatic Excel import. Use Download Excel for explicit conversion. |
| Repeated commas/pipes | Parse positions first; blank adjacent fields require consecutive separators. |
| FIXED error | Positive widths, zero-based nonoverlapping explicit positions, header fit and value overflow. |
| Procedure parameter error | Current call has four named parameters; older sample procedure signatures are incompatible. |
| Source CSV missing | Confirm file-input path is selected, then input folder, job-ID filename and permissions. |
| No report files | Validity flags, date/condition matches, result sets and grouping metadata. |
| Report exists, no email | Effective mail setting, client/company eligibility, SMTP status and `emailDelivery`. |
| Scheduler does not fire | Enabled/nonblank schedule, backend running, scheduler setting/timezone, five-minute window and slot files/marker. |
| Unexpected Last Run Date | Distinguish modified date, `rjob.joblastrun`, history trigger values and legacy behavior; do not repair DB values without authorization. |

Current limits include demo-only authentication, client-side pagination, external
DB/procedure dependencies, preserved D projections on existing mapping edits and
validation restrictions for calculated/duplicate aliases when Store Results needs
valid unique column names. Prior QA findings require a fresh retest before being
called current failures.

Further reading:

- [Retirement Builder analysis index](docs/retirement-builder-analysis/README.md)
- [Complete user flow](docs/retirement-builder-analysis/02-complete-user-flow.md)
- [Dropdown sources](docs/retirement-builder-analysis/04-dropdown-data-sources.md)
- [Persistence analysis](docs/retirement-builder-analysis/08-state-and-data-persistence.md)
- [Project instructions](AGENTS.md)
- [Job 60 testing workflow](skills/retirement-builder-test-skills.md)
- [Payroll Builder analysis and planning reference](skills/payroll-builder-skills.md)

Historical analysis can differ from current code. State what was actually verified
and keep DB/query/report effects within the user's authorized task.

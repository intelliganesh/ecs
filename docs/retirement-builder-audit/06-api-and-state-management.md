# Retirement Builder APIs, state and persistence

The repo defines six method/path operations under the Retirement Builder router and two supporting health operations. The dashboard's static Template download is a separate browser asset request. SQL Server, filesystem output and SMTP are backend dependencies. The wizard uses the same-origin `/api/v1` prefix. Vite proxies `/api` to `http://127.0.0.1:8000`, and the dev port may be incremented when the default is occupied.

## HTTP operations

| Integration | Method and path | Request | Success handling | Failure handling and dependencies |
| --- | --- | --- | --- | --- |
| API01 Options | GET `/api/v1/retirement-builder/options` | No params/body | Typed option JSON; App fetches once per mount, aborts on unmount, merges into empty defaults and provides it via OptionsContext | Frontend fallback and option error; SQL errors can leave partial/empty catalog without non-200. Uses documented catalogs, XML, and code formats. |
| API02 List jobs | GET `/api/v1/retirement-builder/jobs` | No query params; filters and sort are client-side | Array with raw legacy fields and normalized id/general/schedule. List refresh runs every five seconds while document visible, also after run settles. | SQL failure returns 500. Initial frontend shows load error; poll errors retain old data. Query 42 returns enabled jobs. Manual-only schedule gets blank legacy day/time/type and null start in normalized schedule. |
| API03 Job detail | GET `/api/v1/retirement-builder/jobs/{job_id}` | Integer path ID | Full config with general, schedule, mapping, subscriptions, fileSettings and queryConfiguration. Frontend hydrates draft and Edit General. | 404 missing, 500 read failure. Error is captured but not rendered by the current Dashboard. |
| API04 Create job | POST `/api/v1/retirement-builder/jobs` | JSON config; optional Idempotency-Key header; frontend supplies both | 201 with complete job and assigned ID. App clears create attempt and returns to dashboard. Backend transaction inserts main and child rows. | 422 malformed/request fields, 409 key conflict, 500 persistence error. Key can replay completed or await identical pending request. |
| API05 Update job | PUT `/api/v1/retirement-builder/jobs/{job_id}` | Integer path ID and JSON config; supports partial body | 200 with complete job. Merges omitted fields and updates parent plus replaces six child config sets in one transaction. | 404 missing, 422 rejected supplied fields, 500 save error. Wizard stays on Subscriptions and displays response detail. |
| API06 Run job | POST `/api/v1/retirement-builder/jobs/{job_id}/run` | Integer path ID. Empty body uses saved source; nonempty `text/csv` streams up to 5 MiB and overrides saved source. Dashboard uses empty body. | 200 with `runId`, `rowCount`, `storedRows`, `files:[{fileName,csv}]` and first-file aliases `fileName,csv`. Files are persisted separately and browser links use response data. | 404 missing, 409 disabled, 413 too large, 415 unsupported body media, 422 data/config errors, 500 DB/output failure. Failure history only when attempt reaches report execution. |
| API07 Backend health | GET `/health` | None | `{"status":"ok","service":"backend"}` | No DB check. Operational endpoint, no browser calls. |
| API08 Database health | GET `/health/db` | None | `{"status":"ok","database":"connected"}` after `SELECT 1` | Returns `{"status":"degraded","database":"unavailable"}` on failure; no separate status code set. Operational endpoint, no browser calls. |

**Static asset** GET `/mapped_payroll_columns_HDT.xlsx` is a direct browser download of [the packaged template](/Users/apple/Desktop/ESC/frontend/public/mapped_payroll_columns_HDT.xlsx). The General picker imports locally. There is no HTTP workbook upload, job DELETE, historical report download route, schedule-status endpoint, or backend login endpoint in this router. CSV response links are browser Blob URLs created by the dashboard.

[API wiring](/Users/apple/Desktop/ESC/backend/app/main.py:25) · [Routes and save](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:790) · [Run](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1056) · [Vite proxy](/Users/apple/Desktop/ESC/frontend/vite.config.ts) · [Browser requests](/Users/apple/Desktop/ESC/frontend/src/App.tsx:245)

### Options response

- `fileFormats` contains usable labels ordered case-insensitively, sourced by SQL 32. `outputFileNameFormats` supplies `{label,value}` rows from SQL 53 filtered to seven codes and sorted by part count and precedence.
- `buildFrequencies`, `hours`, `minutes`, `meridiems`, `weekDays`, `recordTypes` and `sortDirections` come from the XML file. `comparisonOperators` comes from Python operator mapping.
- `mappingColumns` and `mappingColumnTypes` come from SQL 30. Trim key/label; display description or fallback key, ignore blank key and duplicate case-insensitive label. SQL date/numeric type families and known type names are normalized, with text fallback.
- `payrollMappingColumns` is the intersection of those labels with Record Type, Company Name, Pay Date, Employee Count and Net Salary Total. `payrollCompanies` maps unique company IDs to names. The mapping format dictionary and flattened `mappingFormats` are code-defined. [Catalog](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:283) · [XML](/Users/apple/Desktop/ESC/backend/config/options.xml) · [Payroll catalog](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:20)

### Job payload shape

```json
{
  "general": {
    "fileName": "Example", "fileFormat": "Pipe", "description": "",
    "outputFileNameFormat": "FILENAME", "enable": true,
    "storeResultsToTable": true, "reportSource": "companyPayroll"
  },
  "schedule": {"startDate": null},
  "mapping": {
    "includeHeader": false,
    "rows": [{
      "field": "Pay Date", "startPosition": "0", "length": "0",
      "recordType": "Detail", "defaultValue": "", "mappingColumn": "", "format": "YYYY-MM-DD"
    }]
  },
  "subscriptions": {"mergeFiles": false, "rows": []},
  "fileSettings": {"sortingOrder": [], "conditionalStatements": []}
}
```

A populated schedule includes `buildFrequency`, `hour`, `minute`, `meridiem`, and optional UI `week`. Sorting rows are `{orderBy,mappingColumn,direction}`; condition rows are `{mappingColumn,condition,value}`. A subscription row is `{client,email,companyId?}` with a DB client or payroll company target. Optional API-only `queryConfiguration` accepts `{recttype,query,conditions,sortOrder}`; the UI omits it. Schema/model defaults are different from fresh UI defaults. For example API requests default `reportSource` to CSV and `includeHeader` to true, while a fresh UI starts payroll with Include Header Row unchecked.

The API validates the submitted PUT fields before it merges omitted values. It uses Pydantic `model_fields_set` per section to distinguish absent values from an explicit null/empty value, with full child-row arrays replaced when provided. The UI sends all normal sections. It drops all-empty subscriptions, joins parsed email tags, and uses 0 for blank mapping numeric fields. An entirely blank Schedule sends only a null start date, allowing untouched API defaults to remain without creating a runnable schedule. [Models](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:41) · [Payload](/Users/apple/Desktop/ESC/frontend/src/App.tsx:354) · [Partial updates](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:686)

## State locations

| State | Owner and lifetime | What it contains and transitions |
| --- | --- | --- |
| Demo session | React RootRoutes plus sessionStorage | `ecs-demo-authenticated` and `ecs-demo-user`. No backend session/token exchange or sign-out control in traced shell. |
| Wizard draft | React App plus sessionStorage `ecs-retirement-builder-draft` | Mode, existing job ID, General flags and file label, schedule, mapping rows, subscriptions including draft text, settings. Restored only for matching mode, Edit also requires numeric job ID. Local row sequence is raised on load. Taking Dashboard clears session snapshot. In-memory App values can remain until Add or Edit resets them. |
| Wizard guards/network | React App state/refs | Validated steps, current route, save/upload messages, importing, upload request gen, saving state and synchronous in-flight guard. Refresh reinitializes transient errors/references. |
| Create identity | React ref and sessionStorage `ecs-retirement-builder-create-attempt` plus server memory | SHA-256 client fingerprint and random key. Reused for same body. Server keeps pending Futures and completed outcomes keyed by header, TTL 3600 seconds with 1,024 completed limit. Add resets key, successful creation clears it, failure allows retry. No persistent backend idempotency table. |
| Dashboard data and filters | App memory | Enabled API rows, load status and map of ten filters. Filters remain while the same App stays mounted across wizard navigation, and refresh clears state. |
| Dashboard selection/sort/run | Dashboard component memory | Selected IDs, sort column/direction, running flags, errors, immediate result and Blob URLs. Component remount resets these; API history survives. Poll runs independently of these local values. |
| Dialog and searchable pickers | FileSettingsModal/SearchableSelect local state and DOM | Applied settings propagate to App; in-progress dialog edits, open dropdown and search do not persist across refresh. Start/close and focus behavior are per component. |
| Scheduler/run process | APScheduler, locked status counter, transactions | Scheduler cadence, job lock, filesystem slot markers, per-process In Progress counts. SQL state and files survive browser reload and server restart. |

No localStorage use was found in this feature. The shared Context is for options, while wizard state is local to App and copied to the per-tab session draft. [App state](/Users/apple/Desktop/ESC/frontend/src/App.tsx:187) · [Effects](/Users/apple/Desktop/ESC/frontend/src/App.tsx:245) · [API idempotency](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:839)

## SQL Server persistence

The router loads SQL IDs from `backend/query.brl` XML at import. `_prepared_query` substitutes placeholders with SQLAlchemy bound names. Separately defined typed/parameterized SQL handles full reads, locking, history inserts, company resolution and result inserts. Both write flows use an engine transaction. PUT SQL 44 deletes existing config children before rewriting, leaving history/results as their own records.

| Data or operation | Object and relevant query | Persistence notes |
| --- | --- | --- |
| Job parent | `rjob`; SQL 36 insert, 45 update, 42 enabled list, READ_JOB detail | Flags, name, description, literal delimiter in filetype, filename format code, metadata. Create supplies null end date. `msrepl_tran_version` is not passed by the app. SQL 45 also stamps joblastrun while updating a job, relevant to the [Last Run audit risk](05-validations-and-edge-cases.md). |
| Schedule | `rjob_schedule_info`; SQL 38 and READ_SCHEDULE / READ_ENABLED_SCHEDULES | Stores label/code, nullable combined startDateTime, day index, integer hour/minute, AM/PM. Inserts even for manual-only. |
| Mappings | `rjob_file_detail`; SQL 35 and READ_MAPPINGS | Dataset number 1, sequential column position, field/source/value/format/type/start/length. |
| Subscription data | `rjob_client_detail`; SQL 37 and READ_SUBSCRIPTIONS | Encoded payroll company or integer client, joined email string. Also main `ismerge` and combined `mergeemail` values. |
| Query configuration | `rjob_query`; SQL 31 and READ_QUERY_CONFIGURATION | Payroll H/D/T rows and D condition/sort text. Old PAYROLL marker can be read. CSV sorted files persist CSV_SORT text, while current normal CSV filters use the condition table. Unrelated saved markers survive rewrites as configured. |
| Sort and conditions | `rjob_file_sorting_details` SQL 54; `rjob_file_condition_details` SQL 55 and reads | Positive priority sequence, mapping column; operator and normalized threshold. Directions are preserved in query clause metadata. Historical negative priority is a read fallback. |
| Job history | `rjob_history`; SQL 52 update, INSERT_RUN_HISTORY fallback, SQL 42 reads | Latest status/timestamp/message; update/insert with GETDATE(). SQL 42 displays later of job and history run datetimes and left joins latest global history detail. No writes to next trigger field in traced paths. |
| Output rows | `rjob_result`; INSERT_RESULT, migration 001 | One row per rendered data record, run ID, job ID, 1-based row number, H/D/T type, JSON formatting. Append across separate runs if enabled. |
| Catalogs and source tables | `rjob_mapping_column` SQL 30, `rjob_file_typ` SQL 32, `rjobformat` SQL 53; `companies`, `employees`, `payroll` | Read-only in the wizard. Procedure owns source joins. Payroll names resolve company IDs separately for grouping and mail. |

[SQL catalog](/Users/apple/Desktop/ESC/backend/query.brl:456) · [Parameter binding](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:386) · [Child writes](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:703) · [Job reads](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:606) · [Result table migration](/Users/apple/Desktop/ESC/backend/migrations/001_retirement_builder_results.sql)

## Run, filesystem and scheduling data flow

- A manual request locks a job with UPDLOCK/HOLDLOCK, rehydrates it, rejects disabled or missing rows, resolves output delimiter, loads source, then enters a savepoint for generation. Company Payroll uses `PAYROLL_REPORT_PROCEDURE` with templates at save and a job ID for saved H/D/T runs. The legacy CSV branch reads `REPORT_INPUT_DIR/{jobId}.csv` when the API body is empty. Text/csv body overrides either source.
- Results render, publish and optionally insert within the orchestrated run. `publish_report` uses a temporary file and atomic replace, then removes the final file on an exception through the context. Job history saves success or records failure after savepoint rollback. HTTP response carries output strings, and downloads are not dependent on re-reading the stored files.
- Manual output path is `REPORT_OUTPUT_DIR/manual/{jobId}/{runId}/{filename}`. Scheduled output path is `REPORT_OUTPUT_DIR/scheduled/{jobId}/{UTC-slot}/{filename}`. No-report scheduled success writes `.complete` for duplicate avoidance. Relative settings resolve under backend directory.
- Scheduler installs a background job when enabled, runs every 30 seconds, uses timezone-aware slot checks, verifies current schedule and same-slot marker under job lock, and calls common generation. SMTP is attempted after commit only for scheduled output with matching subscriptions and mail enabled. No send event/delivery receipt is persisted for dashboard consumption. [Manual execution](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:964) · [Filesystem](/Users/apple/Desktop/ESC/backend/app/report_files.py:11) · [Automation](/Users/apple/Desktop/ESC/backend/app/report_scheduler.py:99) · [SMTP](/Users/apple/Desktop/ESC/backend/app/report_mail.py:35)

## Dependencies and configuration

| Area | Dependencies and switches |
| --- | --- |
| Frontend | React/React DOM, React Router BrowserRouter, TypeScript, Vite, Lucide icons, SheetJS `xlsx`, `@noble/hashes`, native file/date input and browser Blob URLs. No chart or visualization dependency used by this feature. |
| Backend | FastAPI 0.115.6, Uvicorn 0.34.0, pydantic-settings 2.7.1, SQLAlchemy 2.0.37, pyodbc 5.2.0, APScheduler 3.11.3, standard Python CSV/decimal/ZoneInfo/email/smtplib. |
| SQL | SQL Server with configured ODBC driver and `DB_*`/trust options. SQLAlchemy uses pool_pre_ping. Migration 011 defines `usp_CompanyPayrollReport` and its template mode. No second helper needed. |
| Feature settings | `SCHEDULER_ENABLED` default true; `SCHEDULER_TIMEZONE` default UTC. `MAIL_ENABLED` default false; mail config uses `MAIL_*` and encrypted SMTP. `REPORT_INPUT_DIR`, `REPORT_OUTPUT_DIR`, `PAYROLL_REPORT_PROCEDURE`, `API_V1_PREFIX`, `CORS_ORIGINS`. These are source defaults; actual secrets and delivery status were not probed. |
| Authentication | Browser-level demo guard only in this source. FastAPI has CORS configuration and no corresponding Retirement Builder authentication dependency. Reverse proxy or external access controls were not assessed. |

[Frontend dependencies](/Users/apple/Desktop/ESC/frontend/package.json) · [Backend dependencies](/Users/apple/Desktop/ESC/backend/requirements.txt) · [Configuration](/Users/apple/Desktop/ESC/backend/app/core/config.py:14) · [Database engine](/Users/apple/Desktop/ESC/backend/app/db.py:9) · [Authentication routing](/Users/apple/Desktop/ESC/frontend/src/main.tsx:9)


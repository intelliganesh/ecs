# APIs and request flow

## Scope and architecture

There are **7 feature HTTP method/path operations across 5 path templates**. GET and POST `/jobs` are different operations; GET and PUT `/jobs/{job_id}` are different operations. The health endpoints, Vite assets, static template and SMTP are supporting interfaces, not extra feature REST operations. Every browser request uses relative `/api/v1`; Vite proxies `/api` to port 8000. FastAPI includes the router with the configured prefix (default `/api/v1`). [frontend/src/App.tsx:41](/Users/apple/Desktop/ESC/frontend/src/App.tsx:41), [frontend/vite.config.ts:6](/Users/apple/Desktop/ESC/frontend/vite.config.ts:6), [backend/app/main.py:33](/Users/apple/Desktop/ESC/backend/app/main.py:33), [backend/app/core/config.py:17](/Users/apple/Desktop/ESC/backend/app/core/config.py:17).

All endpoints are in `backend/app/routers/retirement_builder.py`. The module combines controller, validation, business helpers and SQL access; there is no separate repository layer to name. The SQLAlchemy engine wraps pyodbc. Payroll execution additionally uses a raw cursor. [backend/app/db.py:1](/Users/apple/Desktop/ESC/backend/app/db.py:1), [backend/app/payroll_source.py:196](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:196).

## All seven operations

| # | Method / endpoint | When and caller | Request | Response / use | Backend chain / SQL / tables | Errors and writes |
|---|---|---|---|---|---|---|
| API-1 | GET `/api/v1/retirement-builder/jobs` | Dashboard mount, visible 5s polls, after run settlement: `fetchRetirementJobs` | None | Array of legacy and nested job summaries; normalize then display/filter/sort | `list_retirement_builder_jobs` → `_job_rows` query 42, query 32, `READ_ENABLED_SCHEDULES`; rjob, schedule, history, history_details, file_typ [backend/app/routers/retirement_builder.py:953](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:953) | 500 on SQL failure. Initial UI error, later poll retains old data. Read only. [frontend/src/App.tsx:319](/Users/apple/Desktop/ESC/frontend/src/App.tsx:319) |
| API-2 | GET `/api/v1/retirement-builder/options` | `App` wizard-entry effect | None; fetch cache no-store | Formats, naming codes, schedule options, mapping labels/types/formats, companies; stored in OptionsContext | `get_retirement_builder_options` → `_options_from_xml`; queries 30/32/53, `READ_PAYROLL_COMPANY_IDS`, XML; mapping_column, file_typ, rjobformat, companies [backend/app/routers/retirement_builder.py:398](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:398) | DB errors often yield partial HTTP 200. Full request failure sets options error and retains prior values. Read only. [frontend/src/App.tsx:300](/Users/apple/Desktop/ESC/frontend/src/App.tsx:300) |
| API-3 | GET `/api/v1/retirement-builder/clients` | `SubscriptionsStep` mounts for CSV source only; effect cleanup aborts on leave | None; cache no-store | `[{id:number,label:string}]`; values use String(id), labels use label | `list_retirement_builder_clients` → query 43 → `prism.export.Client_Details`; status != T [backend/app/routers/retirement_builder.py:936](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:936), [backend/query.brl:743](/Users/apple/Desktop/ESC/backend/query.brl:743) | 503 on SQL error; UI can still accept custom positive ID. Live 503 observed. Read only. [frontend/src/App.tsx:1075](/Users/apple/Desktop/ESC/frontend/src/App.tsx:1075) |
| API-4 | GET `/api/v1/retirement-builder/jobs/{job_id}` | `startEdit`, retry; optional Schedule metadata-restoration attempt | Path integer job ID | Full nested job including queryConfiguration; `loadJob` fills draft | `get_retirement_builder_job` → `_read_edit_job` → batched 7 job-detail SELECTs + file format query; rjob and six detail tables + file_typ [backend/app/routers/retirement_builder.py:1045](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1045), [backend/app/routers/retirement_builder.py:705](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:705) | 404 missing; 500 SQL/ODBC; loading screen shows Retry. Read only. [frontend/src/App.tsx:414](/Users/apple/Desktop/ESC/frontend/src/App.tsx:414) |
| API-5 | POST `/api/v1/retirement-builder/jobs` | Finish new job: `saveJob` | JSON described below; Content-Type application/json; Idempotency-Key | 201 full job including new database ID; navigate dashboard | `create_retirement_builder_job` → `_create_job` → `_validate_payload` → queries 32,36,30, company IDs as needed; `_write_job_details` uses 31/38/35/37/54/55; full reread [backend/app/routers/retirement_builder.py:965](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:965) | 422 validation, 409 changed payload with same key, 500 save failure. Writes configuration in transaction. |
| API-6 | PUT `/api/v1/retirement-builder/jobs/{job_id}` | Finish edit: `saveJob` | Same JSON; no idempotency header | 200 full updated job; navigate dashboard | `update_retirement_builder_job` → read original → merge omitted fields → query45 update parent → query44 delete six detail sets → rewrite → reread [backend/app/routers/retirement_builder.py:1057](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1057) | 404 missing; 422 validation; 500 SQL/runtime/value failure. Transactional replacement of child data. |
| API-7 | POST `/api/v1/retirement-builder/jobs/{job_id}/run` | Dashboard `runSelectedJob` after date dialog | Optional `start_date`, `end_date` query values; browser sends no body. API-only CSV override supported | Run UUID, row/stored counts, delimiter, first file convenience properties, all files, optional emailDelivery; Blob/Excel output | async handler → threadpool `_run_job` → job lock/read → payroll SP or source file → `build_report_files` → disk → optional `INSERT_RESULT` → query52/history inserts; then optional SMTP [backend/app/routers/retirement_builder.py:1199](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1199), [backend/app/routers/retirement_builder.py:1241](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1241) | 404 job, 409 disabled, 422 invalid report/range, 415 non-CSV body, 413 >5MiB body, 500 SQL/disk. Writes history/disk and optional results; may send emails. Not read-only. |

No delete endpoint, dropdown-by-parent endpoint, separate upload endpoint, authentication endpoint, or calculation-preview API was found in the feature. `fetch` appears at the explicit sites above; local helpers/XLSX imports introduce no additional HTTP feature calls. [frontend/src/App.tsx:42](/Users/apple/Desktop/ESC/frontend/src/App.tsx:42), [frontend/src/App.tsx:304](/Users/apple/Desktop/ESC/frontend/src/App.tsx:304), [frontend/src/App.tsx:421](/Users/apple/Desktop/ESC/frontend/src/App.tsx:421), [frontend/src/App.tsx:495](/Users/apple/Desktop/ESC/frontend/src/App.tsx:495), [frontend/src/App.tsx:657](/Users/apple/Desktop/ESC/frontend/src/App.tsx:657), [frontend/src/App.tsx:1078](/Users/apple/Desktop/ESC/frontend/src/App.tsx:1078), [frontend/src/retirementBuilder.ts:84](/Users/apple/Desktop/ESC/frontend/src/retirementBuilder.ts:84).

## Typical request sequence

```mermaid
sequenceDiagram
  participant U as Browser
  participant API as FastAPI
  participant DB as SQL Server
  U->>API: GET jobs (Dashboard)
  API->>DB: query42 + query32 + enabled schedules
  API-->>U: enabled job summaries
  U->>API: GET options (Add)
  API->>DB: query30 + query32 + query53 + companies
  Note over API: Also read options.xml
  API-->>U: dropdown metadata
  Note over U: General / Schedule / Mapping change local draft only
  opt Existing CSV source, on Subscriptions
    U->>API: GET clients
    API->>DB: query43
  end
  U->>API: POST jobs + JSON + Idempotency-Key (Finish)
  API->>DB: transaction: insert parent, details, reread
  API-->>U: 201 with saved ID
  U->>API: GET jobs (return Dashboard; then poll every 5s)
  Note over U: Later choose one job and run dates
  U->>API: POST jobs/id/run?start_date=2026-11-01&end_date=2026-11-30
  API->>DB: lock, read, execute payroll procedure, record run
  Note over API: Generate files, optional row storage; commit then SMTP
  API-->>U: files and counts, optional email acceptance counts
  U->>API: GET jobs (run settled + polling)
```

Edit adds a GET detail before form use and uses PUT at Finish. Retry can repeat detail GET. Refresh reloads options/draft. Returning to CSV Subscriptions remounts it and fetches clients again. StrictMode can cause extra development requests/aborts. There is no guaranteed ordering between independent page effects; the diagram shows a normal logical journey, not a promise of network microsecond order. [frontend/src/App.tsx:300](/Users/apple/Desktop/ESC/frontend/src/App.tsx:300), [frontend/src/App.tsx:414](/Users/apple/Desktop/ESC/frontend/src/App.tsx:414), [frontend/src/App.tsx:1075](/Users/apple/Desktop/ESC/frontend/src/App.tsx:1075), [frontend/src/main.tsx:16](/Users/apple/Desktop/ESC/frontend/src/main.tsx:16).

## Actual request shape with fake values

This is an explanatory example, **not a request executed during this investigation**. Company 101 must exist in a target test database for this payroll subscription to be accepted. No email was sent.

```json
{
  "general": {
    "fileName": "Payroll",
    "fileFormat": "Comma",
    "description": "Example payroll summary",
    "outputFileNameFormat": "FILENAME_CLIENT_PAYDAY",
    "enable": true,
    "storeResultsToTable": true,
    "reportSource": "companyPayroll"
  },
  "schedule": {"startDate": null},
  "mapping": {
    "includeHeader": true,
    "rows": [
      {"field":"Company","startPosition":"0","length":"0","recordType":"Header","defaultValue":"","mappingColumn":"Company Name","format":""},
      {"field":"Staff Count","startPosition":"0","length":"0","recordType":"Detail","defaultValue":"","mappingColumn":"Employee Count","format":""},
      {"field":"Total Pay","startPosition":"0","length":"0","recordType":"Detail","defaultValue":"","mappingColumn":"Net Salary Total","format":""},
      {"field":"Count Check","startPosition":"0","length":"0","recordType":"Trailer","defaultValue":"","mappingColumn":"Employee Count","format":""}
    ]
  },
  "subscriptions": {
    "mergeFiles": false,
    "rows": [{"client":"","companyId":101,"email":"reviewer@example.invalid"}]
  },
  "fileSettings": {
    "sortingOrder": [{"orderBy":"1","mappingColumn":"Pay Date","direction":"DESC"}],
    "conditionalStatements": [{"mappingColumn":"Employee Count","condition":">=","value":"2"}]
  }
}
```

`saveJob` sends no local row IDs, `selectedFile`, workbook bytes, `emailDraft`, `storedStartDateTime`, or `queryConfiguration`. Company subscriptions send `client:''` and companyId; CSV subscriptions send a string client ID and omit companyId. Emails from saved tags plus uncommitted draft text are combined/deduplicated before sending. Blank mapping numeric strings are sent as `"0"`. No schedule values means `{"startDate":null}`; backend Pydantic supplies the remaining schedule defaults. [frontend/src/App.tsx:457](/Users/apple/Desktop/ESC/frontend/src/App.tsx:457), [frontend/src/App.tsx:468](/Users/apple/Desktop/ESC/frontend/src/App.tsx:468), [backend/app/routers/retirement_builder.py:56](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:56).

For a scheduled fake example, schedule would include `startDate:'2026-11-19'`, `buildFrequency:'Weekly'`, `hour:'4'`, `minute:'00'`, `meridiem:'AM'`, `week:'Thursday'`. `rjob_schedule_info.startDateTime` receives `2026-11-19 04:00:00`. [backend/app/routers/retirement_builder.py:467](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:467), [backend/app/routers/retirement_builder.py:880](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:880).

## Response contracts

POST/PUT/GET detail use sections `id`, `general`, `schedule`, `mapping`, `subscriptions`, `fileSettings`, `queryConfiguration`. Exact model field names/defaults: [backend/app/routers/retirement_builder.py:44](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:44), [backend/app/routers/retirement_builder.py:123](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:123). The observed live detail includes `general.testfileName` and `selectedFile` as model fields, but no `schedule.startDateTime`. The frontend tries to read `startDateTime`; that help text is therefore not populated by the currently observed detail response. [frontend/src/App.tsx:406](/Users/apple/Desktop/ESC/frontend/src/App.tsx:406), [frontend/src/App.tsx:924](/Users/apple/Desktop/ESC/frontend/src/App.tsx:924), [HTTP evidence](evidence/read-only-http.json).

Options response keys are enumerated in `RetirementBuilderOptions` [backend/app/routers/retirement_builder.py:166](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:166) and the sanitized [live snapshot](evidence/read-only-http.json). Company names and existing job contents are intentionally omitted from evidence.

A possible simplified run response, with fake identifiers and content:

```json
{
  "runId":"00000000-0000-4000-8000-000000000001",
  "rowCount":3,
  "storedRows":3,
  "delimiter":",",
  "fileName":"Payroll_101_2026-11-01.csv",
  "csv":"Staff Count,Total Pay\r\nExample Manufacturing\r\n2,5500.75\r\n2\r\n",
  "files":[{"fileName":"Payroll_101_2026-11-01.csv","csv":"Staff Count,Total Pay\r\nExample Manufacturing\r\n2,5500.75\r\n2\r\n"}],
  "emailDelivery":{"enabled":false,"matched":0,"accepted":0}
}
```

The column-heading line comes from Detail layout; H/D/T lines can have different widths. `rowCount` counts mapped records, not the heading line or raw employee payroll records. `storedRows` is zero if Store Results is off. `fileName`/`csv` duplicate the first member of `files`; they are not merged content. [backend/app/routers/retirement_builder.py:1152](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1152), [backend/app/retirement_results.py:538](/Users/apple/Desktop/ESC/backend/app/retirement_results.py:538).

## Failure and duplicate behavior

`readSaveError` handles string and Pydantic array detail; 404 has a friendly missing-job message; network TypeError has a connectivity message. The backend validation errors specify paths such as `body.mapping.rows.0.field`. General/mapping errors are initially withheld until the step is attempted. [frontend/src/App.tsx:225](/Users/apple/Desktop/ESC/frontend/src/App.tsx:225), [frontend/src/App.tsx:263](/Users/apple/Desktop/ESC/frontend/src/App.tsx:263), [frontend/src/App.tsx:503](/Users/apple/Desktop/ESC/frontend/src/App.tsx:503), [backend/app/routers/retirement_builder.py:476](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:476).

New creates use SHA-256 of frontend JSON plus a random 16-byte key saved in sessionStorage. Identical retries reuse the key; changed payloads get a new one. Server fingerprints the validated payload, shares a Future for concurrent requests, and caches successful replies for one hour, at most 1,024 entries. Cache is process-local; restart, expiry, or different workers can allow another insert. No database uniqueness rule on file name is established by these checks. [frontend/src/App.tsx:485](/Users/apple/Desktop/ESC/frontend/src/App.tsx:485), [backend/app/routers/retirement_builder.py:198](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:198), [backend/app/routers/retirement_builder.py:1003](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1003).

Run uses a row lock to serialize attempts but has no idempotency key. Two requests can execute sequentially and create two runs. Scheduler uses slot output files/.complete markers to skip an already-completed slot. Email acceptance is not inbox delivery; errors are reported separately from report generation. [backend/app/routers/retirement_builder.py:295](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:295), [backend/app/routers/retirement_builder.py:1199](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1199), [backend/app/report_scheduler.py:62](/Users/apple/Desktop/ESC/backend/app/report_scheduler.py:62), [backend/app/report_mail.py:108](/Users/apple/Desktop/ESC/backend/app/report_mail.py:108).

## Read-only checks actually performed

- Frontend 5174 returned HTTP 200; backend `/health/db` reported connected.
- GET jobs, options and one existing job detail returned 200 through the frontend proxy.
- GET clients returned 503.
- No live POST, PUT, run or SMTP operation was executed. Write-path behavior is supported by source and isolated tests, not a live end-to-end save/run test.

Evidence: [sanitized HTTP results](evidence/read-only-http.json), [test execution notes](evidence/verification.md).

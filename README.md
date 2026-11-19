# ECS Applications

Two local applications are included:

- `frontend/`: React + TypeScript + Vite
- `backend/`: FastAPI + SQLAlchemy + Microsoft SQL Server via `pyodbc`

## Run both applications

From this directory:

```bash
./server.sh
```

The script installs dependencies on first run, creates `backend/.env`, and starts both development servers.

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

To test from another device on the same Wi-Fi, open `http://<host-wifi-ip>:5173` while `server.sh` is running. The frontend forwards API requests to the backend. Use the demo login for local testing with test data.

## Manual setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

The backend expects Microsoft ODBC Driver 18 for SQL Server to be installed locally. `GET /health` works without a database; `GET /health/db` verifies the database connection.

## Run a Retirement Builder job

Apply `backend/migrations/001_retirement_builder_results.sql` once to the ECS database using a SQL Server client. The migration creates `dbo.rjob_result`.

Apply `backend/migrations/002_retirement_builder_mapping_columns.sql` to populate the Mapping Column dropdown. It adds missing defaults to the existing `dbo.rjob_mapping_column` table.

For the local sample database, apply migrations `003` through `006` in order. The sample data uses the existing **QA Payroll Sample Company**, with example contact details and pay periods. The catalog stores source identifiers in `mapping_column` and uses `mapping_column_desc` for the labels displayed in the wizard.

Apply `007_retirement_builder_file_formats.sql` to populate **File Format**. The dropdown shows labels from `dbo.rjob_file_typ`, and saving a job writes the matching delimiter character to `dbo.rjob.filetype`. Existing jobs with saved labels still use the lookup to resolve their delimiters. Source CSV input continues to use comma delimiters.

The **Output File Name Format** dropdown reads its seven labels and codes from `backend/config/options.xml`. Saving a job writes the selected code to `dbo.rjob.FileNameFormat`. The **Format** dropdown on the Mapping tab reads its options from `dbo.rjobformat`.

In File Settings, choose **ASC** or **DESC** and a mapping column. Sort rules apply from top to bottom.

Save the job's mappings and place a UTF-8, comma-delimited source CSV named `<job-id>.csv` in `REPORT_INPUT_DIR`. Select the job on the dashboard and click **Run**. The source header should contain each mapping's source column (or the output field name when the mapping column is blank). For jobs with header or trailer mappings, include a `Record Type` column with `H`, `D`, or `T` and provide those rows in the CSV.

The manual run uses the saved mappings and delimiter and offers the output for download. If **Store Results to Table** is enabled, it also saves each generated data row in `dbo.rjob_result` with the job ID, run ID, row number, record type, and mapped values as JSON. The column heading line is part of the CSV only. API clients may also send a source CSV in the run request with `Content-Type: text/csv`.

The report procedure name comes from `PAYROLL_REPORT_PROCEDURE` in `backend/.env`; for the supplied retirement procedure use `PAYROLL_REPORT_PROCEDURE=dbo.rjobbuilder`. The application calls the configured name with exactly four bound inputs: `@client_id` (the selected **job ID**), `@paystartdate`, `@payenddate`, and `@runType`. Manual/ad hoc runs use `A`; scheduled runs use `S`. The Run dialog supplies the manual dates. Omitted dates and scheduled-call date inputs retain the existing `1900-01-01` sentinel; the supplied procedure calculates its own scheduled date range. The application executes the procedure directly, drains all returned result sets, and reads the existing H, D (including multiple Detail sets), and T outputs. The leading `valid_flag`, `retnum`, and `sort1` columns are metadata, not export fields; zero-validity placeholder rows produce no files. The returned export values and order are preserved without repeating mapping, formatting, filtering or sorting. `retnum`/`sort1` drive client/date filename grouping and client subscriptions. The procedure owns its configured result-table storage and run-date history; the application does not duplicate those in `rjob_result` or `rjob_history_details` on a successful procedure run (`storedRows` reports application inserts only, so it is zero on this path). Jobs with existing production H/D/T SQL fragments use this procedure path even if their legacy source flag is `csv`; plain CSV-only jobs and explicit CSV-body runs keep the file/input path. Existing query definitions, SQL scripts, mappings and save-time query generation are unchanged. Saved SQL must already match the configured procedure. The older single typed-payroll result shape remains readable, but the configured procedure must accept the four-input contract. Restart the backend after changing the procedure setting if automatic reload is not enabled. Database execution of the supplied procedure was not performed during this change.

**Output File Name Format** controls how manual and scheduled runs split the output. The runtime reads code parts **FILENAME**, **CLIENT**, and **PAYDAY** in order. **FILENAME** alone creates one CSV. **CLIENT** and **PAYDAY** group the included detail rows by their respective source values. For example, `FILENAME_CLIENT_PAYDAY` can produce `Retirement_000720_2026-11-11.csv`. Legacy label values still work. Include `Client ID` and `Pay Date` in the source when the selected format uses them. Blank grouping values on header or trailer rows apply to every matching output file.

## Production query generation

For legacy rjob exports (the `csv` report source), create/update also generates SELECT fragments for the production `rjobbuilder_new` contract. These fragments omit `FROM`: the procedure appends `from #ret_builder_info`. With Include Header Row checked, H contains the D field names as escaped literals; otherwise H uses configured H mappings and is omitted when none exist. Configured T mappings produce a trailer projection. Without T mappings, the three-column `1900-01-01` trailer is a placeholder, not calculated totals. Existing D SQL and its aliases are preserved. New projections introduce no output aliases beyond the specified `sort1` control column. Calculated/constant D columns with Store Results to Table require confirmed aliases and are rejected until those rules are known. Unconfirmed SQL formats are rejected rather than ignored.

Dataset and column sequence values survive Excel import and editing. Generated records are saved once per H/D/T type using query 31, within the existing create/update transaction; update uses query 44 to replace the old rows. Production sort fragments start with a comma because the procedure appends them to `order by RetNum`. The Company Payroll sample templates remain unchanged. This does **not** switch the application runner to production: the supplied production procedure accepts four parameters and returns separate H/D/T result sets, while the current Company Payroll runner has a different three-parameter, six-column contract. Production execution integration and output-alias rules remain separate work. No production procedure should be invoked merely to test query generation.

## Schedule Retirement Builder reports and emails

Backend warnings and errors are appended to `backend/logs/errors.log`, including API failures,
validation failures, database fallback/health failures, scheduler failures, and SMTP failures.
Each line is a JSON object with an ISO 8601 UTC timestamp (`Z`), severity, logger, source location,
process/thread, message, and exception stack/cause when available. HTTP failures also include
a request ID, method, path, and status; mail failures include the job ID and SMTP response code/text
when the server provides them. Request bodies, headers, query strings, SQL statements and bound
parameters are not logged by the error handlers. Configured database/SMTP passwords are redacted
from file output. Existing terminal logging remains available.

`ERROR_LOG_FILE` defaults to `logs/errors.log` relative to `backend/`. `ERROR_LOG_MAX_BYTES`
defaults to 10 MiB and `ERROR_LOG_BACKUP_COUNT` to 5; backups are named `errors.log.1` through
`errors.log.5` (newest first). The directory is created automatically and excluded from Git.
Restart the backend after changing logging settings. Use one backend worker with this file
rotation setup, consistent with the scheduler/service configuration. Existing terminal output
from before logging was configured is not imported into the file.

Configure these settings in `backend/.env` and restart the backend. See `backend/.env.example` for the full list of SMTP settings.

| Setting | What it controls |
| --- | --- |
| `SCHEDULER_ENABLED` | Starts APScheduler with the API when `true`. |
| `SCHEDULER_TIMEZONE` | Time zone used for the Start Date and Time entered on the Schedule form. Use an IANA name such as `Asia/Kolkata` or `America/New_York`. |
| `REPORT_INPUT_DIR` | Folder containing the source CSV for manual and scheduled runs. |
| `REPORT_OUTPUT_DIR` | Folder where the API saves both manual and scheduled reports. |
| `PAYROLL_REPORT_PROCEDURE` | SQL Server procedure used by every Company Payroll Report job. An unqualified name uses the `dbo` schema. |
| `MAIL_ENABLED` | Emails generated CSVs to matching subscriptions when `true`, for scheduled runs and manual runs using the saved report source. File generation and database storage work with mail disabled. |

Paths can be absolute or relative to `backend/`. Keep the backend running and place the source CSV for job `31` at `REPORT_INPUT_DIR/31.csv`. Update the CSV before the next run if the source data changes. The scheduler reads the enabled jobs every 30 seconds and can pick up a due run within five minutes of its scheduled time. Weekly and biweekly runs use the selected weekday. Monthly runs use the day of the Start Date, or the last day of shorter months.

Manual files are saved under `manual/<job-id>/<run-id>/`. Scheduled files are saved under `scheduled/<job-id>/<scheduled-time-in-UTC>/`. Run one scheduler against a given ECS database and output folder. Keep the scheduled file in place during the five-minute window so a restart can recognize that the run already completed.

When mail is enabled, enter each recipient under the appropriate **Payroll Company** in Subscriptions. For CSV-source jobs, include a `Client ID` in each detail row and subscribe the recipient to that client. A CSV containing multiple companies or clients is attached only if the recipient is subscribed to every one in the file. To email files to individual companies or clients, choose an Output File Name Format that includes **Client ID**. The dashboard shows the mail server's response after **Run**, and generated files remain downloadable if delivery fails. API runs that upload an override CSV return the files for download.


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

Apply `008_retirement_builder_output_file_name_formats.sql` to seed **Output File Name Format**, then apply `010_output_file_name_format_codes.sql` to assign the seven codes and migrate saved jobs. The dropdown shows `dbo.rjobformat.jobformat` and saves the corresponding `jobformattype` code in `dbo.rjob.FileNameFormat`.

In File Settings, choose **ASC** or **DESC** and a mapping column. Sort rules apply from top to bottom.

Save the job's mappings and place a UTF-8, comma-delimited source CSV named `<job-id>.csv` in `REPORT_INPUT_DIR`. Select the job on the dashboard and click **Run**. The source header should contain each mapping's source column (or the output field name when the mapping column is blank). For jobs with header or trailer mappings, include a `Record Type` column with `H`, `D`, or `T` and provide those rows in the CSV.

The manual run uses the saved mappings and delimiter and offers the output for download. If **Store Results to Table** is enabled, it also saves each generated data row in `dbo.rjob_result` with the job ID, run ID, row number, record type, and mapped values as JSON. The column heading line is part of the CSV only. API clients may also send a source CSV in the run request with `Content-Type: text/csv`.

New jobs in the wizard use the **Company Payroll Report**. Apply `009_payroll_record_queries.sql` to backfill existing payroll jobs, then apply `011_inline_payroll_record_queries.sql` to move the templates into the procedure and drop the old helper function. The app calls the procedure configured in `PAYROLL_REPORT_PROCEDURE`, which defaults to `dbo.usp_CompanyPayrollReport`. On save, `@templates_only = 1` returns `recttype` and `Query` for `H`, `D`, and `T`. The app writes those rows to `dbo.rjob_query` using SQL ID `31`. The `D` row stores condition and sort clause text in `Conditions` and `Sort_Order`. For manual and scheduled runs, the app passes `@jobid` so the procedure reads and runs the three saved SELECTs. The app uses the saved condition and sort clauses and applies the configured mappings to the CSV. A replacement procedure must support both modes and return the same six report columns in the same order when run. Restart the backend after changing the procedure name. **Pay Date** uses the payroll month returned by the procedure. For **Client ID** filename formats and payroll subscriptions, the app matches each company name returned by the procedure to a unique `dbo.companies.id`.

**Output File Name Format** controls how manual and scheduled runs split the output. The runtime reads code parts **FILENAME**, **CLIENT**, and **PAYDAY** in order. **FILENAME** alone creates one CSV. **CLIENT** and **PAYDAY** group the included detail rows by their respective source values. For example, `FILENAME_CLIENT_PAYDAY` can produce `Retirement_000720_2026-11-11.csv`. Legacy label values still work. Include `Client ID` and `Pay Date` in the source when the selected format uses them. Blank grouping values on header or trailer rows apply to every matching output file.

## Schedule Retirement Builder reports and emails

Configure these settings in `backend/.env` and restart the backend. See `backend/.env.example` for the full list of SMTP settings.

| Setting | What it controls |
| --- | --- |
| `SCHEDULER_ENABLED` | Starts APScheduler with the API when `true`. |
| `SCHEDULER_TIMEZONE` | Time zone used for the Start Date and Time entered on the Schedule form. Use an IANA name such as `Asia/Kolkata` or `America/New_York`. |
| `REPORT_INPUT_DIR` | Folder containing the source CSV for manual and scheduled runs. |
| `REPORT_OUTPUT_DIR` | Folder where the API saves both manual and scheduled reports. |
| `PAYROLL_REPORT_PROCEDURE` | SQL Server procedure used by every Company Payroll Report job. An unqualified name uses the `dbo` schema. |
| `MAIL_ENABLED` | Emails generated CSVs to matching subscriptions when `true`. File generation and database storage work with mail disabled. |

Paths can be absolute or relative to `backend/`. Keep the backend running and place the source CSV for job `31` at `REPORT_INPUT_DIR/31.csv`. Update the CSV before the next run if the source data changes. The scheduler reads the enabled jobs every 30 seconds and can pick up a due run within five minutes of its scheduled time. Weekly and biweekly runs use the selected weekday. Monthly runs use the day of the Start Date, or the last day of shorter months.

Manual files are saved under `manual/<job-id>/<run-id>/`. Scheduled files are saved under `scheduled/<job-id>/<scheduled-time-in-UTC>/`. Run one scheduler against a given ECS database and output folder. Keep the scheduled file in place during the five-minute window so a restart can recognize that the run already completed.

When mail is enabled, enter each recipient under the appropriate **Payroll Company** in Subscriptions. For CSV-source jobs, include a `Client ID` in each detail row and subscribe the recipient to that client. A CSV containing multiple companies or clients is attached only if the recipient is subscribed to every one in the file. To email files to individual companies or clients, choose an Output File Name Format that includes **Client ID**. Delivery errors appear in the backend log and leave the generated file available.


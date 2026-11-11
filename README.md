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

In File Settings, choose **ASC** or **DESC** and a mapping column. Sort rules apply from top to bottom.

Save the job's mappings and place a UTF-8, comma-delimited source CSV named `<job-id>.csv` in `REPORT_INPUT_DIR`. Select the job on the dashboard and click **Run**. The source header should contain each mapping's source column (or the output field name when the mapping column is blank). For jobs with header or trailer mappings, include a `Record Type` column with `H`, `D`, or `T` and provide those rows in the CSV.

The manual run uses the saved mappings and delimiter and offers the output for download. If **Store Results to Table** is enabled, it also saves each generated data row in `dbo.rjob_result` with the job ID, run ID, row number, record type, and mapped values as JSON. The column heading line is part of the CSV only. API clients may also send a source CSV in the run request with `Content-Type: text/csv`.

**Output File Name Format** controls how manual and scheduled runs split the output. **File Name** creates one CSV. **Client ID** and **Payday** group the included detail rows by their respective source values. A combination groups by all selected fields and adds the entered file name when **File Name** is selected. For example, **File Name + Client ID + Payday** can produce `Retirement_000720_2026-11-11.csv`. Include `Client ID` and `Pay Date` in the source when the selected format uses them. Blank grouping values on header or trailer rows apply to every matching output file.

## Schedule Retirement Builder reports and emails

Configure these settings in `backend/.env` and restart the backend. See `backend/.env.example` for the full list of SMTP settings.

| Setting | What it controls |
| --- | --- |
| `SCHEDULER_ENABLED` | Starts APScheduler with the API when `true`. |
| `SCHEDULER_TIMEZONE` | Time zone used for the Start Date and Time entered on the Schedule form. Use an IANA name such as `Asia/Kolkata` or `America/New_York`. |
| `REPORT_INPUT_DIR` | Folder containing the source CSV for manual and scheduled runs. |
| `REPORT_OUTPUT_DIR` | Folder where the API saves both manual and scheduled reports. |
| `MAIL_ENABLED` | Emails generated CSVs to matching subscriptions when `true`. File generation and database storage work with mail disabled. |

Paths can be absolute or relative to `backend/`. Keep the backend running and place the source CSV for job `31` at `REPORT_INPUT_DIR/31.csv`. Update the CSV before the next run if the source data changes. The scheduler reads the enabled jobs every 30 seconds and can pick up a due run within five minutes of its scheduled time. Weekly and biweekly runs use the selected weekday. Monthly runs use the day of the Start Date, or the last day of shorter months.

Manual files are saved under `manual/<job-id>/<run-id>/`. Scheduled files are saved under `scheduled/<job-id>/<scheduled-time-in-UTC>/`. Run one scheduler against a given ECS database and output folder. Keep the scheduled file in place during the five-minute window so a restart can recognize that the run already completed.

When mail is enabled, include a `Client ID` in each detail row and add the recipient under that client in Subscriptions. Each recipient gets an email with the CSVs they are subscribed to. A CSV containing multiple clients is attached only if the recipient is subscribed to every client in that file. To email files to individual clients, choose an Output File Name Format that includes **Client ID**. Delivery errors appear in the backend log and leave the generated file available.


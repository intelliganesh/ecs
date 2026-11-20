# ECS project instructions

These instructions apply throughout this repository. Follow the current user's
task and restrictions; a documentation or analysis request does not authorize
application edits, database writes, report Runs or email delivery.

## Project map

- `frontend/`: React, TypeScript and Vite. `src/App.tsx` contains the application
  UI; `src/retirementBuilder.ts` contains Retirement Builder models/helpers.
- `backend/`: FastAPI, SQLAlchemy and Microsoft SQL Server through pyodbc.
  `app/main.py` is the API entrypoint; `app/core/config.py` loads settings.
- `backend/app/routers/retirement_builder.py`: Retirement Builder endpoints,
  validation, options and persistence.
- `backend/app/retirement_query_builder.py`: generated report-query fragments.
- `backend/app/retirement_procedure.py`, `retirement_results.py`: procedure output
  handling, formatting, grouping and report serialization.
- `backend/app/report_scheduler.py`, `report_mail.py`, `report_files.py`:
  scheduling, mail delivery and report files.
- `backend/query.brl`: existing SQL query definitions. `backend/config/options.xml`:
  configurable options, including Output File Name Format.
- `backend/tests/`, `frontend/tests/`: automated tests. `docs/`, `qa-results/`,
  `qa-evidence/`: analysis and QA documentation/evidence.
- `README.md`: setup and historical behavior notes. Verify behavior against
  current source/runtime; some older descriptions may no longer match the code.

## Change boundaries

- Make only changes needed for the current task. Inspect the working tree first;
  preserve existing user changes and unrelated files. Do not reset, clean or
  revert them as part of another task.
- For read-only analysis, inspect code, files, logs, API GETs or DB SELECTs only.
  A stored procedure or API with a read-looking name may still write or send mail;
  inspect its effects before invoking it.
- Do not change DB values, schema, migrations, stored procedures or existing SQL
  queries unless the current task explicitly authorizes those changes. A code fix
  does not implicitly authorize a migration, data repair or live job execution.
- Do not create jobs, execute reports, trigger scheduled work, send email or
  perform manual database cleanup as an incidental verification step. Use the
  scope and authorization of the current task.
- Keep `MAIL_ENABLED=false` for local QA. Never enable or send mail for testing
  without an explicit task authorizing that delivery. Check effective settings
  before a live Run; do not silently modify `.env` to make a test proceed.
- Preserve generated reports and existing evidence. Do not delete them as cleanup.
  Keep credentials, `.env` secrets and sensitive payroll/SSN values out of commits,
  shared reports and chat output.
- Documentation-only tasks change documentation only. Do not start services,
  change configuration, connect to the DB or run jobs merely to edit a guide.

## Implementation and verification

- Read the affected flow before editing. Trace UI values through requests,
  validation, persistence and consumers; preserve compatibility with existing jobs
  unless a requested behavior change requires otherwise.
- Treat labels, stored values, source column names, client IDs and job IDs as
  distinct. Check the existing mapping/lookup contract rather than guessing.
- For Retirement Builder saves, preserve H/D/T record-type requirements and field
  ordering. Verify current procedure parameters, query fragments, date handling,
  sorting and formatting from code instead of assuming a historical contract.
- Keep query/config sources centralized where already designed. Do not introduce
  hardcoded substitutes for DB/XML dropdown values as a routine fix.
- Prefer focused tests with mocked DB/SMTP/scheduler dependencies. Inspect tests
  for side effects before running them; never point mutation tests at the shared
  database. Report blockers instead of bypassing restrictions.
- Existing commands, when relevant and safe for the requested work:
  - Backend, from `backend/`: `MAIL_ENABLED=false SCHEDULER_ENABLED=false .venv/bin/python -m unittest discover -s tests`.
  - Frontend, from `frontend/`: `npm run lint`, `npm run build`, and
    `node --test tests/*.test.mjs`.
- Check the actual running URL/port; Vite's configured default is 5173, while the
  commonly used local testing instance is 5174. Do not assume either is active.
  `server.sh` can install dependencies/create configuration/start services; do not
  execute it as a harmless inspection command.
- Verify outcomes appropriate to the change. Distinguish code inspection, mocked
  tests, UI behavior, live DB verification and actual generated-file checks.
  Do not claim an unexecuted scenario passed or a UI wait is an API measurement.
- Report changes, checks, confirmed issues, limitations and remaining work. Do not
  fix newly discovered unrelated issues without scope to do so.

## Job 60 testing workflow

For an authorized Retirement Builder edit/manual-Run test of **job 60**, read
[the job 60 testing guide](docs/retirement-builder-testing/SKILLS.md) before acting.
That guide contains its specific UI-only mutation rules, no-new-job restriction,
scenario matrix, mail controls, fresh-baseline capture and mandatory restoration.
Those job-specific permissions do not authorize edits or Runs for other jobs and
do not apply automatically to unrelated project work. SKILLS.md is a project
workflow document, not an installed Codex skill.

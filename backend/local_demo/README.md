# Local Retirement and Payroll Builder demo

This setup uses SQL Server at `127.0.0.1:1433`, database `ecs`. The existing
production connection in `backend/.env` has not been changed. Local credentials
are in this directory's ignored `.env` file, with owner-only file permissions.
Do not commit or share that file.

## Start the isolated application

From `backend/`:

```sh
.venv/bin/python local_demo/start.py
```

From `frontend/`, in a second terminal:

```sh
npm run dev:local-demo
```

Open `http://127.0.0.1:5175`. Its API proxy targets the local demo API on port
8001. The standard Vite proxy and production database connection remain unchanged.
The local `.env` uses `RETIREMENT_REPORT_PROCEDURE=dbo.rjobbuilder` and
`PAYROLL_REPORT_PROCEDURE=dbo.payrolljobbuilder`. Change the relevant key and
restart the local API to select another compatible SP; saved queries are not
rewritten. Mail follows `MAIL_ENABLED` in the local `.env`: `false` blocks all
email and `true` permits delivery to configured subscribers when a report runs.
Restart the API after changing it. It is currently `false`. The local launcher
disables both automatic report schedulers for manual QA. Report files use
`backend/report-output/local-demo`. No services are started by database setup.

## What was provisioned

- Missing `rjob*` and `payroll*` configuration tables were created in local `ecs`.
  Existing tables, procedures and records were preserved. No jobs were seeded.
- Seventeen source tables were created under local `prism.export`, retaining all
  1,088 original column definitions: names, types, lengths, precision/scale,
  nullability, identity/computed attributes and collations. Source primary and
  unique keys were included. This is a dependency-specific test schema, not a
  full replica of all Prism tables, foreign keys, triggers or security settings.
- One explicitly authorized extra local computed column,
  `EMPLOYEE_PAYROLL_REGISTER.R_Gross_Earn AS (GROSS_EARN)`, lets the existing
  payroll SP compile without modifying its text. The source table and SP were
  not changed.
- `dbo.rjobbuilder`, `dbo.payrolljobbuilder`, the two current edit procedures,
  `dbo.fn_ee_phone_no` and `dbo.payroll_wage_data_wcsumm` were copied with their
  definitions unchanged. Exact text comparison passed for all six objects.
- Local `Syd` and `Syd_Testing` compatibility databases contain synonyms pointing
  exclusively to local `ecs`; `Syd_Testing` also has the unchanged phone function.
  These support database names embedded in the existing SPs.
- Missing format/mapping/grouping catalog entries were inserted from source.
  Existing local entries were preserved. Three file-format spellings and six
  mapping entries differed from the source comparison, so the local catalogs
  are a preserved superset, not a byte-for-byte replacement. Some differences
  are identity/order values; existing labels/types may also differ.
- `backend/config/options.xml` and `backend/query.brl` were not modified.

## Synthetic data

Clients `901` and `902` (Prism IDs `000901`, `000902`) have three fictional
employees: `D00901`, `D00902`, `D00903`. Demo pay dates are October 15 and
November 13, 20 and 24, 2026. Use October 1–November 30, 2026 to cover all dates.

There are 12 vouchers, 48 earnings rows, 36 deductions and 12 other-earnings
rows. Fixtures include regular wages, overtime, tips, reimbursements,
pretax/Roth deductions, loans, YTD values and WC lookup data. Email addresses use
`example.invalid`; SSN-like placeholders use the invalid `000` area prefix.
No production employee, client or payroll records were copied.

## Reproducibility and verification

`bootstrap.py` consumes metadata/catalog snapshots, never a production connection.
It defaults to plan-only mode; `--apply` is explicit and requires the expected
local SQL Server identity. Existing objects/records are never overwritten.
The computed alias requires a separate explicit flag. `seed.py` inserts missing
synthetic keys only and does not create jobs or run SPs.

The setup's temporary metadata and verification directory is recorded in
`/tmp/ecs-local-builder-setup-path`. It contains column definitions, catalog/SP
definitions, create scripts and verification reports, not a database backup or
production employee/payroll rows. Keep it local; temporary files may expire.

Validation covered local column definitions, copied module text, local alias
targets and fixture counts. Existing non-catalog local tables retained their
row counts and content fingerprints during provisioning. No stored procedure,
report Run, scheduler or email was executed for this setup. Runtime calculations
and generated reports still require separately authorized local job testing.

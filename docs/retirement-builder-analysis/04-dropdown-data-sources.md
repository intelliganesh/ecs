# Every dropdown's complete data path

## Shared fetch and select behavior

`App` enters any wizard screen → effect keyed by `isWizard` → `fetch('/api/v1/retirement-builder/options', {cache:'no-store'})` → FastAPI `get_retirement_builder_options` → `_options_from_xml` → XML plus database lookups → response → `OptionsContext` → `SearchableSelect` or native `select`. There is no separate backend controller/service/repository class: the router function and its helpers execute SQL directly. [frontend/src/App.tsx:300](/Users/apple/Desktop/ECS/frontend/src/App.tsx:300), [backend/app/routers/retirement_builder.py:931](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:931), [backend/app/routers/retirement_builder.py:398](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:398).

One wizard entry normally makes one options request; step-to-step navigation keeps `isWizard=true` and reuses context. Leaving and reentering refetches; refresh refetches. React StrictMode may start/abort an extra effect in development. There is no React Query/SWR/Redux query cache. `cache:'no-store'` requests fresh HTTP data; context avoids per-step requests. XML and SQL are read on each backend options call; settings alone have an `lru_cache`. [frontend/src/App.tsx:318](/Users/apple/Desktop/ECS/frontend/src/App.tsx:318), [frontend/src/main.tsx:16](/Users/apple/Desktop/ECS/frontend/src/main.tsx:16), [backend/app/core/config.py:78](/Users/apple/Desktop/ECS/backend/app/core/config.py:78).

`SearchableSelect` stores query/open/activeIndex locally. Searches filter **labels**, case-insensitively. Selection calls the parent setter and closes the menu; choosing an option makes no API call. Empty `clearLabel` options let the user clear certain fields. Most selects prepend an existing saved value; File Format, Output Name, Mapping Column, Format and Clients explicitly opt out. Searchable menus support arrows, Enter, Escape, click-outside close and return focus. [frontend/src/App.tsx:90](/Users/apple/Desktop/ECS/frontend/src/App.tsx:90).

## Trace for all 16 definitions

| Dropdown | React state / component | API / timing / parameters | Backend and data access | Table / label and ID | Mapping and dependency |
|---|---|---|---|---|---|
| File Format | `fileFormat` / General `SearchableSelect` | GET `/options`, wizard entry, no params | `_options_from_xml` → `_file_formats` → query 32 | `dbo.rjob_file_typ.filetyp` is option label/value; `delimiter` is stored separator | Sorted case-insensitively; invalid names/delimiters filtered; aliases normalized. [backend/app/routers/retirement_builder.py:329](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:329), [frontend/src/App.tsx:850](/Users/apple/Desktop/ECS/frontend/src/App.tsx:850) |
| Output File Name Format | `outputFileNameFormat` | Same GET | `_output_file_name_formats`, reads `config/options.xml` | **No SQL/SP/table used for these options**; XML text=label, `value`=code | Seven codes; backend whitelist; affects grouping and filenames. [backend/app/routers/retirement_builder.py:367](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:367), [frontend/src/App.tsx:858](/Users/apple/Desktop/ECS/frontend/src/App.tsx:858) |
| Build Frequency | `schedule.buildFrequency` | Same GET | XML `buildFrequencies` | No DB; text=value and label | Shared select overrides passed options based on `ariaLabel`; no dependent fetch. [frontend/src/App.tsx:111](/Users/apple/Desktop/ECS/frontend/src/App.tsx:111), [backend/config/options.xml:12](/Users/apple/Desktop/ECS/backend/config/options.xml:12) |
| Hour | `schedule.hour` | Same GET | XML `hours` | No DB | 1–12; does not trigger another request. [backend/config/options.xml:18](/Users/apple/Desktop/ECS/backend/config/options.xml:18) |
| Minute | `schedule.minute` | Same GET | XML `minutes` | No DB | 00–59; no dependency fetch. [backend/config/options.xml:22](/Users/apple/Desktop/ECS/backend/config/options.xml:22) |
| AM or PM | `schedule.meridiem` | Same GET | XML `meridiems` | No DB | Affects 24-hour conversion on save. [backend/app/routers/retirement_builder.py:467](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:467), [backend/config/options.xml:30](/Users/apple/Desktop/ECS/backend/config/options.xml:30) |
| Week | `schedule.week` | Same GET | XML `weekDays` | No DB | Validation depends on frequency; always visible. [frontend/src/App.tsx:274](/Users/apple/Desktop/ECS/frontend/src/App.tsx:274), [backend/config/options.xml:31](/Users/apple/Desktop/ECS/backend/config/options.xml:31) |
| Record Type | `mappingRows[i].recordType` | Same GET | XML `recordTypes` | No DB | Despite literal JSX fallback Header/Detail/Trailer, shared component chooses runtime XML by `ariaLabel.endsWith('record type')`. [frontend/src/App.tsx:111](/Users/apple/Desktop/ECS/frontend/src/App.tsx:111), [frontend/src/App.tsx:1026](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1026) |
| Mapping Column | `mappingRows[i].mapping` | Same GET | `_mapping_catalog` → query 30 | `dbo.rjob_mapping_column`: key `mapping_column`, label `mapping_column_desc`, type `mapping_column_dt` | API gives sorted unique descriptions; select stores displayed label; save resolves label to database key. Includes all catalog fields, not only payroll. [backend/app/routers/retirement_builder.py:307](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:307), [backend/app/routers/retirement_builder.py:828](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:828), [frontend/src/App.tsx:1033](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1033) |
| Format | `mappingRows[i].format` | Same GET | query 53 → `_mapping_format_options` | `dbo.rjobformat.jobformat` code; `jobformat + ' - ' + jobformat_desc` label; `jobformattype` category | Filtered locally by inferred/declared source type; type changes may clear incompatible format. [backend/app/routers/retirement_builder.py:377](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:377), [frontend/src/App.tsx:978](/Users/apple/Desktop/ECS/frontend/src/App.tsx:978) |
| Payroll Company | `subscriptions[i].companyId` | Same GET; payroll path | `payroll_company_ids` → `READ_PAYROLL_COMPANY_IDS` | `dbo.companies`; grouped name, unique `MIN(id)` only if count=1 | Positive IDs only; frontend displays `id - name`; parses ID; clears legacy client. No API on selection. [backend/app/payroll_source.py:44](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:44), [frontend/src/App.tsx:1071](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1071) |
| Clients | `subscriptions[i].client`, `clientCatalog` | GET `/clients` when CSV Subscriptions mounts, no params; not fetched on payroll path | `list_retirement_builder_clients` → query 43 | `prism.export.Client_Details.Client_ID` numeric ID; `Client_ID + ' - ' + Client_DBA_Name` label; status != T | `.map(id => String(id))` with label dictionary; duplicate IDs first label; positive custom ID allowed. [backend/app/routers/retirement_builder.py:936](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:936), [backend/query.brl:743](/Users/apple/Desktop/ECS/backend/query.brl:743), [frontend/src/App.tsx:1072](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1072) |
| Sort direction / Order By | modal `sortingRows[i][0]`, native select | GET `/options` already loaded | XML `sortDirections` | No DB for options | Blank prompt, ASC, DESC. Priority is separate internal `sortingRows[i][2]`, not this dropdown. [frontend/src/App.tsx:1286](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1286), [backend/config/options.xml:35](/Users/apple/Desktop/ECS/backend/config/options.xml:35) |
| Sort Mapping Column | modal `sortingRows[i][1]` | Same loaded context | Full mapping catalog + `PAYROLL_COLUMNS` code | Payroll: code-defined five labels. CSV: mapped source labels + catalog, case-insensitive unique | `allowCustom=true`; backend payroll validation rejects names outside five. [frontend/src/App.tsx:1145](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1145), [frontend/src/App.tsx:1292](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1292) |
| Condition Mapping Column | modal `conditionalRows[i][0]` | Same context | Same as Sort Mapping Column | Same source and labels | Chooses numeric/date input validation; no fetch. [frontend/src/App.tsx:1152](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1152) |
| Condition operator | modal `conditionalRows[i][1]`, native select | Same GET | Python `COMPARISONS` dictionary | No DB | Eight operators; existing unsupported entry is shown disabled; invalid rule cannot Save. [backend/app/retirement_results.py:71](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:71), [frontend/src/App.tsx:1295](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1295) |

## Every finite choice and its separate behavior

### File Format: live database values

| Label | Delimiter | Result |
|---|---|---|
| Comma | `,` | CSV columns separated by comma; quoting handled by Python csv.writer |
| Pipe | `\|` | Same columns separated by pipe |
| Tab | tab character | Same columns separated by tab |
| Semicolon | `;` | Same columns separated by semicolon |
| Space | one space | Same columns separated by space; whitespace delimiter preserved |

All still use `.csv` filenames. These five values were read from the actual DB and from GET options. The underlying delimiter, not its display label, is written to `rjob.filetype`. [backend/app/routers/retirement_builder.py:338](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:338), [backend/app/routers/retirement_builder.py:975](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:975), [backend/app/retirement_results.py:543](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:543), [DB evidence](evidence/read-only-database.json).

### Output names: XML is authoritative for this dropdown

| Code | Label | Grouping | Fake output example |
|---|---|---|---|
| FILENAME | File Name | One file | `Payroll.csv` |
| CLIENT | Client ID | Per client/company ID | `101.csv` |
| PAYDAY | Payday | Per normalized source date | `2026-11-01.csv` |
| FILENAME_CLIENT | File Name + Client ID | Per ID | `Payroll_101.csv` |
| FILENAME_PAYDAY | File Name + Payday | Per date | `Payroll_2026-11-01.csv` |
| CLIENT_PAYDAY | Client ID + Payday | Per ID/date pair | `101_2026-11-01.csv` |
| FILENAME_CLIENT_PAYDAY | File Name + Client ID + Payday | Per ID/date pair | `Payroll_101_2026-11-01.csv` |

Blank or invalid saved codes fall back to File Name in generation. In payroll, Client ID means resolved payroll company ID; Payday means `payroll_month` labeled Pay Date. Selecting CLIENT displays a help message and may require resolving unique company IDs on run. `rjobformat` currently contains similar output-name records, but this dropdown reads XML, not those records. [backend/config/options.xml:3](/Users/apple/Desktop/ECS/backend/config/options.xml:3), [backend/app/retirement_results.py:145](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:145), [backend/app/payroll_source.py:149](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:149), [frontend/src/App.tsx:865](/Users/apple/Desktop/ECS/frontend/src/App.tsx:865).

### Schedule options

| Choices | Individual meaning |
|---|---|
| Daily | `D`; every eligible date at configured time after start date |
| Weekly | `W`; chosen Week day each week |
| Bi-Weekly | `B`; every 14 days from first selected weekday on/after start date |
| Monthly | `M`; start-date day each month, clamped to month end |
| Hours 1,2,3,4,5,6,7,8,9,10,11,12 | Each selects that 12-hour clock hour; AM/PM determines 24-hour time |
| Minutes 00–59 inclusive | Every integer from 0 to 59 is its exact minute; labels are zero-padded |
| AM | hour modulo 12; 12 AM becomes 00 |
| PM | hour modulo 12 + 12; 12 PM becomes 12 |
| Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday | Persist schedule weekday 0,1,2,3,4,5,6 respectively; weekly rules use that day |
| Clear prompts | Empty stored draft string; no schedule if all six fields clear |

Evidence: XML [backend/config/options.xml:12](/Users/apple/Desktop/ECS/backend/config/options.xml:12), save conversions [backend/app/routers/retirement_builder.py:459](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:459), scheduler [backend/app/report_scheduler.py:26](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:26). No retirement-age dropdown exists.

### Record Type, sort and operators

| Option | Behavior |
|---|---|
| Header | Stored H; mapped source H records output before D and T |
| Detail | Stored D; detail source records are filtered and sorted |
| Trailer | Stored T; maps source T records after details; not an automatically calculated footer |
| Blank Record Type | Save/run treats as Detail; initial manual row appears blank |
| ASC | Ascending source-value sort; numeric when all nonblank values parse as Decimal, otherwise case-insensitive text |
| DESC | Descending sort; numeric blanks remain last; text fallback uses reversed string ordering |
| `=` | Equals |
| `==` | Equals; payroll saved clause normalizes it to `=` |
| `!=` | Not equal |
| `<>` | Not equal |
| `<` | Strictly less than |
| `<=` | Less than or equal |
| `>` | Strictly greater than |
| `>=` | Greater than or equal |

All conditions combine using AND and apply to Detail records. Blank direction/operator is a prompt and fails modal Save if the rule exists. [backend/app/routers/retirement_builder.py:834](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:834), [backend/app/retirement_results.py:438](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:438), [backend/app/retirement_results.py:474](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:474), [backend/app/retirement_results.py:502](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:502), [backend/app/payroll_source.py:76](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:76).

### All 35 live Mapping Column choices

Each choice picks the named source value; it does not cause a request or calculate that value. The database catalog is metadata, not proof that the payroll procedure supplies every column. Only `rectype`, `company_name`, `payroll_month`, `employee_count`, `net_salary_total` are supplied by the current payroll report. Every other mapping needs a default in payroll, or appropriate CSV source data for CSV jobs. [backend/app/payroll_source.py:27](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:27), [backend/app/payroll_source.py:132](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:132).

| Saved catalog key | Dropdown label | Declared type |
|---|---|---|
| company_id | Client ID | text |
| company_name | Company Name | text |
| pay_date | Date | date |
| date_of_birth | Date of Birth | date |
| employee_count | Employee Count | number |
| employee_id | Employee ID | text |
| employee_name | Employee Name | text |
| work_email | Employee Work Email | email |
| first_name | First Name | text |
| gross_pay | Gross Pay | number |
| hire_date | Hire Date | date |
| hours_worked | Hours Worked | number |
| last_name | Last Name | text |
| net_salary | Net Salary | number |
| net_salary_total | Net Salary Total | number |
| payroll_month | Pay Date | date |
| pay_end_date | Pay End Date | date |
| pay_start_date | Pay Start Date | date |
| phone | Phone | phone |
| rectype | Record Type | text |
| ssn | SSN | ssn |
| termination_date | Termination Date | date |
| allowances | Allowances | number |
| basic_salary | Basic Salary | number |
| city | Company City | text |
| company_code | Company Code | text |
| company_email | Company Email | email |
| company_phone | Company Phone | phone |
| deductions | Deductions | number |
| department | Department | text |
| designation | Designation | text |
| employee_code | Employee Code | text |
| is_active | Is Active | text |
| paydate | Employee Pay Date | date |
| payment_status | Payment Status | text |

Sort/filter payroll choices are Company Name, Employee Count, Net Salary Total, Pay Date, Record Type (five code-defined labels). Custom entries can be typed into settings, but payroll validation accepts only these fields. For non-Pay-Date fields the modal requires numeric thresholds even for Company Name or Record Type; a numeric-looking rule on text data may therefore save and later fail conversion. [frontend/src/App.tsx:1151](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1151), [frontend/src/App.tsx:1171](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1171), [backend/app/payroll_source.py:154](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:154).

### Format choices: actual availability versus code support

**VERIFIED live:** `mappingFormatsByType={}` and `mappingFormats=[]`; opening a numeric mapping Format dropdown showed only **No format**. The seven rows currently in `rjobformat` are output-name categories (FILENAME etc.), which `_mapping_format_options` excludes. No usable transformation choices are currently populated. [HTTP evidence](evidence/read-only-http.json), [backend/app/routers/retirement_builder.py:377](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:377).

**VERIFIED in source, not currently selectable from live catalog:** the renderer supports the individual date, number, text, padding, phone and SSN codes explained in [calculations](07-calculations-and-business-rules.md). They appear only if query 53 returns recognized type categories and codes; there is no hardcoded UI fallback. Phone/email/SSN buckets also include text/all formats; number/date use their own bucket plus all. [frontend/src/App.tsx:981](/Users/apple/Desktop/ECS/frontend/src/App.tsx:981), [backend/app/retirement_results.py:29](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:29).

## Actual end-to-end dropdown example: Mapping Column

1. General entry fetches `/api/v1/retirement-builder/options` through the Vite proxy. [frontend/src/App.tsx:304](/Users/apple/Desktop/ECS/frontend/src/App.tsx:304)
2. Handler calls `_options_from_xml`; `_mapping_catalog` executes query 30: `SELECT mapping_column, mapping_column_desc, mapping_column_dt FROM dbo.rjob_mapping_column`. [backend/app/routers/retirement_builder.py:307](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:307), [backend/query.brl:456](/Users/apple/Desktop/ECS/backend/query.brl:456)
3. Confirmed live row: key `employee_count`, description `Employee Count`, type `number`. No customer data is needed for this lookup. [DB evidence](evidence/read-only-database.json).
4. API contains `mappingColumns` with `Employee Count`, `mappingColumnLabels.employee_count='Employee Count'`, and `mappingColumnTypes['Employee Count']='number'`. [backend/app/routers/retirement_builder.py:430](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:430)
5. Select shows the label; callback stores `mappingRows[i].mapping='Employee Count'`. Finish sends `mappingColumn:'Employee Count'`. [frontend/src/App.tsx:1033](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1033), [frontend/src/App.tsx:471](/Users/apple/Desktop/ECS/frontend/src/App.tsx:471)
6. `_write_job_details` resolves the label to `employee_count`; query 35 stores it in `rjob_file_detail.jobfieldmapping`. Run resolves that key against the payroll aliases and reads the procedure's Employee Count output. [backend/app/routers/retirement_builder.py:828](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:828), [backend/app/routers/retirement_builder.py:895](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:895), [backend/app/routers/retirement_builder.py:1140](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1140), [backend/app/retirement_results.py:403](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:403).

## Empty/error behavior and dependencies

- If query 30 fails, catalog becomes empty, while XML options can still load. If the later DB block fails, companies become empty; any already-read file/format values may remain. SQLAlchemy errors are swallowed in these blocks, so options may return HTTP 200 with partial/empty lists. XML parse errors are not handled by those SQL exception blocks. [backend/app/routers/retirement_builder.py:398](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:398).
- Empty options with a clearLabel can show the clear option rather than the loading/error message, because `filteredOptions.length` is nonzero. Errors are not a guaranteed prominent banner. Other saved-value selects may still show a saved value absent from the new options. [frontend/src/App.tsx:112](/Users/apple/Desktop/ECS/frontend/src/App.tsx:112), [frontend/src/App.tsx:152](/Users/apple/Desktop/ECS/frontend/src/App.tsx:152).
- Clients HTTP error empties the catalog and retains custom positive-ID entry. The live endpoint returned **503**. The underlying SQL failure reason and upstream table availability are **NOT VERIFIED**; query 43's cross-database dependency is confirmed from source, not proven to be the failure cause. [frontend/src/App.tsx:1078](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1078), [backend/app/routers/retirement_builder.py:941](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:941).
- Dependencies are local: source column → format type/options; frequency → Week validation; reportSource → company/client selector and settings columns; filename grouping → required source columns at run. No selection triggers a cascading dropdown-fetch API. [frontend/src/App.tsx:274](/Users/apple/Desktop/ECS/frontend/src/App.tsx:274), [frontend/src/App.tsx:1003](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1003), [frontend/src/App.tsx:1075](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1075), [backend/app/retirement_results.py:423](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:423).

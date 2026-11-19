# Calculations and business rules, in simple English

## Where the numbers come from

The feature builds payroll exports. Its actual calculations are payroll aggregation, formatting/rounding, comparisons, scheduling and file grouping. It contains no retirement-age or compound-interest formula. Current live mapping-format options are empty; formatting formulas below are implemented and tested with local data, but not currently selectable from the live dropdown. [backend/config/payroll_record_queries.json:1](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:1), [backend/app/retirement_results.py:325](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:325), [HTTP evidence](evidence/read-only-http.json).

## 1. Payroll count and net-salary total: SQL

For each `(company_name, payroll_month)` group, both D and T SQL execute:

```sql
COUNT(*) AS employee_count,
SUM(p.net_salary) AS net_salary_total
```

The joins are company → employee → payroll. The current queries count joined **payroll rows**, not distinct people. If one person has two payroll rows in the same company/month group, the count increases twice. SUM ignores NULL salaries; an all-NULL group has a NULL sum, which later becomes an empty CSV cell or a mapping default. No status/active filter is included. Company name, rather than company ID, is the grouping key. Evidence: [backend/config/payroll_record_queries.json:3](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:3), installed SP [backend/migrations/012_payroll_report_date_range.sql:12](/Users/apple/Desktop/ECS/backend/migrations/012_payroll_report_date_range.sql:12).

Fake example:

| Company/month | Joined payroll row | net_salary |
|---|---|---|
| Example Manufacturing / 2026-11-01 | Person A's row | 2500.25 |
| Same group | Person B's row | 3000.50 |

`employee_count = COUNT(*) = 2`. `net_salary_total = 2500.25 + 3000.50 = 5500.75`. The trailer repeats 2 and 5500.75 for that group. It is not a grand total across all months, and Python does not recalculate that aggregate after filters. Header is company name plus zero count and zero total in SQL. Wrapper makes Header Pay Date NULL. [backend/migrations/012_payroll_report_date_range.sql:11](/Users/apple/Desktop/ECS/backend/migrations/012_payroll_report_date_range.sql:11), [backend/app/payroll_source.py:164](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:164).

The label Pay Date is actually `payroll.payroll_month`. Filtering 2026-11-02 through 2026-11-30 would exclude a 2026-11-01 payroll-month record even if a separate paycheck date was later in November. This distinction is important when explaining apparent missing records. [backend/config/payroll_record_queries.json:3](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:3).

### Existing salary setup calculations: separate from report execution

Migration 003 seeds `net_salary = basic_salary + allowances - deductions` and adds `gross_pay = CONVERT(decimal(13,2), basic_salary + allowances)` as a computed column. Example: 3000+200−150=3050 net, 3000+200=3200 gross. The report reads existing net_salary; it does not rerun the seed formula. How every real payroll row was produced is **NOT VERIFIED**. The computed gross_pay definition was verified in live schema metadata. [backend/migrations/003_sample_payroll_data.sql:32](/Users/apple/Desktop/ECS/backend/migrations/003_sample_payroll_data.sql:32), [backend/migrations/003_sample_payroll_data.sql:90](/Users/apple/Desktop/ECS/backend/migrations/003_sample_payroll_data.sql:90), [schema evidence](evidence/read-only-database.json).

## 2. Mapping a value: Python

For each output field:

```python
source_key = (mapping.mappingColumn.strip() or mapping.field.strip()).casefold()
value = row.get(source_key) or mapping.defaultValue
output[mapping.field] = _format_value(value, mapping)
```

Aliases resolve catalog keys/display labels against actual headings first. An empty or absent source uses Default Value. A source string `'0'` is nonempty and is retained. A whitespace string is nonempty and is retained unless a chosen format strips it. Missing columns without defaults fail before rendering. Unknown payroll fields without defaults fail on save; the full Mapping Column catalog can offer fields the payroll procedure does not supply. [backend/app/retirement_results.py:179](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:179), [backend/app/retirement_results.py:403](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:403), [backend/app/retirement_results.py:419](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:419), [backend/app/retirement_results.py:550](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:550), [backend/app/payroll_source.py:132](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:132).

`Start Position` never participates in this value formula. `Length` participates only in LA/RA padding. Output always uses csv.writer with a selected separator; setting position/length does not switch to fixed-width mode. [backend/app/retirement_results.py:538](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:538), [backend/app/retirement_results.py:362](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:362).

## 3. Numeric formatting and rounding: Python Decimal

Named formats:

| Format code | Decimal places | Example input → output |
|---|---|---|
| `0 - Integer` | 0 | `-10.505` → `-11` |
| `0.00 - Decimal` | 2 | `-10.505` → `-10.51` |
| `0.0000 - Decimal` | 4 | `12.34565` → `12.3457` |
| `#,##0` | 0 plus thousands grouping | `1234.5` → `1,235` |
| `#,##0.00` | 2 plus grouping | `1234.505` → `1,234.51` |
| Numeric mask `#+` optionally `$` and decimal `#` digits | Count decimal # characters; no grouping; remove trailing fractional zeros | `$###.##`: `1234.50` → `$1234.5`; negative result places `-` before `$` |

Exact formula is `Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)` with adequate local precision. Ties round away from zero (1.005→1.01; −1.005→−1.01). This is not JavaScript floating-point rounding. Numeric mask integer `#` count does not limit total integer digits. Nonfinite values, unparseable values or exponent adjusted ≥1000 fail formatting. Empty value or blank format bypasses all transformation. [backend/app/retirement_results.py:325](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:325).

An existing test actually checked `-10.505` → `-10.51` and `-11`, with date formatting, and passed in this investigation. [backend/tests/test_retirement_results.py:216](/Users/apple/Desktop/ECS/backend/tests/test_retirement_results.py:216). Other examples in this table are derived from code unless present in an executed test; they are not live payroll runs.

## 4. Threshold precision and storage: backend validation

Numeric condition thresholds are rounded to **two decimals** using ROUND_HALF_UP before database writes. They must fit absolute magnitude ≤`9999999999999999.99` after rounding. Formula:

```text
rounded = Decimal(input).quantize(Decimal('0.01'), ROUND_HALF_UP)
```

123.456→123.46; −1.005→−1.01; −0.001→0.00 (negative zero normalized). 9999999999999999.995 fails because rounding exceeds storage range. NaN/Infinity fail. These exact boundaries are covered by an existing test that passed. [backend/app/routers/retirement_builder.py:500](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:500), [backend/tests/test_retirement_builder.py:584](/Users/apple/Desktop/ECS/backend/tests/test_retirement_builder.py:584).

A date threshold is identified by valid ISO `YYYY-MM-DD`. Date `2026-11-01` stores condition_symbol `date:>=` and numeric condition_value `20261101`; `_condition_from_db` decodes both. Its saved payroll D clause is `[Pay Date] >= '2026-11-01'`. Dates are not rounded. [backend/app/routers/retirement_builder.py:680](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:680), [backend/app/routers/retirement_builder.py:920](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:920), [backend/app/payroll_source.py:73](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:73).

## 5. Filter rules: Python, not an extra payroll WHERE

Each rule resolves a source column. Date thresholds compare parsed source dates; otherwise both sides are Decimal. All rules must pass:

```text
keep Detail = rule1(source) AND rule2(source) AND ...
```

Operators: =/== equal, !=/<> unequal, <, <=, >, >=. No rules means all details pass. The comparison uses unformatted source values; mapping numeric formatting happens later. Thresholds are already rounded by save, which can change a comparison boundary. A threshold 2.345 becomes 2.35, so source 2.346 is less than it. [backend/app/retirement_results.py:438](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:438), [backend/app/retirement_results.py:474](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:474), [backend/app/routers/retirement_builder.py:575](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:575).

Fake example: counts 1,2,3 with rule Employee Count>=2 retain 2 and 3. With two payroll months and rule Net Salary Total>5500, totals 5500.75 and 4000.00 retain only 5500.75. This filters already grouped payroll summary rows, not individual employees before aggregation. [backend/config/payroll_record_queries.json:3](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:3), [backend/app/retirement_results.py:474](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:474).

Only D is directly condition-filtered. For payroll, matching T rows are removed in alignment with discarded details; an alignment mismatch fails. Header rows may remain, and matching grouping constraints still apply. Trailers are not recomputed into a new total. For ordinary CSV, arbitrary trailer totals are preserved and may no longer match filtered details. [backend/app/retirement_results.py:489](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:489).

Modal validation calls for dates only on payroll Pay Date. For CSV date-like columns it also allows numeric threshold text; actual run then chooses numeric comparisons for that threshold. It does not support general textual comparisons like Company Name='Example'. Backend payroll validation rejects date values on non-Pay-Date fields. [frontend/src/App.tsx:1171](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1171), [backend/app/payroll_source.py:160](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:160).

## 6. Inclusive run date range and sentinel

`1900-01-01` means unbounded. Omitted start/end become that sentinel. A bounded run includes a date d exactly when:

```text
(start is sentinel OR start <= d) AND (end is sentinel OR d <= end)
```

Both endpoints are included. A reversed range fails only if both sides are bounded. Sentinel cannot represent a precise filter for 1 January 1900. [backend/app/retirement_results.py:86](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:86), [backend/app/routers/retirement_builder.py:1241](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1241).

Payroll dates are filtered by SQL on `CAST([Pay Date] AS date)` after grouped report construction. H rows are retained only for companies with matching dated D/T when bounded. CSV date-range filtering looks for Pay Date/Payday source or fallback Check Date; it applies to D and T before detail conditions. A missing date source for a bounded CSV run fails. [backend/migrations/012_payroll_report_date_range.sql:51](/Users/apple/Desktop/ECS/backend/migrations/012_payroll_report_date_range.sql:51), [backend/app/retirement_results.py:430](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:430), [backend/app/retirement_results.py:472](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:472).

No date range is stored as the job's next default range by the UI. Requested bounds are stored per attempt in history_details. Scheduled runs use both sentinel dates and therefore report all available dates under the current implementation. [backend/app/routers/retirement_builder.py:1109](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1109), [backend/app/report_scheduler.py:75](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:75).

## 7. Sort priority and direction

Sorting rules order by numeric `orderBy`. Python applies rules in reverse priority using stable sorts, so first rule is the main key. For each key, if all nonblank source strings parse as Decimal, it sorts numerically; otherwise casefolded text. Numeric blanks are last for both directions. Text fallback reverses the complete string sort for DESC. [backend/app/retirement_results.py:450](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:450), [backend/app/retirement_results.py:502](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:502).

Example: Pay Date DESC then Employee Count ASC makes newer source dates first, with smaller counts first within tied dates. ISO date strings sort chronologically by lexical order; other date encodings are **not parsed for sorting**. Dashboard sorting is separate and operates displayed strings with Intl.Collator. [frontend/src/App.tsx:570](/Users/apple/Desktop/ECS/frontend/src/App.tsx:570), [backend/app/retirement_results.py:502](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:502).

The modal automatically gives each new rule `max(existing priority)+1`. If that exceeds SQL int max it renumbers. Add flow direction initially blank; Edit new rule defaults ASC. The UI label Order By actually selects direction. Current sort priority table stores compact positives; direction is kept in `rjob_query.Sort_Order`, which has priority when reading. [frontend/src/App.tsx:1230](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1230), [backend/app/routers/retirement_builder.py:739](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:739), [backend/app/routers/retirement_builder.py:914](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:914).

## 8. Date, text, padding, phone and SSN formats

These are supported renderer codes, not a claim of populated live dropdown options. [backend/app/retirement_results.py:29](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:29), [backend/app/retirement_results.py:325](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:325).

| Individual code | Behavior |
|---|---|
| `MMDDYYYY`, `MMDDYYYY - Date` | 2026-02-09→02092026 |
| `MM/DD/YYYY` | →02/09/2026 |
| `MM-DD-YYYY` | →02-09-2026 |
| `CCYYMMDD`, `YYYYMMDD` | →20260209 |
| `YYYY-MM-DD` | →2026-02-09 |
| `DD/MM/YYYY` | →09/02/2026 |
| `DD-MM-YYYY` | →09-02-2026 |
| `Trim Whitespace` | Strip leading/trailing whitespace |
| `Uppercase` | Apply Python str.upper |
| `Lowercase` | Apply Python str.lower |
| `LA`, `LA - Left Justified` | ljust(length); pads right, never truncates longer values |
| `RA`, `RA - Right Justified` | rjust(length); pads left, never truncates longer values |
| `Digits Only` | Validate allowed phone punctuation then strip nondigits |
| `(XXX) XXX-XXXX` | Ten North American digits formatted with parentheses; optional leading country 1 removed |
| `XXX-XXX-XXXX` | Same ten-digit rule with dashes |
| `International (+)` | Requires explicit + or 00 prefix; converts to +; 2–15 digits, first not 0 |
| `XXXXXXXXX`, `XXXXXXXXX - SSN` | Nine digits after stripping dashes/outer spaces; output plain digits |
| `XXX-XX-XXXX`, `XXX-XX-XXXX - SSN` | Nine digits with dash positions inserted |

Date input parser accepts ISO YYYY-MM-DD, M/D/YYYY, or exactly MMDDYYYY. It checks real calendar dates. Arbitrary locale parsing is not used. Padding >1000 fails on run even though saved Length accepts up to SQL int max. Phone extensions and unexpected punctuation fail. Email-like columns can receive text/all formats; no dedicated email format renderer exists. Unsupported nonblank format fails when a nonempty value is formatted. [backend/app/retirement_results.py:281](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:281), [backend/app/retirement_results.py:297](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:297), [backend/app/retirement_results.py:325](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:325).

## 9. Grouping, filenames, headers and merging

The seven output-name formats choose zero, one or two grouping dimensions: client/company ID and payday. Distinct retained Detail groups produce separate files. Dates normalize to ISO. H/T templates match exact dimension values or blank wildcard dimensions; missing matching source header/trailer for a populated group fails. Output records order H then D then T. [backend/app/retirement_results.py:224](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:224), [backend/app/retirement_results.py:515](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:515), [backend/app/retirement_results.py:546](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:546).

Name parts replace invalid filename characters, strip trailing dots/spaces and obey UTF-8 byte budgets. Base name drops `.csv`; blank unsafe base falls back to job-ID name. Reserved device names are prefixed `_`. Colliding sanitized group names get a 12-character SHA-256 suffix and then a numeric suffix if necessary. These are file-name rules, not report calculations. [backend/app/retirement_results.py:163](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:163), [backend/app/retirement_results.py:516](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:516).

Include Header Row adds output column names (Detail layout preferred). It does not create an H data record. Mapping H selects existing Header source records. Merge Files joins eligible files per email recipient, removes repeated heading lines if Include Header Row is true, and names the attachment `<base>_merged.csv`. Download files remain separate. [backend/app/retirement_results.py:538](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:538), [backend/app/retirement_results.py:563](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:563), [backend/app/report_mail.py:78](/Users/apple/Desktop/ECS/backend/app/report_mail.py:78).

## 10. Email eligibility and counts

Recipients are lowercased for matching/deduplication. Each recipient accumulates subscribed `(company,id)` or `(client,id)` pairs. A file is eligible only when **all** of its company/client IDs are covered by that recipient's subscriptions: `required <= subscribed`. One file containing 101 and 102 is not sent to someone subscribed only to 101. Unknown file identities prevent eligibility. Client 101 and company 101 are separate namespaces. [backend/app/report_mail.py:40](/Users/apple/Desktop/ECS/backend/app/report_mail.py:40).

`matched` counts recipient addresses with eligible files; `accepted` counts messages accepted by SMTP without the handled error. It does not count files, rows or delivered inboxes. Mail disabled →no SMTP. Manual CSV-body override skips email; saved-source manual and scheduled reports can email after report commit. [backend/app/report_mail.py:69](/Users/apple/Desktop/ECS/backend/app/report_mail.py:69), [backend/app/report_mail.py:108](/Users/apple/Desktop/ECS/backend/app/report_mail.py:108), [backend/app/routers/retirement_builder.py:1228](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1228).

## 11. Schedule calculations and default assumptions

| Rule | Exact implementation |
|---|---|
| 24-hour time | `int(hour)%12 + (12 if PM else 0)` |
| Week index | Stored Sunday=0…Saturday=6; Python weekday converted `(stored-1)%7` |
| Eligible start | Candidate day must be >=saved start date; null startDateTime means no slot |
| Daily | Every eligible day at chosen time |
| Weekly | Candidate weekday must equal selected weekday |
| Bi-Weekly | first selected day = start + `(selected-start.weekday())%7`; eligible if days since first selected day modulo14=0 |
| Monthly | Eligible day = min(saved monthly date if valid, otherwise start.day, days in candidate month), implemented as min(month_day,monthrange(...)[1]) |
| Grace window | 0<=nowUTC−slotUTC<5 minutes; checks today and yesterday to cover midnight |
| DST | Candidate rejected if UTC roundtrip changes local wall time; broader ambiguous-time behavior NOT VERIFIED by this investigation |
| Polling | Scheduler checks every30s, immediate first check, max_instances1, coalesce true |

Evidence: [backend/app/routers/retirement_builder.py:459](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:459), [backend/app/routers/retirement_builder.py:467](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:467), [backend/app/report_scheduler.py:26](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:26), [backend/app/report_scheduler.py:110](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:110). Timezone is `scheduler_timezone`, default UTC; the user's browser timezone does not automatically choose it. Actual running service's timezone/enabled setting was not inspected, so deployed scheduler configuration is **NOT VERIFIED**. [backend/app/core/config.py:27](/Users/apple/Desktop/ECS/backend/app/core/config.py:27).

A start date 2026-11-11 (Wednesday) with Bi-Weekly Sunday first qualifies on 2026-11-15, then 2026-11-29. An existing passing test covers a Sunday 23:58 slot observed Monday 00:01 in Asia/Kolkata and rejects the middle week. This proves the function under those test inputs, not a live scheduled execution. [backend/tests/test_report_scheduler.py:16](/Users/apple/Desktop/ECS/backend/tests/test_report_scheduler.py:16).

## 12. Counts and limits

| Quantity | Rule / consequence |
|---|---|
| rowCount | Number of mapped H/D/T output records across generated files; output heading not counted |
| storedRows | Same records if Store Results true, else0; includes H and T; JSON stores formatted output values |
| Source bytes | 5×1024×1024 limit in API/file/payroll paths |
| Source rows | Up to10,000; blank physical lines still affect loop counter |
| Columns | Up to100 input headings and100 output columns per record type; unique case-insensitive output fields within each layout |
| Output size | 10×1024×1024 bytes across files; both character-position and final UTF-8 length checks |
| Position/length | Whole0–2147483647 on save; LA/RA length≤1000 on run |
| Email addresses | Individual length≤254, local part≤64; aggregate combined row email text≤255 on save |
| Date input | Schedule SQL datetime minimum1753; manual date input allows0001; payroll uses date/datetime source; actual boundary live execution NOT VERIFIED |

Evidence: [backend/app/retirement_results.py:23](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:23), [backend/app/retirement_results.py:375](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:375), [backend/app/retirement_results.py:538](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:538), [backend/app/retirement_results.py:582](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:582), [backend/app/routers/retirement_builder.py:521](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:521), [frontend/src/App.tsx:790](/Users/apple/Desktop/ECS/frontend/src/App.tsx:790).

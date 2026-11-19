# Questions you may be asked

Answers describe the actual implementation, using simple English. **NOT VERIFIED** means no direct evidence was collected for that claim. The [README](README.md) explains which layers were tested.

## 1. What is this feature in one sentence?

It saves reusable report jobs and separately runs mapped payroll/CSV exports.

Evidence: [frontend/src/App.tsx:449](/Users/apple/Desktop/ECS/frontend/src/App.tsx:449).

## 2. Is this a pension or investment calculator?

No such inputs/formulas appear in this feature; current payroll summaries count joined rows and sum existing net salary.

Evidence: [backend/app/payroll_source.py:27](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:27).

## 3. Who is the intended user?

Actual role names are NOT VERIFIED. Operations/payroll users are a reasonable product-intent inference, not a code-enforced role.

Evidence: [frontend/src/main.tsx:9](/Users/apple/Desktop/ECS/frontend/src/main.tsx:9).

## 4. How many screens are there?

Five core screens, two dialogs, plus adjacent Login. Add/Edit reuse the same four step components.

Evidence: [frontend/src/App.tsx:85](/Users/apple/Desktop/ECS/frontend/src/App.tsx:85).

## 5. Does Next save to the database?

No. It validates/navigation-updates the draft. Finish does POST/PUT.

Evidence: [frontend/src/App.tsx:357](/Users/apple/Desktop/ECS/frontend/src/App.tsx:357).

## 6. Why does my unfinished form survive refresh?

The wizard copies its draft into same-tab sessionStorage; refresh restores it.

Evidence: [frontend/src/App.tsx:344](/Users/apple/Desktop/ECS/frontend/src/App.tsx:344).

## 7. Can another device recover that draft?

There is no server draft/cross-device mechanism in this code.

Evidence: [frontend/src/App.tsx:222](/Users/apple/Desktop/ECS/frontend/src/App.tsx:222).

## 8. What does the Excel file on General do?

It reads the first worksheet locally and replaces mapping definitions. It does not upload payroll data.

Evidence: [frontend/src/retirementBuilder.ts:84](/Users/apple/Desktop/ECS/frontend/src/retirementBuilder.ts:84).

## 9. Where does Template download come from?

Static frontend public/mapped_payroll_columns_HDT.xlsx. No feature REST endpoint.

Evidence: [frontend/src/App.tsx:692](/Users/apple/Desktop/ECS/frontend/src/App.tsx:692).

## 10. Where does new job data come from?

New UI jobs default to companyPayroll, calling the saved payroll procedure at run time.

Evidence: [frontend/src/App.tsx:84](/Users/apple/Desktop/ECS/frontend/src/App.tsx:84).

## 11. How do I choose CSV versus payroll in the UI?

There is no source selector. Existing source inferred from saved query configuration chooses the code path.

Evidence: [backend/app/routers/retirement_builder.py:735](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:735).

## 12. Where do File Format options come from?

GET options queries dbo.rjob_file_typ; filetyp labels map to stored delimiters.

Evidence: [backend/app/routers/retirement_builder.py:329](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:329).

## 13. Does the Output File Name Format dropdown read rjobformat?

No. It reads options.xml. Similar database rows exist but do not supply this dropdown.

Evidence: [backend/app/routers/retirement_builder.py:367](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:367).

## 14. Why is Format empty except No format?

The current rjobformat rows have output-name categories; none qualify as mapping-format types. Source supports formats, live catalog does not populate them.

Evidence: [backend/app/routers/retirement_builder.py:377](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:377).

## 15. Does Mapping Column mean that the payroll SP supplies that field?

No. It shows the full35-item catalog. Payroll supplies five fields; other mappings need defaults.

Evidence: [backend/app/payroll_source.py:132](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:132).

## 16. What does blank Mapping Column mean?

Use the Field Name as the source lookup key, after alias resolution.

Evidence: [backend/app/retirement_results.py:179](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:179).

## 17. What does Default Value do?

It fills an empty/missing mapped value. It does not override an existing nonempty source.

Evidence: [backend/app/retirement_results.py:550](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:550).

## 18. What is Add Dataset?

It appends one mapping row. Save always sets DataSetNo=1.

Evidence: [frontend/src/App.tsx:512](/Users/apple/Desktop/ECS/frontend/src/App.tsx:512).

## 19. Are Start Position and Length building fixed-width files?

No. Start Position is stored metadata; Length only affects explicit LA/RA padding. Renderer always writes delimited output.

Evidence: [backend/app/retirement_results.py:538](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:538).

## 20. Is Include Header Row the same as Record Type Header?

No. Checkbox writes output field names. Header type maps actual H source records.

Evidence: [backend/app/retirement_results.py:544](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:544).

## 21. What happens if Record Type is blank?

Backend treats it as Detail/D.

Evidence: [backend/app/routers/retirement_builder.py:834](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:834).

## 22. Can I run without a schedule?

Yes. Leave schedule completely blank; stored startDateTime is null.

Evidence: [frontend/src/App.tsx:273](/Users/apple/Desktop/ECS/frontend/src/App.tsx:273).

## 23. Why did setting Daily and a time not schedule my job?

A start date is also needed for non-null startDateTime; the frontend lets the date stay blank.

Evidence: [backend/app/routers/retirement_builder.py:467](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:467).

## 24. What is monthly run day?

No separate input exists. Scheduler uses start day and clamps to month end.

Evidence: [backend/app/report_scheduler.py:33](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:33).

## 25. Which timezone governs scheduled reports?

Configured scheduler_timezone, default UTC. Running service setting is NOT VERIFIED; browser timezone is not automatically used.

Evidence: [backend/app/core/config.py:27](/Users/apple/Desktop/ECS/backend/app/core/config.py:27).

## 26. Does a missed scheduled job always catch up later?

No. Current slot check accepts only a five-minute window.

Evidence: [backend/app/report_scheduler.py:45](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:45).

## 27. Why are disabled jobs absent?

Query42 filters isEnabled=1. There is no disabled-record dashboard toggle.

Evidence: [backend/query.brl:693](/Users/apple/Desktop/ECS/backend/query.brl:693).

## 28. Does unchecking Store Results delete old rows?

No. It skips optional result inserts on future runs.

Evidence: [backend/app/routers/retirement_builder.py:1154](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1154).

## 29. Does Merge Files combine downloaded reports?

No. It combines eligible email attachments per recipient when there is more than one.

Evidence: [backend/app/report_mail.py:78](/Users/apple/Desktop/ECS/backend/app/report_mail.py:78).

## 30. Why did a subscriber get no file?

A recipient must be subscribed to every identity contained in that file; mail must also be enabled, valid and accepted.

Evidence: [backend/app/report_mail.py:40](/Users/apple/Desktop/ECS/backend/app/report_mail.py:40).

## 31. Can I leave email blank?

Yes. A selected company/client with blank email is accepted; it simply supplies no recipient address.

Evidence: [backend/app/routers/retirement_builder.py:550](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:550).

## 32. What if the Clients API fails?

Live endpoint returned503. CSV client dropdown code permits custom positive ID entry; payroll uses companies from options instead.

Evidence: [frontend/src/App.tsx:1075](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1075).

## 33. Is login secure server authentication?

The local login gate checks constants in the frontend and sets session flags; feature handlers do not attach authentication dependencies. Production auth/roles are NOT VERIFIED.

Evidence: [frontend/src/LoginPage.tsx:20](/Users/apple/Desktop/ECS/frontend/src/LoginPage.tsx:20).

## 34. What is the exact payroll SP?

dbo.usp_CompanyPayrollReport, verified against installed definition and migration012. It calls system sys.sp_executesql internally.

Evidence: [backend/migrations/012_payroll_report_date_range.sql:1](/Users/apple/Desktop/ECS/backend/migrations/012_payroll_report_date_range.sql:1).

## 35. What inputs does the SP receive?

Saved jobID and run start/end dates.1900-01-01 means an open side.

Evidence: [backend/app/payroll_source.py:198](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:198).

## 36. Where does Pay Date actually come from?

payroll.payroll_month, aliased Pay Date. It is not payroll.pay_date in this report.

Evidence: [backend/config/payroll_record_queries.json:3](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:3).

## 37. Does Employee Count count distinct employees?

No. SQL uses COUNT(*) over joined payroll rows per company_name/payroll_month.

Evidence: [backend/config/payroll_record_queries.json:3](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:3).

## 38. Is Trailer a grand total?

Current payroll T query repeats the same company/month aggregate as D. It is not a global total recalculated after filtering.

Evidence: [backend/config/payroll_record_queries.json:4](/Users/apple/Desktop/ECS/backend/config/payroll_record_queries.json:4).

## 39. Are filters applied to employees before payroll totals?

No. SQL aggregates first; Python filters Detail summary rows afterward.

Evidence: [backend/app/retirement_results.py:474](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:474).

## 40. Can conditions compare ordinary text?

The modal expects date/numeric thresholds; Python uses date/Decimal comparisons. General string equality is not implemented.

Evidence: [frontend/src/App.tsx:1171](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1171).

## 41. How are decimals rounded?

Thresholds round to2 places; output numeric formats use their selected places. Both use Decimal ROUND_HALF_UP.

Evidence: [backend/app/routers/retirement_builder.py:500](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:500).

## 42. What is stored in rjob_result?

Formatted output values as JSON, H/D/T type, row number, jobID and runUUID; not the output column-heading line.

Evidence: [backend/app/retirement_results.py:582](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:582).

## 43. Does Finish execute the saved SQL?

It saves configuration and template texts. Payroll SELECTs execute on Run or scheduler.

Evidence: [backend/app/routers/retirement_builder.py:873](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:873).

## 44. Does edit simply patch each child record?

No. It merges omitted payload fields, updates the parent, deletes six child sets and rewrites them transactionally.

Evidence: [backend/app/routers/retirement_builder.py:1058](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1058).

## 45. Are duplicate creates impossible?

The client guard/key and process-local server cache reduce retries; restart/expiry/multiworker limits remain.

Evidence: [backend/app/routers/retirement_builder.py:1003](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1003).

## 46. Are duplicate runs prevented?

They are serialized with a row lock; two manual requests can still run twice. Scheduler separately skips completed slot outputs.

Evidence: [backend/app/routers/retirement_builder.py:1199](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1199).

## 47. Does accepted email mean delivered?

It only means the mail call was accepted without the handled error. Inbox delivery is NOT VERIFIED.

Evidence: [backend/app/report_mail.py:108](/Users/apple/Desktop/ECS/backend/app/report_mail.py:108).

## 48. What survives dashboard refresh?

Jobs reload; run download Blob URLs/results disappear. Server files and optional result rows persist independently.

Evidence: [frontend/src/App.tsx:670](/Users/apple/Desktop/ECS/frontend/src/App.tsx:670).

## 49. Why might Last Run change after editing?

Query45 sets joblastrun=GETDATE even on edit; backend only suppresses it when no history status exists.

Evidence: [backend/query.brl:765](/Users/apple/Desktop/ECS/backend/query.brl:765).

## 50. Does dashboard history show every run?

No. It displays joined summary/history fields; query42 joins only the globally latest history_detail row, not latest for each job.

Evidence: [backend/query.brl:693](/Users/apple/Desktop/ECS/backend/query.brl:693).

## 51. How many APIs and SQL units are traced?

Seven HTTP operations;32 SQL definitions/templates by documented source-unit convention;1 application SP plus its system helper.

Evidence: [backend/app/routers/retirement_builder.py:218](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:218).

## 52. What was really tested?

54 backend tests,9 frontend utility tests, SELECT-only metadata/HTTP checks, and unsaved browser navigation. Live saves/runs/SMTP were intentionally not tested.

Evidence: [backend/tests/test_retirement_builder.py:30](/Users/apple/Desktop/ECS/backend/tests/test_retirement_builder.py:30).

## 53. How can I confirm the failed upstream client table?

In an authorized read-only connection, check metadata/permissions for prism.export.Client_Details and rerun query43; do not infer the exact SQL failure from503 alone.

Evidence: [backend/query.brl:743](/Users/apple/Desktop/ECS/backend/query.brl:743).

## 54. How can I verify provider-specific retirement rules?

Ask the product owner for required provider schema, field definitions and acceptance criteria, then trace each requirement to mappings and tests. The source alone does not establish that intent.

Evidence: [frontend/src/App.tsx:1000](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1000).

## Traceability examples for discussions

| Finding | Frontend function/file | API | Backend function/file | SQL/SP | Table | Simple explanation |
|---|---|---|---|---|---|---|
| File Format | GeneralStep [frontend/src/App.tsx:850](/Users/apple/Desktop/ECS/frontend/src/App.tsx:850) | GET options | _file_formats [backend/app/routers/retirement_builder.py:329](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:329) | query32 [backend/query.brl:482](/Users/apple/Desktop/ECS/backend/query.brl:482) | dbo.rjob_file_typ | Name shown; delimiter stored |
| Employee Count Mapping Column | MappingStep [frontend/src/App.tsx:1033](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1033) | GET options; POST/PUT jobs | _mapping_catalog/_write_job_details [backend/app/routers/retirement_builder.py:307](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:307), [backend/app/routers/retirement_builder.py:828](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:828) | query30/query35 | dbo.rjob_mapping_column / rjob_file_detail | Label becomes saved key |
| Payroll Company | SubscriptionsStep [frontend/src/App.tsx:1106](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1106) | GET options | payroll_company_ids [backend/app/payroll_source.py:44](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:44) | READ_PAYROLL_COMPANY_IDS | dbo.companies | Unique name resolves positive ID |
| CSV Clients | SubscriptionsStep [frontend/src/App.tsx:1115](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1115) | GET clients | list_retirement_builder_clients [backend/app/routers/retirement_builder.py:936](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:936) | query43 [backend/query.brl:743](/Users/apple/Desktop/ECS/backend/query.brl:743) | prism.export.Client_Details | Live503; exact upstream cause NOT VERIFIED |
| Store Results checkbox | GeneralStep [frontend/src/App.tsx:875](/Users/apple/Desktop/ECS/frontend/src/App.tsx:875) | POST/PUT jobs then POST run | _execute_report_run [backend/app/routers/retirement_builder.py:1154](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1154) | INSERT_RESULT | dbo.rjob / dbo.rjob_result | Save flag now; insert generated records on future run |
| Run date range | RunDateDialog [frontend/src/App.tsx:752](/Users/apple/Desktop/ECS/frontend/src/App.tsx:752) | POST run?start_date&end_date | load_payroll_source [backend/app/payroll_source.py:198](/Users/apple/Desktop/ECS/backend/app/payroll_source.py:198) | dbo.usp_CompanyPayrollReport | rjob_query/companies/employees/payroll | Bound dates filter payroll-month summaries |
| Output name choices | GeneralStep [frontend/src/App.tsx:858](/Users/apple/Desktop/ECS/frontend/src/App.tsx:858) | GET options | _output_file_name_formats [backend/app/routers/retirement_builder.py:367](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:367) | No SQL/SP for dropdown | No table; options.xml | Configured code controls grouping/name |
| Merge Files | SubscriptionsStep [frontend/src/App.tsx:1096](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1096) | POST/PUT jobs; POST run | send_subscribed_reports [backend/app/report_mail.py:78](/Users/apple/Desktop/ECS/backend/app/report_mail.py:78) | Parent ismerge write; no merge SP | dbo.rjob | Recipient's attachments merge in Python |

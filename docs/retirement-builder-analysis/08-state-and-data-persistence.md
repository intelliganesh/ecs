# State, saving and editing

## Where values live

| Layer | Actual mechanism | Lifetime / use | Evidence |
|---|---|---|---|
| Authentication UI | RootRoutes useState + sessionStorage flags `ecs-demo-authenticated`, `ecs-demo-user` | Browser session; demo route gate; no backend auth request | [frontend/src/main.tsx:9](/Users/apple/Desktop/ECS/frontend/src/main.tsx:9) |
| Wizard | App useState for General, Schedule, mapping rows, fileSettings, subscribers | Shared parent persists across four routes | [frontend/src/App.tsx:249](/Users/apple/Desktop/ECS/frontend/src/App.tsx:249) |
| Dropdown metadata | OptionsContext created with emptyOptions, provided from App | In-memory across wizard steps; refetch entering wizard/refresh | [frontend/src/App.tsx:48](/Users/apple/Desktop/ECS/frontend/src/App.tsx:48), [frontend/src/App.tsx:300](/Users/apple/Desktop/ECS/frontend/src/App.tsx:300) |
| Draft | sessionStorage `ecs-retirement-builder-draft` serialized Draft | Same-tab refresh restoration; removed outside wizard | [frontend/src/App.tsx:222](/Users/apple/Desktop/ECS/frontend/src/App.tsx:222), [frontend/src/App.tsx:344](/Users/apple/Desktop/ECS/frontend/src/App.tsx:344) |
| Create retries | Ref + sessionStorage `ecs-retirement-builder-create-attempt` | Fingerprint/key reuse for identical failed/uncertain POST | [frontend/src/App.tsx:241](/Users/apple/Desktop/ECS/frontend/src/App.tsx:241), [frontend/src/App.tsx:485](/Users/apple/Desktop/ECS/frontend/src/App.tsx:485) |
| Dashboard | App jobs/filters; Dashboard sort/page/selectedJobs/runResult/downloads | Local component state; Dashboard unmount discards inner state; filters stay in App until full refresh | [frontend/src/App.tsx:261](/Users/apple/Desktop/ECS/frontend/src/App.tsx:261), [frontend/src/App.tsx:581](/Users/apple/Desktop/ECS/frontend/src/App.tsx:581) |
| SearchableSelect | Internal open/query/activeIndex/value (when uncontrolled) | Menu lifetime; most selects controlled by parent | [frontend/src/App.tsx:90](/Users/apple/Desktop/ECS/frontend/src/App.tsx:90) |
| EmailTagsInput | Parent email/emailDraft; local attempted flag/ref | Draft addresses included at Finish; tags commit on delimiters/blur | [frontend/src/App.tsx:159](/Users/apple/Desktop/ECS/frontend/src/App.tsx:159) |
| File Settings | Modal useState copied from initialSorting/initialConditional | Saved to App only by Save & Continue; cancel loses edits | [frontend/src/App.tsx:1155](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1155), [frontend/src/App.tsx:1181](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1181) |
| Run dates | Native form's uncontrolled date values read by FormData | Lost on close/refresh; only passed to Run | [frontend/src/App.tsx:765](/Users/apple/Desktop/ECS/frontend/src/App.tsx:765) |
| Database | SQL Server parent/detail/history/results tables | Persists independently of browser | [backend/app/routers/retirement_builder.py:965](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:965), [backend/app/routers/retirement_builder.py:1099](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1099) |
| Report files | Atomic temp-write + os.replace into report-output directories | Manual run UUID directory; scheduled time-slot directory | [backend/app/report_files.py:10](/Users/apple/Desktop/ECS/backend/app/report_files.py:10), [backend/app/routers/retirement_builder.py:1133](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1133), [backend/app/report_scheduler.py:63](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:63) |

No Redux, Zustand, React Hook Form, React Query, SWR or localStorage is used in the traced feature. React useState, useContext, effects, memoization and refs are the actual tools. `xlsx` parses imported workbooks and produces local Excel downloads. [frontend/src/App.tsx:1](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1), [frontend/src/retirementBuilder.ts:1](/Users/apple/Desktop/ECS/frontend/src/retirementBuilder.ts:1), [frontend/package.json:1](/Users/apple/Desktop/ECS/frontend/package.json:1).

## Default state differences that matter

| Property | New UI | Backend model / existing load |
|---|---|---|
| reportSource | companyPayroll | GeneralForm default csv; loaded existing source inferred from saved query rows |
| enable | true, hidden in Add | Backend true; Edit uses saved value |
| includeHeader | false | MappingForm default true; load falls back true if missing |
| storeResultsToTable | false | Backend false |
| mergeFiles | false | Backend false |
| schedule | All six strings blank | Pydantic weekly4:00AMThursday with startDate null; an existing null-start job loads all blank |
| mappings/subscribers/rules | Empty arrays | Reconstructed from SQL; local UI IDs regenerated |
| fileName/fileFormat/outputName/description | Blank | Saved name-format blank normalizes to FILENAME |

Evidence: [frontend/src/App.tsx:79](/Users/apple/Desktop/ECS/frontend/src/App.tsx:79), [frontend/src/App.tsx:256](/Users/apple/Desktop/ECS/frontend/src/App.tsx:256), [frontend/src/App.tsx:405](/Users/apple/Desktop/ECS/frontend/src/App.tsx:405), [frontend/src/App.tsx:406](/Users/apple/Desktop/ECS/frontend/src/App.tsx:406), [backend/app/routers/retirement_builder.py:44](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:44), [backend/app/routers/retirement_builder.py:56](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:56), [backend/app/routers/retirement_builder.py:83](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:83). Backend defaults are not the visible new-form defaults.

## Re-renders and data movement

Input onChange calls setters or parent callbacks; replacing a state value rerenders the relevant React subtree. Mapping edits use row IDs to patch the right row; subscription edits do the same. Derived validation recalculates in App. `useMemo` recalculates transformed jobs/sorted filtered jobs when dependencies change; memoization does not save data. Search dropdown state changes rerender that select. There is no calculate-everything effect or debounced save service. [frontend/src/App.tsx:270](/Users/apple/Desktop/ECS/frontend/src/App.tsx:270), [frontend/src/App.tsx:299](/Users/apple/Desktop/ECS/frontend/src/App.tsx:299), [frontend/src/App.tsx:511](/Users/apple/Desktop/ECS/frontend/src/App.tsx:511), [frontend/src/App.tsx:554](/Users/apple/Desktop/ECS/frontend/src/App.tsx:554), [frontend/src/App.tsx:596](/Users/apple/Desktop/ECS/frontend/src/App.tsx:596).

Navigation swaps step components while App keeps the common values. `navigate` validates preceding steps by target index. Backward movement does not clear later data. Changing source labels can invalidate/clear only the mapping format under the source-type rule; other earlier edits do not generally reset schedules, subscriptions or settings. This can leave stale rules pointing to an old field, caught only by later validation/run. [frontend/src/App.tsx:357](/Users/apple/Desktop/ECS/frontend/src/App.tsx:357), [frontend/src/App.tsx:1010](/Users/apple/Desktop/ECS/frontend/src/App.tsx:1010).

## Draft persistence and refresh

`readDraft(mode)` parses sessionStorage and only accepts a matching Add/Edit mode; Edit must have numeric jobId. It restores local rowSequence to at least the largest stored mapping/subscription ID. Initial draft is read only on initial App mount on a wizard route, not each Next click. A mismatched explicitly requested Edit job discards that initial draft. [frontend/src/App.tsx:224](/Users/apple/Desktop/ECS/frontend/src/App.tsx:224), [frontend/src/App.tsx:250](/Users/apple/Desktop/ECS/frontend/src/App.tsx:250).

The draft effect stores General, source, schedule, storedStartDateTime, mapping rows, checkboxes, subscription emails/draft emails, fileSettings, mode and jobId after relevant changes. It is client-side automatic draft retention, **not automatic database saving**. It catches storage failures silently. Refresh loses validation-attempt flags, modal temporary edits and in-progress run output; it reloads dropdown options. Invalid JSON produces no restored draft. Opening Edit without a requested ID or a suitable saved job ID returns to Dashboard. [frontend/src/App.tsx:263](/Users/apple/Desktop/ECS/frontend/src/App.tsx:263), [frontend/src/App.tsx:340](/Users/apple/Desktop/ECS/frontend/src/App.tsx:340).

The route itself supplies the current step; Draft has no step field. After refreshing Subscriptions in the browser, navigating Back showed the entered Employee Count mapping, confirming same-tab draft recovery in this investigation. SessionStorage does not guarantee recovery after a browser session closes; no cross-device or server draft exists in this code. No beforeunload warning is registered. [frontend/src/App.tsx:223](/Users/apple/Desktop/ECS/frontend/src/App.tsx:223), [verification notes](evidence/verification.md).

Cancel navigates out and removes the stored draft. App memory may still contain values until reset, and browser Back can reenter with that memory if App did not unmount. After full reload outside the wizard, the draft is gone. Cancel is not database rollback because no server save has occurred yet. [frontend/src/App.tsx:344](/Users/apple/Desktop/ECS/frontend/src/App.tsx:344), [frontend/src/App.tsx:405](/Users/apple/Desktop/ECS/frontend/src/App.tsx:405).

## Frontend properties to database parameters

| UI state | JSON on Finish | Parameter / final destination |
|---|---|---|
| fileName | general.fileName | @jobfilename→rjob.jobfilename; @jobName→schedule.jobName |
| fileFormat | general.fileFormat (display/configured name) | Lookup delimiter→@filetype→rjob.filetype |
| description | general.description | @jobdesc→rjob.jobdesc |
| outputFileNameFormat | general.outputFileNameFormat | normalized code→@fileNameFormat→rjob.FileNameFormat |
| enable | general.enable | @isEnabled→rjob.isEnabled |
| storeResultsToTable | general.storeResultsToTable | @StoreResult→rjob.StoreResults |
| reportSource | general.reportSource | Not a dedicated parent column; payroll generates marked H/D/T query rows in rjob_query; read infers source |
| selectedFile | Omitted by UI | Workbook filename retained only in draft; no persisted upload/blob |
| schedule | startDate null when manual; otherwise all fields with blank date→null | @startDateTime, frequency fields, weekday integer, hour/minute/session→rjob_schedule_info |
| includeHeader | mapping.includeHeader | @includeHRecord→rjob.includeHeader |
| row.field | mapping.rows[].field | @jobclientcolumn→rjob_file_detail.jobclientcolumn |
| row.mapping | mapping.rows[].mappingColumn | Display/key resolution→@jobfieldmapping→jobfieldmapping |
| row.defaultValue | mapping.rows[].defaultValue | @jobdefaultvalue→jobdefaultvalue |
| row.recordType | mapping.rows[].recordType | H/D/T normalization→@jobrectype→jobrectype |
| row.format | mapping.rows[].format | @jobformat→jobformat |
| row.startPosition / length | Strings, blanks replaced0 | Integers→@startposition/@field_len→startposition/field_len |
| Mapping row order | Array order | datasetNo always1; colSeqNo=index+1 |
| mergeFiles | subscriptions.mergeFiles | @ismerge→rjob.ismerge |
| client/companyId | per row; exactly one namespace | Positive ID→@jobclientid→rjob_client_detail.jobclientid |
| email/emailDraft | combined validated deduplicated emails | @jobemailind→rjob_client_detail.jobemailind; aggregate @mergeemail→rjob.mergeemail |
| sortingOrder | fileSettings.sortingOrder | Positive sequential priority→sort table; direction/column ORDER BY text→rjob_query.Sort_Order |
| conditionalStatements | fileSettings.conditionalStatements | Rounded numeric/date-encoded fields→condition table; payroll D clause→rjob_query.Conditions |
| Local row IDs | Omitted | UI-only sequence; no mapping/subscription identity round trip |
| queryConfiguration | Not sent by UI | Backend generates payroll rows or retains original API/legacy rows on PUT |

Evidence: frontend serialization [frontend/src/App.tsx:468](/Users/apple/Desktop/ECS/frontend/src/App.tsx:468), parent save [backend/app/routers/retirement_builder.py:975](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:975), update [backend/app/routers/retirement_builder.py:1072](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1072), child writes [backend/app/routers/retirement_builder.py:822](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:822), source inference [backend/app/routers/retirement_builder.py:735](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:735).

## Existing records and IDs

Dashboard Edit sets requested jobId in router navigation state, clears selectedJobId, then fetches detail. `loadJob` rebuilds fields and gives every mapping/subscription a new local row ID. Successful save retains the same SQL job ID for PUT. New POST obtains `SCOPE_IDENTITY`; that ID is then reused for all child inserts in the same transaction. IDs are not generated from file names. [frontend/src/App.tsx:442](/Users/apple/Desktop/ECS/frontend/src/App.tsx:442), [frontend/src/App.tsx:406](/Users/apple/Desktop/ECS/frontend/src/App.tsx:406), [frontend/src/App.tsx:72](/Users/apple/Desktop/ECS/frontend/src/App.tsx:72), [backend/app/routers/retirement_builder.py:580](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:580), [backend/query.brl:529](/Users/apple/Desktop/ECS/backend/query.brl:529).

Edit GET uses one batch with eight result sets, consumes even empty sets in order and builds the nested model. Run/create/update rereads use separate SELECTs. Missing fields in partial API updates are copied from the original before rewriting, but the frontend normally sends all visible sections. User-supplied values are validated before that merge. There is no version/ETag conflict check, so simultaneous editors can overwrite each other's configuration. [backend/app/routers/retirement_builder.py:705](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:705), [backend/app/routers/retirement_builder.py:810](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:810), [backend/app/routers/retirement_builder.py:1058](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1058).

`storedStartDateTime` is frontend state and is expected by its help text, but `ScheduleForm` has no startDateTime field and the observed GET lacks it. Entering Schedule can therefore cause an extra metadata-restoration GET that only resolves it to null. Do not promise the stored datetime hint is available from this API. [frontend/src/App.tsx:297](/Users/apple/Desktop/ECS/frontend/src/App.tsx:297), [frontend/src/App.tsx:427](/Users/apple/Desktop/ECS/frontend/src/App.tsx:427), [backend/app/routers/retirement_builder.py:56](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:56), [HTTP evidence](evidence/read-only-http.json).

## Duplicate submissions, transactions and output persistence

- `savingRef.current` blocks overlapping Finish calls synchronously; `saving` disables Finish. Other navigation is not generally locked during the request. POST retries reuse a key for matching payload. [frontend/src/App.tsx:449](/Users/apple/Desktop/ECS/frontend/src/App.tsx:449), [frontend/src/App.tsx:479](/Users/apple/Desktop/ECS/frontend/src/App.tsx:479).
- Server create cache is in-process, one-hour TTL, maximum1,024 completed keys, plus pending Futures and a lock. Different body under same key→409; failed create is not cached. This is not durable/multiworker idempotency. [backend/app/routers/retirement_builder.py:198](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:198), [backend/app/routers/retirement_builder.py:1003](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1003).
- PUT transaction updates parent, deletes child sets by ID, rewrites them, and rereads. SQL exceptions normally roll back all those writes. Existing report history/results remain. No deletion is performed by browser Back/Cancel. [backend/app/routers/retirement_builder.py:1058](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1058), [backend/query.brl:755](/Users/apple/Desktop/ECS/backend/query.brl:755).
- Run locks the job and uses a savepoint for report generation/storage. Handled errors roll back attempted result writes, remove newly published report files through context cleanup, then record failure outside the savepoint. SQL failure in history recording can still cause outer rollback. This is application cleanup around transactions, not a single atomic transaction encompassing SQL, disk and SMTP. [backend/app/routers/retirement_builder.py:1164](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1164), [backend/app/report_files.py:10](/Users/apple/Desktop/ECS/backend/app/report_files.py:10).
- Successful saved-source manual run sends email after database transaction exit; SMTP problems do not undo report rows/files. API CSV override skips email. [backend/app/routers/retirement_builder.py:1199](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1199), [backend/app/routers/retirement_builder.py:1228](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1228).
- Manual files use report-output/manual/jobID/runUUID; scheduled files use scheduled/jobID/UTCslot. Scheduler completion is detected by existing CSV or .complete marker, not a durable queue record. Two manual requests are serialized, not deduplicated. Crash recovery across database/files/mail is **NOT VERIFIED**. [backend/app/report_scheduler.py:62](/Users/apple/Desktop/ECS/backend/app/report_scheduler.py:62), [backend/app/routers/retirement_builder.py:1133](/Users/apple/Desktop/ECS/backend/app/routers/retirement_builder.py:1133).
- `rjob_result` stores formatted output JSON per run UUID and1-based row number, with H/D/T. The feature exposes no result-history browse API; dashboard run downloads are in-memory Blob URLs and disappear when that component/result is lost. [backend/app/retirement_results.py:582](/Users/apple/Desktop/ECS/backend/app/retirement_results.py:582), [backend/migrations/001_retirement_builder_results.sql:3](/Users/apple/Desktop/ECS/backend/migrations/001_retirement_builder_results.sql:3), [frontend/src/App.tsx:670](/Users/apple/Desktop/ECS/frontend/src/App.tsx:670).

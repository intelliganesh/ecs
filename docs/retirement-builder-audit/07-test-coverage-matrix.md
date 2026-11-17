# Phase 2 test coverage plan

This matrix tracks 171 scenarios across all 95 numbered features. The status column reflects the [Phase 2 test execution report](phase-2/01-test-execution-report.md). Where a row names input variants, it remains one parameterized scenario. Phase 2 used isolated job and payroll fixtures, temporary report paths, a controlled clock and a loopback SMTP sink.

| Test ID | Feature ID | Step | Functionality to Test | Test Scenario | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- |
| RET-T001 | RET-F001 | Entry | Sign-in route guard | Open a protected route without the demo session; confirm redirect, sign-in and dashboard landing. | High | PASS |
| RET-T002 | RET-F002 | Entry | Demo credentials and error | Submit accepted demo inputs, blank email/password, wrong password and invalid email syntax; verify route and error handling. | High | PASS |
| RET-T003 | RET-F002 | Entry | Demo credentials and error | Use different email case and leading/trailing spaces with the exact password, then case-altered password. | Medium | PASS |
| RET-T004 | RET-F003 | Entry | Password visibility | Toggle password visibility twice and confirm input text, mask and accessible name. | Low | PASS |
| RET-T005 | RET-F004 | Shell | Shell navigation | Use menu toggle, Retirement Builder sidebar button and SYD from wizard and list. | Medium | PASS |
| RET-T006 | RET-F005 | Shell | Responsive layout | Inspect list, wizard, modal and picker at desktop, 767/768, 520 and 430 px widths; verify scroll and no clipped actions. | High | PASS |
| RET-T007 | RET-F005 | Shell | Responsive layout | Open later wizard tabs, mapping grid and modal at small width and zoom with real keyboard; inspect reachable last buttons. | Medium | NOT TESTED |
| RET-T008 | RET-F006 | Dashboard | Enabled job list | Load enabled/manual-only/scheduled fixtures; verify normalized list columns, and disabled fixture invisibility. | High | PASS |
| RET-T009 | RET-F006 | Dashboard | Enabled job list | Verify Job Last Run blank for new/no history, with legacy sentinel date, and retained when manual-only. | High | PASS |
| RET-T010 | RET-F007 | Dashboard | Background list refresh | Observe initial fetch, five-second visible refresh, background pause, resumed updates and cancellation on route change. | Medium | NOT TESTED |
| RET-T011 | RET-F007 | Dashboard | Background list refresh | Simulate polling failure after good data and check retained rows versus initial-error display. | Medium | PASS |
| RET-T012 | RET-F008 | Dashboard | Loading, empty and error rows | Compare slow load, empty dataset, no filtered match, and initial HTTP failure states. | Medium | PASS |
| RET-T013 | RET-F009 | Dashboard | Column filters | Exercise all ten filter inputs individually, then intersection, case, trim and clearing. | High | PASS |
| RET-T014 | RET-F010 | Dashboard | Column sorting | Click each header twice and switch columns; verify asc/desc, numeric-aware text, tie behavior and aria-sort. | Medium | PASS |
| RET-T015 | RET-F010 | Dashboard | Column sorting | Use records whose time strings differ in hour width and AM/PM; compare actual natural-text order with time-of-day semantics. | Medium | FAIL |
| RET-T016 | RET-F011 | Dashboard | Row selection | Select/deselect row and verify transient run result or error is cleared. | Medium | PASS |
| RET-T017 | RET-F012 | Dashboard | Select all visible | Select all visible, apply a narrower filter, deselect visible and compare retained hidden row IDs. | High | PASS |
| RET-T018 | RET-F013 | Dashboard | Edit and Run availability | Compare zero, one and multiple selected; include filtered-out selected row and inspect enabled actions. | High | FAIL |
| RET-T019 | RET-F013 | Dashboard | Edit and Run availability | While running, examine checkbox lock and whether Edit/Add remains available; compare with requests and server job lock. | High | PASS |
| RET-T020 | RET-F014 | Dashboard | Template download | Download Template, verify filename and open an unmodified copy as supported mapping workbook. | Medium | PASS |
| RET-T021 | RET-F015 | Dashboard | Start new job | Open Add after an Edit/canceled draft; confirm required fields blank, flags unchecked and no stale rows or key. | High | PASS |
| RET-T022 | RET-F016 | Dashboard | Open existing job by Edit | Select an enabled job and click Edit; compare all persisted sections with hydrated fields. | High | PASS |
| RET-T023 | RET-F017 | Dashboard | Open existing job by name | Click the file-name cell with no selection and confirm equivalent Edit path. | Medium | PASS |
| RET-T024 | RET-F018 | Dashboard | Job-detail fetch failure | Simulate detail GET 404 and network failure; compare dashboard feedback with developer console-only failure. | High | FAIL |
| RET-T025 | RET-F019 | Dashboard | Manual run request | Run one enabled manual-only job in an isolated fixture and verify one POST, pending UI state then observed result. | Critical | PASS |
| RET-T026 | RET-F020 | Dashboard | Manual run failure feedback | Trigger missing input, malformed source and network failure separately; compare result banner and persisted history. | High | PASS |
| RET-T027 | RET-F021 | Dashboard | Manual run result feedback | Run fixtures with 0, 1 or multiple result files; verify counts, status text and link visibility. | High | PASS |
| RET-T028 | RET-F021 | Dashboard | Manual run result feedback | Compare no-match payroll success (zero files) to no-match ungrouped legacy CSV still rendering a configured file. | High | PASS |
| RET-T029 | RET-F022 | Dashboard | Download generated files | Download single/multiple CSVs, compare bytes to server result and disk, re-run and check old links replaced. | High | PASS |
| RET-T030 | RET-F022 | Dashboard | Download generated files | Reload after a successful run and check whether earlier links remain available. | Medium | PASS |
| RET-T031 | RET-F023 | Wizard | Step tabs and validation | Try jumping from blank General, incomplete Schedule and invalid Mapping to later tabs; confirm first guarded step. | High | PASS |
| RET-T032 | RET-F023 | Wizard | Step tabs and validation | Bypass normal tabs via direct later route with valid General but incomplete earlier fields; verify Finish blocks. | High | PASS |
| RET-T033 | RET-F024 | Wizard | Next and Back navigation | Move Next/Back between all four steps with unsaved inputs and compare values; observe Next disabled during import. | High | NOT TESTED |
| RET-T034 | RET-F025 | Wizard | Cancel and draft reset | Cancel with edited data, enter Add again, confirm reset and inspect whether a warning appears. | High | PASS |
| RET-T035 | RET-F025 | Wizard | Cancel and draft reset | Cancel a modal with unapplied settings, then reopen; compare persisted job rules and wizard draft. | Medium | PASS |
| RET-T036 | RET-F026 | Wizard | Refresh and draft restore | Reload a draft in Add and Edit; check saved form values and that unapplied modal changes are gone. | High | PASS |
| RET-T037 | RET-F026 | Wizard | Refresh and draft restore | Simulate sessionStorage unavailable/malformed and concurrent same-tab flow; verify safe fallback and key restoration. | Medium | NOT TESTED |
| RET-T038 | RET-F027 | Wizard | History and direct route | Use Back/Forward after Cancel and open direct step routes with no, matching and wrong-mode drafts. | High | FAIL |
| RET-T039 | RET-F028 | General | File Name | Enter blank, whitespace-only and regular File Name; inspect field-level UI and API checks. | High | PASS |
| RET-T040 | RET-F028 | General | File Name | Try 255 and 256 characters and Unicode near filename byte limit with significant whitespace and path characters. | High | PASS |
| RET-T041 | RET-F029 | General | File Format | Choose each configured delimiter label and verify shown label, saved byte and rendered file delimiter. | Critical | PASS |
| RET-T042 | RET-F029 | General | File Format | Test legacy CSV/CSV_PIPE/CSV_TAB/CSV_SEMI aliases, unknown labels and unsupported catalog values. | High | PASS |
| RET-T043 | RET-F030 | General | Description | Persist multiline Description and try 300 vs 301 characters. | Medium | PASS |
| RET-T044 | RET-F031 | General | Output File Name Format | Choose blank/new naming codes and open Edit to check code label rehydration. | High | PASS |
| RET-T045 | RET-F031 | General | Output File Name Format | Submit unknown, duplicate-token and reordered valid codes in API fixture; compare fallback and dropdown behavior. | High | PASS |
| RET-T046 | RET-F032 | General | Payroll Client ID help | Choose payroll output formats containing Client ID and change to Payday only; check contextual hint. | Low | PASS |
| RET-T047 | RET-F033 | General Edit | Enable/Disable toggle | Toggle checkbox in Edit, save disabled fixture, confirm disappearance and verify disabled run response using job ID. | High | PASS |
| RET-T048 | RET-F033 | General Edit | Enable/Disable toggle | Check disabled job recovery through normal dashboard and direct API read/update on disposable job. | High | FAIL |
| RET-T049 | RET-F034 | General | Store Results to Table | Run equivalents with storage off/on; confirm the same generated bytes and storedRows 0/N respectively. | High | PASS |
| RET-T050 | RET-F035 | General | Browse and workbook import | Import seven-row workbook, compare field names and H/D/T order with first sheet and verify it replaces the grid. | High | PASS |
| RET-T051 | RET-F035 | General | Browse and workbook import | Import XLS, XLSX, headers-only alternate layout, H/D/T shorthand, duplicate exact/case-variant and blank fields. | High | PASS |
| RET-T052 | RET-F036 | General | Workbook validation and loading | Import unsupported extension, bad signature, and empty first sheet; record distinct messages and unchanged mappings. | High | PASS |
| RET-T053 | RET-F036 | General | Workbook validation and loading | Inspect large workbook and slow parse behavior in an isolated browser. Verify absence or presence of a size error without compromising responsiveness. | Medium | PASS |
| RET-T054 | RET-F037 | General | Import replacement and stale reads | Choose a second workbook before first parse resolves or cancel during import; confirm stale result is ignored. | High | NOT TESTED |
| RET-T055 | RET-F038 | Schedule | Start Date and manual-only mode | Save wholly blank Schedule and reopen; confirm Manual only, null start, blank Edit and manual Run. | High | PASS |
| RET-T056 | RET-F038 | Schedule | Start Date and manual-only mode | Compare 1752-12-31, 1753-01-01, 9999-12-31 and invalid calendar dates via UI/API; retain null case. | High | PASS |
| RET-T057 | RET-F038 | Schedule | Start Date and manual-only mode | Enter frequency/time but omit Start Date; inspect saved Manual only and whether user gets clear feedback. | High | FAIL |
| RET-T058 | RET-F039 | Schedule | Frequency selection | Compare Daily, Weekly, Bi-Weekly and Monthly persistence and options. | High | PASS |
| RET-T059 | RET-F040 | Schedule | Hour, Minute, AM/PM | Exercise hour/minute/meridiem endpoints, including 12:00 AM and 12:00 PM conversion. | High | PASS |
| RET-T060 | RET-F040 | Schedule | Hour, Minute, AM/PM | API boundary fixtures include hours 0, 1, 12, 13 and minutes 0, 59, 60, negatives, fractions and signed plus. | High | PASS |
| RET-T061 | RET-F041 | Schedule | Week selector | With time entered, compare blank Week under weekly variants and Daily/Monthly. | Medium | PASS |
| RET-T062 | RET-F042 | Mapping | Add Dataset and empty state | Add blank mapping row and compare General import, Add row, and Edit row numeric defaults. | High | PASS |
| RET-T063 | RET-F043 | Mapping | Delete mapping row | Delete middle and final mapping row and verify actual array/validation/sequence. | High | PASS |
| RET-T064 | RET-F043 | Mapping | Delete mapping row | Delete then import a replacement, refresh and verify expected row identities and no stale settings. | Medium | PASS |
| RET-T065 | RET-F044 | Mapping | Include Header Row | Run with Include Header Row on/off, keeping actual H layout, and compare file rows vs result counts. | High | PASS |
| RET-T066 | RET-F045 | Mapping | Mapping field identity | Set Field Name that matches source and one sourced via Mapping Column; inspect headings and stored keys. | High | PASS |
| RET-T067 | RET-F045 | Mapping | Mapping field identity | Try blank field, 255/256 characters, duplicate case-varied names in one type, same name across different types and 100/101 mapping columns. | High | PASS |
| RET-T068 | RET-F046 | Mapping | Mapping positions and lengths | Save blanks, 0 and SQL int max in Start Position/Length; check persisted fields and runtime padding independence. | High | PASS |
| RET-T069 | RET-F046 | Mapping | Mapping positions and lengths | Try negative, decimal, nonnumeric and above SQL int for both numeric fields; verify Length 1000/1001 in left-padding run. | High | PASS |
| RET-T070 | RET-F047 | Mapping | Record Type selector | Configure H, D, T and blank record type across CSV and payroll fixtures; verify generated layouts. | High | PASS |
| RET-T071 | RET-F047 | Mapping | Record Type selector | API inject unsupported type to disposable payroll/CSV fixtures; note save vs run validation, blank default and mixed shape. | High | PASS |
| RET-T072 | RET-F048 | Mapping | Mapping fallback value | Use missing/blank source with a provided fallback, then whitespace and numeric zero; compare formatted values. | High | PASS |
| RET-T073 | RET-F048 | Mapping | Mapping fallback value | Test optional defaults with lengths 255/256 and a default that cannot parse under selected Format. | High | PASS |
| RET-T074 | RET-F049 | Mapping | Source column selector | Inspect catalog options for current payroll and legacy CSV, and select Same as Field Name. | High | PASS |
| RET-T075 | RET-F049 | Mapping | Source column selector | Verify option labels derive from DB description/key, dedupe and inferred type; try source with different case. | High | PASS |
| RET-T076 | RET-F050 | Mapping | Field format selector | Choose number/date/text type switches and verify compatible formats remain while incompatible clears. | High | PASS |
| RET-T077 | RET-F050 | Mapping | Field format selector | Verify all listed formats for text, date, number, phone, email and SSN across mapped and inferred types. | Medium | PASS |
| RET-T078 | RET-F051 | Mapping | File Settings entry points | From Mapping click gear and separate plus; confirm both open the same modal and do not modify mapping rows. | Medium | PASS |
| RET-T079 | RET-F052 | Shared | Searchable picker interactions | Exercise search, no match, click, Arrow Up/Down, Enter, Escape, click-outside and scroll positioning for picker. | High | PASS |
| RET-T080 | RET-F052 | Shared | Searchable picker interactions | Exercise option loading/error, remove a previously saved catalog value, and check specialized client/custom placeholders. | Medium | NOT TESTED |
| RET-T081 | RET-F053 | Settings | Open saved settings | Reopen settings on saved job and compare displayed rule rows, positions and normalized decimals. | Medium | PASS |
| RET-T082 | RET-F054 | Settings | Add sorting rule | Add two sort rules in Add and Edit; compare initial direction, sequence and saved priorities. | High | NOT TESTED |
| RET-T083 | RET-F054 | Settings | Add sorting rule | Save sparse or legacy signed sort priorities and verify edit shows canonical direction and re-save renumbers positively. | Medium | PASS |
| RET-T084 | RET-F055 | Settings | Change/delete sorting rule | Change both direction and column, delete first rule, apply, and check remaining sort order. | High | PASS |
| RET-T085 | RET-F056 | Settings | Add conditional rule | Add a condition and verify empty source/operator/value and accessible label indexes. | Medium | PASS |
| RET-T086 | RET-F056 | Settings | Add conditional rule | Select each supported comparison operator and verify enum and metadata write. | High | PASS |
| RET-T087 | RET-F057 | Settings | Change/delete conditional rule | Change each condition value, delete a condition and verify unrelated sort rules are unchanged. | High | PASS |
| RET-T088 | RET-F057 | Settings | Change/delete conditional rule | Use an unsupported saved operator and verify its disabled display and application validation. | High | PASS |
| RET-T089 | RET-F058 | Settings | Custom rule column search | Try custom CSV rule name and noncatalog payroll name. Verify offered custom selection and save/run validation. | High | PASS |
| RET-T090 | RET-F059 | Settings | Apply settings | Apply valid and incomplete sort and conditional rows separately; check closure and exact alert. | High | PASS |
| RET-T091 | RET-F059 | Settings | Apply settings | Apply invalid value, exponent form, blank and signed fraction such as -.5; confirm API precision separately. | High | PASS |
| RET-T092 | RET-F060 | Settings | Clear settings draft | Clear settings and Cancel, reopen then Clear and Apply; compare resulting parent draft lists. | Medium | PASS |
| RET-T093 | RET-F061 | Settings | Close settings without applying | Close dialog by Cancel, backdrop and Escape, then verify draft discard and focus restoration. | Medium | PASS |
| RET-T094 | RET-F061 | Settings | Close settings without applying | Use Tab/Shift+Tab with a portalled mapping selector open, Escape at nested levels and verify focus return. | Medium | FAIL |
| RET-T095 | RET-F062 | Subscriptions | Merge Files checkbox | Toggle Merge Files in subscribed fixture; compare flag storage and manual output before and after. | High | PASS |
| RET-T096 | RET-F063 | Subscriptions | Add/Delete subscription row | Add, delete and reorder-by-deleting subscription drafts; verify no empty row persisted. | Medium | PASS |
| RET-T097 | RET-F064 | Subscriptions | Payroll company picker | Choose visible payroll company, save, and compare signed DB value and rehydrated company display. | High | PASS |
| RET-T098 | RET-F064 | Subscriptions | Payroll company picker | Use missing, duplicate company name and unknown ID conditions in disposable data. Verify catalog and grouping/mail errors. | High | PASS |
| RET-T099 | RET-F065 | Subscriptions | CSV Clients picker | Use CSV mode with saved/default/custom client options; verify integer conversion and leading zeros. | High | PASS |
| RET-T100 | RET-F065 | Subscriptions | CSV Clients picker | Try IDs 0, INT_MAX, excess, decimal, negative, nonnumeric, leading zeroes and displayed selected-client text. | High | PASS |
| RET-T101 | RET-F066 | Subscriptions | Email entry and commit | Commit email with Enter, comma, semicolon and blur; invalid text stays editable and blocks save. | High | PASS |
| RET-T102 | RET-F066 | Subscriptions | Email entry and commit | Try 64/65 local-part and 254/255 complete-address boundaries, malformed syntax and case variants. | High | PASS |
| RET-T103 | RET-F067 | Subscriptions | Paste and deduplicate email | Paste comma/semicolon/newline-separated addresses into selected text and compare deduped tags. | High | PASS |
| RET-T104 | RET-F067 | Subscriptions | Paste and deduplicate email | Compare exact-string UI dedupe with case-insensitive scheduled delivery behavior; no real email addresses. | Medium | PASS |
| RET-T105 | RET-F068 | Subscriptions | Remove email tag | Remove one email by X and last by Backspace on empty input without affecting remaining text. | Medium | PASS |
| RET-T106 | RET-F069 | Subscriptions | Subscription save guards | Compare no rows, empty rows, target only, email only and missing/unknown company during Finish. | High | PASS |
| RET-T107 | RET-F069 | Subscriptions | Subscription save guards | Use combined emails at 255/256 characters, blank target-plus-empty mail, and both companyId and client API values. | High | PASS |
| RET-T108 | RET-F070 | Subscriptions | Finish new job | Complete new payroll job with all sections in disposable data; verify 201, job ID and transactional rows. | Critical | PASS |
| RET-T109 | RET-F071 | Subscriptions | Finish existing job | Update existing job with changed configuration; verify same ID, actual child replacement and existing history. | Critical | PASS |
| RET-T110 | RET-F071 | Subscriptions | Finish existing job | Use PUT with omitted sections versus explicit empty values; check preservation, validation and clear behavior. | High | PASS |
| RET-T111 | RET-F071 | Subscriptions | Finish existing job | Edit a previously run fixture without running it; observe Last Run Date given SQL 45 timestamp and list derivation. | High | FAIL |
| RET-T112 | RET-F072 | Save | Create retry and concurrent guard | Double-click Finish and simulate retry with same key/body; verify one insert and one returned job ID. | Critical | PASS |
| RET-T113 | RET-F072 | Save | Create retry and concurrent guard | Send same key with changed payload, near-boundary invalid key, restart/expiry or concurrent worker requests. | High | FAIL |
| RET-T114 | RET-F073 | Save | Save failure handling | Simulate 422 field detail, non-JSON error, network error and DB error; inspect usable UI recovery. | High | NOT TESTED |
| RET-T115 | RET-F074 | Save | Persist file type and job metadata | Verify labels vs literal delimiters in the DB including legacy labels before re-save and file naming codes. | Critical | PASS |
| RET-T116 | RET-F075 | Save | Persist schedule and mappings | Check saved schedule row, null datetime manual defaults and 1-based mapping sequences in dataset 1. | High | PASS |
| RET-T117 | RET-F075 | Save | Persist schedule and mappings | Verify uppercase/lowercase frequency mapping, weekday persisted indexes, data row sequences and null/blank legacy fields. | Medium | PASS |
| RET-T118 | RET-F076 | Save | Persist subscriptions | Check saved client ID versus payroll signed-company key and combined email text length. | High | PASS |
| RET-T119 | RET-F077 | Save | Persist sort, condition, and queries | Check saved three payroll queries/Detail rule text, CSV_SORT, positive sort rows and normalized condition rows. | Critical | PASS |
| RET-T120 | RET-F077 | Save | Persist sort, condition, and queries | Test finite Decimal threshold boundaries, midpoint rounding, negative zero, signed exponent, 16+2 overflow and invalid finite checks. | High | PASS |
| RET-T121 | RET-F077 | Save | Persist sort, condition, and queries | Use bracket/comma in CSV source sort labels and compare stored quote escaping and exact parse round trip. | High | PASS |
| RET-T122 | RET-F078 | Integration | API options/catalog loading | Compare options response values to SQL/XML and dropdowns. Record partial lookup failures and default messages. | High | PASS |
| RET-T123 | RET-F078 | Integration | API options/catalog loading | Inspect missing XML section, duplicate mapping names/types, invalid delimiters and unconfigured catalogs in isolated fixture. | Medium | PASS |
| RET-T124 | RET-F079 | Execution | Payroll procedure source | Observe procedure template call on save then job-id execution, outputs and representative mapped projection. | Critical | PASS |
| RET-T125 | RET-F079 | Execution | Payroll procedure source | Use duplicate/missing/altered payroll query records in controlled fixtures; verify exact H/D/T guard and legacy PAYROLL path. | Critical | PASS |
| RET-T126 | RET-F079 | Execution | Payroll procedure source | Fix a group with duplicate employee payroll records and NULL salary values; compare SQL COUNT(*) and SUM outcomes. | High | BLOCKED |
| RET-T127 | RET-F080 | Execution | Legacy CSV file source | Run a CSV-mode fixture with job ID input file; check configured directory, encoding and missing file message. | High | PASS |
| RET-T128 | RET-F080 | Execution | Legacy CSV file source | Compare missing, unreadable and oversized configured source files and verify error text, history and no output. | High | PASS |
| RET-T129 | RET-F081 | Execution | Manual API CSV override | POST text/csv override plus empty, wrong media type and over-limit bodies; confirm chosen source and errors. | High | PASS |
| RET-T130 | RET-F081 | Execution | Manual API CSV override | Test exactly 5 MiB and 5 MiB+1 with correct and incorrect request content types, including charset. | High | PASS |
| RET-T131 | RET-F082 | Execution | Parent-job run eligibility | Attempt absent/disabled job and compare 404/409, no generated outputs and no orphan history rows. | High | PASS |
| RET-T132 | RET-F083 | Execution | Source and layout validation | Use missing/duplicate headings, wrong width, missing H/T layout and missing mapped fields against correct controls. | Critical | PASS |
| RET-T133 | RET-F083 | Execution | Source and layout validation | Test 100/101 headings and 10,000/10,001 source rows, BOM, malformed UTF-8, strict quoting and blank lines. | High | PASS |
| RET-T134 | RET-F083 | Execution | Source and layout validation | Test numeric condition source missing, unsupported record type, missing expected H/D/T kind and source field with fallback. | High | FAIL |
| RET-T135 | RET-F084 | Execution | Detail filtering | Run filtered payroll and CSV fixtures with exact numeric threshold; compare raw criteria, D rows and payroll T rows. | Critical | PASS |
| RET-T136 | RET-F084 | Execution | Detail filtering | Evaluate all equality/inequality/relational operators and AND short-circuit with negative/zero/decimal operands. Check input and stored thresholds. | High | PASS |
| RET-T137 | RET-F084 | Execution | Detail filtering | Filter some/all detail rows with H/T, compare aligned trailers, and test mismatch guard for payroll D/T record counts. | High | PASS |
| RET-T138 | RET-F085 | Execution | Detail sort priority | Sort multi-key fixture with a true tie in first key; compare ASC/DESC priority, numeric vs text and source H/T order. | High | PASS |
| RET-T139 | RET-F085 | Execution | Detail sort priority | Use numeric, all-blank, mixed text/numeric, case ties and ISO/non-ISO dates. Confirm treatment of numeric blanks and lexical fallback. | High | PASS |
| RET-T140 | RET-F086 | Execution | Output name and grouping | Group by each filename code and verify filenames, group counts, detail membership and associated H/T. | Critical | PASS |
| RET-T141 | RET-F086 | Execution | Output name and grouping | File Name only fixture should produce one consolidated file with generic plus matched H/T. | High | PASS |
| RET-T142 | RET-F086 | Execution | Output name and grouping | Client ID fixture with two IDs and two dates should produce one file per client. | High | PASS |
| RET-T143 | RET-F086 | Execution | Output name and grouping | Payday fixture with two clients on each date should produce one file per date. | High | PASS |
| RET-T144 | RET-F086 | Execution | Output name and grouping | File Name + Client ID fixture should use the base prefix and split per client. | High | PASS |
| RET-T145 | RET-F086 | Execution | Output name and grouping | File Name + Payday fixture should use the base prefix and split per date. | High | PASS |
| RET-T146 | RET-F086 | Execution | Output name and grouping | Client ID + Payday fixture should produce one file for each client-date pair. | High | PASS |
| RET-T147 | RET-F086 | Execution | Output name and grouping | File Name + Client ID + Payday fixture should use the base prefix and both keys. | High | PASS |
| RET-T148 | RET-F086 | Execution | Output name and grouping | Check missing grouping source/value, default group fallback, wildcard H/T and explicit unmatched layouts. | High | PASS |
| RET-T149 | RET-F086 | Execution | Output name and grouping | Check reserved Windows names, Unicode truncation, filename sanitization, stable casefold collisions and hash suffixes. | High | PASS |
| RET-T150 | RET-F087 | Execution | Value formatting and CSV output | Render number/date/text/phone/SSN/padding fixtures and compare exact file and JSON values. | Critical | PASS |
| RET-T151 | RET-F087 | Execution | Value formatting and CSV output | Verify six date output formats, three input representations, leap year handling and invalid date errors. | High | PASS |
| RET-T152 | RET-F087 | Execution | Value formatting and CSV output | Verify 0/2/4-place decimal, thousands separators, positive/negative half rounding, nonfinite and extreme magnitude. | High | PASS |
| RET-T153 | RET-F087 | Execution | Value formatting and CSV output | Verify all phone formats and required prefixes, SSN masks and invalid length, whitespace and case transforms. | High | PASS |
| RET-T154 | RET-F087 | Execution | Value formatting and CSV output | Verify CSV delimiter escaping, embedded newline/quotes, heading selection without D, and byte cap across multiple groups. | High | PASS |
| RET-T155 | RET-F088 | Execution | Publish and store results | Compare successful publish, result storage on/off and multi-file counts with expected DB rows and disk path. | Critical | PASS |
| RET-T156 | RET-F088 | Execution | Publish and store results | Check stored JSON row numbers and UUID boundaries with duplicated H/T across grouped outputs and no inserts for heading-only row. | High | PASS |
| RET-T157 | RET-F089 | Execution | History and rollback | Trigger failure after output begins and verify transaction/file rollback and Failed history. | Critical | PASS |
| RET-T158 | RET-F089 | Execution | History and rollback | Compare Success/Failed/Pending/In Progress across manual runs, DB errors, poll refresh and process restart. | High | PASS |
| RET-T159 | RET-F090 | Automation | Scheduler lifecycle and slot | Exercise scheduler start flag, date eligibility, UTC slot and each recurrence using controlled clock fixtures. | Critical | PASS |
| RET-T160 | RET-F090 | Automation | Scheduler lifecycle and slot | Compare start-date future/past, selected time, weekday, bi-weekly anchor, last day of month, DST gap/overlap and outside five-minute window. | High | PASS |
| RET-T161 | RET-F090 | Automation | Scheduler lifecycle and slot | Check scheduler disabled, invalid timezone startup, and recovery after outage longer than execution window. | Medium | PASS |
| RET-T162 | RET-F091 | Automation | Scheduled duplicate suppression | Poll same scheduled slot twice with present file or .complete; verify one effective run; inspect lock behavior. | Critical | PASS |
| RET-T163 | RET-F091 | Automation | Scheduled duplicate suppression | Run scheduled zero reports and check .complete duplicate skip; test another scheduler process against job row lock. | High | PASS |
| RET-T164 | RET-F092 | Automation | Subscription delivery eligibility | Verify each recipient receives only reports whose entire company/client set is covered. | Critical | PASS |
| RET-T165 | RET-F092 | Automation | Subscription delivery eligibility | Check no recipients, disabled mail, unmatched/ambiguous IDs, multiple subscriptions per normalized address and manual run silence. | High | PASS |
| RET-T166 | RET-F093 | Automation | Scheduled mail attachment merge | Verify scheduled merge on/off with two eligible files and Include Header Row on/off; compare disk outputs. | High | PASS |
| RET-T167 | RET-F093 | Automation | Scheduled mail attachment merge | Check filenames, byte concatenation, one heading across merged attachments, delimiters preserved and one-file no-op. | High | PASS |
| RET-T168 | RET-F094 | Automation | SMTP send and error recording | Use a controlled test SMTP sink for SSL/TLS, matching attachment and reject/connection errors; verify no real recipients. | Critical | PASS |
| RET-T169 | RET-F094 | Automation | SMTP send and error recording | Compare mail success transport-only, delivery failure and Generate Success state. Verify downloaded CSV equals attachment bytes. | High | PASS |
| RET-T170 | RET-F095 | Integration | Operational health endpoints | Check service health in up/degraded conditions and distinguish HTTP status from JSON payload. | Medium | PASS |
| RET-T171 | RET-F095 | Integration | Operational health endpoints | Simulate SQL connection failure and validate health API response status/JSON and list/catalog UI differences. | Medium | PASS |


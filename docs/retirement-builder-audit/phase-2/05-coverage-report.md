# Retirement Builder Phase 2 coverage

92/95 features (96.8%) have at least one executed assertion with PASS or FAIL. This is feature reach. Complete planned coverage is measured separately. “Verified” requires every linked test to pass, “Failed assertion” means at least one failed, and “Partially verified” means at least one passed with another still open.

| Metric | Result |
| --- | --- |
| Scenarios | 171 |
| Conclusive scenarios | 162/171 (94.7%) |
| Feature outcomes | 76 verified, 6 partially verified, 10 failed assertion, 3 no conclusive run |
| Calculation definitions | 29/29 with executed checks; see calculation outcomes and limits in the dedicated report |


## Features

| Feature | Name | Outcome | Scenarios |
| --- | --- | --- | --- |
| RET-F001 | Sign-in route guard | Verified | [RET-T001](01-test-execution-report.md#ret-t001) |
| RET-F002 | Demo credentials and error | Verified | [RET-T002](01-test-execution-report.md#ret-t002), [RET-T003](01-test-execution-report.md#ret-t003) |
| RET-F003 | Password visibility | Verified | [RET-T004](01-test-execution-report.md#ret-t004) |
| RET-F004 | Shell navigation | Verified | [RET-T005](01-test-execution-report.md#ret-t005) |
| RET-F005 | Responsive layout | Partially verified | [RET-T006](01-test-execution-report.md#ret-t006), [RET-T007](01-test-execution-report.md#ret-t007) |
| RET-F006 | Enabled job list | Verified | [RET-T008](01-test-execution-report.md#ret-t008), [RET-T009](01-test-execution-report.md#ret-t009) |
| RET-F007 | Background list refresh | Partially verified | [RET-T010](01-test-execution-report.md#ret-t010), [RET-T011](01-test-execution-report.md#ret-t011) |
| RET-F008 | Loading, empty and error rows | Verified | [RET-T012](01-test-execution-report.md#ret-t012) |
| RET-F009 | Column filters | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| RET-F010 | Column sorting | Failed assertion | [RET-T014](01-test-execution-report.md#ret-t014), [RET-T015](01-test-execution-report.md#ret-t015) |
| RET-F011 | Row selection | Verified | [RET-T016](01-test-execution-report.md#ret-t016) |
| RET-F012 | Select all visible | Verified | [RET-T017](01-test-execution-report.md#ret-t017) |
| RET-F013 | Edit and Run availability | Failed assertion | [RET-T018](01-test-execution-report.md#ret-t018), [RET-T019](01-test-execution-report.md#ret-t019) |
| RET-F014 | Template download | Verified | [RET-T020](01-test-execution-report.md#ret-t020) |
| RET-F015 | Start new job | Verified | [RET-T021](01-test-execution-report.md#ret-t021) |
| RET-F016 | Open existing job by Edit | Verified | [RET-T022](01-test-execution-report.md#ret-t022) |
| RET-F017 | Open existing job by name | Verified | [RET-T023](01-test-execution-report.md#ret-t023) |
| RET-F018 | Job-detail fetch failure | Failed assertion | [RET-T024](01-test-execution-report.md#ret-t024) |
| RET-F019 | Manual run request | Verified | [RET-T025](01-test-execution-report.md#ret-t025) |
| RET-F020 | Manual run failure feedback | Verified | [RET-T026](01-test-execution-report.md#ret-t026) |
| RET-F021 | Manual run result feedback | Verified | [RET-T027](01-test-execution-report.md#ret-t027), [RET-T028](01-test-execution-report.md#ret-t028) |
| RET-F022 | Download generated files | Verified | [RET-T029](01-test-execution-report.md#ret-t029), [RET-T030](01-test-execution-report.md#ret-t030) |
| RET-F023 | Step tabs and validation | Verified | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T032](01-test-execution-report.md#ret-t032) |
| RET-F024 | Next and Back navigation | No conclusive run | [RET-T033](01-test-execution-report.md#ret-t033) |
| RET-F025 | Cancel and draft reset | Verified | [RET-T034](01-test-execution-report.md#ret-t034), [RET-T035](01-test-execution-report.md#ret-t035) |
| RET-F026 | Refresh and draft restore | Partially verified | [RET-T036](01-test-execution-report.md#ret-t036), [RET-T037](01-test-execution-report.md#ret-t037) |
| RET-F027 | History and direct route | Failed assertion | [RET-T038](01-test-execution-report.md#ret-t038) |
| RET-F028 | File Name | Verified | [RET-T039](01-test-execution-report.md#ret-t039), [RET-T040](01-test-execution-report.md#ret-t040) |
| RET-F029 | File Format | Verified | [RET-T041](01-test-execution-report.md#ret-t041), [RET-T042](01-test-execution-report.md#ret-t042) |
| RET-F030 | Description | Verified | [RET-T043](01-test-execution-report.md#ret-t043) |
| RET-F031 | Output File Name Format | Verified | [RET-T044](01-test-execution-report.md#ret-t044), [RET-T045](01-test-execution-report.md#ret-t045) |
| RET-F032 | Payroll Client ID help | Verified | [RET-T046](01-test-execution-report.md#ret-t046) |
| RET-F033 | Enable/Disable toggle | Failed assertion | [RET-T047](01-test-execution-report.md#ret-t047), [RET-T048](01-test-execution-report.md#ret-t048) |
| RET-F034 | Store Results to Table | Verified | [RET-T049](01-test-execution-report.md#ret-t049) |
| RET-F035 | Browse and workbook import | Verified | [RET-T050](01-test-execution-report.md#ret-t050), [RET-T051](01-test-execution-report.md#ret-t051) |
| RET-F036 | Workbook validation and loading | Verified | [RET-T052](01-test-execution-report.md#ret-t052), [RET-T053](01-test-execution-report.md#ret-t053) |
| RET-F037 | Import replacement and stale reads | No conclusive run | [RET-T054](01-test-execution-report.md#ret-t054) |
| RET-F038 | Start Date and manual-only mode | Failed assertion | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T056](01-test-execution-report.md#ret-t056), [RET-T057](01-test-execution-report.md#ret-t057) |
| RET-F039 | Frequency selection | Verified | [RET-T058](01-test-execution-report.md#ret-t058) |
| RET-F040 | Hour, Minute, AM/PM | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T060](01-test-execution-report.md#ret-t060) |
| RET-F041 | Week selector | Verified | [RET-T061](01-test-execution-report.md#ret-t061) |
| RET-F042 | Add Dataset and empty state | Verified | [RET-T062](01-test-execution-report.md#ret-t062) |
| RET-F043 | Delete mapping row | Verified | [RET-T063](01-test-execution-report.md#ret-t063), [RET-T064](01-test-execution-report.md#ret-t064) |
| RET-F044 | Include Header Row | Verified | [RET-T065](01-test-execution-report.md#ret-t065) |
| RET-F045 | Mapping field identity | Verified | [RET-T066](01-test-execution-report.md#ret-t066), [RET-T067](01-test-execution-report.md#ret-t067) |
| RET-F046 | Mapping positions and lengths | Verified | [RET-T068](01-test-execution-report.md#ret-t068), [RET-T069](01-test-execution-report.md#ret-t069) |
| RET-F047 | Record Type selector | Verified | [RET-T070](01-test-execution-report.md#ret-t070), [RET-T071](01-test-execution-report.md#ret-t071) |
| RET-F048 | Mapping fallback value | Verified | [RET-T072](01-test-execution-report.md#ret-t072), [RET-T073](01-test-execution-report.md#ret-t073) |
| RET-F049 | Source column selector | Verified | [RET-T074](01-test-execution-report.md#ret-t074), [RET-T075](01-test-execution-report.md#ret-t075) |
| RET-F050 | Field format selector | Verified | [RET-T076](01-test-execution-report.md#ret-t076), [RET-T077](01-test-execution-report.md#ret-t077) |
| RET-F051 | File Settings entry points | Verified | [RET-T078](01-test-execution-report.md#ret-t078) |
| RET-F052 | Searchable picker interactions | Partially verified | [RET-T079](01-test-execution-report.md#ret-t079), [RET-T080](01-test-execution-report.md#ret-t080) |
| RET-F053 | Open saved settings | Verified | [RET-T081](01-test-execution-report.md#ret-t081) |
| RET-F054 | Add sorting rule | Partially verified | [RET-T082](01-test-execution-report.md#ret-t082), [RET-T083](01-test-execution-report.md#ret-t083) |
| RET-F055 | Change/delete sorting rule | Verified | [RET-T084](01-test-execution-report.md#ret-t084) |
| RET-F056 | Add conditional rule | Verified | [RET-T085](01-test-execution-report.md#ret-t085), [RET-T086](01-test-execution-report.md#ret-t086) |
| RET-F057 | Change/delete conditional rule | Verified | [RET-T087](01-test-execution-report.md#ret-t087), [RET-T088](01-test-execution-report.md#ret-t088) |
| RET-F058 | Custom rule column search | Verified | [RET-T089](01-test-execution-report.md#ret-t089) |
| RET-F059 | Apply settings | Verified | [RET-T090](01-test-execution-report.md#ret-t090), [RET-T091](01-test-execution-report.md#ret-t091) |
| RET-F060 | Clear settings draft | Verified | [RET-T092](01-test-execution-report.md#ret-t092) |
| RET-F061 | Close settings without applying | Failed assertion | [RET-T093](01-test-execution-report.md#ret-t093), [RET-T094](01-test-execution-report.md#ret-t094) |
| RET-F062 | Merge Files checkbox | Verified | [RET-T095](01-test-execution-report.md#ret-t095) |
| RET-F063 | Add/Delete subscription row | Verified | [RET-T096](01-test-execution-report.md#ret-t096) |
| RET-F064 | Payroll company picker | Verified | [RET-T097](01-test-execution-report.md#ret-t097), [RET-T098](01-test-execution-report.md#ret-t098) |
| RET-F065 | CSV Clients picker | Verified | [RET-T099](01-test-execution-report.md#ret-t099), [RET-T100](01-test-execution-report.md#ret-t100) |
| RET-F066 | Email entry and commit | Verified | [RET-T101](01-test-execution-report.md#ret-t101), [RET-T102](01-test-execution-report.md#ret-t102) |
| RET-F067 | Paste and deduplicate email | Verified | [RET-T103](01-test-execution-report.md#ret-t103), [RET-T104](01-test-execution-report.md#ret-t104) |
| RET-F068 | Remove email tag | Verified | [RET-T105](01-test-execution-report.md#ret-t105) |
| RET-F069 | Subscription save guards | Verified | [RET-T106](01-test-execution-report.md#ret-t106), [RET-T107](01-test-execution-report.md#ret-t107) |
| RET-F070 | Finish new job | Verified | [RET-T108](01-test-execution-report.md#ret-t108) |
| RET-F071 | Finish existing job | Failed assertion | [RET-T109](01-test-execution-report.md#ret-t109), [RET-T110](01-test-execution-report.md#ret-t110), [RET-T111](01-test-execution-report.md#ret-t111) |
| RET-F072 | Create retry and concurrent guard | Failed assertion | [RET-T112](01-test-execution-report.md#ret-t112), [RET-T113](01-test-execution-report.md#ret-t113) |
| RET-F073 | Save failure handling | No conclusive run | [RET-T114](01-test-execution-report.md#ret-t114) |
| RET-F074 | Persist file type and job metadata | Verified | [RET-T115](01-test-execution-report.md#ret-t115) |
| RET-F075 | Persist schedule and mappings | Verified | [RET-T116](01-test-execution-report.md#ret-t116), [RET-T117](01-test-execution-report.md#ret-t117) |
| RET-F076 | Persist subscriptions | Verified | [RET-T118](01-test-execution-report.md#ret-t118) |
| RET-F077 | Persist sort, condition, and queries | Verified | [RET-T119](01-test-execution-report.md#ret-t119), [RET-T120](01-test-execution-report.md#ret-t120), [RET-T121](01-test-execution-report.md#ret-t121) |
| RET-F078 | API options/catalog loading | Verified | [RET-T122](01-test-execution-report.md#ret-t122), [RET-T123](01-test-execution-report.md#ret-t123) |
| RET-F079 | Payroll procedure source | Partially verified | [RET-T124](01-test-execution-report.md#ret-t124), [RET-T125](01-test-execution-report.md#ret-t125), [RET-T126](01-test-execution-report.md#ret-t126) |
| RET-F080 | Legacy CSV file source | Verified | [RET-T127](01-test-execution-report.md#ret-t127), [RET-T128](01-test-execution-report.md#ret-t128) |
| RET-F081 | Manual API CSV override | Verified | [RET-T129](01-test-execution-report.md#ret-t129), [RET-T130](01-test-execution-report.md#ret-t130) |
| RET-F082 | Parent-job run eligibility | Verified | [RET-T131](01-test-execution-report.md#ret-t131) |
| RET-F083 | Source and layout validation | Failed assertion | [RET-T132](01-test-execution-report.md#ret-t132), [RET-T133](01-test-execution-report.md#ret-t133), [RET-T134](01-test-execution-report.md#ret-t134) |
| RET-F084 | Detail filtering | Verified | [RET-T135](01-test-execution-report.md#ret-t135), [RET-T136](01-test-execution-report.md#ret-t136), [RET-T137](01-test-execution-report.md#ret-t137) |
| RET-F085 | Detail sort priority | Verified | [RET-T138](01-test-execution-report.md#ret-t138), [RET-T139](01-test-execution-report.md#ret-t139) |
| RET-F086 | Output name and grouping | Verified | [RET-T140](01-test-execution-report.md#ret-t140), [RET-T141](01-test-execution-report.md#ret-t141), [RET-T142](01-test-execution-report.md#ret-t142), [RET-T143](01-test-execution-report.md#ret-t143), [RET-T144](01-test-execution-report.md#ret-t144), [RET-T145](01-test-execution-report.md#ret-t145), [RET-T146](01-test-execution-report.md#ret-t146), [RET-T147](01-test-execution-report.md#ret-t147), [RET-T148](01-test-execution-report.md#ret-t148), [RET-T149](01-test-execution-report.md#ret-t149) |
| RET-F087 | Value formatting and CSV output | Verified | [RET-T150](01-test-execution-report.md#ret-t150), [RET-T151](01-test-execution-report.md#ret-t151), [RET-T152](01-test-execution-report.md#ret-t152), [RET-T153](01-test-execution-report.md#ret-t153), [RET-T154](01-test-execution-report.md#ret-t154) |
| RET-F088 | Publish and store results | Verified | [RET-T155](01-test-execution-report.md#ret-t155), [RET-T156](01-test-execution-report.md#ret-t156) |
| RET-F089 | History and rollback | Verified | [RET-T157](01-test-execution-report.md#ret-t157), [RET-T158](01-test-execution-report.md#ret-t158) |
| RET-F090 | Scheduler lifecycle and slot | Verified | [RET-T159](01-test-execution-report.md#ret-t159), [RET-T160](01-test-execution-report.md#ret-t160), [RET-T161](01-test-execution-report.md#ret-t161) |
| RET-F091 | Scheduled duplicate suppression | Verified | [RET-T162](01-test-execution-report.md#ret-t162), [RET-T163](01-test-execution-report.md#ret-t163) |
| RET-F092 | Subscription delivery eligibility | Verified | [RET-T164](01-test-execution-report.md#ret-t164), [RET-T165](01-test-execution-report.md#ret-t165) |
| RET-F093 | Scheduled mail attachment merge | Verified | [RET-T166](01-test-execution-report.md#ret-t166), [RET-T167](01-test-execution-report.md#ret-t167) |
| RET-F094 | SMTP send and error recording | Verified | [RET-T168](01-test-execution-report.md#ret-t168), [RET-T169](01-test-execution-report.md#ret-t169) |
| RET-F095 | Operational health endpoints | Verified | [RET-T170](01-test-execution-report.md#ret-t170), [RET-T171](01-test-execution-report.md#ret-t171) |


## Input definitions

45/45 definitions have at least one conclusive linked scenario. A linked scenario is evidence for its recorded variants.

| Definition | Input, rule or branch | Linked scenario outcome | Scenarios |
| --- | --- | --- | --- |
| FI01 | Email | Verified | [RET-T001](01-test-execution-report.md#ret-t001), [RET-T002](01-test-execution-report.md#ret-t002), [RET-T003](01-test-execution-report.md#ret-t003) |
| FI02 | Password | Verified | [RET-T002](01-test-execution-report.md#ret-t002), [RET-T003](01-test-execution-report.md#ret-t003), [RET-T004](01-test-execution-report.md#ret-t004) |
| FI03 | Select all visible jobs | Failed assertion | [RET-T016](01-test-execution-report.md#ret-t016), [RET-T017](01-test-execution-report.md#ret-t017), [RET-T018](01-test-execution-report.md#ret-t018) |
| FI04 | Select {file name} | Failed assertion | [RET-T016](01-test-execution-report.md#ret-t016), [RET-T018](01-test-execution-report.md#ret-t018), [RET-T019](01-test-execution-report.md#ret-t019) |
| FI05 | Filter File Name | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI06 | Filter Description | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI07 | Filter Modified On | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI08 | Filter Last Run Date | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI09 | Filter Run Day | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI10 | Filter Run Time | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI11 | Filter Schedule Type | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI12 | Filter File Type | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI13 | Filter Is Active | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI14 | Filter Status | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| FI15 | File Name | Verified | [RET-T039](01-test-execution-report.md#ret-t039), [RET-T040](01-test-execution-report.md#ret-t040) |
| FI16 | File Format | Verified | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T041](01-test-execution-report.md#ret-t041), [RET-T042](01-test-execution-report.md#ret-t042) |
| FI17 | Description | Verified | [RET-T043](01-test-execution-report.md#ret-t043) |
| FI18 | Output File Name Format | Verified | [RET-T044](01-test-execution-report.md#ret-t044), [RET-T045](01-test-execution-report.md#ret-t045), [RET-T046](01-test-execution-report.md#ret-t046) |
| FI19 | Enable / Disable | Failed assertion | [RET-T047](01-test-execution-report.md#ret-t047), [RET-T048](01-test-execution-report.md#ret-t048) |
| FI20 | Store Results to Table | Verified | [RET-T049](01-test-execution-report.md#ret-t049), [RET-T155](01-test-execution-report.md#ret-t155) |
| FI21 | File (Browse Files) | Partially verified | [RET-T050](01-test-execution-report.md#ret-t050), [RET-T051](01-test-execution-report.md#ret-t051), [RET-T052](01-test-execution-report.md#ret-t052), [RET-T053](01-test-execution-report.md#ret-t053), [RET-T054](01-test-execution-report.md#ret-t054) |
| FI22 | Start Date | Failed assertion | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T056](01-test-execution-report.md#ret-t056), [RET-T057](01-test-execution-report.md#ret-t057) |
| FI23 | Build Frequency | Verified | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T058](01-test-execution-report.md#ret-t058), [RET-T061](01-test-execution-report.md#ret-t061) |
| FI24 | Hour | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T060](01-test-execution-report.md#ret-t060) |
| FI25 | Minute | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T060](01-test-execution-report.md#ret-t060) |
| FI26 | AM or PM | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T060](01-test-execution-report.md#ret-t060) |
| FI27 | Week | Verified | [RET-T058](01-test-execution-report.md#ret-t058), [RET-T061](01-test-execution-report.md#ret-t061) |
| FI28 | Include Header Row | Verified | [RET-T065](01-test-execution-report.md#ret-t065) |
| FI29 | Field Name | Verified | [RET-T062](01-test-execution-report.md#ret-t062), [RET-T067](01-test-execution-report.md#ret-t067) |
| FI30 | Start Position | Verified | [RET-T062](01-test-execution-report.md#ret-t062), [RET-T068](01-test-execution-report.md#ret-t068), [RET-T069](01-test-execution-report.md#ret-t069) |
| FI31 | Length | Verified | [RET-T062](01-test-execution-report.md#ret-t062), [RET-T068](01-test-execution-report.md#ret-t068), [RET-T069](01-test-execution-report.md#ret-t069) |
| FI32 | Record Type | Verified | [RET-T070](01-test-execution-report.md#ret-t070), [RET-T071](01-test-execution-report.md#ret-t071) |
| FI33 | Default Value | Verified | [RET-T072](01-test-execution-report.md#ret-t072), [RET-T073](01-test-execution-report.md#ret-t073) |
| FI34 | Mapping Column | Verified | [RET-T074](01-test-execution-report.md#ret-t074), [RET-T075](01-test-execution-report.md#ret-t075), [RET-T076](01-test-execution-report.md#ret-t076) |
| FI35 | Format | Verified | [RET-T076](01-test-execution-report.md#ret-t076), [RET-T077](01-test-execution-report.md#ret-t077), [RET-T150](01-test-execution-report.md#ret-t150) |
| FI36 | Order By | Partially verified | [RET-T082](01-test-execution-report.md#ret-t082), [RET-T083](01-test-execution-report.md#ret-t083), [RET-T084](01-test-execution-report.md#ret-t084) |
| FI37 | Mapping Column | Partially verified | [RET-T079](01-test-execution-report.md#ret-t079), [RET-T082](01-test-execution-report.md#ret-t082), [RET-T084](01-test-execution-report.md#ret-t084), [RET-T089](01-test-execution-report.md#ret-t089) |
| FI38 | Mapping Column | Verified | [RET-T085](01-test-execution-report.md#ret-t085), [RET-T087](01-test-execution-report.md#ret-t087), [RET-T089](01-test-execution-report.md#ret-t089) |
| FI39 | Condition | Verified | [RET-T086](01-test-execution-report.md#ret-t086), [RET-T088](01-test-execution-report.md#ret-t088), [RET-T090](01-test-execution-report.md#ret-t090) |
| FI40 | Value | Verified | [RET-T085](01-test-execution-report.md#ret-t085), [RET-T087](01-test-execution-report.md#ret-t087), [RET-T091](01-test-execution-report.md#ret-t091), [RET-T120](01-test-execution-report.md#ret-t120) |
| FI41 | Merge Files | Verified | [RET-T095](01-test-execution-report.md#ret-t095), [RET-T166](01-test-execution-report.md#ret-t166), [RET-T167](01-test-execution-report.md#ret-t167) |
| FI42 | Payroll Company / Payroll company {n} | Verified | [RET-T097](01-test-execution-report.md#ret-t097), [RET-T098](01-test-execution-report.md#ret-t098) |
| FI43 | Clients / Client {n} | Verified | [RET-T099](01-test-execution-report.md#ret-t099), [RET-T100](01-test-execution-report.md#ret-t100) |
| FI44 | Mail / Email {n} | Verified | [RET-T101](01-test-execution-report.md#ret-t101), [RET-T102](01-test-execution-report.md#ret-t102), [RET-T103](01-test-execution-report.md#ret-t103), [RET-T104](01-test-execution-report.md#ret-t104), [RET-T105](01-test-execution-report.md#ret-t105), [RET-T106](01-test-execution-report.md#ret-t106), [RET-T107](01-test-execution-report.md#ret-t107) |
| FI45 | Search {control name} | Failed assertion | [RET-T079](01-test-execution-report.md#ret-t079), [RET-T080](01-test-execution-report.md#ret-t080), [RET-T094](01-test-execution-report.md#ret-t094) |

## Validation rules and guards

73/74 definitions have at least one conclusive linked scenario. A linked scenario is evidence for its recorded variants.

| Definition | Input, rule or branch | Linked scenario outcome | Scenarios |
| --- | --- | --- | --- |
| V01 | Email browser syntax plus trimmed/lowercased exact demo address, password exact and case-sensitive. Blank credentials fail the component comparison. | Verified | [RET-T002](01-test-execution-report.md#ret-t002), [RET-T003](01-test-execution-report.md#ret-t003) |
| V02 | Toolbar Edit/Run require exactly one selected ID in loaded jobs. Selection checkboxes disabled during run; Run button also disabled during its request. | Failed assertion | [RET-T016](01-test-execution-report.md#ret-t016), [RET-T017](01-test-execution-report.md#ret-t017), [RET-T018](01-test-execution-report.md#ret-t018), [RET-T019](01-test-execution-report.md#ret-t019) |
| V03 | Empty/whitespace normalizes to empty; any text is accepted and matched against display strings. | Verified | [RET-T013](01-test-execution-report.md#ret-t013) |
| V04 | File Name and File Format must be nonblank for Add, and when supplied to PUT. | Verified | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T039](01-test-execution-report.md#ret-t039), [RET-T041](01-test-execution-report.md#ret-t041) |
| V05 | 255 characters max. No UI character blacklist; forbidden filename characters handled at runtime. | Verified | [RET-T040](01-test-execution-report.md#ret-t040) |
| V06 | 20 characters max on supplied API input. | Verified | [RET-T042](01-test-execution-report.md#ret-t042) |
| V07 | Must resolve to a configured label, alias, or literal delimiter, with supported catalog type. Catalog excludes blank labels, labels over 20, multichar and quote/NUL/line separators. API blank guard rejects raw space/tab on explicit save; choose Space/Tab labels in UI. | Verified | [RET-T041](01-test-execution-report.md#ret-t041), [RET-T042](01-test-execution-report.md#ret-t042), [RET-T123](01-test-execution-report.md#ret-t123) |
| V08 | Optional, max 300 on API rather than inline UI length. | Verified | [RET-T043](01-test-execution-report.md#ret-t043) |
| V09 | Optional, max 55; unknown/duplicates/invalid parts resolve to File Name fallback, not enum rejection. | Verified | [RET-T044](01-test-execution-report.md#ret-t044), [RET-T045](01-test-execution-report.md#ret-t045) |
| V10 | Pydantic bool contract; Edit only visible, Add initializes true. | Failed assertion | [RET-T047](01-test-execution-report.md#ret-t047), [RET-T048](01-test-execution-report.md#ret-t048), [RET-T131](01-test-execution-report.md#ret-t131) |
| V11 | Pydantic bool contract; false in fresh wizard. | Verified | [RET-T049](01-test-execution-report.md#ret-t049) |
| V12 | File chooser accepts .xlsx/.xls and MIME hints; JS compares case-insensitive suffix. | Verified | [RET-T050](01-test-execution-report.md#ret-t050), [RET-T051](01-test-execution-report.md#ret-t051) |
| V13 | XLSX ZIP prefix; XLS OLE or recognized BIFF signature; a renamed plain-text file fails. | Verified | [RET-T051](01-test-execution-report.md#ret-t051) |
| V14 | First worksheet only, require at least one discovered trimmed field. Uses field/column-like first-sheet header and subsequent values or first row as raw names. | Verified | [RET-T051](01-test-execution-report.md#ret-t051), [RET-T052](01-test-execution-report.md#ret-t052), [RET-T053](01-test-execution-report.md#ret-t053) |
| V15 | XLSX.read and related errors caught. A failed replacement preserves old mappings; UI hides previous success text under error. | Verified | [RET-T051](01-test-execution-report.md#ret-t051) |
| V16 | Blank fields dropped, duplicate exact names dropped (case variants remain), H/Header and T/Trailer recognized, all other type cells interpreted as Detail. | Verified | [RET-T050](01-test-execution-report.md#ret-t050), [RET-T052](01-test-execution-report.md#ret-t052) |
| V17 | Request-generation counter discards stale success/error and Dashboard navigation invalidates pending parse. Forward advancement and Next blocked while reading. | No conclusive run | [RET-T054](01-test-execution-report.md#ret-t054) |
| V18 | HTML date uses min 1753-01-01/max 9999-12-31. Frontend guards year pattern/lower bound; API date model validates structure and explicit lower bound. | Verified | [RET-T056](01-test-execution-report.md#ret-t056) |
| V19 | Wholly blank draft bypasses field guards. Null start date means manual-only, even if other schedule metadata exists. | Failed assertion | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T057](01-test-execution-report.md#ret-t057) |
| V20 | Required in nonblank UI schedule. API enum Daily/Weekly/Bi-Weekly/Monthly with default Weekly if omitted. | Verified | [RET-T058](01-test-execution-report.md#ret-t058), [RET-T061](01-test-execution-report.md#ret-t061) |
| V21 | Whole 1–12. 0, negative, fractional, excessive, or blank (populated schedule) fails. | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T060](01-test-execution-report.md#ret-t060) |
| V22 | Whole 0–59, text can have leading zeroes. | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T060](01-test-execution-report.md#ret-t060) |
| V23 | Required in nonblank schedule; API literal AM or PM, default AM when omitted. | Verified | [RET-T059](01-test-execution-report.md#ret-t059), [RET-T061](01-test-execution-report.md#ret-t061) |
| V24 | UI requires Week only for Weekly/Bi-Weekly. API literal weekday if supplied, default Thursday. | Verified | [RET-T058](01-test-execution-report.md#ret-t058), [RET-T061](01-test-execution-report.md#ret-t061) |
| V25 | Pydantic bool contract. UI Add unchecked, API default true, edit uses saved flag. | Verified | [RET-T065](01-test-execution-report.md#ret-t065) |
| V26 | At least 1 mapping for create, explicitly supplied PUT rows, UI forward and run. | Verified | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T067](01-test-execution-report.md#ret-t067) |
| V27 | Trimmed Field Name required for every row. | Verified | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T067](01-test-execution-report.md#ret-t067) |
| V28 | Up to 255. | Verified | [RET-T067](01-test-execution-report.md#ret-t067) |
| V29 | Max 100 columns per record type and case-insensitively unique output names per type at run. | Verified | [RET-T067](01-test-execution-report.md#ret-t067) |
| V30 | Blank UI saves 0; explicit API value is whole 0–2,147,483,647. Rejects negative, decimal, signed plus and too-large values. | Verified | [RET-T062](01-test-execution-report.md#ret-t062), [RET-T068](01-test-execution-report.md#ret-t068), [RET-T069](01-test-execution-report.md#ret-t069) |
| V31 | Same whole-number bounds as V30; actual padding has a separate lower runtime cap V65. | Verified | [RET-T062](01-test-execution-report.md#ret-t062), [RET-T068](01-test-execution-report.md#ret-t068), [RET-T069](01-test-execution-report.md#ret-t069) |
| V32 | String up to 20 characters; default blank means Detail at run. Payroll validates supported H/D/T aliases on save. | Verified | [RET-T070](01-test-execution-report.md#ret-t070), [RET-T071](01-test-execution-report.md#ret-t071) |
| V33 | Optional, up to 255. Numeric/date validity checked only when formatted. | Verified | [RET-T072](01-test-execution-report.md#ret-t072), [RET-T073](01-test-execution-report.md#ret-t073) |
| V34 | Optional, up to 255; blank uses Field Name. | Verified | [RET-T066](01-test-execution-report.md#ret-t066), [RET-T074](01-test-execution-report.md#ret-t074) |
| V35 | Optional, up to 20; runtime validates known label for nonblank value. | Verified | [RET-T076](01-test-execution-report.md#ret-t076), [RET-T077](01-test-execution-report.md#ret-t077), [RET-T150](01-test-execution-report.md#ret-t150) |
| V36 | Populated modal sorting row must select direction and column. API enum ASC/DESC with default ASC if omitted. | Verified | [RET-T084](01-test-execution-report.md#ret-t084), [RET-T090](01-test-execution-report.md#ret-t090) |
| V37 | Nonblank column up to 255; if orderBy nonempty must be whole 0–2,147,483,647. Rule rank not editable UI. | Partially verified | [RET-T082](01-test-execution-report.md#ret-t082), [RET-T083](01-test-execution-report.md#ret-t083), [RET-T084](01-test-execution-report.md#ret-t084) |
| V38 | Nonblank, up to 255. | Verified | [RET-T085](01-test-execution-report.md#ret-t085), [RET-T090](01-test-execution-report.md#ret-t090) |
| V39 | Required supported comparison and max 50 characters server-side. | Verified | [RET-T086](01-test-execution-report.md#ret-t086), [RET-T088](01-test-execution-report.md#ret-t088), [RET-T090](01-test-execution-report.md#ret-t090) |
| V40 | Signed decimal or exponent, including -.5 and 1., required alongside source and operator. | Verified | [RET-T091](01-test-execution-report.md#ret-t091) |
| V41 | Finite Decimal, round half-up to 2 places and fit at most 16 whole digits. | Verified | [RET-T120](01-test-execution-report.md#ret-t120) |
| V42 | Pydantic bool. Disabled feature flag/mail attachment checks still gate delivery; enabled without multiple attachments stays single. | Verified | [RET-T095](01-test-execution-report.md#ret-t095), [RET-T166](01-test-execution-report.md#ret-t166), [RET-T167](01-test-execution-report.md#ret-t167) |
| V43 | Completely blank UI rows discarded. Partially filled rows need a valid target. API rejects client and company on same row. | Verified | [RET-T096](01-test-execution-report.md#ret-t096), [RET-T097](01-test-execution-report.md#ret-t097), [RET-T106](01-test-execution-report.md#ret-t106), [RET-T107](01-test-execution-report.md#ret-t107) |
| V44 | Addresses split on comma/semicolon/newline. Pattern, 254 characters max and local part up to 64. Server checks an ASCII pattern and frontend uses a separately defined regex. | Verified | [RET-T101](01-test-execution-report.md#ret-t101), [RET-T102](01-test-execution-report.md#ret-t102), [RET-T107](01-test-execution-report.md#ret-t107) |
| V45 | Payroll mapping must reference one of five supported source names or have Default Value; sort/filter always must use supported source names. | Failed assertion | [RET-T071](01-test-execution-report.md#ret-t071), [RET-T089](01-test-execution-report.md#ret-t089), [RET-T134](01-test-execution-report.md#ret-t134) |
| V46 | Optional numeric company ID 0–2,147,483,647 via API. Must exist in unique company lookup and job must be payroll. | Verified | [RET-T097](01-test-execution-report.md#ret-t097), [RET-T098](01-test-execution-report.md#ret-t098) |
| V47 | Digits, allow 0 and leading zeroes, max 2,147,483,647. UI parses "id - display name" but posts integer text. | Verified | [RET-T099](01-test-execution-report.md#ret-t099), [RET-T100](01-test-execution-report.md#ret-t100) |
| V48 | Comma-space joined nonempty row email strings including separators max 255. Target-only row accepted. | Verified | [RET-T102](01-test-execution-report.md#ret-t102), [RET-T107](01-test-execution-report.md#ret-t107) |
| V49 | Exact strings deduped in same row; malformed address from delimiter paste/commit remains in editable draft and blocks Finish. SMTP matching downcases address. | Verified | [RET-T101](01-test-execution-report.md#ret-t101), [RET-T103](01-test-execution-report.md#ret-t103), [RET-T104](01-test-execution-report.md#ret-t104) |
| V50 | Trim search; literal case-insensitive contains. Custom menus cap search at 255 chars, reject case duplicate, and optionally constrain numeric client values. | Partially verified | [RET-T079](01-test-execution-report.md#ret-t079), [RET-T080](01-test-execution-report.md#ret-t080), [RET-T089](01-test-execution-report.md#ret-t089) |
| V51 | Edit draft needs numeric job ID. Forward attempts validate earlier steps. Direct/history effect checks General but not all earlier steps until normal validation/Finish. | Failed assertion | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T032](01-test-execution-report.md#ret-t032), [RET-T036](01-test-execution-report.md#ret-t036), [RET-T038](01-test-execution-report.md#ret-t038) |
| V52 | Nonempty request body must have base type text/csv and be ≤5 MiB. Empty means use configured source. Configured CSV capped after reading at most max+1; payroll cap enforced per row and final UTF-8 byte length. | Verified | [RET-T129](01-test-execution-report.md#ret-t129), [RET-T130](01-test-execution-report.md#ret-t130) |
| V53 | UTF-8 (BOM accepted), strict comma input. At least one name, max 100, all nonempty and distinct after trim/casefold. | Verified | [RET-T132](01-test-execution-report.md#ret-t132), [RET-T133](01-test-execution-report.md#ret-t133) |
| V54 | H/T layout needs a Record Type heading. Each source kind needs a configured layout, and each configured kind needs at least one initial source row. Blank/unrecognized type fails for typed source. | Failed assertion | [RET-T070](01-test-execution-report.md#ret-t070), [RET-T071](01-test-execution-report.md#ret-t071), [RET-T132](01-test-execution-report.md#ret-t132), [RET-T134](01-test-execution-report.md#ret-t134) |
| V55 | Up to 10,000 source rows; CSV counter advances through blank rows before skipping. Nonblank row width must equal header count. Payroll procedure also capped at 10,000. | Verified | [RET-T132](01-test-execution-report.md#ret-t132), [RET-T133](01-test-execution-report.md#ret-t133) |
| V56 | Every mapped/fallback field must be in headings unless nonempty default exists. | Failed assertion | [RET-T072](01-test-execution-report.md#ret-t072), [RET-T132](01-test-execution-report.md#ret-t132), [RET-T134](01-test-execution-report.md#ret-t134) |
| V57 | Group dimension source required. Retained D must have client/date or configured fallback. Dates valid, and a grouped file with H/T input requires matching H/T. | Verified | [RET-T140](01-test-execution-report.md#ret-t140), [RET-T148](01-test-execution-report.md#ret-t148) |
| V58 | Source column and supported operator required. Raw source and threshold must be finite Decimal. Blanks, nonnumeric strings (including ISO dates) and NaN/Infinity fail when evaluated. | Failed assertion | [RET-T134](01-test-execution-report.md#ret-t134), [RET-T135](01-test-execution-report.md#ret-t135), [RET-T136](01-test-execution-report.md#ret-t136) |
| V59 | Source column required. Mixed numeric and nonnumeric makes whole key use casefolded text, not rejection. | Verified | [RET-T138](01-test-execution-report.md#ret-t138), [RET-T139](01-test-execution-report.md#ret-t139) |
| V60 | If any D is removed and trailers exist, their original count must match raw D count. No retained D returns with no files. | Verified | [RET-T137](01-test-execution-report.md#ret-t137) |
| V61 | Valid date in recognized ISO or US input forms. Invalid calendar date fails except empty values bypass. | Verified | [RET-T151](01-test-execution-report.md#ret-t151) |
| V62 | Finite decimal, bounded magnitude, quantizable at chosen scale. | Verified | [RET-T152](01-test-execution-report.md#ret-t152) |
| V63 | Allowed source chars and digits, explicit country prefix/length for international, 10-digit or leading North American 1 as applicable. | Verified | [RET-T153](01-test-execution-report.md#ret-t153) |
| V64 | Nine ASCII digits after trim and hyphen removal. | Verified | [RET-T153](01-test-execution-report.md#ret-t153) |
| V65 | Width >1,000 fails for nonempty value with LA - Left Justified. Unknown format fails for nonempty value. | Verified | [RET-T069](01-test-execution-report.md#ret-t069), [RET-T150](01-test-execution-report.md#ret-t150) |
| V66 | Missing job 404, disabled manual 409 before report writes. Invalid run config/data 422. | Verified | [RET-T131](01-test-execution-report.md#ret-t131) |
| V67 | Output total max 10 MiB of generated UTF-8. Configured source missing/unreadable and report writes failing have specific messages. | Verified | [RET-T127](01-test-execution-report.md#ret-t127), [RET-T128](01-test-execution-report.md#ret-t128), [RET-T154](01-test-execution-report.md#ret-t154), [RET-T157](01-test-execution-report.md#ret-t157) |
| V68 | Exactly one marked H/D/T template per job, SQL hash check against approved templates. Legacy PAYROLL must match current expected signature with procedure call removed. Procedure name must be valid SQL identifiers. | Verified | [RET-T124](01-test-execution-report.md#ret-t124), [RET-T125](01-test-execution-report.md#ret-t125) |
| V69 | Payroll Conditions parse canonical column/operator/numeric threshold; sort text must serialize back exactly; payroll columns must be supported. | Verified | [RET-T119](01-test-execution-report.md#ret-t119), [RET-T121](01-test-execution-report.md#ret-t121), [RET-T125](01-test-execution-report.md#ret-t125) |
| V70 | Missing/nonunique company name fails when a company ID is required for grouping or subscriptions. | Verified | [RET-T098](01-test-execution-report.md#ret-t098) |
| V71 | Optional header 1–128 visible ASCII characters. Same key/different fingerprint → 409. Browser suppresses in-flight repeats; backend coalesces same pending. | Failed assertion | [RET-T112](01-test-execution-report.md#ret-t112), [RET-T113](01-test-execution-report.md#ret-t113) |
| V72 | queryConfiguration.recttype up to 10. App removes old generated markers and creates known payroll H/D/T or CSV_SORT metadata on write. | Verified | [RET-T119](01-test-execution-report.md#ret-t119), [RET-T125](01-test-execution-report.md#ret-t125) |
| V73 | Require enabled dated job and due slot within 5-minute window; recheck under job lock; skip slot markers, missing outputs/subscriptions, unmatched file IDs, or disabled mail. | Verified | [RET-T159](01-test-execution-report.md#ret-t159), [RET-T160](01-test-execution-report.md#ret-t160), [RET-T161](01-test-execution-report.md#ret-t161), [RET-T162](01-test-execution-report.md#ret-t162), [RET-T163](01-test-execution-report.md#ret-t163), [RET-T164](01-test-execution-report.md#ret-t164), [RET-T165](01-test-execution-report.md#ret-t165) |
| V74 | Mail enabled requires nonblank host, username, password and from address. Config restricts SMTP, SSL/TLS, port 1–65535. | Verified | [RET-T164](01-test-execution-report.md#ret-t164), [RET-T165](01-test-execution-report.md#ret-t165), [RET-T168](01-test-execution-report.md#ret-t168), [RET-T169](01-test-execution-report.md#ret-t169) |

## Conditional branches

31/31 definitions have at least one conclusive linked scenario. A linked scenario is evidence for its recorded variants.

| Definition | Input, rule or branch | Linked scenario outcome | Scenarios |
| --- | --- | --- | --- |
| B01 | Demo session on entry | Verified | [RET-T001](01-test-execution-report.md#ret-t001) |
| B02 | Demo credential comparison | Verified | [RET-T002](01-test-execution-report.md#ret-t002), [RET-T003](01-test-execution-report.md#ret-t003) |
| B03 | Dashboard fetch outcome | Verified | [RET-T011](01-test-execution-report.md#ret-t011), [RET-T012](01-test-execution-report.md#ret-t012) |
| B04 | Dashboard selection cardinality | Failed assertion | [RET-T016](01-test-execution-report.md#ret-t016), [RET-T017](01-test-execution-report.md#ret-t017), [RET-T018](01-test-execution-report.md#ret-t018), [RET-T019](01-test-execution-report.md#ret-t019) |
| B05 | Dashboard sort/filter | Failed assertion | [RET-T013](01-test-execution-report.md#ret-t013), [RET-T014](01-test-execution-report.md#ret-t014), [RET-T015](01-test-execution-report.md#ret-t015) |
| B06 | Add, Edit, Edit without context | Verified | [RET-T021](01-test-execution-report.md#ret-t021), [RET-T022](01-test-execution-report.md#ret-t022), [RET-T023](01-test-execution-report.md#ret-t023), [RET-T032](01-test-execution-report.md#ret-t032) |
| B07 | Forward validation/import in progress | Partially verified | [RET-T031](01-test-execution-report.md#ret-t031), [RET-T033](01-test-execution-report.md#ret-t033), [RET-T054](01-test-execution-report.md#ret-t054) |
| B08 | Wizard refresh/history | Failed assertion | [RET-T034](01-test-execution-report.md#ret-t034), [RET-T036](01-test-execution-report.md#ret-t036), [RET-T037](01-test-execution-report.md#ret-t037), [RET-T038](01-test-execution-report.md#ret-t038) |
| B09 | General mode | Verified | [RET-T021](01-test-execution-report.md#ret-t021), [RET-T047](01-test-execution-report.md#ret-t047) |
| B10 | Output name format includes Client ID and source is payroll | Verified | [RET-T046](01-test-execution-report.md#ret-t046) |
| B11 | Workbook outcome | Partially verified | [RET-T050](01-test-execution-report.md#ret-t050), [RET-T051](01-test-execution-report.md#ret-t051), [RET-T052](01-test-execution-report.md#ret-t052), [RET-T053](01-test-execution-report.md#ret-t053), [RET-T054](01-test-execution-report.md#ret-t054) |
| B12 | Empty versus populated schedule draft | Failed assertion | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T057](01-test-execution-report.md#ret-t057), [RET-T061](01-test-execution-report.md#ret-t061) |
| B13 | Weekly/Bi-Weekly versus Daily/Monthly | Verified | [RET-T058](01-test-execution-report.md#ret-t058), [RET-T061](01-test-execution-report.md#ret-t061) |
| B14 | Saved start date | Verified | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T056](01-test-execution-report.md#ret-t056), [RET-T116](01-test-execution-report.md#ret-t116) |
| B15 | Source | Verified | [RET-T074](01-test-execution-report.md#ret-t074), [RET-T089](01-test-execution-report.md#ret-t089), [RET-T097](01-test-execution-report.md#ret-t097), [RET-T099](01-test-execution-report.md#ret-t099) |
| B16 | Mapping source/type changes | Verified | [RET-T075](01-test-execution-report.md#ret-t075), [RET-T076](01-test-execution-report.md#ret-t076), [RET-T077](01-test-execution-report.md#ret-t077) |
| B17 | File Settings draft | Verified | [RET-T035](01-test-execution-report.md#ret-t035), [RET-T078](01-test-execution-report.md#ret-t078), [RET-T090](01-test-execution-report.md#ret-t090), [RET-T092](01-test-execution-report.md#ret-t092), [RET-T093](01-test-execution-report.md#ret-t093) |
| B18 | Dropdown interaction/options | Failed assertion | [RET-T079](01-test-execution-report.md#ret-t079), [RET-T080](01-test-execution-report.md#ret-t080), [RET-T089](01-test-execution-report.md#ret-t089), [RET-T094](01-test-execution-report.md#ret-t094) |
| B19 | Subscription row content | Verified | [RET-T096](01-test-execution-report.md#ret-t096), [RET-T097](01-test-execution-report.md#ret-t097), [RET-T099](01-test-execution-report.md#ret-t099), [RET-T101](01-test-execution-report.md#ret-t101), [RET-T106](01-test-execution-report.md#ret-t106), [RET-T107](01-test-execution-report.md#ret-t107) |
| B20 | Finish outcome | Partially verified | [RET-T108](01-test-execution-report.md#ret-t108), [RET-T109](01-test-execution-report.md#ret-t109), [RET-T114](01-test-execution-report.md#ret-t114) |
| B21 | Run request source | Verified | [RET-T124](01-test-execution-report.md#ret-t124), [RET-T127](01-test-execution-report.md#ret-t127), [RET-T128](01-test-execution-report.md#ret-t128), [RET-T129](01-test-execution-report.md#ret-t129) |
| B22 | Run eligibility | Verified | [RET-T055](01-test-execution-report.md#ret-t055), [RET-T131](01-test-execution-report.md#ret-t131) |
| B23 | Output grouping | Verified | [RET-T140](01-test-execution-report.md#ret-t140), [RET-T141](01-test-execution-report.md#ret-t141), [RET-T142](01-test-execution-report.md#ret-t142), [RET-T143](01-test-execution-report.md#ret-t143), [RET-T144](01-test-execution-report.md#ret-t144), [RET-T145](01-test-execution-report.md#ret-t145), [RET-T146](01-test-execution-report.md#ret-t146), [RET-T147](01-test-execution-report.md#ret-t147), [RET-T148](01-test-execution-report.md#ret-t148) |
| B24 | Filtering and no matches | Verified | [RET-T028](01-test-execution-report.md#ret-t028), [RET-T135](01-test-execution-report.md#ret-t135), [RET-T136](01-test-execution-report.md#ret-t136), [RET-T137](01-test-execution-report.md#ret-t137) |
| B25 | CSV headings | Verified | [RET-T065](01-test-execution-report.md#ret-t065), [RET-T154](01-test-execution-report.md#ret-t154) |
| B26 | Store Results to Table | Verified | [RET-T049](01-test-execution-report.md#ret-t049), [RET-T155](01-test-execution-report.md#ret-t155), [RET-T156](01-test-execution-report.md#ret-t156) |
| B27 | Manual results UI | Verified | [RET-T025](01-test-execution-report.md#ret-t025), [RET-T026](01-test-execution-report.md#ret-t026), [RET-T027](01-test-execution-report.md#ret-t027), [RET-T028](01-test-execution-report.md#ret-t028), [RET-T029](01-test-execution-report.md#ret-t029), [RET-T030](01-test-execution-report.md#ret-t030), [RET-T158](01-test-execution-report.md#ret-t158) |
| B28 | Scheduled time eligibility | Verified | [RET-T159](01-test-execution-report.md#ret-t159), [RET-T160](01-test-execution-report.md#ret-t160), [RET-T161](01-test-execution-report.md#ret-t161), [RET-T162](01-test-execution-report.md#ret-t162), [RET-T163](01-test-execution-report.md#ret-t163) |
| B29 | Email eligibility | Verified | [RET-T164](01-test-execution-report.md#ret-t164), [RET-T165](01-test-execution-report.md#ret-t165), [RET-T168](01-test-execution-report.md#ret-t168), [RET-T169](01-test-execution-report.md#ret-t169) |
| B30 | Merge Files | Verified | [RET-T166](01-test-execution-report.md#ret-t166), [RET-T167](01-test-execution-report.md#ret-t167) |
| B31 | Viewport | Partially verified | [RET-T006](01-test-execution-report.md#ret-t006), [RET-T007](01-test-execution-report.md#ret-t007), [RET-T093](01-test-execution-report.md#ret-t093) |


## Phase 1 risk follow-up

| Risk ID | Phase 2 observation | Related tests |
| --- | --- | --- |
| R01 | Confirmed hidden-selection defect. | [RET-T018](01-test-execution-report.md#ret-t018) |
| R02 | Isolated API answers without the UI demo session. Network exposure and production authorization were outside this functional audit. | [RET-T001](01-test-execution-report.md#ret-t001), [RET-T170](01-test-execution-report.md#ret-t170) |
| R03 | Confirmed disabled-job recovery defect. | [RET-T047](01-test-execution-report.md#ret-t047), [RET-T048](01-test-execution-report.md#ret-t048) |
| R04 | Canceled draft reopened through Back. | [RET-T034](01-test-execution-report.md#ret-t034), [RET-T038](01-test-execution-report.md#ret-t038) |
| R05 | Detail 404 and disconnect stayed silent. | [RET-T024](01-test-execution-report.md#ret-t024) |
| R06 | Partial schedule saved as Manual only without a missing-date warning. | [RET-T057](01-test-execution-report.md#ret-t057) |
| R07 | Save accepts a value that fails the padding path at runtime; Start Position is stored independently. | [RET-T068](01-test-execution-report.md#ret-t068), [RET-T069](01-test-execution-report.md#ret-t069), [RET-T073](01-test-execution-report.md#ret-t073), [RET-T134](01-test-execution-report.md#ret-t134) |
| R08 | Replacement and 4,000-row import exercised. Overlapping parse/cancel race remains open. | [RET-T053](01-test-execution-report.md#ret-t053), [RET-T054](01-test-execution-report.md#ret-t054), [RET-T064](01-test-execution-report.md#ret-t064) |
| R09 | Confirmed Company Name filter save/run mismatch. | [RET-T134](01-test-execution-report.md#ret-t134), [RET-T135](01-test-execution-report.md#ret-t135) |
| R10 | Chronological dashboard sort failed. ISO and non-ISO detail comparison exercised separately. | [RET-T015](01-test-execution-report.md#ret-t015), [RET-T139](01-test-execution-report.md#ret-t139) |
| R11 | Generated success survives SMTP rejection; manual run produced no mail. | [RET-T165](01-test-execution-report.md#ret-t165), [RET-T168](01-test-execution-report.md#ret-t168), [RET-T169](01-test-execution-report.md#ret-t169) |
| R12 | SQL outage returned a partial options response with HTTP 200; selection state after live catalog removal remains open. | [RET-T080](01-test-execution-report.md#ret-t080), [RET-T122](01-test-execution-report.md#ret-t122), [RET-T123](01-test-execution-report.md#ret-t123), [RET-T171](01-test-execution-report.md#ret-t171) |
| R13 | Date bounds, UTF-8 byte cap, unusual names and malformed CSV exercised. Browser OS date-picker combinations remain limited. | [RET-T040](01-test-execution-report.md#ret-t040), [RET-T056](01-test-execution-report.md#ret-t056), [RET-T133](01-test-execution-report.md#ret-t133), [RET-T149](01-test-execution-report.md#ret-t149) |
| R14 | Single-process replay held; a second process created a duplicate. Run serialization was checked separately. | [RET-T112](01-test-execution-report.md#ret-t112), [RET-T113](01-test-execution-report.md#ret-t113), [RET-T162](01-test-execution-report.md#ret-t162), [RET-T163](01-test-execution-report.md#ret-t163) |
| R15 | Responsive geometry checked; portalled picker focus skips controls. | [RET-T006](01-test-execution-report.md#ret-t006), [RET-T007](01-test-execution-report.md#ret-t007), [RET-T094](01-test-execution-report.md#ret-t094) |
| R16 | Both seeded payroll months returned. Schedule clock selects run time; no user-configurable data date range was exercised. | [RET-T124](01-test-execution-report.md#ret-t124), [RET-T126](01-test-execution-report.md#ret-t126), [RET-T159](01-test-execution-report.md#ret-t159) |
| R17 | CSV escaping and raw cell preservation checked at the generator. Import behavior in external spreadsheet applications was outside scope. | [RET-T150](01-test-execution-report.md#ret-t150), [RET-T154](01-test-execution-report.md#ret-t154) |
| R18 | Slot expiry, duplicate detector, success status and repeated execution were tested with controlled time. Full-duration service outages were not staged. | [RET-T158](01-test-execution-report.md#ret-t158), [RET-T160](01-test-execution-report.md#ret-t160), [RET-T161](01-test-execution-report.md#ret-t161), [RET-T162](01-test-execution-report.md#ret-t162), [RET-T163](01-test-execution-report.md#ret-t163) |
| R19 | Edit advanced displayed date without execution. | [RET-T111](01-test-execution-report.md#ret-t111) |

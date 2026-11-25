# Retirement Builder testing action notes

Read [AGENTS.md](AGENTS.md) and the
[job 60 testing guide](skills/retirement-builder-test-skills.md). These notes do
not authorize additional actions or change their database protection rules.

## Report testing scope

- Excel `.xlsx`/`.xls` workbooks are inputs for **uploading mapping columns** in
  the user's workflow. They are not the report-delivery target for routine QA.
- Validate the generated **`.csv`, `.txt` and TAB `.tsv` files and their data**.
  Check extensions, actual delimiters/FIXED layout, headers/trailers, field order,
  source accuracy, mappings, formats, sorting, conditions, filenames, downloads,
  single/multiple clients, blanks, quotes, Unicode and identifier leading zeros.
- Do not test generated Excel files, Download Excel, native Microsoft Excel
  opening, configured Excel import or add-in setup unless the user explicitly
  requests Excel compatibility testing. An existing Excel download button does
  not make those checks part of routine report QA.
- Do not block text-report validation because Excel or an add-in is unavailable.
  Mark Excel output/native checks **OUT OF SCOPE** unless separately requested.
  Existing Excel helper tests in an authorized automated suite do not require
  expanding the live testing scope. Leave application functionality unchanged.

## Safety reminder

Use existing job 60 only. UI Save/Finish and manual Run require current user
authorization; do not make manual database changes, create jobs, change schema,
queries or stored procedures, trigger the scheduler or send mail. Keep
`MAIL_ENABLED=false`, capture a fresh baseline, restore original editable settings
after authorized mutations, preserve reports and evidence, and report PASS, FAIL,
BLOCKED and NOT TESTED accurately. Do not fix issues without separate approval.

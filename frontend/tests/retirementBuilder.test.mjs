import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'vite'
import XLSX from 'xlsx'

const cacheDir = await mkdtemp(join(tmpdir(), 'retirement-builder-test-'))
const vite = await createServer({
  cacheDir,
  configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(async () => {
  await vite.close()
  await rm(cacheDir, { recursive: true, force: true })
})
const {
  configuredFileFormat, createJobListRequestGuard, displayJobStatus, displayRunTime, emailAddresses, generalFieldErrors,
  mergeSavedJob, normalizeSortingPriorities, sortingPriorityError, pasteEmailText, readExcelMappings, reportWorkbook,
  excelDownloadFileName, reportMimeType, validEmail, validIsoDate, validWholeNumber,
} = await vite.ssrLoadModule('/src/retirementBuilder.ts')

test('report downloads preserve bytes and use format-appropriate MIME and Excel filenames', async () => {
  for (const [extension, mime] of [
    ['csv', 'text/csv'], ['txt', 'text/plain'], ['tsv', 'text/tab-separated-values'],
  ]) {
    for (const suffix of [extension, extension.toUpperCase()]) {
      const fileName = `Payroll.v2_000204_2026-10-15.${suffix}`
      const content = 'PAYDATE,NAME,ID,BLANK\r\n10/15/2026,"José, Alex",000001,\r\n'
      const blob = new Blob([content], { type: reportMimeType(fileName) })
      assert.equal(blob.type, `${mime};charset=utf-8`)
      assert.equal(blob.size, Buffer.byteLength(content, 'utf8'))
      assert.equal(await blob.text(), content)
      assert.equal(excelDownloadFileName(fileName), 'Payroll.v2_000204_2026-10-15.xlsx')
    }
  }
  assert.equal(excelDownloadFileName('Payroll.v2'), 'Payroll.v2.xlsx')
  assert.equal(reportMimeType('Historical.csv', [['Fixed    ']]), 'text/plain;charset=utf-8')
})

test('saving immediately replaces the dashboard format while retaining history and other jobs', () => {
  const jobs = [
    { id: 60, general: { fileName: 'Demo', fileFormat: 'FIXED', enable: true },
      schedule: { hour: '4', week: 'Thursday' }, joblastrun: '2026-11-18', Job_Last_Status: 'Success' },
    { id: 61, general: { fileName: 'Other', fileFormat: 'PIPE', enable: true } },
  ]
  const before = structuredClone(jobs)
  const saved = { id: 60, general: { fileFormat: 'CSV', enable: true }, schedule: { week: 'Friday' } }
  const next = mergeSavedJob(jobs, saved)
  assert.equal(next[0].general.fileFormat, 'CSV')
  assert.equal(next[0].general.fileName, 'Demo')
  assert.equal(next[0].joblastrun, '2026-11-18')
  assert.equal(next[0].Job_Last_Status, 'Success')
  assert.deepEqual(next[0].schedule, { hour: '4', week: 'Friday' })
  assert.equal(next[1], jobs[1])
  assert.deepEqual(jobs, before)
  assert.equal(mergeSavedJob(next, saved).length, 2)
  assert.deepEqual(mergeSavedJob(next, { id: 60, general: { enable: false } }), [jobs[1]])
  assert.equal(mergeSavedJob([], saved)[0].general.fileFormat, 'CSV')
})

test('a list response started before Save cannot overwrite the new dashboard format', async () => {
  const guard = createJobListRequestGuard()
  let resolveOld
  const old = new Promise((resolve) => { resolveOld = resolve })
  let jobs = [{ id: 60, general: { fileFormat: 'FIXED' } }]
  const pending = guard.apply(() => old, (value) => { jobs = value })
  guard.invalidate()
  jobs = mergeSavedJob(jobs, { id: 60, general: { fileFormat: 'CSV' } })
  await guard.apply(() => Promise.resolve([{ id: 60, general: { fileFormat: 'CSV' }, joblastrun: '2026-11-18' }]),
    (value) => { jobs = value })
  resolveOld([{ id: 60, general: { fileFormat: 'FIXED' } }])
  await pending
  assert.equal(jobs[0].general.fileFormat, 'CSV')
  assert.equal(jobs[0].joblastrun, '2026-11-18')
})

test('aborted dashboard requests do not replace current rows', async () => {
  const guard = createJobListRequestGuard()
  const controller = new AbortController()
  let resolve
  const pending = new Promise((done) => { resolve = done })
  const committed = []
  const request = guard.apply(() => pending, (rows) => committed.push(rows), controller.signal)
  controller.abort()
  resolve([{ id: 60 }])
  await request
  assert.deepEqual(committed, [])
})

test('FIXED Excel downloads use structured fields instead of splitting padded records on spaces', () => {
  const fields = [
    ['NAME            ', 'SSN      ', 'COUNT'],
    ['Doe, Sam "Ace"  ', '000000000', '    7'],
  ]
  const workbook = reportWorkbook('NAME            SSN      COUNT\r\nDoe, Sam "Ace"  000000000    7\r\n', ' ', fields)
  const bytes = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })
  const reopened = XLSX.read(bytes, { type: 'buffer', raw: true })
  const sheet = reopened.Sheets.Report
  assert.deepEqual(XLSX.utils.sheet_to_json(sheet, { header: 1, raw: true }), fields)
  assert.equal(sheet.B2.t, 's')
  assert.equal(sheet.B2.v, '000000000')
})

test('General flags blank and oversized required values', () => {
  assert.deepEqual(generalFieldErrors('  ', ''), {
    fileName: 'Enter a file name.',
    fileFormat: 'Select a file format.',
  })
  assert.ok(generalFieldErrors('x'.repeat(256), 'CSV').fileName)
  assert.deepEqual(generalFieldErrors('QA', 'CSV'), { fileName: '', fileFormat: '' })
})

test('restored file format labels use the current configured option', () => {
  const options = ['CSV', 'FIXED', 'PIPE', 'TAB', 'SEMICOLON']
  assert.equal(configuredFileFormat('Comma', options), 'CSV')
  assert.equal(configuredFileFormat('CSV', options), 'CSV')
  assert.equal(configuredFileFormat('Pipe', options), 'PIPE')
  assert.equal(configuredFileFormat('CSV_TAB', options), 'TAB')
  assert.equal(configuredFileFormat('CSV_SEMI', options), 'SEMICOLON')
  assert.equal(configuredFileFormat('Comma', ['CSV', 'Comma']), 'Comma')
  assert.equal(configuredFileFormat('CSV', ['Comma']), 'Comma')
  assert.equal(configuredFileFormat('Comma', []), 'Comma')
  assert.equal(configuredFileFormat('', options), '')
})

test('mapping and schedule number checks use the accepted ranges', () => {
  for (const value of ['-1', 'abc', '', '1.5', '2147483648']) assert.equal(validWholeNumber(value), false)
  for (const value of ['0', '2147483647']) assert.equal(validWholeNumber(value), true)
  assert.equal(validWholeNumber('0', 1, 12), false)
  assert.equal(validWholeNumber('12', 1, 12), true)
  assert.equal(validWholeNumber('05', 0, 59), true)
  assert.equal(validWholeNumber('60', 0, 59), false)
})

test('sort priorities require unique positive integers and a column', () => {
  assert.equal(sortingPriorityError([]), '')
  for (const orderBy of ['', '0', '-1', '1.5', 'ASC', '2147483648']) {
    assert.match(sortingPriorityError([{ orderBy, mappingColumn: 'paydate' }]), /positive whole-number priority/)
  }
  assert.match(sortingPriorityError([
    { orderBy: '1', mappingColumn: 'paydate' }, { orderBy: '01', mappingColumn: 'Employee_Name' },
  ]), /different priority/)
  assert.match(sortingPriorityError([{ orderBy: '1', mappingColumn: ' ' }]), /mapping column/)
  assert.equal(sortingPriorityError([{ orderBy: '2147483647', mappingColumn: 'paydate' }]), '')
})

test('priority-only payloads preserve precedence and strip legacy directions', () => {
  const rows = [
    { orderBy: '3', mappingColumn: ' Employee_Name ', direction: 'DESC' },
    { orderBy: '1', mappingColumn: 'paydate', direction: 'ASC' },
  ]
  const result = normalizeSortingPriorities(rows)
  assert.deepEqual(result, [
    { orderBy: '1', mappingColumn: 'paydate' },
    { orderBy: '2', mappingColumn: 'Employee_Name' },
  ])
  assert.equal(rows[0].orderBy, '3')
  assert.deepEqual(normalizeSortingPriorities(result.slice(1)), [{ orderBy: '1', mappingColumn: 'Employee_Name' }])
})

test('date conditions require a real calendar date in ISO format', () => {
  for (const value of ['2026-11-01', '2024-02-29', ' 0001-01-01 ']) assert.equal(validIsoDate(value), true)
  for (const value of ['2026-02-29', '2026-13-01', '0000-01-01', '20261101', '2026-11-1']) {
    assert.equal(validIsoDate(value), false)
  }
})

test('Excel downloads preserve delimited columns and treat report values as text', () => {
  for (const delimiter of [',', '\t', ' ', ';', '|', '~']) {
    const columnLabels = ['Company, Name', 'Pay Date', 'Code', 'Note', 'Empty', 'Literal']
    const values = [
      `Audit${delimiter}Alpha`, '2026-11-01', '00007', 'First line\n"Second line"', '', '=1+1',
    ]
    const quote = (value) => `"${value.replaceAll('"', '""')}"`
    const csv = [columnLabels, values].map((row) => row.map(quote).join(delimiter)).join('\r\n') + '\r\n'
    const output = XLSX.write(reportWorkbook(csv, delimiter), { bookType: 'xlsx', type: 'buffer' })
    const parsed = XLSX.read(output, { type: 'buffer' }).Sheets.Report
    assert.deepEqual(XLSX.utils.sheet_to_json(parsed, { header: 1, defval: '' }), [columnLabels, values])
    assert.equal(parsed.F2.t, 's')
    assert.equal(parsed.F2.f, undefined)
  }
  const { Report } = reportWorkbook('sep=,\r\nClient Name\r\n', '\t').Sheets
  assert.deepEqual(XLSX.utils.sheet_to_json(Report, { header: 1 }), [['sep=,'], ['Client Name']])
})

test('multiple emails replace the selected draft and are validated individually', () => {
  const invalid = 'not-an-email'
  const replacement = 'one+qa@example.invalid, two@example.invalid\nthree@example.invalid'
  assert.equal(validEmail(invalid), false)
  assert.equal(pasteEmailText(invalid, replacement, 0, invalid.length), replacement)
  const emails = emailAddresses(replacement)
  assert.equal(emails.length, 3)
  assert.ok(emails.every(validEmail))
})

test('dashboard preserves minutes and actual history status', () => {
  assert.equal(displayRunTime('1', '5', 'AM'), '1:05 AM')
  assert.equal(displayJobStatus(null), 'Pending')
  assert.equal(displayJobStatus('Unknown'), 'Pending')
  assert.equal(displayJobStatus('In Progress'), 'In Progress')
  assert.equal(displayJobStatus('Failed'), 'Failed')
  assert.equal(displayJobStatus('Success'), 'Success')
})

test('Excel imports retain Detail and Trailer rows and deduplicate fields', async () => {
  const book = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ['Field Name', 'Record Type'],
    ['PAY_DATE', 'D'],
    ['TRAILER_COUNT', 'T'],
    ['PAY_DATE', 'D'],
  ]), 'Mappings')
  for (const [bookType, extension] of [['xlsx', 'xlsx'], ['biff8', 'xls']]) {
    const file = new File([XLSX.write(book, { type: 'buffer', bookType })], `mapping.${extension}`)
    assert.deepEqual(await readExcelMappings(file), [
      { field: 'PAY_DATE', recordType: 'Detail' },
      { field: 'TRAILER_COUNT', recordType: 'Trailer' },
    ])
  }
})

test('a renamed text file and a broken XLSX container both fail to import', async () => {
  await assert.rejects(readExcelMappings(new File(['PAY_DATE,COUNT'], 'renamed.xlsx')))
  await assert.rejects(readExcelMappings(new File([Uint8Array.of(0x50, 0x4b, 0x03, 0x04)], 'corrupt.xlsx')))
})

test('Excel mapping imports preserve dataset ordering metadata and separate H D T fields', async () => {
  const book = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ['Field Name', 'Record Type', 'DataSetNo', 'ColSeqNo'],
    ['Name', 'H', 1, 1],
    ['Name', 'D', 2, 3],
    ['Name', 'D', 3, 1],
    ['Name', 'T', 4, 1],
  ]), 'Mappings')
  const file = new File([XLSX.write(book, { type: 'buffer', bookType: 'xlsx' })], 'ordered.xlsx')
  assert.deepEqual(await readExcelMappings(file), [
    { field: 'Name', recordType: 'Header', dataSetNo: 1, colSeqNo: 1 },
    { field: 'Name', recordType: 'Detail', dataSetNo: 2, colSeqNo: 3 },
    { field: 'Name', recordType: 'Detail', dataSetNo: 3, colSeqNo: 1 },
    { field: 'Name', recordType: 'Trailer', dataSetNo: 4, colSeqNo: 1 },
  ])
})

test('file names cannot contain characters that are invalid in file names', () => {
  assert.equal(generalFieldErrors('Report_1', 'CSV').fileName, '')
  for (const name of ['a/b', 'a:b', 'a*b', 'a?b', 'a"b', 'a<b', 'a>b', 'a|b', 'a\\b']) {
    assert.match(generalFieldErrors(name, 'CSV').fileName, /cannot contain/)
  }
})

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
  displayFileFormat, displayJobStatus, displayRunTime, emailAddresses, generalFieldErrors,
  pasteEmailText, readExcelMappings, validEmail, validWholeNumber,
} = await vite.ssrLoadModule('/src/retirementBuilder.ts')

test('General flags blank and oversized required values', () => {
  assert.deepEqual(generalFieldErrors('  ', ''), {
    fileName: 'Enter a file name.',
    fileFormat: 'Select a file format.',
  })
  assert.ok(generalFieldErrors('x'.repeat(256), 'CSV').fileName)
  assert.deepEqual(generalFieldErrors('QA', 'CSV'), { fileName: '', fileFormat: '' })
})

test('mapping and schedule number checks use the accepted ranges', () => {
  for (const value of ['-1', 'abc', '', '1.5', '2147483648']) assert.equal(validWholeNumber(value), false)
  for (const value of ['0', '2147483647']) assert.equal(validWholeNumber(value), true)
  assert.equal(validWholeNumber('0', 1, 12), false)
  assert.equal(validWholeNumber('12', 1, 12), true)
  assert.equal(validWholeNumber('05', 0, 59), true)
  assert.equal(validWholeNumber('60', 0, 59), false)
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

test('dashboard preserves delimiters, minutes, and actual history status', () => {
  assert.equal(displayFileFormat('CSV_PIPE'), 'CSV (Pipe Delimited)')
  assert.equal(displayFileFormat('CSV (Pipe Delimited)'), 'CSV (Pipe Delimited)')
  assert.equal(displayFileFormat('CSV_TAB'), 'CSV (Tab Delimited)')
  assert.equal(displayFileFormat('CSV_SEMI'), 'CSV (Semicolon Delimited)')
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

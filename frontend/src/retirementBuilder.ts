import * as XLSX from 'xlsx'

type DatasetPosition = { dataSetNo?: number; colSeqNo?: number }

export function mappingDatasets<T extends DatasetPosition>(rows: T[]) {
  const numbers = [...new Set(rows.map((row) => row.dataSetNo ?? 1))].sort((a, b) => a - b)
  return (numbers.length ? numbers : [1]).map((number) => ({
    number, rows: rows.filter((row) => (row.dataSetNo ?? 1) === number),
  }))
}

export function normalizeDatasetSequences<T extends DatasetPosition>(rows: T[]): T[] {
  const maximum = new Map<number, number>()
  rows.forEach((row) => maximum.set(row.dataSetNo ?? 1, Math.max(maximum.get(row.dataSetNo ?? 1) ?? 0, row.colSeqNo ?? 0)))
  return rows.map((row) => {
    const dataset = row.dataSetNo ?? 1
    const sequence = row.colSeqNo ?? (maximum.get(dataset) ?? 0) + 1
    maximum.set(dataset, Math.max(maximum.get(dataset) ?? 0, sequence))
    return { ...row, dataSetNo: dataset, colSeqNo: sequence }
  })
}

export function nextMappingPosition(rows: DatasetPosition[], dataset?: number) {
  const number = dataset ?? (rows.length ? Math.max(...rows.map((row) => row.dataSetNo ?? 1)) + 1 : 1)
  const sequence = Math.max(0, ...rows.filter((row) => (row.dataSetNo ?? 1) === number).map((row) => row.colSeqNo ?? 0)) + 1
  if (number > 2147483647 || sequence > 2147483647) throw new Error('The dataset or column sequence exceeds the integer limit.')
  return { dataSetNo: number, colSeqNo: sequence }
}

export function reportMimeType(fileName: string, excelRows?: string[][] | null): string {
  const extension = fileName.split('.').pop()?.toLowerCase()
  const type = excelRows != null ? 'text/plain'
    : extension === 'csv' ? 'text/csv' : extension === 'tsv' ? 'text/tab-separated-values' : 'text/plain'
  return `${type};charset=utf-8`
}

export function excelDownloadFileName(fileName: string): string {
  return fileName.replace(/\.(csv|txt|tsv)$/i, '') + '.xlsx'
}

type SavedJobSnapshot = { id: number; general?: { enable?: boolean }; schedule?: object }

export function mergeSavedJob<T extends SavedJobSnapshot>(jobs: T[], saved: T): T[] {
  const previous = jobs.find((job) => job.id === saved.id)
  const merged = {
    ...previous, ...saved,
    general: { ...previous?.general, ...saved.general },
    schedule: { ...previous?.schedule, ...saved.schedule },
  } as T
  return previous ? jobs.map((job) => job.id === saved.id ? merged : job) : [merged, ...jobs]
}

export function createJobListRequestGuard() {
  let revision = 0
  return {
    invalidate() { revision += 1 },
    async apply<T>(load: () => Promise<T>, commit: (value: T) => void, signal?: AbortSignal) {
      const started = revision
      const value = await load()
      if (started === revision && !signal?.aborted) commit(value)
    },
  }
}

const legacyFileFormatNames = new Map([
  ['CSV', 'COMMA'],
  ['CSV (COMMA DELIMITED)', 'COMMA'],
  ['CSV_PIPE', 'PIPE'],
  ['CSV (PIPE DELIMITED)', 'PIPE'],
  ['CSV_TAB', 'TAB'],
  ['CSV (TAB DELIMITED)', 'TAB'],
  ['CSV_SEMI', 'SEMICOLON'],
  ['CSV (SEMICOLON DELIMITED)', 'SEMICOLON'],
])

export function configuredFileFormat(value: string, options: string[]) {
  if (!value.trim() || !options.length) return value
  const requested = value.trim().toUpperCase()
  const exact = options.find((option) => option.toUpperCase() === requested)
  if (exact !== undefined) return exact

  const legacy = legacyFileFormatNames.get(requested) ?? requested
  return options.find((option) => {
    const name = option.toUpperCase()
    return (legacyFileFormatNames.get(name) ?? name) === legacy
  }) ?? value
}

export function displayJobStatus(status?: string | null) {
  switch (status?.trim().toLowerCase()) {
    case 'success': case 'completed': return 'Success'
    case 'failed': case 'failure': case 'error': return 'Failed'
    case 'in progress': case 'running': case 'processing': return 'In Progress'
    default: return 'Pending'
  }
}

export function displayRunTime(hour?: string, minute?: string, meridiem?: string) {
  return hour && minute
    ? [`${hour}:${minute.padStart(2, '0')}`, meridiem].filter(Boolean).join(' ')
    : ''
}

export type ReportEmailDelivery = { enabled: boolean; matched: number; accepted: number }

export function reportEmailMessage({ enabled, matched, accepted }: ReportEmailDelivery) {
  if (!enabled) return 'Email delivery is disabled.'
  if (!matched) return 'No subscribers matched the generated files.'
  if (!accepted) return 'Email delivery failed. The files are available below.'
  if (accepted < matched) return `Mail server accepted delivery for ${accepted} of ${matched} recipients.`
  return `Mail server accepted delivery for ${accepted} ${accepted === 1 ? 'recipient' : 'recipients'}.`
}

export function generalFieldErrors(fileName: string, fileFormat: string) {
  return {
    fileName: !fileName.trim() ? 'Enter a file name.' : fileName.length > 255 ? 'Use at most 255 characters.'
      : /[\\/:*?"<>|\u0000-\u001f]/.test(fileName) ? 'File Name cannot contain \\ / : * ? " < > | or control characters.' : '',
    fileFormat: !fileFormat.trim() ? 'Select a file format.' : '',
  }
}

export function pasteEmailText(value: string, pasted: string, start: number | null, end: number | null) {
  return value.slice(0, start ?? value.length) + pasted + value.slice(end ?? value.length)
}

export function isExcelFile(file: File): boolean { const name = file.name.toLowerCase(); return name.endsWith('.xlsx') || name.endsWith('.xls') }

export function reportWorkbook(csv: string, delimiter: string, excelRows?: string[][] | null) {
  if (excelRows != null) {
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(excelRows), 'Report')
    return workbook
  }
  // A neutral first line keeps the reader from interpreting report data as a format directive.
  const firstLine = delimiter === '0' ? '1' : '0'
  const parsed = XLSX.read(`${firstLine}\r\n${csv}`, { type: 'string', FS: delimiter, raw: true })
  const rows = XLSX.utils.sheet_to_json<string[]>(parsed.Sheets[parsed.SheetNames[0]], {
    header: 1, range: 1, blankrows: true,
  })
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(rows), 'Report')
  return workbook
}

function normalizeExcelRecordType(value: unknown): string {
  const type = String(value ?? '').trim().toUpperCase()
  if (type === 'H' || type === 'HEADER') return 'Header'
  if (type === 'T' || type === 'TRAILER') return 'Trailer'
  return 'Detail'
}

type ImportedMapping = { field: string; recordType: string; dataSetNo?: number; colSeqNo?: number }

export async function readExcelMappings(file: File): Promise<ImportedMapping[]> {
  const buffer = await file.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  const hasSignature = (signature: number[]) => signature.every((byte, index) => bytes[index] === byte)
  const isWorkbook = file.name.toLowerCase().endsWith('.xlsx')
    ? hasSignature([0x50, 0x4b, 0x03, 0x04])
    : hasSignature([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1])
      || (bytes[0] === 0x09 && [0x00, 0x02, 0x04, 0x08].includes(bytes[1]))
  if (!isWorkbook) throw new Error('Invalid workbook signature')

  const workbook = XLSX.read(buffer, { type: 'array' })
  const sheet = workbook.Sheets[workbook.SheetNames[0]]
  if (!sheet) return []
  const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, defval: '' })
  const header = rows[0] ?? []
  const headers = header.map((value) => String(value).trim().toLowerCase())
  const fieldIndex = headers.findIndex((value) => value.includes('column') || value.includes('field'))
  const recordTypeIndex = headers.findIndex((value) => value.includes('record') && value.includes('type'))
  const compactHeaders = headers.map((value) => value.replace(/[ _]/g, ''))
  const datasetIndex = compactHeaders.indexOf('datasetno')
  const sequenceIndex = compactHeaders.indexOf('colseqno')
  const metadata = (row: unknown[]) => {
    const result: { dataSetNo?: number; colSeqNo?: number } = {}
    for (const [index, key] of [[datasetIndex, 'dataSetNo'], [sequenceIndex, 'colSeqNo']] as const) {
      if (index < 0 || String(row[index] ?? '').trim() === '') continue
      const value = String(row[index]).trim()
      if (!validWholeNumber(value)) throw new Error('Invalid dataset or column sequence')
      result[key] = Number(value)
    }
    return result
  }
  const fields: ImportedMapping[] = fieldIndex >= 0 && rows.length > 1
    ? rows.slice(1).map((row) => ({
        field: String(row[fieldIndex] ?? '').trim(),
        recordType: normalizeExcelRecordType(row[recordTypeIndex]),
        ...metadata(row),
      }))
    : header.map((value) => ({ field: String(value).trim(), recordType: 'Detail' }))
  return fields.filter((row, index, all) => row.field && all.findIndex((candidate) => candidate.field === row.field
    && candidate.recordType === row.recordType && (candidate.dataSetNo ?? 1) === (row.dataSetNo ?? 1)) === index)
}

const emailPattern = /^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$/i
export const emailAddresses = (value: string) => value.split(/[,;\n]/).map((email) => email.trim()).filter(Boolean)
export const validEmail = (email: string) => email.length <= 254 && email.indexOf('@') <= 64 && emailPattern.test(email)

export function validWholeNumber(value: string, minimum = 0, maximum = 2147483647) {
  return /^[0-9]+$/.test(value.trim()) && Number(value) >= minimum && Number(value) <= maximum
}

export type SortingPriorityRow = { orderBy: string; mappingColumn: string }

export function sortingPriorityError(rows: SortingPriorityRow[]) {
  if (rows.some((row) => !validWholeNumber(row.orderBy, 1))) return 'Enter a positive whole-number priority for each sort rule.'
  if (new Set(rows.map((row) => Number(row.orderBy))).size !== rows.length) return 'Use a different priority for each sort rule.'
  if (rows.some((row) => !row.mappingColumn.trim())) return 'Choose a mapping column for each sort rule.'
  return ''
}

export function normalizeSortingPriorities(rows: SortingPriorityRow[]): SortingPriorityRow[] {
  return [...rows].sort((a, b) => Number(a.orderBy) - Number(b.orderBy)).map((row, index) => ({
    orderBy: String(index + 1), mappingColumn: row.mappingColumn.trim(),
  }))
}

export function validIsoDate(value: string) {
  const iso = value.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso) || iso.startsWith('0000-')) return false
  const date = new Date(`${iso}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === iso
}

export function mappingColumnType(column: string, knownTypes: Record<string, string>) {
  const name = column.trim().toLowerCase()
  const knownName = Object.keys(knownTypes).find((key) => key.toLowerCase() === name)
  const knownType = knownName && knownTypes[knownName]
  if (knownType && knownType !== 'text' && knownType !== 'number') return knownType

  const words = column.trim().replace(/([a-z0-9])([A-Z])/g, '$1 $2').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
  if (/\b(?:ssn|social security number)\b/.test(words)) return 'ssn'
  if (/\b(?:phone|telephone|mobile|cellphone|fax)\b|^(?:(?:home|work|mobile|cell)?phone|telephone)(?:number|no)?$/.test(words)
    && !/\b(?:extension|ext|type|label|country code|verified)\b/.test(words)) return 'phone'
  if (/\b(?:email|e mail)\b|^(?:work|home|employee|personal)?email(?:address)?$/.test(words)) return 'email'
  if (knownType) return knownType
  if (/\b(?:date|dob)\b|^(?:pay|hire|birth|termination|start|end)date$/.test(words)) return 'date'
  if (/\b(?:amount|salary|wages|hours|count|gross pay|net pay|contribution|deduction|balance|percent|rate)\b/.test(words)) return 'number'
  return 'text'
}

export type ConditionValueType = 'text' | 'number' | 'date'

export function conditionValueError(value: string, type: ConditionValueType) {
  if (type === 'date') return validIsoDate(value) ? '' : 'Enter a valid date in YYYY-MM-DD format.'
  if (type === 'number') return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())
    && Number.isFinite(Number(value)) ? '' : 'Enter a number for each numeric condition.'
  return value.trim() && !value.includes('\0') && value.length <= 4000 ? '' : 'Enter a text value of up to 4,000 characters.'
}

export const manualRunDateHelp = 'Blank dates are sent as 01/01/1900. They do not mean an open-ended range. Enter both dates for a specific manual report.'

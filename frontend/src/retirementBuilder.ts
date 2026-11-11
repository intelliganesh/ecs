import * as XLSX from 'xlsx'

const fileFormatLabels: Record<string, string> = {
  CSV: 'CSV (Comma Delimited)',
  CSV_PIPE: 'CSV (Pipe Delimited)',
  CSV_TAB: 'CSV (Tab Delimited)',
  CSV_SEMI: 'CSV (Semicolon Delimited)',
}

export function displayFileFormat(format = '') {
  const value = format.trim()
  return fileFormatLabels[value.toUpperCase()] ?? value
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

export function generalFieldErrors(fileName: string, fileFormat: string) {
  return {
    fileName: !fileName.trim() ? 'Enter a file name.' : fileName.length > 255 ? 'Use at most 255 characters.' : '',
    fileFormat: !fileFormat.trim() ? 'Select a file format.' : '',
  }
}

export function pasteEmailText(value: string, pasted: string, start: number | null, end: number | null) {
  return value.slice(0, start ?? value.length) + pasted + value.slice(end ?? value.length)
}

export function isExcelFile(file: File): boolean { const name = file.name.toLowerCase(); return name.endsWith('.xlsx') || name.endsWith('.xls') }

function normalizeExcelRecordType(value: unknown): string {
  const type = String(value ?? '').trim().toUpperCase()
  if (type === 'H' || type === 'HEADER') return 'Header'
  if (type === 'T' || type === 'TRAILER') return 'Trailer'
  return 'Detail'
}

export async function readExcelMappings(file: File): Promise<Array<{ field: string; recordType: string }>> {
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
  const fields = fieldIndex >= 0 && rows.length > 1
    ? rows.slice(1).map((row) => ({
        field: String(row[fieldIndex] ?? '').trim(),
        recordType: normalizeExcelRecordType(row[recordTypeIndex]),
      }))
    : header.map((value) => ({ field: String(value).trim(), recordType: 'Detail' }))
  return fields.filter((row, index, all) => row.field && all.findIndex((candidate) => candidate.field === row.field) === index)
}

const emailPattern = /^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$/i
export const emailAddresses = (value: string) => value.split(/[,;\n]/).map((email) => email.trim()).filter(Boolean)
export const validEmail = (email: string) => email.length <= 254 && email.indexOf('@') <= 64 && emailPattern.test(email)

export function validWholeNumber(value: string, minimum = 0, maximum = 2147483647) {
  return /^[0-9]+$/.test(value.trim()) && Number(value) >= minimum && Number(value) <= maximum
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

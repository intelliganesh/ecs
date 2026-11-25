import * as XLSX from 'xlsx'

// Source keys come from the payroll options API; no separate field catalog.
export function payrollMappingWorkbook(labels: Record<string, string>) {
  const columns = Object.entries(labels).filter(([key]) => key.trim().toLowerCase() !== 'default')
  if (!columns.length) throw new Error('No payroll mapping columns are available.')
  const sheet = XLSX.utils.aoa_to_sheet([
    ['Field Name', 'Mapping Column', 'Record Type', 'DataSetNo', 'ColSeqNo'],
    ...columns.map(([key, label], index) => [label.trim() || key, key, 'Detail', 1, index + 1]),
  ])
  sheet['!cols'] = [{ wch: 34 }, { wch: 28 }, { wch: 16 }, { wch: 14 }, { wch: 14 }]
  sheet['!autofilter'] = { ref: sheet['!ref']! }
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, 'Payroll Mappings')
  return workbook
}

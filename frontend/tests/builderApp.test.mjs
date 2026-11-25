import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import React from 'react'
import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

const cacheDir = await mkdtemp(join(tmpdir(), 'ecs-builder-ui-test-'))
const vite = await createServer({
  configFile: false, cacheDir, plugins: [react()],
  server: { middlewareMode: true, hmr: false, ws: false, watch: null }, appType: 'custom',
})
const { default: App } = await vite.ssrLoadModule('/src/App.tsx')
after(async () => { await vite.close(); await rm(cacheDir, { recursive: true, force: true }) })

function render(path, drafts = {}) {
  const previousWindow = globalThis.window
  const previousStorage = globalThis.sessionStorage
  const previousFetch = globalThis.fetch
  globalThis.window = { innerWidth: 1400 }
  globalThis.sessionStorage = { getItem: (key) => drafts[key] ? JSON.stringify(drafts[key]) : null }
  globalThis.fetch = () => { throw new Error('Live API access prohibited in UI tests') }
  try {
    return renderToString(React.createElement(MemoryRouter, { initialEntries: [path] },
      React.createElement(App, { userEmail: 'fixture@example.invalid' })))
  } finally {
    globalThis.window = previousWindow
    globalThis.sessionStorage = previousStorage
    globalThis.fetch = previousFetch
  }
}

const draft = (name, mode = 'add') => ({
  mode, jobId: mode === 'edit' ? 987654 : null, enable: false,
  fileName: name, fileFormat: 'CSV', description: '', outputFileNameFormat: 'FILE_NAME',
  reportSource: 'csv', storeResultsToTable: false, selectedFile: '',
  schedule: { startDate: '', buildFrequency: '', hour: '', minute: '', meridiem: '', week: '' },
  includeHeader: true, mappingRows: [{ id: 1, field: 'Wages', mapping: 'earnings',
    dataSetNo: 1, colSeqNo: 1, startPosition: '0', length: '0', recordType: 'Detail', defaultValue: '', format: '' }],
  mergeFiles: false, subscriptions: [{ id: 2, client: '204', email: 'fixture@example.invalid' }],
  fileSettings: { sortingOrder: [], conditionalStatements: [] },
  wageMappings: [{ clientId: 204, wageColumn: 'OTW', payCode: 'OT', searchWord: '' }],
  grouping: [], queryLocked: mode === 'edit',
})

test('payroll navigation opens its dashboard with the same job controls', () => {
  const html = render('/payroll-builder')
  assert.match(html, /<h1>Payroll Builder<\/h1>/)
  assert.match(html, /Payroll Builder<!-- --> scheduled jobs/)
  assert.match(html, />Active Jobs</)
  assert.match(html, />Disabled Jobs</)
  assert.match(html, />Add</)
  assert.match(html, />Edit</)
  assert.doesNotMatch(html, /mapped_payroll_columns_HDT.xlsx/)
  assert.match(html, /<button[^>]*>Template/)
  assert.doesNotMatch(html, /blank-page/)
})

test('retirement dashboard remains available separately', () => {
  const html = render('/retirement-builder')
  assert.match(html, /<h1>Retirement Builder<\/h1>/)
  assert.match(html, /href="\/mapped_payroll_columns_HDT.xlsx"/)
  assert.doesNotMatch(html, /id="payroll-wages-title"/)
})

test('payroll add wizard uses its own draft and general screen', () => {
  const html = render('/payroll-builder/jobs/new', {
    'ecs-payroll-builder-draft': draft('Payroll fixture'),
    'ecs-retirement-builder-draft': draft('Retirement fixture'),
  })
  assert.match(html, /value="Payroll fixture"/)
  assert.doesNotMatch(html, /value="Retirement fixture"/)
  assert.match(html, /Add New Job/)
  assert.match(html, /Output File Name Format/)
})

test('payroll subscriptions retain wage mappings without the grouping controls', () => {
  const html = render('/payroll-builder/jobs/new/subscriptions', { 'ecs-payroll-builder-draft': draft('Payroll fixture') })
  assert.match(html, /id="payroll-wages-title"/)
  assert.doesNotMatch(html, /id="payroll-grouping-title"/)
  assert.match(html, /aria-label="Earning code 1"/)
  assert.match(html, /aria-label="Wage field 1"/)
  assert.match(html, />Finish</)
})

test('existing payroll mapping controls remain editable even with an old locked draft', () => {
  const html = render('/payroll-builder/jobs/edit/mapping', { 'ecs-payroll-builder-draft': draft('Payroll fixture', 'edit') })
  assert.match(html, /Edit Job/)
  assert.doesNotMatch(html, /fieldset disabled="" class="control-fieldset"/)
  assert.doesNotMatch(html, /disabled=""[^>]*aria-label="Delete Wages mapping"/)
  assert.match(html, />Add Dataset</)
})

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
const { default: App, SaveConfirmation } = await vite.ssrLoadModule('/src/App.tsx')
after(async () => { await vite.close(); await rm(cacheDir, { recursive: true, force: true }) })

function render(path, drafts = {}, width = 1400) {
  const previousWindow = globalThis.window
  const previousStorage = globalThis.sessionStorage
  const previousFetch = globalThis.fetch
  globalThis.window = { innerWidth: width }
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

test('collapsed navigation retains accessible menu names and identifies the current builder', () => {
  for (const [path, label] of [['/payroll-builder', 'Payroll Builder'], ['/retirement-builder', 'Retirement Builder']]) {
    const html = render(path, {}, 390)
    assert.match(html, /sidebar-collapsed/)
    assert.match(html, /role="navigation" aria-label="Main navigation"/)
    assert.match(html, new RegExp(`aria-label="${label}" title="${label}" aria-current="page"`))
    assert.match(html, /aria-label="Benefits" title="Benefits"/)
    assert.match(html, /class="menu-label">Menu</)
  }
})

test('save confirmation announces success, escapes job text and provides a named dismissal', () => {
  const html = renderToString(React.createElement(SaveConfirmation, {
    message: 'Job <script>example</script> was updated successfully.', onDismiss: () => {},
  }))
  assert.match(html, /role="status" aria-atomic="true"/)
  assert.match(html, /Job saved/)
  assert.match(html, /&lt;script&gt;example&lt;\/script&gt;/)
  assert.doesNotMatch(html, /<script>/)
  assert.match(html, /aria-label="Dismiss save confirmation"/)
})

test('wizard buttons name the next step without the removed finish guidance', () => {
  const drafts = { 'ecs-payroll-builder-draft': draft('Payroll fixture') }
  assert.match(render('/payroll-builder/jobs/new', drafts), /Next: Schedule/)
  assert.match(render('/payroll-builder/jobs/new/mapping', drafts), /Next: Subscriptions/)
  assert.match(render('/payroll-builder/jobs/new/subscriptions', drafts), /Next: Wage Mappings/)
  assert.match(render('/payroll-builder/jobs/new/wage-mappings', drafts), />Finish</)
  assert.doesNotMatch(render('/payroll-builder/jobs/new/wage-mappings', drafts), /Review your wage mappings/)
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

test('payroll wage mappings move to step five for new and existing jobs', () => {
  for (const mode of ['add', 'edit']) {
  const path = mode === 'edit' ? 'edit' : 'new'
  const drafts = { 'ecs-payroll-builder-draft': draft('Payroll fixture', mode) }
  const subscriptions = render(`/payroll-builder/jobs/${path}/subscriptions`, drafts)
  assert.doesNotMatch(subscriptions, /id="payroll-wages-title"/)
  assert.match(subscriptions, /Next: Wage Mappings/)
  assert.doesNotMatch(subscriptions, />Finish</)
  const html = render(`/payroll-builder/jobs/${path}/wage-mappings`, drafts)
  assert.match(html, /aria-label="Step 5: Wage Mappings" aria-current="step"/)
  assert.match(html, /id="payroll-wages-title"/)
  assert.doesNotMatch(html, /id="payroll-grouping-title"/)
  assert.match(html, /aria-label="Earning code 1"/)
  assert.match(html, /aria-label="Wage field 1"/)
  assert.match(html, />Finish</)
  assert.match(html, />OT</)
  }
})

test('retirement subscriptions remain the fourth and final step', () => {
  const html = render('/jobs/new/subscriptions', { 'ecs-retirement-builder-draft': draft('Retirement fixture') })
  assert.doesNotMatch(html, /Step 5:/)
  assert.match(html, />Finish</)
})

test('existing payroll mapping controls remain editable even with an old locked draft', () => {
  const html = render('/payroll-builder/jobs/edit/mapping', { 'ecs-payroll-builder-draft': draft('Payroll fixture', 'edit') })
  assert.match(html, /Edit Job/)
  assert.doesNotMatch(html, /fieldset disabled="" class="control-fieldset"/)
  assert.doesNotMatch(html, /disabled=""[^>]*aria-label="Delete Wages mapping"/)
  assert.match(html, />Add Dataset</)
})

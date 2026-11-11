import { sha256 } from '@noble/hashes/sha2.js'
import { bytesToHex } from '@noble/hashes/utils.js'
import { ChangeEvent, FormEvent, KeyboardEvent as ReactKeyboardEvent, ReactNode, createContext, useContext, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { ChevronRight, CircleDot, Layers, Plus, Settings, Trash2, X } from 'lucide-react'
import {
  displayFileFormat, displayJobStatus, displayRunTime, emailAddresses, generalFieldErrors,
  isExcelFile, mappingColumnType, pasteEmailText, readExcelMappings, validEmail, validWholeNumber,
} from './retirementBuilder'

type Screen = 'dashboard' | 'general' | 'schedule' | 'mapping' | 'subscriptions' | 'placeholder'
type SideIcon = 'edit' | 'file' | 'copy'
type MappingRow = { id: number; field: string; startPosition: string; length: string; recordType: string; defaultValue: string; mapping: string; format: string }
type ApiMappingRow = { field?: string; startPosition?: string; length?: string; recordType?: string; defaultValue?: string; mappingColumn?: string; format?: string }
type ScheduleValues = { startDate: string; buildFrequency: string; hour: string; minute: string; meridiem: string; week: string }
type SortDirection = 'ASC' | 'DESC'
type SortingRow = { orderBy: string; mappingColumn: string; direction: SortDirection }
type ConditionalRow = { mappingColumn: string; condition: string; value: string }
type FileSettingsValues = { sortingOrder: SortingRow[]; conditionalStatements: ConditionalRow[] }
type JobsStatus = 'loading' | 'ready' | 'error'
type Subscription = { id: number; client: string; email: string; emailDraft?: string; baseClient: string }
type TableFilters = Record<number, string>
type DashboardJob = { id: number; values: string[] }
type JobRunFile = { fileName: string; csv: string }
type JobRun = JobRunFile & { runId: string; rowCount: number; storedRows: number; files?: JobRunFile[] }
type RetirementBuilderApiJob = { id: number; general?: { fileName?: string; fileFormat?: string; description?: string; outputFileNameFormat?: string; enable?: boolean; storeResultsToTable?: boolean; selectedFile?: string }; schedule?: { startDate?: string | null; week?: string; hour?: string; minute?: string; meridiem?: string; buildFrequency?: string }; mapping?: { includeHeader?: boolean; rows?: ApiMappingRow[] }; subscriptions?: { mergeFiles?: boolean; rows?: Array<{ client?: string; email?: string }> }; fileSettings?: { sortingOrder?: Partial<SortingRow>[]; conditionalStatements?: Partial<ConditionalRow>[] }; jobid?: number; jobfilename?: string; jobdesc?: string; filetype?: string; isEnabled?: boolean | number; ismerge?: boolean; runday?: string; runtime?: string; ScheduleType?: string; joblastmodified?: string | null; joblastrun?: string | null; Job_Last_Status?: string | null }
type RetirementBuilderOptions = { fileFormats: string[]; outputFileNameFormats: string[]; buildFrequencies: string[]; hours: string[]; minutes: string[]; meridiems: string[]; weekDays: string[]; recordTypes: string[]; sortDirections: SortDirection[]; mappingColumns: string[]; mappingColumnTypes: Record<string, string>; mappingFormatsByType: Record<string, string[]> }

const navigation: [SideIcon, string][] = [['edit', 'Benefits'], ['file', 'Mass Mutual Files'], ['copy', 'Process Validator'], ['copy', 'Retirement Builder'], ['edit', 'Prism'], ['copy', 'Services'], ['copy', 'Swipe Clock'], ['copy', 'Payroll Builder'], ['copy', 'NYS-45'], ['copy', 'Reports']]
const menuPaths: Record<string, string> = { Benefits: '/benefits', 'Mass Mutual Files': '/mass-mutual-files', 'Process Validator': '/process-validator', Prism: '/prism', Services: '/services', 'Swipe Clock': '/swipe-clock', 'Payroll Builder': '/payroll-builder', 'NYS-45': '/nys-45', Reports: '/reports' }
const menuTitles: Record<string, string> = Object.fromEntries(Object.entries(menuPaths).map(([label, path]) => [path, label]))
const apiBaseUrl = '/api/v1'
async function fetchRetirementJobs(signal?: AbortSignal): Promise<RetirementBuilderApiJob[]> {
  const response = await fetch(`${apiBaseUrl}/retirement-builder/jobs`, { signal })
  if (!response.ok) throw new Error('Unable to load Retirement Builder jobs')
  const jobs = await response.json() as RetirementBuilderApiJob[]
  return jobs.map(normalizeApiJob)
}
const emptyOptions: RetirementBuilderOptions = { fileFormats: [], outputFileNameFormats: [], buildFrequencies: [], hours: [], minutes: [], meridiems: [], weekDays: [], recordTypes: [], sortDirections: [], mappingColumns: [], mappingColumnTypes: {}, mappingFormatsByType: {} }
const OptionsContext = createContext({ values: emptyOptions, loading: true, error: '' })
function normalizeApiJob(raw: RetirementBuilderApiJob): RetirementBuilderApiJob { const id = Number(raw.id ?? raw.jobid); const runTime = raw.runtime?.match(/^(\d{1,2}):(\d{1,2})(?:\s+(AM|PM))?$/i); const scheduleType = ({ D: 'Daily', W: 'Weekly', B: 'Bi-Weekly', M: 'Monthly', MD: 'Monthly' } as Record<string, string>)[raw.ScheduleType ?? ''] ?? raw.ScheduleType; return { ...raw, id, general: { ...raw.general, fileName: raw.general?.fileName ?? raw.jobfilename, description: raw.general?.description ?? raw.jobdesc ?? '', fileFormat: raw.general?.fileFormat ?? raw.filetype, enable: raw.general?.enable ?? (raw.isEnabled === true || raw.isEnabled === 1), storeResultsToTable: raw.general?.storeResultsToTable ?? false }, schedule: raw.schedule ?? { week: raw.runday, buildFrequency: scheduleType, hour: runTime?.[1], minute: runTime?.[2], meridiem: runTime?.[3]?.toUpperCase() }, subscriptions: raw.subscriptions ?? { mergeFiles: raw.ismerge } } }
function toDashboardJob(rawJob: RetirementBuilderApiJob): DashboardJob {
  const job = normalizeApiJob(rawJob)
  const { general = {}, schedule = {} } = job
  const lastRunDate = job.joblastrun?.slice(0, 10) || ''
  return {
    id: job.id,
    values: [
      general.fileName || `Job ${job.id}`, general.description || '', job.joblastmodified?.slice(0, 10) || '',
      lastRunDate === '1900-01-01' ? '' : lastRunDate, schedule.week || '', displayRunTime(schedule.hour, schedule.minute, schedule.meridiem),
      schedule.buildFrequency || '', displayFileFormat(general.fileFormat),
      general.enable === false ? 'No' : 'Yes', displayJobStatus(job.Job_Last_Status),
    ],
  }
}
function toApiFileType(value: string): string { if (value.length <= 20) return value; if (value.includes('Pipe')) return 'CSV_PIPE'; if (value.includes('Tab')) return 'CSV_TAB'; if (value.includes('Semicolon')) return 'CSV_SEMI'; return 'CSV' }
function parseClientId(value: string): number | null { const match = value.trim().match(/^(\d+)/); if (!match) return null; const id = Number(match[1]); return Number.isSafeInteger(id) && id <= 2147483647 ? id : null }
let rowSequence = 0
const nextRowId = () => (rowSequence += 1)
const placeholderFormat = 'Select Format'
function toMappingRow(row: ApiMappingRow & { mapping?: string }): MappingRow { const format = row.format === placeholderFormat ? '' : row.format ?? ''; const mapping = row.mapping ?? row.mappingColumn ?? ''; return { id: nextRowId(), field: row.field ?? '', startPosition: row.startPosition ?? '', length: row.length ?? '', recordType: row.recordType ?? '', defaultValue: row.defaultValue ?? '', mapping, format } }
function normalizeMappingRows(rows: ApiMappingRow[] = []): MappingRow[] { return rows.map((row) => toMappingRow(row)) }
const newMappingRow = (): MappingRow => toMappingRow({ startPosition: '0', length: '0' })
const newSubscription = (): Subscription => ({ id: nextRowId(), client: '', email: '', baseClient: '' })
const toSubscription = (row: { client?: string; email?: string }): Subscription => ({ id: nextRowId(), client: row.client ?? '', email: row.email ?? '', baseClient: row.client ?? '' })
const makeInitialMappings = (): MappingRow[] => []
const scheduleDefaults: Omit<ScheduleValues, 'startDate'> = {
  buildFrequency: 'Weekly', hour: '4', minute: '00', meridiem: 'AM', week: 'Thursday',
}

function createDefaultSchedule(): ScheduleValues {
  const today = new Date()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return { ...scheduleDefaults, startDate: `${today.getFullYear()}-${month}-${day}` }
}
const emptyFileSettings: FileSettingsValues = { sortingOrder: [], conditionalStatements: [] }
const outputNameFormats = ['File Name', 'Client ID', 'Payday', 'File Name + Client ID', 'File Name + Payday', 'Client ID + Payday', 'File Name + Client ID + Payday']
const addPaths: Record<Screen, string> = { dashboard: '/retirement-builder', general: '/jobs/new', schedule: '/jobs/new/schedule', mapping: '/jobs/new/mapping', subscriptions: '/jobs/new/subscriptions', placeholder: '/placeholder' }
const editPaths: Record<Screen, string> = { dashboard: '/retirement-builder', general: '/jobs/edit/general', schedule: '/jobs/edit/schedule', mapping: '/jobs/edit/mapping', subscriptions: '/jobs/edit/subscriptions', placeholder: '/placeholder' }

function screenFromPath(path: string): Screen { if (path === '/retirement-builder') return 'dashboard'; if (path === '/jobs/new' || path === '/jobs/edit/general') return 'general'; if (path === '/jobs/new/schedule' || path === '/jobs/edit/schedule') return 'schedule'; if (path === '/jobs/new/mapping' || path === '/jobs/edit/mapping') return 'mapping'; if (path === '/jobs/new/subscriptions' || path === '/jobs/edit/subscriptions') return 'subscriptions'; return 'placeholder' }

function SearchableSelect({
  options, defaultValue = '', value: controlledValue, onValueChange, ariaLabel, errorId,
  clearLabel, allowCustom = false, includeSavedOption = true,
}: {
  options: string[]
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  ariaLabel: string
  errorId?: string
  clearLabel?: string
  allowCustom?: boolean
  includeSavedOption?: boolean
}) {
  const root = useRef<HTMLSpanElement>(null); const menu = useRef<HTMLDivElement>(null); const trigger = useRef<HTMLButtonElement>(null); const listId = useId(); const [internalValue, setInternalValue] = useState(defaultValue); const value = controlledValue ?? internalValue; const [query, setQuery] = useState(''); const [open, setOpen] = useState(false); const [activeIndex, setActiveIndex] = useState(0); const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({})
  const { values: runtimeOptions, loading: runtimeOptionsLoading, error: runtimeOptionsError } = useContext(OptionsContext)
  const apiOptions = ariaLabel === 'File format' ? runtimeOptions.fileFormats : ariaLabel === 'Output file name format' ? runtimeOptions.outputFileNameFormats : ariaLabel === 'Build frequency' ? runtimeOptions.buildFrequencies : ariaLabel === 'Hour' ? runtimeOptions.hours : ariaLabel === 'Minute' ? runtimeOptions.minutes : ariaLabel === 'AM or PM' ? runtimeOptions.meridiems : ariaLabel === 'Week' ? runtimeOptions.weekDays : ariaLabel.endsWith('record type') ? runtimeOptions.recordTypes : options
  const effectiveOptions = [...new Set([
    ...(clearLabel ? [''] : []),
    ...(includeSavedOption && controlledValue ? [controlledValue] : []),
    ...apiOptions,
  ])]
  const search = query.trim()
  const customOption = allowCustom && search && !effectiveOptions.some((option) => option.toLowerCase() === search.toLowerCase())
    ? search : ''
  const filteredOptions = effectiveOptions.filter((option) => (option || clearLabel || '').toLowerCase().includes(search.toLowerCase()))
  if (customOption) filteredOptions.push(customOption)
  useEffect(() => { const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) { setOpen(false); setQuery('') } }; document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close) }, [])
  useLayoutEffect(() => { if (!open) return undefined; const position = () => { const rect = root.current?.getBoundingClientRect(); if (!rect) return; const width = Math.min(Math.max(rect.width, 320), window.innerWidth - 16); const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)); const availableBelow = window.innerHeight - rect.bottom - 8; const availableAbove = rect.top - 8; const openUp = availableBelow < 340 && availableAbove > availableBelow; const maxHeight = Math.max(150, Math.min(270, openUp ? availableAbove : availableBelow)); setMenuStyle({ position: 'fixed', zIndex: 1000, left, width, maxWidth: 'calc(100vw - 16px)', maxHeight, ...(openUp ? { top: 'auto', bottom: window.innerHeight - rect.top + 5 } : { top: rect.bottom + 5, bottom: 'auto' }) }) }; position(); window.addEventListener('resize', position); window.addEventListener('scroll', position, true); return () => { window.removeEventListener('resize', position); window.removeEventListener('scroll', position, true) } }, [open])
  useEffect(() => { if (open) menu.current?.querySelector('[data-active="true"]')?.scrollIntoView?.({ block: 'nearest' }) }, [open, activeIndex])
  const closeMenu = (restoreFocus = false) => { setOpen(false); setQuery(''); if (restoreFocus) trigger.current?.focus() }
  const choose = (option: string, restoreFocus = false) => { if (controlledValue === undefined) setInternalValue(option); onValueChange?.(option); closeMenu(restoreFocus) }
  const openMenu = () => { setQuery(''); setActiveIndex(Math.max(0, effectiveOptions.indexOf(value))); setOpen(true) }
  const onTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => { if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) { event.preventDefault(); openMenu() } }
  const onMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => { if (event.key === 'Escape') { event.preventDefault(); closeMenu(true) } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); if (filteredOptions.length) setActiveIndex((index) => (index + (event.key === 'ArrowDown' ? 1 : -1) + filteredOptions.length) % filteredOptions.length) } else if (event.key === 'Enter' && (event.target as HTMLElement).tagName === 'INPUT') { event.preventDefault(); const option = filteredOptions[activeIndex]; if (option !== undefined) choose(option, true) } }
  return <span className="searchable-select" ref={root}><button type="button" ref={trigger} className="searchable-select-trigger" aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? listId : undefined} aria-label={ariaLabel} aria-invalid={!!errorId} aria-describedby={errorId} onKeyDown={onTriggerKeyDown} onClick={() => { if (open) setOpen(false); else openMenu() }}><span className={value ? '' : 'placeholder'}>{value || clearLabel || 'Select Format'}</span><span className="select-chevron" aria-hidden="true">⌄</span></button>{open && createPortal(<div className="searchable-select-menu" id={listId} ref={menu} style={menuStyle} role="listbox" onKeyDown={onMenuKeyDown}><input autoFocus className="searchable-select-search" value={query} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0) }} placeholder={allowCustom ? "Search or enter a source column…" : "Search…"} maxLength={allowCustom ? 255 : undefined} aria-label={`Search ${ariaLabel}`} aria-controls={listId} aria-activedescendant={filteredOptions.length ? `${listId}-${activeIndex}` : undefined} />{filteredOptions.length ? filteredOptions.map((option, index) => <button type="button" role="option" id={`${listId}-${index}`} data-active={index === activeIndex} aria-selected={option === value} className={`searchable-select-option ${option === value ? 'selected' : ''} ${index === activeIndex ? 'active' : ''}`} key={option} onClick={() => choose(option, true)}>{option && option === customOption ? `Use “${option}”` : option || clearLabel}</button>) : <span className="searchable-select-empty">{runtimeOptionsError || (runtimeOptionsLoading ? 'Loading options…' : 'No matches')}</span>}</div>, document.body)}</span>
}

const subscriptionEmails = (row: Subscription) => [...new Set([...emailAddresses(row.email), ...emailAddresses(row.emailDraft ?? '')])]

function EmailTagsInput({ value, draft, onChange, ariaLabel, validate }: {
  value: string
  draft: string
  onChange: (email: string, draft: string) => void
  ariaLabel: string
  validate: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const errorId = useId()
  const [attempted, setAttempted] = useState(false)
  const emails = emailAddresses(value)
  const invalid = emails.some((email) => !validEmail(email))
    || ((validate || attempted) && emailAddresses(draft).some((email) => !validEmail(email)))
  const addEmails = (raw: string) => {
    const additions = emailAddresses(raw)
    setAttempted(true)
    if (additions.some((email) => !validEmail(email))) {
      onChange(value, raw)
      return
    }
    onChange([...new Set([...emails, ...additions])].join(', '), '')
  }
  const removeEmail = (email: string) => onChange(emails.filter((item) => item !== email).join(', '), draft)

  return <>
    <div className="email-tags-input" onClick={() => inputRef.current?.focus()}>
      <div className="email-tags-list">
        {emails.map((email) => <span className="email-tag" key={email}>{email}<button type="button" className="email-tag-remove" onClick={(event) => { event.stopPropagation(); removeEmail(email) }} aria-label={`Remove ${email}`}><X aria-hidden="true" /></button></span>)}
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => onChange(value, event.target.value)}
          onPaste={(event) => {
            const pasted = event.clipboardData.getData('text')
            if (!/[,;\n]/.test(pasted)) return
            event.preventDefault()
            const { value: current, selectionStart, selectionEnd } = event.currentTarget
            addEmails(pasteEmailText(current, pasted, selectionStart, selectionEnd))
          }}
          onKeyDown={(event) => {
            if (['Enter', ',', ';'].includes(event.key)) {
              event.preventDefault()
              addEmails(draft)
            } else if (event.key === 'Backspace' && !draft && emails.length) {
              removeEmail(emails[emails.length - 1])
            }
          }}
          onBlur={() => addEmails(draft)}
          aria-label={ariaLabel}
          aria-invalid={invalid}
          aria-describedby={invalid ? errorId : undefined}
          placeholder="Enter email address and press Enter"
        />
      </div>
    </div>
    {invalid && <span className="field-error" id={errorId} role="alert">Enter a valid email address.</span>}
  </>
}

const wizardSteps: Screen[] = ['general', 'schedule', 'mapping', 'subscriptions']
const earliestStartDate = '1753-01-01'
const draftKey = 'ecs-retirement-builder-draft'
type Draft = { mode: 'add' | 'edit'; jobId: number | null; enable: boolean; fileName: string; fileFormat: string; description: string; outputFileNameFormat: string; storeResultsToTable: boolean; selectedFile: string; schedule: ScheduleValues; includeHeader: boolean; mappingRows: MappingRow[]; mergeFiles: boolean; subscriptions: Subscription[]; fileSettings: FileSettingsValues }
function readDraft(mode: 'add' | 'edit'): Draft | null { try { const raw = sessionStorage.getItem(draftKey); if (!raw) return null; const draft = JSON.parse(raw) as Draft; if (draft.mode !== mode || (mode === 'edit' && typeof draft.jobId !== 'number')) return null; rowSequence = Math.max(rowSequence, ...draft.mappingRows.map((row) => row.id), ...draft.subscriptions.map((row) => row.id)); return draft } catch { return null } }
async function readSaveError(response: Response, fallback = 'Unable to save Retirement Builder job') {
  if (response.status === 404) return 'This Retirement Builder job no longer exists. Return to the dashboard and select it again.'
  try {
    const body = await response.json() as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      const details = body.detail.map(({ loc, msg }) => {
        const field = Array.isArray(loc) ? loc.slice(1).join('.') : ''
        return typeof msg === 'string' ? [field, msg].filter(Boolean).join(' — ') : ''
      }).filter(Boolean)
      if (details.length) return details.join(' ')
    }
  } catch { /* non-JSON error body */ }
  return response.status === 422 ? 'The submitted values were rejected by the server.' : fallback
}

const createAttemptKey = 'ecs-retirement-builder-create-attempt'
type CreateAttempt = { fingerprint: string; key: string }

function readCreateAttempt(): CreateAttempt | null {
  try { return JSON.parse(sessionStorage.getItem(createAttemptKey) ?? 'null') as CreateAttempt | null }
  catch { return null }
}

export default function App({ userEmail }: { userEmail: string }) {
  const location = useLocation(); const routerNavigate = useNavigate(); const screen = screenFromPath(location.pathname); const isEditFlow = location.pathname.startsWith('/jobs/edit/'); const isWizard = screen !== 'dashboard' && screen !== 'placeholder'
  const [initialDraft] = useState(() => isWizard ? readDraft(isEditFlow ? 'edit' : 'add') : null)
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 767); const [showSettings, setShowSettings] = useState(false); const [saveError, setSaveError] = useState(''); const [saving, setSaving] = useState(false); const savingRef = useRef(false)
  const [enable, setEnable] = useState(initialDraft?.enable ?? true); const [fileName, setFileName] = useState(initialDraft?.fileName ?? ''); const [fileFormat, setFileFormat] = useState(initialDraft?.fileFormat ?? ''); const [description, setDescription] = useState(initialDraft?.description ?? ''); const [outputFileNameFormat, setOutputFileNameFormat] = useState(initialDraft?.outputFileNameFormat ?? ''); const [storeResultsToTable, setStoreResultsToTable] = useState(initialDraft?.storeResultsToTable ?? false); const [selectedFile, setSelectedFile] = useState(initialDraft?.selectedFile ?? '')
  const [schedule, setSchedule] = useState<ScheduleValues>(() => initialDraft?.schedule ?? createDefaultSchedule()); const [includeHeader, setIncludeHeader] = useState(initialDraft?.includeHeader ?? true); const [mappingRows, setMappingRows] = useState<MappingRow[]>(() => initialDraft?.mappingRows ?? makeInitialMappings()); const [fileSettings, setFileSettings] = useState<FileSettingsValues>(initialDraft?.fileSettings ?? emptyFileSettings)
  const [mergeFiles, setMergeFiles] = useState(initialDraft?.mergeFiles ?? false); const [subscriptions, setSubscriptions] = useState<Subscription[]>(() => initialDraft?.subscriptions ?? [newSubscription()])
  const [retirementJobs, setRetirementJobs] = useState<RetirementBuilderApiJob[]>([]); const [jobsStatus, setJobsStatus] = useState<JobsStatus>('loading'); const [selectedJobId, setSelectedJobId] = useState<number | null>(initialDraft?.jobId ?? null); const [filters, setFilters] = useState<TableFilters>({}); const [options, setOptions] = useState({ values: emptyOptions, loading: true, error: '' })
  const [validatedSteps, setValidatedSteps] = useState<Partial<Record<Screen, boolean>>>({})
  const [uploadError, setUploadError] = useState('')
  const [importing, setImporting] = useState(false)
  const uploadRequest = useRef(0)
  const createAttempt = useRef<CreateAttempt | null>(null)
  const generalErrors = generalFieldErrors(fileName, fileFormat)
  const invalidGeneral = Object.values(generalErrors).some(Boolean)
  const scheduleErrors = {
    startDate: schedule.startDate && (!/^\d{4}-/.test(schedule.startDate) || schedule.startDate < earliestStartDate)
      ? 'Choose a date between 1753-01-01 and 9999-12-31.' : '',
    hour: validWholeNumber(schedule.hour, 1, 12) ? '' : 'Select an hour from 1 to 12.',
    minute: validWholeNumber(schedule.minute, 0, 59) ? '' : 'Select a minute from 00 to 59.',
  }
  const invalidMapping = mappingRows.some((row) => !validWholeNumber(row.startPosition) || !validWholeNumber(row.length))
  const awaitingJob = isWizard && isEditFlow && selectedJobId === null
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${apiBaseUrl}/retirement-builder/options`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Unable to load Retirement Builder options')
        return response.json() as Promise<RetirementBuilderOptions>
      })
      .then((values) => setOptions({ values: { ...emptyOptions, ...values }, loading: false, error: '' }))
      .catch(() => {
        if (!controller.signal.aborted) setOptions({ values: emptyOptions, loading: false, error: 'Unable to load Retirement Builder options.' })
      })
    return () => controller.abort()
  }, [])
  useEffect(() => {
    if (screen !== 'dashboard') return
    const controller = new AbortController()
    const refresh = async (initial = false) => {
      try {
        const jobs = await fetchRetirementJobs(controller.signal)
        if (!controller.signal.aborted) { setRetirementJobs(jobs); setJobsStatus('ready') }
      } catch {
        if (initial && !controller.signal.aborted) { setRetirementJobs([]); setJobsStatus('error') }
      }
    }
    setJobsStatus('loading')
    void refresh(true)
    const interval = window.setInterval(() => { if (!document.hidden) void refresh() }, 5000)
    return () => { controller.abort(); window.clearInterval(interval) }
  }, [screen])
  useEffect(() => { setSaveError(''); setShowSettings(false) }, [location.pathname])
  useEffect(() => { if (awaitingJob) routerNavigate('/retirement-builder', { replace: true }) }, [awaitingJob, routerNavigate])
  useEffect(() => { try { if (!isWizard) { sessionStorage.removeItem(draftKey); return } if (awaitingJob) return; const draft: Draft = { mode: isEditFlow ? 'edit' : 'add', jobId: selectedJobId, enable, fileName, fileFormat, description, outputFileNameFormat, storeResultsToTable, selectedFile, schedule, includeHeader, mappingRows, mergeFiles, subscriptions, fileSettings }; sessionStorage.setItem(draftKey, JSON.stringify(draft)) } catch { /* session storage unavailable: draft is simply not kept across refresh */ } }, [awaitingJob, description, enable, fileFormat, fileName, fileSettings, includeHeader, isEditFlow, isWizard, mappingRows, mergeFiles, outputFileNameFormat, schedule, selectedFile, selectedJobId, storeResultsToTable, subscriptions])
  useEffect(() => {
    if (isWizard && !awaitingJob && screen !== 'general' && invalidGeneral) {
      setValidatedSteps((current) => ({ ...current, general: true }))
      routerNavigate((isEditFlow ? editPaths : addPaths).general, { replace: true })
    }
  }, [awaitingJob, invalidGeneral, isEditFlow, isWizard, routerNavigate, screen])

  const clearCreateAttempt = () => {
    createAttempt.current = null
    try { sessionStorage.removeItem(createAttemptKey) } catch { /* storage unavailable */ }
  }

  const validateBefore = (target: number, edit = isEditFlow) => {
    if (target > 0 && importing) return false
    const invalid = [invalidGeneral, Object.values(scheduleErrors).some(Boolean), invalidMapping]
    const index = invalid.findIndex((failed, step) => failed && step < target)
    if (index === -1) return true
    const step = wizardSteps[index]
    setValidatedSteps((current) => ({ ...current, [step]: true }))
    routerNavigate((edit ? editPaths : addPaths)[step])
    return false
  }

  const navigate = (next: Screen, edit = isEditFlow) => {
    if (!validateBefore(wizardSteps.indexOf(next), edit)) return
    if (next === 'dashboard') {
      uploadRequest.current += 1
      setImporting(false)
    }
    routerNavigate((edit ? editPaths : addPaths)[next])
  }

  const importWorkbook = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    event.target.value = ''
    const request = ++uploadRequest.current
    setUploadError('')
    if (!isExcelFile(file)) {
      setImporting(false)
      setUploadError('Choose an Excel workbook ending in .xlsx or .xls.')
      return
    }

    setImporting(true)
    try {
      const fields = await readExcelMappings(file)
      if (request !== uploadRequest.current) return
      if (!fields.length) {
        setUploadError('The first worksheet has no mapping fields. Add fields and try again.')
        return
      }
      setMappingRows(fields.map((field) => toMappingRow({ ...field, startPosition: '0', length: '0' })))
      setSelectedFile(file.name)
    } catch {
      if (request === uploadRequest.current) setUploadError('Unable to read this workbook. Open it in Excel, save a valid copy, and try again.')
    } finally {
      if (request === uploadRequest.current) setImporting(false)
    }
  }
  const resetForm = () => { setSelectedJobId(null); setSaveError(''); setEnable(true); setFileName(''); setFileFormat(''); setDescription(''); setOutputFileNameFormat(''); setStoreResultsToTable(false); setSelectedFile(''); setSchedule(createDefaultSchedule()); setIncludeHeader(true); setMergeFiles(false); setSubscriptions([newSubscription()]); setMappingRows(makeInitialMappings()); setFileSettings(emptyFileSettings) }
  const loadJob = (job: RetirementBuilderApiJob) => { const general = job.general ?? {}; const jobSchedule = job.schedule ?? {}; setSelectedJobId(job.id); setSaveError(''); setEnable(general.enable !== false); setFileName(general.fileName ?? ''); setFileFormat(general.fileFormat ?? ''); setDescription(general.description ?? ''); setOutputFileNameFormat(general.outputFileNameFormat ?? ''); setStoreResultsToTable(Boolean(general.storeResultsToTable)); setSelectedFile(general.selectedFile ?? ''); setSchedule({ startDate: jobSchedule.startDate ?? '', buildFrequency: jobSchedule.buildFrequency ?? scheduleDefaults.buildFrequency, hour: jobSchedule.hour ?? scheduleDefaults.hour, minute: jobSchedule.minute ?? scheduleDefaults.minute, meridiem: jobSchedule.meridiem ?? scheduleDefaults.meridiem, week: jobSchedule.week ?? scheduleDefaults.week }); setIncludeHeader(job.mapping?.includeHeader ?? true); setMappingRows(normalizeMappingRows(job.mapping?.rows ?? [])); setMergeFiles(Boolean(job.subscriptions?.mergeFiles)); setSubscriptions((job.subscriptions?.rows ?? []).map(toSubscription)); setFileSettings({ sortingOrder: (job.fileSettings?.sortingOrder ?? []).map((row) => ({ orderBy: row.orderBy ?? '', mappingColumn: row.mappingColumn ?? '', direction: row.direction ?? 'ASC' })), conditionalStatements: (job.fileSettings?.conditionalStatements ?? []).map((row) => ({ mappingColumn: row.mappingColumn ?? '', condition: row.condition ?? '', value: row.value ?? '' })) }) }
  const startAdd = () => {
    clearCreateAttempt()
    setValidatedSteps({})
    setUploadError('')
    resetForm()
    navigate('general', false)
  }
  const startEdit = async (jobId: number) => { try { const response = await fetch(`${apiBaseUrl}/retirement-builder/jobs/${jobId}`); if (!response.ok) throw new Error(await readSaveError(response)); const job = normalizeApiJob(await response.json() as RetirementBuilderApiJob); loadJob(job); setValidatedSteps({}); setUploadError(''); navigate('general', true) } catch (error) { setSaveError(error instanceof Error ? error.message : 'Unable to load the selected Retirement Builder job') } }
  const saveJob = async () => {
    if (savingRef.current || !validateBefore(wizardSteps.length)) return
    if (isEditFlow && selectedJobId === null) {
      setSaveError('This job could not be found. Return to the dashboard and select it again.')
      return
    }
    setValidatedSteps((current) => ({ ...current, subscriptions: true }))
    setSaveError('')
    const clientIds = subscriptions.map((row) => parseClientId(row.client))
    if (clientIds.some((id) => id === null)) {
      setSaveError('Select a valid numeric client ID for every subscription row.')
      return
    }
    const emails = subscriptions.map(subscriptionEmails)
    if (emails.some((row) => row.some((email) => !validEmail(email)))) return

    const body = JSON.stringify({
      general: { fileName, fileFormat: toApiFileType(fileFormat), description, outputFileNameFormat, enable, storeResultsToTable },
      schedule: { ...schedule, startDate: schedule.startDate || null },
      mapping: { includeHeader, rows: mappingRows.map(({ field, startPosition, length, recordType, defaultValue, mapping, format }) => ({
        field, startPosition, length, recordType, defaultValue, mappingColumn: mapping, format,
      })) },
      subscriptions: { mergeFiles, rows: clientIds.map((id, index) => ({ client: String(id), email: emails[index].join(', ') })) },
      fileSettings,
    })
    savingRef.current = true
    setSaving(true)
    try {
      const isUpdate = selectedJobId !== null
      const endpoint = `${apiBaseUrl}/retirement-builder/jobs${isUpdate ? `/${selectedJobId}` : ''}`
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (!isUpdate) {
        const fingerprint = bytesToHex(sha256(new TextEncoder().encode(body)))
        const prior = createAttempt.current ?? readCreateAttempt()
        const attempt = prior?.fingerprint === fingerprint
          ? prior
          : { fingerprint, key: bytesToHex(crypto.getRandomValues(new Uint8Array(16))) }
        createAttempt.current = attempt
        try { sessionStorage.setItem(createAttemptKey, JSON.stringify(attempt)) } catch { /* in-memory retries still work */ }
        headers['Idempotency-Key'] = attempt.key
      }
      const response = await fetch(endpoint, { method: isUpdate ? 'PUT' : 'POST', headers, body })
      if (!response.ok) throw new Error(await readSaveError(response))
      let saved: RetirementBuilderApiJob
      try { saved = normalizeApiJob(await response.json() as RetirementBuilderApiJob) }
      catch { throw new Error('Unexpected response from the Retirement Builder service.') }
      if (!isUpdate) clearCreateAttempt()
      setSelectedJobId(saved.id)
      navigate('dashboard')
    } catch (error) {
      setSaveError(error instanceof TypeError ? 'Unable to reach the Retirement Builder service. Please try again.' : error instanceof Error ? error.message : 'Unable to save Retirement Builder job')
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }
  const updateFilter = (index: number, value: string) => setFilters((current) => value ? { ...current, [index]: value } : Object.fromEntries(Object.entries(current).filter(([key]) => Number(key) !== index)))
  const updateMappingRow = (id: number, patch: Partial<MappingRow>) => setMappingRows((rows) => rows.map((row) => row.id === id ? { ...row, ...patch } : row))
  const addMappingRow = () => setMappingRows((rows) => [...rows, newMappingRow()])
  const pageTitle = screen === 'placeholder' ? menuTitles[location.pathname] ?? '' : 'Retirement Builder'; const title = screen === 'dashboard' || screen === 'placeholder' ? '' : isEditFlow ? 'Edit Job' : 'Add New Job'; const userName = userEmail.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  const content = (() => {
    if (screen === 'dashboard') return <Dashboard jobs={retirementJobs.map(toDashboardJob)} status={jobsStatus} filters={filters} onFilterChange={updateFilter} onAdd={startAdd} onEdit={startEdit}
      onRunSettled={(id, result) => {
        if (result) setRetirementJobs((jobs) => jobs.map((job) => job.id === id ? { ...job, Job_Last_Status: result } : job))
        void fetchRetirementJobs().then(setRetirementJobs).catch(() => { /* Keep the current dashboard state. */ })
      }}
    />
    if (screen === 'placeholder') return <section className="blank-page" aria-label={`${pageTitle} blank page`} />
    if (awaitingJob) return null
    if (screen === 'general') return <GeneralStep
      fileName={fileName} fileFormat={fileFormat} description={description} outputFileNameFormat={outputFileNameFormat}
      enable={isEditFlow ? enable : undefined} onEnableChange={setEnable}
      storeResultsToTable={storeResultsToTable} selectedFile={selectedFile} importing={importing} uploadError={uploadError}
      errors={validatedSteps.general ? generalErrors : undefined}
      onFileNameChange={setFileName} onFileFormatChange={setFileFormat} onDescriptionChange={setDescription}
      onOutputFileNameFormatChange={setOutputFileNameFormat} onStoreResultsChange={setStoreResultsToTable}
      onFileChange={importWorkbook} onCancel={() => navigate('dashboard')}
      onSubmit={(event) => { event.preventDefault(); navigate('schedule') }}
    />
    if (screen === 'schedule') return <ScheduleStep schedule={schedule}
      errors={validatedSteps.schedule ? scheduleErrors : undefined}
      onChange={(patch) => setSchedule((current) => ({ ...current, ...patch }))}
      onBack={() => navigate('general')} onNext={() => navigate('mapping')}
    />
    if (screen === 'mapping') return <MappingStep includeHeader={includeHeader} rows={mappingRows}
      validate={!!validatedSteps.mapping} onHeaderChange={setIncludeHeader} onRowChange={updateMappingRow}
      onDelete={(id) => setMappingRows((rows) => rows.filter((row) => row.id !== id))}
      onOpenSettings={() => setShowSettings(true)} onBack={() => navigate('schedule')} onNext={() => navigate('subscriptions')}
    />
    return <SubscriptionsStep mergeFiles={mergeFiles} subscriptions={subscriptions} error={saveError}
      saving={saving} validate={!!validatedSteps.subscriptions} onMergeChange={setMergeFiles}
      onClientChange={(id, client) => setSubscriptions((rows) => rows.map((row) => row.id === id ? { ...row, client } : row))}
      onEmailChange={(id, email, emailDraft) => setSubscriptions((rows) => rows.map((row) => row.id === id ? { ...row, email, emailDraft } : row))}
      onAdd={() => setSubscriptions((rows) => [...rows, newSubscription()])}
      onDelete={(id) => setSubscriptions((rows) => rows.filter((row) => row.id !== id))}
      onBack={() => navigate('mapping')} onFinish={saveJob}
    />
  })()
  return <OptionsContext.Provider value={options}><div className={`app-shell ${sidebarOpen ? 'sidebar-expanded' : 'sidebar-collapsed'}`}><header className="topbar"><div className="brand">ESC</div><button className="menu-button" onClick={() => setSidebarOpen((open) => !open)} aria-label="Toggle navigation">☰</button><div className="user-name">{userName}</div></header><div className="workspace"><Sidebar active={screen} onNavigate={navigate} onNavigatePath={routerNavigate} /><main className="main-content"><div className="page-heading"><h1>{pageTitle}</h1><div className="breadcrumb"><CircleDot className="breadcrumb-icon" aria-hidden="true" /><button type="button" className="breadcrumb-link" onClick={() => navigate('dashboard')}>SYD</button><ChevronRight className="breadcrumb-chevron" aria-hidden="true" /><span>{title}</span></div></div>{screen === 'dashboard' || screen === 'placeholder' ? content : <WizardCard title={title} activeStep={screen} onCancel={() => navigate('dashboard')} onNavigate={navigate} headerActions={screen === 'mapping' ? <button type="button" className="button button-primary" onClick={addMappingRow}><span className="button-icon"><ToolIcon name="plus" /></span>Add Dataset</button> : screen === 'general' && isEditFlow ? <button type="button" className="button button-light" onClick={() => navigate('dashboard')}>Cancel</button> : undefined}>{content}</WizardCard>}<footer><span>Copyright © 2026</span><strong>Employer Services Corporation.</strong><span>All rights reserved.</span></footer></main></div>{showSettings && <FileSettingsModal mappingRows={mappingRows} initialSorting={fileSettings.sortingOrder} initialConditional={fileSettings.conditionalStatements} onSave={(sortingOrder, conditionalStatements) => { setFileSettings({ sortingOrder, conditionalStatements }); setShowSettings(false) }} onClose={() => setShowSettings(false)} />}</div></OptionsContext.Provider>
}

function MenuIcon({ name }: { name: SideIcon }) { if (name === 'file') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3.5h9l5 5V20.5H5z" /><path d="M14 3.5v5h5" /></svg>; if (name === 'copy') return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="6.5" width="11" height="13" rx="1.5" /><path d="M8 6.5V4.8A1.8 1.8 0 0 1 9.8 3h9a1.8 1.8 0 0 1 1.8 1.8v9A1.8 1.8 0 0 1 18.8 15H15" /></svg>; return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 16.5-.7 3.2 3.2-.7L18.8 6.7a2.2 2.2 0 0 0-3.1-3.1z" /><path d="m14.7 5.3 4 4" /></svg> }
function Sidebar({ active, onNavigate, onNavigatePath }: { active: Screen; onNavigate: (screen: Screen) => void; onNavigatePath: (path: string) => void }) { return <aside className="sidebar">{navigation.map(([icon, label]) => <button className={`nav-item ${label === 'Retirement Builder' && active !== 'placeholder' ? 'active' : ''}`} key={label} onClick={() => label === 'Retirement Builder' ? onNavigate('dashboard') : onNavigatePath(menuPaths[label])}><span className="nav-icon"><MenuIcon name={icon} /></span><span>{label}</span>{['Benefits', 'Mass Mutual Files', 'Prism'].includes(label) && <span className="nav-chevron">‹</span>}</button>)}</aside> }
function ToolIcon({ name }: { name: 'layers' | 'plus' | 'trash' }) { if (name === 'plus') return <Plus aria-hidden="true" />; if (name === 'trash') return <Trash2 aria-hidden="true" />; return <Layers aria-hidden="true" /> }
function WizardCard({ title, activeStep, onCancel, onNavigate, headerActions, children }: { title: string; activeStep: Screen; onCancel: () => void; onNavigate: (screen: Screen) => void; headerActions?: ReactNode; children: ReactNode }) { const steps: { key: Screen; label: string }[] = [{ key: 'general', label: 'General' }, { key: 'schedule', label: 'Schedule' }, { key: 'mapping', label: 'Mapping' }, { key: 'subscriptions', label: 'Subscriptions' }]; return <><div className="wizard-steps-shell"><nav className="wizard-steps">{steps.map((step, index) => <button className={`wizard-step ${activeStep === step.key ? 'active' : ''}`} key={step.key} aria-current={activeStep === step.key ? 'step' : undefined} onClick={() => onNavigate(step.key)}><span className="step-number" aria-hidden="true">{index + 1}</span><span>{step.label}</span></button>)}</nav></div><section className="wizard-card"><div className="card-heading"><h2>{title}</h2><div className="card-heading-actions">{headerActions}{activeStep !== 'general' && <button className="button button-light" onClick={onCancel}>Cancel</button>}</div></div>{children}</section></> }
function Dashboard({ jobs, status, filters, onFilterChange, onAdd, onEdit, onRunSettled }: {
  jobs: DashboardJob[]
  status: JobsStatus
  filters: TableFilters
  onFilterChange: (index: number, value: string) => void
  onAdd: () => void
  onEdit: (jobId: number) => void
  onRunSettled: (jobId: number, result?: 'Success' | 'Failed') => void
}) {
  const headings = ['File Name', 'Description', 'Modified On', 'Last Run Date', 'Run Day', 'Run Time', 'Schedule Type', 'File Type', 'Is Active', 'Status']
  const [sort, setSort] = useState<{ index: number; direction: 'asc' | 'desc' } | null>(null)
  const [selectedJobs, setSelectedJobs] = useState<number[]>([])
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState('')
  const [runResult, setRunResult] = useState<JobRun | null>(null)
  const [downloads, setDownloads] = useState<{ fileName: string; url: string }[]>([])
  const selected = selectedJobs.length === 1 ? jobs.find((job) => job.id === selectedJobs[0]) : undefined
  const valueFor = (job: DashboardJob, index: number) => running && job.id === selected?.id && headings[index] === 'Status'
    ? 'In Progress' : job.values[index] ?? ''
  const sortedJobs = jobs.filter((job) => headings.every((_, index) =>
    valueFor(job, index).toLowerCase().includes((filters[index] ?? '').trim().toLowerCase())
  )).sort((left, right) => {
    if (!sort) return 0
    const comparison = valueFor(left, sort.index).localeCompare(valueFor(right, sort.index), undefined, { numeric: true, sensitivity: 'base' })
    return sort.direction === 'asc' ? comparison : -comparison
  })
  const allVisibleSelected = sortedJobs.length > 0 && sortedJobs.every((job) => selectedJobs.includes(job.id))
  const toggleSort = (index: number) => setSort((current) => current?.index === index
    ? { index, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { index, direction: 'asc' })
  const selectJob = (jobId: number) => {
    setSelectedJobs((current) => current.includes(jobId) ? current.filter((id) => id !== jobId) : [...current, jobId])
    setRunResult(null)
    setRunError('')
  }
  const toggleAll = () => {
    const visibleIds = sortedJobs.map((job) => job.id)
    setSelectedJobs((current) => allVisibleSelected
      ? current.filter((id) => !visibleIds.includes(id))
      : [...new Set([...current, ...visibleIds])])
    setRunResult(null)
    setRunError('')
  }
  const runSelectedJob = async () => {
    if (!selected || running) return
    setRunning(true)
    setRunResult(null)
    setRunError('')
    try {
      const response = await fetch(`${apiBaseUrl}/retirement-builder/jobs/${selected.id}/run`, { method: 'POST' })
      if (!response.ok) throw new Error(await readSaveError(response, 'Unable to run the job.'))
      setRunResult(await response.json() as JobRun)
      onRunSettled(selected.id, 'Success')
    } catch (cause) {
      setRunError(cause instanceof TypeError
        ? 'Unable to reach the Retirement Builder service.'
        : cause instanceof Error ? cause.message : 'Unable to run the job.')
      onRunSettled(selected.id, cause instanceof TypeError ? undefined : 'Failed')
    } finally {
      setRunning(false)
    }
  }
  useEffect(() => {
    const files = runResult?.files ?? (runResult?.fileName ? [runResult] : [])
    const links = files.map(({ fileName, csv }) => ({
      fileName, url: URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })),
    }))
    setDownloads(links)
    return () => links.forEach(({ url }) => URL.revokeObjectURL(url))
  }, [runResult])

  return <section className="dashboard-card">
    <div className="dashboard-actions">
      <p className="dashboard-scope">Showing enabled jobs only.</p>
      <a className="button button-primary" href="/mapped_payroll_columns_HDT.xlsx" download="mapped_payroll_columns_HDT.xlsx">Template <span aria-hidden="true">⇩</span></a>
      <button className="button button-primary" onClick={onAdd}>Add</button>
      <button className="button button-primary" disabled={!selected} onClick={() => selected && onEdit(selected.id)}>Edit</button>
      <button className="button button-primary" disabled={!selected || running} onClick={runSelectedJob}>
        {running ? 'Running…' : 'Run'}
      </button>
    </div>
    {runError && <p className="dashboard-action-message" role="alert">{runError}</p>}
    {runResult && <div className="dashboard-action-message" role="status">
      Generated {runResult.rowCount} rows. Saved {runResult.storedRows} rows to the database.
      {downloads.length === 1 && <> <a href={downloads[0].url} download={downloads[0].fileName}>Download CSV</a></>}
      {downloads.length > 1 && <div className="report-downloads">
        {downloads.map(({ fileName, url }) => <a key={fileName} href={url} download={fileName}>{fileName}</a>)}
      </div>}
    </div>}
    <div className="jobs-table-wrap">
      <table className="jobs-table">
        <caption className="sr-only">Retirement Builder scheduled jobs</caption>
        <thead><tr>
          <th scope="col" className="jobs-select-column"><input type="checkbox" checked={allVisibleSelected} onChange={toggleAll} disabled={running} aria-label="Select all visible jobs" /></th>
          {headings.map((heading, index) => <th scope="col" key={heading} aria-sort={sort?.index === index ? sort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
            <div className="table-heading-sort">
              <button type="button" className="table-sort-button" onClick={() => toggleSort(index)} aria-label={`Sort by ${heading}`}>{heading}<span aria-hidden="true">{sort?.index === index ? sort.direction === 'asc' ? ' ↑' : ' ↓' : ' ↕'}</span></button>
              <input value={filters[index] ?? ''} onChange={(event) => onFilterChange(index, event.target.value)} aria-label={`Filter ${heading}`} />
            </div>
          </th>)}
        </tr></thead>
        <tbody>{sortedJobs.length ? sortedJobs.map((job) => <tr key={job.id} className={selectedJobs.includes(job.id) ? 'selected-row' : undefined}>
          <td className="jobs-select-cell"><input type="checkbox" checked={selectedJobs.includes(job.id)} onChange={() => selectJob(job.id)} disabled={running} aria-label={`Select ${job.values[0]}`} /></td>
          {headings.map((_, index) => <td key={index} className={index === 9 ? 'status-cell' : ''}>
            {index === 0 ? <button type="button" className="file-name-link" onClick={() => onEdit(job.id)}>{valueFor(job, index)}</button> : valueFor(job, index)}
          </td>)}
        </tr>) : <tr><td className="empty-table" colSpan={headings.length + 1} role={status === 'error' ? 'alert' : undefined}>
          {status === 'error' ? 'Unable to load Retirement Builder jobs. Please try again.' : status === 'loading' ? 'Loading…' : 'No matching records found'}
        </td></tr>}</tbody>
      </table>
    </div>
  </section>
}
function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <span className="field-error" id={id} role="alert">{message}</span> : null
}

function GeneralStep({
  fileName, fileFormat, description, outputFileNameFormat, enable, onEnableChange, storeResultsToTable, selectedFile,
  importing, uploadError, errors, onFileNameChange, onFileFormatChange, onDescriptionChange,
  onOutputFileNameFormatChange, onStoreResultsChange, onFileChange, onCancel, onSubmit,
}: {
  fileName: string
  fileFormat: string
  description: string
  outputFileNameFormat: string
  enable?: boolean
  onEnableChange: (value: boolean) => void
  storeResultsToTable: boolean
  selectedFile: string
  importing: boolean
  uploadError: string
  errors?: { fileName: string; fileFormat: string }
  onFileNameChange: (value: string) => void
  onFileFormatChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  onOutputFileNameFormatChange: (value: string) => void
  onStoreResultsChange: (value: boolean) => void
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void
  onCancel: () => void
  onSubmit: (event: FormEvent) => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  return <form className="form-step general-step" onSubmit={onSubmit} noValidate>
    <div className="general-form-content">
      <div className="general-fields">
        <div className="general-field">
          <label htmlFor="retirement-file-name">File Name</label>
          <input id="retirement-file-name" value={fileName} required aria-invalid={!!errors?.fileName}
            aria-describedby={errors?.fileName ? 'retirement-file-name-error' : undefined}
            onChange={(event) => onFileNameChange(event.target.value)} />
          <FieldError id="retirement-file-name-error" message={errors?.fileName} />
        </div>
        <div className="general-field">
          <span>File Format</span>
          <SearchableSelect options={[]} value={fileFormat} onValueChange={onFileFormatChange} ariaLabel="File format"
            errorId={errors?.fileFormat ? 'retirement-file-format-error' : undefined} />
          <FieldError id="retirement-file-format-error" message={errors?.fileFormat} />
        </div>
        <label className="general-field general-field-full">Description<textarea value={description} onChange={(event) => onDescriptionChange(event.target.value)} /></label>
        <label className="general-field general-field-full">Output File Name Format<SearchableSelect options={outputNameFormats} value={outputFileNameFormat} onValueChange={onOutputFileNameFormatChange} ariaLabel="Output file name format" /></label>
      </div>
      <section className="general-option-section">
        <div className="general-options">
          {enable !== undefined && <label className="general-option">
            <input type="checkbox" checked={enable} onChange={(event) => onEnableChange(event.target.checked)} />
            <span>{enable ? 'Enable' : 'Disable'}</span>
          </label>}
          <label className="general-option"><input type="checkbox" checked={storeResultsToTable} onChange={(event) => onStoreResultsChange(event.target.checked)} /><span>Store Results to Table</span></label>
        </div>
      </section>
      <section className="general-upload-section" aria-labelledby="upload-file-heading">
        <div className="general-section-heading"><h3 id="upload-file-heading">File</h3></div>
        <div className="general-upload-zone" aria-busy={importing}>
          <span className="upload-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 3.5h9l5 5V20.5H5z" /><path d="M14 3.5v5h5" /><path d="M12 16V4m0 0 2.5 2.5M12 11l-2.5 2.5" /></svg></span>
          <div className="upload-copy">
            <strong>{importing ? 'Reading workbook…' : selectedFile && !uploadError ? selectedFile : 'Choose an Excel workbook'}</strong>
            <span>{selectedFile && !importing && !uploadError ? 'Mapping fields imported. Only the mappings are saved with the job.' : 'Import mapping fields from an .xlsx or .xls workbook. Only the mappings are saved with the job.'}</span>
          </div>
          <input ref={fileInputRef} type="file" accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel" onChange={onFileChange} aria-labelledby="upload-file-heading" />
          <button type="button" className="button button-light" onClick={() => fileInputRef.current?.click()}
            aria-describedby={uploadError ? 'retirement-workbook-error' : undefined}>Browse Files</button>
        </div>
        <FieldError id="retirement-workbook-error" message={uploadError} />
      </section>
    </div>
    <div className="general-form-actions">
      <button className="button button-light" type="button" onClick={onCancel}>Cancel</button>
      <button className="button button-primary" type="submit" disabled={importing}>Next</button>
    </div>
  </form>
}

function ScheduleStep({ schedule, errors, onChange, onBack, onNext }: {
  schedule: ScheduleValues
  errors?: { startDate: string; hour: string; minute: string }
  onChange: (patch: Partial<ScheduleValues>) => void
  onBack: () => void
  onNext: () => void
}) {
  return <div className="form-step schedule-step">
    <div className="schedule-form-content">
      <div className="general-section-heading"><h3>Schedule Details</h3></div>
      <div className="schedule-fields">
        <div className="schedule-field">
          <label htmlFor="retirement-start-date">Start Date</label>
          <input id="retirement-start-date" type="date" min={earliestStartDate} max="9999-12-31" value={schedule.startDate}
            aria-invalid={!!errors?.startDate} aria-describedby={errors?.startDate ? 'retirement-start-date-error' : undefined}
            onInput={(event) => onChange({ startDate: event.currentTarget.value })}
            onChange={(event) => onChange({ startDate: event.currentTarget.value })} />
          <FieldError id="retirement-start-date-error" message={errors?.startDate} />
        </div>
        <label className="schedule-field">Build Frequency<SearchableSelect options={[]} value={schedule.buildFrequency} onValueChange={(buildFrequency) => onChange({ buildFrequency })} ariaLabel="Build frequency" /></label>
        <fieldset className="schedule-time-field">
          <legend>Time</legend>
          <div className="time-row">
            <SearchableSelect options={[]} value={schedule.hour} onValueChange={(hour) => onChange({ hour })} ariaLabel="Hour" errorId={errors?.hour ? 'retirement-hour-error' : undefined} />
            <SearchableSelect options={[]} value={schedule.minute} onValueChange={(minute) => onChange({ minute })} ariaLabel="Minute" errorId={errors?.minute ? 'retirement-minute-error' : undefined} />
            <SearchableSelect options={[]} value={schedule.meridiem} onValueChange={(meridiem) => onChange({ meridiem })} ariaLabel="AM or PM" />
          </div>
          <FieldError id="retirement-hour-error" message={errors?.hour} />
          <FieldError id="retirement-minute-error" message={errors?.minute} />
        </fieldset>
        <label className="schedule-field schedule-field-full">Week<SearchableSelect options={[]} value={schedule.week} onValueChange={(week) => onChange({ week })} ariaLabel="Week" /></label>
      </div>
    </div>
    <div className="step-footer"><button className="button button-light" onClick={onBack}>Back</button><button className="button button-primary" onClick={onNext}>Next</button></div>
  </div>
}

function MappingNumber({ label, value, onChange, validate }: {
  label: string; value: string; onChange: (value: string) => void; validate: boolean
}) {
  const errorId = useId()
  const invalid = validate && !validWholeNumber(value)
  return <><input aria-label={label} value={value} inputMode="numeric" aria-invalid={invalid}
    aria-describedby={invalid ? errorId : undefined} onChange={(event) => onChange(event.target.value)} />
    <FieldError id={errorId} message={invalid ? 'Enter a whole number from 0 to 2147483647.' : undefined} /></>
}

function MappingStep({ includeHeader, rows, validate, onHeaderChange, onRowChange, onDelete, onOpenSettings, onBack, onNext }: {
  includeHeader: boolean
  rows: MappingRow[]
  validate: boolean
  onHeaderChange: (checked: boolean) => void
  onRowChange: (id: number, patch: Partial<MappingRow>) => void
  onDelete: (id: number) => void
  onOpenSettings: () => void
  onBack: () => void
  onNext: () => void
}) {
  const { values } = useContext(OptionsContext)
  const columnNames = new Map<string, string>()
  for (const name of [...values.mappingColumns, ...rows.map((row) => row.field.trim())]) {
    if (name && !columnNames.has(name.toLowerCase())) columnNames.set(name.toLowerCase(), name)
  }
  const columns = Array.from(columnNames.values())
  const formatsFor = (column: string) => values.mappingFormatsByType[mappingColumnType(column, values.mappingColumnTypes)] ?? []

  return <div className="form-step mapping-step">
    <div className="mapping-sticky-toolbar">
      <div className="mapping-header">
        <div><h3>Dataset Mapping</h3><p>Map source fields to the output columns used by this file.</p></div>
        <div className="mapping-header-actions">
          <label className="check-label"><input type="checkbox" checked={includeHeader} onChange={(event) => onHeaderChange(event.target.checked)} />Include Header Row</label>
        </div>
      </div>
      <div className="mapping-actions">
        <button type="button" className="icon-button" onClick={onOpenSettings} aria-label="Manage dataset settings" title="Manage dataset settings"><Settings aria-hidden="true" /></button>
        <button className="icon-button" onClick={onOpenSettings} aria-label="Add mapping rule" title="Add mapping rule"><ToolIcon name="plus" /></button>
      </div>
    </div>
    <div className="mapping-table-wrap">
      <table className="mapping-table">
        <thead><tr>{['Field Name', 'Start Position', 'Length', 'Record Type', 'Default Value', 'Mapping Column', 'Format', 'Action'].map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => {
          const label = row.field || 'New'
          const formats = formatsFor(row.mapping || row.field)
          const changeSource = (patch: Pick<MappingRow, 'field'> | Pick<MappingRow, 'mapping'>) => {
            const next = { ...row, ...patch }
            const typeChanged = mappingColumnType(row.mapping || row.field, values.mappingColumnTypes)
              !== mappingColumnType(next.mapping || next.field, values.mappingColumnTypes)
            const format = typeChanged && !formatsFor(next.mapping || next.field).includes(row.format) ? '' : row.format
            onRowChange(row.id, { ...patch, format })
          }
          return <tr key={row.id}>
            <td><input aria-label={`Field Name ${index + 1}`} value={row.field} onChange={(event) => changeSource({ field: event.target.value })} /></td>
            <td><MappingNumber label={`${row.field} start position`} value={row.startPosition} validate={validate} onChange={(startPosition) => onRowChange(row.id, { startPosition })} /></td>
            <td><MappingNumber label={`${row.field} length`} value={row.length} validate={validate} onChange={(length) => onRowChange(row.id, { length })} /></td>
            <td><SearchableSelect options={['Header', 'Detail', 'Trailer']} value={row.recordType} onValueChange={(recordType) => onRowChange(row.id, { recordType })} ariaLabel={`${label} record type`} /></td>
            <td><input aria-label={`${row.field} default value`} value={row.defaultValue} onChange={(event) => onRowChange(row.id, { defaultValue: event.target.value })} /></td>
            <td><SearchableSelect options={columns} value={row.mapping} onValueChange={(mapping) => changeSource({ mapping })}
              ariaLabel={`${label} mapping column`} clearLabel="Same as Field Name" allowCustom /></td>
            <td><SearchableSelect options={formats} value={row.format} onValueChange={(format) => onRowChange(row.id, { format })}
              ariaLabel={`${label} format`} clearLabel="No format" includeSavedOption={false} /></td>
            <td><button className="icon-button trash" onClick={() => onDelete(row.id)} aria-label={`Delete ${row.field} mapping`} title={`Delete ${row.field} mapping`}><ToolIcon name="trash" /></button></td>
          </tr>
        })}</tbody>
      </table>
    </div>
    <div className="step-footer"><button className="button button-light" onClick={onBack}>Back</button><button className="button button-primary" onClick={onNext}>Next</button></div>
  </div>
}

function SubscriptionsStep({ mergeFiles, subscriptions, error, saving, validate, onMergeChange, onClientChange, onEmailChange, onAdd, onDelete, onBack, onFinish }: { mergeFiles: boolean; subscriptions: Subscription[]; error: string; saving: boolean; validate: boolean; onMergeChange: (checked: boolean) => void; onClientChange: (id: number, client: string) => void; onEmailChange: (id: number, email: string, draft: string) => void; onAdd: () => void; onDelete: (id: number) => void; onBack: () => void; onFinish: () => void }) { return <div className="form-step subscriptions-step"><div className="subscription-toolbar"><label className="check-label"><input type="checkbox" checked={mergeFiles} onChange={(event) => onMergeChange(event.target.checked)} />Merge Files</label><button className="button button-primary" onClick={onAdd}><span className="button-icon"><ToolIcon name="plus" /></span>Add Row</button></div>{error && <p className="dashboard-action-message" role="alert">{error}</p>}<div className="subscription-table-wrap"><table className="subscription-table"><thead><tr><th scope="col">Clients</th><th scope="col">Mail</th><th scope="col">Action</th></tr></thead><tbody>{subscriptions.map((subscription, index) => <tr key={subscription.id}><td><SearchableSelect options={[subscription.baseClient, '000720 - UBMD Pediatrics'].filter(Boolean)} value={subscription.client} onValueChange={(client) => onClientChange(subscription.id, client)} ariaLabel={`Client ${index + 1}`} /></td><td><EmailTagsInput value={subscription.email} draft={subscription.emailDraft ?? ''} validate={validate} onChange={(email, draft) => onEmailChange(subscription.id, email, draft)} ariaLabel={`Email ${index + 1}`} /></td><td><button className="icon-button trash" onClick={() => onDelete(subscription.id)} aria-label={`Delete subscription ${index + 1}`} title={`Delete subscription ${index + 1}`}><ToolIcon name="trash" /></button></td></tr>)}</tbody></table></div><div className="step-footer"><button className="button button-light" onClick={onBack}>Back</button><button className="button button-primary" onClick={onFinish} disabled={saving}>Finish</button></div></div> }
function FileSettingsModal({ mappingRows, initialSorting, initialConditional, onSave, onClose }: {
  mappingRows: MappingRow[]
  initialSorting: SortingRow[]
  initialConditional: ConditionalRow[]
  onSave: (sortingOrder: SortingRow[], conditionalStatements: ConditionalRow[]) => void
  onClose: () => void
}) {
  const { values } = useContext(OptionsContext)
  const columnNames = new Map<string, string>()
  for (const name of [...mappingRows.map((row) => row.mapping.trim() || row.field.trim()), ...values.mappingColumns]) {
    if (name && !columnNames.has(name.toLowerCase())) columnNames.set(name.toLowerCase(), name)
  }
  const mappingColumns = Array.from(columnNames.values())
  const [sortingRows, setSortingRows] = useState(() => initialSorting.map((row) => [row.direction ?? 'ASC', row.mappingColumn, row.orderBy]))
  const [conditionalRows, setConditionalRows] = useState(() => initialConditional.map((row) => [row.mappingColumn, row.condition, row.value]))
  const [sortError, setSortError] = useState('')
  const dialog = useRef<HTMLElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  const saveRows = () => {
    if (sortingRows.some((row) => !row[1]?.trim())) {
      setSortError('Choose a mapping column for each sort rule.')
      return
    }
    onSave(
      sortingRows.map(([direction, mappingColumn, orderBy]) => ({
        orderBy, mappingColumn, direction: direction === 'DESC' ? 'DESC' : 'ASC',
      })),
      conditionalRows.map(([mappingColumn, condition, value]) => ({ mappingColumn, condition, value })),
    )
  }

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    dialog.current?.focus()
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.defaultPrevented) return
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); return }
      if (event.key !== 'Tab' || !dialog.current) return
      const focusable = Array.from(dialog.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled])'))
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (!dialog.current.contains(document.activeElement) || (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); previous?.focus() }
  }, [])

  return <div className="modal-backdrop" onClick={onClose}>
    <section className="settings-modal" ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-label="File Settings" onClick={(event) => event.stopPropagation()}>
      <div className="modal-header">
        <h2>File Settings:</h2>
        <div>
          <button type="button" className="button button-light" onClick={onClose}>Cancel</button>
          <button type="button" className="button button-light" onClick={() => { setSortingRows([]); setConditionalRows([]); setSortError('') }}>Clear</button>
          <button type="button" className="button button-primary" onClick={saveRows}>Save &amp; Continue</button>
        </div>
      </div>
      {sortError && <p className="field-error" role="alert">{sortError}</p>}
      <SettingsTable
        title="Sorting Order:"
        description="Sort by these columns from top to bottom."
        columns={['Order By', 'Mapping Column', 'Action']}
        mappingColumns={mappingColumns}
        sortDirections={values.sortDirections}
        rows={sortingRows}
        onAdd={() => setSortingRows((rows) => {
          const nextPriority = rows.reduce((max, row) => Math.max(max, Number(row[2])), 0) + 1
          if (nextPriority <= 2147483647) return [...rows, ['ASC', '', String(nextPriority)]]
          return [...rows, ['ASC', '', '']].map(([direction, column], index) => [direction, column, String(index + 1)])
        })}
        onDelete={(index) => { setSortingRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index)); setSortError('') }}
        onChange={(rowIndex, columnIndex, value) => {
          setSortingRows((rows) => rows.map((row, index) => index === rowIndex ? row.map((cell, cellIndex) => cellIndex === columnIndex ? value : cell) : row))
          setSortError('')
        }}
      />
      <SettingsTable
        title="Conditional Statements:"
        description="Add rules that control how records are processed."
        columns={['Mapping Column', 'Condition', 'Value', 'Action']}
        mappingColumns={mappingColumns}
        rows={conditionalRows}
        onAdd={() => setConditionalRows((rows) => [...rows, ['', '', '']])}
        onDelete={(index) => setConditionalRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}
        onChange={(rowIndex, columnIndex, value) => setConditionalRows((rows) => rows.map((row, index) => index === rowIndex ? row.map((cell, cellIndex) => cellIndex === columnIndex ? value : cell) : row))}
      />
    </section>
  </div>
}

function SettingsTable({ title, description, columns, mappingColumns, sortDirections = [], rows, onAdd, onDelete, onChange }: {
  title: string
  description: string
  columns: string[]
  mappingColumns: string[]
  sortDirections?: SortDirection[]
  rows: string[][]
  onAdd: () => void
  onDelete: (index: number) => void
  onChange: (rowIndex: number, columnIndex: number, value: string) => void
}) {
  return <section className="settings-section">
    <div className="settings-section-heading">
      <div><strong>{title}</strong><span className="settings-section-description">{description}</span></div>
      <button type="button" className="button button-primary" onClick={onAdd}><span className="button-icon"><ToolIcon name="plus" /></span>Add</button>
    </div>
    <table className="settings-table">
      <thead><tr>{columns.map((column) => <th scope="col" key={column}>{column}</th>)}</tr></thead>
      <tbody>{rows.length ? rows.map((row, rowIndex) => <tr key={rowIndex}>
        {columns.map((column, columnIndex) => {
          const label = `${title} ${column} ${rowIndex + 1}`
          const value = row[columnIndex] ?? ''
          const change = (nextValue: string) => onChange(rowIndex, columnIndex, nextValue)
          if (column === 'Action') return <td key={column}>
            <button type="button" className="icon-button trash" onClick={() => onDelete(rowIndex)} aria-label={`Delete ${title} row ${rowIndex + 1}`}><ToolIcon name="trash" /></button>
          </td>
          if (column === 'Order By') return <td key={column}>
            <select value={value} onChange={(event) => change(event.target.value)} aria-label={label}>
              {sortDirections.map((direction) => <option key={direction} value={direction}>{direction}</option>)}
            </select>
          </td>
          if (column === 'Mapping Column') return <td key={column}>
            <SearchableSelect options={mappingColumns} value={value} onValueChange={change} ariaLabel={label} clearLabel="Select a column" allowCustom />
          </td>
          return <td key={column}>
            <input value={value} placeholder={column === 'Condition' ? 'Enter condition' : 'Enter value'} onChange={(event) => change(event.target.value)} aria-label={label} />
          </td>
        })}
      </tr>) : <tr><td colSpan={columns.length} className="settings-empty">No items added yet.</td></tr>}</tbody>
    </table>
  </section>
}

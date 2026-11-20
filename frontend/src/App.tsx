import { sha256 } from '@noble/hashes/sha2.js'
import { bytesToHex } from '@noble/hashes/utils.js'
import { ChangeEvent, FormEvent, KeyboardEvent as ReactKeyboardEvent, ReactNode, createContext, useCallback, useContext, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { ChevronRight, CircleDot, Layers, Plus, Settings, Trash2, X } from 'lucide-react'
import { writeFile } from 'xlsx'
import {
  configuredFileFormat, createJobListRequestGuard, displayJobStatus, displayRunTime, emailAddresses, generalFieldErrors,
  isExcelFile, mappingColumnType, pasteEmailText, readExcelMappings, reportEmailMessage, reportWorkbook,
  mergeSavedJob, normalizeSortingPriorities, sortingPriorityError, validEmail, validIsoDate, validWholeNumber,
  type ReportEmailDelivery, type SortingPriorityRow,
} from './retirementBuilder'

type Screen = 'dashboard' | 'general' | 'schedule' | 'mapping' | 'subscriptions' | 'placeholder'
type ReportSource = 'csv' | 'companyPayroll'
type SideIcon = 'edit' | 'file' | 'copy'
type MappingRow = { dataSetNo?: number; colSeqNo?: number; id: number; field: string; startPosition: string; length: string; recordType: string; defaultValue: string; mapping: string; format: string }
type ApiMappingRow = { dataSetNo?: number; colSeqNo?: number; field?: string; startPosition?: string; length?: string; recordType?: string; defaultValue?: string; mappingColumn?: string; format?: string }
type ScheduleValues = { startDate: string; buildFrequency: string; hour: string; minute: string; meridiem: string; week: string }
type SortingRow = SortingPriorityRow
type ConditionalRow = { mappingColumn: string; condition: string; value: string }
type FileSettingsValues = { sortingOrder: SortingRow[]; conditionalStatements: ConditionalRow[] }
type JobsStatus = 'loading' | 'ready' | 'error'
type ApiSubscription = { client?: string; email?: string; companyId?: number | null }
type Subscription = { id: number; client: string; email: string; emailDraft?: string; companyId?: number }
type ClientOption = { id: number; label: string }
type TableFilters = Record<number, string>
type DashboardJob = { id: number; values: string[] }
type JobRunFile = { fileName: string; csv: string; excelRows?: string[][] | null }
type JobRun = JobRunFile & {
  runId: string; rowCount: number; storedRows: number; delimiter?: string; files?: JobRunFile[];
  emailDelivery?: ReportEmailDelivery | null;
}
type RetirementBuilderApiJob = { id: number; general?: { fileName?: string; fileFormat?: string; description?: string; outputFileNameFormat?: string; enable?: boolean; storeResultsToTable?: boolean; selectedFile?: string; reportSource?: ReportSource }; schedule?: { startDate?: string | null; startDateTime?: string | null; week?: string; hour?: string; minute?: string; meridiem?: string; buildFrequency?: string }; mapping?: { includeHeader?: boolean; rows?: ApiMappingRow[] }; subscriptions?: { mergeFiles?: boolean; rows?: ApiSubscription[] }; fileSettings?: { sortingOrder?: Partial<SortingRow>[]; conditionalStatements?: Partial<ConditionalRow>[] }; jobid?: number; jobfilename?: string; jobdesc?: string; filetype?: string; isEnabled?: boolean | number; ismerge?: boolean; runday?: string; runtime?: string; ScheduleType?: string; joblastmodified?: string | null; joblastrun?: string | null; Job_Last_Status?: string | null }
type RetirementBuilderOptions = { fileFormats: string[]; outputFileNameFormats: Array<{ label: string; value: string }>; buildFrequencies: string[]; hours: string[]; minutes: string[]; meridiems: string[]; weekDays: string[]; recordTypes: string[]; comparisonOperators: string[]; mappingColumns: string[]; payrollMappingColumns: string[]; payrollMappingColumnKeys: string[]; mappingColumnLabels: Record<string, string>; payrollCompanies: Record<string, string>; mappingColumnTypes: Record<string, string>; mappingFormatsByType: Record<string, string[]>; mappingFormatLabels: Record<string, string> }

const navigation: [SideIcon, string][] = [['edit', 'Benefits'], ['file', 'Mass Mutual Files'], ['copy', 'Process Validator'], ['copy', 'Retirement Builder'], ['edit', 'Prism'], ['copy', 'Services'], ['copy', 'Swipe Clock'], ['copy', 'Payroll Builder'], ['copy', 'NYS-45'], ['copy', 'Reports']]
const menuPaths: Record<string, string> = { Benefits: '/benefits', 'Mass Mutual Files': '/mass-mutual-files', 'Process Validator': '/process-validator', Prism: '/prism', Services: '/services', 'Swipe Clock': '/swipe-clock', 'Payroll Builder': '/payroll-builder', 'NYS-45': '/nys-45', Reports: '/reports' }
const menuTitles: Record<string, string> = Object.fromEntries(Object.entries(menuPaths).map(([label, path]) => [path, label]))
const apiBaseUrl = '/api/v1'
async function fetchRetirementJobs(signal?: AbortSignal): Promise<RetirementBuilderApiJob[]> {
  const response = await fetch(`${apiBaseUrl}/retirement-builder/jobs`, { signal, cache: 'no-store' })
  if (!response.ok) throw new Error('Unable to load Retirement Builder jobs')
  const jobs = await response.json() as RetirementBuilderApiJob[]
  return jobs.map(normalizeApiJob)
}
const emptyOptions: RetirementBuilderOptions = { fileFormats: [], outputFileNameFormats: [], buildFrequencies: [], hours: [], minutes: [], meridiems: [], weekDays: [], recordTypes: [], comparisonOperators: [], mappingColumns: [], payrollMappingColumns: [], payrollMappingColumnKeys: [], mappingColumnLabels: {}, payrollCompanies: {}, mappingColumnTypes: {}, mappingFormatsByType: {}, mappingFormatLabels: {} }
const OptionsContext = createContext({ values: emptyOptions, loading: true, error: '' })
const mappingLabel = (column: string, labels: Record<string, string>) =>
  Object.prototype.hasOwnProperty.call(labels, column) ? labels[column] : column
function normalizeApiJob(raw: RetirementBuilderApiJob): RetirementBuilderApiJob { const id = Number(raw.id ?? raw.jobid); const runTime = raw.runtime?.match(/^(\d{1,2}):(\d{1,2})(?:\s+(AM|PM))?$/i); const scheduleType = ({ D: 'Daily', W: 'Weekly', B: 'Bi-Weekly', M: 'Monthly', MD: 'Monthly' } as Record<string, string>)[raw.ScheduleType ?? ''] ?? raw.ScheduleType; return { ...raw, id, general: { ...raw.general, fileName: raw.general?.fileName ?? raw.jobfilename, description: raw.general?.description ?? raw.jobdesc ?? '', fileFormat: raw.general?.fileFormat ?? raw.filetype, enable: raw.general?.enable ?? (raw.isEnabled === true || raw.isEnabled === 1), storeResultsToTable: raw.general?.storeResultsToTable ?? false }, schedule: raw.schedule ?? { week: raw.runday, buildFrequency: scheduleType, hour: runTime?.[1], minute: runTime?.[2], meridiem: runTime?.[3]?.toUpperCase() }, subscriptions: raw.subscriptions ?? { mergeFiles: raw.ismerge } } }
function toDashboardJob(job: RetirementBuilderApiJob): DashboardJob {
  const { general = {}, schedule = {} } = job
  const lastRunDate = job.joblastrun?.slice(0, 10) || ''
  return {
    id: job.id,
    values: [
      general.fileName || `Job ${job.id}`, general.description || '', job.joblastmodified?.slice(0, 10) || '',
      lastRunDate === '1900-01-01' ? '' : lastRunDate, schedule.week || '', displayRunTime(schedule.hour, schedule.minute, schedule.meridiem),
      schedule.startDate === null ? 'Manual only' : schedule.buildFrequency || '', general.fileFormat ?? '',
      general.enable === false ? 'No' : 'Yes', displayJobStatus(job.Job_Last_Status),
    ],
  }
}
function parseClientId(value: string): number | null {
  const match = value.trim().match(/^(\d+)(?: - .+)?$/)
  if (!match) return null
  const id = Number(match[1])
  return Number.isSafeInteger(id) && id > 0 && id <= 2147483647 ? id : null
}
let rowSequence = 0
const nextRowId = () => (rowSequence += 1)
const placeholderFormat = 'Select Format'
function toMappingRow(row: ApiMappingRow & { mapping?: string }): MappingRow { const format = row.format === placeholderFormat ? '' : row.format ?? ''; const mapping = row.mapping ?? row.mappingColumn ?? ''; return { dataSetNo: row.dataSetNo, colSeqNo: row.colSeqNo, id: nextRowId(), field: row.field ?? '', startPosition: row.startPosition ?? '', length: row.length ?? '', recordType: row.recordType ?? '', defaultValue: row.defaultValue ?? '', mapping, format } }
function normalizeMappingRows(rows: ApiMappingRow[] = []): MappingRow[] { return rows.map((row) => toMappingRow(row)) }
const newSubscription = (): Subscription => ({ id: nextRowId(), client: '', email: '' })
const toSubscription = (row: ApiSubscription): Subscription => ({ id: nextRowId(), client: row.client ?? '', email: row.email ?? '', companyId: row.companyId ?? undefined })
const scheduleDefaults: Omit<ScheduleValues, 'startDate'> = {
  buildFrequency: 'Weekly', hour: '4', minute: '00', meridiem: 'AM', week: 'Thursday',
}
const emptySchedule: ScheduleValues = { startDate: '', buildFrequency: '', hour: '', minute: '', meridiem: '', week: '' }
const emptyFileSettings: FileSettingsValues = { sortingOrder: [], conditionalStatements: [] }
const defaultNewReportSource: ReportSource = 'companyPayroll'
const addPaths: Record<Screen, string> = { dashboard: '/retirement-builder', general: '/jobs/new', schedule: '/jobs/new/schedule', mapping: '/jobs/new/mapping', subscriptions: '/jobs/new/subscriptions', placeholder: '/placeholder' }
const editPaths: Record<Screen, string> = { dashboard: '/retirement-builder', general: '/jobs/edit/general', schedule: '/jobs/edit/schedule', mapping: '/jobs/edit/mapping', subscriptions: '/jobs/edit/subscriptions', placeholder: '/placeholder' }

function screenFromPath(path: string): Screen { if (path === '/retirement-builder') return 'dashboard'; if (path === '/jobs/new' || path === '/jobs/edit/general') return 'general'; if (path === '/jobs/new/schedule' || path === '/jobs/edit/schedule') return 'schedule'; if (path === '/jobs/new/mapping' || path === '/jobs/edit/mapping') return 'mapping'; if (path === '/jobs/new/subscriptions' || path === '/jobs/edit/subscriptions') return 'subscriptions'; return 'placeholder' }

function SearchableSelect({
  options, optionLabels, defaultValue = '', value: controlledValue, onValueChange, ariaLabel, errorId,
  clearLabel, allowCustom = false, includeSavedOption = true, canAddCustom, searchPlaceholder, optionsLoading, optionsError, placeholder = placeholderFormat,
}: {
  options: string[]
  optionLabels?: Record<string, string>
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  ariaLabel: string
  errorId?: string
  clearLabel?: string
  allowCustom?: boolean
  placeholder?: string
  canAddCustom?: (value: string) => boolean
  searchPlaceholder?: string
  includeSavedOption?: boolean
  optionsLoading?: boolean
  optionsError?: string
}) {
  const root = useRef<HTMLSpanElement>(null); const menu = useRef<HTMLDivElement>(null); const trigger = useRef<HTMLButtonElement>(null); const listId = useId(); const [internalValue, setInternalValue] = useState(defaultValue); const value = controlledValue ?? internalValue; const [query, setQuery] = useState(''); const [open, setOpen] = useState(false); const [activeIndex, setActiveIndex] = useState(0); const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({})
  const { values: runtimeOptions, loading: runtimeOptionsLoading, error: runtimeOptionsError } = useContext(OptionsContext)
  const apiOptions = ariaLabel === 'File format' ? runtimeOptions.fileFormats : ariaLabel === 'Build frequency' ? runtimeOptions.buildFrequencies : ariaLabel === 'Hour' ? runtimeOptions.hours : ariaLabel === 'Minute' ? runtimeOptions.minutes : ariaLabel === 'AM or PM' ? runtimeOptions.meridiems : ariaLabel === 'Week' ? runtimeOptions.weekDays : ariaLabel.endsWith('record type') ? runtimeOptions.recordTypes : options
  const effectiveOptions = [...new Set([
    ...(clearLabel ? [''] : []),
    ...(includeSavedOption && controlledValue && !apiOptions.includes(controlledValue) ? [controlledValue] : []),
    ...apiOptions,
  ])]
  const optionLabel = (option: string) => option ? optionLabels?.[option] ?? option : clearLabel ?? ''
  const search = query.trim()
  const customOption = allowCustom && search && (canAddCustom?.(search) ?? true) &&
    !effectiveOptions.some((option) => option.toLowerCase() === search.toLowerCase())
    ? search : ''
  const filteredOptions = effectiveOptions.filter((option) => optionLabel(option).toLowerCase().includes(search.toLowerCase()))
  if (customOption) filteredOptions.push(customOption)
  useEffect(() => { const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) { setOpen(false); setQuery('') } }; document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close) }, [])
  useLayoutEffect(() => { if (!open) return undefined; const position = () => { const rect = root.current?.getBoundingClientRect(); if (!rect) return; const width = Math.min(Math.max(rect.width, 320), window.innerWidth - 16); const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)); const availableBelow = window.innerHeight - rect.bottom - 8; const availableAbove = rect.top - 8; const openUp = availableBelow < 340 && availableAbove > availableBelow; const maxHeight = Math.max(150, Math.min(270, openUp ? availableAbove : availableBelow)); setMenuStyle({ position: 'fixed', zIndex: 1000, left, width, maxWidth: 'calc(100vw - 16px)', maxHeight, ...(openUp ? { top: 'auto', bottom: window.innerHeight - rect.top + 5 } : { top: rect.bottom + 5, bottom: 'auto' }) }) }; position(); window.addEventListener('resize', position); window.addEventListener('scroll', position, true); return () => { window.removeEventListener('resize', position); window.removeEventListener('scroll', position, true) } }, [open])
  useEffect(() => { if (open) menu.current?.querySelector('[data-active="true"]')?.scrollIntoView?.({ block: 'nearest' }) }, [open, activeIndex])
  const closeMenu = (restoreFocus = false) => { setOpen(false); setQuery(''); if (restoreFocus) trigger.current?.focus() }
  const choose = (option: string, restoreFocus = false) => { if (controlledValue === undefined) setInternalValue(option); onValueChange?.(option); closeMenu(restoreFocus) }
  const openMenu = () => { setQuery(''); setActiveIndex(Math.max(0, effectiveOptions.indexOf(value))); setOpen(true) }
  const onTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => { if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) { event.preventDefault(); openMenu() } }
  const onMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => { if (event.key === 'Escape') { event.preventDefault(); closeMenu(true) } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); if (filteredOptions.length) setActiveIndex((index) => (index + (event.key === 'ArrowDown' ? 1 : -1) + filteredOptions.length) % filteredOptions.length) } else if (event.key === 'Enter' && (event.target as HTMLElement).tagName === 'INPUT') { event.preventDefault(); const option = filteredOptions[activeIndex]; if (option !== undefined) choose(option, true) } }
  return <span className="searchable-select" ref={root}>
    <button type="button" ref={trigger} className="searchable-select-trigger" aria-haspopup="listbox" aria-expanded={open}
      aria-controls={open ? listId : undefined} aria-label={ariaLabel} aria-invalid={!!errorId} aria-describedby={errorId}
      onKeyDown={onTriggerKeyDown} onClick={() => { if (open) setOpen(false); else openMenu() }}>
      <span className={value ? '' : 'placeholder'}>{optionLabel(value) || placeholder}</span>
      <span className="select-chevron" aria-hidden="true">⌄</span>
    </button>
    {open && createPortal(
      <div className="searchable-select-menu" id={listId} ref={menu} style={menuStyle} role="listbox" onKeyDown={onMenuKeyDown}>
        <input autoFocus className="searchable-select-search" value={query}
          onChange={(event) => { setQuery(event.target.value); setActiveIndex(0) }}
          placeholder={searchPlaceholder ?? (allowCustom ? 'Search or enter a source column…' : 'Search…')}
          maxLength={allowCustom ? 255 : undefined} aria-label={`Search ${ariaLabel}`} aria-controls={listId}
          aria-activedescendant={filteredOptions.length ? `${listId}-${activeIndex}` : undefined} />
        {filteredOptions.length ? filteredOptions.map((option, index) =>
          <button type="button" role="option" id={`${listId}-${index}`} data-active={index === activeIndex}
            aria-selected={option === value} key={option} onClick={() => choose(option, true)}
            className={`searchable-select-option ${option === value ? 'selected' : ''} ${index === activeIndex ? 'active' : ''}`}>
            {option && option === customOption ? `Use “${option}”` : optionLabel(option)}
          </button>
        ) : <span className="searchable-select-empty">
          {(optionsError ?? runtimeOptionsError) || ((optionsLoading ?? runtimeOptionsLoading) ? 'Loading options…' : 'No matches')}
        </span>}
      </div>, document.body)}
  </span>
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
type Draft = { mode: 'add' | 'edit'; jobId: number | null; enable: boolean; fileName: string; fileFormat: string; description: string; outputFileNameFormat: string; storeResultsToTable: boolean; selectedFile: string; reportSource: ReportSource; schedule: ScheduleValues; storedStartDateTime?: string | null; includeHeader: boolean; mappingRows: MappingRow[]; mergeFiles: boolean; subscriptions: Subscription[]; fileSettings: FileSettingsValues }
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
  const requestedJobId = isEditFlow && typeof location.state?.jobId === 'number' ? location.state.jobId : null
  const [initialDraft] = useState(() => {
    const draft = isWizard ? readDraft(isEditFlow ? 'edit' : 'add') : null
    return requestedJobId === null || draft?.jobId === requestedJobId ? draft : null
  })
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 767); const [showSettings, setShowSettings] = useState(false); const [saveError, setSaveError] = useState(''); const [saving, setSaving] = useState(false); const savingRef = useRef(false)
  const [enable, setEnable] = useState(initialDraft?.enable ?? true); const [fileName, setFileName] = useState(initialDraft?.fileName ?? ''); const [draftFileFormat, setFileFormat] = useState(initialDraft?.fileFormat ?? ''); const [description, setDescription] = useState(initialDraft?.description ?? ''); const [outputFileNameFormat, setOutputFileNameFormat] = useState(initialDraft?.outputFileNameFormat ?? ''); const [storeResultsToTable, setStoreResultsToTable] = useState(initialDraft?.storeResultsToTable ?? false); const [selectedFile, setSelectedFile] = useState(initialDraft?.selectedFile ?? '')
  const [reportSource, setReportSource] = useState<ReportSource>(initialDraft?.reportSource ?? (isEditFlow ? 'csv' : defaultNewReportSource))
  const [schedule, setSchedule] = useState<ScheduleValues>(initialDraft?.schedule ?? emptySchedule); const [includeHeader, setIncludeHeader] = useState(initialDraft?.includeHeader ?? false); const [mappingRows, setMappingRows] = useState<MappingRow[]>(initialDraft?.mappingRows ?? []); const [fileSettings, setFileSettings] = useState<FileSettingsValues>(initialDraft?.fileSettings ?? emptyFileSettings)
  const [mergeFiles, setMergeFiles] = useState(initialDraft?.mergeFiles ?? false); const [subscriptions, setSubscriptions] = useState<Subscription[]>(initialDraft?.subscriptions ?? [])
  const [retirementJobs, setRetirementJobs] = useState<RetirementBuilderApiJob[]>([]); const [jobsStatus, setJobsStatus] = useState<JobsStatus>('loading'); const [selectedJobId, setSelectedJobId] = useState<number | null>(initialDraft?.jobId ?? null); const [filters, setFilters] = useState<TableFilters>({}); const [options, setOptions] = useState({ values: emptyOptions, loading: true, error: '' })
  const jobListRequests = useRef(createJobListRequestGuard())
  const [storedStartDateTime, setStoredStartDateTime] = useState(initialDraft?.storedStartDateTime)
  const [validatedSteps, setValidatedSteps] = useState<Partial<Record<Screen, boolean>>>({})
  const [editLoadError, setEditLoadError] = useState('')
  const [editLoadAttempt, setEditLoadAttempt] = useState(0)
  const [uploadError, setUploadError] = useState('')
  const [importing, setImporting] = useState(false)
  const uploadRequest = useRef(0)
  const createAttempt = useRef<CreateAttempt | null>(null)
  const fileFormat = configuredFileFormat(draftFileFormat, options.values.fileFormats)
  const fixedFormat = fileFormat.trim().toUpperCase() === 'FIXED'
  const generalErrors = generalFieldErrors(fileName, fileFormat)
  const invalidGeneral = Object.values(generalErrors).some(Boolean)
  const manualOnlyDraft = !Object.values(schedule).some(Boolean)
  const scheduleErrors = {
    startDate: schedule.startDate && (!/^\d{4}-/.test(schedule.startDate) || schedule.startDate < earliestStartDate)
      ? 'Choose a date between 1753-01-01 and 9999-12-31.' : '',
    buildFrequency: schedule.buildFrequency ? '' : 'Select a build frequency.',
    hour: validWholeNumber(schedule.hour, 1, 12) ? '' : 'Select an hour from 1 to 12.',
    minute: validWholeNumber(schedule.minute, 0, 59) ? '' : 'Select a minute from 00 to 59.',
    meridiem: schedule.meridiem ? '' : 'Select AM or PM.',
    week: !schedule.week && ['Weekly', 'Bi-Weekly'].includes(schedule.buildFrequency) ? 'Select a day of the week.' : '',
  }
  const payrollColumns = options.values.payrollMappingColumns
  const requiresMappingDefault = (source: string) => {
    if (reportSource !== 'companyPayroll' || !payrollColumns.length || !source) return false
    const normalized = source.toLowerCase()
    const { mappingColumnLabels, payrollMappingColumnKeys } = options.values
    return !payrollColumns.some((label) => label.toLowerCase() === normalized)
      && !payrollMappingColumnKeys.some((key) => key.toLowerCase() === normalized
        || mappingColumnLabels[key]?.toLowerCase() === normalized)
  }
  const invalidMapping = !mappingRows.length || mappingRows.some((row) =>
    !row.field.trim() || (requiresMappingDefault(row.mapping.trim() || row.field.trim()) && !row.defaultValue)
    || [row.startPosition, row.length].some((value) => value.trim() && !validWholeNumber(value))
    || (fixedFormat && !(includeHeader && ['H', 'HEADER'].includes(row.recordType.trim().toUpperCase()))
      && !validWholeNumber(row.length, 1, 1000)))
  const loadingEditJob = requestedJobId !== null && requestedJobId !== selectedJobId
  const awaitingJob = isEditFlow && (loadingEditJob || selectedJobId === null)
  const restoringStartDateTime = isEditFlow && screen === 'schedule' && storedStartDateTime === undefined
  const editDetailsId = loadingEditJob ? requestedJobId : restoringStartDateTime ? selectedJobId : null
  const dashboardJobs = useMemo(() => retirementJobs.map(toDashboardJob), [retirementJobs])
  useEffect(() => {
    if (!isWizard) return
    const controller = new AbortController()
    setOptions((current) => ({ ...current, loading: true, error: '' }))
    fetch(`${apiBaseUrl}/retirement-builder/options`, { signal: controller.signal, cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('Unable to load Retirement Builder options')
        return response.json() as Promise<RetirementBuilderOptions>
      })
      .then((values) => {
        if (!controller.signal.aborted) setOptions({ values: { ...emptyOptions, ...values }, loading: false, error: '' })
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setOptions((current) => ({ ...current, loading: false, error: 'Unable to load Retirement Builder options.' }))
        }
      })
    return () => controller.abort()
  }, [isWizard])
  useEffect(() => {
    if (screen !== 'dashboard') return
    const controller = new AbortController()
    setJobsStatus('loading')
    void jobListRequests.current.apply(
      () => fetchRetirementJobs(controller.signal),
      (jobs) => { setRetirementJobs(jobs); setJobsStatus('ready') },
      controller.signal,
    ).catch(() => {
      if (!controller.signal.aborted) { setRetirementJobs([]); setJobsStatus('error') }
    })
    return () => controller.abort()
  }, [screen])
  useEffect(() => { setSaveError(''); setShowSettings(false) }, [location.pathname])
  useEffect(() => {
    if (awaitingJob && requestedJobId === null) routerNavigate('/retirement-builder', { replace: true })
  }, [awaitingJob, requestedJobId, routerNavigate])
  useEffect(() => { try { if (!isWizard) { sessionStorage.removeItem(draftKey); return } if (awaitingJob) return; const draft: Draft = { mode: isEditFlow ? 'edit' : 'add', jobId: selectedJobId, enable, fileName, fileFormat, description, outputFileNameFormat, storeResultsToTable, selectedFile, reportSource, schedule, storedStartDateTime, includeHeader, mappingRows, mergeFiles, subscriptions, fileSettings }; sessionStorage.setItem(draftKey, JSON.stringify(draft)) } catch { /* session storage unavailable: draft is simply not kept across refresh */ } }, [awaitingJob, description, enable, fileFormat, fileName, fileSettings, includeHeader, isEditFlow, isWizard, mappingRows, mergeFiles, outputFileNameFormat, reportSource, schedule, selectedFile, selectedJobId, storeResultsToTable, storedStartDateTime, subscriptions])
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
    const invalid = [invalidGeneral, !manualOnlyDraft && Object.values(scheduleErrors).some(Boolean), invalidMapping]
    const index = invalid.findIndex((failed, step) => failed && step < target)
    if (index === -1) return true
    const step = wizardSteps[index]
    setValidatedSteps((current) => ({ ...current, [step]: true }))
    routerNavigate((edit ? editPaths : addPaths)[step])
    // Errors can sit above the viewport; scroll to the first one once the step has rendered.
    window.setTimeout(() => document.querySelector('[aria-invalid="true"], .field-error')?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 150)
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
      setMappingRows(fields.map((field) => toMappingRow(isEditFlow ? { ...field, startPosition: '0', length: '0' } : field)))
      setSelectedFile(file.name)
    } catch {
      if (request === uploadRequest.current) setUploadError('Unable to read this workbook. Open it in Excel, save a valid copy, and try again.')
    } finally {
      if (request === uploadRequest.current) setImporting(false)
    }
  }
  const resetForm = () => { setSelectedJobId(null); setSaveError(''); setEnable(true); setFileName(''); setFileFormat(''); setDescription(''); setOutputFileNameFormat(''); setStoreResultsToTable(false); setSelectedFile(''); setReportSource(defaultNewReportSource); setSchedule(emptySchedule); setStoredStartDateTime(undefined); setIncludeHeader(false); setMergeFiles(false); setSubscriptions([]); setMappingRows([]); setFileSettings(emptyFileSettings) }
  const loadJob = useCallback((job: RetirementBuilderApiJob) => { const general = job.general ?? {}; const jobSchedule = job.schedule ?? {}; setSelectedJobId(job.id); setSaveError(''); setEnable(general.enable !== false); setFileName(general.fileName ?? ''); setFileFormat(general.fileFormat ?? ''); setDescription(general.description ?? ''); setOutputFileNameFormat(general.outputFileNameFormat ?? ''); setStoreResultsToTable(Boolean(general.storeResultsToTable)); setSelectedFile(general.selectedFile ?? ''); setReportSource(general.reportSource ?? 'csv'); setSchedule(jobSchedule.startDate === null ? emptySchedule : {
      startDate: jobSchedule.startDate ?? '',
      buildFrequency: jobSchedule.buildFrequency ?? scheduleDefaults.buildFrequency,
      hour: jobSchedule.hour ?? scheduleDefaults.hour,
      minute: jobSchedule.minute ?? scheduleDefaults.minute,
      meridiem: jobSchedule.meridiem ?? scheduleDefaults.meridiem,
      week: jobSchedule.week ?? scheduleDefaults.week,
    }); setStoredStartDateTime(jobSchedule.startDateTime ?? null); setIncludeHeader(job.mapping?.includeHeader ?? true); setMappingRows(normalizeMappingRows(job.mapping?.rows ?? [])); setMergeFiles(Boolean(job.subscriptions?.mergeFiles)); setSubscriptions((job.subscriptions?.rows ?? []).map(toSubscription)); setFileSettings({ sortingOrder: (job.fileSettings?.sortingOrder ?? []).map((row) => ({ orderBy: row.orderBy ?? '', mappingColumn: row.mappingColumn ?? '' })), conditionalStatements: (job.fileSettings?.conditionalStatements ?? []).map((row) => ({ mappingColumn: row.mappingColumn ?? '', condition: row.condition ?? '', value: row.value ?? '' })) }) }, [])
  useEffect(() => {
    if (editDetailsId === null) return
    const controller = new AbortController()
    const fallback = 'Unable to load the selected Retirement Builder job.'
    setEditLoadError('')
    const load = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/retirement-builder/jobs/${editDetailsId}`, { signal: controller.signal })
        if (!response.ok) throw new Error(await readSaveError(response, fallback))
        const job = normalizeApiJob(await response.json() as RetirementBuilderApiJob)
        if (job.id !== editDetailsId) throw new Error(fallback)
        if (controller.signal.aborted) return
        if (loadingEditJob) loadJob(job)
        else setStoredStartDateTime(job.schedule?.startDateTime ?? null)
      } catch (error) {
        if (!controller.signal.aborted && loadingEditJob) setEditLoadError(error instanceof Error && !(error instanceof TypeError) ? error.message : fallback)
      }
    }
    void load()
    return () => controller.abort()
  }, [editDetailsId, editLoadAttempt, loadJob, loadingEditJob])
  const startAdd = () => {
    clearCreateAttempt()
    setValidatedSteps({})
    setUploadError('')
    resetForm()
    navigate('general', false)
  }
  const startEdit = (jobId: number) => {
    setSelectedJobId(null)
    setValidatedSteps({})
    setUploadError('')
    setEditLoadError('')
    routerNavigate(editPaths.general, { state: { jobId } })
  }
  const saveJob = async () => {
    if (savingRef.current || !validateBefore(wizardSteps.length)) return
    if (isEditFlow && selectedJobId === null) {
      setSaveError('This job could not be found. Return to the dashboard and select it again.')
      return
    }
    setValidatedSteps((current) => ({ ...current, subscriptions: true }))
    setSaveError('')
    const subscriptionRows = subscriptions.filter((row) =>
      row.companyId !== undefined || row.client.trim() || row.email.trim() || row.emailDraft?.trim(),
    )
    const clientIds = subscriptionRows.map((row) => row.companyId === undefined ? parseClientId(row.client) : '')
    if (clientIds.some((id) => id === null)) {
      setSaveError(reportSource === 'companyPayroll' ? 'Select a payroll company for every subscription row.' : 'Select a positive client ID for every subscription row.')
      return
    }
    const emails = subscriptionRows.map(subscriptionEmails)
    if (emails.some((row) => row.some((email) => !validEmail(email)))) return

    const body = JSON.stringify({
      general: { fileName, fileFormat, description, outputFileNameFormat, enable, storeResultsToTable, reportSource },
      schedule: manualOnlyDraft ? { startDate: null } : { ...schedule, startDate: schedule.startDate || null, week: schedule.week || undefined },
      mapping: { includeHeader, rows: mappingRows.map(({ dataSetNo, colSeqNo, field, startPosition, length, recordType, defaultValue, mapping, format }) => ({
        dataSetNo, colSeqNo, field, startPosition: startPosition.trim() || '0', length: length.trim() || '0', recordType, defaultValue, mappingColumn: mapping, format,
      })) },
      subscriptions: { mergeFiles, rows: subscriptionRows.map((row, index) => ({
        client: String(clientIds[index]), companyId: row.companyId, email: emails[index].join(', '),
      })) },
      fileSettings: {
        ...fileSettings,
        sortingOrder: normalizeSortingPriorities(fileSettings.sortingOrder),
      },
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
      jobListRequests.current.invalidate()
      setRetirementJobs((jobs) => mergeSavedJob(jobs, saved))
      setJobsStatus('ready')
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
  const addMappingRow = () => setMappingRows((rows) => [...rows, toMappingRow(isEditFlow ? { startPosition: '0', length: '0' } : {})])
  const pageTitle = screen === 'placeholder' ? menuTitles[location.pathname] ?? '' : 'Retirement Builder'; const title = screen === 'dashboard' || screen === 'placeholder' ? '' : isEditFlow ? 'Edit Job' : 'Add New Job'; const userName = userEmail.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  const content = (() => {
    if (screen === 'dashboard') return <Dashboard jobs={dashboardJobs} status={jobsStatus} filters={filters} onFilterChange={updateFilter} onAdd={startAdd} onEdit={startEdit}
      onRunSettled={(id, result) => {
        if (result) setRetirementJobs((jobs) => jobs.map((job) => job.id === id ? { ...job, Job_Last_Status: result } : job))
        void jobListRequests.current.apply(() => fetchRetirementJobs(), setRetirementJobs)
          .catch(() => { /* Keep the current dashboard state. */ })
      }}
    />
    if (screen === 'placeholder') return <section className="blank-page" aria-label={`${pageTitle} blank page`} />
    if (awaitingJob) return <div className="edit-job-state">
      {editLoadError ? <>
        <p role="alert">{editLoadError}</p>
        <button type="button" className="button button-light" onClick={() => {
          setEditLoadError('')
          setEditLoadAttempt((attempt) => attempt + 1)
        }}>Retry</button>
      </> : <p role="status">Loading job details…</p>}
    </div>
    if (screen === 'general') return <GeneralStep
      fileName={fileName} fileFormat={fileFormat} description={description} outputFileNameFormat={outputFileNameFormat}
      reportSource={reportSource}
      isEdit={isEditFlow} enable={enable} onEnableChange={setEnable}
      storeResultsToTable={storeResultsToTable} selectedFile={selectedFile} importing={importing} uploadError={uploadError}
      errors={validatedSteps.general ? generalErrors : undefined}
      onFileNameChange={setFileName} onFileFormatChange={setFileFormat} onDescriptionChange={setDescription}
      onOutputFileNameFormatChange={setOutputFileNameFormat} onStoreResultsChange={setStoreResultsToTable}
      onFileChange={importWorkbook} onCancel={() => navigate('dashboard')}
      onSubmit={(event) => { event.preventDefault(); navigate('schedule') }}
    />
    if (screen === 'schedule') return <ScheduleStep schedule={schedule} storedStartDateTime={isEditFlow ? storedStartDateTime : undefined}
      errors={validatedSteps.schedule ? scheduleErrors : undefined}
      onChange={(patch) => setSchedule((current) => ({ ...current, ...patch }))}
      onBack={() => navigate('general')} onNext={() => navigate('mapping')}
    />
    if (screen === 'mapping') return <MappingStep requiresDefault={requiresMappingDefault} includeHeader={includeHeader} rows={mappingRows} fixed={fixedFormat}
      validate={!!validatedSteps.mapping} onHeaderChange={setIncludeHeader} onRowChange={updateMappingRow}
      onDelete={(id) => setMappingRows((rows) => rows.filter((row) => row.id !== id))}
      onOpenSettings={() => setShowSettings(true)} onBack={() => navigate('schedule')} onNext={() => navigate('subscriptions')}
    />
    return <SubscriptionsStep reportSource={reportSource} mergeFiles={mergeFiles} subscriptions={subscriptions} error={saveError}
      saving={saving} validate={!!validatedSteps.subscriptions} onMergeChange={setMergeFiles}
      onClientChange={(id, client) => setSubscriptions((rows) => rows.map((row) => row.id === id ? { ...row, client } : row))}
      onCompanyChange={(id, companyId) => setSubscriptions((rows) => rows.map((row) => row.id === id ? { ...row, client: '', companyId } : row))}
      onEmailChange={(id, email, emailDraft) => setSubscriptions((rows) => rows.map((row) => row.id === id ? { ...row, email, emailDraft } : row))}
      onAdd={() => setSubscriptions((rows) => [...rows, newSubscription()])}
      onDelete={(id) => setSubscriptions((rows) => rows.filter((row) => row.id !== id))}
      onBack={() => navigate('mapping')} onFinish={saveJob}
    />
  })()
  return <OptionsContext.Provider value={options}><div className={`app-shell ${sidebarOpen ? 'sidebar-expanded' : 'sidebar-collapsed'}`}><header className="topbar"><div className="brand">ECS</div><button className="menu-button" onClick={() => setSidebarOpen((open) => !open)} aria-label="Toggle navigation">☰</button><div className="user-name">{userName}</div></header><div className="workspace"><Sidebar active={screen} onNavigate={navigate} onNavigatePath={routerNavigate} /><main className="main-content"><div className="page-heading"><h1>{pageTitle}</h1><div className="breadcrumb"><CircleDot className="breadcrumb-icon" aria-hidden="true" /><button type="button" className="breadcrumb-link" onClick={() => navigate('dashboard')}>SYD</button><ChevronRight className="breadcrumb-chevron" aria-hidden="true" /><span>{title}</span></div></div>{screen === 'dashboard' || screen === 'placeholder' ? content : <WizardCard title={title} activeStep={screen} stepsDisabled={awaitingJob} onCancel={() => navigate('dashboard')} onNavigate={navigate} headerActions={screen === 'mapping' ? <button type="button" className="button button-primary" onClick={addMappingRow}><span className="button-icon"><ToolIcon name="plus" /></span>Add Dataset</button> : screen === 'general' && isEditFlow ? <button type="button" className="button button-light" onClick={() => navigate('dashboard')}>Cancel</button> : undefined}>{content}</WizardCard>}<footer><span>Copyright © 2026</span><strong>Employer Services Corporation.</strong><span>All rights reserved.</span></footer></main></div>{showSettings && <FileSettingsModal reportSource={reportSource} mappingRows={mappingRows} initialSorting={fileSettings.sortingOrder} initialConditional={fileSettings.conditionalStatements} onSave={(sortingOrder, conditionalStatements) => { setFileSettings({ sortingOrder, conditionalStatements }); setShowSettings(false) }} onClose={() => setShowSettings(false)} />}</div></OptionsContext.Provider>
}

function MenuIcon({ name }: { name: SideIcon }) { if (name === 'file') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3.5h9l5 5V20.5H5z" /><path d="M14 3.5v5h5" /></svg>; if (name === 'copy') return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="6.5" width="11" height="13" rx="1.5" /><path d="M8 6.5V4.8A1.8 1.8 0 0 1 9.8 3h9a1.8 1.8 0 0 1 1.8 1.8v9A1.8 1.8 0 0 1 18.8 15H15" /></svg>; return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 16.5-.7 3.2 3.2-.7L18.8 6.7a2.2 2.2 0 0 0-3.1-3.1z" /><path d="m14.7 5.3 4 4" /></svg> }
function Sidebar({ active, onNavigate, onNavigatePath }: { active: Screen; onNavigate: (screen: Screen) => void; onNavigatePath: (path: string) => void }) { return <aside className="sidebar">{navigation.map(([icon, label]) => <button className={`nav-item ${label === 'Retirement Builder' && active !== 'placeholder' ? 'active' : ''}`} key={label} onClick={() => label === 'Retirement Builder' ? onNavigate('dashboard') : onNavigatePath(menuPaths[label])}><span className="nav-icon"><MenuIcon name={icon} /></span><span>{label}</span>{['Benefits', 'Mass Mutual Files', 'Prism'].includes(label) && <span className="nav-chevron">‹</span>}</button>)}</aside> }
function ToolIcon({ name }: { name: 'layers' | 'plus' | 'trash' }) { if (name === 'plus') return <Plus aria-hidden="true" />; if (name === 'trash') return <Trash2 aria-hidden="true" />; return <Layers aria-hidden="true" /> }
function WizardCard({ title, activeStep, stepsDisabled, onCancel, onNavigate, headerActions, children }: { title: string; activeStep: Screen; stepsDisabled: boolean; onCancel: () => void; onNavigate: (screen: Screen) => void; headerActions?: ReactNode; children: ReactNode }) { const steps: { key: Screen; label: string }[] = [{ key: 'general', label: 'General' }, { key: 'schedule', label: 'Schedule' }, { key: 'mapping', label: 'Mapping' }, { key: 'subscriptions', label: 'Subscriptions' }]; return <><div className="wizard-steps-shell"><nav className="wizard-steps">{steps.map((step, index) => <button className={`wizard-step ${activeStep === step.key ? 'active' : ''}`} key={step.key} aria-current={activeStep === step.key ? 'step' : undefined} disabled={stepsDisabled} onClick={() => onNavigate(step.key)}><span className="step-number" aria-hidden="true">{index + 1}</span><span>{step.label}</span></button>)}</nav></div><section className="wizard-card"><div className="card-heading"><h2>{title}</h2><div className="card-heading-actions">{headerActions}{activeStep !== 'general' && <button className="button button-light" onClick={onCancel}>Cancel</button>}</div></div>{children}</section></> }
const jobsPerPage = 10
const jobSortCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

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
  const [page, setPage] = useState(1)
  const tableScroll = useRef<HTMLDivElement>(null)
  const [selectedJobs, setSelectedJobs] = useState<number[]>([])
  const [runTarget, setRunTarget] = useState<DashboardJob | null>(null)
  const [runningJobId, setRunningJobId] = useState<number | null>(null)
  const [runError, setRunError] = useState('')
  const [runResult, setRunResult] = useState<JobRun | null>(null)
  const [downloads, setDownloads] = useState<Array<JobRunFile & { url: string }>>([])
  const [downloadError, setDownloadError] = useState('')
  const delimiter = runResult?.delimiter
  const running = runningJobId !== null
  const valueFor = useCallback((job: DashboardJob, index: number) => index === 9 && job.id === runningJobId
    ? 'In Progress' : job.values[index] ?? '', [runningJobId])
  const sortedJobs = useMemo(() => {
    const activeFilters = Object.entries(filters)
      .map(([index, value]) => [Number(index), value.trim().toLowerCase()] as const)
      .filter(([, value]) => value)
    const matches = jobs.filter((job) => activeFilters.every(([index, value]) =>
      valueFor(job, index).toLowerCase().includes(value)
    ))
    if (sort) {
      matches.sort((left, right) => {
        const comparison = jobSortCollator.compare(valueFor(left, sort.index), valueFor(right, sort.index))
        return sort.direction === 'asc' ? comparison : -comparison
      })
    }
    return matches
  }, [jobs, filters, sort, valueFor])
  const pageCount = Math.max(1, Math.ceil(sortedJobs.length / jobsPerPage))
  const currentPage = Math.min(page, pageCount)
  const firstJobIndex = (currentPage - 1) * jobsPerPage
  const visibleJobs = sortedJobs.slice(firstJobIndex, firstJobIndex + jobsPerPage)
  const jobRange = visibleJobs.length === 1 ? firstJobIndex + 1 : `${firstJobIndex + 1}–${firstJobIndex + visibleJobs.length}`
  const selection = visibleJobs.filter((job) => selectedJobs.includes(job.id))
  const selected = selection.length === 1 ? selection[0] : undefined
  const allVisibleSelected = visibleJobs.length > 0 && selection.length === visibleJobs.length

  useEffect(() => { setPage((previous) => Math.min(previous, pageCount)) }, [pageCount])

  const goToPage = (nextPage: number) => {
    setPage(nextPage)
    setSelectedJobs([])
    setRunResult(null)
    setRunError('')
    tableScroll.current?.scrollTo({ top: 0 })
  }
  const toggleSort = (index: number) => {
    setSort((current) => current?.index === index
      ? { index, direction: current.direction === 'asc' ? 'desc' : 'asc' }
      : { index, direction: 'asc' })
    goToPage(1)
  }
  const updateDashboardFilter = (index: number, value: string) => {
    onFilterChange(index, value)
    goToPage(1)
  }
  const selectJob = (jobId: number) => {
    setSelectedJobs((current) => current.includes(jobId) ? current.filter((id) => id !== jobId) : [...current, jobId])
    setRunResult(null)
    setRunError('')
  }
  const toggleAll = () => {
    setSelectedJobs(allVisibleSelected ? [] : visibleJobs.map((job) => job.id))
    setRunResult(null)
    setRunError('')
  }
  const runSelectedJob = async (job: DashboardJob, dates: URLSearchParams) => {
    if (running) return
    setRunTarget(null)
    setRunningJobId(job.id)
    setRunResult(null)
    setRunError('')
    try {
      const query = dates.size ? `?${dates}` : ''
      const response = await fetch(`${apiBaseUrl}/retirement-builder/jobs/${job.id}/run${query}`, { method: 'POST' })
      if (!response.ok) throw new Error(await readSaveError(response, 'Unable to run the job.'))
      setRunResult(await response.json() as JobRun)
      onRunSettled(job.id, 'Success')
    } catch (cause) {
      setRunError(cause instanceof TypeError
        ? 'Unable to reach the Retirement Builder service.'
        : cause instanceof Error ? cause.message : 'Unable to run the job.')
      onRunSettled(job.id, cause instanceof TypeError ? undefined : 'Failed')
    } finally {
      setRunningJobId(null)
    }
  }
  useEffect(() => {
    setDownloadError('')
    const files = runResult?.files ?? (runResult?.fileName ? [runResult] : [])
    const links = files.map(({ fileName, csv, excelRows }) => ({
      fileName, csv, excelRows, url: URL.createObjectURL(new Blob([csv], {
        type: excelRows != null ? 'text/plain;charset=utf-8' : 'text/csv;charset=utf-8',
      })),
    }))
    setDownloads(links)
    return () => links.forEach(({ url }) => URL.revokeObjectURL(url))
  }, [runResult])

  const downloadExcel = ({ fileName, csv, excelRows }: JobRunFile, delimiter: string) => {
    setDownloadError('')
    try {
      writeFile(reportWorkbook(csv, delimiter, excelRows), fileName.replace(/\.csv$/i, '') + '.xlsx')
    } catch {
      setDownloadError('Unable to create the Excel download. You can still download the report file.')
    }
  }

  return <section className="dashboard-card">
    <div className="dashboard-actions">
      <p className="dashboard-scope">Showing enabled jobs only.</p>
      <a className="button button-primary" href="/mapped_payroll_columns_HDT.xlsx" download="mapped_payroll_columns_HDT.xlsx">Template <span aria-hidden="true">⇩</span></a>
      <button className="button button-primary" onClick={onAdd}>Add</button>
      <button className="button button-primary" disabled={!selected} onClick={() => selected && onEdit(selected.id)}>Edit</button>
      <button className="button button-primary" disabled={!selected || running} onClick={() => selected && setRunTarget(selected)}>
        {running ? 'Running…' : 'Run'}
      </button>
    </div>
    {runError && <p className="dashboard-action-message" role="alert">{runError}</p>}
    {runResult && <div className="dashboard-action-message" role="status">
      {runResult.rowCount === 0 && !(runResult.files?.length ?? Number(Boolean(runResult.fileName)))
        ? 'No matching records. No files generated.'
        : `Generated ${runResult.rowCount} rows. Saved ${runResult.storedRows} rows to the database.`}
      {runResult.emailDelivery && <div>{reportEmailMessage(runResult.emailDelivery)}</div>}
      {downloads.length > 0 && <div className="report-downloads">
        {downloads.map((file) => <div className="report-download" key={file.fileName}>
          <a href={file.url} download={file.fileName}>{downloads.length === 1 ? file.excelRows != null ? 'Download File' : 'Download CSV' : file.fileName}</a>
          {delimiter?.length === 1 && <button type="button" className="report-excel-button"
            aria-label={downloads.length === 1 ? undefined : `Download Excel for ${file.fileName}`}
            onClick={() => downloadExcel(file, delimiter)}>Download Excel</button>}
        </div>)}
      </div>}
    </div>}
    {downloadError && <p className="dashboard-action-message" role="alert">{downloadError}</p>}
    <div className="jobs-table-wrap" ref={tableScroll}>
      <table className="jobs-table">
        <caption className="sr-only">Retirement Builder scheduled jobs</caption>
        <thead><tr>
          <th scope="col" className="jobs-select-column"><input type="checkbox" checked={allVisibleSelected} onChange={toggleAll} disabled={running} aria-label="Select all visible jobs" /></th>
          {headings.map((heading, index) => <th scope="col" key={heading} aria-sort={sort?.index === index ? sort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
            <div className="table-heading-sort">
              <button type="button" className="table-sort-button" onClick={() => toggleSort(index)} aria-label={`Sort by ${heading}`}>{heading}<span aria-hidden="true">{sort?.index === index ? sort.direction === 'asc' ? ' ↑' : ' ↓' : ' ↕'}</span></button>
              <input value={filters[index] ?? ''} onChange={(event) => updateDashboardFilter(index, event.target.value)} aria-label={`Filter ${heading}`} />
            </div>
          </th>)}
        </tr></thead>
        <tbody>{visibleJobs.length ? visibleJobs.map((job) => <tr key={job.id} className={selectedJobs.includes(job.id) ? 'selected-row' : undefined}>
          <td className="jobs-select-cell"><input type="checkbox" checked={selectedJobs.includes(job.id)} onChange={() => selectJob(job.id)} disabled={running} aria-label={`Select ${job.values[0]}`} /></td>
          {headings.map((_, index) => <td key={index} className={index === 9 ? 'status-cell' : ''}>
            {index === 0 ? <button type="button" className="file-name-link" onClick={() => onEdit(job.id)}>{valueFor(job, index)}</button> : valueFor(job, index)}
          </td>)}
        </tr>) : <tr><td className="empty-table" colSpan={headings.length + 1} role={status === 'error' ? 'alert' : undefined}>
          {status === 'error' ? 'Unable to load Retirement Builder jobs. Please try again.' : status === 'loading' ? 'Loading…' : 'No matching records found'}
        </td></tr>}</tbody>
      </table>
    </div>
    {sortedJobs.length > 0 && <nav className="jobs-pagination" aria-label="Job list pagination">
      <span aria-live="polite">{jobRange} of {sortedJobs.length} {sortedJobs.length === 1 ? 'job' : 'jobs'}</span>
      <div className="jobs-pagination-controls">
        <button type="button" className="button button-light" aria-label="Previous page"
          disabled={currentPage === 1 || running} onClick={() => goToPage(currentPage - 1)}>Previous</button>
        <span>Page {currentPage} of {pageCount}</span>
        <button type="button" className="button button-light" aria-label="Next page"
          disabled={currentPage === pageCount || running} onClick={() => goToPage(currentPage + 1)}>Next</button>
      </div>
    </nav>}
    {runTarget && <RunDateDialog jobName={runTarget.values[0]} onCancel={() => setRunTarget(null)}
      onRun={(dates) => void runSelectedJob(runTarget, dates)} />}
  </section>
}

function RunDateDialog({ jobName, onCancel, onRun }: {
  jobName: string
  onCancel: () => void
  onRun: (dates: URLSearchParams) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => element?.close()
  }, [])

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const start = String(fields.get('start_date') ?? '')
    const end = String(fields.get('end_date') ?? '')
    if ([start, end].some((value) => value && !validIsoDate(value))) {
      setError('Enter valid start and end dates.')
      return
    }
    if (start && end && start !== '1900-01-01' && end !== '1900-01-01' && start > end) {
      setError('Start Date must be on or before End Date.')
      return
    }
    const dates = new URLSearchParams()
    if (start) dates.set('start_date', start)
    if (end) dates.set('end_date', end)
    onRun(dates)
  }

  return <dialog className="run-date-modal" ref={dialog} aria-labelledby="run-date-title"
    onCancel={(event) => { event.preventDefault(); onCancel() }}>
    <form onSubmit={submit}>
      <h2 id="run-date-title">Run job</h2>
      <p>{jobName}</p>
      <div className="run-date-fields" aria-describedby="run-date-help">
        <label>Start Date<input type="date" name="start_date" autoFocus min="0001-01-01" max="9999-12-31"
          onInput={() => setError('')} /></label>
        <label>End Date<input type="date" name="end_date" min="0001-01-01" max="9999-12-31"
          onInput={() => setError('')} /></label>
      </div>
      <small id="run-date-help">Leave either date blank to leave that side of the range open.</small>
      <FieldError id="run-date-error" message={error} />
      <div className="run-date-actions">
        <button type="button" className="button button-light" onClick={onCancel}>Cancel</button>
        <button type="submit" className="button button-primary">Run</button>
      </div>
    </form>
  </dialog>
}

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <span className="field-error" id={id} role="alert">{message}</span> : null
}

function GeneralStep({
  fileName, fileFormat, description, outputFileNameFormat, reportSource,
  isEdit, enable, onEnableChange, storeResultsToTable, selectedFile,
  importing, uploadError, errors, onFileNameChange, onFileFormatChange, onDescriptionChange,
  onOutputFileNameFormatChange, onStoreResultsChange, onFileChange, onCancel, onSubmit,
}: {
  fileName: string
  fileFormat: string
  description: string
  outputFileNameFormat: string
  reportSource: ReportSource
  isEdit: boolean
  enable: boolean
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
  const { values, loading } = useContext(OptionsContext)
  const filenameOptions = values.outputFileNameFormats
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
            includeSavedOption={false}
            errorId={errors?.fileFormat ? 'retirement-file-format-error' : undefined} />
          <FieldError id="retirement-file-format-error" message={errors?.fileFormat} />
        </div>
        <label className="general-field general-field-full">Description<textarea value={description} onChange={(event) => onDescriptionChange(event.target.value)} /></label>
        <div className="general-field general-field-full">
          <span>Output File Name Format</span>
          <SearchableSelect options={filenameOptions.map((option) => option.value)}
            optionLabels={Object.fromEntries(filenameOptions.map((option) => [option.value, option.label]))}
            value={loading && !filenameOptions.length ? '' : outputFileNameFormat}
            onValueChange={onOutputFileNameFormatChange} ariaLabel="Output file name format"
            includeSavedOption={false} />
          {reportSource === 'companyPayroll' && outputFileNameFormat.split('_').includes('CLIENT') &&
            <small className="general-field-help">Client ID uses the payroll company ID in file names.</small>}
        </div>
      </div>
      <section className="general-option-section">
        <div className="general-options">
          {isEdit && <label className="general-option">
            <input type="checkbox" checked={enable} onChange={(event) => onEnableChange(event.target.checked)} />
            <span>Enable</span>
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

function ScheduleStep({ schedule, storedStartDateTime, errors, onChange, onBack, onNext }: {
  schedule: ScheduleValues
  storedStartDateTime?: string | null
  errors?: Record<keyof ScheduleValues, string>
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
            aria-invalid={!!errors?.startDate}
            aria-describedby={[
              'retirement-start-date-help',
              storedStartDateTime && 'retirement-stored-start-date',
              errors?.startDate && 'retirement-start-date-error',
            ].filter(Boolean).join(' ')}
            onInput={(event) => onChange({ startDate: event.currentTarget.value })}
            onChange={(event) => onChange({ startDate: event.currentTarget.value })} />
          <small id="retirement-start-date-help" className="general-field-help">Leave the schedule blank for manual runs only.</small>
          {storedStartDateTime && <small id="retirement-stored-start-date" className="general-field-help">
            Stored start date and time <time dateTime={storedStartDateTime.replace(' ', 'T')}>{storedStartDateTime}</time>
          </small>}
          <FieldError id="retirement-start-date-error" message={errors?.startDate} />
        </div>
        <label className="schedule-field">Build Frequency
          <SearchableSelect options={[]} value={schedule.buildFrequency} onValueChange={(buildFrequency) => onChange({ buildFrequency })} ariaLabel="Build frequency"
            clearLabel="Select frequency" errorId={errors?.buildFrequency ? 'retirement-frequency-error' : undefined} />
          <FieldError id="retirement-frequency-error" message={errors?.buildFrequency} />
        </label>
        <fieldset className="schedule-time-field">
          <legend>Run Time</legend>
          <div className="time-row">
            <SearchableSelect options={[]} value={schedule.hour} onValueChange={(hour) => onChange({ hour })} ariaLabel="Hour" placeholder="Hour" errorId={errors?.hour ? 'retirement-hour-error' : undefined} />
            <SearchableSelect options={[]} value={schedule.minute} onValueChange={(minute) => onChange({ minute })} ariaLabel="Minute" placeholder="Minute" errorId={errors?.minute ? 'retirement-minute-error' : undefined} />
            <SearchableSelect options={[]} value={schedule.meridiem} onValueChange={(meridiem) => onChange({ meridiem })} ariaLabel="AM or PM" placeholder="AM/PM" errorId={errors?.meridiem ? 'retirement-meridiem-error' : undefined} />
          </div>
          <FieldError id="retirement-hour-error" message={errors?.hour} />
          <FieldError id="retirement-minute-error" message={errors?.minute} />
          <FieldError id="retirement-meridiem-error" message={errors?.meridiem} />
        </fieldset>
        <label className="schedule-field">Week
          <SearchableSelect options={[]} value={schedule.week} onValueChange={(week) => onChange({ week })} ariaLabel="Week"
            clearLabel="Select day" errorId={errors?.week ? 'retirement-week-error' : undefined} />
          <FieldError id="retirement-week-error" message={errors?.week} />
        </label>
      </div>
    </div>
    <div className="step-footer"><button className="button button-light" onClick={onBack}>Back</button><button className="button button-primary" onClick={onNext}>Next</button></div>
  </div>
}

function MappingNumber({ label, value, onChange, validate, minimum = 0, maximum = 2147483647 }: {
  label: string; value: string; onChange: (value: string) => void; validate: boolean; minimum?: number; maximum?: number
}) {
  const errorId = useId()
  const invalid = validate && (minimum > 0 || !!value.trim()) && !validWholeNumber(value, minimum, maximum)
  return <><input aria-label={label} value={value} inputMode="numeric" aria-invalid={invalid}
    aria-describedby={invalid ? errorId : undefined} onChange={(event) => onChange(event.target.value)} />
    <FieldError id={errorId} message={invalid ? `Enter a whole number from ${minimum} to ${maximum}.` : undefined} /></>
}

function MappingStep({ requiresDefault, includeHeader, rows, fixed, validate, onHeaderChange, onRowChange, onDelete, onOpenSettings, onBack, onNext }: {
  requiresDefault: (source: string) => boolean
  includeHeader: boolean
  rows: MappingRow[]
  fixed: boolean
  validate: boolean
  onHeaderChange: (checked: boolean) => void
  onRowChange: (id: number, patch: Partial<MappingRow>) => void
  onDelete: (id: number) => void
  onOpenSettings: () => void
  onBack: () => void
  onNext: () => void
}) {
  const { values } = useContext(OptionsContext)
  const columnLabel = (column: string) => mappingLabel(column, values.mappingColumnLabels)
  const typeFor = (column: string) => mappingColumnType(columnLabel(column), values.mappingColumnTypes)
  const formatsFor = (type: string) => {
    const buckets = ['phone', 'email', 'ssn'].includes(type) ? [type, 'text', 'all'] : [type, 'all']
    // Left/right justification pads any value, so it stays selectable (and survives a column change) for numbers and dates too.
    const padding = (values.mappingFormatsByType.text ?? []).filter((code) => code === 'RA' || code === 'LA')
    return Array.from(new Set([...buckets.flatMap((bucket) => values.mappingFormatsByType[bucket] ?? []), ...padding]))
  }

  return <div className="form-step mapping-step">
    <div className="mapping-scroll" role="region" aria-label="Dataset mapping rows" tabIndex={0}>
      <div className="mapping-controls">
        <h3>Dataset Mapping</h3>
        <div className="mapping-header-actions">
          <label className="check-label" title="Adds the column names above the mapped records.">
            <input type="checkbox" checked={includeHeader} onChange={(event) => onHeaderChange(event.target.checked)} />Include Header Row
          </label>
          <button type="button" className="icon-button" onClick={onOpenSettings} aria-label="Manage dataset settings" title="Manage dataset settings"><Settings aria-hidden="true" /></button>
          <button className="icon-button" onClick={onOpenSettings} aria-label="Add file setting rule" title="Add a sort or condition rule (opens File Settings)"><ToolIcon name="plus" /></button>
        </div>
      </div>
      <div className="mapping-table-wrap">
        <table className="mapping-table">
          <thead><tr>{['Field Name', 'Start Position', 'Length', 'Record Type', 'Default Value', 'Mapping Column', 'Format', 'Action'].map((heading) => <th scope="col" key={heading} title={heading === 'Start Position' ? 'FIXED format only. Zero-based: 0 is the first character of the line.' : undefined}>{heading}</th>)}</tr></thead>
          <tbody>{rows.map((row, index) => {
            const label = row.field || 'New'
            const fixedLengthRequired = fixed && !(includeHeader && ['H', 'HEADER'].includes(row.recordType.trim().toUpperCase()))
            const type = typeFor(row.mapping || row.field)
            const formats = formatsFor(type)
            const formatValue = formats.includes(row.format) ? row.format
              : formats.find((code) => values.mappingFormatLabels[code] === row.format) ?? row.format
            const needsDefault = requiresDefault(row.mapping.trim() || row.field.trim())
            const defaultError = needsDefault && !row.defaultValue && (validate || !!row.mapping)
            const defaultErrorId = `mapping-default-error-${row.id}`
            const changeSource = (patch: Pick<MappingRow, 'field'> | Pick<MappingRow, 'mapping'>) => {
              const next = { ...row, ...patch }
              const nextType = typeFor(next.mapping || next.field)
              const format = nextType !== type && !formatsFor(nextType).includes(formatValue) ? '' : row.format
              onRowChange(row.id, { ...patch, format })
            }
            return <tr key={row.id}>
              <td>
                <input aria-label={`Field Name ${index + 1}`} value={row.field}
                  aria-invalid={validate && !row.field.trim()}
                  aria-describedby={validate && !row.field.trim() ? `mapping-field-error-${row.id}` : undefined}
                  onChange={(event) => changeSource({ field: event.target.value })} />
                <FieldError id={`mapping-field-error-${row.id}`} message={validate && !row.field.trim() ? 'Enter a field name.' : undefined} />
              </td>
              <td><MappingNumber label={`${row.field} start position`} value={row.startPosition} validate={validate} onChange={(startPosition) => onRowChange(row.id, { startPosition })} /></td>
              <td><MappingNumber label={`${row.field} length`} value={row.length} validate={validate}
                minimum={fixedLengthRequired ? 1 : 0} maximum={fixedLengthRequired ? 1000 : 2147483647}
                onChange={(length) => onRowChange(row.id, { length })} /></td>
              <td><SearchableSelect options={['Header', 'Detail', 'Trailer']} value={row.recordType} onValueChange={(recordType) => onRowChange(row.id, { recordType })} ariaLabel={`${label} record type`} /></td>
              <td>
                <input aria-label={`${row.field} default value`} value={row.defaultValue} aria-required={needsDefault}
                  aria-invalid={defaultError} aria-describedby={defaultError ? defaultErrorId : undefined}
                  onChange={(event) => onRowChange(row.id, { defaultValue: event.target.value })} />
                <FieldError id={defaultErrorId} message={defaultError ? 'Enter a default value for this payroll field.' : undefined} />
              </td>
              <td><SearchableSelect options={values.mappingColumns} value={columnLabel(row.mapping)} onValueChange={(mapping) => changeSource({ mapping })}
                ariaLabel={`${label} mapping column`} clearLabel="Same as Field Name" includeSavedOption={false} /></td>
              <td><SearchableSelect options={formats} optionLabels={values.mappingFormatLabels}
                value={formatValue} onValueChange={(format) => onRowChange(row.id, { format })}
                ariaLabel={`${label} format`} clearLabel="No format" includeSavedOption={false} /></td>
              <td><button className="icon-button trash" onClick={() => onDelete(row.id)} aria-label={`Delete ${row.field} mapping`} title={`Delete ${row.field} mapping`}><ToolIcon name="trash" /></button></td>
            </tr>
          })}{!rows.length && <tr><td colSpan={8}>
            {validate ? <span className="field-error" role="alert">Add at least one dataset mapping.</span> : 'No mappings added.'}
          </td></tr>}</tbody>
        </table>
      </div>
    </div>
    <div className="step-footer"><button className="button button-light" onClick={onBack}>Back</button><button className="button button-primary" onClick={onNext}>Next</button></div>
  </div>
}

function SubscriptionsStep({
  reportSource, mergeFiles, subscriptions, error, saving, validate,
  onMergeChange, onClientChange, onCompanyChange, onEmailChange, onAdd, onDelete, onBack, onFinish,
}: {
  reportSource: ReportSource
  mergeFiles: boolean
  subscriptions: Subscription[]
  error: string
  saving: boolean
  validate: boolean
  onMergeChange: (checked: boolean) => void
  onClientChange: (id: number, client: string) => void
  onCompanyChange: (id: number, companyId: number) => void
  onEmailChange: (id: number, email: string, draft: string) => void
  onAdd: () => void
  onDelete: (id: number) => void
  onBack: () => void
  onFinish: () => void
}) {
  const { values } = useContext(OptionsContext)
  const payroll = reportSource === 'companyPayroll'
  const companyOptions = Object.entries(values.payrollCompanies).map(([id, name]) => `${id} - ${name}`)
  const [clientCatalog, setClientCatalog] = useState({ rows: [] as ClientOption[], loading: true, error: '' })
  const clientOptions = clientCatalog.rows.map(({ id }) => String(id))
  const clientLabels = Object.fromEntries(clientCatalog.rows.map(({ id, label }) => [String(id), label]))
  useEffect(() => {
    if (payroll) return
    const controller = new AbortController()
    fetch(`${apiBaseUrl}/retirement-builder/clients`, { signal: controller.signal, cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('Unable to load the client list.')
        return response.json() as Promise<ClientOption[]>
      })
      .then((rows) => {
        if (!controller.signal.aborted) setClientCatalog({ rows, loading: false, error: '' })
      })
      .catch(() => {
        if (!controller.signal.aborted) setClientCatalog({
          rows: [], loading: false, error: 'Unable to load the client list. You can still enter a client ID.',
        })
      })
    return () => controller.abort()
  }, [payroll])

  return <div className="form-step subscriptions-step">
    <div className="subscription-toolbar">
      <label className="check-label" title="Combines each recipient's emailed attachments into one file. Generated report files are not changed."><input type="checkbox" checked={mergeFiles} onChange={(event) => onMergeChange(event.target.checked)} />Merge Files <small className="general-field-help">(emailed attachments only)</small></label>
      <button className="button button-primary" onClick={onAdd}><span className="button-icon"><ToolIcon name="plus" /></span>Add Row</button>
    </div>
    {error && <p className="dashboard-action-message" role="alert">{error}</p>}
    <div className="subscription-table-wrap">
      <table className="subscription-table">
        <thead><tr><th scope="col">{payroll ? 'Payroll Company' : 'Clients'}</th><th scope="col">Mail</th><th scope="col">Action</th></tr></thead>
        <tbody>{subscriptions.map((subscription, index) => {
          const companyName = subscription.companyId === undefined ? undefined : values.payrollCompanies[subscription.companyId]
          return <tr key={subscription.id}>
            <td>{payroll ? <>
              <SearchableSelect options={companyOptions}
                value={companyName === undefined ? '' : `${subscription.companyId} - ${companyName}`}
                onValueChange={(value) => {
                  const companyId = parseClientId(value)
                  if (companyId !== null) onCompanyChange(subscription.id, companyId)
                }}
                ariaLabel={`Payroll company ${index + 1}`} searchPlaceholder="Search payroll companies…" placeholder="Select company" />
              {subscription.client && <small className="general-field-help">Select a payroll company to enable email for this row.</small>}
            </> : <SearchableSelect options={clientOptions} optionLabels={clientLabels} includeSavedOption={false}
              optionsLoading={clientCatalog.loading} optionsError={clientCatalog.error}
              value={String(parseClientId(subscription.client) ?? '')} onValueChange={(client) => onClientChange(subscription.id, client)}
              ariaLabel={`Client ${index + 1}`} allowCustom placeholder="Select client"
              searchPlaceholder="Search or enter a client ID…"
              canAddCustom={(value) => {
                const id = /^[0-9]+$/.test(value) ? parseClientId(value) : null
                return id !== null && !(String(id) in clientLabels)
              }} />}
            </td>
            <td><EmailTagsInput value={subscription.email} draft={subscription.emailDraft ?? ''} validate={validate}
              onChange={(email, draft) => onEmailChange(subscription.id, email, draft)} ariaLabel={`Email ${index + 1}`} /></td>
            <td><button className="icon-button trash" onClick={() => onDelete(subscription.id)} aria-label={`Delete subscription ${index + 1}`}
              title={`Delete subscription ${index + 1}`}><ToolIcon name="trash" /></button></td>
          </tr>
        })}</tbody>
      </table>
    </div>
    <div className="step-footer"><button className="button button-light" onClick={onBack}>Back</button><button className="button button-primary" onClick={onFinish} disabled={saving} aria-busy={saving}>{saving ? 'Saving…' : 'Finish'}</button></div>
  </div>
}
function FileSettingsModal({ reportSource, mappingRows, initialSorting, initialConditional, onSave, onClose }: {
  reportSource: ReportSource
  mappingRows: MappingRow[]
  initialSorting: SortingRow[]
  initialConditional: ConditionalRow[]
  onSave: (sortingOrder: SortingRow[], conditionalStatements: ConditionalRow[]) => void
  onClose: () => void
}) {
  const { values } = useContext(OptionsContext)
  const columnNames = new Map<string, string>()
  const mappedColumns = mappingRows.map((row) => mappingLabel(row.mapping.trim() || row.field.trim(), values.mappingColumnLabels))
  for (const name of [...mappedColumns, ...values.mappingColumns]) {
    if (name && !columnNames.has(name.toLowerCase())) columnNames.set(name.toLowerCase(), name)
  }
  const mappingColumns = reportSource === 'companyPayroll' ? values.payrollMappingColumns : Array.from(columnNames.values())
  const isDateColumn = (column: string) => reportSource === 'companyPayroll'
    ? column.trim().toLowerCase() === 'pay date'
    : mappingColumnType(column, values.mappingColumnTypes) === 'date'
  const [sortingRows, setSortingRows] = useState(() => initialSorting.map((row, index) => [row.orderBy || String(index + 1), mappingLabel(row.mappingColumn, values.mappingColumnLabels)]))
  const [conditionalRows, setConditionalRows] = useState(() => initialConditional.map((row) => [row.mappingColumn, row.condition, row.value]))
  const [sortError, setSortError] = useState('')
  const dialog = useRef<HTMLElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  const saveRows = () => {
    const priorities = sortingRows.map(([orderBy, mappingColumn]) => ({ orderBy, mappingColumn }))
    const priorityError = sortingPriorityError(priorities)
    if (priorityError) {
      setSortError(priorityError)
      return
    }
    if (conditionalRows.some(([column, condition]) => !column.trim() || !values.comparisonOperators.includes(condition))) {
      setSortError('Choose a mapping column and comparison operator for each condition.')
      return
    }
    const invalidCondition = conditionalRows.find(([column, , value]) => {
      const number = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())
      return isDateColumn(column) ? !validIsoDate(value) && (reportSource === 'companyPayroll' || !number) : !number
    })
    if (invalidCondition) {
      setSortError(isDateColumn(invalidCondition[0])
        ? 'Enter a valid date in YYYY-MM-DD format.'
        : 'Enter a number for each numeric condition.')
      return
    }
    onSave(
      normalizeSortingPriorities(priorities),
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
        description="Priority 1 is applied first, followed by 2, 3, and so on."
        columns={['Order By', 'Mapping Column', 'Action']}
        mappingColumns={mappingColumns}
        rows={sortingRows}
        onAdd={() => setSortingRows((rows) => {
          const nextPriority = rows.reduce((max, [priority]) => validWholeNumber(priority, 1) ? Math.max(max, Number(priority)) : max, 0) + 1
          if (nextPriority <= 2147483647) return [...rows, [String(nextPriority), '']]
          return [...rows, ['', '']].map(([, column], index) => [String(index + 1), column])
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
        comparisonOperators={values.comparisonOperators}
        isDateColumn={isDateColumn}
        rows={conditionalRows}
        onAdd={() => setConditionalRows((rows) => [...rows, ['', '', '']])}
        onDelete={(index) => setConditionalRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}
        onChange={(rowIndex, columnIndex, value) => setConditionalRows((rows) => rows.map((row, index) => index === rowIndex ? row.map((cell, cellIndex) => cellIndex === columnIndex ? value : cell) : row))}
      />
    </section>
  </div>
}

function SettingsTable({ title, description, columns, mappingColumns, comparisonOperators = [], isDateColumn, rows, onAdd, onDelete, onChange }: {
  title: string
  description: string
  columns: string[]
  mappingColumns: string[]
  comparisonOperators?: string[]
  isDateColumn?: (column: string) => boolean
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
            <input type="number" min="1" max="2147483647" step="1" value={value}
              onChange={(event) => change(event.target.value)} aria-label={label} />
          </td>
          if (column === 'Mapping Column') return <td key={column}>
            <SearchableSelect options={mappingColumns} value={value} onValueChange={change} ariaLabel={label} clearLabel="Select a column" allowCustom />
          </td>
          if (column === 'Condition') return <td key={column}>
            <select value={value} onChange={(event) => change(event.target.value)} aria-label={label}>
              <option value="">Select operator</option>
              {value && !comparisonOperators.includes(value) && <option value={value} disabled>{value} (unsupported)</option>}
              {comparisonOperators.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
            </select>
          </td>
          return <td key={column}>
            <input value={value} placeholder={isDateColumn?.(row[0]) ? 'YYYY-MM-DD' : 'Enter value'}
              onChange={(event) => change(event.target.value)} aria-label={label} />
          </td>
        })}
      </tr>) : <tr><td colSpan={columns.length} className="settings-empty">No items added yet.</td></tr>}</tbody>
    </table>
  </section>
}

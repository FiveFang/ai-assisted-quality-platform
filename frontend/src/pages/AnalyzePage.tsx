import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, ChevronDown, ChevronUp, CheckCircle, XCircle, Clock, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { api, fetcher } from '@/api/client'
import type { AnalysisProgress } from '@/types/api'

const DRAFT_KEY = 'qa_platform_analyze_draft'

type DraftValues = Pick<FormValues, 'reference' | 'prd' | 'jira' | 'openapi'>

function loadDraft(): DraftValues | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    return raw ? (JSON.parse(raw) as DraftValues) : null
  } catch {
    return null
  }
}

function saveDraft(values: DraftValues) {
  try {
    if (values.reference || values.prd || values.jira || values.openapi) {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(values))
    }
  } catch { /* storage full or unavailable — ignore */ }
}

function clearDraft() {
  try { localStorage.removeItem(DRAFT_KEY) } catch { /* ignore */ }
}

const TOKEN_PRESETS = [
  { label: '16K (default)', value: 16384 },
  { label: '32K', value: 32768 },
  { label: '64K', value: 65536 },
  { label: '100K', value: 100000 },
] as const

const schema = z.object({
  reference: z.string().min(1, 'Project name is required'),
  prd: z.string().optional(),
  jira: z.string().optional(),
  openapi: z.string().optional(),
  max_tokens: z.number().int().positive().optional(),
}).refine(
  (d) => d.prd || d.jira || d.openapi,
  { message: 'Provide at least one input (PRD, Jira, or OpenAPI)', path: ['prd'] },
)

type FormValues = z.infer<typeof schema>

const PIPELINE_STEPS: { key: string; label: string; detail: string }[] = [
  { key: 'parsing',    label: 'Parsing artifacts',            detail: 'PRD · Jira · OpenAPI' },
  { key: 'extracting', label: 'Extracting requirements',      detail: 'Claude Opus — most intensive step' },
  { key: 'enriching',  label: 'Extracting workflows & rules', detail: 'Entities · RAG enrichment · parallel' },
  { key: 'ambiguities',label: 'Detecting ambiguities',        detail: 'Checking for vague or conflicting requirements' },
  { key: 'scoring',    label: 'Scoring confidence',           detail: 'Pure calculation — no LLM needed' },
  { key: 'assembling', label: 'Assembling result',            detail: 'Schema validation & final JSON' },
]

const STEP_ORDER = PIPELINE_STEPS.map((s) => s.key)

function stepStatus(
  key: string,
  currentStep: string | null,
  pipelineStatus: string,
): 'done' | 'active' | 'pending' | 'failed' {
  if (pipelineStatus === 'complete') return 'done'
  const currentIdx = currentStep ? STEP_ORDER.indexOf(currentStep) : 0
  const keyIdx = STEP_ORDER.indexOf(key)
  if (pipelineStatus === 'failed') {
    if (keyIdx < currentIdx) return 'done'
    if (keyIdx === currentIdx) return 'failed'
    return 'pending'
  }
  if (keyIdx < currentIdx) return 'done'
  if (keyIdx === currentIdx) return 'active'
  return 'pending'
}

function PipelineProgress({ progress }: { progress: AnalysisProgress | null; }) {
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef(Date.now())

  useEffect(() => {
    startRef.current = Date.now()
    setElapsed(0)
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 1000)
    return () => clearInterval(t)
  }, [])

  const currentStep = progress?.current_step ?? 'parsing'
  const pipelineStatus = progress?.status ?? 'running'
  const displayElapsed = progress?.elapsed_seconds != null ? Math.round(progress.elapsed_seconds) : elapsed

  return (
    <div className="rounded-lg border bg-muted/20 p-4 space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">
          {pipelineStatus === 'failed' ? 'Pipeline failed' : pipelineStatus === 'complete' ? 'Analysis complete' : 'Running pipeline…'}
        </span>
        <span className="text-xs text-muted-foreground tabular-nums">{displayElapsed}s</span>
      </div>

      <ul className="space-y-2">
        {PIPELINE_STEPS.map(({ key, label, detail }) => {
          const status = stepStatus(key, currentStep, pipelineStatus)
          return (
            <li key={key} className="flex items-start gap-2.5 text-sm">
              <span className="mt-0.5 shrink-0">
                {status === 'done'    && <CheckCircle className="h-4 w-4 text-green-500" />}
                {status === 'active'  && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
                {status === 'pending' && <Clock className="h-4 w-4 text-muted-foreground/40" />}
                {status === 'failed'  && <XCircle className="h-4 w-4 text-destructive" />}
              </span>
              <div className="min-w-0">
                <span className={
                  status === 'done'    ? 'text-foreground' :
                  status === 'active'  ? 'text-foreground font-medium' :
                  status === 'failed'  ? 'text-destructive' :
                  'text-muted-foreground'
                }>
                  {label}
                </span>
                {status === 'active' && (
                  <p className="text-xs text-muted-foreground mt-0.5">{detail}</p>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      {progress?.error && (
        <p className="text-xs text-destructive border-t pt-2 mt-1">{progress.error}</p>
      )}
    </div>
  )
}

function InputSection({
  title, badge, children, defaultOpen = false,
}: { title: string; badge?: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-lg border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-sm"
      >
        <div className="flex items-center gap-2">
          <span className="font-medium">{title}</span>
          {badge && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{badge}</span>
          )}
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>
      {open && <div className="p-4 border-t">{children}</div>}
    </div>
  )
}

export function AnalyzePage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState<AnalysisProgress | null>(null)
  const [draftRestored, setDraftRestored] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const maxTokens = watch('max_tokens')

  // Restore draft on mount
  useEffect(() => {
    const draft = loadDraft()
    if (draft && (draft.reference || draft.prd || draft.jira || draft.openapi)) {
      reset(draft)
      setDraftRestored(true)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-save draft as user types (debounced 600ms)
  const watchedFields = watch(['reference', 'prd', 'jira', 'openapi'])
  useEffect(() => {
    const [reference, prd, jira, openapi] = watchedFields
    const t = setTimeout(() => saveDraft({ reference, prd, jira, openapi }), 600)
    return () => clearTimeout(t)
  }, [watchedFields])

  // Poll progress while the request is in-flight
  useEffect(() => {
    if (!isSubmitting || !jobId) return
    let cancelled = false

    const poll = async () => {
      try {
        const p = await fetcher<AnalysisProgress>(`/requirements/progress/${jobId}`)
        if (!cancelled) setProgress(p)
      } catch {
        // 404 until the first progress event arrives — ignore
      }
    }

    poll()
    const interval = setInterval(poll, 1500)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [isSubmitting, jobId])

  const onSubmit = async (values: FormValues) => {
    setError(null)
    setProgress(null)
    const id = crypto.randomUUID()
    setJobId(id)

    const raw_inputs: Record<string, string> = {}
    if (values.prd)     raw_inputs.prd = values.prd
    if (values.jira)    raw_inputs.jira = values.jira
    if (values.openapi) raw_inputs.openapi = values.openapi

    try {
      const source_type = values.prd ? 'PRD' : values.jira ? 'JIRA' : 'OPENAPI'
      const result = await api.analyzeRequirements({
        source_type,
        reference: values.reference,
        raw_inputs,
        job_id: id,
        ...(values.max_tokens ? { max_tokens: values.max_tokens } : {}),
      })
      clearDraft()
      navigate(`/requirements/${result.requirement_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">New Analysis</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Provide your requirement artifacts. All inputs are optional — submit what you have.
        </p>
      </div>

      {draftRestored && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm dark:border-amber-800 dark:bg-amber-950/30">
          <div className="flex items-center gap-2 text-amber-800 dark:text-amber-300">
            <RotateCcw className="h-3.5 w-3.5 shrink-0" />
            <span>Draft restored from your last session.</span>
          </div>
          <button
            type="button"
            onClick={() => { clearDraft(); reset({}); setDraftRestored(false) }}
            className="ml-4 text-xs text-amber-600 underline-offset-2 hover:underline dark:text-amber-400"
          >
            Clear
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="reference">Project name / reference</Label>
          <Input
            id="reference"
            placeholder="e.g. checkout-v2-redesign"
            {...register('reference')}
          />
          {errors.reference && (
            <p className="text-xs text-destructive">{errors.reference.message}</p>
          )}
        </div>

        <div className="space-y-3">
          <InputSection title="PRD / Design Doc" badge="text" defaultOpen>
            <Textarea
              rows={10}
              placeholder="Paste your PRD or design document here..."
              className="font-mono text-xs"
              {...register('prd')}
            />
          </InputSection>
          <InputSection title="Jira Stories" badge="JSON or text">
            <Textarea
              rows={8}
              placeholder="Paste exported Jira JSON or story descriptions..."
              className="font-mono text-xs"
              {...register('jira')}
            />
          </InputSection>
          <InputSection title="OpenAPI Spec" badge="YAML or JSON">
            <Textarea
              rows={8}
              placeholder="Paste your OpenAPI/Swagger spec here..."
              className="font-mono text-xs"
              {...register('openapi')}
            />
          </InputSection>
        </div>

        {errors.prd?.message && (
          <p className="text-sm text-destructive">{errors.prd.message}</p>
        )}

        <InputSection title="Advanced options">
          <div className="space-y-2">
            <Label className="text-sm">Max output tokens per LLM call</Label>
            <p className="text-xs text-muted-foreground">
              Increase if analysis fails with a truncation or JSON parse error on large inputs.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {TOKEN_PRESETS.map(({ label, value }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setValue('max_tokens', maxTokens === value ? undefined : value)}
                  className={[
                    'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                    maxTokens === value
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-input bg-background hover:bg-muted',
                  ].join(' ')}
                >
                  {label}
                </button>
              ))}
            </div>
            {maxTokens && maxTokens > 32768 && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                High token limits increase cost and latency significantly.
              </p>
            )}
          </div>
        </InputSection>

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm">
            <p className="font-medium text-destructive mb-1">Analysis failed</p>
            <p className="text-destructive/80 break-words">{error}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="submit" disabled={isSubmitting} className="min-w-32">
            {isSubmitting ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing…</>
            ) : (
              'Run Analysis →'
            )}
          </Button>
        </div>

        {isSubmitting && <PipelineProgress progress={progress} />}
      </form>
    </div>
  )
}

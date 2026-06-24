import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, ChevronDown, ChevronUp, CheckCircle2, XCircle, RotateCcw, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import useSWR from 'swr'
import { api, fetcher } from '@/api/client'
import type { AnalysisProgress, ModelsResponse } from '@/types/api'

/* ─── Draft persistence ────────────────────────────────────────────── */

const DRAFT_KEY = 'qa_platform_analyze_draft'

type DraftValues = Pick<FormValues, 'reference' | 'prd' | 'jira' | 'openapi'>

function loadDraft(): DraftValues | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    return raw ? (JSON.parse(raw) as DraftValues) : null
  } catch { return null }
}

function saveDraft(values: DraftValues) {
  try {
    if (values.reference || values.prd || values.jira || values.openapi)
      localStorage.setItem(DRAFT_KEY, JSON.stringify(values))
  } catch { /* ignore */ }
}

function clearDraft() {
  try { localStorage.removeItem(DRAFT_KEY) } catch { /* ignore */ }
}

/* ─── Token presets ─────────────────────────────────────────────────── */

const TOKEN_PRESETS = [
  { label: '16K (default)', value: 16384 },
  { label: '32K', value: 32768 },
  { label: '64K', value: 65536 },
  { label: '100K', value: 100000 },
] as const

/* ─── Form schema ───────────────────────────────────────────────────── */

const schema = z.object({
  reference: z.string().min(1, 'Project name is required'),
  prd: z.string().optional(),
  jira: z.string().optional(),
  openapi: z.string().optional(),
  max_tokens: z.number().int().positive().optional(),
  model: z.string().optional(),
}).refine(
  (d) => d.prd || d.jira || d.openapi,
  { message: 'Provide at least one input (PRD, Jira, or OpenAPI)', path: ['prd'] },
)

type FormValues = z.infer<typeof schema>

/* ─── Pipeline stepper ──────────────────────────────────────────────── */

const PIPELINE_STEPS: { key: string; label: string; detail: string }[] = [
  { key: 'parsing',     label: 'Parse artifacts',         detail: 'PRD · Jira · OpenAPI' },
  { key: 'extracting',  label: 'Extract requirements',    detail: 'Claude Opus — most intensive' },
  { key: 'enriching',   label: 'Enrich & classify',       detail: 'Workflows · rules · entities · RAG' },
  { key: 'ambiguities', label: 'Detect ambiguities',      detail: 'Vague or conflicting requirements' },
  { key: 'scoring',     label: 'Score confidence',        detail: 'Pure calculation — no LLM' },
  { key: 'assembling',  label: 'Assemble result',         detail: 'Schema validation & final JSON' },
]

const STEP_ORDER = PIPELINE_STEPS.map((s) => s.key)

type StepState = 'done' | 'active' | 'pending' | 'failed'

function stepStatus(key: string, currentStep: string | null, pipelineStatus: string): StepState {
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

function PipelineProgress({ progress }: { progress: AnalysisProgress | null }) {
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

  const statusLabel =
    pipelineStatus === 'failed' ? 'Pipeline failed' :
    pipelineStatus === 'complete' ? 'Analysis complete' :
    'Running analysis…'

  return (
    <div className="rounded-2xl border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{statusLabel}</span>
        <span className="text-xs text-muted-foreground tabular-nums">{displayElapsed}s</span>
      </div>

      <div className="space-y-1">
        {PIPELINE_STEPS.map(({ key, label, detail }, idx) => {
          const status = stepStatus(key, currentStep, pipelineStatus)
          const isLast = idx === PIPELINE_STEPS.length - 1

          return (
            <div key={key} className="flex gap-3">
              {/* Icon + connector line */}
              <div className="flex flex-col items-center">
                <div className={[
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold transition-all',
                  status === 'done'    ? 'bg-emerald-100 text-emerald-700' :
                  status === 'active'  ? 'bg-primary text-primary-foreground shadow-md shadow-primary/30' :
                  status === 'failed'  ? 'bg-red-100 text-red-600' :
                  'bg-muted text-muted-foreground/50',
                ].join(' ')}>
                  {status === 'done'   && <CheckCircle2 className="h-3.5 w-3.5" />}
                  {status === 'active' && <Loader2 className="h-3 w-3 animate-spin" />}
                  {status === 'failed' && <XCircle className="h-3.5 w-3.5" />}
                  {status === 'pending' && <span>{idx + 1}</span>}
                </div>
                {!isLast && (
                  <div className={[
                    'w-px flex-1 my-0.5',
                    status === 'done' ? 'bg-emerald-200' : 'bg-border',
                  ].join(' ')} style={{ minHeight: '12px' }} />
                )}
              </div>

              {/* Step info */}
              <div className="pb-3 min-w-0">
                <span className={[
                  'text-sm',
                  status === 'done'    ? 'text-foreground' :
                  status === 'active'  ? 'text-foreground font-medium' :
                  status === 'failed'  ? 'text-destructive' :
                  'text-muted-foreground',
                ].join(' ')}>
                  {label}
                </span>
                {status === 'active' && (
                  <p className="text-xs text-muted-foreground mt-0.5">{detail}</p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {progress?.error && (
        <p className="text-xs text-destructive border-t pt-3">{progress.error}</p>
      )}
    </div>
  )
}

/* ─── Collapsible input section ─────────────────────────────────────── */

function InputSection({
  title, badge, children, defaultOpen = false,
}: { title: string; badge?: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors text-sm"
      >
        <div className="flex items-center gap-2.5">
          <span className="font-medium">{title}</span>
          {badge && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{badge}</span>
          )}
        </div>
        {open
          ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
          : <ChevronDown className="h-4 w-4 text-muted-foreground" />
        }
      </button>
      {open && <div className="px-4 pb-4 border-t">{children && <div className="pt-3">{children}</div>}</div>}
    </div>
  )
}

/* ─── Page ──────────────────────────────────────────────────────────── */

export function AnalyzePage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState<AnalysisProgress | null>(null)
  const [draftRestored, setDraftRestored] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const maxTokens = watch('max_tokens')
  const model = watch('model')

  // Models the server can actually serve (only providers with keys configured)
  const { data: modelsData } = useSWR<ModelsResponse>('/models', fetcher)

  // Restore draft on mount
  useEffect(() => {
    const draft = loadDraft()
    if (draft && (draft.reference || draft.prd || draft.jira || draft.openapi)) {
      reset(draft)
      setDraftRestored(true)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-save draft as user types (debounced 600ms)
  const watchedFields = watch(['reference', 'prd', 'jira', 'openapi'])
  useEffect(() => {
    const [reference, prd, jira, openapi] = watchedFields
    const t = setTimeout(() => saveDraft({ reference, prd, jira, openapi }), 600)
    return () => clearTimeout(t)
  }, [watchedFields])

  // Poll progress while in-flight
  useEffect(() => {
    if (!isSubmitting || !jobId) return
    let cancelled = false
    const poll = async () => {
      try {
        const p = await fetcher<AnalysisProgress>(`/requirements/progress/${jobId}`)
        if (!cancelled) setProgress(p)
      } catch { /* 404 until first event — ignore */ }
    }
    poll()
    const interval = setInterval(poll, 1500)
    return () => { cancelled = true; clearInterval(interval) }
  }, [isSubmitting, jobId])

  const handleCancel = async () => {
    setCancelling(true)
    if (jobId) { try { await api.cancelJob(jobId) } catch { /* ignore */ } }
    abortRef.current?.abort()
  }

  const onSubmit = async (values: FormValues) => {
    setError(null)
    setProgress(null)
    setCancelling(false)
    const id = crypto.randomUUID()
    setJobId(id)
    const controller = new AbortController()
    abortRef.current = controller

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
        ...(values.model ? { model: values.model } : {}),
      }, controller.signal)
      clearDraft()
      navigate(`/requirements/${result.requirement_id}`)
    } catch (err) {
      // Aborted locally, or the server returned 499 — both mean "cancelled by user"
      const aborted = err instanceof DOMException && err.name === 'AbortError'
      const cancelled499 = err instanceof Error && err.message.toLowerCase().includes('cancelled')
      if (aborted || cancelled499) {
        setError('Analysis cancelled.')
      } else {
        setError(err instanceof Error ? err.message : 'Analysis failed')
      }
    } finally {
      setCancelling(false)
      abortRef.current = null
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Page header */}
      <div className="mb-7">
        <div className="flex items-center gap-2 mb-1.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">New Analysis</h1>
        </div>
        <p className="text-sm text-muted-foreground ml-9">
          Paste your requirement artifacts — PRD, Jira stories, or OpenAPI spec. Mix and match.
        </p>
      </div>

      {/* Draft restored banner */}
      {draftRestored && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm">
          <div className="flex items-center gap-2 text-amber-800">
            <RotateCcw className="h-3.5 w-3.5 shrink-0" />
            <span>Draft restored from your last session.</span>
          </div>
          <button
            type="button"
            onClick={() => { clearDraft(); reset({}); setDraftRestored(false) }}
            className="ml-4 text-xs text-amber-600 underline-offset-2 hover:underline"
          >
            Clear
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        {/* Project reference */}
        <div className="rounded-xl border bg-card px-4 py-3.5 space-y-1.5">
          <Label htmlFor="reference" className="text-sm font-medium">Project name / reference</Label>
          <Input
            id="reference"
            placeholder="e.g. checkout-v2-redesign"
            className="bg-background"
            {...register('reference')}
          />
          {errors.reference && (
            <p className="text-xs text-destructive">{errors.reference.message}</p>
          )}
        </div>

        {/* Artifact inputs */}
        <div className="space-y-2">
          <InputSection title="PRD / Design Doc" badge="text" defaultOpen>
            <Textarea
              rows={10}
              placeholder="Paste your PRD or design document here…"
              className="font-mono text-xs bg-background resize-none"
              {...register('prd')}
            />
          </InputSection>
          <InputSection title="Jira Stories" badge="JSON or text">
            <Textarea
              rows={8}
              placeholder="Paste exported Jira JSON or story descriptions…"
              className="font-mono text-xs bg-background resize-none"
              {...register('jira')}
            />
          </InputSection>
          <InputSection title="OpenAPI Spec" badge="YAML or JSON">
            <Textarea
              rows={8}
              placeholder="Paste your OpenAPI / Swagger spec here…"
              className="font-mono text-xs bg-background resize-none"
              {...register('openapi')}
            />
          </InputSection>
        </div>

        {errors.prd?.message && (
          <p className="text-sm text-destructive">{errors.prd.message}</p>
        )}

        {/* Advanced options */}
        <InputSection title="Advanced options">
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Max output tokens per LLM call — increase if analysis fails with a truncation error on large inputs.
            </p>
            <div className="flex flex-wrap gap-2">
              {TOKEN_PRESETS.map(({ label, value }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setValue('max_tokens', maxTokens === value ? undefined : value)}
                  className={[
                    'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
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
              <p className="text-xs text-amber-600">High token limits increase cost and latency significantly.</p>
            )}

            {modelsData && modelsData.options.length > 0 && (
              <div className="space-y-2 pt-3 border-t">
                <p className="text-xs text-muted-foreground">
                  Model — defaults to per-step routing (fast models for parsing, powerful for extraction).
                  Pick one to force the entire analysis onto a specific model.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setValue('model', undefined)}
                    className={[
                      'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                      !model
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-input bg-background hover:bg-muted',
                    ].join(' ')}
                  >
                    Default
                  </button>
                  {modelsData.options.map((opt) => (
                    <button
                      key={opt.spec}
                      type="button"
                      onClick={() => setValue('model', model === opt.spec ? undefined : opt.spec)}
                      className={[
                        'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                        model === opt.spec
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-input bg-background hover:bg-muted',
                      ].join(' ')}
                      title={opt.spec}
                    >
                      {opt.model_id}
                      <span className={[
                        'ml-1.5 text-[10px]',
                        model === opt.spec ? 'text-primary-foreground/70' : 'text-muted-foreground',
                      ].join(' ')}>
                        {opt.provider}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </InputSection>

        {/* Error / cancellation notice */}
        {error && (
          error === 'Analysis cancelled.' ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-sm text-amber-800">Analysis cancelled. Your inputs are saved — adjust and run again.</p>
            </div>
          ) : (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3.5">
              <p className="text-sm font-medium text-destructive mb-0.5">Analysis failed</p>
              <p className="text-xs text-destructive/80 break-words">{error}</p>
            </div>
          )
        )}

        {/* Submit / Cancel */}
        <div className="flex justify-end gap-2 pt-1">
          {isSubmitting && (
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={handleCancel}
              disabled={cancelling}
              className="border-destructive/30 text-destructive hover:bg-destructive/5"
            >
              {cancelling
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Cancelling…</>
                : <><XCircle className="h-4 w-4" /> Cancel</>
              }
            </Button>
          )}
          <Button type="submit" disabled={isSubmitting} size="lg" className="min-w-36">
            {isSubmitting
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing…</>
              : <><Sparkles className="h-4 w-4" /> Run Analysis</>
            }
          </Button>
        </div>

        {/* Progress stepper */}
        {isSubmitting && <PipelineProgress progress={progress} />}
      </form>
    </div>
  )
}

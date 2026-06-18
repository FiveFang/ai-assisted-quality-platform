import { useState, useRef, useMemo, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import useSWR from 'swr'
import {
  Loader2, AlertTriangle, CheckCircle2, XCircle, ChevronLeft,
  History, FlaskConical, Shield, Layers, GitBranch, Database, Ban,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { SkillPanel } from '@/components/SkillPanel'
import { ConfidenceBadge } from '@/components/ConfidenceBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { fetcher, api } from '@/api/client'
import type { NormalizedRequirement, Ambiguity, Requirement, Workflow, Entity, BusinessRule, ReviewEvent } from '@/types/api'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function ReviewHistory({ requirementId }: { requirementId: string }) {
  const { data } = useSWR<ReviewEvent[]>(`/requirements/${requirementId}/review-history`, fetcher)
  if (!data || data.length === 0) return null
  return (
    <div className="rounded-2xl border bg-card p-5 space-y-3">
      <h3 className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
        <History className="h-4 w-4" /> Review history
      </h3>
      <ol className="space-y-2">
        {data.map((ev) => (
          <li key={ev.id} className="flex items-start gap-3 text-sm">
            {ev.approved
              ? <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
              : <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />}
            <div className="flex-1 min-w-0">
              <span className="font-medium">{ev.approved ? 'Approved' : 'Rejected'}</span>
              {ev.reason && <span className="text-muted-foreground"> — {ev.reason}</span>}
            </div>
            <span className="text-xs text-muted-foreground shrink-0">{timeAgo(ev.created_at)}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

const PRIORITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'secondary'> = {
  P0: 'danger', P1: 'warning', P2: 'info', P3: 'secondary',
}

const TYPE_VARIANT: Record<string, 'default' | 'purple' | 'warning' | 'info' | 'secondary'> = {
  FUNCTIONAL: 'default', SECURITY: 'purple', PERFORMANCE: 'warning',
  NON_FUNCTIONAL: 'secondary', ACCESSIBILITY: 'info',
}

const SEVERITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'secondary'> = {
  BLOCKING: 'danger', HIGH: 'warning', MEDIUM: 'info', LOW: 'secondary',
}

function RequirementItem({ req, isRejected, rejectionReason, onReject, onUnreject }: {
  req: Requirement
  isRejected: boolean
  rejectionReason: string | null
  onReject: (reason?: string) => Promise<void>
  onUnreject: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const confirmReject = async () => {
    setBusy(true)
    try { await onReject(reason.trim() || undefined) }
    finally { setBusy(false); setRejecting(false); setReason('') }
  }

  const confirmUnreject = async () => {
    setBusy(true)
    try { await onUnreject() }
    finally { setBusy(false) }
  }

  return (
    <div className={[
      'rounded-xl border bg-background p-3.5 space-y-2 transition-all',
      isRejected ? 'border-red-200 bg-red-50/30 opacity-60' : 'hover:shadow-sm',
    ].join(' ')}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={['font-mono text-[11px] text-muted-foreground', isRejected ? 'line-through' : ''].join(' ')}>
            {req.requirement_id}
          </span>
          <Badge variant={PRIORITY_VARIANT[req.priority] ?? 'secondary'}>{req.priority}</Badge>
          <Badge variant={TYPE_VARIANT[req.type] ?? 'secondary'}>{req.type}</Badge>
          {isRejected && <Badge variant="danger">Rejected</Badge>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isRejected ? (
            <button
              onClick={confirmUnreject}
              disabled={busy}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-3 w-3 animate-spin inline" /> : 'Undo'}
            </button>
          ) : (
            <button
              onClick={() => setRejecting((v) => !v)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive transition-colors"
            >
              <Ban className="h-3 w-3" /> Reject
            </button>
          )}
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground shrink-0"
          >
            {open ? 'less' : 'more'}
          </button>
        </div>
      </div>

      <p className={['text-sm font-medium leading-snug', isRejected ? 'line-through text-muted-foreground' : ''].join(' ')}>
        {req.title}
      </p>

      {isRejected && rejectionReason && (
        <p className="text-xs text-destructive/70 italic">Reason: {rejectionReason}</p>
      )}

      {rejecting && !isRejected && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 space-y-2">
          <Textarea
            placeholder="Rejection reason (optional)…"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="resize-none text-xs"
          />
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => { setRejecting(false); setReason('') }}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <Button
              size="sm"
              variant="destructive"
              onClick={confirmReject}
              disabled={busy}
              className="h-7 px-3 text-xs"
            >
              {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Confirm reject'}
            </Button>
          </div>
        </div>
      )}

      {open && (
        <div className="space-y-2.5 pt-1">
          <p className="text-xs text-muted-foreground leading-relaxed">{req.description}</p>
          {req.acceptance_criteria.length > 0 && (
            <ul className="space-y-1">
              {req.acceptance_criteria.map((c, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 mt-0.5 shrink-0" />
                  {c}
                </li>
              ))}
            </ul>
          )}
          {req.tags.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {req.tags.map((t) => <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AmbiguityItem({ amb, onDismiss }: { amb: Ambiguity; onDismiss?: () => void }) {
  const [dismissing, setDismissing] = useState(false)

  const handleDismiss = async () => {
    if (!onDismiss) return
    setDismissing(true)
    try { await onDismiss() } finally { setDismissing(false) }
  }

  return (
    <div className={[
      'rounded-xl border p-3.5 space-y-1.5',
      amb.blocking ? 'border-red-200 bg-red-50/60' : 'bg-background',
    ].join(' ')}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <AlertTriangle className={`h-3.5 w-3.5 ${amb.blocking ? 'text-red-500' : 'text-amber-500'}`} />
          <span className="font-mono text-[11px] text-muted-foreground">{amb.ambiguity_id}</span>
          <Badge variant={SEVERITY_VARIANT[amb.severity] ?? 'secondary'}>{amb.severity}</Badge>
          {amb.blocking && <Badge variant="danger">Blocking</Badge>}
        </div>
        {amb.blocking && onDismiss && (
          <button
            onClick={handleDismiss}
            disabled={dismissing}
            className="shrink-0 text-xs text-muted-foreground hover:text-foreground border rounded px-2 py-0.5 hover:bg-background transition-colors disabled:opacity-50"
          >
            {dismissing ? <Loader2 className="h-3 w-3 animate-spin inline" /> : 'Dismiss'}
          </button>
        )}
      </div>
      <p className="text-sm">{amb.description}</p>
      <p className="text-xs text-muted-foreground">
        <span className="font-medium">Suggestion:</span> {amb.suggested_clarification}
      </p>
      <p className="text-xs text-muted-foreground">
        Affects: <span className="font-mono">{amb.affected_requirement}</span>
      </p>
    </div>
  )
}

function WorkflowItem({ wf }: { wf: Workflow }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-xl border bg-background p-3.5 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-muted-foreground">{wf.workflow_id}</span>
          <span className="text-sm font-medium">{wf.name}</span>
        </div>
        <button onClick={() => setOpen((v) => !v)} className="text-xs text-muted-foreground hover:text-foreground">
          {open ? 'less' : 'steps'}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">{wf.description}</p>
      {open && wf.steps.length > 0 && (
        <ol className="text-xs space-y-1.5 border-t pt-2.5">
          {wf.steps.map((s, i) => (
            <li key={s.step_id} className="flex gap-2.5">
              <span className="text-muted-foreground w-4 shrink-0 tabular-nums">{i + 1}.</span>
              <span><span className="font-medium">{s.actor}:</span> {s.action}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function EntityItem({ entity }: { entity: Entity }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border bg-background px-3.5 py-2.5">
      <Badge variant="secondary" className="mt-0.5 shrink-0 text-[10px]">{entity.type}</Badge>
      <div className="min-w-0">
        <p className="text-sm font-medium truncate">{entity.name}</p>
        {entity.description && <p className="text-xs text-muted-foreground">{entity.description}</p>}
        {entity.attributes.length > 0 && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{entity.attributes.join(', ')}</p>
        )}
      </div>
    </div>
  )
}

function RuleItem({ rule }: { rule: BusinessRule }) {
  return (
    <div className="rounded-xl border bg-background px-3.5 py-2.5 space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-[11px] text-muted-foreground">{rule.rule_id}</span>
        <Badge variant="secondary" className="text-[10px]">{rule.rule_type}</Badge>
        {!rule.is_explicit && <Badge variant="warning" className="text-[10px]">inferred</Badge>}
      </div>
      <p className="text-sm">{rule.description}</p>
    </div>
  )
}

export function RAAReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [rejectReason, setRejectReason] = useState('')
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | 'generate' | null>(null)
  const [retrying, setRetrying] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const ALL_SKILLS = ['functional', 'negative', 'edge_case', 'api', 'security', 'ui'] as const
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set(ALL_SKILLS))
  const [selectedReqIds, setSelectedReqIds] = useState<Set<string>>(new Set())

  const toggleSkill = (key: string) =>
    setSelectedSkills((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })

  const toggleReq = (id: string) =>
    setSelectedReqIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  const genAbortRef = useRef<AbortController | null>(null)
  const genJobRef = useRef<string | null>(null)

  const { data, error, isLoading, mutate } = useSWR<NormalizedRequirement>(
    id ? `/requirements/${id}` : null, fetcher,
  )
  const { data: testSuiteRef } = useSWR<{ test_suite_id: string }>(
    data?.status === 'APPROVED' || data?.status === 'AWAITING_REVIEW'
      ? `/requirements/${id}/test-suite`
      : null,
    fetcher,
    { shouldRetryOnError: false, onErrorRetry: () => {} },
  )

  // Recompute the same 4-factor breakdown used by ConfidenceScorerSkill on the backend.
  const confidenceBreakdown = useMemo(() => {
    if (!data) return null
    const reqs = data.requirements

    // Factor 1 — source completeness (weight 0.25)
    // What: fraction of expected fields present across all requirements.
    const requiredFields = ['requirement_id', 'type', 'title', 'description', 'acceptance_criteria']
    const sourceCompleteness = reqs.length === 0 ? 0 :
      reqs.reduce((sum, r) => {
        const has = requiredFields.filter((f) => {
          const v = (r as unknown as Record<string, unknown>)[f]
          return v !== undefined && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)
        }).length
        return sum + has / requiredFields.length
      }, 0) / reqs.length

    // Factor 2 — entity coverage (weight 0.25)
    // What: how many requirements reference at least one extracted entity by name.
    const entityNames = new Set(data.entities.map((e) => e.name.toLowerCase()))
    let entityCoverage = 0.5 // neutral — no entities expected for simple requirements
    if (entityNames.size > 0) {
      let refs = 0, covered = 0
      for (const req of reqs) {
        const hay = (req.description + ' ' + req.tags.join(' ')).toLowerCase()
        for (const name of entityNames) {
          if (hay.includes(name)) { refs++; covered++; break }
        }
      }
      entityCoverage = covered / Math.max(refs, 1)
    }

    // Factor 3 — rule coverage (weight 0.30)
    // What: business rules found relative to acceptance criteria count (expect ~1 rule per 2 criteria).
    const totalCriteria = reqs.reduce((s, r) => s + r.acceptance_criteria.length, 0)
    const ruleCoverage = totalCriteria === 0 ? 0.5 :
      Math.min(data.business_rules.length / Math.max(totalCriteria / 2, 1), 1.0)

    // Factor 4 — ambiguity health (weight 0.20)
    // What: 1.0 minus cumulative penalty from MEDIUM/HIGH/BLOCKING ambiguities.
    let penalty = 0
    for (const a of data.ambiguities) {
      if (a.severity === 'BLOCKING') penalty += 0.3
      else if (a.severity === 'HIGH') penalty += 0.1
      else if (a.severity === 'MEDIUM') penalty += 0.05
    }
    const ambiguityHealth = Math.max(1.0 - penalty, 0)

    return { sourceCompleteness, entityCoverage, ruleCoverage, ambiguityHealth }
  }, [data])

  const nonRejectedReqs = useMemo(() => {
    if (!data) return []
    const rejected = new Set(Object.keys(data.rejected_requirements ?? {}))
    return data.requirements.filter((r) => !rejected.has(r.requirement_id))
  }, [data])

  // Initialise requirement selection to all non-rejected whenever the NR loads/changes.
  useEffect(() => {
    setSelectedReqIds(new Set(nonRejectedReqs.map((r) => r.requirement_id)))
  }, [data?.requirement_id])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="text-center py-24">
        <p className="text-destructive text-sm">{error?.message ?? 'Requirement not found'}</p>
      </div>
    )
  }

  const blockingAmbiguities = data.ambiguities.filter((a) => a.blocking)
  const canApprove = blockingAmbiguities.length === 0

  const isCancellation = (err: unknown) =>
    (err instanceof DOMException && err.name === 'AbortError') ||
    (err instanceof Error && err.message.toLowerCase().includes('cancelled'))

  const startGenJob = () => {
    const controller = new AbortController()
    const jobId = crypto.randomUUID()
    genAbortRef.current = controller
    genJobRef.current = jobId
    return { signal: controller.signal, job_id: jobId }
  }

  const handleCancelGenerate = async () => {
    setCancelling(true)
    if (genJobRef.current) { try { await api.cancelJob(genJobRef.current) } catch { /* ignore */ } }
    genAbortRef.current?.abort()
  }

  const handleApprove = async () => {
    setSubmitting('approve'); setActionError(null); setCancelling(false)
    try {
      await api.reviewRequirement(data.requirement_id, true)
      await mutate()
      const job = startGenJob()
      const suite = await api.generateTests(data.requirement_id, {
        ...job,
        selected_skills: selectedSkills.size < ALL_SKILLS.length ? [...selectedSkills] : undefined,
        selected_requirement_ids: selectedReqIds.size < nonRejectedReqs.length ? [...selectedReqIds] : undefined,
      })
      navigate(`/tests/${suite.test_suite_id}`)
    } catch (err) {
      setActionError(isCancellation(err) ? 'Test generation cancelled.' : (err instanceof Error ? err.message : 'Failed'))
      setSubmitting(null); setCancelling(false)
    }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) return
    setSubmitting('reject'); setActionError(null)
    try {
      await api.reviewRequirement(data.requirement_id, false, rejectReason)
      navigate('/')
    } catch (err) { setActionError(err instanceof Error ? err.message : 'Failed'); setSubmitting(null) }
  }

  const handleGenerateTests = async () => {
    setSubmitting('generate'); setActionError(null); setCancelling(false)
    try {
      const job = startGenJob()
      const suite = await api.generateTests(data.requirement_id, {
        ...job,
        selected_skills: selectedSkills.size < ALL_SKILLS.length ? [...selectedSkills] : undefined,
        selected_requirement_ids: selectedReqIds.size < nonRejectedReqs.length ? [...selectedReqIds] : undefined,
      })
      navigate(`/tests/${suite.test_suite_id}`)
    } catch (err) {
      setActionError(isCancellation(err) ? 'Test generation cancelled.' : (err instanceof Error ? err.message : 'Failed'))
      setSubmitting(null); setCancelling(false)
    }
  }

  // Parse which skills failed from review_reasons (e.g. "AmbiguityDetectorSkill failed: ...")
  const failedSkillClasses = new Set(
    (data?.review_reasons ?? [])
      .map((r) => { const m = r.match(/^(\w+Skill) failed:/); return m ? m[1] : null })
      .filter(Boolean) as string[]
  )

  const SKILL_CLASS_TO_KEY: Record<string, string> = {
    AmbiguityDetectorSkill: 'ambiguity_detector',
    RuleExtractorSkill: 'rule_extractor',
    WorkflowExtractorSkill: 'workflow_extractor',
  }

  const handleRejectRequirement = async (reqId: string, reason?: string) => {
    await api.rejectRequirement(data.requirement_id, reqId, reason)
    await mutate()
  }

  const handleUnrejectRequirement = async (reqId: string) => {
    await api.unrejectRequirement(data.requirement_id, reqId)
    await mutate()
  }

  const rejectedIds = data.rejected_requirements ?? {}
  const rejectedCount = Object.keys(rejectedIds).length

  const handleDismissAmbiguity = async (ambiguityId: string) => {
    try {
      await api.dismissAmbiguity(data.requirement_id, ambiguityId)
      await mutate()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Dismiss failed')
    }
  }

  const handleRerunSkill = async (skillKey: string) => {
    if (!data) return
    setRetrying(skillKey); setActionError(null)
    try {
      await api.rerunSkill(data.requirement_id, skillKey)
      await mutate()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Retry failed')
    } finally {
      setRetrying(null)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">

      {/* Header */}
      <div>
        <Link to="/" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-3 transition-colors">
          <ChevronLeft className="h-3.5 w-3.5" /> All Requirements
        </Link>

        <div className="rounded-2xl border bg-card px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-xl font-semibold tracking-tight truncate">{data.source.reference}</h1>
              <p className="text-xs text-muted-foreground font-mono mt-0.5">{data.requirement_id}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
              <StatusBadge status={data.status} />
              <ConfidenceBadge score={data.metadata.confidence_score} showBar />
            </div>
          </div>

          {/* Stat row */}
          <div className="mt-4 pt-4 border-t grid grid-cols-4 gap-4">
            {[
              { icon: Layers, label: 'Requirements', value: data.requirements.length },
              { icon: GitBranch, label: 'Workflows', value: data.workflows.length },
              { icon: Shield, label: 'Rules', value: data.business_rules.length },
              { icon: Database, label: 'Entities', value: data.entities.length },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="text-center">
                <div className="flex items-center justify-center gap-1.5 text-muted-foreground mb-0.5">
                  <Icon className="h-3.5 w-3.5" />
                  <span className="text-xs">{label}</span>
                </div>
                <p className="text-lg font-semibold tabular-nums">{value}</p>
              </div>
            ))}
          </div>

          {/* Meta */}
          <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
            <span>Model: {data.metadata.processing_model}</span>
            {data.metadata.processing_duration_ms && (
              <span>·</span>
            )}
            {data.metadata.processing_duration_ms && (
              <span>{(data.metadata.processing_duration_ms / 1000).toFixed(1)}s</span>
            )}
          </div>
        </div>
      </div>

      {/* Human review notice */}
      {data.human_review_required && data.review_reasons.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4">
          <p className="text-sm font-medium text-amber-800 mb-1.5 flex items-center gap-1.5">
            <AlertTriangle className="h-4 w-4" /> Human review required
          </p>
          <ul className="space-y-0.5">
            {data.review_reasons.map((r, i) => (
              <li key={i} className="text-xs text-amber-700 flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0">·</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Skill panels */}
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground px-1">Agent output</p>

        <SkillPanel skillName="RequirementExtractorSkill" label="Extracted Requirements" description="Parses raw input into structured functional, performance, and non-functional requirements" count={data.requirements.length} defaultOpen>
          {rejectedCount > 0 && (
            <p className="text-xs text-muted-foreground flex items-center gap-1.5 pb-1">
              <Ban className="h-3 w-3 text-destructive/60 shrink-0" />
              {rejectedCount} of {data.requirements.length} rejected — won't generate test cases
            </p>
          )}
          {data.requirements.length === 0
            ? <p className="text-sm text-muted-foreground">No requirements extracted.</p>
            : data.requirements.map((req) => (
                <RequirementItem
                  key={req.requirement_id}
                  req={req}
                  isRejected={req.requirement_id in rejectedIds}
                  rejectionReason={rejectedIds[req.requirement_id] ?? null}
                  onReject={(reason) => handleRejectRequirement(req.requirement_id, reason)}
                  onUnreject={() => handleUnrejectRequirement(req.requirement_id)}
                />
              ))
          }
        </SkillPanel>

        <SkillPanel
          skillName="AmbiguityDetectorSkill"
          label="Ambiguities"
          description="Flags unclear, conflicting, or underspecified language that needs human resolution before testing"
          count={data.ambiguities.length}
          defaultOpen={data.ambiguities.length > 0 || failedSkillClasses.has('AmbiguityDetectorSkill')}
          onRetry={failedSkillClasses.has('AmbiguityDetectorSkill') ? () => handleRerunSkill(SKILL_CLASS_TO_KEY['AmbiguityDetectorSkill']) : undefined}
          retrying={retrying === SKILL_CLASS_TO_KEY['AmbiguityDetectorSkill']}
        >
          {failedSkillClasses.has('AmbiguityDetectorSkill') && data.ambiguities.length === 0
            ? <p className="text-sm text-destructive/80 flex items-center gap-1.5">
                <XCircle className="h-4 w-4 text-destructive shrink-0" /> Detection failed — use Retry to re-run without re-analyzing everything.
              </p>
            : data.ambiguities.length === 0
              ? <p className="text-sm text-muted-foreground flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" /> No ambiguities detected.
                </p>
              : data.ambiguities.map((a) => (
                  <AmbiguityItem
                    key={a.ambiguity_id}
                    amb={a}
                    onDismiss={a.blocking ? () => handleDismissAmbiguity(a.ambiguity_id) : undefined}
                  />
                ))
          }
        </SkillPanel>

        <SkillPanel
          skillName="WorkflowExtractorSkill"
          label="Workflows"
          description="Maps multi-step user journeys and process flows described across the requirements"
          count={data.workflows.length}
          defaultOpen={failedSkillClasses.has('WorkflowExtractorSkill')}
          onRetry={failedSkillClasses.has('WorkflowExtractorSkill') ? () => handleRerunSkill(SKILL_CLASS_TO_KEY['WorkflowExtractorSkill']) : undefined}
          retrying={retrying === SKILL_CLASS_TO_KEY['WorkflowExtractorSkill']}
        >
          {failedSkillClasses.has('WorkflowExtractorSkill') && data.workflows.length === 0
            ? <p className="text-sm text-destructive/80 flex items-center gap-1.5">
                <XCircle className="h-4 w-4 text-destructive shrink-0" /> Extraction failed — use Retry to re-run without re-analyzing everything.
              </p>
            : data.workflows.length === 0
              ? <p className="text-sm text-muted-foreground">No workflows extracted.</p>
              : data.workflows.map((wf) => <WorkflowItem key={wf.workflow_id} wf={wf} />)
          }
        </SkillPanel>

        <SkillPanel skillName="EntityExtractorSkill" label="Entities" description="Identifies key domain objects — users, data models, services — referenced in the requirement text" count={data.entities.length}>
          {data.entities.length === 0
            ? <p className="text-sm text-muted-foreground">No entities extracted.</p>
            : <div className="grid grid-cols-2 gap-2">
                {data.entities.map((e, i) => <EntityItem key={i} entity={e} />)}
              </div>
          }
        </SkillPanel>

        <SkillPanel
          skillName="RuleExtractorSkill"
          label="Business Rules"
          description="Extracts validation constraints and business logic implicit in the requirement text"
          count={data.business_rules.length}
          defaultOpen={failedSkillClasses.has('RuleExtractorSkill')}
          onRetry={failedSkillClasses.has('RuleExtractorSkill') ? () => handleRerunSkill(SKILL_CLASS_TO_KEY['RuleExtractorSkill']) : undefined}
          retrying={retrying === SKILL_CLASS_TO_KEY['RuleExtractorSkill']}
        >
          {failedSkillClasses.has('RuleExtractorSkill') && data.business_rules.length === 0
            ? <p className="text-sm text-destructive/80 flex items-center gap-1.5">
                <XCircle className="h-4 w-4 text-destructive shrink-0" /> Extraction failed — use Retry to re-run without re-analyzing everything.
              </p>
            : data.business_rules.length === 0
              ? <p className="text-sm text-muted-foreground">No business rules extracted.</p>
              : data.business_rules.map((r) => <RuleItem key={r.rule_id} rule={r} />)
          }
        </SkillPanel>

        <SkillPanel skillName="ConfidenceScorerSkill" label="Confidence Score" description="Scores extraction quality across 4 weighted factors to indicate how reliably the output can be trusted">
          <div className="space-y-4">
            {/* Overall */}
            <div className="flex items-center gap-3">
              <ConfidenceBadge score={data.metadata.confidence_score} showBar />
              <span className="text-sm text-muted-foreground">
                {data.metadata.confidence_score >= 0.8
                  ? 'High — extraction is reliable.'
                  : data.metadata.confidence_score >= 0.65
                    ? 'Moderate — review ambiguities carefully.'
                    : 'Low — manual review strongly recommended.'}
              </span>
            </div>

            {/* Factor breakdown */}
            {confidenceBreakdown && (() => {
              const factors = [
                {
                  label: 'Source completeness',
                  score: confidenceBreakdown.sourceCompleteness,
                  weight: 0.25,
                  description: 'Fraction of expected fields (id, type, title, description, acceptance criteria) present across all extracted requirements.',
                },
                {
                  label: 'Entity coverage',
                  score: confidenceBreakdown.entityCoverage,
                  weight: 0.25,
                  description: 'How many requirements reference at least one extracted entity by name. Neutral (50%) when no entities were found.',
                },
                {
                  label: 'Rule coverage',
                  score: confidenceBreakdown.ruleCoverage,
                  weight: 0.30,
                  description: `Business rules extracted vs expected (≈1 rule per 2 acceptance criteria). ${data.business_rules.length} rules found across ${data.requirements.reduce((s, r) => s + r.acceptance_criteria.length, 0)} criteria.`,
                },
                {
                  label: 'Ambiguity health',
                  score: confidenceBreakdown.ambiguityHealth,
                  weight: 0.20,
                  description: `Starts at 100% and loses points per ambiguity: −30% BLOCKING, −10% HIGH, −5% MEDIUM. ${data.ambiguities.length} ambiguit${data.ambiguities.length === 1 ? 'y' : 'ies'} detected.`,
                },
              ]
              return (
                <div className="rounded-xl border bg-background divide-y">
                  {factors.map((f) => {
                    const contribution = f.score * f.weight
                    const pct = Math.round(f.score * 100)
                    const barColor = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400'
                    return (
                      <div key={f.label} className="px-4 py-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-4">
                          <span className="text-xs font-medium">{f.label}</span>
                          <div className="flex items-center gap-2 shrink-0">
                            <div className="h-1.5 w-20 rounded-full bg-muted overflow-hidden">
                              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-xs tabular-nums w-7 text-right">{pct}%</span>
                            <span className="text-[10px] text-muted-foreground w-8">×{f.weight}</span>
                            <span className="text-xs font-medium tabular-nums w-10 text-right">
                              +{Math.round(contribution * 100)}pt
                            </span>
                          </div>
                        </div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">{f.description}</p>
                      </div>
                    )
                  })}
                  <div className="px-4 py-2.5 flex items-center justify-between bg-muted/30">
                    <span className="text-[11px] text-muted-foreground">Weighted total</span>
                    <span className="text-xs font-semibold tabular-nums">
                      {Math.round(data.metadata.confidence_score * 100)}%
                    </span>
                  </div>
                </div>
              )
            })()}
          </div>
        </SkillPanel>

        <SkillPanel
          skillName="RAGEnricherSkill"
          label="RAG Context"
          description="Retrieves similar past requirements from the vector store to provide historical grounding during extraction"
          count={data.enriched_context.is_available ? data.enriched_context.similar_requirements.length : undefined}
        >
          {!data.enriched_context.is_available ? (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm text-amber-800">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">Not enriched — vector store unavailable</p>
                <p className="text-xs mt-0.5 text-amber-700">Start Postgres with pgvector to enable RAG enrichment.</p>
              </div>
            </div>
          ) : data.enriched_context.similar_requirements.length === 0 && data.enriched_context.relevant_domain_knowledge.length === 0 ? (
            <p className="text-sm text-muted-foreground">No historical context found — vector store is empty.</p>
          ) : (
            <div className="space-y-3">
              {data.enriched_context.similar_requirements.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1">Similar requirements</p>
                  {data.enriched_context.similar_requirements.map((s, i) => (
                    <div key={i} className="text-xs text-muted-foreground flex gap-2">
                      <span className="font-mono">{s.requirement_id}</span>
                      <span>similarity {((s.similarity ?? 0) * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              )}
              {data.enriched_context.relevant_domain_knowledge.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1">Domain knowledge</p>
                  <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
                    {data.enriched_context.relevant_domain_knowledge.map((k, i) => <li key={i}>{k}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </SkillPanel>
      </div>

      <ReviewHistory requirementId={data.requirement_id} />

      {/* Action panel */}
      <div className="rounded-2xl border bg-card p-5 space-y-4">

        {/* Skill selector */}
        {(data.status === 'AWAITING_REVIEW' || data.status === 'APPROVED') && submitting === null && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Test types to generate</p>
            <div className="grid grid-cols-3 gap-2">
              {([
                { key: 'functional', label: 'Functional', sub: 'Happy-path' },
                { key: 'negative',   label: 'Negative',   sub: 'Error paths' },
                { key: 'edge_case',  label: 'Edge Cases', sub: 'Boundaries' },
                { key: 'api',        label: 'API Tests',  sub: 'HTTP contracts' },
                { key: 'security',   label: 'Security',   sub: 'OWASP checks' },
                { key: 'ui',         label: 'UI / Mobile', sub: 'Playwright/Appium' },
              ] as const).map(({ key, label, sub }) => {
                const checked = selectedSkills.has(key)
                return (
                  <label
                    key={key}
                    className={[
                      'flex items-start gap-2.5 rounded-xl border p-3 cursor-pointer transition-colors select-none',
                      checked ? 'border-primary/40 bg-primary/5' : 'border-border bg-background hover:bg-muted/40',
                    ].join(' ')}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleSkill(key)}
                      className="mt-0.5 h-3.5 w-3.5 accent-primary shrink-0"
                    />
                    <div className="min-w-0">
                      <p className="text-xs font-medium leading-none">{label}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
                    </div>
                  </label>
                )
              })}
            </div>
            {selectedSkills.size === 0 && (
              <p className="text-xs text-destructive">Select at least one test type.</p>
            )}
          </div>
        )}

        {/* Requirement selector */}
        {(data.status === 'AWAITING_REVIEW' || data.status === 'APPROVED') && submitting === null && nonRejectedReqs.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Requirements ({selectedReqIds.size} / {nonRejectedReqs.length} selected)
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSelectedReqIds(new Set(nonRejectedReqs.map((r) => r.requirement_id)))}
                  className="text-xs text-primary hover:underline"
                >
                  All
                </button>
                <button
                  onClick={() => setSelectedReqIds(new Set())}
                  className="text-xs text-muted-foreground hover:underline"
                >
                  None
                </button>
              </div>
            </div>
            <div className="space-y-0.5 max-h-44 overflow-y-auto rounded-xl border bg-background p-2">
              {nonRejectedReqs.map((req) => {
                const checked = selectedReqIds.has(req.requirement_id)
                return (
                  <label
                    key={req.requirement_id}
                    className={[
                      'flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 cursor-pointer transition-colors',
                      checked ? 'bg-primary/5' : 'hover:bg-muted/40',
                    ].join(' ')}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleReq(req.requirement_id)}
                      className="h-3.5 w-3.5 accent-primary shrink-0"
                    />
                    <span className="font-mono text-[10px] text-muted-foreground shrink-0 w-24 truncate">
                      {req.requirement_id}
                    </span>
                    <span className="text-xs truncate">{req.title}</span>
                  </label>
                )
              })}
            </div>
            {selectedReqIds.size === 0 && (
              <p className="text-xs text-destructive">Select at least one requirement.</p>
            )}
          </div>
        )}

        {(submitting === 'approve' || submitting === 'generate') && (
          <div className="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-primary">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              <span>Generating tests — this can take a minute…</span>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCancelGenerate}
              disabled={cancelling}
              className="border-destructive/30 text-destructive hover:bg-destructive/5 shrink-0"
            >
              {cancelling
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Cancelling…</>
                : <><XCircle className="h-3.5 w-3.5" /> Cancel</>
              }
            </Button>
          </div>
        )}

        {testSuiteRef && (
          <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-emerald-800">
              <FlaskConical className="h-4 w-4" />
              <span className="font-medium">Tests generated for this analysis.</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerateTests}
                disabled={submitting !== null || selectedSkills.size === 0 || selectedReqIds.size === 0}
                className="border-emerald-300 text-emerald-800 hover:bg-emerald-100"
              >
                {submitting === 'generate'
                  ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…</>
                  : <><FlaskConical className="h-3.5 w-3.5" /> Regenerate</>
                }
              </Button>
              <Button asChild size="sm">
                <Link to={`/tests/${testSuiteRef.test_suite_id}`}>View Test Suite →</Link>
              </Button>
            </div>
          </div>
        )}

        {data.status === 'AWAITING_REVIEW' && !testSuiteRef && (
          <>
            {!canApprove && (
              <p className="text-sm text-red-600 flex items-center gap-1.5">
                <XCircle className="h-4 w-4 shrink-0" />
                {blockingAmbiguities.length} blocking {blockingAmbiguities.length === 1 ? 'ambiguity' : 'ambiguities'} must be resolved before approval.
              </p>
            )}
            <div className="flex items-start gap-3">
              <Textarea
                placeholder="Rejection reason (required to reject)…"
                rows={2}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="flex-1 resize-none"
              />
              <div className="flex flex-col gap-2 shrink-0">
                <Button variant="outline" onClick={handleReject} disabled={!rejectReason.trim() || submitting !== null} className="border-destructive/30 text-destructive hover:bg-destructive/5">
                  {submitting === 'reject' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                  Reject
                </Button>
                <Button onClick={handleApprove} disabled={!canApprove || submitting !== null || selectedSkills.size === 0 || selectedReqIds.size === 0}>
                  {submitting === 'approve'
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                    : <><CheckCircle2 className="h-4 w-4" /> Approve & Generate Tests</>
                  }
                </Button>
              </div>
            </div>
          </>
        )}

        {data.status === 'APPROVED' && !testSuiteRef && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">Approved — no test suite generated yet.</p>
            <Button onClick={handleGenerateTests} disabled={submitting !== null || selectedSkills.size === 0 || selectedReqIds.size === 0} size="sm">
              {submitting === 'generate'
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                : <><FlaskConical className="h-4 w-4" /> Generate Tests</>
              }
            </Button>
          </div>
        )}

        {data.status === 'REJECTED' && (
          <p className="text-sm text-muted-foreground flex items-center gap-1.5">
            <XCircle className="h-4 w-4 text-destructive" />
            Rejected. Re-analyze with updated inputs to proceed.
          </p>
        )}

        {actionError && (
          <p className={`text-xs ${actionError.toLowerCase().includes('cancelled') ? 'text-amber-600' : 'text-destructive'}`}>
            {actionError}
          </p>
        )}
      </div>
    </div>
  )
}

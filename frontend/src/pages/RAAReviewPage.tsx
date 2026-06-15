import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import useSWR from 'swr'
import {
  Loader2, AlertTriangle, CheckCircle2, XCircle, ChevronLeft,
  History, FlaskConical, Shield, Layers, GitBranch, Database, BarChart2,
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

function RequirementItem({ req }: { req: Requirement }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-xl border bg-background p-3.5 space-y-2 transition-shadow hover:shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[11px] text-muted-foreground">{req.requirement_id}</span>
          <Badge variant={PRIORITY_VARIANT[req.priority] ?? 'secondary'}>{req.priority}</Badge>
          <Badge variant={TYPE_VARIANT[req.type] ?? 'secondary'}>{req.type}</Badge>
        </div>
        <button onClick={() => setOpen((v) => !v)} className="text-xs text-muted-foreground hover:text-foreground shrink-0">
          {open ? 'less' : 'more'}
        </button>
      </div>
      <p className="text-sm font-medium leading-snug">{req.title}</p>
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

function AmbiguityItem({ amb }: { amb: Ambiguity }) {
  return (
    <div className={[
      'rounded-xl border p-3.5 space-y-1.5',
      amb.blocking ? 'border-red-200 bg-red-50/60' : 'bg-background',
    ].join(' ')}>
      <div className="flex items-center gap-2 flex-wrap">
        <AlertTriangle className={`h-3.5 w-3.5 ${amb.blocking ? 'text-red-500' : 'text-amber-500'}`} />
        <span className="font-mono text-[11px] text-muted-foreground">{amb.ambiguity_id}</span>
        <Badge variant={SEVERITY_VARIANT[amb.severity] ?? 'secondary'}>{amb.severity}</Badge>
        {amb.blocking && <Badge variant="danger">Blocking</Badge>}
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
  const [actionError, setActionError] = useState<string | null>(null)

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

  const handleApprove = async () => {
    setSubmitting('approve'); setActionError(null)
    try {
      await api.reviewRequirement(data.requirement_id, true)
      await mutate()
      const suite = await api.generateTests(data.requirement_id)
      navigate(`/tests/${suite.test_suite_id}`)
    } catch (err) { setActionError(err instanceof Error ? err.message : 'Failed'); setSubmitting(null) }
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
    setSubmitting('generate'); setActionError(null)
    try {
      const suite = await api.generateTests(data.requirement_id)
      navigate(`/tests/${suite.test_suite_id}`)
    } catch (err) { setActionError(err instanceof Error ? err.message : 'Failed'); setSubmitting(null) }
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

        <SkillPanel skillName="RequirementExtractorSkill" label="Extracted Requirements" count={data.requirements.length} defaultOpen>
          {data.requirements.length === 0
            ? <p className="text-sm text-muted-foreground">No requirements extracted.</p>
            : data.requirements.map((req) => <RequirementItem key={req.requirement_id} req={req} />)
          }
        </SkillPanel>

        <SkillPanel skillName="AmbiguityDetectorSkill" label="Ambiguities" count={data.ambiguities.length} defaultOpen={data.ambiguities.length > 0}>
          {data.ambiguities.length === 0
            ? <p className="text-sm text-muted-foreground flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" /> No ambiguities detected.
              </p>
            : data.ambiguities.map((a) => <AmbiguityItem key={a.ambiguity_id} amb={a} />)
          }
        </SkillPanel>

        <SkillPanel skillName="WorkflowExtractorSkill" label="Workflows" count={data.workflows.length}>
          {data.workflows.length === 0
            ? <p className="text-sm text-muted-foreground">No workflows extracted.</p>
            : data.workflows.map((wf) => <WorkflowItem key={wf.workflow_id} wf={wf} />)
          }
        </SkillPanel>

        <SkillPanel skillName="EntityExtractorSkill" label="Entities" count={data.entities.length}>
          {data.entities.length === 0
            ? <p className="text-sm text-muted-foreground">No entities extracted.</p>
            : <div className="grid grid-cols-2 gap-2">
                {data.entities.map((e, i) => <EntityItem key={i} entity={e} />)}
              </div>
          }
        </SkillPanel>

        <SkillPanel skillName="RuleExtractorSkill" label="Business Rules" count={data.business_rules.length}>
          {data.business_rules.length === 0
            ? <p className="text-sm text-muted-foreground">No business rules extracted.</p>
            : data.business_rules.map((r) => <RuleItem key={r.rule_id} rule={r} />)
          }
        </SkillPanel>

        <SkillPanel skillName="ConfidenceScorerSkill" label="Confidence Score">
          <div className="flex items-center gap-4">
            <ConfidenceBadge score={data.metadata.confidence_score} showBar />
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <BarChart2 className="h-4 w-4" />
              {data.metadata.confidence_score >= 0.8
                ? 'High confidence — extraction is reliable.'
                : data.metadata.confidence_score >= 0.65
                  ? 'Moderate confidence — review ambiguities carefully.'
                  : 'Low confidence — manual review strongly recommended.'}
            </div>
          </div>
        </SkillPanel>

        <SkillPanel
          skillName="RAGEnricherSkill"
          label="RAG Context"
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
        {testSuiteRef && (
          <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-emerald-800">
              <FlaskConical className="h-4 w-4" />
              <span className="font-medium">Tests generated for this analysis.</span>
            </div>
            <Button asChild size="sm">
              <Link to={`/tests/${testSuiteRef.test_suite_id}`}>View Test Suite →</Link>
            </Button>
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
                <Button onClick={handleApprove} disabled={!canApprove || submitting !== null}>
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
            <Button onClick={handleGenerateTests} disabled={submitting !== null} size="sm">
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

        {actionError && <p className="text-xs text-destructive">{actionError}</p>}
      </div>
    </div>
  )
}

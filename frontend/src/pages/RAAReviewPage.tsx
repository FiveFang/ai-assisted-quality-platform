import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import useSWR from 'swr'
import { Loader2, AlertTriangle, CheckCircle, XCircle, ChevronLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { SkillPanel } from '@/components/SkillPanel'
import { ConfidenceBadge } from '@/components/ConfidenceBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { fetcher, api } from '@/api/client'
import type { NormalizedRequirement, Ambiguity, Requirement, Workflow, Entity, BusinessRule } from '@/types/api'

const PRIORITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'secondary'> = {
  P0: 'danger',
  P1: 'warning',
  P2: 'info',
  P3: 'secondary',
}

const TYPE_VARIANT: Record<string, 'default' | 'purple' | 'warning' | 'info' | 'secondary'> = {
  FUNCTIONAL: 'default',
  SECURITY: 'purple',
  PERFORMANCE: 'warning',
  NON_FUNCTIONAL: 'secondary',
  ACCESSIBILITY: 'info',
}

const SEVERITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'secondary'> = {
  BLOCKING: 'danger',
  HIGH: 'warning',
  MEDIUM: 'info',
  LOW: 'secondary',
}

function RequirementItem({ req }: { req: Requirement }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-muted-foreground">{req.requirement_id}</span>
          <Badge variant={PRIORITY_VARIANT[req.priority] ?? 'secondary'}>{req.priority}</Badge>
          <Badge variant={TYPE_VARIANT[req.type] ?? 'secondary'}>{req.type}</Badge>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {open ? 'less' : 'more'}
        </button>
      </div>
      <p className="text-sm font-medium">{req.title}</p>
      {open && (
        <>
          <p className="text-xs text-muted-foreground">{req.description}</p>
          {req.acceptance_criteria.length > 0 && (
            <ul className="text-xs space-y-1 mt-1">
              {req.acceptance_criteria.map((c, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <CheckCircle className="h-3 w-3 text-green-500 mt-0.5 shrink-0" />
                  {c}
                </li>
              ))}
            </ul>
          )}
          {req.tags.length > 0 && (
            <div className="flex gap-1 flex-wrap mt-1">
              {req.tags.map((t) => (
                <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function AmbiguityItem({ amb }: { amb: Ambiguity }) {
  return (
    <div className={`rounded-md border p-3 space-y-1.5 ${amb.blocking ? 'border-red-200 bg-red-50' : ''}`}>
      <div className="flex items-center gap-2">
        <AlertTriangle className={`h-3.5 w-3.5 ${amb.blocking ? 'text-red-500' : 'text-amber-500'}`} />
        <span className="font-mono text-xs text-muted-foreground">{amb.ambiguity_id}</span>
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
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-mono text-xs text-muted-foreground mr-2">{wf.workflow_id}</span>
          <span className="text-sm font-medium">{wf.name}</span>
        </div>
        <button onClick={() => setOpen((v) => !v)} className="text-xs text-muted-foreground hover:text-foreground">
          {open ? 'less' : 'steps'}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">{wf.description}</p>
      {open && wf.steps.length > 0 && (
        <ol className="text-xs space-y-1 border-t pt-2 mt-1">
          {wf.steps.map((s, i) => (
            <li key={s.step_id} className="flex gap-2">
              <span className="text-muted-foreground w-4 shrink-0">{i + 1}.</span>
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
    <div className="flex items-start gap-3 rounded-md border px-3 py-2">
      <Badge variant="secondary" className="mt-0.5 shrink-0">{entity.type}</Badge>
      <div>
        <p className="text-sm font-medium">{entity.name}</p>
        {entity.description && (
          <p className="text-xs text-muted-foreground">{entity.description}</p>
        )}
        {entity.attributes.length > 0 && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {entity.attributes.join(', ')}
          </p>
        )}
      </div>
    </div>
  )
}

function RuleItem({ rule }: { rule: BusinessRule }) {
  return (
    <div className="rounded-md border px-3 py-2 space-y-1">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-muted-foreground">{rule.rule_id}</span>
        <Badge variant="secondary">{rule.rule_type}</Badge>
        {!rule.is_explicit && (
          <Badge variant="warning" className="text-[10px]">inferred</Badge>
        )}
      </div>
      <p className="text-sm">{rule.description}</p>
    </div>
  )
}

export function RAAReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [rejectReason, setRejectReason] = useState('')
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, error, isLoading } = useSWR<NormalizedRequirement>(
    id ? `/api/v1/requirements/${id}` : null,
    fetcher,
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-24">
        <p className="text-destructive">{error?.message ?? 'Requirement not found'}</p>
      </div>
    )
  }

  const blockingAmbiguities = data.ambiguities.filter((a) => a.blocking)
  const canApprove = blockingAmbiguities.length === 0

  const handleApprove = async () => {
    setSubmitting('approve')
    setActionError(null)
    try {
      await api.reviewRequirement(data.requirement_id, true)
      const suite = await api.generateTests(data.requirement_id)
      navigate(`/tests/${suite.test_suite_id}`)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed')
      setSubmitting(null)
    }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) return
    setSubmitting('reject')
    setActionError(null)
    try {
      await api.reviewRequirement(data.requirement_id, false, rejectReason)
      navigate('/')
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed')
      setSubmitting(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2">
            <ChevronLeft className="h-4 w-4" /> Dashboard
          </Link>
          <h1 className="text-2xl font-semibold">{data.source.reference}</h1>
          <div className="flex items-center gap-3 mt-1">
            <StatusBadge status={data.status} />
            <ConfidenceBadge score={data.metadata.confidence_score} showBar />
            <span className="text-sm text-muted-foreground">
              {data.requirements.length} requirements · {data.workflows.length} workflows · {data.business_rules.length} rules
            </span>
          </div>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <p>Model: {data.metadata.processing_model}</p>
          {data.metadata.processing_duration_ms && (
            <p>{(data.metadata.processing_duration_ms / 1000).toFixed(1)}s</p>
          )}
        </div>
      </div>

      {/* Human review notice */}
      {data.human_review_required && data.review_reasons.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
          <p className="font-medium text-amber-800 mb-1">Human review required</p>
          <ul className="list-disc list-inside space-y-0.5 text-amber-700">
            {data.review_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* Per-skill output panels */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Agent Output — per skill
        </h2>

        <SkillPanel
          skillName="RequirementExtractorSkill"
          label="Extracted Requirements"
          count={data.requirements.length}
          defaultOpen
        >
          {data.requirements.length === 0 ? (
            <p className="text-sm text-muted-foreground">No requirements extracted.</p>
          ) : (
            data.requirements.map((req) => <RequirementItem key={req.requirement_id} req={req} />)
          )}
        </SkillPanel>

        <SkillPanel
          skillName="AmbiguityDetectorSkill"
          label="Ambiguities"
          count={data.ambiguities.length}
          defaultOpen={data.ambiguities.length > 0}
        >
          {data.ambiguities.length === 0 ? (
            <p className="text-sm text-muted-foreground flex items-center gap-1.5">
              <CheckCircle className="h-4 w-4 text-green-500" /> No ambiguities detected.
            </p>
          ) : (
            data.ambiguities.map((a) => <AmbiguityItem key={a.ambiguity_id} amb={a} />)
          )}
        </SkillPanel>

        <SkillPanel
          skillName="WorkflowExtractorSkill"
          label="Workflows"
          count={data.workflows.length}
        >
          {data.workflows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No workflows extracted.</p>
          ) : (
            data.workflows.map((wf) => <WorkflowItem key={wf.workflow_id} wf={wf} />)
          )}
        </SkillPanel>

        <SkillPanel
          skillName="EntityExtractorSkill"
          label="Entities"
          count={data.entities.length}
        >
          {data.entities.length === 0 ? (
            <p className="text-sm text-muted-foreground">No entities extracted.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {data.entities.map((e, i) => <EntityItem key={i} entity={e} />)}
            </div>
          )}
        </SkillPanel>

        <SkillPanel
          skillName="RuleExtractorSkill"
          label="Business Rules"
          count={data.business_rules.length}
        >
          {data.business_rules.length === 0 ? (
            <p className="text-sm text-muted-foreground">No business rules extracted.</p>
          ) : (
            data.business_rules.map((r) => <RuleItem key={r.rule_id} rule={r} />)
          )}
        </SkillPanel>

        <SkillPanel
          skillName="ConfidenceScorerSkill"
          label="Confidence Score"
        >
          <div className="flex items-center gap-4">
            <ConfidenceBadge score={data.metadata.confidence_score} showBar />
            <span className="text-sm text-muted-foreground">
              {data.metadata.confidence_score >= 0.8
                ? 'High confidence — extraction is reliable.'
                : data.metadata.confidence_score >= 0.65
                  ? 'Moderate confidence — review ambiguities carefully.'
                  : 'Low confidence — manual review strongly recommended.'}
            </span>
          </div>
        </SkillPanel>

        <SkillPanel
          skillName="RAGEnricherSkill"
          label="RAG Context"
          count={data.enriched_context.similar_requirements.length}
        >
          {data.enriched_context.similar_requirements.length === 0 &&
          data.enriched_context.relevant_domain_knowledge.length === 0 ? (
            <p className="text-sm text-muted-foreground">No historical context found.</p>
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
                  <ul className="text-xs text-muted-foreground list-disc list-inside">
                    {data.enriched_context.relevant_domain_knowledge.map((k, i) => (
                      <li key={i}>{k}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </SkillPanel>
      </div>

      {/* Review gate */}
      <div className="border-t pt-6 space-y-3">
        {!canApprove && (
          <p className="text-sm text-red-600 flex items-center gap-1.5">
            <XCircle className="h-4 w-4" />
            {blockingAmbiguities.length} blocking {blockingAmbiguities.length === 1 ? 'ambiguity' : 'ambiguities'} must be resolved before approval.
          </p>
        )}

        <div className="flex items-start gap-3">
          <Textarea
            placeholder="Rejection reason (required to reject)…"
            rows={2}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            className="flex-1"
          />
          <div className="flex flex-col gap-2">
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={!rejectReason.trim() || submitting !== null}
            >
              {submitting === 'reject' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
              Reject
            </Button>
            <Button
              onClick={handleApprove}
              disabled={!canApprove || submitting !== null}
            >
              {submitting === 'approve' ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
              ) : (
                <><CheckCircle className="h-4 w-4" /> Approve & Generate Tests</>
              )}
            </Button>
          </div>
        </div>

        {actionError && <p className="text-sm text-destructive">{actionError}</p>}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import useSWR from 'swr'
import {
  Loader2,
  ChevronLeft,
  CheckCircle,
  XCircle,
  Code2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { ScaffoldViewer } from '@/components/ScaffoldViewer'
import { fetcher, api } from '@/api/client'
import { cn } from '@/lib/utils'
import type { TestSuite, TestCase } from '@/types/api'

const PRIORITY_COLOR: Record<string, string> = {
  P0: 'text-red-700 bg-red-50 border-red-200',
  P1: 'text-amber-700 bg-amber-50 border-amber-200',
  P2: 'text-blue-700 bg-blue-50 border-blue-200',
  P3: 'text-slate-600 bg-slate-50 border-slate-200',
}

const TYPE_VARIANT: Record<string, 'default' | 'purple' | 'warning' | 'info' | 'secondary' | 'danger'> = {
  FUNCTIONAL: 'default',
  API: 'info',
  SECURITY: 'purple',
  UI: 'secondary',
  MOBILE: 'secondary',
  EDGE_CASE: 'warning',
  NEGATIVE: 'danger',
}

const ALL_TYPES = ['FUNCTIONAL', 'API', 'SECURITY', 'UI', 'MOBILE', 'EDGE_CASE', 'NEGATIVE']

function TestCaseRow({
  tc,
  selected,
  active,
  onSelect,
  onClick,
}: {
  tc: TestCase
  selected: boolean
  active: boolean
  onSelect: () => void
  onClick: () => void
}) {
  return (
    <div
      className={cn(
        'border-b px-4 py-3 flex items-start gap-3 cursor-pointer transition-colors',
        active ? 'bg-accent' : 'hover:bg-muted/40',
        tc.is_duplicate && 'opacity-50',
      )}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={onSelect}
        onClick={(e) => e.stopPropagation()}
        className="mt-1 h-4 w-4 shrink-0"
      />
      <div className="flex-1 min-w-0" onClick={onClick}>
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span
            className={cn(
              'rounded-full border px-1.5 py-0 text-[10px] font-bold',
              PRIORITY_COLOR[tc.priority] ?? PRIORITY_COLOR.P3,
            )}
          >
            {tc.priority}
          </span>
          <Badge variant={TYPE_VARIANT[tc.type] ?? 'secondary'} className="text-[10px]">
            {tc.type}
          </Badge>
          {tc.automation_scaffold && (
            <Code2 className="h-3 w-3 text-green-500" />
          )}
          {tc.is_duplicate && (
            <Badge variant="secondary" className="text-[10px]">duplicate</Badge>
          )}
        </div>
        <p className="text-sm font-medium truncate">{tc.title}</p>
        <p className="text-xs text-muted-foreground font-mono">{tc.source_requirement_id}</p>
      </div>
      {active ? (
        <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
      ) : (
        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
      )}
    </div>
  )
}

function TestCaseDetail({ tc }: { tc: TestCase }) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-semibold">{tc.title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{tc.description}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-muted-foreground">Type</span>
          <p className="font-medium">{tc.type}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Priority</span>
          <p className="font-medium">{tc.priority}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Source</span>
          <p className="font-mono">{tc.source_requirement_id}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Risk</span>
          <p className="font-medium">{Math.round(tc.risk_score * 100)}%</p>
        </div>
      </div>

      {tc.preconditions.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1.5">Preconditions</p>
          <ul className="text-xs space-y-1">
            {tc.preconditions.map((p, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="text-muted-foreground shrink-0">•</span> {p}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tc.steps.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1.5">Steps</p>
          <ol className="text-xs space-y-2">
            {tc.steps.map((s) => (
              <li key={s.step_number} className="flex gap-2">
                <span className="text-muted-foreground font-mono w-4 shrink-0">{s.step_number}.</span>
                <div>
                  <p>{s.action}</p>
                  <p className="text-muted-foreground mt-0.5">→ {s.expected_result}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {tc.expected_results.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1.5">Expected results</p>
          <ul className="text-xs space-y-1">
            {tc.expected_results.map((r, i) => (
              <li key={i} className="flex gap-1.5">
                <CheckCircle className="h-3 w-3 text-green-500 mt-0.5 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tc.assertions.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1.5">Assertions</p>
          <ul className="text-xs space-y-1 font-mono">
            {tc.assertions.map((a) => (
              <li key={a.assertion_id} className="text-muted-foreground">
                {a.assertion_type} {a.operator} {String(a.expected_value)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tc.automation_scaffold && (
        <div>
          <p className="text-xs font-medium mb-1.5">Scaffold</p>
          <ScaffoldViewer scaffold={tc.automation_scaffold} />
        </div>
      )}
    </div>
  )
}

export function TGAReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeType, setActiveType] = useState<string>('ALL')
  const [activeTestId, setActiveTestId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [rejectReason, setRejectReason] = useState('')
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, error, isLoading } = useSWR<TestSuite>(
    id ? `/api/v1/tests/${id}` : null,
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
        <p className="text-destructive">{error?.message ?? 'Test suite not found'}</p>
      </div>
    )
  }

  const filtered =
    activeType === 'ALL'
      ? data.test_cases
      : data.test_cases.filter((tc) => tc.type === activeType)

  const sorted = [...filtered].sort((a, b) => {
    const order = ['P0', 'P1', 'P2', 'P3']
    return order.indexOf(a.priority) - order.indexOf(b.priority)
  })

  const activeTest = data.test_cases.find((tc) => tc.test_id === activeTestId)

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(sorted.filter((tc) => !tc.is_duplicate).map((tc) => tc.test_id)))
  const clearAll = () => setSelected(new Set())

  const handleApprove = async () => {
    setSubmitting('approve')
    setActionError(null)
    try {
      await api.reviewTestSuite(data.test_suite_id, true)
      navigate(`/requirements/${data.source_requirement_id}`)
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
      await api.reviewTestSuite(data.test_suite_id, false, rejectReason)
      navigate(`/requirements/${data.source_requirement_id}`)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed')
      setSubmitting(null)
    }
  }

  const typesPresent = ALL_TYPES.filter((t) => data.metadata.by_type[t])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <Link
          to={`/requirements/${data.source_requirement_id}`}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2"
        >
          <ChevronLeft className="h-4 w-4" /> RAA Review
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Test Review</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {data.metadata.total_test_cases} cases generated · coverage {Math.round(data.metadata.coverage_estimate * 100)}%
            </p>
          </div>
          <div className="flex gap-2 flex-wrap justify-end text-xs">
            {Object.entries(data.metadata.by_priority).map(([p, n]) => (
              <span key={p} className={cn('rounded-full border px-2 py-0.5 font-semibold', PRIORITY_COLOR[p] ?? PRIORITY_COLOR.P3)}>
                {p}: {n}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Coverage bar */}
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${data.metadata.coverage_estimate * 100}%` }}
        />
      </div>

      {/* Type filter tabs */}
      <div className="flex gap-1 flex-wrap">
        <button
          onClick={() => setActiveType('ALL')}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            activeType === 'ALL' ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/70',
          )}
        >
          All ({data.metadata.total_test_cases})
        </button>
        {typesPresent.map((t) => (
          <button
            key={t}
            onClick={() => setActiveType(t)}
            className={cn(
              'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              activeType === t ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/70',
            )}
          >
            {t} ({data.metadata.by_type[t]})
          </button>
        ))}
      </div>

      {/* Master-detail */}
      <div className="flex gap-4 min-h-[500px]">
        {/* List */}
        <div className="w-80 shrink-0 rounded-lg border overflow-hidden flex flex-col">
          <div className="flex items-center justify-between border-b px-4 py-2 bg-muted/30">
            <span className="text-xs text-muted-foreground">{sorted.length} shown</span>
            <div className="flex gap-2 text-xs">
              <button onClick={selectAll} className="hover:text-foreground text-muted-foreground">select non-dup</button>
              <button onClick={clearAll} className="hover:text-foreground text-muted-foreground">clear</button>
            </div>
          </div>
          <div className="overflow-y-auto flex-1">
            {sorted.map((tc) => (
              <TestCaseRow
                key={tc.test_id}
                tc={tc}
                selected={selected.has(tc.test_id)}
                active={tc.test_id === activeTestId}
                onSelect={() => toggleSelect(tc.test_id)}
                onClick={() => setActiveTestId(tc.test_id === activeTestId ? null : tc.test_id)}
              />
            ))}
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 rounded-lg border overflow-y-auto p-5">
          {activeTest ? (
            <TestCaseDetail tc={activeTest} />
          ) : (
            <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
              Select a test case to view details
            </div>
          )}
        </div>
      </div>

      {/* Review gate */}
      <div className="border-t pt-5 space-y-3">
        <p className="text-sm text-muted-foreground">
          {selected.size} selected · {data.test_cases.filter((tc) => tc.is_duplicate).length} duplicates (pre-deselected)
        </p>

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
            <Button onClick={handleApprove} disabled={submitting !== null}>
              {submitting === 'approve' ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Approving…</>
              ) : (
                <><CheckCircle className="h-4 w-4" /> Approve All</>
              )}
            </Button>
          </div>
        </div>

        {actionError && <p className="text-sm text-destructive">{actionError}</p>}
      </div>
    </div>
  )
}

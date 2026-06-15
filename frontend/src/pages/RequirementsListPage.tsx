import { Link } from 'react-router-dom'
import useSWR from 'swr'
import { Loader2, Plus, FileText, ClipboardCheck, Clock, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ConfidenceBadge } from '@/components/ConfidenceBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { fetcher } from '@/api/client'
import type { RequirementSummary } from '@/types/api'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function StatCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType
  label: string
  value: number
  sub?: string
}) {
  return (
    <div className="rounded-xl border bg-card px-5 py-4">
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        <Icon className="h-4 w-4" />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-semibold text-foreground tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

export function RequirementsListPage() {
  const { data, error, isLoading } = useSWR<RequirementSummary[]>(
    '/requirements/',
    fetcher,
    { refreshInterval: 10000 },
  )

  const awaitingReview = data?.filter((r) => r.status === 'AWAITING_REVIEW').length ?? 0
  const approved = data?.filter((r) => r.status === 'APPROVED').length ?? 0

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Requirements</h1>
          <p className="text-sm text-muted-foreground mt-1">All analyzed requirement sets, newest first.</p>
        </div>
        <Button asChild>
          <Link to="/analyze">
            <Plus className="h-4 w-4" />
            New Analysis
          </Link>
        </Button>
      </div>

      {/* Stats row */}
      {data && data.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <StatCard icon={ClipboardCheck} label="Total" value={data.length} sub="all time" />
          <StatCard icon={AlertCircle} label="Needs Review" value={awaitingReview}
            sub={awaitingReview > 0 ? 'action required' : 'all clear'} />
          <StatCard icon={Clock} label="Approved" value={approved} sub="ready for testing" />
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error.message}
        </div>
      )}

      {data && data.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card py-24 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted mb-4">
            <FileText className="h-6 w-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground">No analyses yet</p>
          <p className="text-xs text-muted-foreground mt-1.5 mb-5 max-w-xs">
            Submit a PRD, Jira export, or OpenAPI spec to extract requirements and generate test suites.
          </p>
          <Button asChild size="sm">
            <Link to="/analyze">Run first analysis</Link>
          </Button>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="rounded-2xl border bg-card overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="text-left px-5 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Reference</th>
                <th className="text-left px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Confidence</th>
                <th className="text-left px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Reqs</th>
                <th className="text-left px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Analyzed</th>
                <th className="px-4 py-3" />
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {data.map((req) => (
                <tr key={req.requirement_id} className="hover:bg-muted/30 transition-colors group">
                  <td className="px-5 py-3.5">
                    <div className="font-medium text-foreground">{req.reference}</div>
                    <div className="text-[11px] text-muted-foreground font-mono mt-0.5">{req.requirement_id}</div>
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <StatusBadge status={req.status} />
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    <ConfidenceBadge score={req.confidence_score} />
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="tabular-nums text-muted-foreground">{req.requirement_count}</span>
                  </td>
                  <td className="px-4 py-3.5 text-muted-foreground text-xs">{timeAgo(req.created_at)}</td>
                  <td className="px-4 py-3.5">
                    <Button variant="ghost" size="sm" asChild className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <Link to={`/requirements/${req.requirement_id}`}>Review →</Link>
                    </Button>
                  </td>
                  <td className="px-4 py-3.5">
                    {req.test_suite_id ? (
                      <Button variant="ghost" size="sm" asChild className="opacity-0 group-hover:opacity-100 transition-opacity">
                        <Link to={`/tests/${req.test_suite_id}`}>Tests →</Link>
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground/50">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

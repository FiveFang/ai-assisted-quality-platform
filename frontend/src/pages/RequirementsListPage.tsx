import { Link } from 'react-router-dom'
import useSWR from 'swr'
import { Loader2, Plus, FileText } from 'lucide-react'
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
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

export function RequirementsListPage() {
  const { data, error, isLoading } = useSWR<RequirementSummary[]>(
    '/requirements/',
    fetcher,
    { refreshInterval: 10000 },
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Requirements</h1>
          <p className="text-muted-foreground text-sm mt-1">
            All analyzed requirement sets, newest first.
          </p>
        </div>
        <Button asChild>
          <Link to="/analyze">
            <Plus className="h-4 w-4" />
            New Analysis
          </Link>
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error.message}
        </div>
      )}

      {data && data.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-24 text-center">
          <FileText className="h-10 w-10 text-muted-foreground mb-4" />
          <p className="text-sm font-medium">No analyses yet</p>
          <p className="text-xs text-muted-foreground mt-1 mb-4">
            Submit a PRD, Jira export, or OpenAPI spec to get started.
          </p>
          <Button asChild size="sm">
            <Link to="/analyze">Run first analysis</Link>
          </Button>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Reference</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Confidence</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Reqs</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Analyzed</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Analysis</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Tests</th>
              </tr>
            </thead>
            <tbody>
              {data.map((req, i) => (
                <tr
                  key={req.requirement_id}
                  className={`border-b last:border-0 hover:bg-muted/20 transition-colors ${i % 2 === 0 ? '' : 'bg-muted/10'}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium">{req.reference}</div>
                    <div className="text-xs text-muted-foreground font-mono mt-0.5">
                      {req.requirement_id}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={req.status} />
                      {req.human_review_required && req.status === 'AWAITING_REVIEW' && (
                        <span className="text-xs text-amber-600 font-medium">review needed</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBadge score={req.confidence_score} />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {req.requirement_count}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {timeAgo(req.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Button variant="ghost" size="sm" asChild>
                      <Link to={`/requirements/${req.requirement_id}`}>View →</Link>
                    </Button>
                  </td>
                  <td className="px-4 py-3">
                    {req.test_suite_id ? (
                      <Button variant="ghost" size="sm" asChild>
                        <Link to={`/tests/${req.test_suite_id}`}>View →</Link>
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
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

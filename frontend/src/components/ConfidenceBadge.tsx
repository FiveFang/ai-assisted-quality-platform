import { cn } from '@/lib/utils'

interface Props {
  score: number
  showBar?: boolean
}

export function ConfidenceBadge({ score, showBar = false }: Props) {
  const pct = Math.round(score * 100)
  const color =
    score >= 0.8
      ? 'text-green-700 bg-green-50 border-green-200'
      : score >= 0.65
        ? 'text-amber-700 bg-amber-50 border-amber-200'
        : 'text-red-700 bg-red-50 border-red-200'

  const barColor = score >= 0.8 ? 'bg-green-500' : score >= 0.65 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="inline-flex items-center gap-2">
      <span className={cn('rounded-full border px-2.5 py-0.5 text-xs font-semibold', color)}>
        {pct}%
      </span>
      {showBar && (
        <div className="h-2 w-24 rounded-full bg-muted overflow-hidden">
          <div className={cn('h-full rounded-full', barColor)} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  )
}

import { cn } from '@/lib/utils'

interface Props {
  score: number
  showBar?: boolean
}

export function ConfidenceBadge({ score, showBar = false }: Props) {
  const pct = Math.round(score * 100)
  const { text, bg, ring, bar } =
    score >= 0.8
      ? { text: 'text-emerald-700', bg: 'bg-emerald-50', ring: 'ring-emerald-200', bar: 'bg-emerald-500' }
      : score >= 0.65
        ? { text: 'text-amber-700', bg: 'bg-amber-50', ring: 'ring-amber-200', bar: 'bg-amber-500' }
        : { text: 'text-red-700', bg: 'bg-red-50', ring: 'ring-red-200', bar: 'bg-red-400' }

  return (
    <div className="inline-flex items-center gap-2.5">
      <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1', text, bg, ring)}>
        {pct}%
      </span>
      {showBar && (
        <div className="h-1.5 w-20 rounded-full bg-muted overflow-hidden">
          <div className={cn('h-full rounded-full transition-all', bar)} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  )
}

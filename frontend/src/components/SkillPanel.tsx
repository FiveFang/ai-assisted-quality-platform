import type { ReactNode } from 'react'
import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronDown, Loader2, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  skillName: string
  label: string
  description?: string
  count?: number
  defaultOpen?: boolean
  children: ReactNode
  onRetry?: () => void
  retrying?: boolean
}

export function SkillPanel({ skillName, label, description, count, defaultOpen = false, children, onRetry, retrying }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <div
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setOpen((v) => !v) }}
          className={cn(
            'flex w-full items-center justify-between rounded-xl border bg-card px-4 py-3 text-sm transition-colors hover:bg-muted/50 cursor-pointer select-none',
            open && 'rounded-b-none border-b-transparent',
          )}
        >
          <div className="flex items-center gap-3 min-w-0">
            <span className="shrink-0 rounded-md bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary ring-1 ring-primary/20">
              {skillName.replace('Skill', '')}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-foreground truncate">{label}</span>
                {count !== undefined && (
                  <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground tabular-nums">
                    {count}
                  </span>
                )}
              </div>
              {description && (
                <p className="text-[11px] text-muted-foreground truncate mt-0.5">{description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {onRetry && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onRetry() }}
                disabled={retrying}
                className="flex items-center gap-1 rounded-md border border-primary/30 bg-primary/5 px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/10 disabled:opacity-50 transition-colors"
              >
                {retrying
                  ? <Loader2 className="h-3 w-3 animate-spin" />
                  : <RotateCcw className="h-3 w-3" />
                }
                {retrying ? 'Retrying…' : 'Retry'}
              </button>
            )}
            <ChevronDown
              className={cn(
                'h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200',
                open && 'rotate-180',
              )}
            />
          </div>
        </div>
      </Collapsible.Trigger>

      <Collapsible.Content className="overflow-hidden">
        <div className="rounded-b-xl border border-t-0 bg-card p-4 space-y-3">
          {children}
        </div>
      </Collapsible.Content>
    </Collapsible.Root>
  )
}

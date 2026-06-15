import type { ReactNode } from 'react'
import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  skillName: string
  label: string
  count?: number
  defaultOpen?: boolean
  children: ReactNode
}

export function SkillPanel({ skillName, label, count, defaultOpen = false, children }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger
        className={cn(
          'flex w-full items-center justify-between rounded-xl border bg-card px-4 py-3 text-sm transition-colors hover:bg-muted/50',
          open && 'rounded-b-none border-b-transparent',
        )}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="shrink-0 rounded-md bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary ring-1 ring-primary/20">
            {skillName.replace('Skill', '')}
          </span>
          <span className="font-medium text-foreground truncate">{label}</span>
          {count !== undefined && (
            <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground tabular-nums">
              {count}
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200',
            open && 'rotate-180',
          )}
        />
      </Collapsible.Trigger>

      <Collapsible.Content className="overflow-hidden">
        <div className="rounded-b-xl border border-t-0 bg-card p-4 space-y-3">
          {children}
        </div>
      </Collapsible.Content>
    </Collapsible.Root>
  )
}

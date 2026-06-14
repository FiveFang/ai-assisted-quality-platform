import type { ReactNode } from 'react'
import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronDown, ChevronRight } from 'lucide-react'
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
      <Collapsible.Trigger className="flex w-full items-center justify-between rounded-md border bg-muted/40 px-4 py-3 text-sm hover:bg-muted/70 transition-colors">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            {skillName}
          </span>
          <span className="font-medium">{label}</span>
          {count !== undefined && (
            <span className="text-xs text-muted-foreground">({count})</span>
          )}
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
      </Collapsible.Trigger>
      <Collapsible.Content
        className={cn(
          'overflow-hidden data-[state=open]:animate-none',
        )}
      >
        <div className="border border-t-0 rounded-b-md p-4 space-y-3">{children}</div>
      </Collapsible.Content>
    </Collapsible.Root>
  )
}

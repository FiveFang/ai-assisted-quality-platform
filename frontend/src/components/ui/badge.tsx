import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default:     'bg-primary text-primary-foreground',
        secondary:   'bg-muted text-muted-foreground',
        destructive: 'bg-red-50 text-red-700 ring-1 ring-red-200',
        outline:     'ring-1 ring-border text-foreground bg-transparent',
        success:     'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
        warning:     'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
        danger:      'bg-red-50 text-red-700 ring-1 ring-red-200',
        info:        'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
        purple:      'bg-violet-50 text-violet-700 ring-1 ring-violet-200',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }

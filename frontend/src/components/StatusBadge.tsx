import type { ProcessingStatus } from '@/types/api'
import { Badge } from '@/components/ui/badge'

const CONFIG: Record<ProcessingStatus, { label: string; variant: 'success' | 'warning' | 'danger' | 'info' | 'secondary' }> = {
  PENDING: { label: 'Pending', variant: 'secondary' },
  PROCESSING: { label: 'Processing', variant: 'info' },
  AWAITING_REVIEW: { label: 'Needs Review', variant: 'warning' },
  APPROVED: { label: 'Approved', variant: 'success' },
  REJECTED: { label: 'Rejected', variant: 'danger' },
  FAILED: { label: 'Failed', variant: 'danger' },
}

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  const { label, variant } = CONFIG[status] ?? { label: status, variant: 'secondary' }
  return <Badge variant={variant}>{label}</Badge>
}

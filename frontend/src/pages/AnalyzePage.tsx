import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { api } from '@/api/client'

const schema = z.object({
  reference: z.string().min(1, 'Project name is required'),
  prd: z.string().optional(),
  jira: z.string().optional(),
  openapi: z.string().optional(),
}).refine(
  (d) => d.prd || d.jira || d.openapi,
  { message: 'Provide at least one input (PRD, Jira, or OpenAPI)', path: ['prd'] },
)

type FormValues = z.infer<typeof schema>

function InputSection({
  title,
  badge,
  children,
  defaultOpen = false,
}: {
  title: string
  badge?: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-lg border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-sm"
      >
        <div className="flex items-center gap-2">
          <span className="font-medium">{title}</span>
          {badge && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {badge}
            </span>
          )}
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>
      {open && <div className="p-4 border-t">{children}</div>}
    </div>
  )
}

export function AnalyzePage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (values: FormValues) => {
    setError(null)
    const raw_inputs: Record<string, string> = {}
    if (values.prd) raw_inputs.prd = values.prd
    if (values.jira) raw_inputs.jira = values.jira
    if (values.openapi) raw_inputs.openapi = values.openapi

    try {
      const source_type = values.prd ? 'PRD' : values.jira ? 'JIRA' : 'OPENAPI'
      const result = await api.analyzeRequirements({
        source_type,
        reference: values.reference,
        raw_inputs,
      })
      navigate(`/requirements/${result.requirement_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">New Analysis</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Provide your requirement artifacts. All inputs are optional — submit what you have.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="reference">Project name / reference</Label>
          <Input
            id="reference"
            placeholder="e.g. checkout-v2-redesign"
            {...register('reference')}
          />
          {errors.reference && (
            <p className="text-xs text-destructive">{errors.reference.message}</p>
          )}
        </div>

        <div className="space-y-3">
          <InputSection title="PRD / Design Doc" badge="text" defaultOpen>
            <Textarea
              rows={10}
              placeholder="Paste your PRD or design document here..."
              className="font-mono text-xs"
              {...register('prd')}
            />
          </InputSection>

          <InputSection title="Jira Stories" badge="JSON or text">
            <Textarea
              rows={8}
              placeholder="Paste exported Jira JSON or story descriptions..."
              className="font-mono text-xs"
              {...register('jira')}
            />
          </InputSection>

          <InputSection title="OpenAPI Spec" badge="YAML or JSON">
            <Textarea
              rows={8}
              placeholder="Paste your OpenAPI/Swagger spec here..."
              className="font-mono text-xs"
              {...register('openapi')}
            />
          </InputSection>
        </div>

        {(errors.prd?.message ?? error) && (
          <p className="text-sm text-destructive">
            {errors.prd?.message ?? error}
          </p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button
            type="submit"
            disabled={isSubmitting}
            className="min-w-32"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing…
              </>
            ) : (
              'Run Analysis →'
            )}
          </Button>
        </div>

        {isSubmitting && (
          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground mb-2">Running pipeline…</p>
            <ul className="space-y-1 text-xs">
              <li>⟳ Parsing artifacts</li>
              <li>⟳ Extracting requirements</li>
              <li>⟳ Enriching with RAG context</li>
              <li>⟳ Detecting ambiguities</li>
              <li>⟳ Scoring confidence</li>
            </ul>
          </div>
        )}
      </form>
    </div>
  )
}

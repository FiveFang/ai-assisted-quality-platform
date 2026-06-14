import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { AutomationScaffold } from '@/types/api'

export function ScaffoldViewer({ scaffold }: { scaffold: AutomationScaffold }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(scaffold.scaffold_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([scaffold.scaffold_code], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = scaffold.file_path_suggestion.split('/').pop() ?? 'test.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="rounded-md border bg-zinc-950 text-zinc-100 overflow-hidden">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            {scaffold.framework}
          </span>
          <span className="text-xs text-zinc-500">{scaffold.file_path_suggestion}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
            onClick={handleCopy}
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
            onClick={handleDownload}
          >
            Download
          </Button>
        </div>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed font-mono">
        <code>{scaffold.scaffold_code}</code>
      </pre>
    </div>
  )
}

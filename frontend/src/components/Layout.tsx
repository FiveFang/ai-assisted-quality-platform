import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { FlaskConical } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-primary">
            <FlaskConical className="h-5 w-5" />
            QA Platform
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              to="/analyze"
              className={cn(
                'text-muted-foreground hover:text-foreground transition-colors',
                pathname === '/analyze' && 'text-foreground font-medium',
              )}
            >
              New Analysis
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  )
}

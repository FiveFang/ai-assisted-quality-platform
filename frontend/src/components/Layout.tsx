import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { FlaskConical } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()

  const navLinks = [
    { to: '/', label: 'Requirements', exact: true },
    { to: '/analyze', label: 'New Analysis', exact: false },
  ]

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-white/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 h-14">
          <Link to="/" className="flex items-center gap-2.5 font-semibold text-foreground shrink-0">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/20">
              <FlaskConical className="h-3.5 w-3.5 text-primary" />
            </div>
            <span className="text-sm">QA Platform</span>
          </Link>

          <nav className="flex items-center gap-0.5 text-sm">
            {navLinks.map(({ to, label, exact }) => {
              const active = exact ? pathname === to : pathname.startsWith(to)
              return (
                <Link
                  key={to}
                  to={to}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted',
                  )}
                >
                  {label}
                </Link>
              )
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  )
}

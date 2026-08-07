import { Link, NavLink } from 'react-router-dom'
import { Wordmark } from '@/components/bauhaus'

/** Plain centred container, for pages with no company in scope. */
export function Page({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
  )
}

export function Masthead({ minimal = false }: { minimal?: boolean }) {
  return (
    <header className="border-rule bg-panel border-b">
      <div className="mx-auto flex h-12 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none">
          <Wordmark />
        </Link>
        {!minimal && (
          <nav className="ml-auto flex items-center gap-4">
            <NavLink to="/companies" className="eyebrow text-ink-soft hover:text-ink">
              companies
            </NavLink>
            <Link to="/" className="btn py-1 text-[0.8125rem]">
              start one
            </Link>
          </nav>
        )}
      </div>
    </header>
  )
}

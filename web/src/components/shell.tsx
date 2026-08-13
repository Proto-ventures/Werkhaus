import { useEffect, useState } from 'react'
import { flushSync } from 'react-dom'
import { useReducedMotion } from 'motion/react'
import { useTheme } from 'next-themes'
import { Link, NavLink } from 'react-router-dom'
import { Wordmark } from '@/components/bauhaus'
import { startHere } from '@/routes/Landing'

/** Plain centred container, for pages with no company in scope. */
export function Page({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
  )
}

/**
 * Light and dark, said in the interface's own alphabet.
 *
 * A sun and a moon would be the first thing anyone reaches for, and they are
 * pictures of the weather rather than of a setting. This is the same filled
 * square the marks use everywhere else: filled for paper, hollow for after
 * dark. It reads at 10px, it reads in greyscale, and it does not introduce a
 * seventh shape to a product built out of three.
 */
function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const reduced = useReducedMotion()
  // next-themes cannot know the stored choice until it has mounted, and
  // rendering the wrong state for one frame is worse than rendering none.
  const [ready, setReady] = useState(false)
  useEffect(() => setReady(true), [])

  const dark = resolvedTheme === 'dark'

  /**
   * One crossfade for the whole page rather than a transition on every
   * element. Transitioning colours individually is the version that turns into
   * an eyesore: a thousand things easing at slightly different rates, and
   * hover states that feel sluggish forever afterwards.
   *
   * flushSync because the browser snapshots the page the instant the callback
   * returns, and React would otherwise still be holding the update.
   */
  function flip(next: string) {
    const start = document.startViewTransition?.bind(document)
    if (reduced || !start) {
      setTheme(next)
      return
    }
    start(() => flushSync(() => setTheme(next)))
  }

  return (
    <button
      type="button"
      onClick={() => flip(dark ? 'light' : 'dark')}
      aria-label={dark ? 'Switch to the light theme' : 'Switch to the dark theme'}
      title={dark ? 'light' : 'dark'}
      className="focus-visible:ring-ring hover:bg-secondary -m-2 flex size-11 items-center justify-center transition-colors focus-visible:ring-2 focus-visible:outline-none"
    >
      {ready && (
        <span
          className={
            dark
              ? 'border-ink mark mark-square border-2 bg-transparent'
              : 'bg-ink mark mark-square'
          }
        />
      )}
    </button>
  )
}

export function Masthead({ minimal = false }: { minimal?: boolean }) {
  return (
    <header className="border-rule bg-panel sticky top-0 z-40 border-b">
      <div className="mx-auto flex h-12 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link
          to="/"
          className="focus-visible:ring-ring -m-2 inline-flex min-h-11 items-center p-2 focus-visible:ring-2 focus-visible:outline-none"
        >
          <Wordmark />
        </Link>
        <nav className="ml-auto flex items-center gap-4">
          <ThemeToggle />
          {!minimal && (
            <>
              <NavLink
                to="/companies"
                className="eyebrow text-ink-soft hover:text-ink focus-visible:ring-ring -m-3 hidden min-h-11 items-center p-3 focus-visible:ring-2 focus-visible:outline-none sm:inline-flex"
              >
                companies
              </NavLink>
              {/* On the landing route this was a link to the page it was
                  already on. Now it does what it says. */}
              <Link
                to="/"
                onClick={(e) => {
                  if (location.pathname === '/' && startHere()) e.preventDefault()
                }}
                className="btn py-1 text-[0.8125rem]"
              >
                start one
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}

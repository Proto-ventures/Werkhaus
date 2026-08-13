/**
 * Eight small line drawings, one per employee.
 *
 * The roster used to be eight rows of name, job title and a sentence, which is
 * a paragraph pretending to be a list — the eye slides off it. A drawing is
 * read before it is decoded, so the grid can be scanned at a glance and the
 * sentence underneath becomes something you choose to read rather than
 * something in the way.
 *
 * Drawn in the same hairline the rest of the page is built from, monochrome, on
 * `currentColor`, so they inherit the theme and hold up in print and greyscale.
 * No avatars: a generated face for someone who is not a person is the exact
 * kind of confident fiction this product is against.
 */

export type SigilName =
  | 'chief'
  | 'researcher'
  | 'strategist'
  | 'brand'
  | 'growth'
  | 'analyst'
  | 'engineer'
  | 'critic'

export function Sigil({ name, className }: { name: SigilName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.15}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden
    >
      {DRAWINGS[name]}
    </svg>
  )
}

const DRAWINGS: Record<SigilName, React.ReactNode> = {
  /** The agenda: a sheet with a folded corner and what is on it. */
  chief: (
    <>
      <path d="M5 3h9l5 5v13H5z" />
      <path d="M14 3v5h5" />
      <path d="M8 12h8M8 15h8M8 18h5" />
    </>
  ),
  /** Reading: the glass she reads rival pricing pages through. */
  researcher: (
    <>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15l5.5 5.5" />
    </>
  ),
  /** One answer, not a menu: three on the list, one of them committed to. */
  strategist: (
    <>
      <rect x="3" y="4.5" width="3.5" height="3.5" />
      <path d="M9.5 6.25h11" />
      <rect x="3" y="10.25" width="3.5" height="3.5" fill="currentColor" />
      <path d="M9.5 12h11" />
      <rect x="3" y="16" width="3.5" height="3.5" />
      <path d="M9.5 17.75h11" />
    </>
  ),
  /** The words, in the customer's language: a line said out loud. */
  brand: (
    <>
      <path d="M3 5h18v11H9l-4 4v-4H3z" />
      <path d="M7 9h10M7 12h6" />
    </>
  ),
  /** Where they already are. */
  growth: (
    <>
      <path d="M12 3a5 5 0 015 5c0 3.8-5 9-5 9s-5-5.2-5-9a5 5 0 015-5z" />
      <circle cx="12" cy="8" r="1.7" />
      <path d="M3 21h18" />
    </>
  ),
  /** The money model: three bars, one baseline. */
  analyst: (
    <>
      <path d="M3 21h18" />
      <path d="M6 21V11M12 21V5M18 21V14" strokeWidth={1.6} />
    </>
  ),
  /** The page everyone sees, in a browser that is not built yet. */
  engineer: (
    <>
      <path d="M3 5h18v15H3z" />
      <path d="M3 9h18" />
      <path d="M6 7h.01M9 7h.01" strokeWidth={1.8} />
    </>
  ),
  /** The objection, in the shape a fatal mark is drawn in everywhere else. */
  critic: (
    <>
      <path d="M12 3l9 18H3z" />
      <path d="M12 10v5" strokeWidth={1.6} />
      <path d="M12 18h.01" strokeWidth={1.8} />
    </>
  ),
}

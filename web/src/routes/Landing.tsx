import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { LiveShift } from '@/components/demo'
import { useTypedPlaceholder } from '@/components/motion'
import { ReportReplay } from '@/components/report'
import dandelions from '@/assets/dandelions.webp'
import wheat from '@/assets/wheat.webp'

/**
 * The front page shows the product twice: once running, once finished.
 *
 * Around it, a collage: the two canvases cut onto the paper at full strength,
 * one per side, with colour planes sampled from the paintings themselves
 * bridging the seams. Cut-outs rather than washes — a veiled painting is
 * wallpaper, a cut one is a composition. The planes reuse the site's own
 * vocabulary (blob, hexagon, ring, square) so the geometry and the fields
 * read as one picture, not a theme and an afterthought.
 */
export function Landing() {
  return (
    <>
      <Hero />
      <Report />
      <Close />
    </>
  )
}

const IDEAS = [
  'A monthly subscription box for hand-thrown ceramics, one object a month from a named potter.',
  'A booking tool for mobile dog groomers who currently run everything through WhatsApp.',
  'A refill service for cleaning products, delivered by cargo bike.',
]

/** Museum label. An unattributed background is decoration; this is a choice. */
function Caption({ text, className }: { text: string; className?: string }) {
  return (
    <p
      className={`text-ink-soft bg-paper/85 pointer-events-none z-10 px-2 py-0.5 font-mono text-[0.625rem] ${className ?? ''}`}
    >
      {text}
    </p>
  )
}

function Hero() {
  const navigate = useNavigate()
  const [idea, setIdea] = useState('')
  const [focused, setFocused] = useState(false)
  const [busy, setBusy] = useState(false)
  const placeholder = useTypedPlaceholder(IDEAS, focused || idea.length > 0)

  async function begin() {
    if (!idea.trim()) return
    setBusy(true)
    try {
      const company = await api.createCompany(idea.trim())
      navigate(`/c/${company.id}`)
    } catch (e) {
      toast.error((e as Error).message)
      setBusy(false)
    }
  }

  return (
    <section id="top" className="border-rule relative overflow-hidden border-b">
      {/* Small screens: one canvas as a soft backdrop, since there is no room
          for cut-outs beside the text. */}
      <div className="absolute inset-0 lg:hidden" aria-hidden>
        <img
          src={wheat}
          alt=""
          loading="eager"
          className="h-full w-full object-cover object-[66%_45%]"
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to bottom, var(--paper) 34%, color-mix(in oklab, var(--paper) 82%, transparent))',
          }}
        />
      </div>

      {/* Left cut: the Millet, living in the viewport margin on wide screens.
          Width is computed from the free space beside the container, so it
          never reaches the text. */}
      <div
        aria-hidden
        className="absolute inset-y-0 left-0 hidden xl:block"
        style={{
          width: 'min(420px, calc((100vw - 72rem) / 2 + 1.5rem))',
          clipPath: 'polygon(0 0, 100% 0, 74% 100%, 0 100%)',
        }}
      >
        <img
          src={dandelions}
          alt=""
          loading="eager"
          className="h-full w-full object-cover object-[30%_60%]"
        />
      </div>

      {/* Right cut: the Van Gogh at full strength, seam slanting through the
          hero. The demo panel floats on it, solid white on canvas. */}
      <div
        aria-hidden
        className="absolute inset-y-0 right-0 hidden lg:block"
        style={{
          width: 'min(44vw, 700px)',
          clipPath: 'polygon(14% 0, 100% 0, 100% 100%, 0 100%)',
        }}
      >
        <img
          src={wheat}
          alt=""
          loading="eager"
          className="h-full w-full object-cover object-[66%_45%]"
        />
      </div>

      {/* The planes. Each is one of the site's own primitives, in a colour
          sampled from the canvases, placed across a seam so paper and painting
          share pigment. Multiply blends dye rather than cover. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 hidden lg:block">
        <div
          className="bg-wheat-gold absolute -top-24 left-[2vw] h-[24rem] w-[22rem] mix-blend-multiply"
          style={{ opacity: 0.42, borderRadius: '58% 42% 63% 37% / 46% 58% 42% 54%' }}
        />
        <div
          className="bg-cypress absolute top-8 right-[40vw] h-24 w-24"
          style={{
            opacity: 0.88,
            clipPath: 'polygon(28% 4%, 76% 0%, 100% 46%, 74% 98%, 22% 100%, 0% 52%)',
          }}
        />
        <div
          className="border-vg-sky absolute -bottom-24 right-[34vw] size-[20rem] rounded-full border-[3px]"
          style={{ opacity: 0.85 }}
        />
        <div className="bg-yellow absolute right-[42vw] bottom-16 size-7 rotate-[8deg]" />
      </div>

      <Caption
        text="wheat field with cypresses, van gogh, 1889"
        className="absolute right-0 bottom-0"
      />
      <Caption
        text="dandelions, millet, 1868"
        className="absolute bottom-0 left-0 hidden xl:block"
      />

      <div className="relative mx-auto grid max-w-6xl px-4 sm:px-6 lg:grid-cols-[1fr_1fr] lg:gap-12">
        <div className="py-12 lg:py-16">
          <h1 className="display text-[2rem] leading-[1.08] sm:text-[2.75rem]">
            Describe a business.
            <br />
            Eight employees work a shift on it.
          </h1>

          <p className="text-ink-soft mt-5 max-w-xl text-[1.0625rem] leading-relaxed">
            You get market research with the sources attached, a price you can
            defend, and a landing page that loads. Vera, the eighth, spends her
            shift trying to prove the other seven wrong.
          </p>

          <div className="panel mt-8">
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              rows={3}
              placeholder={placeholder}
              className="placeholder:text-ink-faint block w-full resize-none px-4 py-4 text-[0.9375rem] leading-relaxed outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void begin()
              }}
            />
            <div className="border-rule-soft flex items-center justify-between gap-3 border-t px-4 py-2.5">
              <span className="text-ink-faint font-mono text-[0.6875rem]">
                {idea.trim() ? 'ctrl + enter' : 'free while we are testing'}
              </span>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy || !idea.trim()}
                onClick={begin}
              >
                {busy ? 'setting up' : 'start the company'}
              </button>
            </div>
          </div>

          <dl className="mt-8 flex flex-wrap gap-x-8 gap-y-3">
            <Fact k="eight" v="employees on the floor" />
            <Fact k="one" v="paid to attack the rest" />
            <Fact k="every" v="claim marked with its source" />
          </dl>
        </div>

        <div className="pb-12 lg:py-8 lg:pl-8">
          <p className="eyebrow text-ink-faint bg-paper/85 mb-2 inline-block px-1.5 py-0.5">
            a shift, running
          </p>
          <LiveShift />
        </div>
      </div>
    </section>
  )
}

function Fact({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="display text-xl leading-none">{k}</dt>
      <dd className="text-ink-faint bg-paper/85 mt-1 font-mono text-[0.6875rem]">{v}</dd>
    </div>
  )
}

/**
 * The report is pinned over the collage, not mixed into it: the panel stays
 * solid white so the data never shares ground with a painting, and the canvas
 * and planes peek out from behind its edges.
 */
function Report() {
  return (
    <section className="border-rule relative overflow-hidden border-b">
      {/* Wheat again, but a different crop — the golden mass low in the
          canvas, not the hero's cypress framing — so it reads as another
          fragment of the same print, not a repeat. */}
      <div
        aria-hidden
        className="absolute inset-y-0 left-0 hidden xl:block"
        style={{
          width: 'min(360px, calc((100vw - 72rem) / 2 + 1rem))',
          clipPath: 'polygon(0 0, 100% 6%, 70% 100%, 0 100%)',
        }}
      >
        <img
          src={wheat}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover object-[20%_72%]"
        />
      </div>

      <div aria-hidden className="pointer-events-none absolute inset-0 hidden md:block">
        <div
          className="bg-wheat-gold absolute -top-12 right-[3vw] h-[15rem] w-[14rem] mix-blend-multiply"
          style={{ opacity: 0.34, borderRadius: '52% 48% 44% 56% / 60% 42% 58% 40%' }}
        />
        <div
          className="border-vg-sky absolute -bottom-20 left-[9vw] size-[13rem] rounded-full border-[3px]"
          style={{ opacity: 0.8 }}
        />
        <div
          className="bg-meadow absolute top-24 right-[1.5vw] h-16 w-16"
          style={{
            opacity: 0.85,
            clipPath: 'polygon(24% 6%, 74% 0%, 100% 44%, 78% 96%, 20% 100%, 0% 54%)',
          }}
        />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <ReportReplay />
      </div>
    </section>
  )
}

function Close() {
  return (
    <section className="relative overflow-hidden">
      {/* The Millet gets its prominent moment here, mirroring the hero. */}
      <div
        aria-hidden
        className="absolute inset-y-0 right-0 hidden md:block"
        style={{
          width: 'min(38vw, 560px)',
          clipPath: 'polygon(0 0, 100% 0, 100% 100%, 22% 100%)',
        }}
      >
        <img
          src={dandelions}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover object-[30%_45%]"
        />
      </div>

      <div aria-hidden className="pointer-events-none absolute inset-0 hidden md:block">
        <div
          className="bg-wheat-gold absolute -top-16 right-[30vw] h-[16rem] w-[15rem] mix-blend-multiply"
          style={{ opacity: 0.38, borderRadius: '42% 58% 38% 62% / 55% 40% 60% 45%' }}
        />
        <div className="bg-vg-sky absolute right-[26vw] bottom-8 size-14 rounded-full opacity-90" />
        <div
          className="border-sage absolute -bottom-10 right-[8vw] h-28 w-28 border-2"
          style={{
            opacity: 0.9,
            clipPath: 'polygon(22% 8%, 70% 0%, 100% 42%, 82% 94%, 26% 100%, 0% 58%)',
          }}
        />
      </div>

      <Caption text="dandelions, millet, 1868" className="absolute right-0 bottom-0 hidden md:block" />

      <div className="relative mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="display max-w-2xl text-2xl leading-tight sm:text-3xl">
          The next shift starts from what is still missing.
        </h2>
        <p className="text-ink-soft mt-3 max-w-2xl text-[0.9375rem] leading-relaxed">
          Those three lines become the agenda. You pick one and the team works on
          it, or you set them going and see what they choose. You cap what the
          company may spend, and you can stop it in the middle.
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-5">
          <a href="#top" className="btn btn-primary">
            start a company
          </a>
          <Link to="/companies" className="link font-mono text-[0.8125rem]">
            look at one that already ran
          </Link>
        </div>
      </div>
    </section>
  )
}

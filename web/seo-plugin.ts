import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import type { Plugin } from 'vite'
import { GUIDES, GUIDE_INDEX, SITE, type Guide } from './src/routes/seo.js'
import { PRICING } from './src/routes/specimen.js'

/**
 * Real HTML for every URL, written at build time.
 *
 * The app is a single page that mounts into an empty `<div id="root">`, so
 * before this every address on the site served the same `<title>Werkhaus</title>`
 * and no description at all. Generating routes without fixing that produces
 * pages that exist and cannot be told apart — the worst of both, since a
 * crawler sees fourteen identical documents and concludes exactly that.
 *
 * So each route gets its own file, with its own title, description, canonical
 * and structured data, and with the page's actual words already in the body.
 * React replaces that block when it mounts; anything that does not run
 * JavaScript still has something true to read.
 *
 * Not a general prerenderer. It does not run React — that would mean making
 * every component render without a DOM, for a handful of pages whose content is
 * already a data file. The markup below is a deliberate second copy of the
 * page's opening, kept short precisely so it cannot drift far.
 */

interface Page {
  /** Route path, without a leading or trailing slash. '' is the front page. */
  route: string
  title: string
  description: string
  /** Written into #root so a crawler without JavaScript has the page. */
  body: string
  /** Keep it out of the index — true for anything behind a session. */
  noindex?: boolean
  /** schema.org, already stringified. */
  jsonLd?: object[]
}

const esc = (s: string) =>
  s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

/** The prerendered opening of a guide page, in the page's own classes. */
function guideBody(guide: Guide): string {
  return `<article class="mx-auto max-w-3xl px-5 py-14 sm:px-8 lg:py-20">
<h1 class="display text-[1.85rem] leading-[1.1] sm:text-[2.4rem]">${esc(guide.h1)}</h1>
<p class="text-ink-soft mt-5 max-w-[54ch] text-[1.0625rem] leading-[1.65]">Before you build it, four documents about it: who else is already selling to ${esc(
    guide.audience,
  )}, one price you can defend, a money model with every guess labelled, and where the first customers are.</p>
<h2 class="display mt-12 text-xl leading-tight sm:text-2xl">What it checks first, for this one.</h2>
<ol class="mt-6">${guide.checks
    .map(
      (c) =>
        `<li class="border-rule-soft border-t py-4 text-[1rem] leading-relaxed">${esc(c)}</li>`,
    )
    .join('')}</ol>
<p class="display mt-10 text-[1.25rem] leading-snug">${esc(guide.money)}</p>
</article>`
}

function pages(): Page[] {
  const studio = PRICING.find((t) => t.featured)
  const offers = PRICING.map((tier) => ({
    '@type': 'Offer',
    name: tier.label,
    price: tier.price === null ? '0' : String(tier.price),
    priceCurrency: 'EUR',
    description: tier.pitch,
    ...(tier.price === null
      ? {}
      : {
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: String(tier.price),
            priceCurrency: 'EUR',
            unitCode: 'MON',
          },
        }),
  }))

  const front: Page = {
    route: '',
    title: 'Werkhaus — find out if a business is worth building',
    description:
      'Describe a business. Eight employees spend fourteen minutes on the rivals, one price you can defend and a money model with every guess labelled. From €12 a month.',
    body: `<div class="mx-auto max-w-3xl px-5 py-14"><h1 class="display text-[2.4rem] leading-[1.06]">Describe a business. Find out if it&rsquo;s worth building.</h1><p class="text-ink-soft mt-6 text-[1.0625rem] leading-[1.65]">You leave with a folder of ordinary files. Build it in Lovable, Base44, Cursor, or hand it to a developer.</p></div>`,
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'Werkhaus',
        url: SITE,
        description:
          'Decides whether a business is worth building, and hands over the brief.',
      },
      {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: 'Werkhaus',
        applicationCategory: 'BusinessApplication',
        operatingSystem: 'Web',
        url: SITE,
        offers,
      },
    ],
  }

  const hub: Page = {
    route: GUIDE_INDEX.slug,
    title: GUIDE_INDEX.title,
    description: GUIDE_INDEX.description,
    body: `<div class="mx-auto max-w-5xl px-5 py-14"><h1 class="display text-[2.4rem] leading-[1.1]">${esc(
      GUIDE_INDEX.h1,
    )}</h1><ul class="mt-10">${GUIDES.map(
      (g) =>
        `<li class="py-2"><a class="link" href="/for/${g.slug}/">${esc(g.h1)}</a></li>`,
    ).join('')}</ul></div>`,
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: GUIDE_INDEX.title,
        url: `${SITE}/for/`,
        hasPart: GUIDES.map((g) => ({
          '@type': 'WebPage',
          name: g.title,
          url: `${SITE}/for/${g.slug}/`,
        })),
      },
    ],
  }

  const guides: Page[] = GUIDES.map((guide) => ({
    route: `for/${guide.slug}`,
    title: guide.title,
    description: guide.description,
    body: guideBody(guide),
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: guide.title,
        url: `${SITE}/for/${guide.slug}/`,
        description: guide.description,
        isPartOf: { '@type': 'CollectionPage', url: `${SITE}/for/` },
        about: guide.audience,
      },
      {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Werkhaus', item: SITE },
          {
            '@type': 'ListItem',
            position: 2,
            name: 'What is worth building',
            item: `${SITE}/for/`,
          },
          { '@type': 'ListItem', position: 3, name: guide.h1 },
        ],
      },
    ],
  }))

  // Behind a session and different for every visitor. Given a title so a
  // shared link is not blank, and kept out of the index.
  const companies: Page = {
    route: 'companies',
    title: 'Your companies — Werkhaus',
    description: `Every company you have started, and what each one has filed. From €${studio?.price} a month.`,
    body: '',
    noindex: true,
  }

  return [front, hub, ...guides, companies]
}

/**
 * The address that actually answers 200.
 *
 * Netlify serves a directory index and 301s the slashless form onto it, so a
 * canonical without the slash points at a redirect — which is not wrong, and is
 * one hop of doubt in the one tag whose whole job is removing doubt.
 */
function canonical(route: string): string {
  return route ? `${SITE}/${route}/` : `${SITE}/`
}

function render(shell: string, page: Page): string {
  const url = canonical(page.route)
  const head = [
    `<title>${esc(page.title)}</title>`,
    `<meta name="description" content="${esc(page.description)}" />`,
    `<link rel="canonical" href="${url}" />`,
    page.noindex ? '<meta name="robots" content="noindex,follow" />' : '',
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="Werkhaus" />`,
    `<meta property="og:title" content="${esc(page.title)}" />`,
    `<meta property="og:description" content="${esc(page.description)}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${esc(page.title)}" />`,
    `<meta name="twitter:description" content="${esc(page.description)}" />`,
    ...(page.jsonLd ?? []).map(
      (data) =>
        `<script type="application/ld+json">${JSON.stringify(data).replace(
          /</g,
          '\\u003c',
        )}</script>`,
    ),
  ]
    .filter(Boolean)
    .join('\n    ')

  return shell
    .replace(/<title>[^<]*<\/title>/, head)
    .replace('<div id="root"></div>', `<div id="root">${page.body}</div>`)
}

function sitemap(list: Page[]): string {
  const urls = list
    .filter((p) => !p.noindex)
    .map((p) => {
      const url = canonical(p.route)
      // The front page and the hub are the ones worth recrawling often; a
      // guide changes when somebody edits it, which is rarely.
      const priority = p.route === '' ? '1.0' : p.route === 'for' ? '0.8' : '0.6'
      return `  <url><loc>${url}</loc><priority>${priority}</priority></url>`
    })
    .join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
}

export function seo(): Plugin {
  return {
    name: 'werkhaus-seo',
    apply: 'build',
    async closeBundle() {
      const out = path.resolve(import.meta.dirname, 'dist')
      const shell = await readFile(path.join(out, 'index.html'), 'utf8')
      const list = pages()

      for (const page of list) {
        const html = render(shell, page)
        if (page.route === '') {
          await writeFile(path.join(out, 'index.html'), html)
          continue
        }
        const dir = path.join(out, page.route)
        await mkdir(dir, { recursive: true })
        await writeFile(path.join(dir, 'index.html'), html)
      }

      await writeFile(path.join(out, 'sitemap.xml'), sitemap(list))
      await writeFile(
        path.join(out, 'robots.txt'),
        `User-agent: *\nAllow: /\nDisallow: /c/\nDisallow: /companies\n\nSitemap: ${SITE}/sitemap.xml\n`,
      )

      this.info(`seo: ${list.length} pages, sitemap and robots.txt`)
    },
  }
}

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
  /**
   * The card a link preview shows, under /og/. Rendered from the site's own
   * stylesheet and fonts by `web/scripts/og.md`, so a shared link looks like
   * the page it points at rather than like a stock template.
   */
  image: string
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
    image: '/og/og-default.png',
    body: `<div class="mx-auto max-w-3xl px-5 py-14"><h1 class="display text-[2.4rem] leading-[1.06]">Describe a business. Find out if it&rsquo;s worth building.</h1><p class="text-ink-soft mt-6 text-[1.0625rem] leading-[1.65]">You leave with a folder of ordinary files. Build it in Lovable, Base44, Cursor, or hand it to a developer.</p></div>`,
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'Werkhaus',
        url: SITE,
        description:
          'Decides whether a business is worth building, and hands over the brief.',
        logo: `${SITE}/icon-512.png`,
        sameAs: ['https://github.com/Proto-ventures/Werkhaus'],
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
    image: '/og/og-for.png',
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
    image: `/og/og-${guide.slug}.png`,
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
    image: '/og/og-default.png',
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
    `<meta property="og:image" content="${SITE}${page.image}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta property="og:image:alt" content="${esc(page.title)}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:image" content="${SITE}${page.image}" />`,
    `<meta name="twitter:title" content="${esc(page.title)}" />`,
    `<meta name="twitter:description" content="${esc(page.description)}" />`,
    `<link rel="manifest" href="/site.webmanifest" />`,
    `<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />`,
    // The paper colour, so a browser chrome or an OS launcher does not frame
    // the page in its own default grey.
    `<meta name="theme-color" content="#fbfbfb" media="(prefers-color-scheme: light)" />`,
    `<meta name="theme-color" content="#10141f" media="(prefers-color-scheme: dark)" />`,
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

/**
 * The site, written for something that reads rather than crawls.
 *
 * `llms.txt` is the convention a model or an agent looks for when it wants the
 * shape of a site without parsing the site: a name, a summary, and links with
 * a sentence each. `llms-full.txt` is the same thing with the content inlined,
 * for the case where fetching sixteen pages is not worth it.
 *
 * Both are generated from the same data the pages are, so the version an agent
 * reads and the version a person reads cannot disagree — which is the failure
 * these files usually have, being hand-written once and then forgotten.
 */
function llms(): string {
  const price = PRICING.map(
    (t) =>
      `- **${t.label}** — ${t.price === null ? 'free' : `€${t.price}/month, €${t.year}/year`}. ${t.pitch}`,
  ).join('\n')

  return `# Werkhaus

> Describe a business and find out whether it is worth building. Eight AI
> employees spend about fourteen minutes on the part you cannot vibe code — the
> rivals and what they charge, one price you can defend, a money model with
> every guess labelled, and where the first customers already are — and hand
> back four ordinary markdown files you own.

Werkhaus is upstream of the app builders. It does not build the app: you take
the brief to Lovable, Base44, Cursor or a developer. Every claim in what it
produces carries a mark saying where it came from — \`sourced\` (a page that was
actually opened), \`inferred\` (reasoned from something sourced) or
\`assumption\` (a guess, labelled as one). A critic named Vera runs at the end
of every shift and files objections that name the claim and what would settle it.

## What it will not do

- It is not a builder. It works out what to build; building it is somebody else.
- It does not validate anything. Competitor pricing makes a price defensible; only a customer validates one.
- It is not a launch in an hour, and not a replacement for a co-founder.
- It never contacts customers. Outreach is drafted, never sent.
- Today a shift ends with the documents. The landing-page builder is not shipped yet.

## Pricing

${price}

A shift that filed nothing is not charged. Stopping takes effect in under two
seconds and keeps everything already done. The folder is plain markdown on every
plan, including the free one.

## Pages

- [Werkhaus](${SITE}/): the product, a worked example, the price list.
- [What is worth building](${SITE}/for/): one page per business, each naming what a shift checks first.
${GUIDES.map((g) => `- [${g.title}](${SITE}/for/${g.slug}/): ${g.description}`).join('\n')}
`
}

function llmsFull(): string {
  const guides = GUIDES.map(
    (g) => `## ${g.h1}

${SITE}/for/${g.slug}/

For ${g.audience}.

What a shift opens first for this one:

${g.checks.map((c) => `1. ${c}`).join('\n')}

The number it turns on: ${g.money}

Starting idea: "${g.idea}"
`,
  ).join('\n')

  return `${llms()}
---

# Every page, in full

${guides}`
}

function manifest(): string {
  return JSON.stringify(
    {
      name: 'Werkhaus',
      short_name: 'Werkhaus',
      description:
        'Describe a business. Find out if it is worth building.',
      start_url: '/',
      scope: '/',
      display: 'standalone',
      lang: 'en',
      // The paper and the ink, from index.css. A manifest that disagrees with
      // the stylesheet shows as a flash of the wrong colour on launch.
      background_color: '#fbfbfb',
      theme_color: '#fbfbfb',
      icons: [
        { src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
        { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        // Padded onto paper rather than transparent: a launcher that adds its
        // own background gets the one we chose instead of black.
        { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    null,
    2,
  )
}

/**
 * Crawlers that read for a model, named and allowed on purpose.
 *
 * The default when a site says nothing is that each of these decides for
 * itself, and several read a bare `User-agent: *` as permission anyway. Being
 * explicit is the difference between being quoted correctly by an assistant and
 * being described from a third-party summary — which, for this product, has
 * already happened to our competitors' prices and to us.
 */
const AGENTS = [
  'GPTBot',
  'OAI-SearchBot',
  'ChatGPT-User',
  'ClaudeBot',
  'Claude-User',
  'Claude-SearchBot',
  'anthropic-ai',
  'PerplexityBot',
  'Perplexity-User',
  'Google-Extended',
  'Applebot',
  'Applebot-Extended',
  'CCBot',
  'cohere-ai',
  'meta-externalagent',
  'Amazonbot',
  'Bingbot',
  'DuckDuckBot',
  'YandexBot',
]

function robots(): string {
  const named = AGENTS.map(
    (agent) => `User-agent: ${agent}\nAllow: /\nDisallow: /c/\nDisallow: /companies\n`,
  ).join('\n')
  return `# Werkhaus. Read it, quote it, summarise it — the pages are the product's
# argument and we would rather they were repeated accurately than not at all.
# /c/ and /companies are somebody's private workspace, not content.

User-agent: *
Allow: /
Disallow: /c/
Disallow: /companies

${named}
Sitemap: ${SITE}/sitemap.xml
`
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
      await writeFile(path.join(out, 'robots.txt'), robots())
      await writeFile(path.join(out, 'site.webmanifest'), manifest())
      await writeFile(path.join(out, 'llms.txt'), llms())
      await writeFile(path.join(out, 'llms-full.txt'), llmsFull())

      this.info(
        `seo: ${list.length} pages, sitemap, robots, manifest, llms.txt`,
      )
    },
  }
}

# Regenerating the link-preview cards

`web/public/og/*.png` are rendered from the site's own stylesheet and fonts, so
a shared link looks like the page it points at. They are committed rather than
built, because rendering them needs a browser and a Netlify build should not.

Regenerate when a guide's `h1` changes, or when the type or palette does:

1. `cd web && npm run build`
2. Serve the build: `python3 -m http.server 4199 --directory dist`
3. Start a headless browser with a debugging port:
   `~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome --headless \
      --disable-gpu --hide-scrollbars --remote-debugging-port=9222 about:blank`
4. Write `dist/__og.html` — a 1200x630 card that reads `?t=` (title) and `?s=`
   (the strip under the rule), linking `/assets/index-*.css` for the real fonts.
5. Drive one navigation and one `Page.captureScreenshot` per card over the
   DevTools protocol, writing `web/public/og/og-<slug>.png`.

The card names are fixed by `seo-plugin.ts`: `og-default.png`, `og-for.png`,
and `og-<slug>.png` for each entry in `src/routes/seo.ts`. A missing file is a
broken preview and nothing else — the build does not check, because a build
that needs a browser is a build that breaks on somebody else's machine.

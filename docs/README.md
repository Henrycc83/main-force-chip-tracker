# GitHub Pages dashboard

This directory is a dependency-free static site. GitHub Pages can publish it directly from the repository's `docs/` directory.

## Data contract

The page reads `data/dashboard.json` at runtime with `cache: no-store`. The production pipeline should replace the bundled sample only after independent QA passes. Set `sample_data` to `false` (or omit it) for verified production payloads.

If the payload cannot be loaded or fails the required top-level schema check, the page shows an unavailable state and does not display stale fallback values.

## Local preview

Serve the repository root with any static HTTP server, then open `/docs/`. Opening `index.html` directly from the filesystem may block `fetch()` in the browser.

Run the static checks from the repository root:

```text
npm run test:frontend
```

The checks cover JavaScript syntax, required payload keys, 15+15 rank integrity, star boundaries, the final capital-ratio column, keyboard/reduced-motion hooks, mobile layout hooks, and avoidance of `innerHTML` rendering.

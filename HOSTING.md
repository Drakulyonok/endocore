# Hosting the docs for free (with a free, nice domain)

The docs are a static MkDocs site (`mkdocs build` → `site/`). Any static host
works. Below are free options, each giving you a free subdomain, plus how to get
a nicer free domain.

## Recommended: Read the Docs (free subdomain `*.readthedocs.io`)

Best fit for a Python project. Free for open-source, builds on every push.

1. Push the repo to GitHub (see `RELEASE.md`).
2. Sign in at **https://readthedocs.org** with GitHub.
3. **Import** the `endocore` repo.
4. It reads `mkdocs.yml` automatically. Add `docs/requirements.txt` under
   *Admin → Settings → Requirements file* if needed.
5. Your site is live at **`https://endocore.readthedocs.io`**.

## GitHub Pages (free subdomain `*.github.io`)

Already wired: `.github/workflows/docs.yml` builds and deploys on push to
`main`/`master`.

1. Push to GitHub.
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Site goes live at **`https://<user>.github.io/endocore/`**.
   For a project page, add `site_url` and (optionally) a custom domain.

## Cloudflare Pages (free subdomain `*.pages.dev`)

Fast global CDN, generous free tier.

1. **https://pages.cloudflare.com** → connect your GitHub repo.
2. Build command: `pip install -r docs/requirements.txt && mkdocs build`
3. Output directory: `site`
4. Live at **`https://endocore.pages.dev`**.

Netlify (`*.netlify.app`) and Vercel (`*.vercel.app`) work the same way with the
same build command / output dir.

## Getting a *nicer* free domain

The subdomains above are already fine. If you want a shorter/prettier name for
free:

- **`is-a.dev`** — free `yourname.is-a.dev` subdomain via a PR to their GitHub
  repo. Popular for dev projects. → `endocore.is-a.dev`
- **`js.org`** — free `*.js.org` (accepts non-JS docs projects too, by PR).
  → `endocore.js.org`
- **`eu.org`** — free real domains like `endocore.eu.org` (manual approval,
  slower).
- **`.dev` / `.app` / `.io`** — *paid*, but cheap and professional if you ever
  want a real domain. Point a `CNAME` at your Pages/RTD site.

For any of these: create a `CNAME` DNS record pointing your chosen name at the
host (e.g. `<user>.github.io` or `endocore.pages.dev`), then set the custom
domain in the host's settings and `site_url:` in `mkdocs.yml`.

## Preview locally first

```bash
pip install -r docs/requirements.txt
mkdocs serve            # http://127.0.0.1:8000
```

## Summary

| Host | Free domain | Best for |
|------|-------------|----------|
| Read the Docs | `endocore.readthedocs.io` | Python docs, zero-config |
| GitHub Pages | `<user>.github.io/endocore` | already wired via Actions |
| Cloudflare Pages | `endocore.pages.dev` | fastest CDN |
| + `is-a.dev` / `js.org` | `endocore.is-a.dev` / `endocore.js.org` | a prettier free name |

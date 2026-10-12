# Workforce prototypes

Two work-in-progress prototypes for one workforce tool, published with GitHub Pages:

- **WEAVE** (`weave/`): the Workforce Engagement, Actions & Visibility Environment. This is the home page for the planned web dashboard, with a 3D quilt hero where every block is a dashboard panel. It is in progress.
- **Coalesce** (`coalesce/`): Home and Help pages for the Excel add-in in use today, with a 3D crowd hero. It was imported with its history from the original `coalesce-site` repo.

**Live:** <https://mtibbits.github.io/weave-prototypes/>. Every number on these pages is sample data.

## Layout

```
site/index.html               the front page (links to both prototypes)
coalesce/public/              the Coalesce site, served at /coalesce/
weave/public/                 the WEAVE site, served at /weave/
weave/dev/                    dev-only pages (faces.html); never published
weave/tests/                  WEAVE's tests (pytest + Playwright)
weave/README.md               WEAVE's own preview and test steps
weave/docs/superpowers/       WEAVE design notes
tools/build_site.py           assembles _site/ from the three folders above
tools/serve.py                local preview server with correct MIME types
.github/workflows/pages.yml   publishes _site/ to GitHub Pages on every push to main
```

## Preview locally

```
python tools/build_site.py
python tools/serve.py _site
```

Then open <http://127.0.0.1:8000/>. Opening the HTML files straight from disk won't show the 3D heroes, because browsers block those files from `file://` pages.

## Tests

```
python -m pytest
```

The tests need `pytest`. Coalesce's own tests also need Playwright (see `coalesce/README.md`), and you run them from inside `coalesce/`.

WEAVE's tests also need Playwright, and you run them from inside `weave/`. The steps are in `weave/README.md`.

## Licenses

Three.js (MIT) and the Instrument fonts (SIL Open Font License) are copied into the sites, with their license files next to them.

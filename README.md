# Work prototypes

Work-in-progress prototypes, published with GitHub Pages. The first two are for one workforce tool:

- **WEAVE** (`weave/`): the Workforce Engagement, Actions & Visibility Environment. It has a home page for the planned web dashboard, with a 3D quilt hero where every block is a dashboard panel, and a Help page. It is in progress.
- **Coalesce** (`coalesce/`): Home and Help pages for the Excel add-in in use today, with a 3D crowd hero. It was imported with its history from the original `coalesce-site` repo.
- **blazeAhead** (`blazeahead/`): Home, Help and a torch-lit 3D tour for the blazeAhead VS Code extension. It is a snapshot of the local `blazeahead-site` repo at 07cbacc; its development history stays there.

**Live:** <https://mtibbits.github.io/weave-prototypes/>. Every number on these pages is sample data.

## Layout

```
site/index.html               the front page (links to every prototype)
coalesce/public/              the Coalesce site, served at /coalesce/
blazeahead/public/            the blazeAhead site, served at /blazeahead/
weave/public/                 the WEAVE site, served at /weave/
weave/dev/                    dev-only pages (faces.html); never published
weave/tests/                  WEAVE's tests (pytest + Playwright)
weave/tools/                  verify.py and capture_still.py: WEAVE's budget and state check, and the still capture;
                              fixed_clock.py: the tests' fixed instant
weave/README.md               WEAVE's own preview and test steps
weave/docs/superpowers/       WEAVE design notes
tools/build_site.py           assembles _site/ from the folders above
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

The tests need `pytest`. Coalesce's and blazeAhead's own tests also need Playwright (see each one's README), and you run them from inside `coalesce/` or `blazeahead/`.

WEAVE's tests also need Playwright, and you run them from inside `weave/`. The steps are in `weave/README.md`.

## Licenses

Three.js (MIT) and the Instrument, Fraunces and Figtree fonts (SIL Open Font License) are copied into the sites, with their license files next to them.

# WEAVE hero v0: design

**Date:** 2026-10-09 · **Status:** design approved in chat. The owner waived the usual spec and plan review stops ("go"), so this is the record, not a review draft.

## 1. Summary

WEAVE (**Workforce Engagement, Actions & Visibility Environment**) is the proposed name for the web dashboard that will replace the Coalesce Excel add-in. This repo holds two prototypes side by side on GitHub Pages:

- **WEAVE** (new; this design).
- **Coalesce** (the existing site, imported as is).

The WEAVE hero is a **3D sampler quilt**. Each block is one dashboard panel: its name is embroidered top-left and a fabric icon is sewn on (appliqué). The mapping between quilt and dashboard is exact:

| Quilt | Dashboard |
|---|---|
| block | panel |
| sashing between blocks | gutter between tiles |

Clicking the quilt unstitches it into a dashboard of tiles you can rearrange. The quilt grows with the product: live panels are sewn in, planned ones are pinned in place, and on release morning the new blocks are sewn in once per visitor.

## 2. Goals and non-goals

**Goals**
- A public, viewable work-in-progress the owner can open from work and keep iterating on.
- The page is clearly labeled "Prototype · work in progress".
- Panels are data-driven: one file (`panels.js`) holds the name, icon, fabric, status, release and sample number for each. Adding a panel needs no 3D tooling.
- The same static-only rules as Coalesce:
  - Three.js vendored locally;
  - relative URLs;
  - no server code;
  - a still image wherever live 3D can't run.

**Non-goals for v0**
- Photoreal rendering. A Blender realism pass (cloth drape, a poster render) comes later.
- The frayed-corner Help page. It is next after v0.
- Real data. Every number shown is sample data.

## 3. Repo and hosting

```
weave-prototypes/                 github.com/mtibbits/weave-prototypes (public)
├── index.html                    front page: links to both prototypes
├── .github/workflows/pages.yml   every push to main builds and deploys Pages
├── tools/build_site.py           assembles _site/ (CI and local preview use the same script)
├── tools/serve.py                local preview server (from Coalesce)
├── coalesce/                     the Coalesce repo, imported with history (git subtree)
└── weave/
    ├── public/                   served at /weave/
    ├── dev/                      dev-only review pages (faces.html); never published
    ├── tests/                    pytest + Playwright
    ├── tools/                    verify.py: the budget and hero-state check
    └── docs/superpowers/         this spec and the plan
```

**Published URLs:**
- the front page: `https://mtibbits.github.io/weave-prototypes/`
- the WEAVE prototype: `…/weave/`
- the Coalesce prototype: `…/coalesce/`

**Action versions:** `actions/checkout@v6`, `actions/upload-pages-artifact@v5` and `actions/deploy-pages@v5`. These are the versions the owner's volk fork deploys with.

## 4. The panel list (`weave/public/panels.js`)

```js
window.WEAVE_PANELS = {
  release: { version: '1.1', date: '2026-10-09', label: 'sample release' },
  newsWindowDays: 7,
  panels: [ { id, name, icon, fabric, status: 'live'|'planned'|'suggest', since, sample, blurb }, … ]
};
```

The launch set is a **placeholder guess**, marked as such in the file:

| Status | Panels |
|---|---|
| live since 1.0 | Manpower (the Coalesce patch), Hiring, Training, Awards, Action Tracking |
| new in sample release 1.1 | Travel, Desk Allocation |
| planned | Promotions, Feedback, Oversight, Building Access |
| suggest | one blank block, "Suggest a panel" |

That is 12 blocks in a 4 × 3 grid.

## 5. The quilt

- **Layout** (scene units):
  - block 1.0; sashing 0.14; border 0.14;
  - quilt size 4.70 × 3.56;
  - tile mode: same 4 × 3 grid with a 0.24 gutter.
- **Block face:**
  - drawn at runtime on a 512 px canvas;
  - fabric print (calico, gingham, dots, stripe, chambray, plaid, solid, or "people" for the Coalesce patch);
  - a fine weave overlay;
  - a felt appliqué icon with a drop shadow and blanket stitch;
  - the name embroidered upper-left in Instrument Sans Bold with a satin-stitch hatch (long names wrap to two lines);
  - a quilting stitch inset around the edge.
- **Planned block:**
  - fabric slightly faded, with a chalk outline of the icon and the name in chalk;
  - sits askew (about ±2.5°);
  - 3–4 straight pins (3D) near the corners;
  - no seam stitches.
- **Suggest block:** muslin with a chalk "?" and the words "Suggest a panel".
- **Geometry:**
  - each block is a 40 × 40 segment plane, puffed like a pillow and draped by a fixed fold function in quilt space;
  - a morph target holds the flat version, used for tiles;
  - the sashing plane carries muslin, cornerstones and the binding band;
  - a wooden rod with end caps hangs it, with a soft fake shadow behind.
- **Back of each block:** the dashboard tile face, on a separate plane rotated π. Blocks flip to reveal it. The tile face has:
  - a fabric swatch band;
  - the icon and name;
  - a big sample number, a mini bar chart and an "Open →" cue;
  - a "New" tag when new this release;
  - for planned blocks, a "Coming soon" card with a dashed border.
- **Seam stitches:** instanced 3D thread dashes around every sewn block, revealed progressively ("sewing").
- **Light:** hemisphere light plus a warm key light from the upper left. Material is `MeshPhysicalMaterial` with sheen, which gives the fabric look. Neutral tone mapping.

## 6. Motion

All motion is springs toward per-block targets plus a few scripted timelines.

| Moment | What happens |
|---|---|
| Load (intro) | The sashing and rod fade in. Blocks fly in from scattered spots, staggered. Seam stitches sew in. Planned blocks settle askew and pins drop in. |
| Idle | The quilt sways gently on its rod and tilts slightly toward the pointer. |
| Hover a block | It lifts and grows 3 %. A tooltip shows its name and status. |
| Click the quilt (or the "Unstitch" button) | Stitches pop and pins fly off. Blocks lift, staggered from the click point, then fly to tile slots while flattening and flipping. The sashing, rod and shadow fade. |
| Tiles mode | Drag a tile; the others reflow live; release to snap. |
| "Sew it back" | The reverse, in the visitor's new order. |
| Release morning | Each new block starts pinned. Pins pop, it squares up and its face turns sewn. A needle runs its perimeter as stitches appear. Then a card lists what's new. |

## 7. Release logic (`release.js`, pure)

- Versions compare numerically, dot by dot.
- Outside the news window (release date + `newsWindowDays`), nothing is new, unless forced with `?whatsnew`.
- No stored last-seen version:
  - on the first release ever, nothing is new;
  - otherwise the panels whose `since` equals the current release are new.
- With a stored last-seen version: the panels with `lastSeen < since ≤ current` are new.
- After the sequence runs (or nothing was new), the current version is stored under `weave.lastSeenRelease`.
- All storage access sits in `try/catch`.

## 8. The page

- **Header:** a woven-square mark and the "WEAVE" wordmark, a "Prototype · work in progress" pill, and nav links "What's in it", "Coalesce" and "Source".
- **Hero:**
  - eyebrow: the full acronym;
  - headline: "Every part of your workforce, *woven* together.";
  - lede, then the canvas, with the controls Unstitch / Sew it back and Pause motion;
  - a hint line.
- **"What's sewn in":** "Sewn in" and "Pinned for later" lists, built from `panels.js`, with "New" tags.
- **"Why a quilt?":** three sentences on the mapping, plus "Coalesce lives on as the Manpower patch".
- **Footer:** "Sample data only" and the source link.
- **Type and color:**
  - Instrument Serif and Instrument Sans (OFL), reused from Coalesce;
  - linen page `#F3EEE4`, ink `#1E2422`, teal `#1D5E5B`, terracotta `#C4623A`.

## 9. Fallbacks and accessibility

- Coalesce's `decideMode` serves the still image in these cases:
  - no WebGL;
  - reduced motion;
  - no hover;
  - save-data;
  - a slow frame watchdog.
- The still is a JPEG captured from the live render.
- The panel lists carry the content in plain HTML, so nothing depends on the canvas.
- The controls are real buttons. The canvas gets a descriptive `aria-label`.

## 10. Testing

pytest + Playwright, with Chromium on the GPU, as in Coalesce:
- **Pure logic:** release rules and layout/reorder, imported via `page.evaluate`.
- **Page:**
  - loads with no errors;
  - the live canvas is non-blank;
  - the button and a click toggle modes;
  - a drag reorders;
  - `?whatsnew` shows the card;
  - with WebGL disabled, the still shows;
  - the lists match `panels.js`.
- **Build:** `build_site.py` produces the expected tree.

## 11. Later (not v0)

- The frayed-corner Help page.
- A Blender cloth-drape map and a photoreal poster.
- The acronym on the quilt label.
- The real launch set.
- Embedding the hero in the dashboard's first-load view.

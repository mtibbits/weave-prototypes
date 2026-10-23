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
- The frayed-corner Help page's scene. #17 ships the Help page's shell, with a placeholder still; its frayed-corner
  scene comes in #18 and #19.
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
    ├── tools/                    verify.py and capture_still.py: the budget and state check, and the still capture;
    │                             fixed_clock.py: the tests' fixed instant (#12)
    └── docs/superpowers/         this spec and the plan
```

**Published URLs:**
- the front page: `https://mtibbits.github.io/weave-prototypes/`
- the WEAVE prototype: `…/weave/`
- the WEAVE Help page: `…/weave/help/`
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
- The current version is stored under `weave.lastSeenRelease` when the what's-new card is seen (#15), on any path, or at
  boot when nothing is new, and never before `release.date` (until the window opens nothing is written). The card
  counts as seen once half of it is in the viewport, or when it is closed, so a card below the fold on a phone is not
  used up unseen; a card that could not be built writes nothing. A simulated visit writes `weave.lastSeenRelease.sim`
  instead.
- All storage access sits in `try/catch`.

## 8. The page

- **Header:** a woven-square mark and the "WEAVE" wordmark, a "Prototype · work in progress" pill, and nav links "What's in it", "Help", "Coalesce" and "Source".
- **Hero:**
  - eyebrow: the full acronym;
  - headline: "Every part of your workforce, *woven* together.";
  - lede, then the canvas, with the controls Unstitch / Sew it back and Pause motion;
  - a hint line;
  - the what's-new card (#15), below the hint, in an empty polite live region.
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
- Once live, the scene is torn down and the still restored when the frame watchdog finds it too slow (`too-slow`), a
  module or asset fails to load (`load-failed`), WebGL setup fails (`webgl-failed`) or the context is lost
  (`context-lost`).
- The still is a JPEG captured from the live render by `weave/tools/capture_still.py` (D4: the `home` target; #19 adds
  `help`), at the rest-pose recipe, once the watchdog's 2 s window has elapsed (2.5 s of wall time, a lower bound
  while frames take ≤ 100 ms), at ≤ 250 KB.
- The panel lists carry the content in plain HTML, so nothing depends on the canvas.
- The controls are real buttons. The stage (`role="img"`) carries the descriptive `aria-label`, and the canvas is
  `aria-hidden`.
- The what's-new card (#15) lands in a polite live region (`aria-live="polite"`) that is in the page, empty, from
  load, outside the stage. The card never takes focus and is not modal: Tab moves through it and past it, and
  "Got it" or Escape closes it. The `h1` carries `tabindex="-1"` as a programmatic focus target: when focus was in
  the card at its close, it returns to where it came from, else the toggle, else the `h1`.

### URL and page hooks

These ship on the public page; the tests, the capture tools and the sibling epics use them.
- `?pose=rest` holds the quilt at rest (no sway, the pointer ignored); the loop and the watchdog keep running.
- `?frame=still` shows only the stage, filling the viewport. With `?pose=rest` it is the capture recipe, at
  1600 × 1000 and a device pixel ratio of 1; the recipe also carries `now=` set to the tests' fixed date (#12).
- `?nowatchdog` turns the frame watchdog off; `?watchdogLimitMs=N` sets its limit (an absent key keeps 45).
- `?now=YYYY-MM-DD` (test-only, #12) sets the day the release rules see; an invalid value is ignored with a console
  warning and is never written into the page. `?whatsnew` (test-only) shows the current release's panels as new. A
  visit with `?now=`, `?whatsnew` or `?pose=rest` keeps its lastSeen under `weave.lastSeenRelease.sim`, never the real
  visit's `weave.lastSeenRelease`.
- `stage.__weaveRelease` on the `[data-hero]` element, on both paths, set before the hero starts (#12): `today`,
  `force`, `key`, `lastSeen`, `newIds`, `taggedIds` and `recordSeen()`, the only writer of lastSeen (never before the
  release date). #15 calls it when the card is seen (half of it in the viewport, or closed), on any path, and at boot
  when nothing is new.
- `data-release-state` on the stage (#15), set at boot on both paths, reads the card's state: `none` (nothing is new
  this visit), `pending` (the live path, waiting for the quilt), `card` (the card is showing; if its region is missing
  or it cannot be built, nothing shows and nothing is recorded) or `done` (it was closed). The still path goes straight
  to `card`, and a fallback to the still while `pending` shows the card at once. While #16's sew-in plays the state is
  `sewing` (`pending` -> `sewing` -> `card`); a fallback to the still while `sewing` shows the card at once too.
- `data-new-panels` on the stage (#15) is `newIds` joined with spaces, and empty when there is no card; read the exact
  ids from `__weaveRelease.newIds`.
- On the live path the card shows on the first `weave:mode` whose `mode` is `quilt` (the intro's or the sew-in's end,
  a skip, or at once at `?pose=rest`), from the module's own listener, never by polling `__weave.mode`.
- `stage.__weave` on the `[data-hero]` element: `mode`, `order`, `slots`, `clock`, `stop(reason)` and `snapshot()`
  (the scene's world-space geometry as JSON-safe arrays). `order` and `slots` list the slots, so they follow a
  drag (#9). `lastDt`, `project([x, y, z])`, `fades()` (each faded part's `{ opacity, visible }`: the sashing, rod,
  shadow and fillers), `blockBase(id)` (a block's local base positions and normals, before its tilt, with its slot
  and tilt) and `pick(clientX, clientY)` (what a press there would hit) are test-only. #10 adds the per-block calls
  E2's #16 drives, `revealStitches(id, { animate })`, `popStitches`, `popPins`, `restorePins` and `setFace(id, kind)`
  (scene.js holds their contract; `snapshot()` lists the drawn `pins` and `stitches` and the `stitchDash` frame,
  and its blocks include any hover lift or sew-in puff, so a reader that needs seated seams keeps the pointer off the
  blocks), and the test-only `decorIdle`, `hover` (`{ id, amount }`), `groupMatrix()` and `pickBlock(clientX,
  clientY)`. #16 adds the test-only `sewCurve(id)` (a block's perimeter curve, built fresh: `{ at, vertexU, stitchU }`,
  161 points from the top left, clockwise, `NEEDLE_LIFT` above the cloth), `sewLook(id)` (`{ puff, emissive, needle,
  tilt }`), `revealStitchesTo(id, u)` (the dashes up to `u` along that curve) and `sewCalls` (each sew-in once-call's
  count by `'<name> <id>'`, and `reseam`).
- Each `__weave.slots` entry is `{ id, name, status, face, tagged }`. `tagged` (#14) is what the scene asked the tile
  painter for; the painter draws the "New" label on live tiles only.
- `__weave.mode` is the director's state: `intro` (#10), `sewing` (#16), `quilt`, `unstitching`, `tiles` or
  `restitching` (#8). A plain load starts in `intro`, which flies the blocks in and settles into `sewing` when a drawn
  block is new for this visit (in the release's news window, or forced by `?whatsnew`; never at `?pose=rest`), and
  into `quilt` otherwise; `sewing` settles into `quilt`. `?pose=rest` starts in `quilt`. After a fallback it keeps the
  value it had at the teardown, which may be `sewing`, `unstitching` or `restitching`; on the still path the signal is
  that `data-mode` is absent.
- `data-mode` on the stage reads `quilt` or `tiles`. It is set on the live path only: it reads `quilt` from the
  first entry (the intro's) and does not change in `sewing`, then flips when a transition settles (never on an unpaused
  press; a paused press settles at once), and is removed when a fallback restores the still.
- `weave:mode` is an event on the stage with `detail: { mode, from }`, dispatched every time the director enters a
  state, its first state included (`from: null`), from its single state-change path (D39). When it fires,
  `__weave.mode` already reads the new state and, on a settle, `data-mode` has already flipped. A handler that
  toggles synchronously starts the next transition inside the dispatch, so listeners after it read that newer
  state (verify.py's window does this on `tiles`); after a teardown nothing is written and no `weave:mode` fires.
- The Help page, `/weave/help/` (`weave/public/help/index.html`, #17). Its `[data-hero]` stage (`role="img"`) holds
  only the still and is #18's mount point; controls go beside the stage, inside `.hero-figure`, never inside it.
  Its card links and team name come from `window.WEAVE_SITE = { teamName, links: { serviceDesk, tutorial, docs } }`,
  set by `site-config.js`; `js/config.js` exports `safeUrl`, `resolveConfig`, `applyConfig`, `boot`, `MISSING_LABEL`
  and `DEFAULT_TEAM`.

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
- **The clock:** every context the shared fixture makes is pinned to `FIXED_INSTANT`, so no test depends on the
  calendar. The pin also swaps the page's frame loop and timers for Playwright's fake timers, so frame pacing is
  measured only by `verify.py`. `make_page(clock=...)` and `WEAVE_TEST_CLOCK` are the overrides (README, "The fixed
  test clock").
- **Budgets and states:** `verify.py` checks every budget row and every hero state with a screenshot; `--base URL`
  checks the states only, against a deployed copy.

## 11. Later (not v0)

- The Help page's frayed-corner scene (#18, #19); #17 ships its shell.
- A Blender cloth-drape map and a photoreal poster.
- The acronym on the quilt label.
- The real launch set.
- Embedding the hero in the dashboard's first-load view.

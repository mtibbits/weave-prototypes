# The knowledge-base trail map: design

- **Status:** approved in conversation on 2026-09-25; this spec is awaiting the owner's review.
- **Extends:** [2026-09-25-blazeahead-site-design.md](2026-09-25-blazeahead-site-design.md), stop 3 (the knowledge base). Where the two disagree, this spec wins for stop 3.
- **Mockups:** `.superpowers/brainstorm/kb-map/layout.html` (gitignored). The owner chose option C.

## 1. Summary

The kiosk at stop 3 gets a real trail map of the knowledge base: about 20 destinations on five coloured trails. Each trail is a hub with its own blaze. Some destinations are second level (Language specific → Java) and some are third level (Java → Artifactory).

The tour card steps through an overview and then one trail at a time. The current trail lights up on the kiosk map, and the card lists that trail's destinations as links. An **Unfold the map** button, or a click on the kiosk map, opens the whole map as a large sheet in which every linked destination can be clicked.

A single browser module draws the map. The same drawing appears on the live 3D kiosk, over the fallback still image, and on the unfolded sheet. The owner edits the tree in `public/tour-content.js`, and the change shows up everywhere on the next page load, with no Blender rebuild or still re-render.

## 2. Decisions on record

| Question | Decision |
|---|---|
| What can visitors do with the map? | **Both** read it and click through. The card steps through the trails and lights each one up; destinations link out once they have a URL. |
| Layout | **Option C:** the camera is unchanged; the card does the reading; plus an unfold-the-map dialog. |
| Destination list | **The draft tree** (section 3.2) ships as starting copy. The owner refines it later in `tour-content.js`. |
| How the map is made | **Drawn by the page** (approach 1). Blender leaves the board blank. |
| Where links live | Beside each destination's name in `tour-content.js`, not in `site-config.js`. About 21 name/link pairs are easier to keep right side by side. |
| The old knowledge `cards` | Replaced by the trail pages. They were placeholder text. |

## 3. Content

### 3.1 Format

The knowledge stop in `window.BLAZEAHEAD_TOUR.stops[2]` gains a `map`, and its `cards` field goes away:

```js
map: {
  centre: 'blazeAhead',
  trails: [
    { name: 'Language specific', destinations: [
      { name: 'Java', url: '', next: [{ name: 'Artifactory', url: 'https://…' }] },
      { name: 'C++', url: '', next: [{ name: 'SonarQube', url: '' }] },
    ] },
  ],
},
```

- **Colours.** Each trail's colour comes from a fixed palette, in the trail's order: blue `#2F6FA3`, red `#B8452A`, green `#3E7D4C`, purple `#74509C`, ochre `#A0721A`.
- **Links.** A `url` becomes a link only when it starts with `https://` or `http://`. Anything else, such as an empty string, `javascript:` or a typo, is shown as a plain label.
- **Normalising** (in `content.js`, beside the existing tour normalising):
  - Names are trimmed.
  - Destinations and trails without a name are dropped.
  - Only the first 5 trails, the first 5 destinations on a trail, the first 2 `next` stops per destination, and 25 stops in all are kept. Every named stop counts toward the 25, third-level ones included; the draft tree has 21. `next` inside `next` is ignored. (The prototype showed six trails, or more than about 25 stops, no longer lay out cleanly.)
  - Anything left out is reported in one `console.warn`: items past the limits, unnamed items (or ones that aren't objects), and a trail left with no destinations.
- **Fallback.** A missing or unusable `map` (not an object, or no trail with a destination) falls back to the draft tree in `DEFAULT_TOUR`, as the rest of the file already does. When the owner did supply a `map` but it can't be used, a `console.warn` says the shipped map is shown instead.
- **Long names.** On the map, any name longer than 32 characters (a stop, a trail's hub or the centre) is cut short with an ellipsis, and the pills are sized for the cut name. The card and the sheet's link titles show it in full, and on the unfolded map a cut stop name shows in full as a tooltip (an SVG `<title>`).

### 3.2 The draft tree (shipped)

| Trail | Destinations (› marks a third-level stop) |
|---|---|
| Getting connected | Proxy · GitLab · Certificates · Access tokens |
| Agentic workflow | devAgent · Jira · Claude skills · Claude plugins |
| Language specific | Java › Artifactory · C++ › SonarQube · Python › PyPI mirror |
| Infrastructure | Deployment › AWS account · Terraform · Kubernetes |
| Corporate knowledge | Confluence · Onboarding · Security & policy |

That is 21 destinations. All URLs ship empty, so every name starts as a plain label.

## 4. The experience

### 4.1 The card at stop 3

- The card has *trails + 1* pages, stepped with the existing ‹ › pager (`data-card-prev`, `data-card-next`, `data-card-count`).
- The title and paragraphs sit above the page content on every page, as today.
- **Page 1 (overview):** the trails as coloured chips (each a blaze and a name).
- **Pages 2 and on (one trail each):**
  - a panel edged in the trail's colour, headed by its blaze and name;
  - its destinations in two columns, e.g. "Java › Artifactory";
  - linked names are `<a target="_blank" rel="noopener noreferrer">`; unlinked names are muted text.
  - **Short windows** (820 px tall or less, such as a 1080p laptop at 125 %): the card is tighter, and the trail's name sits beside its destinations, which flow in rows instead of two columns. The lower trails, lit on the kiosk, then stay clear of the card, and the card doesn't scroll.
- **Unfold button.** On every page of stop 3, the card's footer shows an **Unfold the map** button in place of the "Use the signposts" hint. The pager stays on the right.
- Arriving at the stop starts on page 1, since `cardIndex` already resets on arrival.
- The ← → keys and the signposts still move between stops.

### 4.2 The lit trail

- Showing trail page *k* lights trail *k* on the kiosk map. The other trails, their destinations and their lines fade to 26 % opacity, and the lit trail gets a soft glow in its own colour.
- The overview page, and leaving the stop, return the map to "no trail lit".
- The live kiosk and the still overlay behave the same way.

### 4.3 The unfolded map

- **The dialog.** A `<dialog data-kb-sheet>` in `tour/index.html`, opened with `showModal()`. It holds a header (the title "Knowledge base trail map" and a Close button) and the map drawn with links.
- **Links.** Linked destinations are SVG `<a>` elements with `href`, `target="_blank"` and `rel="noopener noreferrer"`, focusable with Tab and showing a visible focus ring. Each has an accessible name.
- **Opening.** The Unfold button opens it, and so does clicking the kiosk map: the live board when stopped at stop 3, or the still overlay. It opens only while standing at stop 3, never during a walk.
- **Closing.**
  - Escape or Close shuts it. Focus returns to the Unfold button when that opened it; after a click on the kiosk map, it goes to the card heading.
  - While it is open, the page's own key handler does nothing. Today Escape leaves the tour, and ← → walk; neither may happen with the dialog open.
- **Size.** The sheet is up to 1300 px wide and 92 vh tall. The map keeps its shape and fills the height left under the header, up to the sheet's width, centred. It keeps a minimum width of 960 px, so the words never shrink past legibility. Where even that is too tall or too wide, only the map area scrolls: the header and Close button stay in view.
- **When there's no map.** The dialog is only reachable at stop 3.

## 5. The drawing: `public/js/kbmap.js`

A pure module with no DOM dependencies beyond the painter it is handed.

### 5.1 Layout

```
layoutMap(map, measure) → { scale, crowded, clashes, centre, here,
  trails: [{ name, color, x, y, w, h, size, destinations: [...] }], boxes }
```

It places everything on a board **1380 × 880 units**: the real board's millimetres. `measure(text, font)` returns a width, and in the browser it is canvas `measureText`.

- **Centre.** An amber pill with the `centre` name at (0.5, 0.517) of the board. A red "you are here" pin and its italic label sit centred just below it.
- **Hubs.** Each trail is a pill in its colour, with a white blaze mark at its left end. Hubs go into fixed slots for the trail count, taken in order.

  | Trails | Slots (fractions of the board) |
  |---|---|
  | 5 | top (0.50, 0.29); upper-left (0.27, 0.34); upper-right (0.73, 0.34); lower-right (0.73, 0.73); lower-left (0.27, 0.73) |
  | 4 | upper-left, upper-right, lower-right, lower-left (as for 5) |
  | 1–3 | the first 1–3 slots for 5 |

- **Destinations.** Each hub's destinations fan out in a fixed direction per slot: top 270°, upper-left 205°, upper-right 335°, lower-right 25°, lower-left 155° (screen degrees, y down). They are spaced evenly across min(130°, 40° × (n − 1)), 115 units beyond the pill's edge. With five destinations, every other one stands 55 units further out. A dot is kept far enough in that its label fits centred above or below it.
- **Third-level stops.** They go 130 units beyond their destination, straight on if there's room. Otherwise they bend 30°, 60° or 90° either way, until the dot is on the board, the label fits on a side that doesn't face back along the spur, and the spur crosses no other line. They are drawn smaller, on dashed spurs.
- **Labels.** Each label goes in one of eight places around its dot: above, below, left, right, or a diagonal. It takes the place that best faces away from its incoming line, scoring:
  - overlaps with any pill, dot or earlier label (with a 7-unit gap), or running off the board: 100 each;
  - crossing its own line: 40;
  - crossing any other line: 4.

  Every label sits on a small paper-coloured backing, so a line running under it is hidden rather than struck through. (On the still overlay the backing is white, since it is multiplied.)
- **Fit pass.** While any label clashes, the layout tries again at the same size up to six times. Each time, every clashing destination steps out 45 units (twice at most), and every clashing third-level stop takes its next bend. Only then does all the lettering shrink by 5 %, down to 60 %. A pill (a hub or the centre) that runs off the board's margin, or touches another pill (their rims meet), clashes too; moving stops can't clear that, so the lettering shrinks straight away. Starting sizes: hub 26, destination 27, third-level 25, centre 30 (units). The result reports the final `scale`, and `crowded` if clashes remain at 60 %. The page then logs a warning.

### 5.2 Painting

```
drawMap(painter, laid, { focus = null, links = false, paper = true })
```

- **Painters.** Two implement the same six primitives: line (optionally dashed), circle, rounded rectangle, text, a link group, and a titled group (the tooltip for a cut name; the canvas ignores it).
  - `svgPainter(document)` returns an `<svg viewBox="0 0 1380 880">`.
  - `canvasPainter(ctx, scale)` draws on a 2D canvas.
- **Glow.** SVG uses an `feDropShadow` filter; the canvas uses `shadowBlur` and `shadowColor`.
- **Paper.** `paper` fills the board `#DCCDA6`, the Blender paper's albedo, so the live board and the still match. The still overlay passes `paper: false`, so it can multiply onto the still's own lit paper.
- **Fonts.** Fraunces (names) and Figtree (hub pills). The caller waits for `document.fonts.load` of both before measuring or painting. If the fonts fail, it measures and paints with whatever font rendered, so the fit still holds.

## 6. Where the drawing goes

### 6.1 The live 3D kiosk

- **Build export.** The layout module exports `props.kiosk.board` in `world.json`:
  - `centre`, unit `right` and `up` vectors, and `size: [1.38, 0.88]`;
  - `light`: a 9 × 6 grid of linear RGB tints, sampled with `light_at` over the board. This is light only, since the texture carries the albedo.
- **The panel.** `world.js` builds a plane 3 mm in front of the Blender paper, split 8 × 5 so each vertex takes a tint from the grid. Its material is `MeshBasicMaterial({ map, vertexColors: true, fog: true })`.
- **The texture.** A `CanvasTexture` (sRGB, mipmapped, the renderer's maximum anisotropy) on a 2048 × 1306 canvas.
- **Stage API.** `stage-live.js` adds `api.paintMap(laid, focus)`, which redraws the canvas and flags the texture for upload. Both are skipped when the board already shows that layout with that trail lit.
- **Clicks.** When stopped at stop 3, hovering over the panel shows a pointer cursor, and a click opens the sheet. The panel is found by raycasting.
- **Failure.** If the panel can't be made, the board stays blank paper. The panel's canvas starts as blank paper too, so a paint that fails leaves paper, not black. The card's links and the sheet still work, and the page logs a `console.warn`.

### 6.2 The still image

- **Build export.** The layout module writes the board's four corners, projected into the knowledge still, to `still-signs.json`:

  ```json
  "knowledge": { "left": […], "right": […], "board": [[x, y], [x, y], [x, y], [x, y]] }
  ```

  The corners are fractions of the image, clockwise from top-left.
- **The overlay.** `tour.js` keeps a container sized 1380 × 880 CSS px holding the SVG (`paper: false`).
  - It is placed with a CSS `matrix3d` homography that maps the container's corners onto the board corners in page pixels. These come from the still `<img>` rect, the same way `placeSigns` places the sign buttons.
  - It uses `mix-blend-mode: multiply`, so the still's lantern light shows through.
- **When it shows.** Only at stop 3, only when not walking, and only while the page shows the still image rather than the live canvas (before 3D arrives, without 3D, with reduced motion, or after the live stage stops). It is re-placed on resize, and a click on it opens the sheet.
- **The still itself.** Blender renders the board as blank paper, so the knowledge still is re-rendered once.

### 6.3 The sheet

The same drawing via `svgPainter` with `links: true`, `paper: true`.

## 7. Blender and build changes

- **`build_blazeahead.py`, `build_kiosk`:**
  - The `KioskMap` part keeps only the paper board. It keeps the mesh name `KioskMap`, which `world.js` requires.
  - The hardcoded nodes, lines, map labels and pinned notes are removed.
- **`blazeahead_layout.py`:** exports the board frame and light grid (6.1) and the still corners (6.2).
- **Regenerated assets:** `blazeahead.glb`, `world.json`, `still-signs.json`, and `stills/knowledge.webp` (`--stills --only knowledge`, about 7 min).
- **`tour.js`:** the stage description for stop 3 becomes: "A trail kiosk headed Knowledge Base, with a map of coloured trails leading from blazeAhead to the company's tools."

## 8. Testing and verification

These follow the repo's pytest + Playwright style.

- **Content** (`test_content.py`):
  - the draft tree is used when `map` is missing or unusable;
  - the limits hold (5 trails, 5 destinations on a trail, 2 `next`, 25 stops in all, no fourth level);
  - bad URLs become plain labels;
  - empty names are dropped;
  - long names are cut on the map only.
- **Layout** (`test_kbmap.py`, new):
  - For the draft tree: every label lies within the board margin, no two boxes overlap, and `scale` ≥ 0.85.
  - For 20 stops with a spur on every trail, 25 stops with five on every trail, four trails, and a single stop: no overlaps, everything within the margin, and `scale` ≥ 0.85, 0.6, 0.6 and 0.9 respectively.
  - `focus` fades only the other trails.
  - The SVG painter links only when asked and keeps names as text; the canvas painter paints the paper and the pills in their colours; `quadMatrix3d` lands the board's corners exactly.
- **Card and state** (`test_tour_state.py`, `test_tour_live.py`):
  - stop 3 has 6 pages;
  - each trail page links to its URLs, and unlinked names are not `<a>`;
  - paging repaints the live board, and the live texture redraw count goes up;
  - arriving resets to page 1.
- **Dialog:**
  - it opens from the button and from clicking the live board;
  - Escape closes it without leaving the tour, and focus returns;
  - ← → don't walk while it is open;
  - links have `target=_blank` and `rel` containing `noopener`.
- **Still overlay** (reduced-motion context, at 1440 × 900 and 1024 × 768): the overlay's projected corners lie within 4 px of the board corners from `still-signs.json`.
- **Build** (`test_layout.py`):
  - the board export and light grid are present and sane;
  - the still corners lie inside the image;
  - `test_each_stops_prop_sits_above_the_tour_card` still passes.
- **Screenshots** (`tools/verify.py`):
  - new shots of a lit trail (live), the still overlay (reduced motion), and the open sheet;
  - existing budgets still hold. `kbmap.js` adds about 21 KB to the tour page.

## 9. Files

- **New:**
  - `public/js/kbmap.js`
  - `tests/test_kbmap.py`
  - this spec
- **Changed:**
  - `public/tour-content.js`: the `map`, with comments explaining the format
  - `public/js/content.js`: map normalising and card pages; `cards` removed
  - `public/js/tour-state.js`: page count
  - `public/js/tour.js`: pages, lit trail, still overlay, sheet, key guard
  - `public/js/stage-live.js`: `paintMap`, board clicks
  - `public/js/world.js`: the board panel
  - `public/tour/index.html`: the dialog and the overlay container
  - `public/css/site.css`: trail panel, chips, sheet, overlay
  - `blender/build_blazeahead.py`
  - `blender/blazeahead_layout.py`
  - `tools/verify.py`
  - `README.md`: an owner note on editing the map
  - the main spec: a pointer from stop 3 to this spec
  - existing tests as listed in section 8
- **Regenerated:** the assets listed in section 7, and `dist/blazeahead-site.zip`.

## 10. Risks

- **Layout quality on owner-edited trees.** Mitigations: the fit pass, the limits, and the worst-case test. The draft tree must look at least as clean as the mockup; the verify screenshots are checked by eye.
- **Fonts arriving late.** Nothing is measured or drawn until the fonts have loaded (`loadMapFonts`), so there is no fallback paint to lay out again. If they fail to load, the map is laid out and drawn once with the font that did render.
- **Still-overlay alignment across window shapes.** The still is always shown at 16:9 (`site.css`), so fractions of its rect are exact. Tested at two sizes.
- **The page's global key handler.** Guarded while the dialog is open (section 4.3), with tests.

## 11. Out of scope

- Descriptions or tooltips per destination.
- Searching the map.
- Opening the map from other stops.
- Product logos (they stay out, as in the main spec).
- Owner-chosen trail colours.

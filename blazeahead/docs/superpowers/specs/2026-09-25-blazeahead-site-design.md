# blazeAhead project site: design

**Date:** 2026-09-25 · **Status:** approved to build (the owner gave explicit approval on 2026-09-24/25). Items marked **DEFAULT** are my assumptions, which the owner hasn't confirmed; each one is listed again in §12.

**References**
- Concept canvas (private): <https://claude.ai/artifact/R2JWkUmA5Z8Xr2SqCT1gty>. It holds concepts A (Torchlight), B (Trailhead) and the Help junction. **The owner chose B.**
- Sister project: `C:\Programs\src\coalesce-site`. This site reuses its proven pipeline: Blender authors the pieces, Three.js runs them live, everything is static, and still images serve as fallbacks.

## 1. Summary

blazeAhead is a VS Code extension for working with Claude Code on the corporate network. The site replaces today's tall page of about 12 stacked slides with three pages:

- **Home:** "Download blazeAhead", a live 3D trailhead (a log signpost and a torch at the mouth of a forest path) and a **Take the tour** button.
- **Tour:** the camera walks the user down the winding, torch-lit path. It stops at four places, one for each feature:
  1. the continuity proxy (a **stream**);
  2. environment scaffolding (a **base camp**);
  3. the knowledge base (a **map board**);
  4. the In Flight queue (a **launch clearing**).

  At every stop, a signpost on the left edge names the previous topic and a signpost on the right edge names the next one. Clicking either one animates the walk.
- **Help:** a trail junction whose three-armed signpost points to the ways to get help.

The metaphor: the corporate network is an overgrown forest, and blazeAhead lights the trail. "Blaze" means both a trail mark and fire. The Emerson-attributed "leave a trail" quote belongs to the extension's identity (§12).

## 2. Goals and non-goals

**Goals**
- A memorable home that builds brand recognition. Its hero is the torch, whose flame carries a blue crystal, echoing the extension's flame icon.
- A guided tour that explains the four features better than a slide stack does.
- Zero runtime dependencies, as with Coalesce: plain HTML, CSS and JS served by GitLab Pages, with no build step, no server code and nothing loaded from the internet.
- Easy upkeep. Links and version live in one settings file (`site-config.js`), and all tour copy lives in one content file (`tour-content.js`).
- Graceful fallback. Wherever live 3D can't or shouldn't run (no WebGL, VDI, reduced motion, a slow GPU), the same pages work with still images.

**Non-goals**
- Phones and tablets. The owner said the site won't be used on phones. Layouts must not break at small widths, but no phone-specific design is done.
- Writing the knowledge-base articles or the real stop copy. The site ships the owner's descriptions as draft copy in `tour-content.js`.
- Analytics, logins and live data.
- Changing the extension's activity-bar icon.

## 3. Decisions on record

| Topic | Decision |
|---|---|
| Hosting | Internal GitLab Pages, publishing `public/` as-is, like Coalesce. All URLs are relative, because a project's Pages site lives under a sub-path. |
| Devices | Desktop Chromium browsers (Edge/Chrome). No phone design. |
| Look | **DEFAULT (free rein):** a night-forest palette. Ink `#0C171B`, panel `#13232A`, line `#28404A`, text `#EEE7D8`, muted `#A9B8B5`, torch amber `#FFB23F`, crystal blue `#4AA8FF` (used sparingly). Fraunces for display and Figtree for body (both SIL OFL, vendored). One dark theme by design. |
| 3D style | Stylized low-poly with a flat-shaded forest, fog for depth and emissive glow. The flame is **stylized** ("SVG-ish", like the icon), not realistic fire, and it is animated so it looks alive. Fire only ever appears in a torch, never loose in the forest. |
| Motion | The home scene idles: the flame breathes, lights flow down the path, and the brush parts around the pointer. The tour walks between stops in about 3–4 s. When the user has turned on reduced motion, still images cross-fade instead. |
| 3D pipeline | Blender 5.2 LTS authors the meshes, the layout and the still images (Cycles). Three.js 0.170.0 (MIT, vendored) renders and animates in the browser. |
| Download | **DEFAULT:** a `.vsix` on GitLab releases, using the same release-permalink scheme and publish script as Coalesce. The home page carries "Install from VSIX" steps. |
| Help page | **DEFAULT:** the three arrows point to Issues (Jira), Docs (Confluence) and back to the Tour. |
| Old slide page | **DEFAULT:** retired. Its content moves into the four stops. |
| Third-party code | Three.js (MIT) plus the Fraunces and Figtree fonts (OFL), each shipped with its license. Nothing is copied from Blizzard or from the coworker's icon: the flame and crystal are our own design. |

## 4. The experience

### 4.1 Shared chrome
- **Header:** the brand mark (our flame with a blue diamond) and the "blazeAhead" wordmark, linking home. Nav: Tour · Docs · Releases · Help. A **Download blazeAhead** button.
- **Footer:** "blazeAhead · maintained by [TEAM NAME]" · GitLab project · Report an issue.
- Links resolve from `site-config.js`, as in Coalesce. An empty link stays in place, becomes plain text and reads "Link coming soon".

### 4.2 Home (`index.html`)
1. **Hero:** a wide stage, about 16:9 and capped near 76 vh, showing the trailhead.
   - The camera looks down the path with the log signpost (6-inch log, 3 ft tall, 1×6×18 arrow board) on the path's left and the torch on its right.
   - The left ~40% of the frame is dark forest, and the headline sits there.
   - The signpost's board reads "The tour", and clicking the board also starts the tour.
   - Copy:
     - Headline: "Find the trail. *Keep it lit.*"
     - Lede: "blazeAhead is a VS Code extension for Claude Code on our network. It keeps your sessions flowing through busy services, sets up your keys for Jira, Confluence, GitLab and Artifactory, maps where things live, and runs your Jira queue through devAgent."
     - Buttons: **Download blazeAhead** (primary) and **Take the tour** (secondary, to `tour/`).
     - Release line: "Version [VERSION], [DATE] · Release notes".
   - A "Pause motion" toggle sits top-right on the stage when the scene is live.
2. **Install in three steps:**
   1. **Download** `blazeAhead.vsix`.
   2. **Install it in VS Code:** Extensions view (Ctrl+Shift+X) → the **…** menu → **Install from VSIX…** → pick the file. Terminal alternative: `code --install-extension blazeAhead.vsix`.
   3. **Reload** when VS Code asks. The flame appears in the activity bar.

   Note: "Updating? Install the new .vsix the same way; it replaces the old version."
3. **Project home cards:**
   - **Take the tour:** "Walk the trail: four stops, two minutes."
   - **Docs:** usage docs.
   - **Release notes:** the GitLab releases page.
   - **Help:** the Help page.

### 4.3 Tour (`tour/index.html`)
- A full-viewport scene under a slim top bar. The bar holds the brand (links home), an "Exit tour" link and the Download button.
- **Stops:** Trailhead → Continuity → Scaffolding → Knowledge → In Flight → (Download). Each stop has a hash: `#continuity`, `#scaffolding`, `#knowledge`, `#in-flight`. Deep links work, and so do the browser's Back and Forward buttons.
- **Arrival on the page:**
  - With no hash, the page shows the trailhead view, then walks to stop 1 by itself. This is the "we go with you down the path" moment.
  - With a hash, the page opens at that stop.
- **At a stop:**
  - **Left-edge signpost:** names the previous topic and points back. At stop 1 it reads **Trailhead** and goes to the home page.
  - **Right-edge signpost:** names the next topic and points on. At stop 4 it reads **Download** and goes to `../#install`.
  - Both signposts are real 3D boards. A transparent `<button>` sits over each one, labelled for example "Back: Trailhead" or "Next: Scaffolding", so keyboard and screen-reader users can use them.
  - **Card:** an HTML panel at the bottom centre, at most about 620 px wide. It shows an eyebrow ("Stop 2 of 4"), the title, 1–3 short paragraphs, optional bullet points and, for Knowledge, a pager ("Card 1 of N" with ‹ ›).
  - **Trail map:** a small horizontal line of six markers (Trailhead, the four stops, Download). The current stop is lit, and the markers are buttons.
- **Keyboard:** → next, ← back, Esc to the home page. Focus moves to the new card's heading on arrival.
- **Walking (live):**
  - The camera leaves the stop view, steps onto the path, follows it at eye height past the torches, then steps off and turns to face the next vignette.
  - The UI hides and the buttons are disabled while walking.
  - The pace is an unhurried stroll: about 2.9 m/s on average, clamped to 4–12 s, so a leg between stops (about 27 m) takes about 9.5 s. The camera eases in, glides at a steady speed and eases out, never faster than about 1.4× its average. (Owner feedback, 2026-09-25: the first cut, 7 m/s with a cubic ease that surged to 3× mid-walk, felt like running through the forest. The second, 3.4 m/s, was still a smidge fast.)
  - Turns are slow and separate from the walk. The camera turns from the stop's view to face down the path as it sets off, and turns to the next stop's view as it arrives. Each turn goes at about 20°/s on average, taking at most half the walk. A right-angle turn therefore takes about 4.5 s and peaks near 30°/s; with the path's bends added, the legs peak at 39–44°/s. In between, the camera looks at the average of the path's points 5–20 m ahead, so it doesn't sway with every bend. `TURN_RATE` in `rig.js` tunes the turns. (Owner feedback, 2026-09-25: turns were fast. The look target used to follow the path's points, so the camera swung the right angle within the last few metres of a leg, at 140–340°/s.) The one exception is walking back to the trailhead, a near U-turn, which peaks at about 54°/s.
  - A request made mid-walk is queued: only the latest destination counts.
- **Walking (still or reduced motion):** a 400 ms cross-fade between still images, or an instant switch when the user has turned on reduced motion.
- **Stop scenes:**

  | Stop | Scene | Details |
  |---|---|---|
  | 1 | **The stream** | A brook runs behind the path. Rocks stand for the errors (429, 503, SSE glitch, stream error, timeout). The lights ride the current and swirl around the rocks, so nothing stops. Hovering a rock shows a tooltip such as "429 Too Many Requests · absorbed". |
  | 2 | **Base camp** | A tent glowing from inside, a gear crate, a lantern pole, and a key rack with four brass keys tagged Jira, Confluence, GitLab and Artifactory. |
  | 3 | **The map board** | A trail kiosk headed "KNOWLEDGE BASE". Its board carries the knowledge-base trail map (see [2026-09-25-kb-trail-map-design.md](2026-09-25-kb-trail-map-design.md)), lit by two lanterns. |
  | 4 | **The launch clearing** | The canopy opens to stars. An "IN FLIGHT" board holds issue tags, and lights lift off it, climb over the trees and head on down the trail. Two torches flank the board. |

### 4.4 Help (`help/index.html`)
1. **Hero:** the junction. A signpost carries three arrow boards, **Issues**, **Docs** and **Tour** (DEFAULT), with a torch and lights running down three branching paths. It is live, with idle motion and hover, or a still.
2. **Copy:** eyebrow "HELP", headline "Which way *from here?*" and lede "Lost on the trail? Report an issue, look it up in the docs, or take the tour."
3. **Three cards:** each carries an arrow glyph matching its board.
   - **Issues:** "Report a problem or ask for a change. Tickets go to [TEAM NAME] in Jira." → Open an issue
   - **Docs:** "How each feature works, and where our customized GitLab, Confluence and Jira pages live." → Read the docs
   - **Tour:** "Walk the trail: the four features in two minutes." → Take the tour

## 5. Content model

**`public/site-config.js`** holds `window.BLAZEAHEAD_SITE`:

```js
window.BLAZEAHEAD_SITE = {
  teamName: '', gitlabProjectUrl: '', vsixFileName: 'blazeAhead.vsix',
  downloadLink: 'release-page',          // or 'direct' once releases are published with tools/publish-release.ps1
  version: '', releaseDate: '',
  links: { docs: '', issues: '' },
};
```

- The derived URLs follow Coalesce's `config.js`: `releases`, `download` (release page or direct permalink) and `project`.
- `issues` is where "Report an issue" and the Help card go.

**`public/tour-content.js`** holds `window.BLAZEAHEAD_TOUR`:

```js
window.BLAZEAHEAD_TOUR = {
  trailhead: { sign: 'Trailhead' },
  stops: [ { id: 'continuity', sign: 'Continuity', title: '…', paragraphs: ['…'], points: ['…'] },
           { id: 'scaffolding', … }, { id: 'knowledge', …, cards: [ { title: '…', text: '…' } ] }, { id: 'in-flight', … } ],
  end: { sign: 'Download' },
  help: { signs: { left: 'Issues', right: 'Docs', ahead: 'Tour' } },
  rocks: ['429 Too Many Requests', '503 Service Unavailable', 'SSE glitch', 'Stream error', 'Timeout'],
};
```

- The world has exactly four stop scenes, and the content's stops map to them by order.
- If there are more than four, the extras are ignored and the console warns.
- If there are fewer than four, the tour ends early.
- Sign labels in the live scene are drawn at runtime from this file.
- The still images carry the default labels baked in. If a label changes, the stills can be re-rendered (README).

Draft copy, taken from the owner's descriptions (**to be replaced with real copy**):

| Stop | Title | Text |
|---|---|---|
| Continuity | The continuity proxy | Our network gets busy. When a service answers with a 429 or a 503, an event stream hiccups, or a reply breaks off mid-stream, the continuity proxy absorbs it and carries on. Your Claude Code session keeps going instead of falling over. |
| Scaffolding | Scaffold your environment | blazeAhead sets up your development environment and mints the personal access tokens you need: Jira, Confluence, GitLab, Artifactory and more. You start the trail with every key already on the ring. |
| Knowledge | The knowledge base | Every internal tool, charted as trails from one trailhead; the card steps through the trails (see the trail-map spec). |
| In Flight | The In Flight queue | In Flight connects to Jira and runs prompts through the devAgent workflow straight from Jira issues. It isn't about engineering one prompt; it's about keeping hundreds of them moving. |

Knowledge also carries three placeholder cards: "Proxy connections", "How things are set up" and "Where things live", each with "[Card text from the current site]".

## 6. The world (Blender)

**`blender/blazeahead_layout.py`** is pure Python with no `bpy`, so plain pytest can test it. It is deterministic, with fixed seeds.
- **Terrain:** its own value-noise height function, flattened around the stop vignettes so the water sits level.
- **World path:**
  - The path runs trailhead → stop 1 → … → stop 4 → a short run-out: a Catmull-Rom spline resampled every 0.25 m.
  - Stops are about 24 m of trail apart.
  - Each stop has a local frame: an origin on the path, and a heading along the path (local +x).
  - The vignette sits on the left of the walking direction (local +y).
  - The stop's camera stands 2.6 m to the right of the path, at 1.25 m eye height, looking at the vignette.
- **Views:**
  - Each view is `{position, target, hfov}`: horizontal field of view, fitted to width, so the edge signposts stay at the screen edges on any window shape.
  - Views exist for the trailhead (the home hero), the four stops and the junction.
  - The layout also computes each still image's sign-board screen boxes, for the fallback buttons.
- **Walks:**
  - For each consecutive pair of views: camera points out along the path at 1.6 m eye height, then into the next view.
  - Look targets blend from vignette to look-ahead to vignette.
- **Scatter:** trees, branch clumps, canopy clumps, ferns and bushes, only inside a corridor about 30 m either side of the path.
  - Kept clear: the path, the stream channel, the clearings and the sign positions.
  - Instances are grouped into **chunks** by nearest stop, so the browser draws only the chunks near the camera.
- **Baked light:**
  - Every instance and every ground vertex gets an RGB tint: ambient night blue plus warm falloff from each torch, lantern and tent within reach.
  - This is how the browser gets pools of torchlight without dozens of real-time lights.
- **Vignette props:** positions and headings for the stream (with rocks), camp, kiosk and launch board; torches along the trail; the paths the lights follow (the tour path, the stream, the launch curve, the three junction branches).
- **Junction** (Help): its own small layout, with three branching trails and the three-board signpost.

**`blender/build_blazeahead.py`** (bpy) does the following:
- builds every mesh, in low-poly style with vertex colours;
- exports **`public/assets/blazeahead.glb`**: one mesh per asset type, with no textures;
- writes **`public/assets/world.json`** and **`public/assets/junction.json`**: instances, tints, chunks, views, walks, props, light paths, signs and still-sign boxes;
- saves `blender/blazeahead.blend`;
- self-checks the GLB (mesh names and triangle budget).

With `--stills`, it renders Cycles stills for the six views: the trailhead, the four stops and the junction. The grade uses a fog-transmittance pass plus numpy bloom (the technique proved on the concept canvas). The results go to `public/assets/stills/*.webp`: 1600×900, each ≤ 300 KB.

**Budgets**
- GLB ≤ 600 KB.
- World JSON ≤ 900 KB.
- Visible triangles per frame ≤ 450k.
- Draw calls ≤ 120.

## 7. Web runtime

**Modules** (`public/js/`), all plain ES modules loaded through an import map, as in Coalesce:

| Module | Role |
|---|---|
| `config.js` | Resolves `site-config.js` into links and text (ported from Coalesce). |
| `content.js` | Reads `tour-content.js` with defaults and validation, and renders cards. |
| `eligibility.js` | Checks WebGL, reduced motion, hover/fine pointer and save-data, and runs the frame watchdog (ported). |
| `rig.js` | Pure camera math: view fitting to the aspect, walk interpolation, easing, durations. Unit-tested in the browser. |
| `tour-state.js` | Pure tour state machine: current stop, walking, queued target, hash ↔ stop, KB card index. Unit-tested. |
| `world.js` | Loads the GLB and JSON, then builds the scene: fog; hemisphere and moon light plus up to four point lights for the nearest torches; the ground; instanced vegetation with per-instance tints and chunk visibility; props; signposts with runtime label textures; torches (flame shells, crystal, additive glow sprites, flicker); lights flowing along their paths (instanced sprites); water (scrolling streak texture and foam); stars; hover (fern parting, flame lean, rock tooltips); `render(dt)`. |
| `stage.js` | Mounts live or still for a page variant (`home`, `tour`, `help`): the device check, lazy import of Three.js and the world, the render loop, pause, the watchdog, resize, the IntersectionObserver, visibility and context loss. It reports `data-stage-state` and `data-stage-reason`, as Coalesce's hero did. |
| `tour.js` | Tour page glue: tour-state, the stage (camera walks), the card DOM, the sign buttons (positioned by projecting the 3D boards, or from the still's boxes), the trail map, the keyboard and the hash. |

**Live vs still:**
- The rules are Coalesce's: live only with WebGL, a fine hover pointer, no reduced motion and no save-data.
- A frame watchdog drops to stills if the median frame time exceeds 45 ms over the first 2 s.
- Three.js and the world download only after the device qualifies. Until then the still image is on screen.

**Performance:**
- Pixel ratio capped at 1.5.
- Chunk culling.
- No real-time shadows. Lighting is baked, with at most four dynamic point lights.
- Glow comes from additive sprites instead of post-processing.
- Rendering pauses when the stage is off-screen, the tab is hidden or the user pauses.

**Accessibility:**
- The canvas is `aria-hidden`, and the stage has a text description (`role="img"` plus a label on Home and Help).
- On the tour, all content is real HTML: card, buttons and trail map.
- Visible focus rings; text contrast ≥ 4.5:1; skip link; buttons for everything clickable.

## 8. Files

```
blazeahead-site/
├── public/                       ← exactly what GitLab Pages serves
│   ├── index.html                Home
│   ├── tour/index.html           Tour
│   ├── help/index.html           Help
│   ├── site-config.js            links, team, version            (edit me)
│   ├── tour-content.js           stop copy, sign labels, KB trail map (edit me)
│   ├── css/site.css
│   ├── js/                       config, content, eligibility, rig, tour-state, world, stage, tour
│   ├── vendor/three/             three.module.min.js, GLTFLoader, BufferGeometryUtils, LICENSE
│   ├── fonts/                    Fraunces, Figtree (.woff2) + OFL.txt
│   └── assets/                   blazeahead.glb, world.json, junction.json, favicon.svg, stills/*.webp
├── blender/                      blazeahead_layout.py, build_blazeahead.py, blazeahead.blend
├── tools/                        serve.py, fetch_vendor.py, verify.py, package.py, publish-release.ps1
├── tests/                        pytest + Playwright (Chromium), as in Coalesce
├── docs/superpowers/             spec and plan (not shipped)
├── .gitlab-ci.yml                sample Pages job
└── README.md                     install, edit, release, rebuild, preview
```

## 9. Testing and verification

These use pytest and Playwright in `.venv`, as in Coalesce. JS unit tests run in Chromium via `page.evaluate`.
- **Layout (pure Python):**
  - determinism;
  - four stops about 24 m apart;
  - a continuous path;
  - views look at their vignettes;
  - edge signs inside the view at the left and right edges;
  - no instance on the path, in the stream or in a clearing;
  - tints in range;
  - chunk counts.
- **Blender build** (marked `slow`): the GLB has the expected meshes under budget, and the JSON matches the schema. **Stills** (marked `stills`): six files, 1600×900.
- **JS units:**
  - `config` (URL resolution, safe links);
  - `content` (defaults, validation, stop mapping);
  - `eligibility`;
  - `rig` (walk endpoints equal the views, continuity, durations clamped, fit width);
  - `tour-state` (next and back, bounds, queueing while walking, hash round trip, KB pager).
- **Pages:**
  - all three load without console errors, both live (GPU) and with WebGL off;
  - config and content are wired in, and missing links read "Link coming soon";
  - tour keyboard navigation, deep links and back/forward;
  - the tour reaches every stop and the end signs link correctly;
  - reduced motion uses stills;
  - the walk completes live;
  - rock tooltip;
  - no horizontal scroll at 1024 px.
- **`tools/verify.py`** takes screenshots of every page and stop, plus these budgets:
  - home transfer ≤ 2.5 MB;
  - frame median ≤ max(16.7 ms, baseline + 1 ms);
  - p95 ≤ 33 ms;
  - GLB, JSON and still sizes within the §6 budgets.

## 10. Delivery

- `dist/blazeahead-site.zip` contains `public/`, `blender/`, `tools/`, `.gitlab-ci.yml`, `README.md` (shipped as `SITE-README.md`) and `requirements-dev.txt`.
- The zip is the deliverable because this laptop can't reach the work GitLab.
- `tools/publish-release.ps1` publishes a `.vsix` release with a permanent "latest" download path. It is Coalesce's script, adapted.

## 11. Risks

| Risk | Mitigation |
|---|---|
| The GPU budget on Iris-class laptops, given a forest plus a walk. | Chunk culling, baked light, sprite glow and a pixel-ratio cap. The watchdog falls back to stills. `verify.py` measures on this laptop. |
| The real-time look falls short of the Cycles concepts. | Baked tints and fog carry most of the mood. The stills are Cycles-quality wherever 3D is off. |
| Copy is drafted from short descriptions. | Every draft is marked, and all copy sits in one file. |

## 12. Open questions for the owner (defaults in use)

1. Is the download a `.vsix` on GitLab releases? **Default: yes**, with the publish script.
2. May the design have free rein, or must it match the current site's colours and fonts? **Default: free rein** (§3).
3. Help arrows: are Issues, Docs and Tour right? **Default: yes.**
4. Should the old slide page be retired? **Default: yes.**
5. Real copy is needed for the four stops, plus the full list of knowledge-base cards.
6. A photo of the coworker's flame icon, so the 3D flame and the favicon can match it.
7. The "leave a trail" quote isn't in Emerson's writings. Its earliest known source is Muriel Strode (1903). The site doesn't quote it, but the extension's sidebar does.

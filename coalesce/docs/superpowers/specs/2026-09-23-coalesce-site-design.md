# Coalesce project site: design

**Date:** 2026-09-23 · **Status:** design approved in conversation; this is the written spec for review.

**References:**
- Visual mockups (private): <https://claude.ai/artifact/SkFBUg4Fm7oyxNEvjnxcqd>, direction B plus the Help page.
- Motion test (private, throwaway): <https://claude.ai/artifact/4fC9aMHuTLD4L29mWQknWv>, "Playful" mode.

## 1. Summary

Coalesce is an Excel add-in (`.xlam`). It pulls manpower data from the corporate database, lays it out across tabs, and emails the results to parent and subordinate organizations. This project builds its home on the web: a two-page static site (**Home** and **Help**) hosted on the team's internal GitLab Pages.

Each page opens with an interactive 3D figure:
- **Home:** one large head-and-shoulders figure made of about 290 small people ("many as one").
- **Help:** the same figure, with a magnifying glass that enlarges one person.

## 2. Goals and non-goals

**Goals**
- A project home where users can download and install Coalesce and reach the docs, release notes, access instructions and help.
- A distinctive 3D hero with "Playful" motion that still works as a still image anywhere 3D can't run.
- Zero runtime dependencies: plain HTML, CSS and JavaScript served by GitLab Pages. No server code, no build step, and nothing loaded from the internet.
- Easy upkeep: one settings file holds every link, the team name and the version text.

**Non-goals**
- Writing the tutorial, docs or SOP (they exist; the site links to them).
- Analytics, forms, logins, and live data from the GitLab API.
- 3D on phones and tablets (they get the still image).

## 3. Decisions on record

| Topic | Decision |
|---|---|
| Hosting | Internal GitLab Pages (already enabled and public). The `public/` folder is published as-is. All URLs are relative, because a project's Pages site lives under a sub-path. |
| Look | Direction B: paper `#F4F0E8`, ink `#1B2423`, muted `#55605E`, teal `#1D5E5B`, terracotta `#C4623A`, line `#E2DBCD`, card `#FFFFFF`. Instrument Serif (display) and Instrument Sans (body). Single light theme by design. |
| Motion | Playful (see §6.3). |
| 3D pipeline | Blender 5.2.2 LTS authors the shapes, layout and still images; Three.js renders and animates in the browser. |
| Download source | GitLab releases. The button uses the "latest release" permalink for the `.xlam` asset (see §7). |
| Third-party code | Three.js (MIT) and the Instrument fonts (SIL OFL) are copied into the site with their licenses. Nothing is copied from `cth9191/blender-to-web`, whose code is all rights reserved; it served only as a technique reference. |

## 4. Files

```
coalesce-site/
├── public/                      ← the website (exactly what GitLab Pages serves)
│   ├── index.html               Home
│   ├── help/index.html          Help
│   ├── site-config.js           ← the one file to edit: links, team name, version
│   ├── css/site.css
│   ├── js/crowd.js              shared 3D engine (loading, springs, states, fallbacks)
│   ├── js/home.js               Home hero
│   ├── js/help.js               Help hero (crowd + magnifier)
│   ├── js/config.js             applies site-config.js to the page
│   ├── vendor/three/            pinned Three.js build + GLTFLoader, RoomEnvironment, LICENSE
│   ├── fonts/                   Instrument Serif / Sans .woff2 + OFL.txt
│   └── assets/                  coalesce.glb, layout.json, home-still.webp, help-still.webp, favicon.svg
├── blender/
│   ├── build_coalesce.py        builds meshes + layout, exports GLB/JSON, renders stills
│   └── coalesce.blend           saved by the script, for hand edits
├── tools/verify.py              automated screenshots and metrics (dev machine only)
├── docs/superpowers/specs/      this spec (not shipped)
├── .gitlab-ci.yml               sample Pages job (use only if the project lacks one)
└── README.md                    install, release, edit and preview instructions
```

## 5. Pages and content

Copy below is final unless noted. `[BRACKETS]` are filled from `site-config.js`.

### 5.1 Shared chrome

- **Header:** logo mark (teal person with a terracotta dot) and the "Coalesce" wordmark linking Home; nav links **Docs · Releases · Get access · Help**; a **Download Coalesce** button.
- **Footer:** "Coalesce · maintained by [TEAM NAME]" · "GitLab project" · "Report an issue" (the latter goes to the service desk).
- The current page's nav item is marked with `aria-current="page"`.

### 5.2 Home (`index.html`)

1. **Hero:**
   - The crowd figure.
   - Headline: "Many people. *One* clear picture."
   - Lede: "Coalesce pulls your manpower data into one Excel workbook, organized across tabs, and emails it up and down the chain to parent and subordinate organizations."
   - Buttons: **Download Coalesce** (primary) and **Read the docs** (secondary).
   - Below them: "Version [VERSION], [DATE] · Release notes".
2. **Install**, as three numbered steps (a real sequence):
   1. **Download** `Coalesce.xlam`. Save it in the folder Excel opens when you click Browse in step 3.
   2. **Unblock it** if Excel blocks its macros: right-click the file → Properties → tick **Unblock** → OK.
   3. **Add it to Excel:** File → Options → Add-ins → Manage: *Excel Add-ins* → Go… → Browse… → choose `Coalesce.xlam` → OK.
   - Note: "Updating? Close Excel, download the new version and replace the old file."
3. **Project home:** four cards.
   - **Documentation:** usage docs and SOP.
   - **Release notes:** the GitLab releases page.
   - **Get access:** request access.
   - **Help:** the Help page.

### 5.3 Help (`help/index.html`)

1. **Hero:**
   - The magnifier figure.
   - Eyebrow: "HELP".
   - Headline: "Let's take a *closer* look."
   - Lede: "Stuck on a step, or not sure what comes next? Learn it with the tutorial, look it up in the SOP, or open a service desk ticket."
2. **Get help:** three cards, with the aside "Not sure which? Start with the tutorial."
   - **Service desk:** "Report a problem or request a change. Tickets go to [TEAM NAME] in Jira." → Open a ticket.
   - **Interactive tutorial:** "A guided walkthrough of onboarding and offboarding someone in Coalesce." → Start the tutorial.
   - **Usage docs & SOP:** "How to use each screen, and the standard operating procedure behind every step." → Read the SOP.

### 5.4 `site-config.js`

```js
window.COALESCE_SITE = {
  teamName: '[TEAM NAME]',
  gitlabProjectUrl: 'https://gitlab.example.com/group/coalesce', // no trailing slash
  xlamFileName: 'Coalesce.xlam',
  downloadLink: 'release-page', // switch to 'direct' once releases are published with tools/publish-release.ps1
  version: '[VERSION]',
  releaseDate: '[DATE]',
  links: {
    docs: '',          // usage docs / SOP
    tutorial: '',
    serviceDesk: '',   // Jira portal
    access: '',        // how to get access
  },
};
```

`js/config.js` fills in the page:
- It sets each `[data-link]` href and each `[data-text]` value.
- It derives two URLs:
  - Releases: `{gitlabProjectUrl}/-/releases`
  - Download: when `downloadLink` is `'direct'`, `{gitlabProjectUrl}/-/releases/permalink/latest/downloads/{xlamFileName}` (downloads the file itself). Otherwise `{gitlabProjectUrl}/-/releases/permalink/latest`, which opens the newest release page and works with any existing release.
- When a link is empty, the element stays in place but becomes non-clickable text with "Link coming soon". Nothing breaks.

## 6. The 3D figure

### 6.1 Blender authoring (`blender/build_coalesce.py`)

Run with `blender -b --factory-startup --python blender/build_coalesce.py`. It is deterministic (fixed seed) and does the following:

1. **Builds the meshes:**
   - The person token: a rounded "shoulders" body (lathe profile) plus a separate head sphere, about 700 triangles.
   - The magnifier: rim, collar and handle. The glass is used only for the still image; the browser draws its own lens.
2. **Computes the layout.** Positions are packed into the front surface of a head-and-shoulders volume:
   - Head: sphere, r 1.2, at height 3.62.
   - Shoulders: half-ellipsoid with a 2.45, b 1.35, c 2.35.
   - Grid spacing 0.265 × 0.30 with alternate rows staggered; token scale 0.40.
   - Result: about 290 positions. About 7% are flagged as accent (terracotta).
3. **Exports:**
   - `public/assets/coalesce.glb`: meshes `Person`, `MagnifierRim`, `MagnifierCollar`, `MagnifierHandle`; no textures; target ≤ 150 KB.
   - `public/assets/layout.json`: Y-up coordinates matching the GLB, the accent flags, the token scale, the Blender version and the export settings.
4. **Checks its own export:** re-imports the GLB into an empty scene and asserts the mesh names and triangle counts.
5. **Renders the stills** in Cycles: `home-still.webp` and `help-still.webp` at 1400 × 1080 with transparent background (real glass lens on Help), each ≤ 250 KB.
6. **Saves** `blender/coalesce.blend`.

### 6.2 Browser engine (`js/crowd.js`)

- Loads the GLB and the layout. All people are drawn as one instanced mesh (one draw call) using a MeshPhysicalMaterial with clearcoat and per-person colors.
- **Lighting:** a RoomEnvironment reflection map, plus a key and a rim directional light, with AgX tone mapping.
- **Motion:** each person is a spring pulled toward a target (home position, or a point on a path).
  - Fixed 120 Hz steps, with the time step capped at 50 ms.
  - The page's own clock stops while paused, hidden or scrolled off-screen, and rendering stops with it.
- **Sizing:** device pixel ratio capped at 1.75, with a ResizeObserver on the hero box.

### 6.3 Playful behavior (both pages)

| State | Behavior |
|---|---|
| Load | People fly in from a loose crowd and coalesce into the figure (~3.5 s). |
| Idle (Home) | Every 3–5 s, one person drifts out and fades to the page color. A terracotta newcomer arrives from the right, takes the open spot, and turns teal ~2.4 s later. The ~7% accent people from the layout stay terracotta. |
| Idle (Help) | No arrivals or departures, and all people are teal except the one under the lens, so nothing competes with the magnifier (see Hover (Help)). |
| Click | The crowd bursts outward from the click point and re-forms. |
| Pointer | The whole figure tilts slightly toward the pointer (about ±14° sideways, ±6° up/down). |
| Hover (Home) | People near the pointer part sideways and lift toward the viewer, then spring back. |
| Hover (Help) | The magnifier follows the pointer (smoothed). The person nearest the lens center turns terracotta and appears about 2× larger through the lens. When the pointer leaves, the magnifier drifts from person to person every ~3 s. |

**Help lens:**
- A second camera with a narrower field of view looks through the lens center.
- It renders into a render target that is shown on a disc inside the rim, with a slight rim vignette, so the magnification is real rather than faked.
- The render target is 512² and is refreshed only while the magnifier or the crowd is moving.

### 6.4 Still image instead of 3D

The HTML ships the still `<img>` by default, and JavaScript swaps in the canvas only when all of these hold:
- WebGL is available;
- `prefers-reduced-motion` is not set;
- the device has a fine pointer that can hover (so not phones or tablets);
- `navigator.connection.saveData` is not set.

A **frame-time watchdog** switches back to the still image if the median frame time exceeds 45 ms over the first 2 s of animation. If the GLB or the library fails to load, the still simply stays.

### 6.5 Controls and accessibility

- **Pause motion** button under the figure. It is keyboard-reachable, toggles `aria-pressed`, and satisfies WCAG 2.2.2 for content that moves longer than 5 s.
- **Figure container:** `role="img"` with a descriptive `aria-label`. The canvas is `aria-hidden`.
- **Accessibility basics:**
  - Every action is a real link or button.
  - Focus is always visible.
  - Text contrast is ≥ 4.5:1 (terracotta is used only for text ≥ 24 px).
  - There is a skip link to the main content.
- **Narrow screens:** layouts reflow to one column at phone width with no horizontal scroll.

### 6.6 Budgets

| Item | Budget |
|---|---|
| Home page total transfer (first visit) | ≤ 1.5 MB, including fonts and Three.js (minified builds) |
| `coalesce.glb` | ≤ 150 KB |
| Each still | ≤ 250 KB |
| People instances | ≤ 300 (+3 spares for arrivals) |
| Frame rate on this laptop (Intel Iris Plus, a stand-in for work PCs) | median ≤ 16.7 ms, p95 ≤ 33 ms at a 1440 × 900 viewport |

## 7. Hosting, releases and delivery

- **Pages job.** Most likely the project already publishes `public/`, and then its CI file stays. Otherwise the sample `.gitlab-ci.yml` runs a `pages` job on the default branch that publishes `public/` as-is.
- **Release convention.** GitLab lets you set a release asset's *direct asset path* only through its API, not the web form. So `tools/publish-release.ps1` (Windows PowerShell 5.1, no installs) does both steps in one command, using a personal access token with `api` scope:
  1. It uploads the `.xlam` to the project's generic package registry.
  2. It creates the release, with an asset link whose direct asset path is `/Coalesce.xlam`.
  - After the first release made this way, set `downloadLink: 'direct'` and the button downloads the newest file itself. Until then (default `'release-page'`), the button opens the newest release page.
- **Delivery.** I hand over `coalesce-site.zip` (≈ 1–2 MB). It contains `public/`, `blender/`, `tools/`, `.gitlab-ci.yml` and `README.md`, but not `docs/`. Install at work:
  1. Unzip into the GitLab project, replacing `public/`.
  2. Fill in `public/site-config.js`.
  3. Commit and push to the default branch.
  4. Attach the `.xlam` to the next release.
- **Local preview.** `python -m http.server` inside `public/`. Browsers won't load 3D files from a double-clicked page. The server is for previewing on a PC only and is never deployed.

## 8. Testing and verification

**Dev-only tooling:** Python Playwright with Chromium (`pip install playwright`, then `playwright install chromium`).

**`tools/verify.py`** serves `public/` locally, loads Home and Help at 1440 × 900 and 390 × 844, and records:
- **Screenshots:**
  - after the intro;
  - hover over the figure (Home parting; Help magnifier);
  - after a click burst;
  - paused;
  - the still image under emulated reduced motion;
  - the still image with WebGL disabled;
  - the still image under touch emulation.
- **Checks:**
  - no console errors;
  - every `[data-link]` resolved or shown as "Link coming soon";
  - fonts loaded;
  - total transfer size;
  - frame-time median and p95 over 5 s;
  - no horizontal scroll at 390 px.

**Blender self-check** (§6.1, step 4): the re-imported GLB has the expected meshes and triangle counts.

**Manual pass:** keyboard tab order, the Help magnifier's feel, and the click burst.

## 9. Risks and open items

- **Link values and team name** are filled in by the owner in `site-config.js`. Until then, cards show "Link coming soon".
- **Macro blocking.** Whether Excel blocks macros in a downloaded add-in depends on IT's security-zone settings. The install steps cover Unblock; IT can avoid the step by trusting the Pages host.
- **Project visibility.** If the GitLab project is private or internal while Pages is public, the Download link asks people to sign in to GitLab first. That is acceptable internally; to avoid it, make the release assets readable to everyone who should download.
- **Release script access.** `publish-release.ps1` needs a GitLab personal access token with `api` scope, and a GitLab version with release permalinks (15.x or newer). On older versions, keep `downloadLink: 'release-page'`.
- **Work PC graphics** are unknown. The watchdog and the still-image path cover weak or virtual machines.
- **Jira naming.** Atlassian renamed Jira Service Desk to Jira Service Management; the card text ("Service desk … in Jira") is correct under either name.

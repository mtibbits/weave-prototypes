# blazeAhead Project Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the blazeAhead static site: Home with a live 3D trailhead, a four-stop guided tour down a torch-lit forest path, and a Help junction. Every page falls back to still images.

**Architecture:**
- A pure-Python layout module is the single source of truth for the world: path, stops, views, walks, scatter, baked light and props.
- A Blender script turns the layout into one small GLB, JSON layout files and Cycles still images.
- In the browser, plain ES modules render the GLB with Three.js using unlit materials. Lighting is baked into vertex and instance colours, plus fog and additive glow, so the forest stays cheap on Iris-class laptops.
- Tour and camera logic are pure modules with their own tests.

**Tech stack:**
- Blender 5.2 LTS, with Python for layout, build and Cycles stills.
- Three.js 0.170.0, vendored ES modules loaded through an import map.
- HTML and CSS only, with no build step.
- pytest 8 and Playwright (Chromium) in `.venv`, the same harness as `coalesce-site`.

**Spec:** `docs/superpowers/specs/2026-09-25-blazeahead-site-design.md`

## Global Constraints

- Static files only. All URLs are relative. Nothing loads from the internet at runtime. Three.js 0.170.0 and the fonts are vendored.
- Target: desktop Chromium. No phone design, but no horizontal scroll at widths of 1024 px and up.
- Palette: ink `#0C171B`, panel `#13232A`, line `#28404A`, text `#EEE7D8`, muted `#A9B8B5`, amber `#FFB23F`, crystal blue `#4AA8FF`. Fonts: Fraunces for display, Figtree for body. Dark theme only.
- Live 3D runs only with WebGL, a fine hover pointer, no reduced motion and no save-data. The watchdog falls back to stills when the median frame time exceeds 45 ms over the first 2 s.
- Budgets:
  - GLB ≤ 600 KB and world JSON ≤ 900 KB.
  - Each still ≤ 300 KB at 1600×900.
  - Home transfer ≤ 2.5 MB.
  - Frame median ≤ max(16.7 ms, empty-page baseline + 1 ms); p95 ≤ 33 ms.
  - Visible triangles ≤ 450k.
- The world has exactly four stop scenes, in this order: continuity (stream), scaffolding (camp), knowledge (kiosk), in-flight (clearing). Content maps to them by order.
- Hashes are `#continuity`, `#scaffolding`, `#knowledge` and `#in-flight`. Sign labels: Trailhead, Continuity, Scaffolding, Knowledge, In Flight, Download.
- Fire only ever appears in a torch or lantern, never loose in the forest.
- Coordinates: the layout works in Blender Z-up. JSON for the browser is Y-up: position `(x, z, -y)`, quaternion `[x, z, -y, w]` in Three.js order, scale `(sx, sz, sy)`.

## Review Focus

1. **An unknown or out-of-range hash** (`#foo`, or `#in-flight` when content has only three stops) should open stop 1 with no console error. This is tested in Task 5 (`tour-state`) and Task 8 (page).
2. **Mashing Next or holding → during a walk** should apply only the latest request, one walk at a time, and never leave the UI stuck hidden. This is tested in Task 5 (queueing) and Task 8 (live walk).
3. **An odd window shape** (1024×768 or 2560×1080) should keep both edge signs on screen with their buttons over them. This is tested in Task 5 (`rig.fitView`) and Task 8 (button boxes inside the viewport).
4. **A hand-edited `tour-content.js`** (a missing field, an empty label, only three stops, or the file failing to load) should still give a working tour built from defaults. This is tested in Task 5 (`content`) and Task 6 (the page with `BLAZEAHEAD_TOUR` removed).
5. **3D dying mid-session** (context lost, or the watchdog tripping during a walk) should leave stills at the current stop with the UI still working. This is tested in Task 7 (`stage` stop → still) and Task 8 (forced stop during a tour).

---

## File map

| File | Responsibility |
|---|---|
| `blender/blazeahead_layout.py` | Pure-Python world. Terrain `height()`, `Spline`, `build_world()`, `build_junction()`, baked light `light_at()`, `to_web()`. |
| `blender/build_blazeahead.py` | bpy side. Meshes, colour attributes, GLB export, `world.json` and `junction.json`, self-check, `--stills` (Cycles plus grade). |
| `public/js/config.js` | Turns `BLAZEAHEAD_SITE` into URLs and text, then applies them to the DOM. |
| `public/js/content.js` | Normalizes `BLAZEAHEAD_TOUR` (defaults, validation) and renders a card's HTML. |
| `public/js/eligibility.js` | Decides live vs still, and hosts the `FrameWatchdog` class. |
| `public/js/rig.js` | Pure camera math: `fitVerticalFov`, `ease`, `Walk`, `poseAt`. |
| `public/js/tour-state.js` | Pure tour state machine. |
| `public/js/world.js` | The Three.js scene built from GLB and JSON. |
| `public/js/stage.js` | Live/still mount, render loop, pause, watchdog, visibility. |
| `public/js/tour.js` | Tour page glue: state, stage, DOM, keys, hash. |
| `public/index.html`, `tour/index.html`, `help/index.html`, `css/site.css`, `assets/favicon.svg` | Pages. |
| `public/site-config.js`, `public/tour-content.js` | Owner-edited settings and copy. |
| `tools/serve.py`, `fetch_vendor.py`, `verify.py`, `package.py`, `publish-release.ps1` | Dev and release tools. |
| `tests/*` | pytest + Playwright. |

---

### Task 1: Scaffold, harness and vendored files

**Files:**
- Create: `requirements-dev.txt`, `pytest.ini`, `tools/serve.py`, `tools/fetch_vendor.py`, `tests/conftest.py`, `tests/helpers.py`, `tests/blank.html`, `tests/test_harness.py`, `tests/test_vendor.py`
- Create (generated): `public/vendor/three/**`, `public/fonts/*.woff2`, `public/fonts/OFL.txt`

**Interfaces:**
- Produces fixtures `base_url`, `browser` (GPU args), `browser_no_webgl`, `make_page(target_browser=None, **context_args)`, `js(body) -> value` (runs async JS in `tests/blank.html`), and `blender_exe`. Also produces helpers `collect_errors(page)`, `stage_result(page)`, `png_rows(png)`.
- The import map in pages: `"three": "./vendor/three/build/three.module.min.js"`, `"three/addons/": "./vendor/three/examples/jsm/"` (use `../` from subfolders).

- [ ] **Step 1: Copy the harness from coalesce-site and adapt it.** `tools/serve.py` is copied verbatim. `tests/conftest.py` is copied, but `base_url` serves the repo root, so pages live at `/public/...` and `tests/blank.html` at `/tests/blank.html`. `tests/helpers.py` keeps `collect_errors` and `png_rows`, and replaces `hero_result` with:

```python
def stage_result(page, selector="[data-stage]", timeout=30000):
    """Wait until the stage settles (live, or still for a reason other than loading); returns [state, reason]."""
    page.wait_for_function(
        "(sel) => { const d = document.querySelector(sel)?.dataset;"
        " return !!d && !!d.stageState && d.stageReason !== 'loading'; }",
        arg=selector, timeout=timeout)
    return page.eval_on_selector(selector, "el => [el.dataset.stageState, el.dataset.stageReason]")
```

`tests/blank.html` is a minimal page carrying the same import map as the site, rooted at `../public/vendor/three/...`.

- [ ] **Step 2: Write `tests/test_vendor.py` (failing).**

```python
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

def test_three_is_vendored_at_the_pinned_version():
    build = (PUBLIC / "vendor/three/build/three.module.min.js").read_text(encoding="utf-8")
    assert 'REVISION="170"' in build.replace(" ", "")
    for rel in ("examples/jsm/loaders/GLTFLoader.js", "examples/jsm/utils/BufferGeometryUtils.js", "LICENSE"):
        assert (PUBLIC / "vendor/three" / rel).is_file(), rel

def test_fonts_and_licence_are_vendored():
    for name in ("Fraunces.woff2", "Fraunces-Italic.woff2", "Figtree.woff2", "OFL.txt"):
        assert (PUBLIC / "fonts" / name).is_file(), name

def test_three_imports_work_in_the_browser(js):
    assert js("const THREE = await import('three'); return THREE.REVISION;") == "170"
```

- [ ] **Step 3: Run it.** Run `.venv/Scripts/python -m pytest tests/test_vendor.py -v`. Expected: FAIL, because the files are missing.
- [ ] **Step 4: Adapt `tools/fetch_vendor.py`** from coalesce-site. Keep the same Three.js list. Fonts come from Google Fonts css2: `Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700` and `Figtree:wght@400..700`, latin subset, saved as `Fraunces.woff2`, `Fraunces-Italic.woff2` and `Figtree.woff2`. OFL comes from `google/fonts` `ofl/fraunces/OFL.txt` and `ofl/figtree/OFL.txt`. Then create the venv (`python -m venv .venv`, `pip install -r requirements-dev.txt`, `playwright install chromium`) and run the fetch script.
- [ ] **Step 5: Run the tests.** Expected: PASS, with `test_harness.py` checking the server answers `/public/` and serves `.js` as `text/javascript`.
- [ ] **Step 6: Commit** `build: harness, local server and vendored Three.js 0.170.0 + Fraunces/Figtree`.

### Task 2: World layout (pure Python)

**Files:**
- Create: `blender/blazeahead_layout.py`
- Test: `tests/test_layout.py`

**Interfaces (Produces):**
- `height(x, y, flat=()) -> float`: value-noise terrain. `flat` is a list of `((cx, cy), r)` discs where the terrain is damped.
- `Spline(points, step=0.25)` with `.pts`, `.length`, `.at(s) -> (x, y, tx, ty)` and `.nearest(x, y) -> (s, dist)`, backed by a grid index.
- `build_world(seed=11) -> dict` in Z-up, with these keys:
  - `path`: Spline control points.
  - `stops`: 4 × `{id, origin, heading, view, signs:{left, right}, vignette}`.
  - `trailhead`: `{view, sign, torch}`.
  - `walks`: 5 × `{from, to, points:[[x,y,z]...], targets:[[x,y,z]...]}`, covering trailhead→1 and 1→2→3→4.
  - `torches`: `[{pos, scale}]`.
  - `lanterns`: `[{pos}]`.
  - `instances`: `{mesh_name: [[x,y,z, qw,qx,qy,qz, sx,sy,sz, r,g,b, chunk], ...]}`.
  - `props`: `{stream, rocks, camp, kiosk, board}` placements.
  - `flows`: `{name: [[x,y,z]...]}`, the paths the lights follow.
  - `ground`: `{verts, faces, colors}`.
- `build_junction(seed=5) -> dict`: the same keys, minus stops and walks, plus `junction: {view, post, boards:[{yaw, h, label_key}]}`.
- `light_at(x, y, z, nx, ny, nz, sources) -> (r, g, b)`: baked light multiplier (linear).
- `to_web(world) -> dict`: the JSON for the browser (Y-up, rounded to 3 decimals, instances flattened per mesh and chunk), containing `version`, `views`, `walks`, `stops`, `signs`, `torches`, `lanterns`, `flows`, `instances`, `props`, `stillSigns` and `bounds`.
- Constants: `STOP_IDS = ["continuity","scaffolding","knowledge","in-flight"]`, `STOP_SPACING = 24.0`, `EYE = 1.25`, `STOP_BACK = 2.6`, `VIEW_HFOV = 62.0` (degrees, horizontal).

- [ ] **Step 1: Write `tests/test_layout.py` (failing).**

```python
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import blazeahead_layout as L

W = L.build_world()

def dist(a, b):
    return math.dist(a[:len(b)], b[:len(a)])

def test_deterministic():
    assert L.to_web(L.build_world()) == L.to_web(W)

def test_four_stops_in_order_about_24_m_apart_along_the_path():
    assert [s["id"] for s in W["stops"]] == L.STOP_IDS
    path = L.Spline(W["path"])
    ss = [path.nearest(*s["origin"][:2])[0] for s in W["stops"]]
    gaps = [b - a for a, b in zip(ss, ss[1:])]
    assert all(18 <= g <= 32 for g in gaps), gaps

def test_views_face_their_vignettes_and_stand_off_the_path():
    path = L.Spline(W["path"])
    for s in W["stops"]:
        v = s["view"]
        _, d_cam = path.nearest(*v["position"][:2])
        assert 1.8 <= d_cam <= 3.4
        to_target = [t - p for t, p in zip(v["target"], v["position"])]
        to_vig = [g - p for g, p in zip(s["vignette"], v["position"])]
        cosang = sum(a * b for a, b in zip(to_target[:2], to_vig[:2])) / (math.hypot(*to_target[:2]) * math.hypot(*to_vig[:2]))
        assert cosang > 0.9

def test_edge_signs_sit_at_the_left_and_right_edges_of_each_stop_view():
    for s in W["stops"]:
        xl = L.screen_x(s["view"], s["signs"]["left"]["board"], aspect=16 / 9)
        xr = L.screen_x(s["view"], s["signs"]["right"]["board"], aspect=16 / 9)
        assert 0.03 <= xl <= 0.2 and 0.8 <= xr <= 0.97, (s["id"], xl, xr)

def test_walks_start_and_end_on_their_views():
    views = [W["trailhead"]["view"]] + [s["view"] for s in W["stops"]]
    assert len(W["walks"]) == 4 and W["walks"][0]["from"] == "trailhead"
    for walk, a, b in zip(W["walks"], views, views[1:]):
        assert dist(walk["points"][0], a["position"]) < 1e-6 and dist(walk["points"][-1], b["position"]) < 1e-6
        assert all(dist(p, q) < 6.0 for p, q in zip(walk["points"], walk["points"][1:]))

def test_nothing_grows_on_the_path_in_the_stream_or_in_clearings():
    path = L.Spline(W["path"])
    for name, items in W["instances"].items():
        if name.startswith(("Canopy", "Rock")):
            continue
        for it in items:
            _, d = path.nearest(it[0], it[1])
            assert d > 0.45, (name, it[:3])

def test_baked_tints_are_bounded_and_torches_warm_their_surroundings():
    near = L.light_at(*W["torches"][0]["pos"][:2], W["torches"][0]["pos"][2] - 1.0, 0, 0, 1, W["sources"])
    far = L.light_at(200.0, 200.0, 0.0, 0, 0, 1, W["sources"])
    assert near[0] > far[0] * 3 and near[0] > near[2]
    for items in W["instances"].values():
        for it in items:
            assert all(0.0 <= c <= 4.0 for c in it[10:13])

def test_web_json_is_y_up_and_within_budget():
    import json
    web = L.to_web(W)
    x, y, z = W["torches"][0]["pos"]
    assert web["torches"][0]["pos"] == [round(x, 3), round(z, 3), round(-y, 3)]
    assert len(json.dumps(web, separators=(",", ":"))) < 900_000

def test_junction_has_three_boards_and_three_branches():
    J = L.build_junction()
    assert [b["key"] for b in J["junction"]["boards"]] == ["left", "right", "ahead"]
    assert len([k for k in J["flows"] if k.startswith("branch")]) == 3
```

- [ ] **Step 2: Run it.** Run `.venv/Scripts/python -m pytest tests/test_layout.py -v`. Expected: FAIL, because the module is missing.
- [ ] **Step 3: Implement `blender/blazeahead_layout.py`.** Port the proven pieces from the concept script: Catmull-Rom plus resampling, the terrain shape, fern/tree scatter rules, the flame outline constants and the signpost dimensions (post radius 0.076, height 0.914; board 0.457 × 0.14 × 0.019). New in this module:
  - value noise with a fixed permutation table;
  - a `Spline` with a grid index for nearest queries;
  - world construction: a winding path whose control points follow the headings `[0°, 18°, -12°, 25°, -8°, 20°]` with ~24 m legs;
  - stop frames at the leg ends, with the vignette at `origin + left*5.2` and the view at `origin + right*STOP_BACK` (right = heading rotated -90°). The eye is at `height + EYE` and the target is `vignette + (0, 0, 0.6)`;
  - signs at `origin ± heading*1.55 + left*0.35`, arrows pointing back and on;
  - walks (view → path points every 3 m at 1.6 m eye → view; look-ahead targets 6 m along the path);
  - scatter restricted to within 32 m of the path, with chunk = index of the nearest stop (trailhead = 0);
  - baked light sources (ambient `#1B3340` × 0.9, moon from `(0.35, -0.8, -1.0)`, torches warm `(1.0, 0.55, 0.22)` I=3.2 r=3.5, lanterns I=2.4 r=2.8, tent I=2.0 r=2.5) with `light_at = ambient + moon·max(0, n·l)·0.35 + Σ I·c·max(0.25, n·d)/(1 + (dist/r)²)`;
  - a corridor ground grid (0.7 m cells within 20 m of the path, channel carved for the stream), with vertex colours = albedo (moss/dirt mix) × `light_at`;
  - `screen_x(view, point, aspect)`, using `VIEW_HFOV` as the horizontal FOV.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: world layout shared by Blender and the website`.

### Task 3: Blender build (meshes, GLB, JSON)

**Files:**
- Create: `blender/build_blazeahead.py`
- Create (generated): `public/assets/blazeahead.glb`, `public/assets/world.json`, `public/assets/junction.json`, `blender/blazeahead.blend`
- Test: `tests/test_blender_build.py` (marked `slow`)

**Interfaces:**
- Consumes: `build_world`, `build_junction`, `to_web`, `light_at` and the mesh name keys from Task 2.
- Produces these GLB mesh nodes, which the browser looks up by name:
  - vegetation: `Trunk0..3`, `Branch`, `Clump0..3`, `Canopy0..1`, `Fern0..3`, `Rock0..2`;
  - signpost and torch: `Post`, `Board`, `TorchStaff`, `TorchCup`;
  - flame: `FlameOuter`, `FlameMid`, `FlameInner`, `Crystal`;
  - props: `Tent`, `TentDoor`, `Rack`, `Key`, `Crate`, `LanternPole`, `LanternCage`, `Kiosk`, `KioskMap`, `LaunchBoard`, `Tag`, `TagLit`, `LogSeat`, `FallenLog`;
  - land and water: `Ground`, `Water`, `Foam`.
- Every mesh has a colour attribute `Col` (FLOAT_COLOR, CORNER), which is the baked final colour or a per-face shade factor. It is exported with `export_vertex_color='ACTIVE'`, `export_normals=False`, `export_texcoords=True` (only `Water` has UVs) and `export_materials='NONE'`.
- Stills-only data (Cycles lights) is not exported.

- [ ] **Step 1: Write `tests/test_blender_build.py` (failing).** Run the Blender build into a temp folder. Assert:
  - the GLB exists and is ≤ 600 KB;
  - every required mesh name is present (parse the GLB JSON chunk: magic `glTF`, first chunk JSON, `nodes[].name`);
  - `world.json` has `version == 1` and 4 stops with the IDs in order;
  - every `instances` key names a mesh in the GLB;
  - the build prints `SELFCHECK` and `BUILD OK`.

```python
import json, struct, subprocess
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["Trunk0", "Branch", "Clump0", "Canopy0", "Fern0", "Rock0", "Post", "Board", "TorchStaff", "TorchCup",
            "FlameOuter", "FlameMid", "FlameInner", "Crystal", "Tent", "TentDoor", "Rack", "Key", "Kiosk",
            "KioskMap", "LaunchBoard", "Tag", "TagLit", "Ground", "Water", "Foam"]

def glb_json(path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON"
    return json.loads(data[20:20 + length])

@pytest.mark.slow
def test_blender_build_exports_the_world(blender_exe, tmp_path):
    out = subprocess.run([blender_exe, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                          str(ROOT / "blender/build_blazeahead.py"), "--", "--out", str(tmp_path),
                          "--blend", str(tmp_path / "w.blend")], capture_output=True, text=True, timeout=900)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-3000:]
    assert "SELFCHECK" in out.stdout and "BUILD OK" in out.stdout
    glb = tmp_path / "blazeahead.glb"
    assert glb.stat().st_size <= 600_000
    names = {n.get("name") for n in glb_json(glb)["nodes"]}
    assert set(REQUIRED) <= names, set(REQUIRED) - names
    world = json.loads((tmp_path / "world.json").read_text())
    assert world["version"] == 1 and [s["id"] for s in world["stops"]] == ["continuity", "scaffolding", "knowledge", "in-flight"]
    assert set(world["instances"]) <= names
    assert (tmp_path / "world.json").stat().st_size <= 900_000
    assert json.loads((tmp_path / "junction.json").read_text())["junction"]["boards"]
```

- [ ] **Step 2: Run it.** Expected: FAIL, because there is no build script.
- [ ] **Step 3: Implement `build_blazeahead.py`.**
  - It imports the layout (with `sys.path` set to the script folder).
  - Mesh builders are ported from the concept script (trunk, branch, clump, fern, rock, board with arrow, post, flame shells via 2D curves, crystal bipyramid, torch staff/cup, tent, key, rack, kiosk and map drawing, launch board, tags, lantern, crate, logs), plus the ground and water from layout data.
  - Per-face shade factors for vegetation come from a canonical light: `0.55 + 0.45*max(0, n·(0.3, -0.5, 0.8))`.
  - Static props get baked per-face colours `albedo × light_at(face centre, face normal)`.
  - The flame gets gradient colours by height (the outer, mid and inner ramps from the concept); the crystal gets per-face blues by facing.
  - Export the GLB with the options above.
  - Write the JSONs via `to_web()`.
  - Save the `.blend`.
  - Self-check: re-import the GLB, then print `SELFCHECK {name: tris}` and `BUILD OK`.
  - Arguments: `--out`, `--blend`, `--stills`, `--samples`.
- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest tests/test_blender_build.py -m slow -v`. Expected: PASS. Then run the build for real into `public/assets/`.
- [ ] **Step 5: Commit** `feat: Blender build for the world pieces and layout`.

### Task 4: Cycles still images

**Files:**
- Modify: `blender/build_blazeahead.py` (add `render_stills`)
- Create (generated): `public/assets/stills/{trailhead,continuity,scaffolding,knowledge,in-flight,junction}.webp`
- Test: `tests/test_blender_build.py::test_stills` (marked `stills`)

**Interfaces:**
- Produces still images whose framing matches `world.json` views at 16:9. The sign boxes are exported in `world.json.stillSigns` as fractions of the image, `{stopId: {left:[x0,y0,x1,y1], right:[…]}}`, computed in Blender with `world_to_camera_view`.

- [ ] **Step 1: Write the failing test.** Run the build with `--stills --samples 8` into a temp folder. Assert six `.webp` files, each 1600×900 (read the VP8/VP8X header) and ≤ 300 KB, and that `stillSigns` has four stops with boxes inside `[0, 1]`.
- [ ] **Step 2: Implement `render_stills`.**
  - For each view, build the full Cycles scene from the layout: real point lights at torches and lanterns, a tent light, the stream water material, stars.
  - Per view: camera with `lens` from `VIEW_HFOV`; beauty EXR plus a fog-transmittance pass with a material override; numpy grade (fog colour band, bloom, vignette); save WEBP at quality 82 through `save_render` (AgX, Medium High Contrast).
  - This is the concept script's `render_passes` and `grade`, ported as-is.
- [ ] **Step 3: Run** `pytest -m stills` (it takes minutes). Expected: PASS. Then render the real stills at 48 samples into `public/assets/stills/`.
- [ ] **Step 4: Commit** `feat: Cycles still images for every view`.

### Task 5: Pure JS modules (config, content, eligibility, rig, tour-state)

**Files:**
- Create: `public/js/config.js`, `public/js/content.js`, `public/js/eligibility.js`, `public/js/rig.js`, `public/js/tour-state.js`, `public/site-config.js`, `public/tour-content.js`
- Test: `tests/test_config.py`, `tests/test_content.py`, `tests/test_eligibility.py`, `tests/test_rig.py`, `tests/test_tour_state.py`

**Interfaces (Produces):**
- `config.js`:
  - `resolveConfig(cfg) -> {teamName, version, releaseDate, urls:{docs, issues, project, releases, download}}`. The GitLab `download` is `…/-/releases/permalink/latest` or `…/latest/downloads/<vsixFileName>`.
  - `applyConfig(root, resolved)`, using the `data-link`, `data-text` and `data-requires` conventions from Coalesce.
  - `boot(win)`.
  - `MISSING_LABEL = 'Link coming soon'`.
- `content.js`:
  - `DEFAULT_TOUR`.
  - `normalizeTour(raw) -> {stops:[{id, sign, title, paragraphs, points, cards}] (≤4, ids forced to STOP_IDS order), trailheadSign, endSign, help:{left,right,ahead}, rocks}`.
  - `cardHtml(stop, cardIndex) -> string` (escaped).
  - `STOP_IDS`.
- `eligibility.js` is a verbatim port of Coalesce: `readEnvironment`, `decideMode`, `FrameWatchdog`.
- `rig.js`:
  - `fitVerticalFov(hfovDeg, aspect) -> vfovDeg`.
  - `easeInOut(t)`.
  - `walkDuration(lengthM)`: returns `clamp(length/7, 2.5, 4.5)` seconds.
  - `class Walk { constructor(points, targets); length; poseAt(u) -> {position:[x,y,z], target:[x,y,z]} }`. It uses centripetal Catmull-Rom over `points` and `targets`, with `u∈[0,1]` mapped by arc length.
- `tour-state.js`: `class TourState`.
  - Constructor: `new TourState(stopCount)`.
  - Properties: `index` (-1 = trailhead, 0..n-1 stops), `walking`, `queued`.
  - Methods:
    - `request(target)` returns `'walk'`, `'queued'` or `'none'`; target is a number or `'next'` / `'prev'`.
    - `arrive()` returns the next target, or null.
    - `hashFor(index)`.
    - `indexForHash(hash)` returns `-1` for unknown.
    - `static fromHash(hash, count)`.
  - Leaving the ends is reported by `request` returning `'exit-start'` or `'exit-end'`.
  - `cardIndex` has `nextCard()` and `prevCard(cardsLength)`.

- [ ] **Step 1: Write the failing tests.** Key cases, written via the `js` fixture (`await import('/public/js/…')`):

```python
def test_tour_state_queues_only_the_latest_request_while_walking(js):
    r = js("""const {TourState} = await import('/public/js/tour-state.js');
      const s = new TourState(4); const a = s.request('next');
      const b = s.request('next'); const c = s.request('next'); const d = s.request(0);
      const after = s.arrive(); return [a, b, c, d, s.index, after, s.walking];""")
    assert r == ["walk", "queued", "queued", "queued", 0, None, False]

def test_unknown_or_out_of_range_hash_opens_stop_one(js):
    r = js("""const {TourState} = await import('/public/js/tour-state.js');
      return [TourState.fromHash('#foo', 4), TourState.fromHash('#in-flight', 3), TourState.fromHash('#knowledge', 4),
              TourState.fromHash('', 4)];""")
    assert r == [0, 0, 2, -1]

def test_ends_exit_to_home_and_download(js):
    r = js("""const {TourState} = await import('/public/js/tour-state.js');
      const s = new TourState(4); s.index = 0; const a = s.request('prev'); s.index = 3; const b = s.request('next');
      return [a, b];""")
    assert r == ["exit-start", "exit-end"]

def test_walk_endpoints_match_views_and_duration_is_clamped(js):
    r = js("""const {Walk, walkDuration, fitVerticalFov} = await import('/public/js/rig.js');
      const w = new Walk([[0,1,0],[3,1,4],[6,1,8]], [[0,1,5],[3,1,9],[6,1,13]]);
      const a = w.poseAt(0), b = w.poseAt(1);
      return [a.position, b.position, walkDuration(3), walkDuration(24), walkDuration(90),
              Math.round(fitVerticalFov(62, 16/9) * 10) / 10, fitVerticalFov(62, 21/9) < fitVerticalFov(62, 4/3)];""")
    assert r[0] == [0, 1, 0] and r[1] == [6, 1, 8]
    assert r[2] == 2.5 and abs(r[3] - 24 / 7) < 1e-9 and r[4] == 4.5
    assert r[5] == 37.3 and r[6] is True

def test_normalize_tour_survives_hand_edits(js):
    r = js("""const {normalizeTour, cardHtml} = await import('/public/js/content.js');
      const t1 = normalizeTour(undefined);
      const t2 = normalizeTour({stops: [{sign: ''}, {title: '<b>x</b>'}, {}]});
      const t3 = normalizeTour({stops: Array.from({length: 6}, () => ({}))});
      return [t1.stops.length, t2.stops.length, t2.stops[0].sign, t3.stops.length, t2.stops.map(s => s.id),
              cardHtml(t2.stops[1], 0).includes('&lt;b&gt;x&lt;/b&gt;')];""")
    assert r[0] == 4 and r[1] == 3 and r[2] == "Continuity" and r[3] == 4
    assert r[4] == ["continuity", "scaffolding", "knowledge"] and r[5] is True
```

  - `test_config.py`: port Coalesce's tests with `vsixFileName` and `issues`. They cover direct vs release-page download, trailing slashes, unsafe `javascript:` links dropped, and missing links → "Link coming soon".
  - `test_eligibility.py`: port Coalesce's tests.
- [ ] **Step 2: Run them.** Expected: FAIL, because the modules are missing.
- [ ] **Step 3: Implement the five modules**, plus `site-config.js` and `tour-content.js` with the draft copy from spec §5. The tour state machine:

```js
// public/js/tour-state.js
import { STOP_IDS } from './content.js';
export class TourState {
  constructor(count) { this.count = Math.max(1, Math.min(count, STOP_IDS.length)); this.index = -1; this.walking = false; this.queued = null; this.cardIndex = 0; }
  resolve(target) {
    if (target === 'next') return this.index + 1;
    if (target === 'prev') return this.index - 1;
    return Math.max(-1, Math.min(this.count - 1, Number(target)));
  }
  request(target) {
    if (this.walking) { this.queued = target; return 'queued'; }
    const to = this.resolve(target);
    if (to >= this.count) return 'exit-end';
    if (to < 0 && this.index <= 0 && target === 'prev') return 'exit-start';
    if (to === this.index) return 'none';
    this.walking = true; this.from = this.index; this.index = to; this.cardIndex = 0;
    return 'walk';
  }
  arrive() {
    this.walking = false;
    const q = this.queued; this.queued = null;
    if (q === null) return null;
    const outcome = this.request(q);
    return outcome === 'walk' ? this.index : null;
  }
  hashFor(i) { return i >= 0 ? `#${STOP_IDS[i]}` : ''; }
  indexForHash(hash) { const i = STOP_IDS.indexOf(String(hash || '').replace(/^#/, '')); return i >= 0 && i < this.count ? i : -1; }
  static fromHash(hash, count) { const h = String(hash || '').replace(/^#/, ''); if (!h) return -1; const i = STOP_IDS.indexOf(h); return i >= 0 && i < count ? i : 0; }
  nextCard(n) { this.cardIndex = Math.min(n - 1, this.cardIndex + 1); return this.cardIndex; }
  prevCard() { this.cardIndex = Math.max(0, this.cardIndex - 1); return this.cardIndex; }
}
```

(The queued-while-walking test expects `arrive()` to apply the latest queued request. In that test it is `0`, which equals the new index, so the outcome is `'none'` and the result is `null`.)
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: settings, tour content, camera rig and tour state`.

### Task 6: Pages with still-image scenes (no 3D yet)

**Files:**
- Create: `public/index.html`, `public/tour/index.html`, `public/help/index.html`, `public/css/site.css`, `public/assets/favicon.svg`, `public/js/tour.js` (still mode)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: Task 5 modules and Task 4 stills.
- Produces this DOM contract, which `stage.js` and `tour.js` rely on:
  - `[data-stage]` is the scene container. It holds an `<img class="stage-still">` and gets `data-stage-state` and `data-stage-reason`.
  - `[data-pause]` is the pause button.
  - On the tour page:
    - card: `[data-tour-card]`, holding `[data-card-eyebrow]`, `[data-card-title]` and `[data-card-body]`, plus `[data-card-prev]`, `[data-card-next]` and `[data-card-count]`;
    - signs: `button[data-sign="left"]` and `button[data-sign="right"]`, each with a `[data-sign-label]`;
    - trail map: `nav[data-trail-map]` containing `button[data-goto="-1|0|1|2|3|end"]`;
    - `body[data-tour-index]` and `body[data-tour-walking]`.
- `tour.js` exports `startTour({win, doc, stage})`. In still mode it swaps `stills/<id>.webp` with a 400 ms cross-fade (none with reduced motion) and positions the sign buttons from `world.json.stillSigns`.

- [ ] **Step 1: Write `tests/test_pages.py` (failing).**
  - Each page loads with no console errors: with WebGL off (still reason `no-webgl`), and live, once Task 7 lands.
  - Config wiring: inject a full config via `add_init_script` and check it.
  - "Link coming soon" appears when links are empty.
  - Home: headline, both CTAs and the three install steps.
  - Help: the three cards link to issues, docs and `../tour/`.
  - Tour, still mode:
    - no hash → stop 1 (the still has no walk, so it goes straight to stop 1);
    - `#knowledge` → index 2, with the KB pager showing "1 of 3";
    - ArrowRight → `#in-flight`, then ArrowRight → navigates to `../#install`;
    - ArrowLeft at stop 1 → home;
    - Esc → home;
    - trail-map buttons jump;
    - `#foo` → stop 1;
    - browser Back returns to the previous stop.
  - Removing `window.BLAZEAHEAD_TOUR` (init script `delete`) still shows four stops with the default copy.
  - No horizontal scroll at 1024×768.
  - Sign buttons stay inside the viewport at 1024×768 and 2560×1080.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement the pages.**
  - Copy is spec §4.2–4.4 verbatim. Pages use the import map, `site-config.js`, `tour-content.js` and `js/config.js`.
  - CSS: dark theme tokens; Fraunces for headings and Figtree for text; buttons, cards, the steps list, the header, the footer.
  - Tour page: card at the bottom centre, trail map top right, sign buttons as transparent hit areas with a visible focus ring.
  - `favicon.svg`: our flame (outer and inner paths from the flame outline) with a blue diamond.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: Home, Tour and Help pages with still-image scenes`.

### Task 7: Live scene (world.js + stage.js)

**Files:**
- Create: `public/js/world.js`, `public/js/stage.js`
- Modify: the pages (mount the stage in live mode)
- Test: `tests/test_stage.py`

**Interfaces:**
- `world.js`:
  - `loadWorld(assetsBase, which)`, where `which` is `'world'` or `'junction'`. Returns `{gltf, layout}`.
  - `class WorldView`:
    - `constructor(canvas, assets, {labels, rocks})`
    - `resize(w, h, dpr)`
    - `setView(view)`
    - `setPose(position, target, hfov)`
    - `update(dt)`: flames, lights, water, hover springs, chunk visibility, nearest lights
    - `render()`
    - `pointer(ndcX, ndcY)` and `pointerLeave()`
    - `projectBox(nameOrObject) -> [x0,y0,x1,y1]` in CSS pixels, for the sign buttons
    - `rockAt(ndcX, ndcY) -> label|null`
    - `stats() -> {triangles, calls}`
    - `dispose()`
- `stage.js`:
  - `mountStage(el, {variant, assetsBase, labels, rocks, watchdog, watchdogLimitMs})` returns `{state, reason, view?, stop}`.
  - Variants: `home` (trailhead view, idle, hover, sign click → `tour/`), `help` (junction), `tour` (controlled by `tour.js`).
  - It exposes `el.__blaze = {view, stop}` for tests and sets `data-stage-frames`.

- [ ] **Step 1: Write `tests/test_stage.py` (failing).**
  - GPU browser: home and help go `live` / `ok` with frames increasing.
  - `?watchdogLimitMs=0.01` → still, reason `too-slow`.
  - Reduced motion → still, reason `reduced-motion`.
  - A forced `el.__blaze.stop('context-lost')` → still image visible, reason `context-lost`.
  - Visible triangles ≤ 450k at every stop, via `view.stats()`.
  - Home hover over the right brush changes fern matrices: `view.hoverChanged > 0`.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement `world.js`.**
  - Materials: `MeshBasicMaterial({vertexColors: true, fog: true})` for all meshes. Instanced meshes get `instanceColor` (the baked tint) multiplied by the per-face shade factor in the vertex colours.
  - Scene: fog `FogExp2('#12242B', 0.03)`, background of the same colour.
  - Instances: one `InstancedMesh` per mesh type and chunk. Visible chunks are the current stop's ±1, from nearest-stop distance.
  - Torches (built from the GLB nodes): staff and cup, plus three flame shells animated with per-shell noise (scaleY 0.9–1.08, rotZ ±3°) and yaw-billboarded to the camera; the crystal steady; an additive glow sprite made from a radial gradient `CanvasTexture`.
  - Lights: `THREE.Points` along the `flows` curves, moving at 0.6 m/s with additive point sprites (size 0.14 world units).
  - Water: `MeshBasicMaterial` with a streak `CanvasTexture` whose offset scrolls, plus foam with opacity pulsing.
  - Stars: `Points` with fog off.
  - Signs: the board mesh per sign plus a label plane carrying a canvas-text texture (Fraunces 700, burnt brown `#2A1A0F`), multiplied by the board's baked light.
  - Hover: raycast the ground plane; ferns within 2.6 m spring-rotate away (per-instance state for affected ferns only); the flame leans toward the pointer (≤ 12°).
  - Rock tooltips via `rockAt`.
- [ ] **Step 4: Implement `stage.js`.** Port the structure of Coalesce's `hero.js`: eligibility, lazy import, canvas, `ResizeObserver`, `IntersectionObserver`, pause, watchdog, context loss → `stop(reason)`, which leaves the still visible.
- [ ] **Step 5: Run the tests.** Expected: PASS.
- [ ] **Step 6: Commit** `feat: live 3D world with still fallback, pause and watchdog`.

### Task 8: Tour in live mode (walks and sign buttons)

**Files:**
- Modify: `public/js/tour.js`, `public/tour/index.html`
- Test: `tests/test_tour_live.py`

**Interfaces:**
- Consumes: `TourState`, `Walk`, `walkDuration`, `easeInOut`, `fitVerticalFov`, `WorldView.setPose`, `projectBox`, `rockAt`, and `mountStage(..., {variant:'tour'})`.
- Produces:
  - `body.dataset.tourIndex` and `body.dataset.tourWalking` ('true'/'false').
  - `window.__tour = {state, go(target)}`, for tests.

- [ ] **Step 1: Write the failing tests** (GPU browser):
  - With no hash, the tour starts at the trailhead, walks and arrives at stop 1 within 6 s; the card shows the Continuity title.
  - Pressing → five times fast during a walk ends at a single stop, with walking ending false and no stuck-hidden UI.
  - Sign button boxes sit within 40 px of the projected board boxes and inside the viewport at 1024×768 and 2560×1080.
  - Hovering the first rock at stop 1 shows a tooltip containing "429".
  - A forced stage stop mid-walk leaves the still at the target stop, the UI enabled and the buttons working.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - The `tour.js` live branch animates `Walk.poseAt(easeInOut(t/duration))` each frame.
  - It hides the card and signs while walking and restores them on arrival.
  - It positions the sign buttons each frame from `projectBox`.
  - Reduced motion never reaches live, so it needs no handling here.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: animated walks between tour stops`.

### Task 9: Verification screenshots and budgets

**Files:**
- Create: `tools/verify.py`

- [ ] **Step 1: Port Coalesce's `verify.py`.**
  - Baseline empty-page frame times.
  - Screenshots: home live, home hover, home paused, tour at each stop (after the walks), a mid-walk frame, help live, and reduced-motion versions of home, tour and help.
  - Budgets from the Global Constraints, including home transfer ≤ 2.5 MB and GLB/JSON/still sizes.
- [ ] **Step 2: Run** `.venv/Scripts/python tools/verify.py` in a headed browser, on the real GPU. Fix any budget failure: reduce scatter counts in the layout or lower the pixel ratio, then re-run.
- [ ] **Step 3: Review every screenshot by eye.** Fix composition, contrast and label legibility.
- [ ] **Step 4: Commit** `test: screenshot and budget verification; visual fixes`.

### Task 10: Delivery (README, CI job, release script, package)

**Files:**
- Create: `README.md`, `.gitlab-ci.yml`, `tools/package.py`, `tools/publish-release.ps1`
- Test: `tests/test_package.py`, `tests/test_publish_release.py`

- [ ] **Step 1: Write the failing tests** (ported from Coalesce):
  - The zip contains `blazeahead-site/public/index.html`, `blazeahead-site/SITE-README.md`, `blazeahead-site/blender/build_blazeahead.py` and `tools/publish-release.ps1`, but no `.venv`, `tests` or `__pycache__`.
  - The publish script's `-DryRun` output names `/packages/generic/blazeahead/<version>/blazeAhead.vsix` and the `direct_asset_path` `/blazeAhead.vsix`.
- [ ] **Step 2: Implement.**
  - README sections:
    - what's in the folder;
    - putting it on GitLab Pages;
    - editing `site-config.js` and `tour-content.js`;
    - publishing a VSIX release;
    - rebuilding the 3D (Blender);
    - local preview;
    - the defaults awaiting confirmation (spec §12).
  - CI job copied from Coalesce.
  - `package.py` builds `dist/blazeahead-site.zip`.
  - `publish-release.ps1` adapted for the `.vsix`.
- [ ] **Step 3: Run the full suite:** `pytest` (fast), then `pytest -m slow`. Expected: all pass.
- [ ] **Step 4: Commit** `docs: README, Pages job, release script and zip packager`.

### Task 11: Final review and fixes

- [ ] **Step 1: Run a whole-branch review** with superpowers:requesting-code-review. It covers correctness, accessibility, the budgets and the Review Focus list above.
- [ ] **Step 2: Fix the Important findings.** Record any deferred minors in the README's "Known limits".
- [ ] **Step 3: Rebuild the zip** and re-run `verify.py`. Commit `fix: final review`.

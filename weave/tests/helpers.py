"""Shared test helpers. pytest puts tests/ on sys.path, so test modules import this directly."""
import json
import struct
import zlib

LINEN = (243, 238, 228)
# The shipped panels' ids, in file order.
DEFAULT_IDS = ["manpower", "hiring", "training", "awards", "promotions", "travel", "feedback", "actions",
               "oversight", "access", "desks", "suggest"]


def collect_errors(page):
    """Record uncaught page errors and console errors from now on; returns the live list."""
    errors = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console.error: {msg.text}") if msg.type == "error" else None)
    return errors


def hero_result(page, timeout=20000):
    """Wait until the hero settles (live, or still for a reason other than loading); returns [state, reason]."""
    page.wait_for_function(
        "() => { const d = document.querySelector('[data-hero]')?.dataset;"
        " return !!d && !!d.heroState && d.heroReason !== 'loading'; }",
        timeout=timeout,
    )
    return page.eval_on_selector("[data-hero]", "el => [el.dataset.heroState, el.dataset.heroReason]")


def png_rows(png):
    """Decode an 8-bit RGB/RGBA, non-interlaced PNG (what Chromium screenshots are) into rows of bytes."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, header = 8, bytearray(), None
    while pos < len(png):
        length, kind = struct.unpack(">I4s", png[pos:pos + 8])
        chunk = png[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
    width, height, depth, color, _, _, interlace = header
    assert depth == 8 and color in (2, 6) and interlace == 0, header
    bpp = 3 if color == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(height):
        kind = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return width, height, bpp, rows


def jpeg_size(data):
    """(width, height) from a JPEG's baseline or progressive frame header (SOF0/SOF2): an independent reader, never
    the capture tool's."""
    assert data[:2] == b"\xff\xd8", data[:2]
    pos = 2
    while pos + 4 <= len(data):
        assert data[pos] == 0xFF, (pos, data[pos])
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if marker in (0xC0, 0xC2):
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return width, height
        pos += 2 + length
    raise AssertionError("no SOF0/SOF2 marker")


def ink_fraction(png, background=LINEN, tolerance=40):
    """Share of pixels in a screenshot that clearly differ from the page's linen paper colour."""
    width, height, bpp, rows = png_rows(png)
    differ = 0
    for row in rows:
        for x in range(0, width * bpp, bpp):
            if abs(row[x] - background[0]) + abs(row[x + 1] - background[1]) + abs(row[x + 2] - background[2]) > tolerance:
                differ += 1
    return differ / (width * height)


STATIC_LABEL = ("A quilt of twelve blocks, one for each WEAVE dashboard panel: "
                "some sewn in, others pinned in place for later releases.")
HOME = "/public/index.html"


PANEL_WARNING_PREFIXES = ("WEAVE: panels.js ", "WEAVE: the live panel ")

# The release rules' warnings (#12): their own family, disjoint from PANEL_WARNING_PREFIXES. Written out here, never
# read from release.js, so a reworded warning fails the tests.
RELEASE_WARNING_PREFIX = "WEAVE: news: "
W_NEWS_VERSION = ("WEAVE: news: release.version in panels.js must be a version string such as '1.1', "
                  "so no panel is new.")
W_NEWS_DATE = "WEAVE: news: release.date in panels.js must be a real day written YYYY-MM-DD, so no panel is new."
W_NEWS_WINDOW = "WEAVE: news: newsWindowDays in panels.js must be a whole number from 1 to 60, so no panel is new."
W_NEWS_SINCE = ("WEAVE: news: the live panel '{id}' has a malformed since (write a string such as '1.1'), "
                "so it is never new.")
W_NEWS_NOW = "WEAVE: news: ?now= must be a real day written YYYY-MM-DD, so it is ignored and today is the local date."
# The two lastSeen keys: real visits, and visits with ?now=, ?whatsnew or ?pose=rest.
LAST_SEEN_KEY = "weave.lastSeenRelease"
SIM_KEY = "weave.lastSeenRelease.sim"

# --- Painting helpers (#6): console collection, font warnings, canvas hashing. ---

FONT_WARNING_PREFIX = "WEAVE: the web font"


def collect_warnings(page, prefixes, warnings=None):
    """Record console warnings starting with `prefixes` (a str or tuple) into `warnings` (a new list if None);
    returns it."""
    warnings = [] if warnings is None else warnings
    page.on("console", lambda msg: warnings.append(msg.text)
            if msg.type == "warning" and msg.text.startswith(prefixes) else None)
    return warnings


def collect_console(page, messages=None):
    """Record every console message from now on as (type, text) into `messages` (a new list if None); returns it."""
    messages = [] if messages is None else messages
    page.on("console", lambda msg: messages.append((msg.type, msg.text)))
    return messages


def font_warnings(messages):
    """The font-wait warnings among collected (type, text) console messages."""
    return [text for kind, text in messages if kind == "warning" and text.startswith(FONT_WARNING_PREFIX)]


# Links weave.css (its @font-face rules) into a blank page and waits for the stylesheet.
LINK_CSS = r"""
    await new Promise((resolve, reject) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/public/css/weave.css';
      link.onload = resolve;
      link.onerror = reject;
      document.head.append(link);
    });
"""

# The one definition of the canvas checks, for any evaluate body: sha256Canvas(c) hashes the canvas's RGBA bytes;
# isUniform(c) is true when every pixel is equal; canvasKey(c) names a faces-page canvas as face:<slot> |
# tile:<slot> | texture:<name>.
CANVAS_JS = r"""
    const sha256Canvas = async (c) => {
      const bytes = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
      return [...digest].map((b) => b.toString(16).padStart(2, '0')).join('');
    };
    const isUniform = (c) => {
      const px = new Uint32Array(c.getContext('2d').getImageData(0, 0, c.width, c.height).data.buffer);
      return px.every((v) => v === px[0]);
    };
    const canvasKey = (c) => (c.dataset.texture !== undefined ? `texture:${c.dataset.texture}`
      : `${c.dataset.kind === 'tile' ? 'tile' : 'face'}:${c.dataset.slot}`);
"""

# The same checks as page globals, for paint_js bodies.
SHA256_JS = CANVAS_JS + "window.sha256Canvas = sha256Canvas; window.isUniform = isUniform;"


def open_paint(make_page, base_url, **context_args):
    """A blank page in a fresh context with weave.css's fonts loaded (fontsReady() must say true) and the hash
    helpers defined; returns run(body), with run.page and run.console (every (type, text) since before the wait)."""
    page = make_page(**context_args)
    messages = collect_console(page)
    # A failed module or font fetch otherwise surfaces only as "Failed to fetch dynamically imported module".
    failed = []
    page.on("requestfailed", lambda request: failed.append(f"{request.url} {request.failure}"))
    page.goto(f"{base_url}/tests/blank.html")
    try:
        ok = page.evaluate(f"async () => {{ {LINK_CSS} {SHA256_JS}"
                           " return (await import('/public/js/tiles.js')).fontsReady(); }")
    except Exception as exc:
        raise AssertionError(f"paint page setup failed; failed requests: {failed}") from exc
    assert ok is True, (font_warnings(messages), failed)

    def run(body):
        return page.evaluate(f"async () => {{ {body} }}")

    run.page = page
    run.console = messages
    return run


FACES = "/dev/faces.html"


def open_faces(make_page, base_url, panels_body=None, wait_until="load", before_goto=None, messages=None,
               wait_painted=True, **context_args):
    """Open the dev faces page and wait until it has painted (body[data-painted]); returns (page, errors).

    `panels_body` swaps panels.js as in open_page. `before_goto(page)` runs after that route and before
    navigation: routes, clock.set_fixed_time and init scripts all go through this one door. Pass a list as
    `messages` to collect every (type, text) console message into it. The font tests hold a font (which
    blocks `load`), so they pass wait_until="commit" and wait_painted=False and time the paint themselves.
    """
    page = make_page(**context_args)
    errors = collect_errors(page)
    if messages is not None:
        collect_console(page, messages)
    if panels_body is not None:
        page.route("**/panels.js", lambda route: route.fulfill(content_type="text/javascript", body=panels_body))
    if before_goto is not None:
        before_goto(page)
    page.goto(base_url + FACES, wait_until=wait_until)
    if wait_painted:
        page.wait_for_selector("body[data-painted]", state="attached", timeout=15000)
    return page, errors


# Every painted canvas on the faces page as face:<slot> | tile:<slot> | texture:<name> -> SHA-256 of its bytes.
PAGE_CANVASES = "[...document.querySelectorAll('canvas[data-slot], canvas[data-texture]')]"

CANVAS_HASHES = f"""async () => {{ {CANVAS_JS}
    const out = {{}};
    for (const c of {PAGE_CANVASES}) out[canvasKey(c)] = await sha256Canvas(c);
    return out;
}}"""


def canvas_hashes(page):
    return page.evaluate(CANVAS_HASHES)


def uniform_canvases(page):
    """Keys (as canvas_hashes names them) of canvases whose every pixel is the same."""
    return page.evaluate(f"() => {{ {CANVAS_JS} return {PAGE_CANVASES}.filter(isUniform).map(canvasKey); }}")


# Loads the shipped panels.js (once per page) and binds DEFAULTS to its entries through #5's cleanPanels.
DEFAULTS_JS = r"""
    if (!window.WEAVE_PANELS) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = '/public/panels.js';
        s.onload = resolve;
        s.onerror = reject;
        document.head.append(s);
      });
    }
    const DEFAULTS = (await import('/public/js/catalog.js')).cleanPanels(window.WEAVE_PANELS).panels;
"""


def hidden_by_attribute(locator):
    """True when the element carries `hidden` AND that actually removes it from layout (not just an empty box)."""
    return locator.evaluate("el => el.hidden === true && getComputedStyle(el).display === 'none'")


def open_page(make_page, base_url, panels_body=None, warnings=None, **context_args):
    """Open the WEAVE page, optionally with panels.js swapped for `panels_body`; returns (page, errors).

    Pass a list as `warnings` to collect the panel-list console warnings (only those families) into it.
    Reduced motion is the default, so list tests never request Three.js and test_hero.py alone owns the hero.
    """
    context_args.setdefault("reduced_motion", "reduce")
    page = make_page(**context_args)
    errors = collect_errors(page)
    if warnings is not None:
        collect_warnings(page, PANEL_WARNING_PREFIXES, warnings)
    if panels_body is not None:
        page.route("**/panels.js", lambda route: route.fulfill(content_type="text/javascript", body=panels_body))
    page.goto(base_url + HOME)
    page.wait_for_load_state("networkidle")
    return page, errors


# --- The Help page (#17). Its tests never read the committed site-config.js values: they route a fixture. ---

HELP = "/public/help/"
FILLED_SITE = {"teamName": "Workforce Systems",
               "links": {"serviceDesk": "https://desk.example.com/portal/7", "tutorial": "https://learn.example.com/weave",
                         "docs": "https://docs.example.com/weave"}}
EMPTY_SITE = {"teamName": "", "links": {"serviceDesk": "", "tutorial": "", "docs": ""}}
SITE_SYNTAX_ERROR = "window.WEAVE_SITE = {"
NOT_FOUND = object()
CARD_KEYS = ["serviceDesk", "tutorial", "docs"]
CARD_TITLES = ["Report a problem", "Take the tutorial", "Read the docs"]


def site_body(cfg):
    """A site-config.js body that sets window.WEAVE_SITE to `cfg`."""
    return f"window.WEAVE_SITE = {json.dumps(cfg)};"


def open_help(make_page, base_url, site=EMPTY_SITE, path=HELP, **context_args):
    """Open the Help page with site-config.js routed to `site`; returns (page, errors).

    `site` is a dict (served as settings), a str (the raw body), NOT_FOUND (a 404) or None (no route, so the
    committed file loads). Whenever it routes, it asserts the route ran exactly once: a route that never matched
    would let the empty-settings tests pass against the committed empty file.
    """
    context_args.setdefault("reduced_motion", "reduce")
    page = make_page(**context_args)
    errors = collect_errors(page)
    fired = []
    if site is not None:
        if site is NOT_FOUND:
            reply = {"status": 404, "content_type": "text/plain", "body": "Not found"}
        else:
            reply = {"content_type": "text/javascript", "body": site_body(site) if isinstance(site, dict) else site}

        def handle(route):
            fired.append(route.request.url)
            route.fulfill(**reply)

        page.route("**/site-config.js", handle)
    page.goto(base_url + path)
    page.wait_for_load_state("networkidle")
    if site is not None:
        assert len(fired) == 1, f"the site-config.js route ran {len(fired)} times: {fired}"
    return page, errors


# --- The live hero (#7). ---

LOAD_FAILED = "WEAVE: the 3D quilt could not load, so the still image stays."
WEBGL_FAILED = "WEAVE: WebGL setup failed, so the still image stays."
PAUSE_NAME = "Pause motion"
STILL_HINT = "Your browser shows a picture of the quilt. The panels below have everything."

# --- The toggle and the live hint (#8): literals from the issue, never imported from dom.js, so a reworded
# constant fails here. ---

UNSTITCH_NAME = "Unstitch"
SEW_NAME = "Sew it back"
QUILT_HINT = ("Click the quilt, or press Unstitch, to lay its blocks out as a dashboard; in the dashboard, drag a tile"
              " to move it.")
TILES_HINT = "Click the background, or press Sew it back, to sew the quilt together again."

# --- The hover tooltip's status words (#10), by drawn face: literals from the issue, never imported from dom.js. ---

SEWN_WORDS = "Sewn in"
PLANNED_WORDS = "Pinned for later"
SUGGEST_WORDS = "Have an idea for a panel?"

# An init script: a weave:mode listener on [data-hero] from the moment it is parsed (before the scene goes live),
# pushing { mode, from, hook: __weave.mode, data: data-mode, t: performance.now() } to window.__modes, then calling
# window.__onMode(event, stage) if a test defined it; and every data-mode value the stage ever takes (old and new) to
# window.__dataModes.
MODE_LOG = r"""
    window.__modes = [];
    window.__dataModes = [];
    const attach = (el) => {
      if (el.__modeLog) return;
      el.__modeLog = true;
      el.addEventListener('weave:mode', (event) => {
        window.__modes.push({ mode: event.detail.mode, from: event.detail.from,
                              hook: el.__weave ? el.__weave.mode : null, data: el.dataset.mode ?? null,
                              t: performance.now() });
        if (window.__onMode) window.__onMode(event, el);
      });
      new MutationObserver((records) => {
        for (const r of records) window.__dataModes.push(r.oldValue);
        window.__dataModes.push(el.dataset.mode ?? null);
      }).observe(el, { attributes: true, attributeFilter: ['data-mode'], attributeOldValue: true });
    };
    new MutationObserver(() => {
      const el = document.querySelector('[data-hero]');
      if (el) attach(el);
    }).observe(document, { childList: true, subtree: true });
"""


def log_modes(page):
    """open_live's before_goto for MODE_LOG."""
    page.add_init_script(MODE_LOG)


def modes(page):
    """The weave:mode record as (mode, from) pairs."""
    return [(e["mode"], e["from"]) for e in page.evaluate("window.__modes")]


def wait_for_data_mode(page, mode, timeout=10000):
    page.wait_for_function("(mode) => document.querySelector('[data-hero]').dataset.mode === mode", arg=mode,
                           timeout=timeout)


# --- The intro (#10): a plain load plays it before the quilt settles, so a test that needs the settled quilt waits. ---

# The settled quilt: data-mode and __weave.mode both quilt. Synchronous (a returned Promise reads as truthy; Issue-9),
# and byte-equal to tools/verify.py's.
QUILT_SETTLED = ("() => { const el = document.querySelector('[data-hero]');"
                 " return el?.dataset.mode === 'quilt' && el.__weave?.mode === 'quilt'; }")
# A plain load's first two weave:mode entries.
PLAIN_START = [("intro", None), ("quilt", "intro")]
DECOR_IDLE = "() => document.querySelector('[data-hero]').__weave.decorIdle === true"
SNAP_JSON = "el => JSON.stringify(el.__weave.snapshot())"
# Every hover negative waits this long; its positive control polls within the same window (weave Issue-8).
HOVER_WINDOW_MS = 500


def wait_for_quilt(page, timeout=15000):
    """Wait until the quilt has settled in quilt mode. D12's budget: 4 s to go live, 4 s of intro, 5 s for E2's
    sew-in and 2 s spare."""
    page.wait_for_function(QUILT_SETTLED, timeout=timeout)


def wait_for_decor(page, timeout=5000):
    """Wait until no stitch or pin animation is running."""
    page.wait_for_function(DECOR_IDLE, timeout=timeout)


def wait_for_mode(page, mode, timeout=10000):
    page.wait_for_function("(mode) => document.querySelector('[data-hero]').__weave.mode === mode", arg=mode,
                           timeout=timeout)


def project(page, xyz):
    """The client (CSS pixel) point where the world point `xyz` projects (through __weave.project)."""
    return page.eval_on_selector("[data-hero]", "(el, p) => el.__weave.project(p)", xyz)


def click_world(page, xyz):
    """Click the canvas where the world point `xyz` projects."""
    page.mouse.click(*project(page, xyz))


# seams(snap, L, nudge = 0): every block that is not planned has each of its 160 edge vertices within 1e-4 (3D) of a
# sashing vertex, from one snapshot, and each block's centre against its quilt slot (off). nudge adds to block slot 0's
# x before matching, so a planted control can redden it.
SEAMS_JS = r"""
    const seams = (snap, L, nudge = 0) => {
      const sp = snap.sashing.positions;
      let checked = 0; let missing = 0; let off = 0;
      for (const b of snap.blocks) {
        const p = b.positions;
        const mean = [0, 1].map((k) => [0, 40, 1640, 1680].reduce((s, j) => s + p[3 * j + k], 0) / 4);
        off = Math.max(off, ...mean.map((v, k) => Math.abs(v - L.slotCentre(b.slot)[k])));
        if (b.face === 'planned') continue;
        const dx = b.slot === 0 ? nudge : 0;
        for (let r = 0; r <= 40; r += 1) {
          for (let c = 0; c <= 40; c += 1) {
            if (r !== 0 && r !== 40 && c !== 0 && c !== 40) continue;
            const j = 3 * (r * 41 + c);
            checked += 1;
            let hit = false;
            for (let k = 0; k < sp.length && !hit; k += 3) {
              hit = Math.hypot(sp[k] - p[j] - dx, sp[k + 1] - p[j + 1], sp[k + 2] - p[j + 2]) <= 1e-4;
            }
            if (!hit) missing += 1;
          }
        }
      }
      return { checked, missing, off };
    };
"""
# eval_on_selector bodies: SEAMS on a fresh snapshot; SEAMS_OF on a snapshot stored as window[name], with a nudge.
SEAMS = f"""async (el) => {{ const L = await import('/public/js/layout.js'); {SEAMS_JS}
    return seams(el.__weave.snapshot(), L); }}"""
SEAMS_OF = f"""async (el, [name, nudge]) => {{ const L = await import('/public/js/layout.js'); {SEAMS_JS}
    return seams(window[name], L, nudge); }}"""


# The four geometry checks per block from one snapshot: flat (one z), flipped (the first triangle faces away from the
# camera), square (corners 0/40 share y, 0/1640 share x) and centred (the corner mean against the tile slot).
TILE_GEOMETRY_JS = r"""
    const tileGeometry = (snap, centreOf) => snap.blocks.map((b, i) => {
      const p = b.positions;
      const v = (j) => p.slice(3 * j, 3 * j + 3);
      const zs = []; for (let j = 2; j < p.length; j += 3) zs.push(p[j]);
      const [a, bb, c] = [0, 1, 2].map((k) => v(b.indices[k]));
      const u = a.map((x, k) => bb[k] - x); const w = a.map((x, k) => c[k] - x);
      const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
      const facing = n.reduce((s, x, k) => s + x * (snap.camera.position[k] - a[k]), 0);
      const corners = [0, 40, 1640, 1680].map(v);
      const mean = [0, 1, 2].map((k) => corners.reduce((s, q) => s + q[k], 0) / 4);
      const want = [...centreOf(i), 0];
      return { flat: Math.max(...zs) - Math.min(...zs), facing,
               square: Math.max(Math.abs(corners[0][1] - corners[1][1]), Math.abs(corners[0][0] - corners[2][0])),
               centre: Math.max(...mean.map((x, k) => Math.abs(x - want[k]))) };
    });
"""


def assert_tile_geometry(blocks):
    for i, g in enumerate(blocks):
        assert g["flat"] <= 1e-6 and g["facing"] < 0 and g["square"] <= 1e-6 and g["centre"] <= 1e-6, (i, g)


def open_live(make_page, base_url, query="?nowatchdog", panels_body=None, before_goto=None, **context_args):
    """Open the WEAVE page on desktop and wait until the quilt is live; returns (page, errors).

    Routes `panels_body` like open_page; `before_goto(page)` runs after that route and before navigation (routes,
    clock.set_fixed_time and init scripts). The stage is scrolled into view, so the loop is running on return.
    """
    page = make_page(**context_args)
    errors = collect_errors(page)
    if panels_body is not None:
        page.route("**/panels.js", lambda route: route.fulfill(content_type="text/javascript", body=panels_body))
    if before_goto is not None:
        before_goto(page)
    page.goto(base_url + HOME + query)
    assert hero_result(page) == ["live", "ok"], errors
    page.locator("[data-hero]").scroll_into_view_if_needed()
    return page, errors


# --- The release object (#12). ---

# Synchronous on purpose: a returned Promise reads as truthy (Issue-9).
RELEASE_READY = "() => !!document.querySelector('[data-hero]')?.__weaveRelease"
RELEASE_STATE = "el => { const { recordSeen, ...state } = el.__weaveRelease; return state; }"
# How far Date.now() moves across a 200 ms timer: about 200 on a real clock, 0 on a pinned one.
CLOCK_ADVANCE = ("async () => { const a = Date.now(); await new Promise((r) => setTimeout(r, 200));"
                 " return Date.now() - a; }")
# A YYYY-MM-DD date literal in the 1900s or 2000s, for the tools' source guards.
DATE_LITERAL_RE = r"(19|20)\d\d-[01]\d-[0-3]\d"


def open_release(make_page, base_url, query="", panels_body=None, before_goto=None, **context_args):
    """Open the WEAVE page at `query` and wait for stage.__weaveRelease; returns (page, errors, warnings).

    `warnings` collects the release (WEAVE: news: ) console warnings. Reduced motion is the default, so the page takes
    the still path and never loads Three. Routes `panels_body` and runs `before_goto(page)` as open_live does.
    """
    context_args.setdefault("reduced_motion", "reduce")
    page = make_page(**context_args)
    errors = collect_errors(page)
    warnings = collect_warnings(page, RELEASE_WARNING_PREFIX)
    if panels_body is not None:
        page.route("**/panels.js", lambda route: route.fulfill(content_type="text/javascript", body=panels_body))
    if before_goto is not None:
        before_goto(page)
    page.goto(base_url + HOME + query)
    page.wait_for_function(RELEASE_READY)
    return page, errors, warnings


def release_keys(page):
    """stage.__weaveRelease's own keys, sorted."""
    return page.eval_on_selector("[data-hero]", "el => Object.keys(el.__weaveRelease).sort()")


def release_state(page):
    """stage.__weaveRelease without recordSeen: { today, force, key, lastSeen, newIds, taggedIds }."""
    return page.eval_on_selector("[data-hero]", RELEASE_STATE)


def record_seen(page):
    """Calls stage.__weaveRelease.recordSeen() and returns what it returned."""
    return page.eval_on_selector("[data-hero]", "el => el.__weaveRelease.recordSeen()")


def live_quilt(make_page, base_url, **kwargs):
    """open_live, then wait until the intro has settled into the quilt; returns (page, errors)."""
    page, errors = open_live(make_page, base_url, **kwargs)
    wait_for_quilt(page)
    return page, errors


def frames(page):
    """The live loop's counted frames (data-hero-frames)."""
    return page.eval_on_selector("[data-hero]", "el => Number(el.dataset.heroFrames || 0)")


def rising(page, wait=600):
    """Whether the live loop counts more frames after `wait` ms."""
    before = frames(page)
    page.wait_for_timeout(wait)
    return frames(page) > before


def weave(page, expr):
    """Evaluate `el.__weave<expr>` on the stage, e.g. weave(page, '.clock')."""
    return page.eval_on_selector("[data-hero]", f"el => el.__weave{expr}")


def corner_z(page, slot):
    """The world z of block `slot`'s four corner vertices, from the page's snapshot()."""
    return page.eval_on_selector("[data-hero]", "(el, slot) => { const p = el.__weave.snapshot().blocks[slot].positions;"
                                 " return [0, 40, 1640, 1680].map((j) => p[3 * j + 2]); }", slot)


def wait_for_reason(page, reason, timeout=20000):
    """Wait for a runtime fallback's reason (port of coalesce/tests/test_hero.py's wait on heroReason): hero_result
    returns at live/ok, before any runtime fallback has happened."""
    page.wait_for_function("(reason) => document.querySelector('[data-hero]')?.dataset.heroReason === reason",
                           arg=reason, timeout=timeout)


# --- Panel-list fixtures shared by test_catalog.py (pure) and test_robustness.py (page). ---

W_OBJECT = "WEAVE: panels.js entry {n} was skipped: it is not an object."
W_ID = "WEAVE: panels.js entry {n} was skipped: its id must be a non-empty string."
W_NAME = "WEAVE: panels.js entry {n} was skipped: its name must be a non-empty string."
W_STATUS = "WEAVE: panels.js entry {n} was skipped: its status must be 'live', 'planned' or 'suggest'."
E1 = ("WEAVE: the panel list (window.WEAVE_PANELS from panels.js) is missing or is not an object. "
      "Check panels.js for a syntax error.")
E2 = "WEAVE: WEAVE_PANELS.panels in panels.js is not an array."
W_DUP = "WEAVE: panels.js entry {n} was skipped: the id '{id}' is already used (the first one is kept)."
W_SAMPLE = "WEAVE: the live panel '{id}' has no valid sample, so it reads \"No sample yet\"."
W_MANY = "WEAVE: panels.js has {count} valid panels; the quilt draws the first 12."
VALID = "{ id: 'ok', name: 'Okay', status: 'planned', sample: null }"

# (id, JS literal of the bad entry, message template): one per malformed kind, pure and page.
MALFORMED = [
    ("object-null", "null", W_OBJECT),
    ("object-number", "7", W_OBJECT),
    ("object-string", "'x'", W_OBJECT),
    ("object-array", "[]", W_OBJECT),
    ("id-missing", "{ name: 'No id', status: 'live' }", W_ID),
    ("id-blank", "{ id: '  ', name: 'Blank id', status: 'live' }", W_ID),
    ("id-number", "{ id: 7, name: 'Seven', status: 'live' }", W_ID),
    ("name-missing", "{ id: 'a', status: 'live' }", W_NAME),
    ("name-blank", "{ id: 'a', name: '  ', status: 'live' }", W_NAME),
    ("name-number", "{ id: 'a', name: 7, status: 'live' }", W_NAME),
    ("status-unknown", "{ id: 'a', name: 'A', status: 'archived' }", W_STATUS),
    ("status-case", "{ id: 'a', name: 'A', status: 'Live' }", W_STATUS),
    ("status-missing", "{ id: 'a', name: 'A' }", W_STATUS),
]


# --- Focus and contrast checks (reused by later children, e.g. #10's tooltip and #14's badge). ---

FOCUS_TARGETS = r"""() => {
    const targets = [...document.querySelectorAll('a[href], button:not([disabled])')].filter((el) =>
        el.getClientRects().length > 0 && !el.closest('[hidden]') && getComputedStyle(el).visibility !== 'hidden');
    targets.forEach((el, i) => { el.dataset.focusProbe = String(i); });
    if (document.activeElement) document.activeElement.blur();
    return targets.map((el) => `${el.tagName.toLowerCase()} "${el.textContent.trim()}" ${el.getAttribute('href') ?? ''}`.trim());
}"""

FOCUSED = r"""() => {
    const el = document.activeElement;
    const style = getComputedStyle(el);
    return [el.dataset.focusProbe ?? null, style.outlineStyle, parseFloat(style.outlineWidth) || 0];
}"""


def focus_failures(page):
    """Tab through every rendered link and button; describe those with no visible (>= 2 px) outline or never reached."""
    targets = page.evaluate(FOCUS_TARGETS)
    assert targets, "no rendered link or button to tab through"
    outlines = {}
    for _ in range(len(targets) + 2):
        page.keyboard.press("Tab")
        probe, style, width = page.evaluate(FOCUSED)
        if probe is not None:
            outlines.setdefault(int(probe), (style, width))
    failures = []
    for i, description in enumerate(targets):
        if i not in outlines:
            failures.append(f"not reached by Tab: {description}")
        elif outlines[i][0] == "none" or outlines[i][1] < 2:
            failures.append(description)
    return failures


# Coalesce's CONTRAST luminance, background walk and opacity, over every element that directly holds text.
CONTRAST = r"""() => {
    const lum = (c) => {
      const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(Number).map((v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const background = (el) => {
      for (let e = el; e; e = e.parentElement) {
        const c = getComputedStyle(e).backgroundColor;
        if (c !== 'transparent' && !c.startsWith('rgba(0, 0, 0, 0)')) return c;
      }
      return 'rgb(243, 238, 228)';
    };
    const opacity = (el) => {
      let o = 1;
      for (let e = el; e; e = e.parentElement) o *= Number(getComputedStyle(e).opacity);
      return o;
    };
    const holdsText = (el) => [...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
    const checked = [...document.body.querySelectorAll('*')].filter((el) => holdsText(el)
      && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden');
    const failures = [];
    for (const el of checked) {
      const style = getComputedStyle(el);
      const a = lum(style.color);
      const b = lum(background(el));
      const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      const size = parseFloat(style.fontSize);
      const weight = Number(style.fontWeight);
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      if (opacity(el) < 1 || ratio < (large ? 3 : 4.5)) {
        failures.push({ text: el.textContent.trim().slice(0, 60), ratio: Math.round(ratio * 100) / 100, size, weight });
      }
    }
    return { checked: checked.length, failures };
}"""


def contrast_failures(page):
    """Every rendered text element under 4.5:1 (3:1 when large), or not fully opaque; fails closed below 10 checked."""
    result = page.evaluate(CONTRAST)
    assert result["checked"] >= 10, f"only {result['checked']} text elements checked"
    return result["failures"]

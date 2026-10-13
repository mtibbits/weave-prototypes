"""Shared test helpers. pytest puts tests/ on sys.path, so test modules import this directly."""
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

# --- Painting helpers (#6): console collection, font warnings, canvas hashing. ---

FONT_WARNING_PREFIX = "WEAVE: the web font"


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
        page.on("console", lambda msg: warnings.append(msg.text)
                if msg.type == "warning" and msg.text.startswith(PANEL_WARNING_PREFIXES) else None)
    if panels_body is not None:
        page.route("**/panels.js", lambda route: route.fulfill(content_type="text/javascript", body=panels_body))
    page.goto(base_url + HOME)
    page.wait_for_load_state("networkidle")
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
QUILT_HINT = "Click the quilt, or press Unstitch, to lay its blocks out as a dashboard."
TILES_HINT = "Click the background, or press Sew it back, to sew the quilt together again."


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

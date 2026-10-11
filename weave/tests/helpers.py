"""Shared test helpers. pytest puts tests/ on sys.path, so test modules import this directly."""
import struct
import zlib

LINEN = (243, 238, 228)


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


# --- Panel-list fixtures shared by test_catalog.py (pure) and test_robustness.py (page). ---

W_OBJECT = "WEAVE: panels.js entry {n} was skipped: it is not an object."
W_ID = "WEAVE: panels.js entry {n} was skipped: its id must be a non-empty string."
W_NAME = "WEAVE: panels.js entry {n} was skipped: its name must be a non-empty string."
W_STATUS = "WEAVE: panels.js entry {n} was skipped: its status must be 'live', 'planned' or 'suggest'."
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

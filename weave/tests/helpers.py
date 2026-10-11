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

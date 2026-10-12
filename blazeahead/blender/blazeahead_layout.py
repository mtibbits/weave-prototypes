"""The blazeAhead world: one pure-Python description shared by Blender (meshes, stills) and the website (world.json).

Everything here is deterministic and uses Blender's axes: x east, y north, z up, metres. `to_web()` converts to the
browser's Y-up axes. Nothing here imports bpy, so plain pytest can test it.

The world is a winding forest path. It starts at the trailhead (the home page's view) and passes four tour stops.
Each stop has a local frame: an origin on the path and a heading (the walking direction). The stop's scene (its
"vignette") sits on the left of the walking direction. Its camera stands STOP_BACK metres to the right of the path,
looking left across the path at the vignette. The walking direction therefore runs left to right on screen: the
previous topic's sign is on the left edge and the next topic's sign is on the right edge.
"""
import math
import random
import re

STOP_IDS = ["continuity", "scaffolding", "knowledge", "in-flight"]
STOP_SPACING = 24.0      # metres between stop origins, roughly (the path winds a little more than that)
EYE = 1.25               # camera height at a stop
WALK_EYE = 1.6           # camera height while walking
STOP_BACK = 2.6          # stop camera distance to the right of the path
STOP_HFOV = 64.0         # horizontal field of view of stop views, degrees (fitted to the window's width)
TRAILHEAD_HFOV = 60.0
JUNCTION_HFOV = 60.0
PATH_HALF = 0.62         # half-width of the dirt path
CORRIDOR = 32.0          # scatter only this far from the path
GROUND_REACH = 20.0      # the ground mesh covers this far from the path
GROUND_CELL = 1.1

# the log signpost the owner described: a 6-inch log, 3 ft above ground, a 1x6x18 board cut to an arrow
POST_R, POST_H = 0.076, 0.914
BOARD_L, BOARD_T, BOARD_W, BOARD_TAIL = 0.457, 0.019, 0.14, 0.10
BOARD_H = 0.80           # board centre height above ground
LABEL_ALONG = 0.095      # label centre, measured from the post axis along the arrow

# our own flame: three nested outlines (x across, y up, flame base at 0) and a blue crystal at its heart
FLAME_OUTER = [(0, 0), (0.30, 0.05), (0.50, 0.25), (0.56, 0.52), (0.50, 0.80), (0.40, 1.00), (0.47, 1.28),
               (0.47, 1.28), (0.24, 1.08), (0.16, 1.32), (0.06, 1.55), (-0.04, 1.80), (-0.04, 1.80),
               (-0.14, 1.52), (-0.22, 1.28), (-0.26, 1.12), (-0.42, 1.30), (-0.42, 1.30), (-0.50, 1.02),
               (-0.56, 0.70), (-0.52, 0.38), (-0.36, 0.10), (-0.16, 0.0)]
FLAME_MID = [(0, 0.12), (0.28, 0.20), (0.40, 0.44), (0.38, 0.70), (0.28, 0.92), (0.30, 1.10), (0.30, 1.10),
             (0.14, 0.98), (0.06, 1.20), (-0.02, 1.42), (-0.02, 1.42), (-0.12, 1.16), (-0.24, 0.96),
             (-0.36, 0.72), (-0.40, 0.46), (-0.30, 0.22)]
FLAME_INNER = [(0, 0.22), (0.20, 0.28), (0.26, 0.48), (0.22, 0.70), (0.12, 0.90), (0.0, 1.08), (0.0, 1.08),
               (-0.12, 0.90), (-0.22, 0.70), (-0.26, 0.48), (-0.20, 0.28)]
FLAME_HEIGHT = 1.80
TORCH_H = 1.30           # torch staff height above ground
TORCH_FLAME_SCALE = 0.26
TRAIL_TORCH_FLAME_SCALE = 0.24

PALETTE = {
    "moss": "#1B2A1E", "moss2": "#26382A", "dirt": "#5E4A39", "bed": "#1A2522",
    "bark": "#3A2F29", "bark2": "#2A2320", "leaf": "#1D3E26", "leaf2": "#16301F", "canopy": "#10251A",
    "fern": "#2E5A35", "fern2": "#47753C", "wood": "#8E7D63", "wood2": "#6C5D4A", "post": "#5E4D3E",
    "iron": "#2A2522", "amber": "#FFB23F", "blue": "#4AA8FF",
}


# ---------------------------------------------------------------- small maths

def lin(hexstr):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def norm2(x, y):
    d = math.hypot(x, y) or 1.0
    return x / d, y / d


def norm3(v):
    d = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / d for c in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def quat_axis_angle(axis, angle):
    ax = norm3(axis)
    s = math.sin(angle / 2)
    return (math.cos(angle / 2), ax[0] * s, ax[1] * s, ax[2] * s)


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


def quat_yaw(a):
    return (math.cos(a / 2), 0.0, 0.0, math.sin(a / 2))


def quat_tilt_yaw(tilt, yaw):
    """Rotate about z by yaw, then tip +z toward the 2D direction of `tilt` by |tilt| radians."""
    q = quat_yaw(yaw)
    t = math.hypot(*tilt)
    if t < 1e-6:
        return q
    return quat_mul(quat_axis_angle((-tilt[1], tilt[0], 0.0), t), q)


def quat_to(direction):
    """Rotation taking +z onto `direction`."""
    d = norm3(direction)
    c = d[2]
    if c > 0.999999:
        return (1.0, 0.0, 0.0, 0.0)
    if c < -0.999999:
        return (0.0, 1.0, 0.0, 0.0)
    return quat_axis_angle(cross((0.0, 0.0, 1.0), d), math.acos(c))


# ---------------------------------------------------------------- terrain

_PERM = list(range(256))
random.Random(1337).shuffle(_PERM)
_PERM += _PERM


def _hash(ix, iy):
    return _PERM[(_PERM[ix & 255] + iy) & 255] / 255.0


def value_noise(x, y):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy), _hash(ix + 1, iy)
    c, d = _hash(ix, iy + 1), _hash(ix + 1, iy + 1)
    return (a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy) * 2 - 1


def height(x, y, flat=()):
    h = 0.45 * value_noise(x * 0.08 + 11.3, y * 0.08 + 7.1) + 0.1 * value_noise(x * 0.3 + 3.7, y * 0.3 + 1.9)
    for (cx, cy), r in flat:
        h *= min(1.0, max(0.12, math.hypot(x - cx, y - cy) / r))
    return h


# ---------------------------------------------------------------- splines

def catmull(ctrl, per_seg=16):
    pts = [tuple(p) for p in ctrl]
    dim = len(pts[0])
    ext = [tuple(2 * a - b for a, b in zip(pts[0], pts[1]))] + pts + [tuple(2 * a - b for a, b in zip(pts[-1], pts[-2]))]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per_seg):
            t = k / per_seg
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t * t * t) for j in range(dim)))
    out.append(pts[-1])
    return out


def resample(poly, step):
    res = [poly[0]]
    carry = 0.0
    for a, b in zip(poly, poly[1:]):
        seg = math.dist(a, b)
        if seg < 1e-9:
            continue
        d = step - carry
        while d <= seg + 1e-12:
            t = d / seg
            res.append(tuple(x + (y - x) * t for x, y in zip(a, b)))
            d += step
        carry = seg - (d - step)
    return res


def _ring(cx, cy, r):
    """Grid cells at Chebyshev distance exactly r from (cx, cy)."""
    if r == 0:
        yield (cx, cy)
        return
    for gx in range(cx - r, cx + r + 1):
        yield (gx, cy - r)
        yield (gx, cy + r)
    for gy in range(cy - r + 1, cy + r):
        yield (cx - r, gy)
        yield (cx + r, gy)


class Spline:
    """A 2D path through control points, resampled every `step` metres, with fast nearest-point queries."""

    CELL = 2.0

    def __init__(self, ctrl, step=0.25):
        self.ctrl = [tuple(p[:2]) for p in ctrl]
        self.step = step
        self.pts = resample(catmull(self.ctrl), step)
        self.grid = {}
        for i, (x, y) in enumerate(self.pts):
            self.grid.setdefault((math.floor(x / self.CELL), math.floor(y / self.CELL)), []).append(i)

    @property
    def length(self):
        return self.step * (len(self.pts) - 1)

    def at(self, s):
        s = max(0.0, min(s, self.length))
        i = min(int(s / self.step), len(self.pts) - 2)
        f = s / self.step - i
        (x0, y0), (x1, y1) = self.pts[i], self.pts[i + 1]
        tx, ty = norm2(x1 - x0, y1 - y0)
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, tx, ty

    def nearest(self, x, y, max_d=float("inf")):
        """(arc length, distance) of the closest resampled point; distance is inf if none lies within max_d."""
        cx, cy = math.floor(x / self.CELL), math.floor(y / self.CELL)
        best, best_d = 0, float("inf")
        ring = 0
        limit = max_d * max_d
        grid, pts = self.grid, self.pts
        while True:
            for key in _ring(cx, cy, ring):
                for i in grid.get(key, ()):
                    px, py = pts[i]
                    d = (px - x) ** 2 + (py - y) ** 2
                    if d < best_d:
                        best, best_d = i, d
            # once something is found, one more ring guarantees it is the true nearest
            if best_d < float("inf") and (ring * self.CELL) ** 2 >= best_d:
                break
            if (ring * self.CELL) ** 2 > limit:
                break
            ring += 1
            if ring > 400:
                break
        if best_d > limit:
            return best * self.step, float("inf")
        return best * self.step, math.sqrt(best_d)

    def nearest_s(self, x, y):
        """Approximate arc length of the closest point (every 8th sample, brute force): cheap at any distance."""
        best, best_d = 0, float("inf")
        for i in range(0, len(self.pts), 8):
            px, py = self.pts[i]
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best_d:
                best, best_d = i, d
        return best * self.step


# ---------------------------------------------------------------- frames

class Frame:
    """A stop's local frame: lx along the walking direction, ly toward the vignette (left), both in metres."""

    def __init__(self, origin, heading_deg):
        self.o = origin
        a = math.radians(heading_deg)
        self.h = (math.cos(a), math.sin(a))
        self.l = (-math.sin(a), math.cos(a))
        self.heading = a

    def w(self, lx, ly):
        return (self.o[0] + lx * self.h[0] + ly * self.l[0], self.o[1] + lx * self.h[1] + ly * self.l[1])

    def vec(self, lx, ly):
        return (lx * self.h[0] + ly * self.l[0], lx * self.h[1] + ly * self.l[1])


# ---------------------------------------------------------------- baked light

def light_at(x, y, z, nx, ny, nz, sources):
    """Linear light multiplier at a point with normal n: ambient + moon + warm point sources (no shadows)."""
    r, g, b = sources["ambient"]
    md = sources["moon"]["dir"]
    k = max(0.0, -(nx * md[0] + ny * md[1] + nz * md[2])) * sources["moon"]["intensity"]
    mc = sources["moon"]["color"]
    r, g, b = r + mc[0] * k, g + mc[1] * k, b + mc[2] * k
    for (px, py, pz), (cr, cg, cb), inten, rad in sources["points"]:
        dx, dy, dz = px - x, py - y, pz - z
        d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        facing = max(0.25, (dx * nx + dy * ny + dz * nz) / d)
        f = inten * facing / (1.0 + (d / rad) ** 2)
        r, g, b = r + cr * f, g + cg * f, b + cb * f
    return r, g, b


def make_sources():
    return {
        "ambient": (0.16, 0.215, 0.275),
        "moon": {"dir": norm3((0.35, -0.8, -1.0)), "color": (0.62, 0.78, 1.0), "intensity": 0.22},
        "points": [],
    }


def add_source(sources, pos, color, intensity, radius):
    sources["points"].append((tuple(pos), color, intensity, radius))


TORCH_LIGHT = ((1.0, 0.55, 0.22), 3.2, 3.5)
LANTERN_LIGHT = ((1.0, 0.62, 0.30), 0.9, 1.8)
TENT_LIGHT = ((1.0, 0.62, 0.30), 1.8, 2.4)
TENT_SIZE = (0.95, 1.1, 1.35)     # half-width, half-length (the door end is local -y), ridge height
FLOW_LIGHT = ((1.0, 0.62, 0.28), 0.35, 1.4)
MAP_BOARD = (1.38, 0.88)          # the knowledge kiosk's map board (width, height), metres
MAP_FACE = (0.0, -0.109, 1.35)    # its centre in the kiosk's frame: 3 mm in front of the paper (local -y faces the viewer)
MAP_GRID = (9, 6)                 # light samples across and down it, for the live scene's tint


# ---------------------------------------------------------------- the world

class Terrain:
    def __init__(self, flat, paths, streams):
        self.flat = flat
        self.paths = paths          # [Spline]
        self.streams = streams      # [(Spline, half, depth)]

    def raw(self, x, y):
        return height(x, y, self.flat)

    def trail(self, x, y):
        d = min(p.nearest(x, y, 1.5)[1] for p in self.paths) if self.paths else 1e9
        t = max(0.0, min(1.0, (PATH_HALF + 0.35 - d) / 0.45))
        return t * t * (3 - 2 * t)

    def channel(self, x, y):
        lower = 0.0
        for s, half, depth in self.streams:
            d = s.nearest(x, y, half + 1.0)[1]
            k = max(0.0, min(1.0, (half + 0.6 - d) / 0.8))
            lower = max(lower, depth * k * k * (3 - 2 * k))
        return lower

    def h(self, x, y):
        return self.raw(x, y) - 0.05 * self.trail(x, y) - self.channel(x, y)


class World:
    """Mutable build state; `build_world()` and `build_junction()` return its `data` dict."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.sources = make_sources()
        self.clearings = []       # [((x, y), r)]: no trees, ferns or bushes
        self.sky_holes = []       # [((x, y), r)]: no canopy
        self.instances = {}       # mesh -> [[x,y,z, qw,qx,qy,qz, sx,sy,sz, r,g,b, chunk]]
        self.torches = []
        self.lanterns = []
        self.signs = []           # every signpost board, for Blender and for labels
        self.flows = {}
        self.props = {}
        self.views = {}

    def add(self, mesh, pos, quat, scale, tint, chunk=0):
        sx, sy, sz = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
        self.instances.setdefault(mesh, []).append(
            [pos[0], pos[1], pos[2], *quat, sx, sy, sz, *tint, chunk])

    def cleared(self, x, y, margin=0.0):
        return any((x - cx) ** 2 + (y - cy) ** 2 < (r + margin) ** 2 for (cx, cy), r in self.clearings)


def facing_yaw(pos, toward):
    """Yaw for a prop whose local -y should face `toward` (both 2D)."""
    ux, uy = norm2(toward[0] - pos[0], toward[1] - pos[1])
    return math.atan2(ux, -uy)


def make_view(position, target, hfov):
    return {"position": [float(c) for c in position], "target": [float(c) for c in target], "hfov": hfov}


def screen_xy(view, p, aspect=16 / 9):
    """Where world point p lands in a view, as fractions of the image (x from the left, y from the top)."""
    pos, tgt = view["position"], view["target"]
    f = norm3([t - q for t, q in zip(tgt, pos)])
    right = norm3(cross(f, (0.0, 0.0, 1.0)))
    up = cross(right, f)
    d = [a - b for a, b in zip(p, pos)]
    x, y, z = dot(d, right), dot(d, up), dot(d, f)
    th = math.tan(math.radians(view["hfov"]) / 2)
    tv = th / aspect
    return 0.5 + 0.5 * (x / z) / th, 0.5 - 0.5 * (y / z) / tv


def screen_x(view, p, aspect=16 / 9):
    return screen_xy(view, p, aspect)[0]


def sign_geometry(post_xy, ground_z, direction, cam_xy, label, h=BOARD_H):
    """One arrow board on a post. direction: where the arrow points (2D). The board faces the camera."""
    dx, dy = norm2(*direction)
    yaw = math.atan2(dy, dx)
    nx, ny = -dy, dx
    if (cam_xy[0] - post_xy[0]) * nx + (cam_xy[1] - post_xy[1]) * ny < 0:
        nx, ny = -nx, -ny
    off = POST_R + BOARD_T / 2
    centre = (post_xy[0] + nx * off, post_xy[1] + ny * off, ground_z + h)
    board = (centre[0] + dx * LABEL_ALONG, centre[1] + dy * LABEL_ALONG, centre[2])
    return {"post": [post_xy[0], post_xy[1], ground_z], "yaw": yaw, "dir": [dx, dy], "n": [nx, ny],
            "centre": list(centre), "board": list(board), "label": label}


def sign_box(view, sign, aspect=16 / 9):
    """Screen box of a sign's board (fractions of the image), for the still-image buttons."""
    cx, cy, cz = sign["centre"]
    dx, dy = sign["dir"]
    pts = []
    for along in (-BOARD_TAIL, BOARD_L - BOARD_TAIL):
        for up in (-BOARD_W / 2, BOARD_W / 2):
            pts.append(screen_xy(view, (cx + dx * along, cy + dy * along, cz + up), aspect))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = 0.012
    return [max(0.0, min(xs) - pad), max(0.0, min(ys) - pad), min(1.0, max(xs) + pad), min(1.0, max(ys) + pad)]


# ---------------------------------------------------------------- stop layouts (stop-local metres)

STOP_ARC = [(-6.0, -2.05), (-2.2, -0.35), (0.0, 0.0), (2.2, -0.35), (6.0, -2.05)]
STREAM_LOCAL = [(-15, 10.25), (-9, 7.15), (-4, 4.95), (0, 3.95), (4, 3.65), (8.5, 4.75), (15, 7.25)]
ROCKS = [(14.2, 0.3, 0.42), (15.8, -0.35, 0.36), (17.4, 0.2, 0.48), (12.4, -0.4, 0.34), (19.1, -0.1, 0.3)]
STOP_SPECS = {
    # vignette anchor, camera target (lx, ly, height), eye, flatten radius, clearings, extras
    "continuity": {"vignette": (0.0, 3.95), "target": (0.3, 3.35, 0.55), "eye": 1.25, "clear": [((0.0, 1.55), 2.4)]},
    "scaffolding": {"vignette": (0.0, 3.0), "target": (0.0, 2.75, 0.6), "eye": 1.25, "clear": [((0.0, 3.15), 4.1)]},
    "knowledge": {"vignette": (0.0, 1.9), "target": (0.0, 1.85, 1.22), "eye": 1.3, "clear": [((0.0, 2.05), 2.7)]},
    "in-flight": {"vignette": (0.0, 4.55), "target": (0.3, 5.25, 1.3), "eye": 1.3, "clear": [((0.0, 6.25), 8.2)]},
}
STOP_FRAMES = [((0.0, 24.0), 92.0), ((1.5, 48.0), 85.0), ((-1.0, 72.0), 95.0), ((1.0, 96.0), 88.0)]
SIGN_POSTS = {"left": (-1.40, 0.55), "right": (1.40, 0.55)}
SIGN_DIRS = {"left": (-0.95, 0.30), "right": (0.95, 0.30)}
SIGN_LABELS = ["trailhead", "continuity", "scaffolding", "knowledge", "in-flight", "download"]


def build_world(seed=11):
    W = World(seed)
    frames = [Frame(o, h) for o, h in STOP_FRAMES]

    # ---- the path: trailhead run-in, a gentle bump toward each stop's scene, wiggles between stops
    ctrl = [(0.0, -9.0), (0.05, -3.0), (0.0, 2.5), (0.7, 8.0), (1.6, 13.0)]
    for i, f in enumerate(frames):
        ctrl += [f.w(lx, ly) for lx, ly in STOP_ARC]
        if i + 1 < len(frames):
            a, b = f.w(6.0, -2.05), frames[i + 1].w(-6.0, -2.05)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            wig = f.vec(0.0, -2.2 if i % 2 == 0 else -1.2)
            ctrl.append((mid[0] + wig[0], mid[1] + wig[1]))
    last = frames[-1]
    ctrl += [last.w(12.0, -3.2), last.w(19.0, -2.4), last.w(26.0, -3.5)]
    path = Spline(ctrl)
    stream = Spline([frames[0].w(lx, ly) for lx, ly in STREAM_LOCAL])

    flat = [((f.w(0.0, 3.5)), 14.0) for f in frames] + [((0.2, 1.5), 8.0)]
    terrain = Terrain(flat, [path], [(stream, 1.25, 0.5)])
    W.path, W.terrain = path, terrain
    H = terrain.h

    # ---- trailhead: the home page's view, looking down the path with the signpost left and the torch right
    # standing back on the path: the sign sits just right of centre, the torch near the right edge, and the
    # left of the frame is dark forest where the page's headline goes
    th_cam = (0.3, -2.2, H(0.3, -2.2) + 1.05)
    th_target = (-1.35, 3.57, H(-1.35, 3.57) + 1.1)
    W.views["trailhead"] = make_view(th_cam, th_target, TRAILHEAD_HFOV)
    th_sign = sign_geometry((-0.72, 2.25), H(-0.72, 2.25), (0.45, 1.0), th_cam[:2], "tour")
    th_torch = (1.02, 2.95)
    W.signs.append(th_sign)
    W.clearings += [((0.3, -2.2), 1.4), ((-0.72, 2.25), 0.7), (th_torch, 0.7)]
    add_torch(W, th_torch, TORCH_FLAME_SCALE)

    # ---- the four stops
    stops = []
    labels = SIGN_LABELS
    for i, (sid, f) in enumerate(zip(STOP_IDS, frames)):
        spec = STOP_SPECS[sid]
        cam_xy = f.w(0.0, -STOP_BACK)
        cam = (cam_xy[0], cam_xy[1], H(*cam_xy) + spec["eye"])
        tx, ty = f.w(spec["target"][0], spec["target"][1])
        target = (tx, ty, H(tx, ty) + spec["target"][2])
        vx, vy = f.w(*spec["vignette"])
        view = make_view(cam, target, STOP_HFOV)
        W.views[sid] = view
        signs = {}
        for side in ("left", "right"):
            px, py = f.w(*SIGN_POSTS[side])
            direction = f.vec(*SIGN_DIRS[side])
            label = labels[i] if side == "left" else labels[i + 2]
            sg = sign_geometry((px, py), H(px, py), direction, cam_xy, label)
            signs[side] = sg
            W.signs.append(sg)
            W.clearings.append(((px, py), 0.75))
        # keep the view open: camera, the line of sight and the scene itself
        W.clearings.append((cam_xy, 1.4))
        for t in (0.35, 0.6):
            W.clearings.append(((cam_xy[0] + (vx - cam_xy[0]) * t, cam_xy[1] + (vy - cam_xy[1]) * t), 1.6))
        for (lx, ly), r in spec["clear"]:
            W.clearings.append((f.w(lx, ly), r))
        stops.append({"id": sid, "origin": [f.o[0], f.o[1], H(*f.o)], "heading": f.heading, "view": view,
                      "signs": signs, "vignette": [vx, vy, H(vx, vy)], "frame": f})

    build_stream(W, frames[0], stream)
    build_camp(W, frames[1])
    build_kiosk(W, frames[2])
    build_launch(W, frames[3])

    # ---- torches along the trail (not crowding the trailhead or the stops), alternating sides
    s_stops = [path.nearest(*f.o)[0] for f in frames]
    s_th = path.nearest(1.02, 2.95)[0]
    side = 1
    s = s_th + 10.0
    while s < path.length - 4:
        if all(abs(s - ss) > 6.5 for ss in s_stops):
            x, y, tx_, ty_ = path.at(s)
            px, py = x - ty_ * 0.85 * side, y + tx_ * 0.85 * side
            if not W.cleared(px, py, 0.2):
                add_torch(W, (px, py), TRAIL_TORCH_FLAME_SCALE)
                W.clearings.append(((px, py), 0.6))
                side = -side
        s += 11.0

    # ---- the lights flow down the path (and glow faintly on it)
    W.flows["path"] = flow_along(W, path, path.nearest(*th_torch)[0] + 0.8, path.length, 1.0)
    for i in range(0, len(W.flows["path"]), 12):
        add_source(W.sources, W.flows["path"][i], *FLOW_LIGHT)

    scatter(W, path, stream, frames, s_stops)
    W.walks = make_walks(W, path, stops)
    W.ground = make_ground(W, [path], stream)
    W.path_ctrl = ctrl
    W.stops = stops
    return finish(W, {"trailhead": {"view": W.views["trailhead"], "sign": th_sign, "torch": list(th_torch)}})


def add_torch(W, xy, flame_scale, height_=TORCH_H):
    z0 = W.terrain.h(*xy)
    flame_base = (xy[0], xy[1], z0 + height_ + 0.116 - 0.035)
    light_pos = (xy[0], xy[1], flame_base[2] + FLAME_HEIGHT * flame_scale * 0.35)
    W.torches.append({"pos": list(light_pos), "base": list(flame_base), "ground": [xy[0], xy[1], z0],
                      "scale": flame_scale, "height": height_})
    add_source(W.sources, light_pos, *TORCH_LIGHT)


def flow_along(W, spline, s0, s1, lift, step=1.5):
    pts = []
    s = s0
    while s <= s1:
        x, y, _, _ = spline.at(s)
        pts.append([x, y, W.terrain.h(x, y) + lift + 0.12 * math.sin(s * 0.9)])
        s += step
    return pts


def build_stream(W, f, stream):
    H = W.terrain.h
    half, depth = 1.25, 0.5
    level = []
    for x, y in stream.pts[::4]:
        level.append([x, y, W.terrain.raw(x, y) - 0.25])
    rocks = []
    for k, (s, lat, r) in enumerate(ROCKS):
        x, y, tx, ty = stream.at(s)
        cx, cy = x - ty * lat, y + tx * lat
        zw = W.terrain.raw(x, y) - 0.25
        rocks.append({"pos": [cx, cy, zw - r * 0.12], "r": r, "yaw": W.rng.uniform(0, 6.283), "flow": [tx, ty],
                      "water": zw, "index": k})
    W.props["stream"] = {"centerline": [list(p) for p in stream.ctrl], "half": half, "depth": depth,
                         "level": level, "rocks": rocks}
    # the lights ride the current, swirling around every rock
    pts = []
    s = 2.0
    while s < stream.length - 2:
        x, y, tx, ty = stream.at(s)
        qx, qy = x - ty * 0.3 * math.sin(s * 0.8), y + tx * 0.3 * math.sin(s * 0.8)
        for rk in rocks:
            vx, vy = qx - rk["pos"][0], qy - rk["pos"][1]
            d = math.hypot(vx, vy)
            if d < rk["r"] + 0.45:
                if d < 1e-3:
                    vx, vy, d = -ty, tx, 1.0
                qx, qy = rk["pos"][0] + vx / d * (rk["r"] + 0.45), rk["pos"][1] + vy / d * (rk["r"] + 0.45)
        pts.append([qx, qy, W.terrain.raw(x, y) - 0.25 + 0.22 + 0.05 * math.sin(s * 1.3)])
        s += 0.7
    W.flows["stream"] = pts
    for i in range(0, len(pts), 6):
        add_source(W.sources, pts[i], *FLOW_LIGHT)
    add_torch(W, f.w(-2.5, 2.3), TRAIL_TORCH_FLAME_SCALE)
    W.clearings.append((f.w(-2.5, 2.3), 0.6))


def prop(W, name, f, lx, ly, cam_xy, extra_yaw=0.0):
    x, y = f.w(lx, ly)
    yaw = facing_yaw((x, y), cam_xy) + extra_yaw
    W.props[name] = {"pos": [x, y, W.terrain.h(x, y)], "yaw": yaw}
    return W.props[name]


def build_camp(W, f):
    cam = f.w(0.0, -STOP_BACK)
    prop(W, "tent", f, -1.35, 3.85, cam, math.radians(12))
    prop(W, "rack", f, 1.2, 2.05, cam)
    prop(W, "crate", f, -0.15, 2.85, cam)
    prop(W, "log_seat", f, 0.2, 1.7, cam, math.radians(8))
    pole = prop(W, "lantern_pole", f, 0.55, 4.45, cam)
    # the lantern hangs from the pole's arm, toward the viewer's left
    ax, ay = math.cos(pole["yaw"]), math.sin(pole["yaw"])
    lp = (pole["pos"][0] - ax * 0.34, pole["pos"][1] - ay * 0.34, pole["pos"][2] + 1.6)
    W.lanterns.append({"pos": list(lp)})
    add_source(W.sources, lp, *LANTERN_LIGHT)
    tent = W.props["tent"]["pos"]
    add_source(W.sources, (tent[0], tent[1], tent[2] + 0.55), *TENT_LIGHT)
    W.props["tent"]["glow"] = [tent[0], tent[1], tent[2] + 0.55]
    # the live scene's halo hangs just outside the doorway, where the lamp's light spills out
    yaw, reach = W.props["tent"]["yaw"], TENT_SIZE[1] + 0.3
    W.props["tent"]["door"] = [tent[0] + math.sin(yaw) * reach, tent[1] - math.cos(yaw) * reach, tent[2] + 0.4]


def build_kiosk(W, f):
    cam = f.w(0.0, -STOP_BACK)
    k = prop(W, "kiosk", f, 0.0, 1.9, cam)
    ax, ay = math.cos(k["yaw"]), math.sin(k["yaw"])
    fx, fy = math.sin(k["yaw"]), -math.cos(k["yaw"])      # local -y (toward the viewer)
    for sx in (-0.62, 0.62):
        lp = (k["pos"][0] + ax * sx + fx * 0.5, k["pos"][1] + ay * sx + fy * 0.5, k["pos"][2] + 1.98)
        W.lanterns.append({"pos": list(lp)})
        add_source(W.sources, lp, *LANTERN_LIGHT)
    # the map board's face: the live scene lays the trail map there, and the still gets its corners
    lx, ly, lz = MAP_FACE
    k["board"] = {"centre": [k["pos"][0] + ax * lx - fx * ly, k["pos"][1] + ay * lx - fy * ly, k["pos"][2] + lz],
                  "right": [ax, ay, 0.0], "up": [0.0, 0.0, 1.0], "normal": [fx, fy, 0.0], "size": list(MAP_BOARD)}


def build_launch(W, f):
    cam = f.w(0.0, -STOP_BACK)
    b = prop(W, "board", f, 0.0, 4.55, cam)
    for lx in (-1.6, 1.6):
        add_torch(W, f.w(lx, 4.05), TRAIL_TORCH_FLAME_SCALE)
    W.sky_holes.append((f.w(0.0, 6.25), 12.0))
    # issues take flight: the lights lift off the board and head on down the trail, above the tour card
    ax, ay = math.cos(b["yaw"]), math.sin(b["yaw"])
    fx, fy = math.sin(b["yaw"]), -math.cos(b["yaw"])
    start = (b["pos"][0] + ax * 0.68 + fx * 0.1, b["pos"][1] + ay * 0.68 + fy * 0.1, b["pos"][2] + 1.51)
    offs = [(0, 0, 0), (0.2, 0.15, 0.5), (0.8, 0.4, 1.1), (1.9, 0.8, 1.6), (3.4, 1.4, 2.0), (5.3, 2.3, 2.3),
            (7.6, 3.6, 2.6), (10.4, 5.4, 2.9), (13.6, 7.8, 3.2)]
    ctrl = []
    for ox, oy, oz in offs:      # offsets are in the board's frame: x along the board, y away from the viewer
        ctrl.append((start[0] + ax * ox - fx * oy, start[1] + ay * ox - fy * oy, start[2] + oz))
    curve = resample(catmull(ctrl, 30), 0.42)
    pts = []
    for i, q in enumerate(curve[1:48]):
        pts.append([q[0] + 0.12 * math.sin(i * 1.7), q[1] + 0.1 * math.cos(i * 1.3), q[2] + 0.08 * math.sin(i * 2.1)])
    W.flows["flight"] = pts
    for i in range(0, 14, 4):
        add_source(W.sources, pts[i], *FLOW_LIGHT)


# ---------------------------------------------------------------- scatter

def near_torch_tilt(W, x, y, radius=2.2, deg=14.0):
    tx = ty = 0.0
    for t in W.torches:
        vx, vy = x - t["ground"][0], y - t["ground"][1]
        d = math.hypot(vx, vy)
        if 1e-3 < d < radius:
            k = math.radians(deg * (1 - d / radius) + 3)
            tx, ty = tx + vx / d * k, ty + vy / d * k
    return tx, ty


def albedo(W, a, b):
    return mix(lin(PALETTE[a]), lin(PALETTE[b]), W.rng.random())


def tint(W, alb, x, y, z, nz=1.0):
    """Albedo x baked light for an instance. nz=-1 for foliage seen from below (canopy, branch clumps): no moon."""
    lr, lg, lb = light_at(x, y, z, 0.0, 0.0, nz, W.sources)
    return (min(4.0, alb[0] * lr), min(4.0, alb[1] * lg), min(4.0, alb[2] * lb))


def scatter(W, path, stream, frames, s_stops):
    rng, H = W.rng, W.terrain.h
    chunk = lambda x, y: int(path.nearest_s(x, y) // 20.0)  # noqa: E731
    xs = [p[0] for p in path.pts]
    ys = [p[1] for p in path.pts]
    x0, x1, y0, y1 = min(xs) - CORRIDOR, max(xs) + CORRIDOR, min(ys) - 12.0, max(ys) + CORRIDOR

    def blocked(x, y, clear):
        d = path.nearest(x, y, CORRIDOR + 1.0)[1]
        if d < clear:
            return True, d
        if stream.nearest(x, y, clear + 1.5)[1] < clear + 1.35:
            return True, d
        return W.cleared(x, y), d

    # trees: denser near the path, never on it, spaced apart
    trees, grid = [], {}
    tries = 0
    target = 900
    while len(trees) < target and tries < target * 40:
        tries += 1
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(0.16, 0.42)
        bad, d = blocked(x, y, 1.35 + r)
        if bad or d > CORRIDOR:
            continue
        if rng.random() > max(0.28, 1.25 - d / 18.0):
            continue
        gx, gy = int(x // 3), int(y // 3)
        if any((x - a) ** 2 + (y - b) ** 2 < (1.1 + r + c) ** 2
               for i in range(gx - 1, gx + 2) for j in range(gy - 1, gy + 2) for a, b, c in grid.get((i, j), ())):
            continue
        grid.setdefault((gx, gy), []).append((x, y, r))
        trees.append((x, y, r))
    for i, (x, y, r) in enumerate(trees):
        z = H(x, y)
        c = chunk(x, y)
        lean = (rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05))
        W.add(f"Trunk{i % 4}", (x, y, z), quat_tilt_yaw(lean, rng.uniform(0, 6.283)), (r, r, rng.uniform(0.85, 1.1)),
              tint(W, albedo(W, "bark", "bark2"), x, y, z + 1.5), c)
        s_near, d = path.nearest(x, y)
        if d < 7.5 and rng.random() < 0.8:
            px, py, _, _ = path.at(s_near)
            aim = math.atan2(py - y, px - x)
            for _ in range(rng.randint(1, 3)):
                az = aim + rng.uniform(-0.9, 0.9)
                el = math.radians(rng.uniform(18, 42))
                ln = rng.uniform(1.4, 3.2)
                h = rng.uniform(2.4, 4.8)
                dv = (math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))
                base = (x, y, z + h)
                tip = (base[0] + dv[0] * ln, base[1] + dv[1] * ln, base[2] + dv[2] * ln)
                sc = rng.uniform(0.5, 1.1)
                if W.cleared(tip[0], tip[1], sc) or W.cleared(base[0] + dv[0] * ln * 0.55, base[1] + dv[1] * ln * 0.55):
                    continue
                W.add("Branch", base, quat_to(dv), (r * 2.2, r * 2.2, ln),
                      tint(W, albedo(W, "bark", "bark2"), *base), c)
                W.add(f"Clump{rng.randrange(4)}", tip, quat_yaw(rng.uniform(0, 6.283)), (sc, sc, sc * 0.9),
                      tint(W, albedo(W, "leaf", "leaf2"), *tip, nz=-1.0), c)
                if rng.random() < 0.5:
                    mid = (base[0] + dv[0] * ln * 0.55, base[1] + dv[1] * ln * 0.55, base[2] + dv[2] * ln * 0.55 - 0.1)
                    sc2 = sc * rng.uniform(0.5, 0.8)
                    W.add(f"Clump{rng.randrange(4)}", mid, quat_yaw(rng.uniform(0, 6.283)), sc2,
                          tint(W, albedo(W, "leaf", "leaf2"), *mid, nz=-1.0), c)

    # canopy overhead (none above the launch clearing, so the stars show)
    for _ in range(520):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        d = path.nearest(x, y, CORRIDOR)[1]
        if d > CORRIDOR - 4 or any((x - cx) ** 2 + (y - cy) ** 2 < r * r for (cx, cy), r in W.sky_holes):
            continue
        z = H(x, y) + rng.uniform(5.5, 10.5)
        sc = rng.uniform(1.8, 3.8)
        W.add(f"Canopy{rng.randrange(2)}", (x, y, z), quat_yaw(rng.uniform(0, 6.283)),
              (sc, sc * rng.uniform(0.8, 1.2), sc * 0.8), tint(W, albedo(W, "canopy", "leaf2"), x, y, z, nz=-1.0),
              chunk(x, y))

    # undergrowth crowding the path edges, plus some deeper in
    cams = [tuple(v["position"][:2]) for v in W.views.values()]

    def plant(x, y, allow_bush=True):
        if blocked(x, y, 0.5)[0]:
            return
        z = H(x, y)
        c = chunk(x, y)
        tilt = near_torch_tilt(W, x, y)
        if not allow_bush or rng.random() < 0.72:
            sc = rng.uniform(0.65, 1.3)
            W.add(f"Fern{rng.randrange(4)}", (x, y, z - 0.02), quat_tilt_yaw(tilt, rng.uniform(0, 6.283)), sc,
                  tint(W, albedo(W, "fern", "fern2"), x, y, z + 0.3), c)
        elif all(math.hypot(x - cx, y - cy) > 3.2 for cx, cy in cams):
            sc = rng.uniform(0.3, 0.75)
            W.add(f"Clump{rng.randrange(4)}", (x, y, z + sc * 0.25),
                  quat_tilt_yaw((tilt[0] * 0.4, tilt[1] * 0.4), rng.uniform(0, 6.283)), (sc, sc, sc * 0.9),
                  tint(W, albedo(W, "leaf", "leaf2"), x, y, z + 0.3), c)

    s = 0.0
    while s < path.length:
        x, y, tx, ty = path.at(s)
        for side in (-1, 1):
            for _ in range(rng.randint(1, 2)):
                off = rng.uniform(0.55, 1.0) if rng.random() < 0.35 else rng.uniform(1.0, 4.2)
                j = rng.uniform(-0.3, 0.3)
                plant(x - ty * side * off + tx * j, y + tx * side * off + ty * j)
        s += 0.55
    s = 0.0
    while s < stream.length:
        x, y, tx, ty = stream.at(s)
        for side in (-1, 1):
            off = 1.25 + 1.35 + rng.uniform(0.2, 2.5)
            plant(x - ty * side * off, y + tx * side * off, allow_bush=False)
        s += 0.9
    for _ in range(360):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if path.nearest(x, y, 14.0)[1] < 14.0:
            plant(x, y)

    # signposts and torches are instances too (their lighting rides in the tint)
    for sg in W.signs:
        px, py, pz = sg["post"]
        c = chunk(px, py)
        W.add("Post", (px, py, pz), (1.0, 0.0, 0.0, 0.0), 1.0,
              tint(W, lin(PALETTE["post"]), px, py, pz + 0.6), c)
        W.add("Board", tuple(sg["centre"]), quat_yaw(sg["yaw"]), 1.0,
              tint(W, lin(PALETTE["wood"]), *sg["centre"]), c)
    for t in W.torches:
        gx, gy, gz = t["ground"]
        c = chunk(gx, gy)
        W.add("TorchStaff", (gx, gy, gz), (1.0, 0.0, 0.0, 0.0), (1.0, 1.0, t["height"] / TORCH_H),
              tint(W, lin(PALETTE["post"]), gx, gy, gz + 0.9), c)
        W.add("TorchCup", (gx, gy, gz + t["height"]), (1.0, 0.0, 0.0, 0.0), 1.0,
              tint(W, lin(PALETTE["iron"]), gx, gy, gz + t["height"]), c)


# ---------------------------------------------------------------- walks and ground

def make_walks(W, path, stops):
    views = [("trailhead", W.views["trailhead"])] + [(s["id"], s["view"]) for s in stops]
    walks = []
    for (a_id, a), (b_id, b) in zip(views, views[1:]):
        sa = path.nearest(*a["position"][:2])[0]
        sb = path.nearest(*b["position"][:2])[0]
        pts, tgts = [list(a["position"])], [list(a["target"])]
        s = sa + 2.0
        while s < sb - 1.5:
            x, y, _, _ = path.at(s)
            ax, ay, _, _ = path.at(min(path.length, s + 6.0))
            pts.append([x, y, W.terrain.h(x, y) + WALK_EYE])
            tgts.append([ax, ay, W.terrain.h(ax, ay) + 1.4])
            s += 3.0
        pts.append(list(b["position"]))
        tgts.append(list(b["target"]))
        walks.append({"from": a_id, "to": b_id, "points": pts, "targets": tgts})
    return walks


def make_ground(W, paths, stream, reach=GROUND_REACH):
    path = paths[0]
    xs = [p[0] for p in path.pts]
    ys = [p[1] for p in path.pts]
    x0 = math.floor((min(xs) - reach) / GROUND_CELL) * GROUND_CELL
    y0 = math.floor((min(ys) - reach) / GROUND_CELL) * GROUND_CELL
    nx = int((max(xs) + reach - x0) / GROUND_CELL) + 1
    ny = int((max(ys) + reach - y0) / GROUND_CELL) + 1
    keep = {}
    for j in range(ny):
        for i in range(nx):
            cx, cy = x0 + (i + 0.5) * GROUND_CELL, y0 + (j + 0.5) * GROUND_CELL
            if path.nearest(cx, cy, reach + 1.0)[1] <= reach:
                keep[(i, j)] = True
    index, verts, colors, albedos = {}, [], [], []
    faces = []
    T = W.terrain
    moss, moss2, dirt, bed = (lin(PALETTE[k]) for k in ("moss", "moss2", "dirt", "bed"))

    def vid(i, j):
        key = (i, j)
        if key not in index:
            x, y = x0 + i * GROUND_CELL, y0 + j * GROUND_CELL
            z = T.h(x, y)
            e = 0.3
            nxv, nyv = T.raw(x - e, y) - T.raw(x + e, y), T.raw(x, y - e) - T.raw(x, y + e)
            n = norm3((nxv, nyv, 2 * e))
            base = mix(moss, moss2, 0.5 + 0.5 * value_noise(x * 0.35, y * 0.35))
            base = mix(base, dirt, T.trail(x, y))
            ch = T.channel(x, y)
            if ch > 0:
                base = mix(base, bed, min(1.0, ch / 0.3))
            lr, lg, lb = light_at(x, y, z, *n, W.sources)
            index[key] = len(verts)
            verts.append([x, y, z])
            albedos.append(list(base))
            colors.append([min(4.0, base[0] * lr), min(4.0, base[1] * lg), min(4.0, base[2] * lb)])
        return index[key]

    for (i, j) in sorted(keep):
        a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
        faces.append([a, b, c, d])
    return {"verts": verts, "faces": faces, "colors": colors, "albedo": albedos}


# ---------------------------------------------------------------- junction (Help)

JUNCTION_TRAILS = {
    "main": [(0.15, -6), (0.1, -1), (0.0, 2.3)],
    "branch-left": [(0.0, 2.3), (-1.4, 3.1), (-3.8, 4.2), (-6.6, 6.8), (-8.4, 11.5), (-9.2, 19), (-10, 28)],
    "branch-right": [(0.0, 2.3), (1.5, 2.9), (4.0, 4.3), (6.9, 7.4), (8.8, 12.5), (9.6, 20), (10.5, 30)],
    "branch-ahead": [(0.0, 2.3), (0.25, 5.0), (-0.45, 9.5), (0.7, 15), (-0.2, 23), (0.8, 34), (0, 48)],
}


def build_junction(seed=5):
    W = World(seed)
    splines = {k: Spline(v) for k, v in JUNCTION_TRAILS.items()}
    allp = list(splines.values())
    terrain = Terrain([((0.0, 2.5), 10.0)], allp, [])
    W.terrain = terrain
    H = terrain.h
    cam = (0.5, 0.75, H(0.5, 0.75) + 1.12)
    target = (-0.15, 3.45, H(-0.15, 3.45) + 0.88)
    W.views["junction"] = make_view(cam, target, JUNCTION_HFOV)
    post = (-0.6, 3.4)
    boards = []
    for key, yaw_deg, h in (("left", 160.0, 0.82), ("right", 14.0, 0.66), ("ahead", 61.0, 0.50)):
        a = math.radians(yaw_deg)
        sg = sign_geometry(post, H(*post), (math.cos(a), math.sin(a)), cam[:2], key, h)
        sg["key"] = key
        boards.append(sg)
        W.signs.append(sg)
    # one post carries all three boards: keep only the first board's post instance
    W.clearings += [(post, 0.8), ((0.5, 0.75), 1.3), ((0.95, 4.6), 0.6)]
    add_torch(W, (0.95, 4.6), 0.24, 1.25)
    for key in ("branch-left", "branch-right", "branch-ahead"):
        sp = splines[key]
        W.flows[key] = flow_along(W, sp, 1.4, min(sp.length, 31.0), 1.0)
        for i in range(0, len(W.flows[key]), 8):
            add_source(W.sources, W.flows[key][i], *FLOW_LIGHT)
        x, y, tx, ty = sp.at(7.0)
        add_torch(W, (x - ty * 0.85, y + tx * 0.85), 0.22, 1.25)
        W.clearings.append(((x - ty * 0.85, y + tx * 0.85), 0.6))
    joined = Spline(JUNCTION_TRAILS["branch-ahead"])
    scatter_junction(W, allp)
    W.path, W.path_ctrl = joined, JUNCTION_TRAILS["branch-ahead"]
    W.ground = make_ground_multi(W, allp)
    W.walks = []
    W.stops = []
    data = finish(W, {"junction": {"view": W.views["junction"], "post": [post[0], post[1], H(*post)],
                                   "boards": boards}})
    return data


def scatter_junction(W, splines):
    """Like scatter(), for the small junction scene: the nearest of several paths counts."""

    class Multi:
        def __init__(self, sps):
            self.sps = sps
            self.pts = [p for s in sps for p in s.pts]

        def nearest(self, x, y, max_d=float("inf")):
            best = (0.0, float("inf"))
            for sp in self.sps:
                q = sp.nearest(x, y, max_d)
                if q[1] < best[1]:
                    best = q
            return best

        def at(self, s):
            return self.sps[0].at(s)

        @property
        def length(self):
            return self.sps[0].length

    multi = Multi(splines)
    rng, H = W.rng, W.terrain.h
    x0, x1, y0, y1 = -24.0, 24.0, -6.0, 50.0
    trees = []
    tries = 0
    while len(trees) < 320 and tries < 20000:
        tries += 1
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(0.16, 0.42)
        d = multi.nearest(x, y, CORRIDOR)[1]
        if d < 1.3 + r or W.cleared(x, y) or rng.random() > max(0.3, 1.25 - d / 18):
            continue
        if any((x - a) ** 2 + (y - b) ** 2 < (1.1 + r + c) ** 2 for a, b, c in trees):
            continue
        trees.append((x, y, r))
    for i, (x, y, r) in enumerate(trees):
        z = H(x, y)
        W.add(f"Trunk{i % 4}", (x, y, z), quat_tilt_yaw((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)),
                                                        rng.uniform(0, 6.283)),
              (r, r, rng.uniform(0.85, 1.1)), tint(W, albedo(W, "bark", "bark2"), x, y, z + 1.5))
        if multi.nearest(x, y, 7.0)[1] < 7.0 and rng.random() < 0.7:
            for _ in range(rng.randint(1, 2)):
                az, el = rng.uniform(0, 6.283), math.radians(rng.uniform(18, 42))
                ln, h = rng.uniform(1.4, 3.0), rng.uniform(2.4, 4.6)
                dv = (math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))
                base = (x, y, z + h)
                W.add("Branch", base, quat_to(dv), (r * 2.2, r * 2.2, ln), tint(W, albedo(W, "bark", "bark2"), *base))
                tip = (base[0] + dv[0] * ln, base[1] + dv[1] * ln, base[2] + dv[2] * ln)
                sc = rng.uniform(0.5, 1.1)
                W.add(f"Clump{rng.randrange(4)}", tip, quat_yaw(rng.uniform(0, 6.283)), (sc, sc, sc * 0.9),
                      tint(W, albedo(W, "leaf", "leaf2"), *tip))
    for _ in range(160):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        z = H(x, y) + rng.uniform(5.5, 10.5)
        sc = rng.uniform(1.8, 3.8)
        W.add(f"Canopy{rng.randrange(2)}", (x, y, z), quat_yaw(rng.uniform(0, 6.283)), (sc, sc, sc * 0.8),
              tint(W, albedo(W, "canopy", "leaf2"), x, y, z))
    for sp in splines:
        s = 0.0
        while s < min(sp.length, 36.0):
            x, y, tx, ty = sp.at(s)
            for side in (-1, 1):
                off = rng.uniform(0.55, 1.0) if rng.random() < 0.35 else rng.uniform(1.0, 4.0)
                px, py = x - ty * side * off, y + tx * side * off
                if multi.nearest(px, py, 0.6)[1] < 0.5 or W.cleared(px, py):
                    continue
                pz = H(px, py)
                sc = rng.uniform(0.65, 1.3)
                W.add(f"Fern{rng.randrange(4)}", (px, py, pz - 0.02),
                      quat_tilt_yaw(near_torch_tilt(W, px, py), rng.uniform(0, 6.283)), sc,
                      tint(W, albedo(W, "fern", "fern2"), px, py, pz + 0.3))
            s += 0.6
    first = True
    for sg in W.signs:
        px, py, pz = sg["post"]
        if first:
            W.add("Post", (px, py, pz), (1.0, 0.0, 0.0, 0.0), 1.0, tint(W, lin(PALETTE["post"]), px, py, pz + 0.6))
            first = False
        W.add("Board", tuple(sg["centre"]), quat_yaw(sg["yaw"]), 1.0, tint(W, lin(PALETTE["wood"]), *sg["centre"]))
    for t in W.torches:
        gx, gy, gz = t["ground"]
        W.add("TorchStaff", (gx, gy, gz), (1.0, 0.0, 0.0, 0.0), (1.0, 1.0, t["height"] / TORCH_H),
              tint(W, lin(PALETTE["post"]), gx, gy, gz + 0.9))
        W.add("TorchCup", (gx, gy, gz + t["height"]), (1.0, 0.0, 0.0, 0.0), 1.0,
              tint(W, lin(PALETTE["iron"]), gx, gy, gz + t["height"]))


def make_ground_multi(W, splines):
    class Multi:
        def __init__(self, sps):
            self.sps = sps
            self.pts = [p for s in sps for p in s.pts]

        def nearest(self, x, y, max_d=float("inf")):
            best = (0.0, float("inf"))
            for sp in self.sps:
                q = sp.nearest(x, y, max_d)
                if q[1] < best[1]:
                    best = q
            return best

    return make_ground(W, [Multi(splines)], None, reach=14.0)


# ---------------------------------------------------------------- output

def finish(W, extra):
    data = {
        "path": [list(p) for p in W.path_ctrl],
        "views": W.views,
        "stops": [{k: v for k, v in s.items() if k != "frame"} for s in W.stops],
        "walks": W.walks,
        "torches": W.torches,
        "lanterns": W.lanterns,
        "signs": W.signs,
        "flows": W.flows,
        "props": W.props,
        "instances": W.instances,
        "clearings": [[list(c), r] for c, r in W.clearings],
        "sky_holes": [[list(c), r] for c, r in W.sky_holes],
        "sources": W.sources,
        "ground": W.ground,
        "terrain": W.terrain,
    }
    data.update(extra)
    return data


def _p(v, nd=3):
    """Blender Z-up point -> browser Y-up point."""
    return [round(v[0], nd), round(v[2], nd), round(-v[1], nd)]


def _q(q, nd=4):
    """Blender (w, x, y, z) -> Three.js [x, y, z, w] in Y-up."""
    w, x, y, z = q
    return [round(x, nd), round(z, nd), round(-y, nd), round(w, nd)]


def _dir2(v, nd=4):
    return [round(v[0], nd), 0.0, round(-v[1], nd)]


def _view(v):
    return {"position": _p(v["position"]), "target": _p(v["target"]), "hfov": v["hfov"]}


def _sign(sg, sources=None):
    out = {"board": _p(sg["board"]), "centre": _p(sg["centre"]), "n": _dir2(sg["n"]), "dir": _dir2(sg["dir"]),
           "label": sg["label"]}
    if sources is not None:
        bx, by, bz = sg["board"]
        out["light"] = [round(c, 3) for c in light_at(bx, by, bz, sg["n"][0], sg["n"][1], 0.0, sources)]
    if "key" in sg:
        out["key"] = sg["key"]
    return out


def board_corners(bd):
    """The map board's corners, clockwise from the top-left as the viewer sees it."""
    w, h = bd["size"]
    return [[c + r * sx * w / 2 + u * sy * h / 2 for c, r, u in zip(bd["centre"], bd["right"], bd["up"])]
            for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]


def board_web(bd, sources):
    """The board's frame for the browser (Y-up) and its baked light: MAP_GRID tints, row by row from the top."""
    w, h = bd["size"]
    cols, rows = MAP_GRID
    light = []
    for j in range(rows):
        for i in range(cols):
            u = -w / 2 + w * i / (cols - 1)
            v = h / 2 - h * j / (rows - 1)
            p = [c + r * u + q * v for c, r, q in zip(bd["centre"], bd["right"], bd["up"])]
            lr, lg, lb = light_at(*p, *bd["normal"], sources)
            light.append([round(min(4.0, lr), 3), round(min(4.0, lg), 3), round(min(4.0, lb), 3)])
    return {"centre": _p(bd["centre"]), "right": _p(bd["right"], 4), "up": _p(bd["up"], 4),
            "normal": _p(bd["normal"], 4), "size": list(bd["size"]), "grid": [cols, rows], "light": light}


def to_web(world):
    views = {k: _view(v) for k, v in world["views"].items()}
    inst = {}
    for mesh, items in world["instances"].items():
        for it in items:
            chunk = it[13]
            flat = inst.setdefault((mesh, chunk), [])
            flat += _p(it[0:3], 2) + _q(it[3:7]) + [round(it[7], 3), round(it[9], 3), round(it[8], 3)] + \
                [round(c, 3) for c in it[10:13]]
    instances = [{"mesh": m, "chunk": c, "data": d} for (m, c), d in sorted(inst.items())]
    chunks = {}
    for mesh, items in world["instances"].items():
        for it in items:
            chunks.setdefault(it[13], []).append(it[0:3])
    chunk_info = []
    for c, pts in sorted(chunks.items()):
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        cz = sum(p[2] for p in pts) / len(pts)
        rad = max(math.dist((cx, cy, cz), p) for p in pts)
        chunk_info.append({"id": c, "centre": _p((cx, cy, cz)), "radius": round(rad, 2)})
    still_signs = {}
    for s in world["stops"]:
        still_signs[s["id"]] = {side: [round(v, 4) for v in sign_box(s["view"], s["signs"][side])]
                                for side in ("left", "right")}
    board = world["props"].get("kiosk", {}).get("board")
    if board:
        kv = next(s["view"] for s in world["stops"] if s["id"] == "knowledge")
        still_signs["knowledge"]["board"] = [[round(v, 4) for v in screen_xy(kv, p)] for p in board_corners(board)]
    if "trailhead" in world:
        still_signs["trailhead"] = {"tour": [round(v, 4) for v in sign_box(world["views"]["trailhead"],
                                                                           world["trailhead"]["sign"])]}
    if "junction" in world:
        jv = world["views"]["junction"]
        still_signs["junction"] = {b["key"]: [round(v, 4) for v in sign_box(jv, b)]
                                   for b in world["junction"]["boards"]}
    web = {
        "version": 1,
        "views": views,
        "stops": [{"id": s["id"], "view": s["id"], "signs": {k: _sign(v, world["sources"]) for k, v in s["signs"].items()},
                   "vignette": _p(s["vignette"])} for s in world["stops"]],
        "walks": [{"from": w["from"], "to": w["to"], "points": [_p(p) for p in w["points"]],
                   "targets": [_p(p) for p in w["targets"]]} for w in world["walks"]],
        "torches": [{"pos": _p(t["pos"]), "base": _p(t["base"]), "scale": t["scale"]} for t in world["torches"]],
        "lanterns": [{"pos": _p(l_["pos"])} for l_ in world["lanterns"]],
        "flows": {k: [_p(p, 2) for p in v] for k, v in world["flows"].items()},
        "instances": instances,
        "chunks": chunk_info,
        "stillSigns": still_signs,
        "props": {},
    }
    if "stream" in world["props"]:
        web["props"]["rocks"] = [{"pos": _p(r["pos"]), "r": r["r"], "index": r["index"]}
                                 for r in world["props"]["stream"]["rocks"]]
    if "tent" in world["props"]:
        web["props"]["tentGlow"] = _p(world["props"]["tent"]["door"])
    if board:
        web["props"]["kioskBoard"] = board_web(board, world["sources"])
    if world["sky_holes"]:
        (cx, cy), r = world["sky_holes"][0]
        web["sky"] = {"centre": _p((cx, cy, 0.0)), "radius": r}
    if "trailhead" in world:
        web["trailhead"] = {"view": "trailhead", "sign": _sign(world["trailhead"]["sign"], world["sources"])}
    if "junction" in world:
        web["junction"] = {"view": "junction", "boards": [_sign(b, world["sources"]) for b in world["junction"]["boards"]]}
    return web


# ---------------------------------------------------------------- signpost words for the still images

# The words on the signposts, by label key, as shipped (the same as js/content.js). The live scene reads the owner's
# public/tour-content.js in the browser; the Cycles stills paint the words in, so the build reads that file too.
DEFAULT_SIGNS = {"trailhead": "Trailhead", "tour": "The tour", "download": "Download", "continuity": "Continuity",
                 "scaffolding": "Scaffolding", "knowledge": "Knowledge", "in-flight": "In Flight",
                 "left": "Issues", "right": "Docs", "ahead": "Tour"}

_JS_TOKEN = re.compile(r"\s+|//[^\n]*|/\*.*?\*/"
                       r"|(?P<str>'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\$])*`)"
                       r"|(?P<word>[A-Za-z_$][\w$]*|\d+(?:\.\d*)?)|(?P<punct>[{}\[\]:,+\-=;.()])", re.S)
_JS_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|\r\n|.)", re.S)
_JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0", "\n": "", "\r\n": ""}


def _js_string(literal):
    def unescape(m):
        e = m.group(1)
        return chr(int(e[1:], 16)) if e[0] in "ux" and len(e) > 1 else _JS_ESCAPES.get(e, e)
    return _JS_ESCAPE.sub(unescape, literal[1:-1])


class _JsLiteral:
    """Reads one JavaScript object literal: objects become dicts, arrays lists, strings (joined across +) str, and
    anything else (numbers, names) None. It tokenizes lazily and stops where the literal ends, so the rest of the
    file may hold any code."""

    def __init__(self, src, pos):
        self.src, self.pos, self.ahead = src, pos, []

    def _token(self):
        while True:
            m = _JS_TOKEN.match(self.src, self.pos) if self.pos < len(self.src) else None
            if not m:
                raise ValueError(f"unreadable JavaScript at {self.pos}")
            self.pos = m.end()
            if m.lastgroup:
                return m.lastgroup, m.group(m.lastgroup)

    def peek(self, k=0):
        while len(self.ahead) <= k:
            self.ahead.append(self._token())
        return self.ahead[k]

    def take(self, want=None):
        tok = self.peek()
        if want is not None and tok[1] != want:
            raise ValueError(f"expected {want!r}, found {tok[1]!r}")
        return self.ahead.pop(0)

    def value(self):
        kind, tok = self.take()
        if tok in ("{", "["):
            close = "}" if tok == "{" else "]"
            out = {} if tok == "{" else []
            while self.peek()[1] != close:
                if tok == "{":
                    key_kind, key = self.take()
                    self.take(":")
                    out[_js_string(key) if key_kind == "str" else key] = self.value()
                else:
                    out.append(self.value())
                if self.peek()[1] != close:
                    self.take(",")
            self.take(close)
            return out
        if kind == "str":
            text = _js_string(tok)
            while self.peek()[1] == "+" and self.peek(1)[0] == "str":
                self.take()
                text += _js_string(self.take()[1])
            return text
        if kind == "word":
            return None
        if tok == "-" and self.peek()[0] == "word":
            self.take()
            return None
        raise ValueError(f"unexpected {tok!r}")


def read_tour_signs(src, name="BLAZEAHEAD_TOUR"):
    """The signpost words set in a tour file (public/tour-content.js), by label key. As in js/content.js, a word
    that is missing, blank or unreadable keeps its shipped value, and only the first four stops count."""
    words = dict(DEFAULT_SIGNS)
    m = re.search(rf"\b{re.escape(name)}\s*=\s*(?=\{{)", src)
    if not m:
        return words
    try:
        tour = _JsLiteral(src, m.end()).value()
    except ValueError:
        return words

    def word(obj, key, fallback):
        v = obj.get(key) if isinstance(obj, dict) else None
        return v.strip() if isinstance(v, str) and v.strip() else fallback

    trail = tour.get("trailhead")
    words["trailhead"] = word(trail, "sign", words["trailhead"])
    words["tour"] = word(trail, "tourSign", words["tour"])
    words["download"] = word(tour.get("end"), "sign", words["download"])
    stops = tour.get("stops")
    if isinstance(stops, list):
        for sid, stop in zip(STOP_IDS, stops):
            words[sid] = word(stop, "sign", words[sid])
    arms = tour.get("help")
    arms = arms.get("signs") if isinstance(arms, dict) else None
    for key in ("left", "right", "ahead"):
        words[key] = word(arms, key, words[key])
    return words

"""Build the blazeAhead 3D pieces in Blender (headless) and export them for the website.

  blender -b --factory-startup --python-exit-code 1 --python blender/build_blazeahead.py -- [options]

  --out DIR      where blazeahead.glb, world.json, junction.json (and stills/) go   (default: public/assets)
  --blend PATH   where to save the editable .blend                                  (default: blender/blazeahead.blend)
  --stills       also render the still images with Cycles (tens of minutes)
  --samples N    Cycles samples for the stills (default: 48)
  --only NAMES   render only these stills, comma-separated (trailhead,continuity,...,junction)

The world itself (path, stops, scatter, baked light) comes from blazeahead_layout.py. This script turns it into
meshes, as follows:

- Shared pieces (trees, ferns, signposts, torches, flame) are exported once. The browser instances them from
  world.json. Their vertex colour is a per-face shade factor; the instance colour carries albedo times baked light.
- Unique props (ground, stream, camp, kiosk, launch board) are exported in place. Their vertex colour is albedo
  times baked light.

The GLB has no normals, UVs (except the water's), or materials: the browser draws it unlit, with fog.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blazeahead_layout as L  # noqa: E402

FONT_PATHS = [r"C:\Windows\Fonts\georgiab.ttf", r"C:\Windows\Fonts\GEORGIAB.TTF", r"C:\Windows\Fonts\georgia.ttf"]
SHADE_DIR = Vector((0.3, -0.5, 0.8)).normalized()
GLB_MAX_BYTES = 600_000


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(HERE.parent / "public" / "assets"))
    p.add_argument("--blend", default=str(HERE / "blazeahead.blend"))
    p.add_argument("--stills", action="store_true")
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--only", default="")
    p.add_argument("--tour", default=str(HERE.parent / "public" / "tour-content.js"),
                   help="the owner's tour file: the stills paint its signpost words")
    return p.parse_args(argv)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def lin(hexstr):
    return L.lin(hexstr)


# ---------------------------------------------------------------- building blocks

class Part:
    """Accumulates geometry into one mesh with a per-corner colour attribute named Col."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.float_color.new("Col")
        self.glow = self.bm.loops.layers.float.new("Glow")

    def add_bm(self, src, face_color=None, loop_color=None, matrix=None):
        """Copy src's faces. face_color(centre, normal) or loop_color(co, normal) gives linear RGB (world space)."""
        if matrix is not None:
            src.transform(matrix)
        src.verts.index_update()
        src.normal_update()
        vmap = [self.bm.verts.new(v.co) for v in src.verts]
        for f in src.faces:
            try:
                nf = self.bm.faces.new([vmap[v.index] for v in f.verts])
            except ValueError:
                continue
            if face_color is not None:
                c = face_color(f.calc_center_median(), f.normal)
                g = c[3] if len(c) > 3 else 0.0
                for loop in nf.loops:
                    loop[self.col] = (c[0], c[1], c[2], 1.0)
                    loop[self.glow] = g
            else:
                for loop, sl in zip(nf.loops, f.loops):
                    c = loop_color(sl.vert.co, f.normal)
                    loop[self.col] = (c[0], c[1], c[2], 1.0)
        src.free()

    def add_mesh(self, me, **kw):
        tmp = bmesh.new()
        tmp.from_mesh(me)
        self.add_bm(tmp, **kw)

    def finish(self):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        attr = me.color_attributes.get("Col")
        me.color_attributes.active_color = attr
        try:
            me.color_attributes.render_color_index = me.color_attributes.active_color_index
        except AttributeError:
            pass
        for uv in list(me.uv_layers):
            me.uv_layers.remove(uv)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def shade(n, factor=1.0):
    """Per-face shade factor for shared pieces: the instance colour supplies albedo and baked light."""
    k = (0.55 + 0.45 * max(0.0, n.dot(SHADE_DIR))) * factor
    return (k, k, k)


RENDER = {"on": False}   # True while building the Cycles scene: colours are plain albedo, lights are real


def baker(sources, albedo):
    """Per-face colour for props exported in place: albedo x baked light at the face (albedo alone for Cycles)."""
    a = albedo if isinstance(albedo, tuple) else lin(albedo)
    if RENDER["on"]:
        return lambda _c, _n: a

    def fn(c, n):
        r, g, b = L.light_at(c.x, c.y, c.z, n.x, n.y, n.z, sources)
        return (min(4.0, a[0] * r), min(4.0, a[1] * g), min(4.0, a[2] * b))
    return fn


def glow(hexstr, k=1.0, strength=1.0):
    """Self-lit faces (lantern cores, glowing tags, the tent door). The 4th value is the Cycles emission mask."""
    c = lin(hexstr)
    return lambda _c, _n: (c[0] * k, c[1] * k, c[2] * k, strength)


def cube_bm(size, loc=(0, 0, 0), rot=None):
    bm = bmesh.new()
    m = Matrix.LocRotScale(Vector(loc), rot, Vector(size))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return bm


def cone_bm(r1, r2, depth, segments=10, loc=(0, 0, 0), rot=None, caps=True):
    bm = bmesh.new()
    m = Matrix.LocRotScale(Vector(loc), rot, None)
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segments, radius1=r1, radius2=r2,
                          depth=depth, matrix=m)
    return bm


def ico_bm(rng, subdiv=1, squash=0.62, jitter=0.2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        v.co *= rng.uniform(1 - jitter, 1 + jitter)
        v.co.z *= squash
    return bm


def bm_from_data(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    return bm


def text_bm(text, size, font, extrude=0.0):
    """Flat, low-resolution text (a few hundred vertices per word): it only ever faces the viewer."""
    cu = bpy.data.curves.new("Txt", "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = extrude
    cu.resolution_u = 2
    if font is not None:
        cu.font = font
    ob = bpy.data.objects.new("Txt", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm


def text_on(text, size, font, max_w, frame):
    """Text standing in a vertical plane: frame = Matrix placing local x (reading) and z (up), facing -y."""
    bm = text_bm(text, size, font)
    xs = [v.co.x for v in bm.verts]
    w = (max(xs) - min(xs)) if xs else 0.0
    k = min(1.0, max_w / w) if w > 0 else 1.0
    # curve text lies in XY facing +Z; stand it up: x -> x, y -> z, z -> -y (toward the viewer)
    stand = Matrix(((k, 0, 0, 0), (0, 0, -k, 0), (0, k, 0, 0), (0, 0, 0, 1)))
    bm.transform(frame @ stand)
    return bm


LABELS = []   # prop text, drawn by the browser as canvas textures (and by Cycles in the stills)


def add_label(text, size, max_w, m, local, albedo_hex, sources, key=None):
    """Record text standing on a prop: centre `local` in the prop frame `m`, facing the frame's -y."""
    pos = m @ Vector(local)
    r3 = m.to_3x3()
    normal = (r3 @ Vector((0, -1, 0))).normalized()
    up = (r3 @ Vector((0, 0, 1))).normalized()
    a = lin(albedo_hex)
    lr, lg, lb = L.light_at(pos.x, pos.y, pos.z, normal.x, normal.y, normal.z, sources)
    LABELS.append({"text": text, "key": key, "pos": list(pos), "normal": list(normal), "up": list(up), "size": size,
                   "maxWidth": max_w, "color": [min(4.0, a[0] * lr), min(4.0, a[1] * lg), min(4.0, a[2] * lb)]})


def load_font():
    for fp in FONT_PATHS:
        if Path(fp).exists():
            return bpy.data.fonts.load(fp, check_existing=True)
    return None


def frame_matrix(pos, yaw):
    return Matrix.Translation(Vector(pos)) @ Matrix.Rotation(yaw, 4, "Z")


# ---------------------------------------------------------------- shared pieces (at the origin)

def trunk_bm(rng, sides=7):
    zs = [-0.4, 0.25, 1.5, 4.0, 7.0, 11.0, 16.0]
    rs = [1.5, 1.12, 1.0, 0.9, 0.78, 0.66, 0.5]
    verts, faces = [], []
    for z, r in zip(zs, rs):
        tw = rng.uniform(0, 0.4)
        for j in range(sides):
            a = 2 * math.pi * j / sides + tw
            rr = r * rng.uniform(0.93, 1.07)
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    for i in range(len(zs) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple((len(zs) - 1) * sides + j for j in range(sides)))
    return bm_from_data(verts, faces)


def fern_bm(rng, fronds=7, segs=6):
    verts, faces = [], []
    up = Vector((0, 0, 1))
    for k in range(fronds):
        ang = 2 * math.pi * k / fronds + rng.uniform(-0.3, 0.3)
        ln = rng.uniform(0.7, 1.0)
        e0, e1 = math.radians(rng.uniform(55, 78)), math.radians(rng.uniform(-38, -12))
        wdt = 0.13 * ln
        d = Vector((math.cos(ang), math.sin(ang), 0))
        lat = Vector((-math.sin(ang), math.cos(ang), 0))
        po = pu = 0.0
        base = len(verts)
        for i in range(segs + 1):
            s = i / segs
            if i:
                a = e0 + (e1 - e0) * ((i - 0.5) / segs)
                po += (ln / segs) * math.cos(a)
                pu += (ln / segs) * math.sin(a)
            w = wdt * (math.sin(math.pi * min(s, 0.999)) ** 0.7) * (1.0 if i % 2 == 0 else 0.6) + 0.004
            c = d * po + up * pu
            verts += [c - lat * w, c + up * (0.22 * w), c + lat * w]
        for i in range(segs):
            a0, a1 = base + 3 * i, base + 3 * i + 3
            faces += [(a0, a0 + 1, a1 + 1, a1), (a0 + 1, a0 + 2, a1 + 2, a1 + 1)]
    return bm_from_data(verts, faces)


def post_bm():
    bm = cone_bm(L.POST_R, L.POST_R * 0.96, L.POST_H + 0.3, segments=12, loc=(0, 0, (L.POST_H + 0.3) / 2 - 0.3))
    for v in bm.verts:
        if v.co.z > L.POST_H - 0.01:
            v.co.z += 0.012
    return bm


def board_bm():
    x0, x1 = -L.BOARD_TAIL, L.BOARD_L - L.BOARD_TAIL
    hw, ht = L.BOARD_W / 2, L.BOARD_T / 2
    outline = [(x0, -hw), (x1 - hw, -hw), (x1, 0.0), (x1 - hw, hw), (x0, hw)]
    verts = [(x, -ht, z) for x, z in outline] + [(x, ht, z) for x, z in outline]
    n = len(outline)
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return bm_from_data(verts, faces)


def closed_catmull(ctrl, per_seg=10):
    pts = [Vector(p) for p in ctrl]
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        if (p2 - p1).length < 1e-6:
            continue
        for k in range(per_seg):
            t = k / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    return out


def flame_shell_bm(outline, extrude, bevel):
    cu = bpy.data.curves.new("Shell", "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 0
    pts = closed_catmull(outline, 5)
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts):
        p.co = (v.x, v.y, 0.0, 1.0)
    sp.use_cyclic_u = True
    ob = bpy.data.objects.new("ShellTmp", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    # stand the outline up: outline y -> z (height); the extrusion runs along y, front toward -y
    bm.transform(Matrix.Rotation(math.pi / 2, 4, "X"))
    return bm


FLAME_SHELLS = [
    ("FlameOuter", L.FLAME_OUTER, 0.00, 0.050, 0.030, 1.80, [(0.0, "#FF7A00"), (0.55, "#FF5A00"), (1.0, "#F04000")]),
    ("FlameMid", L.FLAME_MID, 0.10, 0.045, 0.028, 1.42, [(0.0, "#FFB400"), (0.6, "#FF9000"), (1.0, "#FF7000")]),
    ("FlameInner", L.FLAME_INNER, 0.19, 0.040, 0.024, 1.08, [(0.0, "#FFF0B0"), (0.7, "#FFD45A"), (1.0, "#FFB820")]),
]


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            k = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
            return L.mix(lin(c0), lin(c1), k)
    return lin(stops[-1][1])


def crystal_bm(radius=0.15, top=0.33, bottom=0.24, sides=6):
    verts = [(0, 0, top), (0, 0, -bottom)]
    for j in range(sides):
        a = 2 * math.pi * j / sides + math.pi / sides
        verts.append((radius * math.cos(a), radius * math.sin(a), 0.0))
    faces = []
    for j in range(sides):
        a, b = 2 + j, 2 + (j + 1) % sides
        faces += [(0, a, b), (1, b, a)]
    return bm_from_data(verts, faces)


def crystal_color(_c, n):
    facing = max(0.0, -n.y)         # the flame faces -y (toward the viewer after billboarding)
    return ramp([(0.0, "#0B2A9E"), (0.5, "#2A7BFF"), (1.0, "#8FDCFF")], 0.25 + 0.75 * facing)


def build_shared(rng):
    obs = []
    for i in range(4):
        p = Part(f"Trunk{i}")
        p.add_bm(trunk_bm(rng), face_color=lambda c, n: shade(n))
        obs.append(p.finish())
    p = Part("Branch")
    p.add_bm(cone_bm(0.07, 0.02, 1.0, segments=5, loc=(0, 0, 0.5)), face_color=lambda c, n: shade(n))
    obs.append(p.finish())
    for i in range(4):
        p = Part(f"Clump{i}")
        p.add_bm(ico_bm(rng, 1, 0.62), face_color=lambda c, n: shade(n))
        obs.append(p.finish())
    for i in range(2):
        p = Part(f"Canopy{i}")
        p.add_bm(ico_bm(rng, 1, 0.5), face_color=lambda c, n: shade(n))
        obs.append(p.finish())
    for i in range(4):
        p = Part(f"Fern{i}")
        p.add_bm(fern_bm(rng), face_color=lambda c, n: shade(n))
        obs.append(p.finish())
    p = Part("Post")
    p.add_bm(post_bm(), face_color=lambda c, n: shade(n, 1.25 if n.z > 0.9 else 1.0))
    obs.append(p.finish())
    p = Part("Board")
    p.add_bm(board_bm(), face_color=lambda c, n: shade(n))
    obs.append(p.finish())
    p = Part("TorchStaff")
    p.add_bm(cone_bm(0.032, 0.026, L.TORCH_H + 0.3, 10, loc=(0, 0, (L.TORCH_H + 0.3) / 2 - 0.3)),
             face_color=lambda c, n: shade(n))
    for zc in (L.TORCH_H - 0.22, L.TORCH_H - 0.33):
        p.add_bm(cone_bm(0.034, 0.034, 0.02, 12, loc=(0, 0, zc)), face_color=lambda c, n: shade(n, 0.35))
    obs.append(p.finish())
    p = Part("TorchCup")
    p.add_bm(cone_bm(0.040, 0.082, 0.15, 14, loc=(0, 0, 0.03)), face_color=lambda c, n: shade(n))
    p.add_bm(cone_bm(0.088, 0.088, 0.016, 14, loc=(0, 0, 0.108)), face_color=lambda c, n: shade(n, 1.15))
    obs.append(p.finish())
    for name, outline, depth, ext, bev, h, stops in FLAME_SHELLS:
        p = Part(name)
        p.add_bm(flame_shell_bm(outline, ext, bev), loop_color=lambda co, n, s=stops, hh=h: ramp(s, co.z / hh),
                 matrix=Matrix.Translation((0, -depth, 0)))
        obs.append(p.finish())
    p = Part("Crystal")
    p.add_bm(crystal_bm(), face_color=crystal_color, matrix=Matrix.Translation((0, -0.30, 0.50)) @
             Matrix.Rotation(math.radians(8), 4, "Z"))
    obs.append(p.finish())
    return obs


# ---------------------------------------------------------------- props in place (baked)

def build_ground(name, ground):
    p = Part(name)
    bm = bm_from_data([tuple(v) for v in ground["verts"]], [tuple(f) for f in ground["faces"]])
    colors = ground["albedo"] if RENDER["on"] else ground["colors"]
    bm.verts.index_update()
    vmap = [p.bm.verts.new(v.co) for v in bm.verts]
    for f in bm.faces:
        try:
            nf = p.bm.faces.new([vmap[v.index] for v in f.verts])
        except ValueError:
            continue
        for loop in nf.loops:
            c = colors[loop.vert.index]
            loop[p.col] = (c[0], c[1], c[2], 1.0)
    bm.free()
    return p.finish()


def build_stream(world, rng):
    st = world["props"]["stream"]
    src = world["sources"]
    stream = L.Spline(st["centerline"])
    half = st["half"] + 0.55
    verts, faces, uvs = [], [], []
    across = 6
    n = len(stream.pts)
    step = 3
    rows = list(range(0, n, step))
    for i in rows:
        s = i * stream.step
        x, y, tx, ty = stream.at(s)
        zw = world["terrain"].raw(x, y) - 0.25
        for j in range(across + 1):
            u = j / across
            off = (-1 + 2 * u) * half
            verts.append((x - ty * off, y + tx * off, zw))
            uvs.append((u, s / 3.0))
    cols = across + 1
    for r in range(len(rows) - 1):
        for j in range(across):
            a = r * cols + j
            faces.append((a, a + 1, a + cols + 1, a + cols))
    water_col = lin("#0A2229")
    me = bpy.data.meshes.new("Water")
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        uvl.data[loop.index].uv = uvs[loop.vertex_index]
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    for poly in me.polygons:
        c = poly.center
        r, g, b = L.light_at(c.x, c.y, c.z, 0, 0, 1, src)
        for li in poly.loop_indices:
            attr.data[li].color = (water_col[0] * r, water_col[1] * g, water_col[2] * b, 1.0)
    me.color_attributes.active_color = attr
    water = bpy.data.objects.new("Water", me)
    bpy.context.scene.collection.objects.link(water)
    obs = [water]
    foam = Part("Foam")
    white = lin("#9FB8BD")
    for rk in st["rocks"]:
        rock = Part(f"Rock{rk['index']}")
        bm = ico_bm(rng, 2, 0.72, 0.18)
        r = rk["r"]
        rock.add_bm(bm, face_color=baker(src, "#4A544E"),
                    matrix=Matrix.LocRotScale(Vector(rk["pos"]), Matrix.Rotation(rk["yaw"], 3, "Z").to_quaternion(),
                                              Vector((r, r * 1.15, r * 0.8))))
        obs.append(rock.finish())
        cx, cy = rk["pos"][0], rk["pos"][1]
        zw = rk["water"] + 0.012
        tx, ty = rk["flow"]
        fv, ff = [], []
        segs = 16
        for i in range(segs):
            a = 2 * math.pi * i / segs
            dvx, dvy = math.cos(a), math.sin(a)
            ro = r * (1.06 + 0.08 * rng.random()) * (1.0 + 0.35 * max(0.0, dvx * tx + dvy * ty))
            fv += [(cx + dvx * r * 0.93, cy + dvy * r * 0.93, zw), (cx + dvx * ro, cy + dvy * ro, zw)]
        for i in range(segs):
            a, b = 2 * i, 2 * ((i + 1) % segs)
            ff.append((a, b, b + 1, a + 1))
        for side in (-1, 1):
            base = len(fv)
            nx, ny = -ty * side, tx * side
            a0 = (cx + tx * r * 1.1 + nx * r * 0.45, cy + ty * r * 1.1 + ny * r * 0.45)
            a1 = (cx + tx * (r * 1.1 + 1.5) + nx * (r * 0.45 + 0.55), cy + ty * (r * 1.1 + 1.5) + ny * (r * 0.45 + 0.55))
            fv += [(a0[0], a0[1], zw), (a0[0] + nx * 0.025, a0[1] + ny * 0.025, zw), (a1[0], a1[1], zw)]
            ff.append((base, base + 1, base + 2))
        foam.add_bm(bm_from_data(fv, ff), face_color=lambda c, n: (white[0] * 0.5, white[1] * 0.5, white[2] * 0.5, 0.02))
    obs.append(foam.finish())
    return obs


def build_camp(world, rng, font):
    src = world["sources"]
    obs = []
    tent = world["props"]["tent"]
    m = frame_matrix(tent["pos"], tent["yaw"])
    hw, hl, h = L.TENT_SIZE
    tv = [(-hw, -hl, 0), (hw, -hl, 0), (hw, hl, 0), (-hw, hl, 0), (0, -hl - 0.08, h), (0, hl + 0.08, h)]
    tf = [(0, 3, 5, 4), (1, 4, 5, 2), (3, 2, 5), (0, 1, 4)]
    # the lamp inside lights the doorway and the ground in front of it, not the canvas around it
    outside = dict(src, points=[s for s in src["points"] if list(s[0]) != list(tent["glow"])])
    p = Part("Tent")
    p.add_bm(bm_from_data(tv, tf), face_color=baker(outside, "#9C7542"), matrix=m)
    obs.append(p.finish())
    p = Part("TentDoor")
    p.add_bm(bm_from_data([(-0.42, -hl - 0.012, 0.0), (0.42, -hl - 0.012, 0.0), (0, -hl - 0.05, h * 0.78)],
                          [(0, 1, 2)]), face_color=glow("#FFB768", 1.0), matrix=m)
    obs.append(p.finish())

    rack = world["props"]["rack"]
    m = frame_matrix(rack["pos"], rack["yaw"])
    wood, burn, brass, iron = baker(src, "#8E7D63"), baker(src, "#2A1A0F"), baker(src, "#A88A52"), baker(src, "#221E1B")
    p = Part("Rack")
    for sx in (-0.52, 0.52):
        p.add_bm(cube_bm((0.07, 0.07, 1.45), (sx, 0, 0.62)), face_color=wood, matrix=m)
    p.add_bm(cube_bm((1.12, 0.03, 0.58), (0, -0.035, 1.02)), face_color=wood, matrix=m)
    keys = Part("Key")
    for k, name in enumerate(("Jira", "Confluence", "GitLab", "Artifactory")):
        col, row = k % 2, k // 2
        lx, lz = (-0.27 if col == 0 else 0.27), 1.21 - row * 0.3
        add_label(name, 0.055, 0.46, m, (lx, -0.052, lz), "#2A1A0F", src, key=f"key:{name}")
        p.add_bm(cube_bm((0.012, 0.05, 0.012), (lx, -0.075, lz - 0.06)), face_color=iron, matrix=m)
        km = Matrix.Translation((lx, -0.1, lz - 0.1)) @ Matrix.Rotation(rng.uniform(-0.2, 0.2), 4, "Y")
        kb = cone_bm(0.036, 0.036, 0.007, 14, rot=Matrix.Rotation(math.pi / 2, 3, "X").to_quaternion())
        keys.add_bm(kb, face_color=brass, matrix=m @ km)
        keys.add_bm(cube_bm((0.014, 0.007, 0.13), (0, 0, -0.095)), face_color=brass, matrix=m @ km)
        for zc, w in ((-0.14, 0.036), (-0.115, 0.026)):
            keys.add_bm(cube_bm((w, 0.007, 0.013), (0.012 + w / 2 - 0.007, 0, zc)), face_color=brass, matrix=m @ km)
    obs += [p.finish(), keys.finish()]

    crate = world["props"]["crate"]
    p = Part("Crate")
    p.add_bm(cube_bm((0.62, 0.44, 0.4), (0, 0, 0.2)), face_color=baker(src, "#7A6A52"),
             matrix=frame_matrix(crate["pos"], crate["yaw"]))
    obs.append(p.finish())
    seat = world["props"]["log_seat"]
    p = Part("LogSeat")
    p.add_bm(cone_bm(0.17, 0.16, 1.1, 10, rot=Matrix.Rotation(math.pi / 2, 3, "Y").to_quaternion()),
             face_color=baker(src, "#3A2F29"),
             matrix=Matrix.Translation(Vector(seat["pos"]) + Vector((0, 0, 0.15))) @ Matrix.Rotation(seat["yaw"], 4, "Z"))
    obs.append(p.finish())
    pole = world["props"]["lantern_pole"]
    m = frame_matrix(pole["pos"], pole["yaw"])
    p = Part("LanternPole")
    p.add_bm(cube_bm((0.06, 0.06, 1.9), (0, 0, 0.9)), face_color=wood, matrix=m)
    p.add_bm(cube_bm((0.4, 0.05, 0.05), (-0.18, 0, 1.78)), face_color=wood, matrix=m)
    p.add_bm(cube_bm((0.12, 0.12, 0.17), (-0.34, 0, 1.6)), face_color=iron, matrix=m)
    p.add_bm(cube_bm((0.09, 0.125, 0.125), (-0.34, 0, 1.6)), face_color=glow("#FFC070", 1.0), matrix=m)
    obs.append(p.finish())
    return obs


def build_kiosk(world, font):
    src = world["sources"]
    k = world["props"]["kiosk"]
    m = frame_matrix(k["pos"], k["yaw"])
    wood, dark = baker(src, "#8E7D63"), baker(src, "#5E4E3C")
    paper = baker(src, "#DCCDA6")
    iron = baker(src, "#221E1B")
    p = Part("Kiosk")
    for sx in (-0.8, 0.8):
        p.add_bm(cube_bm((0.1, 0.1, 2.35), (sx, 0, 1.02)), face_color=dark, matrix=m)
    p.add_bm(cube_bm((1.52, 0.05, 1.02), (0, -0.07, 1.35)), face_color=dark, matrix=m)
    p.add_bm(cube_bm((1.72, 0.05, 0.22), (0, -0.07, 2.03)), face_color=wood, matrix=m)
    add_label("KNOWLEDGE BASE", 0.11, 1.5, m, (0, -0.097, 2.03), "#2A1A0F", src, key="kiosk:header")
    for sy, ang in ((-0.3, 24), (0.3, -24)):
        p.add_bm(cube_bm((1.98, 0.72, 0.04), (0, sy, 2.3), Matrix.Rotation(math.radians(ang), 3, "X").to_quaternion()),
                 face_color=wood, matrix=m)
    for sx in (-0.62, 0.62):
        p.add_bm(cube_bm((0.1, 0.1, 0.15), (sx, -0.5, 1.98)), face_color=iron, matrix=m)
        p.add_bm(cube_bm((0.075, 0.105, 0.105), (sx, -0.5, 1.98)), face_color=glow("#FFC070", 1.0), matrix=m)
    # the map board is plain paper: the page draws the trail map on it (live, and over the still)
    mp = Part("KioskMap")
    mp.add_bm(cube_bm((L.MAP_BOARD[0], 0.012, L.MAP_BOARD[1]), (0, -0.1, L.MAP_FACE[2])), face_color=paper, matrix=m)
    return [p.finish(), mp.finish()]


def build_launch(world, rng, font):
    src = world["sources"]
    b = world["props"]["board"]
    m = frame_matrix(b["pos"], b["yaw"])
    wood, dark, burn = baker(src, "#8E7D63"), baker(src, "#5E4E3C"), baker(src, "#2A1A0F")
    paper, ink, pin = baker(src, "#EFE6CF"), baker(src, "#4A3626"), baker(src, "#B83A2A")
    p = Part("LaunchBoard")
    for sx in (-0.88, 0.88):
        p.add_bm(cube_bm((0.1, 0.1, 2.0), (sx, 0, 0.85)), face_color=dark, matrix=m)
    p.add_bm(cube_bm((1.86, 0.05, 0.92), (0, -0.05, 1.25)), face_color=dark, matrix=m)
    p.add_bm(cube_bm((1.9, 0.05, 0.2), (0, -0.05, 1.84)), face_color=wood, matrix=m)
    add_label("IN FLIGHT", 0.11, 1.2, m, (0, -0.077, 1.84), "#2A1A0F", src, key="board:header")
    tags, lit = Part("Tag"), Part("TagLit")
    gone = {(4, 0), (3, 0)}
    glowing = {(2, 0), (4, 1)}
    for col, u in enumerate((-0.68, -0.34, 0.0, 0.34, 0.68)):
        for row, v in enumerate((0.26, 0.0, -0.26)):
            if (col, row) in gone:
                continue
            rot = Matrix.Rotation(math.radians(rng.uniform(-4, 4)), 3, "Y").to_quaternion()
            if (col, row) in glowing:
                lit.add_bm(cube_bm((0.25, 0.004, 0.14), (u, -0.078, 1.25 + v), rot), face_color=glow("#FFB23F", 1.0),
                           matrix=m)
                continue
            tags.add_bm(cube_bm((0.25, 0.004, 0.14), (u, -0.078, 1.25 + v), rot), face_color=paper, matrix=m)
            for j in range(2):
                tags.add_bm(cube_bm((0.16, 0.002, 0.007), (u, -0.081, 1.25 + v + 0.012 - j * 0.03)), face_color=ink,
                            matrix=m)
            tags.add_bm(cone_bm(0.01, 0.01, 0.008, 6, loc=(u, -0.083, 1.25 + v + 0.052),
                                rot=Matrix.Rotation(math.pi / 2, 3, "X").to_quaternion()), face_color=pin, matrix=m)
    return [p.finish(), tags.finish(), lit.finish()]


# ---------------------------------------------------------------- export and checks

def export_glb(path):
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", use_selection=False, export_apply=True, export_yup=True,
        export_normals=False, export_texcoords=True, export_materials="NONE", export_vertex_color="ACTIVE",
        export_all_vertex_colors=False, export_attributes=False)


def self_check(path, required):
    reset()
    bpy.ops.import_scene.gltf(filepath=str(path))
    found = {}
    for ob in bpy.context.scene.objects:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            found[ob.name] = len(ob.data.loop_triangles)
    missing = [n for n in required if n not in found]
    if missing:
        raise RuntimeError(f"self-check failed: {path.name} is missing {missing}")
    size = path.stat().st_size
    if size > GLB_MAX_BYTES:
        raise RuntimeError(f"self-check failed: {path.name} is {size} bytes (budget {GLB_MAX_BYTES})")
    print("SELFCHECK " + json.dumps({"bytes": size, "triangles": found}, sort_keys=True))


def build_web(out):
    rng = __import__("random").Random(7)
    world = L.build_world()
    junction = L.build_junction()
    reset()
    font = load_font()
    obs = build_shared(rng)
    obs.append(build_ground("Ground", world["ground"]))
    obs.append(build_ground("JunctionGround", junction["ground"]))
    obs += build_stream(world, rng)
    obs += build_camp(world, rng, font)
    obs += build_kiosk(world, font)
    obs += build_launch(world, rng, font)
    required = [ob.name for ob in obs]
    glb = out / "blazeahead.glb"
    export_glb(glb)
    web = L.to_web(world)
    web["labels"] = [{"text": lb["text"], "key": lb["key"], "pos": L._p(lb["pos"]), "normal": L._p(lb["normal"], 4),
                      "up": L._p(lb["up"], 4), "size": lb["size"], "maxWidth": lb["maxWidth"],
                      "color": [round(c, 3) for c in lb["color"]]} for lb in LABELS]
    jweb = L.to_web(junction)
    signs = dict(web["stillSigns"])
    signs.update(jweb["stillSigns"])
    (out / "still-signs.json").write_text(json.dumps(signs, separators=(",", ":")), encoding="utf-8")
    for name, data in (("world.json", web), ("junction.json", jweb)):
        (out / name).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    return glb, required, world, junction


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    glb, required, world, junction = build_web(out)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.blend).resolve()))
    self_check(glb, required)
    tour = Path(args.tour)
    if tour.is_file():
        SIGN_TEXT.update(L.read_tour_signs(tour.read_text(encoding="utf-8")))
    print("SIGNS " + json.dumps(SIGN_TEXT))
    if args.stills:
        only = [s for s in args.only.split(",") if s]
        render_all(world, junction, out / "stills", args.samples, only)
    print("BUILD OK")


# ---------------------------------------------------------------- Cycles stills (the fallback images)

import random as _random  # noqa: E402

import numpy as np  # noqa: E402  (bundled with Blender)

SIGN_TEXT = dict(L.DEFAULT_SIGNS)   # main() fills in the words from the owner's tour-content.js
GRADE = {
    "trailhead": dict(fog_density=0.034, fog_start=3.0, exposure=0.35, fstop=2.6),
    "continuity": dict(fog_density=0.03, fog_start=4.0, exposure=0.4, fstop=4.0),
    "scaffolding": dict(fog_density=0.03, fog_start=4.0, exposure=0.4, fstop=4.0),
    "knowledge": dict(fog_density=0.03, fog_start=4.0, exposure=0.4, fstop=4.0),
    "in-flight": dict(fog_density=0.022, fog_start=4.0, exposure=0.4, fstop=5.0),
    "junction": dict(fog_density=0.04, fog_start=3.0, exposure=0.35, fstop=2.8),
}
FOG_LOW, FOG_HIGH = "#2F5560", "#0E1C24"
STILL_SIZE = (1600, 900)


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt, nt.nodes.new("ShaderNodeOutputMaterial")


def no_emission_sampling(m):
    for owner in (m, getattr(m, "cycles", None)):
        if owner is not None and hasattr(owner, "emission_sampling"):
            owner.emission_sampling = "NONE"
            return


def rgba(hexstr):
    return (*lin(hexstr), 1.0)


def ramp_node(nt, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], rgba(stops[0][1])
    els[1].position, els[1].color = stops[-1][0], rgba(stops[-1][1])
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = rgba(col)
    return r


def mat_random(name, hex_a, hex_b, rough=0.85, translucent=0.0, bump=0.0):
    m, nt, out = new_mat(name)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    info = nt.nodes.new("ShaderNodeObjectInfo")
    ramp = ramp_node(nt, [(0.0, hex_a), (1.0, hex_b)])
    nt.links.new(info.outputs["Random"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    shader = bsdf.outputs["BSDF"]
    if bump:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 3.0
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = bump
        nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Fac"], bmp.inputs["Height"])
        nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    if translucent:
        tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
        nt.links.new(ramp.outputs["Color"], tr.inputs["Color"])
        mix_ = nt.nodes.new("ShaderNodeMixShader")
        mix_.inputs[0].default_value = translucent
        nt.links.new(shader, mix_.inputs[1])
        nt.links.new(tr.outputs["BSDF"], mix_.inputs[2])
        shader = mix_.outputs["Shader"]
    nt.links.new(shader, out.inputs["Surface"])
    return m


def mat_attr(name, emission=6.0, rough=0.8):
    """Props: base colour from the Col attribute, emission where the Glow mask is set."""
    m, nt, out = new_mat(name)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    gl = nt.nodes.new("ShaderNodeAttribute")
    gl.attribute_name = "Glow"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = emission
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(col.outputs["Color"], bsdf.inputs["Emission Color"])
    nt.links.new(gl.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], bsdf.inputs["Emission Strength"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_attr_emit(name, strength):
    m, nt, out = new_mat(name)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(col.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    no_emission_sampling(m)
    return m


def mat_emit(name, hexcol, strength):
    m, nt, out = new_mat(name)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba(hexcol)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    no_emission_sampling(m)
    return m


def mat_wood(name, base, dark, bands=14.0):
    m, nt, out = new_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = bands
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = ramp_node(nt, [(0.2, dark), (0.8, base)])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.8
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.25
    nt.links.new(wave.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_bark(name, base, dark):
    m, nt, out = new_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (22.0, 22.0, 1.6)
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 3.0
    tex.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    ramp = ramp_node(nt, [(0.35, dark), (0.65, base)])
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.9
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.6
    nt.links.new(tex.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_water(name):
    m, nt, out = new_mat(name)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = rgba("#071A20")
    bsdf.inputs["Roughness"].default_value = 0.07
    bsdf.inputs["IOR"].default_value = 1.33
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (5.0, 0.6, 1.0)
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 2.5
    tex.inputs["Detail"].default_value = 3.0
    ramp = ramp_node(nt, [(0.58, "#000000"), (0.72, "#FFFFFF")])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.35
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    bsdf.inputs["Emission Color"].default_value = rgba("#8CC7D6")
    nt.links.new(mul.outputs["Value"], bsdf.inputs["Emission Strength"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def fog_material(density, start):
    """Override material for the fog pass: emits transmittance exp(-density*distance); stars (pass index 1) stay clear."""
    m, nt, out = new_mat("FogPass")
    cd = nt.nodes.new("ShaderNodeCameraData")
    ops = []
    for op, val in (("SUBTRACT", start), ("MAXIMUM", 0.0), ("MULTIPLY", -density), ("EXPONENT", None)):
        node = nt.nodes.new("ShaderNodeMath")
        node.operation = op
        if val is not None:
            node.inputs[1].default_value = val
        ops.append(node)
    nt.links.new(cd.outputs["View Distance"], ops[0].inputs[0])
    for a, b in zip(ops, ops[1:]):
        nt.links.new(a.outputs["Value"], b.inputs[0])
    info = nt.nodes.new("ShaderNodeObjectInfo")
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    keep = nt.nodes.new("ShaderNodeMath")
    keep.operation = "MAXIMUM"
    nt.links.new(info.outputs["Object Index"], gt.inputs[0])
    nt.links.new(ops[-1].outputs["Value"], keep.inputs[0])
    nt.links.new(gt.outputs["Value"], keep.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(keep.outputs["Value"], em.inputs["Strength"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def link(name, data, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    return ob


def point_light(name, pos, energy, color, size=0.08):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy, ld.color, ld.shadow_soft_size = energy, color, size
    ob = link(name, ld, pos)
    ob.visible_camera = False
    return ob


def font_object(name, text, size, pos, xdir, up, n, mat, font, max_w):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0012
    if font is not None:
        cu.font = font
    cu.materials.append(mat)
    ob = link(name, cu, pos)
    x, y, z = Vector(xdir).normalized(), Vector(up).normalized(), Vector(n).normalized()
    ob.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
    bpy.context.view_layer.update()
    w = ob.dimensions.x
    if w > max_w:
        ob.scale = (max_w / w,) * 3
    return ob


def build_render_scene(data, labels, rng):
    """The Cycles scene for one world (tour or junction). Returns the flame rigs so each view can face them."""
    labels = list(labels)          # the builders below add their labels again; keep the original set
    RENDER["on"] = True
    reset()
    font = load_font()
    scene = bpy.context.scene
    world = bpy.data.worlds.new("World")
    scene.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = rgba("#0F2029")
    bg.inputs["Strength"].default_value = 0.9
    moon = bpy.data.lights.new("Moon", "SUN")
    moon.energy, moon.color, moon.angle = 0.35, (0.62, 0.78, 1.0), math.radians(4)
    link("Moon", moon).rotation_euler = Vector((0.35, -0.8, -1.0)).to_track_quat("-Z", "Y").to_euler()

    # shared pieces become prototypes (hidden) that every instance links to
    protos = {ob.name: ob for ob in build_shared(rng)}
    mats = {
        "Trunk": mat_random("Bark", L.PALETTE["bark"], L.PALETTE["bark2"], 0.9, bump=0.35),
        "Branch": mat_random("BranchBark", L.PALETTE["bark"], L.PALETTE["bark2"], 0.9),
        "Clump": mat_random("Leaf", L.PALETTE["leaf"], L.PALETTE["leaf2"], 0.75, translucent=0.25),
        "Canopy": mat_random("Canopy", L.PALETTE["canopy"], L.PALETTE["leaf2"], 0.8, translucent=0.15),
        "Fern": mat_random("Fern", L.PALETTE["fern"], L.PALETTE["fern2"], 0.7, translucent=0.35),
        "Post": mat_bark("PostBark", "#5E4D3E", "#2A211B"),
        "Board": mat_wood("BoardWood", L.PALETTE["wood"], L.PALETTE["wood2"]),
        "TorchStaff": mat_bark("StaffBark", "#6A5642", "#35291F"),
        "TorchCup": mat_random("Iron", "#221E1B", "#2E2824", 0.45),
        "FlameOuter": mat_attr_emit("FlameOuterMat", 0.9),
        "FlameMid": mat_attr_emit("FlameMidMat", 1.4),
        "FlameInner": mat_attr_emit("FlameInnerMat", 2.2),
        "Crystal": mat_attr_emit("CrystalMat", 2.4),
    }
    for name, ob in protos.items():
        key = next(k for k in mats if name.startswith(k))
        ob.data.materials.clear()
        ob.data.materials.append(mats[key])
        ob.hide_render = True
        ob.hide_viewport = True
    for mesh_name, items in data["instances"].items():
        me = protos[mesh_name].data
        for i, it in enumerate(items):
            ob = link(f"{mesh_name}.{i}", me, it[0:3])
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = it[3:7]
            ob.scale = it[7:10]

    # props in place, with albedo colours and glow masks
    prop_mat = mat_attr("PropMat")
    props = [build_ground("Ground", data["ground"])]
    if "stream" in data["props"]:
        props += build_stream(data, rng)
        props += build_camp(data, rng, font)
        props += build_kiosk(data, font)
        props += build_launch(data, rng, font)
    water_mat = mat_water("WaterMat")
    for ob in props:
        ob.data.materials.clear()
        ob.data.materials.append(water_mat if ob.name == "Water" else prop_mat)
        if ob.name in ("Foam", "TentDoor", "TagLit"):
            ob.visible_shadow = False

    # flames: one rig per torch, turned toward each view's camera before it renders
    rigs = []
    for k, t in enumerate(data["torches"]):
        rig = bpy.data.objects.new(f"FlameRig{k}", None)
        bpy.context.scene.collection.objects.link(rig)
        rig.location = t["base"]
        rig.scale = (t["scale"],) * 3
        for part in ("FlameOuter", "FlameMid", "FlameInner", "Crystal"):
            ob = link(f"{part}.{k}", protos[part].data)
            ob.parent = rig
            ob.visible_shadow = False
        point_light(f"TorchLight{k}", t["pos"], 90.0 if t["scale"] >= 0.26 else 45.0, (1.0, 0.52, 0.2), 0.08)
        rigs.append(rig)
    for k, lt in enumerate(data["lanterns"]):
        point_light(f"Lantern{k}", lt["pos"], 30.0, (1.0, 0.6, 0.28), 0.08)
    if "tent" in data["props"]:
        point_light("TentLight", data["props"]["tent"]["glow"], 40.0, (1.0, 0.62, 0.3), 0.2)

    # the flowing lights
    mote_me = bpy.data.meshes.new("Mote")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    bm.to_mesh(mote_me)
    bm.free()
    mote_me.materials.append(mat_emit("MoteMat", L.PALETTE["amber"], 22.0))
    for name, pts in data["flows"].items():
        for i, q in enumerate(pts):
            ob = link(f"Mote.{name}.{i}", mote_me, q)
            ob.scale = (0.04,) * 3
            ob.visible_shadow = False
            if i % 2 == 0:
                point_light(f"MoteLight.{name}.{i}", q, 2.0, lin(L.PALETTE["amber"]), 0.04)

    # sign labels and prop labels
    burn = mat_random("Burn", "#2A1A0F", "#24160C", 0.9)
    for k, sg in enumerate(data["signs"]):
        nx, ny = sg["n"]
        off = L.BOARD_T / 2 + 0.0016
        pos = (sg["board"][0] + nx * off, sg["board"][1] + ny * off, sg["board"][2])
        font_object(f"SignLabel{k}", SIGN_TEXT.get(sg["label"], sg["label"]), 0.07, pos, (-ny, nx, 0), (0, 0, 1),
                    (nx, ny, 0), burn, font, 0.33)
    ink = mat_random("Ink", "#2A1A0F", "#3E2C1F", 0.9)
    for k, lb in enumerate(labels):
        nx, ny, nz = lb["normal"]
        font_object(f"PropLabel{k}", lb["text"], lb["size"] * 1.35, lb["pos"], (-ny, nx, 0), lb["up"], lb["normal"],
                    ink, font, lb["maxWidth"])

    # stars over the launch clearing (fog-free)
    if data.get("sky_holes"):
        star_me = bpy.data.meshes.new("Star")
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        bm.to_mesh(star_me)
        bm.free()
        star_me.materials.append(mat_emit("StarMat", "#DDE8FF", 6.0))
        (cx, cy), _r = data["sky_holes"][0]
        for i in range(520):
            az = rng.uniform(0, 2 * math.pi)
            el = math.radians(rng.uniform(18, 85))
            p = (cx + 55 * math.cos(el) * math.cos(az), cy + 55 * math.cos(el) * math.sin(az), 55 * math.sin(el))
            ob = link(f"Star{i}", star_me, p)
            ob.scale = (rng.uniform(0.05, 0.13),) * 3
            ob.visible_shadow = False
            ob.pass_index = 1
    RENDER["on"] = False
    motes = [ob for ob in bpy.context.scene.objects if ob.name.startswith(("Mote.", "MoteLight."))]
    boards = [Vector(sg["board"]) for sg in data["signs"]]
    return {"flames": rigs, "motes": motes, "boards": boards}


def setup_camera(view, fstop):
    scene = bpy.context.scene
    cam = bpy.data.cameras.new("Cam")
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36.0
    cam.lens = 18.0 / math.tan(math.radians(view["hfov"]) / 2)
    pos, tgt = Vector(view["position"]), Vector(view["target"])
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    cam.dof.focus_distance = (tgt - pos).length
    ob = link("Cam", cam, pos)
    ob.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler()
    scene.camera = ob
    bpy.context.view_layer.update()
    return ob


def fill_light(view, energy=30.0):
    fwd = (Vector(view["target"]) - Vector(view["position"])).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    loc = Vector(view["position"]) - right * 0.7 - fwd * 0.4 + Vector((0, 0, 0.45))
    ld = bpy.data.lights.new("Fill", "AREA")
    ld.energy, ld.size, ld.color = energy, 1.4, (1.0, 0.7, 0.42)
    ob = link("Fill", ld, loc)
    ob.rotation_euler = (Vector(view["target"]) - loc).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    return ob


def set_view_transform(exposure):
    vs = bpy.context.scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = exposure


def render_passes(tmp, name, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = STILL_SIZE
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.volume_bounces = 0
    sc.cycles.transparent_max_bounces = 4
    sc.cycles.sample_clamp_indirect = 3.0
    fmt = sc.render.image_settings
    fmt.file_format = "OPEN_EXR"
    fmt.color_depth = "32"
    fmt.color_mode = "RGBA"
    sc.render.filepath = str(tmp / f"{name}_beauty")
    bpy.ops.render.render(write_still=True)
    g = GRADE[name]
    vl = bpy.context.view_layer
    vl.material_override = fog_material(g["fog_density"], g["fog_start"])
    bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
    strength = bg.inputs["Strength"].default_value
    bg.inputs["Strength"].default_value = 0.0
    sc.cycles.samples = 16
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.render.filepath = str(tmp / f"{name}_fog")
    bpy.ops.render.render(write_still=True)
    vl.material_override = None
    bg.inputs["Strength"].default_value = strength


def load_px(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def box_blur(a, r, axis):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    return (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis) - np.take(c, np.arange(n), axis=axis)) / (2 * r + 1)


def blur(a, sigma):
    r = max(1, int(round(sigma)))
    for axis in (0, 1):
        for _ in range(3):
            a = box_blur(a, r, axis)
    return a


def grade(tmp, name, out_path):
    beauty = load_px(tmp / f"{name}_beauty.exr")
    T = np.clip(load_px(tmp / f"{name}_fog.exr")[..., :1], 0, 1).astype(np.float64)
    rgb = beauty[..., :3].astype(np.float64)
    h, w = rgb.shape[:2]
    yy = np.linspace(0, 1, h)[:, None, None]
    band = np.exp(-((yy - 0.5) / 0.28) ** 2)
    fog_lo, fog_hi = np.array(lin(FOG_LOW)), np.array(lin(FOG_HIGH))
    fog = fog_hi + (fog_lo - fog_hi) * band
    rgb = rgb * T + fog * (1 - T)
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    k = np.clip((lum - 0.8) / 0.6, 0, 1) ** 2
    bright = rgb * k[..., None]
    s = w / 1600.0
    bloom = (0.45 * blur(bright, 3 * s) + 0.35 * blur(bright, 10 * s) + 0.3 * blur(bright, 30 * s)
             + 0.25 * blur(bright, 80 * s))
    rgb = rgb + bloom * 0.7
    ys, xs = np.mgrid[0:h, 0:w]
    r2 = ((xs / w - 0.5) * 1.2) ** 2 + ((ys / h - 0.5) * 1.0) ** 2
    rgb *= (1 - 0.45 * r2)[..., None]
    img = bpy.data.images.new(f"{name}_graded", w, h, alpha=True, float_buffer=True)
    for cs in ("Linear Rec.709", "Linear", "scene_linear"):
        try:
            img.colorspace_settings.name = cs
            break
        except TypeError:
            continue
    img.pixels.foreach_set(np.concatenate([rgb, np.ones((h, w, 1))], -1).astype(np.float32).ravel())
    sc = bpy.context.scene
    set_view_transform(GRADE[name]["exposure"])
    fmt = sc.render.image_settings
    fmt.file_format = "WEBP"
    fmt.color_mode = "RGB"
    fmt.quality = 82
    img.save_render(str(out_path), scene=sc)
    bpy.data.images.remove(img)
    print("STILL", out_path)


def render_view(name, view, rigs, out_dir, tmp, samples):
    cam = setup_camera(view, GRADE[name]["fstop"])
    for rig in rigs["flames"]:
        d = cam.location - rig.location
        rig.rotation_euler = (0, 0, math.atan2(d.y, d.x) + math.pi / 2)
    # lights right in front of the lens or over a signpost's words would hide them: leave those out of this view
    for ob in rigs["motes"]:
        p = ob.location
        ob.hide_render = (p - cam.location).length < 3.3 or any((p - b).length < 1.0 for b in rigs["boards"])
    fill = fill_light(view)
    set_view_transform(GRADE[name]["exposure"])
    render_passes(tmp, name, samples)
    grade(tmp, name, out_dir / f"{name}.webp")
    bpy.data.objects.remove(fill)
    bpy.data.objects.remove(cam)


def render_all(world, junction, out_dir, samples, only=()):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = HERE / "_render"
    tmp.mkdir(exist_ok=True)
    rng = _random.Random(3)
    wanted = [n for n in ["trailhead", *L.STOP_IDS] if not only or n in only]
    if wanted:
        rigs = build_render_scene(world, LABELS, rng)
        for name in wanted:
            render_view(name, world["views"][name], rigs, out_dir, tmp, samples)
    if not only or "junction" in only:
        rigs = build_render_scene(junction, [], rng)
        render_view("junction", junction["views"]["junction"], rigs, out_dir, tmp, samples)


if __name__ == "__main__":
    main()

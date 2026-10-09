"""Build the Coalesce 3D pieces in Blender (headless) and export them for the website.

  blender -b --factory-startup --python-exit-code 1 --python blender/build_coalesce.py -- [options]

  --out DIR      where coalesce.glb, layout.json and the stills go   (default: public/assets)
  --blend PATH   where to save the editable .blend                    (default: blender/coalesce.blend)
  --stills       also render home-still.webp and help-still.webp with Cycles (minutes)
  --samples N    Cycles samples for the Home still; Help uses twice as many (default: 32)
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
import coalesce_layout as L  # noqa: E402

PALETTE = {"teal": "#1D5E5B", "terra": "#C4623A", "ink": "#1B2423", "paper": "#F4F0E8"}
WEB_MESHES = ("Person", "MagnifierRim", "MagnifierCollar", "MagnifierHandle")
PERSON_MAX_TRIS = 900


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE.parent / "public" / "assets"))
    parser.add_argument("--blend", default=str(HERE / "coalesce.blend"))
    parser.add_argument("--stills", action="store_true")
    parser.add_argument("--samples", type=int, default=32)
    return parser.parse_args(argv)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def lin(hexstr):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def node_tree(idblock):
    try:
        idblock.use_nodes = True  # always on in Blender 5, still needed on 4.x
    except Exception:
        pass
    return idblock.node_tree


def principled(name, hexcol, rough=0.4, metal=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    bsdf = next(n for n in node_tree(mat).nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin(hexcol), 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def glass(name):
    mat = bpy.data.materials.new(name)
    bsdf = next(n for n in node_tree(mat).nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["IOR"].default_value = 1.5
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    return mat


def finish_mesh(name, bm, mat, smooth_angle=40):
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    me.materials.append(mat)
    return me


def bevel_ring(bm, z, offset, segments):
    edges = [e for e in bm.edges if all(abs(v.co.z - z) < 1e-4 for v in e.verts)]
    verts = list({v for e in edges for v in e.verts})
    bmesh.ops.bevel(bm, geom=edges + verts, offset=offset, offset_type="OFFSET",
                    profile_type="SUPERELLIPSE", segments=segments, profile=0.5,
                    affect="EDGES", clamp_overlap=True)


def person_mesh(mat, name="Person"):
    """Rounded 'shoulders' body with a separate head (the classic person icon), about 600 triangles."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                          radius1=0.30, radius2=0.30, depth=0.34)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, 0.17))
    bevel_ring(bm, 0.34, 0.14, 5)
    bevel_ring(bm, 0.0, 0.025, 1)
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.16,
                              matrix=Matrix.Translation((0, 0, 0.555)))
    return finish_mesh(name, bm, mat)


def ring_mesh(name, mat, r_in, r_out, half_depth, steps=96):
    """Flat ring in the XZ plane (it faces -Y, the camera); its thickness runs along Y."""
    bm = bmesh.new()
    loops = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        loops.append([bm.verts.new((r * c, y, r * s)) for r, y in
                      ((r_in, -half_depth), (r_out, -half_depth), (r_out, half_depth), (r_in, half_depth))])
    for a, b in zip(loops, loops[1:] + loops[:1]):
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return finish_mesh(name, bm, mat, smooth_angle=35)


def rod_mesh(name, mat, radius, length, start, angle_deg, segments=24):
    """Cylinder lying in the XZ plane along `angle_deg`, spanning [start, start + length] from the origin."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius, depth=length)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, start + length / 2))
    a = math.radians(angle_deg)
    turn = Vector((0, 0, 1)).rotation_difference(Vector((math.cos(a), 0.0, math.sin(a))))
    bmesh.ops.transform(bm, matrix=turn.to_matrix().to_4x4(), verts=bm.verts[:])
    return finish_mesh(name, bm, mat, smooth_angle=35)


def magnifier_meshes(ink):
    m = L.MAGNIFIER
    return [
        ring_mesh("MagnifierRim", ink, m["lensRadius"], m["rimOuter"], 0.1),
        rod_mesh("MagnifierCollar", ink, 0.14, 0.34, m["rimOuter"], m["handleAngleDeg"]),
        rod_mesh("MagnifierHandle", ink, 0.105, 1.35, m["rimOuter"] + 0.34, m["handleAngleDeg"]),
    ]


def link(me, location=(0, 0, 0), rotation=None, scale=1.0):
    ob = bpy.data.objects.new(me.name, me)
    ob.location = location
    if rotation is not None:
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = rotation
    ob.scale = (scale, scale, scale)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_web_pieces():
    teal = principled("Teal", PALETTE["teal"], rough=0.38, coat=0.3)
    ink = principled("Ink", PALETTE["ink"], rough=0.3, metal=0.5, coat=0.4)
    return [link(me) for me in [person_mesh(teal), *magnifier_meshes(ink)]]


def export_glb(objects, path):
    for ob in bpy.context.scene.objects:
        ob.select_set(ob in objects)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True, export_normals=True,
                              export_materials="EXPORT", export_cameras=False,
                              export_lights=False, export_animations=False)


def self_check(path):
    """Re-import the GLB into an empty scene and confirm the pieces the website needs are there."""
    reset()
    bpy.ops.import_scene.gltf(filepath=str(path))
    found = {}
    for ob in bpy.context.scene.objects:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            found[ob.name] = len(ob.data.loop_triangles)
    missing = [name for name in WEB_MESHES if name not in found]
    if missing:
        raise RuntimeError(f"self-check failed: {path.name} is missing {missing}")
    if found["Person"] > PERSON_MAX_TRIS:
        raise RuntimeError(f"self-check failed: Person has {found['Person']} triangles (max {PERSON_MAX_TRIS})")
    print("SELFCHECK " + json.dumps(found, sort_keys=True))


# ---------------------------------------------------------------- stills

def area_light(name, location, target, energy, size, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.energy, light.size, light.color = energy, size, color
    ob = bpy.data.objects.new(name, light)
    ob.location = location
    ob.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)


def lights():
    area_light("Key", (-6, -8, 8), (0, 0, 2.5), 1300, 6, (1.0, 0.97, 0.92))
    area_light("Fill", (7, -6, 3), (0, 0, 2.5), 350, 6)
    area_light("Rim", (0, 6, 7), (0, 0, 2.5), 700, 5)


def studio_world(seen_through=None):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    nt = node_tree(world)
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    folder = Path(bpy.utils.system_resource("DATAFILES", path="studiolights/world") or ".")
    hdri = folder / "studio.exr"
    if hdri.is_file():
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(hdri))
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.5
    if seen_through:  # refracted rays see the page colour instead of the studio HDRI
        out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
        path = nt.nodes.new("ShaderNodeLightPath")
        flat = nt.nodes.new("ShaderNodeBackground")
        flat.inputs["Color"].default_value = (*lin(seen_through), 1.0)
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Transmission Ray"], mix.inputs[0])
        nt.links.new(bg.outputs["Background"], mix.inputs[1])
        nt.links.new(flat.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def still_camera():
    cam = bpy.data.cameras.new("Camera")
    cam.lens, cam.sensor_width = L.LENS_MM, L.SENSOR_MM
    ob = bpy.data.objects.new("Camera", cam)
    ob.location = L.camera_position()
    ob.rotation_euler = (Vector(L.CAMERA_TARGET) - ob.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def render(path, samples, transparent_glass=False):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.film_transparent_glass = transparent_glass
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = L.STILL_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.quality = 82
    scene.render.filepath = str(path)
    scene.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def crowd(teal, terra, is_terra):
    for i, position in enumerate(L.crowd_positions()):
        link(terra if is_terra(i) else teal, location=position, scale=L.TOKEN_SCALE)


def people_meshes():
    teal = person_mesh(principled("Teal", PALETTE["teal"], rough=0.35, coat=0.35), "PersonTeal")
    terra = person_mesh(principled("Terra", PALETTE["terra"], rough=0.32, coat=0.35), "PersonTerra")
    return teal, terra


def render_stills(out, samples):
    positions = L.crowd_positions()

    reset()
    teal, terra = people_meshes()
    accents = L.accent_flags(len(positions))
    crowd(teal, terra, lambda i: accents[i])
    studio_world()
    lights()
    still_camera()
    render(Path(out) / "home-still.webp", samples)

    reset()
    teal, terra = people_meshes()
    focus = L.help_focus_index(positions)
    crowd(teal, terra, lambda i: i == focus)
    studio_world(seen_through=PALETTE["paper"])
    lights()
    cam = still_camera()
    centre = Vector(positions[focus]) + Vector((0, 0, 0.14))
    lens_at = centre + (cam.location - centre).normalized() * L.MAGNIFIER["standoff"]
    facing = Vector((0, -1, 0)).rotation_difference((cam.location - lens_at).normalized())
    ink = principled("Ink", PALETTE["ink"], rough=0.3, metal=0.5, coat=0.4)
    for me in magnifier_meshes(ink):
        link(me, location=lens_at, rotation=facing)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=L.MAGNIFIER["lensRadius"] + 0.02)
    for v in bm.verts:
        v.co.y *= 0.18  # flatten along the viewing axis: a biconvex lens that magnifies about 2x
    lens = bpy.data.meshes.new("Lens")
    bm.to_mesh(lens)
    bm.free()
    for poly in lens.polygons:
        poly.use_smooth = True
    lens.materials.append(glass("Glass"))
    link(lens, location=lens_at, rotation=facing)
    render(Path(out) / "help-still.webp", samples * 2, transparent_glass=True)


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reset()
    pieces = build_web_pieces()
    glb = out / "coalesce.glb"
    export_glb(pieces, glb)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.blend).resolve()))
    doc = L.layout_document(bpy.app.version_string)
    (out / "layout.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    self_check(glb)
    if args.stills:
        render_stills(out, args.samples)
    print("BUILD OK")


main()

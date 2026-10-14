"""scene.js: the Three.js reuse exports (part 1) and buildQuilt with its snapshot/project contract (part 2)."""
import pytest

from helpers import DEFAULTS_JS, TILE_GEOMETRY_JS, assert_tile_geometry

SCENE_JS = "const THREE = await import('three'); const S = await import('/public/js/scene.js');"


def run(js, body):
    return js(SCENE_JS + body)


# --- Part 1: the reuse exports. ---

def test_importing_scene_builds_nothing(js):
    r = js(r"""
        let calls = 0;
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (...args) { calls += 1; return original.apply(this, args); };
        await import('/public/js/scene.js');
        HTMLCanvasElement.prototype.getContext = original;
        return { calls, canvases: document.querySelectorAll('canvas').length };
    """)
    assert r == {"calls": 0, "canvases": 0}


def test_fabric_material_with_both_maps(js):
    r = run(js, r"""
        const { makeCanvas } = await import('/public/js/fabric.js');
        const map = new THREE.CanvasTexture(makeCanvas(8));
        const normalMap = new THREE.CanvasTexture(makeCanvas(8));
        const mat = S.fabricMaterial({ map, normalMap });
        return { physical: mat.isMeshPhysicalMaterial === true, roughness: mat.roughness, sheen: mat.sheen,
                 sheenRoughness: mat.sheenRoughness, sheenColor: mat.sheenColor.getHexString(),
                 mapSpace: mat.map.colorSpace, normalSpace: mat.normalMap.colorSpace,
                 sameMap: mat.map === map, sameNormal: mat.normalMap === normalMap };
    """)
    assert r == {"physical": True, "roughness": 0.9, "sheen": 1, "sheenRoughness": 0.8, "sheenColor": "fff1dc",
                 "mapSpace": "srgb", "normalSpace": "", "sameMap": True, "sameNormal": True}


def test_fabric_material_defaults_to_the_shared_weave_normal_map(js):
    r = run(js, r"""
        const a = S.fabricMaterial(); const b = S.fabricMaterial();
        const n = a.normalMap;
        return { shared: n === b.normalMap && n === S.weaveNormalMap(), space: n.colorSpace,
                 size: [n.image.width, n.image.height], wrap: [n.wrapS, n.wrapT].every((w) => w === THREE.RepeatWrapping) };
    """)
    assert r == {"shared": True, "space": "", "size": [512, 512], "wrap": True}


def test_create_renderer_settings(js):
    r = run(js, r"""
        const renderer = S.createRenderer(document.createElement('canvas'));
        const out = { tone: renderer.toneMapping === THREE.NeutralToneMapping,
                      space: renderer.outputColorSpace === THREE.SRGBColorSpace,
                      alpha: renderer.getContext().getContextAttributes().alpha, clearAlpha: renderer.getClearAlpha(),
                      maxRatio: S.MAX_PIXEL_RATIO };
        renderer.dispose();
        return out;
    """)
    assert r == {"tone": True, "space": True, "alpha": True, "clearAlpha": 0, "maxRatio": 1.75}


def test_add_lights_are_a_hemisphere_and_a_warm_upper_left_key(js):
    r = run(js, r"""
        const scene = new THREE.Scene();
        S.addLights(scene);
        const hemi = scene.children.filter((c) => c.isHemisphereLight);
        const keys = scene.children.filter((c) => c.isDirectionalLight);
        const key = keys[0];
        return { hemi: hemi.length, keys: keys.length, pos: key.position.toArray(), rgb: [key.color.r, key.color.b] };
    """)
    assert r["hemi"] == 1 and r["keys"] == 1
    x, y, z = r["pos"]
    assert x < 0 and y > 0 and z > 0
    assert r["rgb"][0] > r["rgb"][1]


CORNER = "{ minX: 1.0, maxX: 2.35, minY: -1.78, maxY: -0.5, margin: 0.1 }"


@pytest.mark.parametrize("aspect", [1.6, 1.0, 2.2])
@pytest.mark.parametrize("bounds", ["default", "corner"])
def test_fit_camera_frames_the_bounds(js, bounds, aspect):
    r = run(js, f"""
        const b = {'S.DEFAULT_BOUNDS' if bounds == 'default' else CORNER};
        const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
        S.fitCamera(camera, {aspect}, {'' if bounds == 'default' else 'b'});
        camera.updateMatrixWorld(true);
        const m = b.margin;
        const corners = [[b.minX - m, b.minY - m], [b.maxX + m, b.minY - m], [b.minX - m, b.maxY + m], [b.maxX + m, b.maxY + m]];
        return {{ ndc: corners.map(([x, y]) => new THREE.Vector3(x, y, 0).project(camera).toArray()),
                  aspect: camera.aspect, fov: camera.fov,
                  target: camera.userData.target.toArray(), centre: [(b.minX + b.maxX) / 2, (b.minY + b.maxY) / 2] }};
    """)
    assert len(r["ndc"]) == 4
    assert all(abs(x) <= 1 + 1e-9 and abs(y) <= 1 + 1e-9 for x, y, _ in r["ndc"]), r["ndc"]
    assert any(1 - abs(x) < 0.02 or 1 - abs(y) < 0.02 for x, y, _ in r["ndc"])  # tight, not just inside
    assert r["aspect"] == aspect and r["fov"] == 35
    assert all(abs(a - b) < 1e-9 for a, b in zip(r["target"], [*r["centre"], 0]))


# --- Part 2: buildQuilt, snapshot() and project(), with the shipped panels through cleanPanels. ---

# Defines slotsOf(n) (the first n default entries, padded with null to 12) and build(slots) (a quilt on an
# 800 x 500 canvas in the page, resized and rendered once).
BUILD_JS = SCENE_JS + DEFAULTS_JS + r"""
    const L = await import('/public/js/layout.js');
    const slotsOf = (n = 12) => { const s = DEFAULTS.slice(0, n); while (s.length < 12) s.push(null); return s; };
    const build = (slots = slotsOf()) => {
      const canvas = document.createElement('canvas');
      canvas.style.cssText = 'display:block;width:800px;height:500px';
      document.body.append(canvas);
      const quilt = S.buildQuilt(S.createRenderer(canvas), { slots });
      quilt.resize(800, 500, 1);
      quilt.render();
      return quilt;
    };
    const planned = (q) => q.blocks.filter((b) => b.userData.face === 'planned');
    const untilted = (q) => q.blocks.filter((b) => b.userData.face !== 'planned');
"""


def build(paint_js, body):
    return paint_js(BUILD_JS + body)


def test_snapshot_is_plain_json_with_the_contract_fields(paint_js):
    r = build(paint_js, r"""
        const snap = build().snapshot();
        const same = (a, b) => {
          if (a === null || typeof a !== 'object') return Object.is(a, b);
          if (b === null || Object.getPrototypeOf(a) !== Object.getPrototypeOf(b)) return false;
          const ka = Object.keys(a); const kb = Object.keys(b);
          return ka.length === kb.length && ka.every((k) => same(a[k], b[k]));
        };
        const numbers = [];
        const walk = (v) => { if (typeof v === 'number') numbers.push(v); else if (v && typeof v === 'object') Object.values(v).forEach(walk); };
        walk(snap);
        const keys = (o) => Object.keys(o).sort();
        return {
          roundTrip: same(JSON.parse(JSON.stringify(snap)), snap),
          top: keys(snap), block: keys(snap.blocks[0]), sashing: keys(snap.sashing), rod: keys(snap.rod),
          shadow: keys(snap.shadow), camera: keys(snap.camera),
          slots: snap.blocks.map((b) => b.slot),
          sizes: snap.blocks.map((b) => [b.positions.length, b.uvs.length, b.indices.length]),
          sashingSizes: [snap.sashing.positions.length / 3, snap.sashing.uvs.length / 2, snap.sashing.indices.length],
          pins: snap.pins, stitches: snap.stitches, finite: numbers.every(Number.isFinite), numbers: numbers.length,
        };
    """)
    assert r["roundTrip"] is True
    assert r["top"] == ["blocks", "camera", "pins", "rod", "sashing", "shadow", "stitches"]
    assert r["block"] == ["face", "id", "indices", "positions", "slot", "status", "uvs"]
    assert r["sashing"] == ["indices", "positions", "uvs"]
    assert r["rod"] == ["end", "radius", "start"]
    assert r["shadow"] == ["height", "position", "quaternion", "width"]
    assert r["camera"] == ["aspect", "fov", "position", "target", "up"]
    assert r["slots"] == list(range(12))
    assert r["sizes"] == [[5043, 3362, 9600]] * 12
    n, n_uv, n_index = r["sashingSizes"]
    assert n == n_uv and n > 0 and n_index > 0 and n_index % 3 == 0
    assert r["pins"] == [] and r["stitches"] == []
    assert r["finite"] is True and r["numbers"] > 12 * 5043


def test_block_positions_match_the_live_meshes(paint_js):
    """An independent path to the snapshot (position attribute + matrixWorld), and a layout oracle (w201)."""
    r = build(paint_js, r"""
        const q = build();
        const snap = q.snapshot();
        const v = new THREE.Vector3();
        let live = 0; let oracle = 0; let checked = 0;
        const influences = q.blocks.map((b) => b.morphTargetInfluences[0]);
        q.blocks.forEach((mesh, i) => {
          const pos = mesh.geometry.attributes.position;
          const s = snap.blocks[i].positions;
          for (let j = 0; j < pos.count; j += 1) {
            v.fromBufferAttribute(pos, j).applyMatrix4(mesh.matrixWorld);
            live = Math.max(live, Math.abs(v.x - s[3 * j]), Math.abs(v.y - s[3 * j + 1]), Math.abs(v.z - s[3 * j + 2]));
          }
          if (mesh.userData.face === 'planned') return;
          checked += 1;
          const [cx, cy] = L.slotCentre(i);
          for (let r = 0; r <= 40; r += 1) {
            for (let c = 0; c <= 40; c += 1) {
              const j = r * 41 + c;
              const lx = c / 40 - 0.5; const ly = 0.5 - r / 40;
              const want = [cx + lx, cy + ly, L.puffZ(lx + 0.5, ly + 0.5) + L.foldZ(cx + lx, cy + ly)];
              oracle = Math.max(oracle, ...want.map((w, d) => Math.abs(w - s[3 * j + d])));
            }
          }
        });
        return { influences, live, oracle, checked };
    """)
    assert r["influences"] == [0] * 12
    assert r["checked"] == 8
    assert r["live"] <= 1e-6 and r["oracle"] <= 1e-6, r


def test_sashing_meets_every_untilted_block_edge(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const snap = q.snapshot();
        const sp = snap.sashing.positions;
        let checked = 0; let missing = 0;
        q.blocks.forEach((mesh, i) => {
          if (mesh.userData.face === 'planned') return;
          const s = snap.blocks[i].positions;
          for (let r = 0; r <= 40; r += 1) {
            for (let c = 0; c <= 40; c += 1) {
              if (r !== 0 && r !== 40 && c !== 0 && c !== 40) continue;
              const j = 3 * (r * 41 + c);
              checked += 1;
              let hit = false;
              for (let k = 0; k < sp.length && !hit; k += 3) {
                hit = Math.abs(sp[k] - s[j]) <= 1e-6 && Math.abs(sp[k + 1] - s[j + 1]) <= 1e-6
                  && Math.abs(sp[k + 2] - s[j + 2]) <= 1e-6;
              }
              if (!hit) missing += 1;
            }
          }
        });
        return { checked, missing };
    """)
    assert r == {"checked": 1280, "missing": 0}


def test_planned_tilts_are_seeded_and_within_limit(paint_js):
    r = build(paint_js, r"""
        const a = build(); const b = build();
        return { faces: a.blocks.map((m) => m.userData.face), a: a.blocks.map((m) => m.rotation.z),
                 b: b.blocks.map((m) => m.rotation.z) };
    """)
    limit = 2.5 * 3.141592653589793 / 180
    assert r["a"] == r["b"]
    assert r["faces"].count("planned") == 4
    for face, rz in zip(r["faces"], r["a"]):
        if face == "planned":
            assert 0 < abs(rz) <= limit
        else:
            assert rz == 0


def test_tilted_blocks_sit_above_the_sashing(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const snap = q.snapshot();
        let low = 0; let vertices = 0;
        for (const mesh of planned(q)) {
          const s = snap.blocks[mesh.userData.slot].positions;
          for (let j = 0; j < s.length; j += 3) {
            vertices += 1;
            if (!(s[j + 2] > L.foldZ(s[j], s[j + 1]))) low += 1;
          }
        }
        const { positions: sp, indices: si } = snap.sashing;
        const cellsIn = (slot) => {
          const [cx, cy] = L.slotCentre(slot);
          let n = 0;
          for (let t = 0; t < si.length; t += 3) {
            const x = (sp[3 * si[t]] + sp[3 * si[t + 1]] + sp[3 * si[t + 2]]) / 3;
            const y = (sp[3 * si[t] + 1] + sp[3 * si[t + 1] + 1] + sp[3 * si[t + 2] + 1]) / 3;
            if (Math.abs(x - cx) < 0.5 && Math.abs(y - cy) < 0.5) n += 1;
          }
          return n;
        };
        return { low, vertices, planned: planned(q).map((m) => cellsIn(m.userData.slot)),
                 untilted: untilted(q).map((m) => cellsIn(m.userData.slot)) };
    """)
    assert r["vertices"] == 4 * 1681 and r["low"] == 0
    assert len(r["planned"]) == 4 and all(n > 0 for n in r["planned"])
    assert r["untilted"] == [0] * 8


def test_morph_target_zero_is_flat(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const v = new THREE.Vector3();
        let worst = 0;
        const counts = q.blocks.map((m) => [m.geometry.morphAttributes.position.length, m.geometry.morphAttributes.normal.length]);
        for (const mesh of q.blocks) {
          mesh.morphTargetInfluences[0] = 1;
          for (let j = 0; j < mesh.geometry.attributes.position.count; j += 1) {
            worst = Math.max(worst, Math.abs(mesh.getVertexPosition(j, v).z));
          }
          mesh.morphTargetInfluences[0] = 0;
        }
        return { counts, worst };
    """)
    assert r["counts"] == [[1, 1]] * 12
    assert r["worst"] <= 1e-9


def test_shadow_matches_the_live_plane(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const snap = q.snapshot();
        const p = new THREE.Vector3(); const quat = new THREE.Quaternion(); const scale = new THREE.Vector3();
        q.shadow.matrixWorld.decompose(p, quat, scale);
        const { width, height } = q.shadow.geometry.parameters;
        return { live: [p.toArray(), quat.toArray(), width * scale.x, height * scale.y],
                 snap: [snap.shadow.position, snap.shadow.quaternion, snap.shadow.width, snap.shadow.height],
                 shadowZ: L.LAYOUT.shadowZ, parentIsScene: q.shadow.parent === q.scene };
    """)
    (lp, lq, lw, lh), (sp, sq, sw, sh) = r["live"], r["snap"]
    assert all(abs(a - b) <= 1e-6 for a, b in zip(lp + lq, sp + sq))
    assert abs(lw - sw) <= 1e-9 and abs(lh - sh) <= 1e-9
    assert sp[2] == r["shadowZ"] and r["parentIsScene"] is True


def test_sashing_weave_matches_the_block_scale(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const block = q.blocks[0].material.normalMap; const sash = q.sashing.material.normalMap;
        return { different: block !== sash, block: block.repeat.toArray(), sash: sash.repeat.toArray(),
                 size: [L.LAYOUT.quiltW, L.LAYOUT.quiltH] };
    """)
    assert r["different"] is True
    (bx, by), (sx, sy), (w, h) = r["block"], r["sash"], r["size"]
    assert abs(sx - w * bx) <= 1e-9 and abs(sy - h * by) <= 1e-9


def test_sway_pivots_on_the_rod(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const before = q.snapshot();
        q.setAmbient({ sway: 0.05 });
        const after = q.snapshot();
        const corner = (s) => s.blocks[8].positions.slice(3 * 1640, 3 * 1641);
        q.setAmbient({ sway: 0, tiltX: 0, tiltY: 0 });
        q.scene.updateMatrixWorld(true);
        const identity = new THREE.Matrix4().elements;
        return { rod: [before.rod.start, before.rod.end, after.rod.start, after.rod.end],
                 corners: [corner(before), corner(after)],
                 identity: Math.max(...q.group.matrixWorld.elements.map((e, i) => Math.abs(e - identity[i]))) };
    """)
    s0, e0, s1, e1 = r["rod"]
    assert all(abs(a - b) <= 1e-9 for a, b in zip(s0 + e0, s1 + e1))
    c0, c1 = r["corners"]
    assert max(abs(a - b) for a, b in zip(c0, c1)) > 0.01
    assert r["identity"] <= 1e-12


def test_project_maps_the_camera_target_to_the_canvas_centre(paint_js):
    r = build(paint_js, r"""
        const q = build();
        const rect = q.renderer.domElement.getBoundingClientRect();
        return { at: q.project(q.camera.userData.target.toArray()),
                 centre: [rect.left + rect.width / 2, rect.top + rect.height / 2] };
    """)
    assert all(abs(a - b) <= 0.5 for a, b in zip(r["at"], r["centre"]))


def test_filler_slots_draw_filler_blocks(paint_js):
    r = build(paint_js, r"""
        const snap = build(slotsOf(10)).snapshot();
        return snap.blocks.map((b) => [b.slot, b.id, b.status, b.face]);
    """)
    assert r[10] == [10, None, None, "filler"] and r[11] == [11, None, None, "filler"]
    assert r[0] == [0, "manpower", "live", "sewn"]


# --- #8: the tile faces, the block poses, the fades and pick. ---

# tilePose(i) / quiltPose(q, i) as the director's contract reads them; tileOf(q, i) is block i's tile child.
POSE_JS = r"""
    const tilePose = (i) => ({ position: [...L.slotCentre(i, 'tiles'), 0], rotY: Math.PI, rotZ: 0, morph: 1 });
    const quiltPose = (q, i) => ({ position: q.blocks[i].position.toArray(), rotY: 0, rotZ: q.blocks[i].rotation.z,
                                   morph: 0 });
    const tileOf = (q, i) => q.blocks[i].children.find((c) => c.userData.part === 'tile') ?? null;
"""


def test_tile_planes_back_every_non_filler_block(paint_js):
    r = build(paint_js, POSE_JS + r"""
        const q = build(slotsOf(10));
        return q.blocks.map((b, i) => {
          const t = tileOf(q, i);
          return t && { slot: t.userData.slot, part: t.userData.part, parent: t.parent === b, rotY: t.rotation.y === Math.PI,
                        z: t.position.z, alphaTest: t.material.alphaTest, painted: !isUniform(t.material.map.image) };
        });
    """)
    for i, tile in enumerate(r[:10]):
        assert tile == {"slot": i, "part": "tile", "parent": True, "rotY": True, "z": tile["z"], "alphaTest": 0.5,
                        "painted": True}
        assert tile["z"] < 0
    assert r[10:] == [None, None]


def test_tile_pose_is_flat_flipped_and_square(paint_js):
    r = build(paint_js, POSE_JS + TILE_GEOMETRY_JS + r"""
        const q = build();
        q.blocks.forEach((_, i) => q.setBlockPose(i, tilePose(i)));
        return tileGeometry(q.snapshot(), (i) => L.slotCentre(i, 'tiles'));
    """)
    assert len(r) == 12
    assert_tile_geometry(r)


def test_set_fade_hides_and_restores(paint_js):
    r = build(paint_js, r"""
        const q = build(slotsOf(10));
        q.setFade(0);
        const gone = q.fades();
        const blocks = q.blocks.slice(0, 10).map((b) => b.visible);
        q.setFade(1);
        return { gone, blocks, back: q.fades() };
    """)
    for state, want in (("gone", {"opacity": 0, "visible": False}), ("back", {"opacity": 1, "visible": True})):
        f = r[state]
        assert [f["sashing"], f["rod"], f["shadow"]] == [want] * 3, (state, f)
        assert f["fillers"] == [{"slot": 10, **want}, {"slot": 11, **want}], (state, f)
    assert r["blocks"] == [True] * 10


def test_pick_names_what_is_under_the_pointer(paint_js):
    r = build(paint_js, POSE_JS + r"""
        const q = build();
        const at = (p) => { const [x, y] = q.project(p); return q.pick(x, y); };
        const snap = q.snapshot();
        const centre5 = snap.blocks[5].positions.slice(3 * 840, 3 * 841);
        const { quiltW } = L.LAYOUT;
        const quilt = [at(centre5), at([0, 0, L.foldZ(0, 0)]), at([-(quiltW / 2 + 0.3), 0, 0]),
                       at([0, L.LAYOUT.rod.y, 0])];
        q.blocks.forEach((_, i) => q.setBlockPose(i, tilePose(i)));
        q.setFade(0);
        const tiles = [at([...L.slotCentre(5, 'tiles'), 0]), at([0, 0, 0])];
        return { quilt, tiles };
    """)
    block, sashing, beside, rod = r["quilt"]
    assert (block["part"], block["slot"]) == ("block", 5)
    assert sashing["part"] == "sashing"
    assert beside["part"] == "none" and rod["part"] == "none"
    tile, gutter = r["tiles"]
    assert (tile["part"], tile["slot"]) == ("tile", 5)
    assert gutter["part"] == "none" and gutter["slot"] is None
    assert all(abs(c) <= 0.02 for c in gutter["point"]), gutter


def test_tile_planes_hide_in_the_quilt_pose(paint_js):
    r = build(paint_js, POSE_JS + r"""
        const q = build();
        const home = q.blocks.map((_, i) => quiltPose(q, i));
        const seen = () => q.blocks.map((_, i) => tileOf(q, i).visible);
        const built = seen();
        q.blocks.forEach((_, i) => q.setBlockPose(i, tilePose(i)));
        const tiled = seen();
        q.blocks.forEach((_, i) => q.setBlockPose(i, home[i]));
        return { built, tiled, back: seen() };
    """)
    assert r == {"built": [False] * 12, "tiled": [True] * 12, "back": [False] * 12}


# --- #9: refolding a block for a new slot, the re-cut sashing, and the slot-aware pick and snapshot. ---

# flatten(q, ...is) sets each block's morph influence to 1 (placeBlock's precondition); swap(q, a, b) refolds blocks a
# and b into each other's slots; quiltAt(q, i) is block i's quilt pose at its current slot; DRAGGED is the order a
# drag of slot 0 to slot 5 gives (moveItem(DEFAULT_IDS, 0, 5)), as entries.
PLACE_JS = POSE_JS + r"""
    const flatten = (q, ...is) => is.forEach((i) => { q.blocks[i].morphTargetInfluences[0] = 1; });
    const swap = (q, a, b) => { flatten(q, a, b); const sa = q.blocks[a].userData.slot; q.placeBlock(a, q.blocks[b].userData.slot); q.placeBlock(b, sa); };
    const quiltAt = (q, i) => ({ position: [...L.slotCentre(q.blocks[i].userData.slot), q.blocks[i].position.z], rotY: 0,
                                 rotZ: q.blocks[i].rotation.z, morph: 0 });
    const EXPECTED = ['hiring', 'training', 'awards', 'promotions', 'travel', 'manpower', 'feedback', 'actions',
                      'oversight', 'access', 'desks', 'suggest'];
    const DRAGGED = EXPECTED.map((id) => DEFAULTS.find((e) => e.id === id));
    const cellsIn = (snap, slot) => {
      const { positions: sp, indices: si } = snap.sashing;
      const [cx, cy] = L.slotCentre(slot);
      let n = 0;
      for (let t = 0; t < si.length; t += 3) {
        const x = (sp[3 * si[t]] + sp[3 * si[t + 1]] + sp[3 * si[t + 2]]) / 3;
        const y = (sp[3 * si[t] + 1] + sp[3 * si[t + 1] + 1] + sp[3 * si[t + 2] + 1]) / 3;
        if (Math.abs(x - cx) < 0.5 && Math.abs(y - cy) < 0.5) n += 1;
      }
      return n;
    };
    const worst = (a, b) => a.reduce((m, v, k) => Math.max(m, Math.abs(v - b[k])), 0);
"""


def test_place_block_refolds_for_the_new_slot(paint_js):
    r = build(paint_js, PLACE_JS + r"""
        const q = build();
        const before = q.blocks.map((_, i) => q.blockBase(i));
        flatten(q, 0, 4);
        q.placeBlock(0, 5);
        q.placeBlock(4, 3);
        const fresh = build(DRAGGED);
        const pairs = [[0, 5], [4, 3]].map(([i, k]) => {
          const a = q.blockBase(i); const b = fresh.blockBase(k);
          return { id: q.blocks[i].userData.id, freshId: fresh.blocks[k].userData.id, slot: a.slot,
                   positions: worst(a.positions, b.positions), normals: worst(a.normals, b.normals) };
        });
        const unmoved = [1, 2, 3, 5, 6, 7, 8, 9, 10, 11].every((i) => JSON.stringify(q.blockBase(i)) === JSON.stringify(before[i]));
        const m = q.blockBase(0);
        const [cx, cy] = L.slotCentre(5);
        let oracle = 0;
        for (let j = 0; j < 1681; j += 1) {
          const lx = (j % 41) / 40 - 0.5; const ly = 0.5 - Math.floor(j / 41) / 40;
          oracle = Math.max(oracle, Math.abs(m.positions[3 * j + 2] - (L.puffZ(lx + 0.5, ly + 0.5) + L.foldZ(cx + lx, cy + ly))));
        }
        const moved = worst(m.positions, before[0].positions);
        return { pairs, unmoved, oracle, moved, tileSlot: tileOf(q, 0).userData.slot, tilt: [m.tilt, q.blockBase(4).tilt] };
    """)
    assert [(p["id"], p["freshId"], p["slot"]) for p in r["pairs"]] == [("manpower", "manpower", 5),
                                                                        ("promotions", "promotions", 3)]
    for p in r["pairs"]:
        assert p["positions"] <= 1e-6 and p["normals"] <= 1e-6, p
    assert r["unmoved"] is True
    assert r["oracle"] <= 1e-6 and r["moved"] > 1e-3, r
    assert r["tileSlot"] == 5
    assert r["tilt"][0] == 0 and r["tilt"][1] != 0


def test_place_block_needs_a_flat_block(paint_js):
    r = build(paint_js, PLACE_JS + r"""
        const q = build();
        const before = q.blockBase(0);
        let message = null;
        try { q.placeBlock(0, 5); } catch (err) { message = err.message; }
        return { message, unchanged: JSON.stringify(q.blockBase(0)) === JSON.stringify(before) };
    """)
    assert r == {"message": "WEAVE: placeBlock needs a flat block (morph influence 1).", "unchanged": True}


def test_refold_is_invisible_while_flat(paint_js):
    """U1a: at influence 1 the base never reaches the screen. Block 0 faces the camera, flat, with its tile hidden
    (a tile pose is culled by FrontSide). Control: at influence 0.5 the same refold does change the picture."""
    r = build(paint_js, PLACE_JS + r"""
        const shot = (q, morph) => {
          q.setBlockPose(0, { position: q.blocks[0].position.toArray(), rotY: 0, rotZ: 0, morph });
          tileOf(q, 0).visible = false;
          q.render();
          return q.renderer.domElement.toDataURL();
        };
        const q = build();
        const flatBefore = shot(q, 1);
        q.placeBlock(0, 5);
        const flatAfter = shot(q, 1);
        const c = build();
        const halfBefore = shot(c, 0.5);
        shot(c, 1);
        c.placeBlock(0, 5);
        const halfAfter = shot(c, 0.5);
        return { flat: flatBefore === flatAfter, half: halfBefore === halfAfter };
    """)
    assert r["flat"] is True
    assert r["half"] is False  # the control: a half-flat block shows its refold


def test_pick_reports_the_current_slot(paint_js):
    """U1b: a refolded block is raycast at its new slot and fold, and its bounding sphere follows the fold."""
    r = build(paint_js, PLACE_JS + r"""
        const q = build();
        const at = (p) => { const [x, y] = q.project(p); return q.pick(x, y); };
        const sphere = q.blocks[0].geometry.boundingSphere.center.z;
        swap(q, 0, 5);
        q.blocks.forEach((b, i) => q.setBlockPose(i, tilePose(b.userData.slot)));
        q.setFade(0);
        const tile = at([...L.slotCentre(5, 'tiles'), 0]);
        q.setFade(1);
        q.blocks.forEach((_, i) => q.setBlockPose(i, quiltAt(q, i)));
        const snap = q.snapshot();
        const block = at(snap.blocks[5].positions.slice(3 * 840, 3 * 841));
        return { tile: [tile.part, tile.slot], block: [block.part, block.slot], id: snap.blocks[5].id,
                 sphere: Math.abs(q.blocks[0].geometry.boundingSphere.center.z - sphere) };
    """)
    assert r["tile"] == ["tile", 5]
    assert r["block"] == ["block", 5] and r["id"] == "manpower"
    assert r["sphere"] > 1e-4, r


def test_snapshot_lists_blocks_in_slot_order(paint_js):
    r = build(paint_js, PLACE_JS + r"""
        const q = build();
        swap(q, 0, 5);
        const snap = q.snapshot();
        return { slots: snap.blocks.map((b) => b.slot), ids: [snap.blocks[0].id, snap.blocks[5].id] };
    """)
    assert r["slots"] == list(range(12))
    assert r["ids"] == ["travel", "manpower"]


def test_reseam_follows_the_planned_slots(paint_js):
    r = build(paint_js, PLACE_JS + r"""
        const q = build();
        swap(q, 3, 4);
        q.blocks.forEach((_, i) => q.setBlockPose(i, quiltAt(q, i)));
        const stale = q.snapshot();
        q.reseam();
        const snap = q.snapshot();
        const sp = snap.sashing.positions;
        let checked = 0; let missing = 0;
        q.blocks.forEach((mesh) => {
          if (mesh.userData.face === 'planned') return;
          const s = snap.blocks[mesh.userData.slot].positions;
          for (let r = 0; r <= 40; r += 1) {
            for (let c = 0; c <= 40; c += 1) {
              if (r !== 0 && r !== 40 && c !== 0 && c !== 40) continue;
              const j = 3 * (r * 41 + c);
              checked += 1;
              let hit = false;
              for (let k = 0; k < sp.length && !hit; k += 3) {
                hit = Math.abs(sp[k] - s[j]) <= 1e-6 && Math.abs(sp[k + 1] - s[j + 1]) <= 1e-6
                  && Math.abs(sp[k + 2] - s[j + 2]) <= 1e-6;
              }
              if (!hit) missing += 1;
            }
          }
        });
        return { stale: cellsIn(stale, 3), planned: cellsIn(snap, 3), square: cellsIn(snap, 4),
                 untilted: q.blocks.filter((b) => b.userData.face !== 'planned').map((b) => cellsIn(snap, b.userData.slot)),
                 checked, missing, ids: [snap.blocks[3].id, snap.blocks[4].id] };
    """)
    assert r["stale"] == 0  # the control: before reseam() the old sashing still has awards' hole at slot 3
    assert r["planned"] > 0 and r["square"] == 0
    assert r["untilted"] == [0] * 8
    assert (r["checked"], r["missing"]) == (1280, 0)
    assert r["ids"] == ["promotions", "awards"]


def test_plane_point_matches_pick_none(paint_js):
    r = build(paint_js, PLACE_JS + r"""
        const q = build();
        const { quiltW, quiltH } = L.LAYOUT;
        return [[-(quiltW / 2 + 0.3), 0, 0], [quiltW / 2 + 0.3, 0.5, 0], [0.4, -(quiltH / 2 + 0.25), 0]].map((p) => {
          const [x, y] = q.project(p);
          const hit = q.pick(x, y);
          return { part: hit.part, err: worst(hit.point, q.planePoint(x, y)) };
        });
    """)
    assert [p["part"] for p in r] == ["none"] * 3
    assert all(p["err"] == 0 for p in r), r

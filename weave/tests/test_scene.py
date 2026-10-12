"""scene.js: the Three.js reuse exports (part 1) and buildQuilt with its snapshot/project contract (part 2)."""
import pytest

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

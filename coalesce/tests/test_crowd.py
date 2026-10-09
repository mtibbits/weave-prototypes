RENDER = """
    const { loadAssets, CrowdView, MagnifierView } = await import('/public/js/crowd.js');
    const { CrowdSim, MagnifierSim } = await import('/public/js/motion.js');
    const assets = await loadAssets('/public/assets/');
    const canvas = document.createElement('canvas');
    document.body.append(canvas);
    const view = new CrowdView(canvas, assets, { preserveDrawingBuffer: true });
    view.resize(700, 540, 1);
    const sim = new CrowdSim(assets.layout, { variant: VARIANT });
    let lens = null;
    if (VARIANT === 'help') {
      const aim = new MagnifierSim(sim, assets.layout.magnifier.restAim);
      aim.advance(0.016);
      lens = new MagnifierView(view, assets);
      view.sync(sim.tokens, assets.layout.tokenScale);
      lens.update(aim.aimPoint());
      lens.render();
    } else {
      view.sync(sim.tokens, assets.layout.tokenScale);
      view.render();
    }
    const gl = view.renderer.getContext();
    const pixels = new Uint8Array(4 * 700 * 540);
    gl.readPixels(0, 0, 700, 540, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let opaque = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) opaque += 1;
    return { count: view.mesh.count, people: assets.layout.people.length, opaque,
             lensParts: lens ? lens.group.children.length : 0, glError: gl.getError() };
"""


def render_frame(js, variant):
    return js(RENDER.replace("VARIANT", repr(variant)))


def test_home_view_draws_the_crowd(js):
    r = render_frame(js, "home")
    assert r["count"] == r["people"] + 3
    assert r["opaque"] > 700 * 540 * 0.05
    assert r["glError"] == 0


def test_help_view_draws_the_crowd_and_the_magnifier(js):
    r = render_frame(js, "help")
    assert r["count"] == r["people"]
    assert r["lensParts"] == 3
    assert r["opaque"] > 700 * 540 * 0.05
    assert r["glError"] == 0


def test_pointer_ray_meets_the_figure_plane(js):
    r = js("""
        const { loadAssets, CrowdView } = await import('/public/js/crowd.js');
        const assets = await loadAssets('/public/assets/');
        const view = new CrowdView(document.createElement('canvas'), assets);
        return { hit: view.pointerToFigure(0, 0), target: assets.layout.camera.target };
    """)
    x, y, z = r["hit"]
    assert abs(x - r["target"][0]) < 0.05
    assert r["target"][1] < y < r["target"][1] + 0.5
    assert abs(z - 1.0) < 1e-6


def test_missing_assets_reject(js):
    message = js("""
        const { loadAssets } = await import('/public/js/crowd.js');
        try { await loadAssets('/public/no-such-folder/'); return 'resolved'; }
        catch (err) { return String(err && err.message || err); }
    """)
    assert message != "resolved"

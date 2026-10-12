"""motion.js: the fixed-step springs (Coalesce's) and the ambient sway and tilt, all on one clock."""
MOTION_JS = "const m = await import('/public/js/motion.js');"


def run(js, body):
    return js(MOTION_JS + body)


def test_spring_brings_a_displaced_block_home(js):
    """Port of coalesce/tests/test_motion.py::test_spring_brings_a_displaced_person_home."""
    r = run(js, r"""
        const s = new m.SpringSet(12);
        for (let i = 0; i < 12; i += 1) { s.setTarget(i, [i, -i, 0.5]); s.p[i] = [i, -i, 0.5]; }
        s.p[4][0] += 1;
        for (let i = 0; i < 180; i += 1) s.advance(1 / 60);
        const far = (i) => Math.hypot(...s.p[i].map((v, d) => v - s.target[i][d]));
        return { moved: far(4), others: [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11].map((i) => [s.p[i], s.target[i]]) };
    """)
    assert r["moved"] < 0.01
    assert all(p == t for p, t in r["others"])


def test_advance_caps_large_time_steps(js):
    """Port of Coalesce's capped-step test: a 5 s hitch advances like one 0.05 s frame."""
    r = run(js, r"""
        const make = () => { const s = new m.SpringSet(2); s.p[1] = [1, 0, 0]; return s; };
        const a = make(); const b = make();
        const h = a.advance(5);
        b.advance(0.05);
        return { h, a: [a.p, a.v], b: [b.p, b.v], caps: [m.capDt(-1), m.capDt(NaN), m.capDt(Infinity), m.capDt(0.01)],
                 consts: [m.STEP, m.MAX_DT] };
    """)
    assert r["h"] == 0.05
    assert r["a"] == r["b"]
    assert r["caps"] == [0, 0, 0, 0.01]
    assert r["consts"] == [1 / 120, 0.05]


def test_snap_jumps_to_the_targets(js):
    r = run(js, r"""
        const s = new m.SpringSet(3);
        s.setTarget(2, [1, 2, 3]);
        s.advance(0.05);
        const moving = !s.settled(1e-6);
        s.snap();
        return { moving, p: s.p, v: s.v, settled: s.settled(1e-12) };
    """)
    assert r["moving"] is True
    assert r["p"] == [[0, 0, 0], [0, 0, 0], [1, 2, 3]]
    assert r["v"] == [[0, 0, 0]] * 3 and r["settled"] is True


def test_sway_is_a_pure_function_of_the_clock(js):
    r = run(js, r"""
        const { swayRad, swayPeriod } = m.AMBIENT;
        const ts = Array.from({ length: 200 }, (_, i) => (swayPeriod * i) / 200);
        return { twice: ts.map((t) => m.swayAngle(t) === m.swayAngle(t)), values: ts.map((t) => m.swayAngle(t)), swayRad };
    """)
    assert all(r["twice"])
    assert all(abs(v) <= r["swayRad"] for v in r["values"])
    assert len({round(v, 12) for v in r["values"]}) >= 2


def test_ambient_amplitudes_are_the_layout_ceilings(js):
    r = run(js, r"""
        const { LAYOUT } = await import('/public/js/layout.js');
        return [m.AMBIENT.swayRad, m.AMBIENT.tiltX, m.AMBIENT.tiltY, LAYOUT.ambientMax];
    """)
    sway, tilt_x, tilt_y, amp = r
    assert [sway, tilt_x, tilt_y] == [amp["sway"], amp["tiltX"], amp["tiltY"]]


def test_follow_tilt_moves_toward_its_target(js):
    r = run(js, r"""
        const tilt = { x: 0, y: 0 };
        const half = m.followTilt(tilt, { x: 1, y: -1 }, 0.5 / m.AMBIENT.follow);
        const whole = m.followTilt(tilt, { x: 1, y: -1 }, 10);
        return { half, whole, tilt };
    """)
    assert r["half"] == {"x": 0.5, "y": -0.5}
    assert r["whole"] == {"x": 1, "y": -1} and r["tilt"] == {"x": 0, "y": 0}


def test_springs_settle_on_raf_time_with_date_frozen(make_page, base_url):
    """The one-clock AC's js leg (U3): Date is frozen, rAF timestamps still advance the springs."""
    page = make_page()
    page.clock.set_fixed_time("2026-10-09T09:00:00")
    page.goto(f"{base_url}/tests/blank.html")
    r = page.evaluate("async () => { " + MOTION_JS + r"""
        const before = Date.now();
        const s = new m.SpringSet(1);
        s.p[0] = [1, 0, 0];
        let elapsed = 0; let frames = 0;
        await new Promise((resolve) => {
          let last = 0;
          const tick = (now) => {
            if (last) { const dt = (now - last) / 1000; elapsed += dt; s.advance(dt); frames += 1; }
            last = now;
            if (elapsed < 3) requestAnimationFrame(tick); else resolve();
          };
          requestAnimationFrame(tick);
        });
        return { far: Math.hypot(...s.p[0]), frames, before, after: Date.now(),
                 fixed: new Date('2026-10-09T09:00:00').getTime() };
    }""")
    assert r["frames"] > 30
    assert r["far"] < 0.01
    assert r["before"] == r["after"] == r["fixed"]

import json

LAYOUT = {
    "people": [[x * 0.5 - 1.0, y * 0.5, 1.0] for y in range(5) for x in range(5)],
    "accent": [1 if i % 10 == 0 else 0 for i in range(25)],
    "figureCenter": [0.0, 1.0, 0.0],
}
PRELUDE = (
    "const m = await import('/public/js/motion.js');"
    f"const layout = {json.dumps(LAYOUT)};"
    "const settle = (sim, seconds, mag) => { for (let i = 0; i < Math.round(seconds * 60); i++)"
    " { sim.advance(1 / 60); if (mag) mag.advance(1 / 60); } };"
    "const far = (t) => Math.hypot(t.p[0] - t.home[0], t.p[1] - t.home[1], t.p[2] - t.home[2]);"
)


def run(js, body):
    return js(PRELUDE + body)


def test_hex_to_linear_matches_srgb(js):
    white, black, teal = run(js, "return [m.hexToLinear('#FFFFFF'), m.hexToLinear('#000000'), m.COLORS.teal];")
    assert white == [1, 1, 1] and black == [0, 0, 0]
    assert all(abs(a - b) < 5e-4 for a, b in zip(teal, [0.0123, 0.1119, 0.1046]))


def test_path_point_hits_endpoints_and_bulges(js):
    start, middle, end, later = run(js, """
        const path = { from: [0, 0, 0], to: [2, 0, 0], t0: 1, dur: 2, ease: 'inout', arc: [0, 1, 0] };
        const out = [0, 0, 0];
        const at = (t) => { m.pathPoint(path, t, out); return out.slice(); };
        return [at(0), at(2), at(3), at(9)];
    """)
    assert start == [0, 0, 0]
    assert all(abs(a - b) < 1e-9 for a, b in zip(middle, [1, 1, 0]))
    assert all(abs(a - b) < 1e-9 for a, b in zip(end, [2, 0, 0])) and later == end


def test_hover_offset_pushes_nearby_people_only(js):
    r = run(js, """
        const out = [0, 0, 0];
        return {
          near: m.hoverOffset([0.3, 0, 0], [0, 0, 0], 1, out).slice(),
          farAway: m.hoverOffset([2, 0, 0], [0, 0, 0], 1, out).slice(),
          off: m.hoverOffset([0.3, 0, 0], [0, 0, 0], 0, out).slice(),
        };
    """)
    assert r["near"][0] > 0.2 and abs(r["near"][1]) < 1e-9 and r["near"][2] > 0.2
    assert r["farAway"] == [0, 0, 0] and r["off"] == [0, 0, 0]


def test_spring_brings_a_displaced_person_home(js):
    assert run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        const t = sim.tokens[12]; t.p[0] += 1;
        settle(sim, 3);
        return far(t);
    """) < 0.01


def test_intro_hides_everyone_then_assembles_the_figure(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        sim.intro();
        const before = sim.tokens.filter((t) => t.home).map((t) => [t.mode, t.s]);
        settle(sim, 6);
        const people = sim.tokens.filter((t) => t.home);
        return { before, modes: [...new Set(people.map((t) => t.mode))],
                 minScale: Math.min(...people.map((t) => t.s)), worst: Math.max(...people.map(far)) };
    """)
    assert all(mode == "intro" and s == 0 for mode, s in r["before"])
    assert r["modes"] == ["home"] and r["minScale"] > 0.99 and r["worst"] < 0.02


def test_turnover_swaps_one_person_and_keeps_the_count(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false; sim.clock = 10;
        const ok = sim.turnover();
        const leaver = sim.tokens.find((t) => t.mode === 'leave');
        const arriver = sim.tokens.find((t) => t.mode === 'arrive');
        const slot = arriver.path.to.slice();
        settle(sim, 14);
        return {
          ok, leaverMode: leaver.mode, leaverScale: leaver.s,
          arriverMode: arriver.mode, arriverHome: arriver.home, slot,
          colorGap: Math.max(...arriver.col.map((c, i) => Math.abs(c - m.COLORS.teal[i]))),
          atHome: sim.tokens.filter((t) => t.mode === 'home').length,
        };
    """)
    assert r["ok"] is True
    assert r["leaverMode"] == "spare" and r["leaverScale"] < 0.01
    assert r["arriverMode"] == "home" and r["arriverHome"] == r["slot"]
    assert r["colorGap"] < 0.01 and r["atHome"] == 25


def test_burst_scatters_everyone_and_the_figure_reforms(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        sim.burst([0, 1, 0]);
        const bursting = sim.tokens.filter((t) => t.mode === 'burst').length;
        settle(sim, 0.7);
        const spread = Math.max(...sim.tokens.filter((t) => t.home).map(far));
        settle(sim, 5);
        const people = sim.tokens.filter((t) => t.home);
        return { bursting, spread, modes: [...new Set(people.map((t) => t.mode))], worst: Math.max(...people.map(far)) };
    """)
    assert r["bursting"] == 25 and r["spread"] > 1.0
    assert r["modes"] == ["home"] and r["worst"] < 0.02


def test_help_variant_has_no_accents_spares_or_turnovers(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const allTeal = sim.tokens.every((t) => t.col.every((c, i) => c === m.COLORS.teal[i]));
        settle(sim, 10);
        return { count: sim.tokens.length, allTeal, turnovers: sim.turnovers, hover: sim.hover.enabled,
                 modes: [...new Set(sim.tokens.map((t) => t.mode))] };
    """)
    assert r == {"count": 25, "allTeal": True, "turnovers": False, "hover": False, "modes": ["home"]}


def test_advance_caps_large_time_steps(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout);
        sim.intro();
        sim.advance(5);
        return { clock: sim.clock, modes: [...new Set(sim.tokens.filter((t) => t.home).map((t) => t.mode))] };
    """)
    assert abs(r["clock"] - 0.05) < 1e-9 and r["modes"] == ["intro"]


def test_home_pointer_parts_nearby_people_then_they_return(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        sim.setPointer([0, 1, 1], true);
        settle(sim, 1);
        const near = far(sim.tokens[13]);
        const corner = far(sim.tokens[0]);
        sim.setPointer(null, false);
        settle(sim, 3);
        return { near, corner, worst: Math.max(...sim.tokens.filter((t) => t.home).map(far)) };
    """)
    assert r["near"] > 0.3 and r["corner"] < 0.05 and r["worst"] < 0.02


def test_magnifier_follows_the_pointer_and_highlights_one_person(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const mag = new m.MagnifierSim(sim, [0, 1]);
        sim.setPointer([0.5, 1.5, 1], true);
        settle(sim, 1, mag);
        const first = { pos: mag.pos.slice(), focus: sim.focusIndex, expected: sim.nearest(mag.pos[0], mag.pos[1]) };
        sim.setPointer([-1, 0.2, 1], true);
        settle(sim, 1, mag);
        return { first, second: sim.focusIndex,
                 terra: sim.tokens.filter((t) => t.colT[0] > t.colT[1]).length,
                 previous: sim.tokens[first.focus].colT };
    """)
    assert abs(r["first"]["pos"][0] - 0.5) < 0.02 and abs(r["first"]["pos"][1] - 1.5) < 0.02
    assert r["first"]["focus"] == r["first"]["expected"] >= 0
    assert r["second"] != r["first"]["focus"] and r["terra"] == 1
    assert r["previous"][0] < r["previous"][1]


def test_magnifier_stays_high_enough_to_keep_its_handle_in_frame(js):
    lowest = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const mag = new m.MagnifierSim(sim, [0, 1]);
        sim.setPointer([0, -5, 1], true);
        settle(sim, 2, mag);
        return mag.pos[1];
    """)
    assert lowest >= 1.0 - 1e-6  # lowest person stands at y = 0; the lens may not aim below y = 1.0


def test_magnifier_drifts_between_people_when_nobody_points(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const mag = new m.MagnifierSim(sim, [3, 3]);
        settle(sim, 8, mag);
        return { moved: Math.hypot(mag.pos[0] - 3, mag.pos[1] - 3), focus: sim.focusIndex };
    """)
    assert r["moved"] > 0.5 and r["focus"] >= 0

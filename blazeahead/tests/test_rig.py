def rig(js, body):
    return js("const R = await import('/public/js/rig.js');" + body)


def test_walk_endpoints_match_views(js):
    r = rig(js, """const w = new R.Walk([[0,1,0],[3,1,4],[6,1,8]]);
      const a = R.walkPose(w, 0, 8, [0,1,5], [6,1,13]), b = R.walkPose(w, 1, 8, [0,1,5], [6,1,13]);
      return [w.pointAt(0), w.pointAt(1), a.position, b.position, a.target, b.target];""")
    assert r == [[0, 1, 0], [6, 1, 8], [0, 1, 0], [6, 1, 8], [0, 1, 5], [6, 1, 13]]


def test_walk_is_continuous_and_monotonic_along_a_straight_line(js):
    r = rig(js, """const w = new R.Walk([[0,0,0],[0,0,-10],[0,0,-20]]);
      const zs = []; for (let i = 0; i <= 20; i++) zs.push(w.pointAt(i / 20)[2]); return [zs, w.length];""")
    zs, length = r
    assert abs(length - 20) < 0.5
    assert all(b < a + 1e-9 for a, b in zip(zs, zs[1:]))
    assert max(abs(b - a) for a, b in zip(zs, zs[1:])) < 1.6


def test_a_walk_between_stops_is_a_stroll_not_a_run(js):
    # the legs between stops are about 27 m: roughly nine and a half seconds each, clamped for very short or long walks
    r = rig(js, "return [R.walkDuration(3), R.walkDuration(27.3), R.walkDuration(90)];")
    assert r[0] == 4 and 9 <= r[1] <= 10 and r[2] == 12


# The camera's heading (yaw) through a walk sampled at 60 fps, and the fastest it turns, in degrees per second.
TURN_RATES = """
  const yawOf = (p) => Math.atan2(p.target[0] - p.position[0], p.target[2] - p.position[2]) * 180 / Math.PI;
  const turnRates = (walk, dur, from, to) => {
    const n = Math.round(dur * 60), out = [];
    let prev = yawOf(R.walkPose(walk, 0, dur, from, to));
    for (let i = 1; i <= n; i++) {
      const y = yawOf(R.walkPose(walk, i / n, dur, from, to));
      out.push(Math.abs(((y - prev + 540) % 360) - 180) * 60);
      prev = y;
    }
    return out;
  };
"""


def test_the_camera_turns_slowly_between_a_stop_and_the_path(js):
    # the stops face sideways, a right angle from the path: the old walk swung round at over 300 deg/s on arrival
    r = rig(js, TURN_RATES + """
      const w = new R.Walk([[0,1,0],[0,1,-9],[0,1,-18],[0,1,-27]]);
      const dur = R.walkDuration(w.length);
      const rates = turnRates(w, dur, [-6,1,0], [-6,1,-27]);
      const mid = R.walkPose(w, 0.5, dur, [-6,1,0], [-6,1,-27]);
      return [Math.max(...rates), rates.slice(0, 15).every((d) => d < 10), mid.target[0] - mid.position[0]];""")
    peak, gentle_start, mid_sideways = r
    assert peak < 35, peak
    assert gentle_start              # the turn eases in rather than snapping round
    assert abs(mid_sideways) < 0.01  # mid-walk the camera looks straight down the path


def test_no_leg_of_the_tour_whips_the_camera_round(js):
    # the old walk peaked at 140-340 deg/s. Walking back to the trailhead is a near U-turn (about 165 deg in under
    # half the walk), so it alone is allowed to turn a little faster.
    r = js("const R = await import('/public/js/rig.js'); const S = await import('/public/js/stage-live.js');"
           + TURN_RATES + """
      const layout = await (await fetch('/public/assets/world.json')).json();
      const out = [];
      for (let a = -1; a < 3; a++) {
        for (const [from, to] of [[a, a + 1], [a + 1, a]]) {
          const plan = S.walkPlan(layout, from, to);
          const w = new R.Walk(plan.points);
          out.push([from, to, Math.max(...turnRates(w, R.walkDuration(w.length), plan.fromTarget, plan.toTarget))]);
        }
      }
      return out;""")
    assert all(peak < (60 if to == -1 else 46) for _, to, peak in r), r


def test_ease_in_out(js):
    r = rig(js, "return [R.easeInOut(0), R.easeInOut(0.5), R.easeInOut(1), R.easeInOut(0.25) < 0.25, R.easeInOut(-1), R.easeInOut(2)];")
    assert r == [0, 0.5, 1, True, 0, 1]


def test_the_camera_glides_rather_than_lunging(js):
    # speed relative to the walk's average: it eases in and out, and never surges past 1.5x mid-walk
    slopes = rig(js, """const n = 400, out = [];
      for (let i = 0; i < n; i++) out.push((R.easeInOut((i + 1) / n) - R.easeInOut(i / n)) * n);
      return out;""")
    assert max(slopes) <= 1.5, max(slopes)
    assert slopes[0] < 0.05 and slopes[-1] < 0.05
    assert all(s >= 0 for s in slopes)


def test_fixed_horizontal_fov_gives_a_vertical_fov_for_any_window(js):
    r = rig(js, """return [Math.round(R.fitVerticalFov(62, 16/9) * 10) / 10,
      R.fitVerticalFov(62, 21/9) < R.fitVerticalFov(62, 4/3), Math.round(R.fitVerticalFov(90, 1) * 10) / 10];""")
    assert r == [37.3, True, 90.0]

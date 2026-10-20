"""#16's sew-in: the pure schedule (motion.js), the scene's sew-in calls (scene.js), and the page's sequence and skips
(main.js, whatsnew.js). Expected values are literals, never imported (PUFF and GLOW's peak legs excepted, as noted)."""
import pytest

# --- The pure schedule (motion.js). ---

SCHEDULE_JS = "const M = await import('/public/js/motion.js');"

class TestSchedule:
    def test_two_blocks_keep_the_nominal_steps(self, js):
        r = js(SCHEDULE_JS + "return M.sewSchedule(2);")
        assert r["scale"] == 1
        assert abs(r["total"] - 3.15) <= 1e-9
        assert len(r["blocks"]) == 2
        want = {"start": 0, "pins": [0, 0.3], "square": [0.3, 0.7], "puff": [0.7, 0.95], "needle": [0.95, 2.15],
                "glow": [2.15, 2.55]}
        for k, block in enumerate(r["blocks"]):
            shift = 0.6 * k
            assert abs(block["start"] - (want["start"] + shift)) <= 1e-9, (k, block)
            for name in ("pins", "square", "puff", "needle", "glow"):
                assert len(block[name]) == 2, (k, name, block)
                for got, nominal in zip(block[name], want[name]):
                    assert abs(got - (nominal + shift)) <= 1e-9, (k, name, block)

    @pytest.mark.parametrize("n", range(1, 13))
    def test_schedule_ends_within_5_s(self, js, n):
        r = js(SCHEDULE_JS + f"return M.sewSchedule({n});")
        steps = {"pins": 0.3, "square": 0.4, "puff": 0.25, "needle": 1.2, "glow": 0.4}
        raw = 0.6 * (n - 1) + 2.55
        assert r["total"] <= 5 + 1e-9, r
        if n <= 5:
            assert r["scale"] == 1
            assert abs(r["total"] - raw) <= 1e-9
        else:
            assert abs(r["total"] - 5) <= 1e-9
            assert abs(r["scale"] - 5 / raw) <= 1e-12
        scale = r["scale"]
        assert len(r["blocks"]) == n
        for k, block in enumerate(r["blocks"]):
            assert abs(block["start"] - 0.6 * scale * k) <= 1e-9, (k, block)
            at = block["start"]
            for name in ("pins", "square", "puff", "needle", "glow"):
                t0, t1 = block[name]
                assert abs(t0 - at) <= 1e-9 and abs((t1 - t0) - steps[name] * scale) <= 1e-9, (k, name, block)
                at = t1
        assert abs(r["blocks"][-1]["glow"][1] - r["total"]) <= 1e-9
        # At most two needle windows overlap at any time: the third's start is past the first's end.
        needles = [b["needle"] for b in r["blocks"]]
        for k in range(len(needles) - 2):
            assert needles[k + 2][0] >= needles[k][1] - 1e-9, (k, needles)

    def test_no_blocks_is_an_empty_schedule(self, js):
        assert js(SCHEDULE_JS + "return M.sewSchedule(0);") == {"scale": 1, "total": 0, "blocks": []}

    @pytest.mark.parametrize("count", ["-1", "1.5", "'2'", "true", "NaN", "null", "[2]", "2n"])
    def test_bad_counts_throw(self, js, count):
        r = js(SCHEDULE_JS + f"""
            try {{ M.sewSchedule({count}); return null; }}
            catch (err) {{ return [err.constructor.name, err.message]; }}
        """)
        assert r == ["RangeError", "WEAVE: sewSchedule needs a whole number of blocks."]

    def test_schedule_is_pure(self, js):
        """Behavioural (seed Issue-565): every clock and timer throws around the calls, as test_director_reads_no_clock
        does; the same count gives the same schedule."""
        r = js(SCHEDULE_JS + r"""
            const names = [[Date, 'now'], [performance, 'now'], [window, 'setTimeout'], [window, 'requestAnimationFrame']];
            const saved = names.map(([o, k]) => o[k]);
            const SavedDate = window.Date;
            const boom = () => { throw new Error('sewSchedule read a clock'); };
            const out = [];
            try {
              names.forEach(([o, k]) => { o[k] = boom; });
              window.Date = function () { throw new Error('sewSchedule built a Date'); };
              for (let n = 1; n <= 12; n += 1) out.push(JSON.stringify(M.sewSchedule(n)));
              out.push(JSON.stringify(M.sewSchedule(7)));
            } finally {
              window.Date = SavedDate;
              names.forEach(([o, k], i) => { o[k] = saved[i]; });
            }
            return out;
        """)
        assert len(r) == 13
        assert r[6] == r[12]


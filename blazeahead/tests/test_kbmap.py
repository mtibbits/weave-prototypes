import pytest


def kb(js, body):
    return js("""const K = await import('/public/js/kbmap.js');
      const C = await import('/public/js/content.js');
      await K.loadMapFonts(document);
      const measure = K.canvasMeasure(document);
      const draft = () => structuredClone(C.DEFAULT_TOUR.stops[2].map);
      const names = ['Build caches', 'Secrets', 'Code review', 'Design docs', 'Service catalog', 'Runbooks',
                     'Mirrors', 'On-call guide'];
      let k = 0;
      const nm = () => names[k++ % names.length];
      const stop = (name, next = []) => ({ name, url: '', next: next.map((n) => ({ name: n, url: '' })) });
      const tree = (trails, dests, spur) => ({ centre: 'blazeAhead', trails: Array.from({ length: trails }, (_, i) => ({
        name: `Trail number ${i + 1}`,
        destinations: Array.from({ length: dests }, (_, j) => (spur && j === 1 ? stop(nm(), [nm()]) : stop(nm()))) })) });
      // no box off the board's margin, no two boxes touching (labels, pills, dots), and the type scale reached
      const clean = (laid) => {
        const b = laid.boxes; const M = K.BOARD.margin; let hits = 0;
        const out = b.filter((x) => x[0] < M || x[1] < M || x[2] > K.BOARD.w - M || x[3] > K.BOARD.h - M).length;
        for (let i = 0; i < b.length; i++) for (let j = i + 1; j < b.length; j++)
          if (b[i][0] < b[j][2] && b[j][0] < b[i][2] && b[i][1] < b[j][3] && b[j][1] < b[i][3]) hits++;
        return [out, hits, laid.crowded, Math.round(laid.scale * 1000) / 1000];
      };
      """ + body)


def test_the_draft_map_fits_at_full_size(js):
    out, hits, crowded, scale = kb(js, "return clean(K.layoutMap(draft(), measure));")
    assert (out, hits, crowded) == (0, 0, False)
    assert scale >= 0.9


@pytest.mark.parametrize("build, floor", [
    ("k = 0; return clean(K.layoutMap(tree(5, 3, true), measure));", 0.85),       # 20 stops, a spur on every trail
    ("k = 3; return clean(K.layoutMap(tree(5, 5, false), measure));", 0.6),       # 25 stops, five on every trail
    ("const m = draft(); m.trails = m.trails.slice(0, 4); return clean(K.layoutMap(m, measure));", 0.6),
    ("return clean(K.layoutMap({ centre: 'x', trails: [{ name: 'Only', destinations: [stop('One')] }] }, measure));", 0.9),
])
def test_fuller_and_smaller_maps_still_fit(js, build, floor):
    out, hits, crowded, scale = kb(js, build)
    assert (out, hits, crowded) == (0, 0, False)
    assert scale >= floor


def test_long_trail_names_still_lay_out_clean(js):
    lengths, (out, hits, crowded, scale) = kb(js, """const m = draft();
      const long = ['Getting connected to the network', 'Agentic workflow and assistants',
                    'Language specific build tools', 'Security and access rules', 'Corporate knowledge and policy'];
      m.trails.forEach((t, i) => { t.name = long[i]; });
      return [long.map((n) => n.length), clean(K.layoutMap(m, measure))];""")
    assert min(lengths) == 25 and max(lengths) == 32
    assert (out, hits, crowded) == (0, 0, False)
    assert scale >= 0.6


def test_a_very_long_trail_name_is_cut_and_its_pill_stays_on_the_board(js):
    texts, pill, board = kb(js, """const m = draft();
      m.trails[0].name = 'Getting connected to the corporate network, safely';
      const laid = K.layoutMap(m, measure);
      const p = K.svgPainter(document); K.drawMap(p, laid);
      const t = laid.trails[0];
      return [[...p.svg.querySelectorAll('text')].map((x) => x.textContent).filter((s) => s.startsWith('Getting')),
              [t.x - t.w / 2, t.y - t.h / 2, t.x + t.w / 2, t.y + t.h / 2], K.BOARD];""")
    assert texts == ["Getting connected to the corpor…"] and len(texts[0]) == 32
    m = board["margin"]
    assert pill[0] >= m and pill[1] >= m and pill[2] <= board["w"] - m and pill[3] <= board["h"] - m, pill


def test_lighting_a_trail_fades_the_others(js):
    lines = kb(js, """const laid = K.layoutMap(draft(), measure);
      const calls = [];
      const rec = new Proxy({}, { get: (_, kind) => (...a) => { if (kind === 'link') a[2](); else calls.push([kind, a[a.length - 1]]); } });
      K.drawMap(rec, laid, { focus: 2 });
      return calls.filter(([kind]) => kind === 'line').map(([, o]) => [o.color, o.alpha, Boolean(o.glow)]);""")
    assert lines
    for color, alpha, glow in lines:
        if color == "#3E7D4C":
            assert alpha == 1 and glow
        else:
            assert alpha == 0.26 and not glow


def test_the_svg_map_links_only_when_asked_and_keeps_names_as_text(js):
    r = kb(js, """const m = draft();
      m.trails[0].destinations[0] = { name: '<b>R&D</b>', url: 'https://x.example.com/', next: [] };
      const laid = K.layoutMap(m, measure);
      const plain = K.svgPainter(document); K.drawMap(plain, laid);
      const linked = K.svgPainter(document); K.drawMap(linked, laid, { links: true });
      const a = linked.svg.querySelector('a');
      return [plain.svg.querySelectorAll('a').length, linked.svg.querySelectorAll('a').length, a.getAttribute('href'),
              a.getAttribute('target'), a.getAttribute('rel'), linked.svg.querySelectorAll('b').length,
              [...linked.svg.querySelectorAll('text')].some((t) => t.textContent === '<b>R&D</b>'),
              plain.svg.getAttribute('viewBox'), plain.svg.querySelectorAll('circle').length];""")
    assert r == [0, 1, "https://x.example.com/", "_blank", "noopener noreferrer", 0, True, "0 0 1380 880", 22]


def test_a_cut_name_shows_in_full_as_a_tooltip_on_the_unfolded_map(js):
    names, titles, label = kb(js, """const m = draft();
      m.trails[0].destinations[0].name = 'Onboarding checklist for new contractors';
      m.trails[1].destinations[0] = { name: 'Certificates and trust stores for Windows', url: 'https://x.example.com/',
                                      next: [] };
      const p = K.svgPainter(document); K.drawMap(p, K.layoutMap(m, measure), { links: true });
      return [[m.trails[0].destinations[0].name, m.trails[1].destinations[0].name],
              [...p.svg.querySelectorAll('title')].map((t) => t.textContent),
              p.svg.querySelector('a').getAttribute('aria-label')];""")
    assert [len(n) for n in names] == [40, 41]
    assert sorted(titles) == sorted(names)          # the cut names only, linked and not
    assert label == names[1]


def test_the_canvas_painter_draws_paper_and_pills(js):
    paper, pill = kb(js, """const laid = K.layoutMap(draft(), measure);
      const c = document.createElement('canvas'); c.width = 1380; c.height = 880;
      const g = c.getContext('2d');
      K.drawMap(K.canvasPainter(g, 1), laid);
      const px = (x, y) => [...g.getImageData(Math.round(x), Math.round(y), 1, 1).data].slice(0, 3);
      return [px(5, 5), px(laid.centre.x - laid.centre.w / 2 + 12, laid.centre.y)];""")
    assert paper == [0xDC, 0xCD, 0xA6]
    assert pill == [0xE8, 0x8E, 0x1F]


def test_quad_matrix_lays_the_board_on_its_four_corners(js):
    got = kb(js, """const quad = [[512, 210], [890, 222], [884, 470], [505, 462]];
      const m = new DOMMatrix(K.quadMatrix3d(1380, 880, quad));
      const at = (x, y) => { const p = m.transformPoint(new DOMPoint(x, y, 0, 1)); return [p.x / p.w, p.y / p.w]; };
      return [at(0, 0), at(1380, 0), at(1380, 880), at(0, 880)];""")
    want = [[512, 210], [890, 222], [884, 470], [505, 462]]
    for (gx, gy), (wx, wy) in zip(got, want):
        assert abs(gx - wx) < 1e-6 and abs(gy - wy) < 1e-6, got


def test_long_names_are_cut_on_the_map(js):
    r = kb(js, "return [K.shortName('A'.repeat(40)), K.shortName('Short')];")
    assert len(r[0]) == 32 and r[0].endswith("…") and r[1] == "Short"

import json


def content(js, body):
    return js("const C = await import('/public/js/content.js');" + body)


def test_defaults_cover_four_stops_the_signs_and_help(js):
    r = content(js, """const t = C.normalizeTour(undefined);
      return [t.stops.map((s) => [s.id, s.sign]), t.trailheadSign, t.endSign, t.help, t.rocks.length,
              C.pageCount(t.stops[2]), t.stops.every((s) => s.title && s.paragraphs.length > 0)];""")
    stops, trail, end, help_, rocks, cards, complete = r
    assert stops == [["continuity", "Continuity"], ["scaffolding", "Scaffolding"], ["knowledge", "Knowledge"],
                     ["in-flight", "In Flight"]]
    assert (trail, end) == ("Trailhead", "Download")
    assert help_ == {"left": "Issues", "right": "Docs", "ahead": "Tour"}
    assert rocks >= 5 and cards == 6 and complete is True


def test_normalize_tour_survives_hand_edits(js):
    r = content(js, """const t2 = C.normalizeTour({stops: [{sign: ''}, {title: '<b>x</b>'}, {}]});
      const t3 = C.normalizeTour({stops: Array.from({length: 6}, () => ({}))});
      const t4 = C.normalizeTour({stops: 'nonsense', help: 7, rocks: [1, null]});
      return [t2.stops.length, t2.stops[0].sign, t3.stops.length, t2.stops.map((s) => s.id),
              t4.stops.length, t4.help.left, t4.rocks.every((x) => typeof x === 'string')];""")
    assert r == [3, "Continuity", 4, ["continuity", "scaffolding", "knowledge"], 4, "Issues", True]


def test_owner_copy_wins_over_defaults(js):
    raw = {"stops": [{"sign": "Keep going", "title": "Our proxy", "paragraphs": ["One.", "Two."],
                      "points": ["A", "B"]}]}
    r = content(js, f"const t = C.normalizeTour({json.dumps(raw)}); return t.stops[0];")
    assert r["sign"] == "Keep going" and r["title"] == "Our proxy"
    assert r["paragraphs"] == ["One.", "Two."] and r["points"] == ["A", "B"]


def test_card_html_escapes_copy_and_pages_through_the_trails(js):
    r = content(js, """const s = {id: 'knowledge', title: '<b>x</b>', paragraphs: ['a & b'], points: [],
        map: {centre: 'c', trails: [
          {name: 'T<1>', destinations: [{name: 'R&D', url: 'https://x.example.com/?a=1&b="2"',
                                         next: [{name: 'Deep', url: ''}]}]},
          {name: 'Two', destinations: [{name: 'Plain', url: '', next: []}]}]}};
      return [C.pageCount(s), C.pageCount({title: 't', paragraphs: [], map: null}), C.cardHtml(s, 0),
              C.cardHtml(s, 1), C.cardHtml(s, 9)];""")
    pages, plain_pages, overview, first, clamped = r
    assert pages == 3 and plain_pages == 1
    assert "&lt;b&gt;x&lt;/b&gt;" in overview and "a &amp; b" in overview
    assert overview.count('class="kb-chip"') == 2 and "T&lt;1&gt;" in overview and "<a " not in overview
    assert 'href="https://x.example.com/?a=1&amp;b=&quot;2&quot;"' in first
    assert 'target="_blank"' in first and 'rel="noopener noreferrer"' in first
    assert ">R&amp;D</a>" in first and '<span class="kb-plain">Deep</span>' in first and "›" in first
    assert "Two" in clamped and '<span class="kb-plain">Plain</span>' in clamped


def test_sign_label_lookup_by_key(js):
    r = content(js, """const t = C.normalizeTour({stops: [{sign: 'Flow'}]});
      return ['trailhead', 'continuity', 'scaffolding', 'download', 'tour', 'left', 'nope'].map((k) => C.signText(t, k));""")
    assert r == ["Trailhead", "Flow", "Scaffolding", "Download", "The tour", "Issues", ""]


def test_the_knowledge_stop_ships_the_draft_trail_map(js):
    r = content(js, """const m = C.normalizeTour(undefined).stops[2].map;
      const stops = m.trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next]));
      return [m.centre, m.trails.map((t) => t.name), stops.length, stops.every((s) => s.url === ''),
              m.trails[2].destinations.map((d) => [d.name, d.next.map((e) => e.name)])];""")
    centre, trails, count, unlinked, language = r
    assert centre == "blazeAhead"
    assert trails == ["Getting connected", "Agentic workflow", "Language specific", "Infrastructure",
                      "Corporate knowledge"]
    assert count == 21 and unlinked is True
    assert language == [["Java", ["Artifactory"]], ["C++", ["SonarQube"]], ["Python", ["PyPI mirror"]]]


def test_only_web_links_become_links(js):
    raw = {"stops": [{}, {}, {"map": {"centre": "Start", "trails": [{"name": "T", "destinations": [
        {"name": "a", "url": "https://wiki.example.com/a"}, {"name": "b", "url": "javascript:alert(1)"},
        {"name": "c", "url": "  http://x.example.com  "}, {"name": "d", "url": "www.example.com"},
        {"name": "e"}]}]}}]}
    r = content(js, f"return C.normalizeTour({json.dumps(raw)}).stops[2].map;")
    assert r["centre"] == "Start"
    assert [(d["name"], d["url"]) for d in r["trails"][0]["destinations"]] == [
        ("a", "https://wiki.example.com/a"), ("b", ""), ("c", "http://x.example.com"), ("d", ""), ("e", "")]


def test_the_map_keeps_to_its_limits_and_says_what_it_left_out(js):
    r = content(js, """const warned = []; const orig = console.warn; console.warn = (m) => warned.push(String(m));
      const one = (n) => ({name: n});
      const map = (trails) => C.normalizeTour({stops: [{}, {}, {map: {trails}}]}).stops[2].map;
      const a = map(Array.from({length: 7}, (_, i) => ({name: 'T' + i, destinations: [one('d' + i)]})));
      const b = map([{name: 'T', destinations: Array.from({length: 8}, (_, j) => one('d' + j))}]);
      const c = map([{name: 'T', destinations: [{name: 'd', next: [one('n1'), one('n2'), {name: 'n3'},
                                                                   {name: 'n4', next: [one('deep')]}]}]}]);
      const d = map(Array.from({length: 5}, (_, i) => ({name: 'T' + i,
        destinations: Array.from({length: 5}, (_, j) => ({name: `d${i}.${j}`, next: [one(`n${i}.${j}`)]}))})));
      console.warn = orig;
      const count = (m) => m.trails.flatMap((t) => t.destinations.flatMap((x) => [x, ...x.next])).length;
      return [a.trails.length, b.trails[0].destinations.length, c.trails[0].destinations[0].next.length,
              c.trails[0].destinations[0].next.some((e) => 'next' in e), count(d), warned.length,
              warned.every((w) => w.startsWith('blazeAhead: the knowledge-base map keeps'))];""")
    assert r == [5, 5, 2, False, 25, 4, True]


def test_unnamed_stops_and_an_unusable_map_are_reported(js):
    nameless, nonsense, default = content(js, """const warnings = (fn) => {
        const warned = []; const orig = console.warn; console.warn = (m) => warned.push(String(m));
        try { fn(); } finally { console.warn = orig; }
        return warned;
      };
      return [
        warnings(() => C.normalizeTour({stops: [{}, {}, {map: {trails: [{name: 'T', destinations: [
          {name: 'ok'}, {url: 'https://x.example.com'}]}]}}]})),
        warnings(() => C.normalizeTour({stops: [{}, {}, {map: 'nonsense'}]})),
        warnings(() => C.normalizeTour(undefined)),
      ];""")
    assert len(nameless) == 1 and "1 unnamed item" in nameless[0], nameless
    assert len(nonsense) == 1 and "shipped map" in nonsense[0], nonsense
    assert default == []


def test_a_broken_map_falls_back_to_the_draft_and_other_stops_have_none(js):
    r = content(js, """const bad = [undefined, 'map', {trails: 'x'},
        {trails: [{name: '', destinations: [{name: 'a'}]},
                  {name: 'T', destinations: [{url: 'https://x.example.com'}, 7, {name: 'ok', next: 'nope'}]},
                  {name: 'Empty', destinations: []}]}];
      const tours = bad.map((m) => C.normalizeTour({stops: [{map: {trails: [{name: 'X', destinations: [{name: 'y'}]}]}},
                                                            {}, {map: m}]}));
      const kept = tours[3].stops[2].map.trails;
      return [tours.slice(0, 3).map((t) => t.stops[2].map.trails.length), kept.map((t) => t.name),
              kept[0].destinations.map((d) => [d.name, d.next.length]), tours[0].stops[0].map];""")
    assert r == [[5, 5, 5], ["T"], [["ok", 0]], None]


def test_shipped_files_load_and_match_the_world(js):
    r = js("""
      for (const src of ['/public/site-config.js', '/public/tour-content.js']) {
        await new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src;
          s.onload = ok; s.onerror = fail; document.head.append(s); });
      }
      const C = await import('/public/js/content.js');
      const t = C.normalizeTour(window.BLAZEAHEAD_TOUR);
      return [typeof window.BLAZEAHEAD_SITE, t.stops.map((s) => s.sign), C.pageCount(t.stops[2]), t.rocks.length,
              t.stops[2].map.trails.length];""")
    assert r == ["object", ["Continuity", "Scaffolding", "Knowledge", "In Flight"], 6, 5, 5]

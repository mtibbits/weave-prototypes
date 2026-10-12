def state(js, body):
    return js("const {TourState} = await import('/public/js/tour-state.js');" + body)


def test_starts_at_the_trailhead_and_walks_to_stop_one(js):
    r = state(js, "const s = new TourState(4); const a = s.index; const b = s.request('next');"
                  "const w = s.walking; const after = s.arrive(); return [a, b, w, s.index, after, s.walking];")
    assert r == [-1, "walk", True, 0, None, False]


def test_queues_only_the_latest_request_while_walking(js):
    r = state(js, """const s = new TourState(4); const a = s.request('next');
      const b = s.request('next'); const c = s.request('next'); const d = s.request(0);
      const after = s.arrive(); return [a, b, c, d, s.index, after, s.walking];""")
    assert r == ["walk", "queued", "queued", "queued", 0, None, False]


def test_a_queued_request_starts_the_next_walk_on_arrival(js):
    r = state(js, """const s = new TourState(4); s.request('next'); s.request(2);
      const next = s.arrive(); return [next, s.index, s.walking, s.from];""")
    assert r == [2, 2, True, 0]


def test_ends_exit_to_home_and_download(js):
    r = state(js, """const s = new TourState(4); s.index = 0; const a = s.request('prev');
      s.index = 3; const b = s.request('next'); return [a, b, s.walking];""")
    assert r == ["exit-start", "exit-end", False]


def test_jumping_to_the_current_stop_does_nothing(js):
    assert state(js, "const s = new TourState(4); s.index = 2; return s.request(2);") == "none"


def test_unknown_or_out_of_range_hash_opens_stop_one(js):
    r = state(js, """return [TourState.fromHash('#foo', 4), TourState.fromHash('#in-flight', 3),
      TourState.fromHash('#knowledge', 4), TourState.fromHash('', 4), TourState.fromHash('#', 4),
      TourState.fromHash(undefined, 4)];""")
    assert r == [0, 0, 2, -1, -1, -1]


def test_hash_round_trip(js):
    r = state(js, "const s = new TourState(4); return [0,1,2,3].map((i) => s.indexForHash(s.hashFor(i))).concat([s.hashFor(-1)]);")
    assert r == [0, 1, 2, 3, ""]


def test_card_pager_stays_in_bounds_and_resets_on_a_new_stop(js):
    r = state(js, """const s = new TourState(4); s.index = 2;
      const a = [s.nextCard(3), s.nextCard(3), s.nextCard(3), s.prevCard(), s.prevCard(), s.prevCard()];
      s.nextCard(3); s.request(3); return a.concat([s.cardIndex]);""")
    assert r == [1, 2, 2, 1, 0, 0, 0]


def test_stop_count_is_clamped_to_the_world(js):
    r = state(js, "return [new TourState(9).count, new TourState(0).count, new TourState(3).count];")
    assert r == [4, 1, 3]


def test_a_queued_exit_is_reported_on_arrival(js):
    r = state(js, """const s = new TourState(4); s.index = 2; s.request('next'); s.request('next');
      const next = s.arrive(); return [next, s.lastOutcome, s.index, s.walking];""")
    assert r == [None, "exit-end", 3, False]

import urllib.request


def test_server_serves_js_as_javascript(base_url):
    with urllib.request.urlopen(f"{base_url}/tests/harness_probe.js") as resp:
        assert resp.headers["Content-Type"].startswith("text/javascript")


def test_js_fixture_runs_module_code(js):
    assert js("const m = await import('/tests/harness_probe.js'); return m.answer();") == 42

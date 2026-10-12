import urllib.request


def test_server_serves_js_as_javascript(base_url):
    with urllib.request.urlopen(f"{base_url}/tests/harness_probe.js") as resp:
        assert resp.headers["Content-Type"].startswith("text/javascript")


def test_js_fixture_runs_module_code(js):
    assert js("const m = await import('/tests/harness_probe.js'); return m.answer();") == 42


def test_a_download_the_browser_abandons_is_not_reported_as_an_error(capfd):
    import socket
    import struct
    import sys
    import time
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import serve

    server, url = serve.start(Path(__file__).resolve().parents[1] / "public")
    try:
        port = server.server_address[1]
        for _ in range(3):   # a closed tab: ask for the 500 KB world, then drop the connection
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(b"GET /assets/blazeahead.glb HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            s.recv(1024)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            s.close()
        time.sleep(0.5)
    finally:
        server.shutdown()
        server.server_close()
    assert "Exception occurred" not in capfd.readouterr().err

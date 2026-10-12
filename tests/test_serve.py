"""tools/serve.py: the preview and test server queues a browser's burst of connections instead of refusing them."""
import functools
import socket
from pathlib import Path

import serve

ROOT = Path(__file__).resolve().parents[1]


def test_server_queues_a_burst_of_connections():
    # Nothing accepts here, so every connection waits in the listen queue. With socketserver's default backlog
    # of 5, Windows refuses the 6th: in the WEAVE suite that surfaced as a rare "Failed to fetch dynamically
    # imported module" (or a font that never loads) whenever a module graph's requests arrived together.
    server = serve._Server(("127.0.0.1", 0), functools.partial(serve.Handler, directory=str(ROOT)))
    sockets, refused = [], 0
    try:
        for _ in range(32):
            s = socket.socket()
            s.settimeout(2)
            try:
                s.connect(server.server_address)
                sockets.append(s)
            except OSError:
                refused += 1
                s.close()
        assert refused == 0, f"{refused} of 32 connections refused"
    finally:
        for s in sockets:
            s.close()
        server.server_close()

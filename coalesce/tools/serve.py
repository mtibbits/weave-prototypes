"""Serve a folder at http://127.0.0.1 with correct MIME types (Windows can map .js to text/plain).

Usage:  python tools/serve.py [folder] [--port 8000]      (folder defaults to public/)
"""
import argparse
import functools
import http.server
import socketserver
import threading
import time
from pathlib import Path

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".png": "image/png",
    ".glb": "model/gltf-binary",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start(directory, port=0):
    """Serve `directory` from a background thread; returns (server, base_url)."""
    handler = functools.partial(Handler, directory=str(directory))
    server = _Server(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def main():
    parser = argparse.ArgumentParser(description="Serve a folder locally with correct MIME types.")
    parser.add_argument("folder", nargs="?", default=str(Path(__file__).resolve().parents[1] / "public"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server, url = start(args.folder, args.port)
    print(f"Serving {args.folder} at {url}/  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()

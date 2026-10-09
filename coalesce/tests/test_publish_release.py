import http.server
import json
import os
import shutil
import threading
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "publish-release.ps1"


def powershell():
    exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not exe:
        pytest.skip("Windows PowerShell is not available")
    return exe


def test_script_has_no_syntax_errors():
    command = ("$errors = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
               f"'{SCRIPT}', [ref]$null, [ref]$errors); $errors.Count")
    result = subprocess.run([powershell(), "-NoProfile", "-Command", command], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "0"


def test_dry_run_builds_a_release_with_the_direct_asset_path(tmp_path):
    xlam = tmp_path / "Coalesce.xlam"
    xlam.write_bytes(b"PK\x03\x04 not a real add-in")
    result = subprocess.run(
        [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
         "-GitLabUrl", "https://gitlab.example.com/", "-Project", "ops/coalesce",
         "-Version", "2.4.0", "-File", str(xlam), "-DryRun"],
        capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    api = "https://gitlab.example.com/api/v4/projects/ops%2Fcoalesce"
    assert lines[0] == f"PUT  {api}/packages/generic/coalesce/2.4.0/Coalesce.xlam"
    assert lines[1] == f"POST {api}/releases"
    body = json.loads("\n".join(lines[2:]))
    assert body["tag_name"] == "v2.4.0" and body["ref"] == "main"
    link = body["assets"]["links"][0]
    assert link["direct_asset_path"] == "/Coalesce.xlam"
    assert link["url"] == f"{api}/packages/generic/coalesce/2.4.0/Coalesce.xlam"
    assert link["link_type"] == "package"


def test_release_notes_are_sent_as_utf8(tmp_path):
    received = {}

    class Echo(http.server.BaseHTTPRequestHandler):
        def _reply(self):
            length = int(self.headers.get("Content-Length", 0))
            received[self.command] = (self.headers.get("Content-Type") or "", self.rfile.read(length))
            body = b"{}"
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_PUT = do_POST = _reply

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    notes = "Café — “quoted” fix"
    try:
        xlam = tmp_path / "Coalesce.xlam"
        xlam.write_bytes(b"PK")
        subprocess.run(
            [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
             "-GitLabUrl", f"http://127.0.0.1:{server.server_address[1]}", "-Project", "ops/coalesce",
             "-Version", "2.4.1", "-File", str(xlam), "-Notes", notes],
            capture_output=True, text=True, check=True, env={**os.environ, "GITLAB_TOKEN": "test-token"})
    finally:
        server.shutdown()
    content_type, body = received["POST"]
    assert "utf-8" in content_type.lower()
    assert json.loads(body.decode("utf-8"))["description"] == notes

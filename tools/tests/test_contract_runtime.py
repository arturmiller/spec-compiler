from __future__ import annotations

import json
from pathlib import Path
import socket
import sys

import httpx

from tools.contract_runtime import running_product


CHILD_SERVER = '''
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

payload = json.dumps({
    "openapi": "3.1.0",
    "info": {"title": "runner test", "version": "1"},
    "paths": {},
}).encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


HTTPServer((sys.argv[1], int(sys.argv[2])), Handler).serve_forever()
'''

PARENT_PROCESS = '''
import os
import subprocess
import sys

child = subprocess.Popen([
    sys.executable,
    "child_server.py",
    os.environ["HOST"],
    os.environ["PORT"],
])
raise SystemExit(child.wait())
'''


def _toml_string(value: str) -> str:
    return json.dumps(value)


def test_running_product_stops_the_complete_process_tree(tmp_path: Path):
    (tmp_path / "child_server.py").write_text(CHILD_SERVER, encoding="utf-8")
    (tmp_path / "parent_process.py").write_text(PARENT_PROCESS, encoding="utf-8")
    (tmp_path / "product.toml").write_text(
        "\n".join(
            [
                "protocol_version = 1",
                "",
                "[runtime]",
                f"command = [{_toml_string(sys.executable)}, \"parent_process.py\"]",
                'openapi_path = "/openapi.json"',
                "ready_timeout_seconds = 10",
                "",
                "[runtime.environment]",
                'HOST = "{host}"',
                'PORT = "{port}"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with running_product(tmp_path) as product:
        response = httpx.get(product.openapi_url)
        response.raise_for_status()
        host, port = product.base_url.removeprefix("http://").rsplit(":", 1)

    try:
        httpx.get(product.openapi_url, timeout=0.25)
    except httpx.HTTPError:
        pass
    else:
        raise AssertionError("Child HTTP server survived runtime cleanup")

    with socket.socket() as sock:
        assert sock.connect_ex((host, int(port))) != 0

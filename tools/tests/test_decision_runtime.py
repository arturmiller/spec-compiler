from __future__ import annotations

import json
from pathlib import Path
import socket
import sys

import pytest

from tools.decision_runtime import DecisionProcessResult, run_decision


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _manifest(command: list[str], *, timeout: float = 10) -> str:
    rendered_command = ", ".join(_toml_string(part) for part in command)
    return (
        "decision_protocol_version = 1\n\n"
        "[decision]\n"
        f"command = [{rendered_command}]\n"
        f"timeout_seconds = {timeout}\n\n"
        "[decision.environment]\n"
        'PYTHONIOENCODING = "utf-8"\n'
    )


def test_run_decision_uses_manifest_and_utf8_json_without_importing_product(
    tmp_path: Path,
):
    script = tmp_path / "decision.py"
    script.write_text(
        "import json, sys\n"
        "request = json.load(sys.stdin)\n"
        "json.dump({'received': request, 'text': 'Anträge'}, sys.stdout, ensure_ascii=False)\n",
        encoding="utf-8",
    )
    (tmp_path / "product.toml").write_text(
        _manifest([sys.executable, "decision.py"]),
        encoding="utf-8",
    )

    result = run_decision(tmp_path, {"case": {"value": True}})

    assert result.returncode == 0
    assert result.json_output() == {
        "received": {"case": {"value": True}},
        "text": "Anträge",
    }


def test_decision_result_rejects_non_object_json():
    result = DecisionProcessResult(0, "[]", "")

    with pytest.raises(ValueError, match="must be a JSON object"):
        result.json_output()


def test_run_decision_rejects_non_utf8_output(tmp_path: Path):
    script = tmp_path / "decision.py"
    script.write_text(
        "import sys\nsys.stdout.buffer.write(b'\\xff')\n",
        encoding="utf-8",
    )
    (tmp_path / "product.toml").write_text(
        _manifest([sys.executable, "decision.py"]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be valid UTF-8"):
        run_decision(tmp_path, {})


def test_run_decision_rejects_unknown_protocol(tmp_path: Path):
    (tmp_path / "product.toml").write_text(
        "decision_protocol_version = 2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="decision_protocol_version = 1"):
        run_decision(tmp_path, {})


def test_run_decision_rejects_working_directory_outside_bundle(tmp_path: Path):
    (tmp_path / "product.toml").write_text(
        "decision_protocol_version = 1\n\n"
        "[decision]\n"
        f"command = [{_toml_string(sys.executable)}, \"-c\", \"pass\"]\n"
        'working_directory = ".."\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must stay in the Product Bundle"):
        run_decision(tmp_path, {})


def test_run_decision_stops_the_complete_process_tree_on_timeout(tmp_path: Path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    ready = tmp_path / "ready"
    child = tmp_path / "child.py"
    child.write_text(
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "from pathlib import Path\n"
        "import sys\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def log_message(self, format, *args): pass\n"
        "Path(sys.argv[2]).write_text('ready', encoding='utf-8')\n"
        "HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, 'child.py', sys.argv[1], sys.argv[2]])\n"
        "raise SystemExit(child.wait())\n",
        encoding="utf-8",
    )
    (tmp_path / "product.toml").write_text(
        _manifest(
            [sys.executable, "parent.py", str(port), str(ready)],
            timeout=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="did not finish"):
        run_decision(tmp_path, {})

    assert ready.is_file(), "The child process never reached its ready state"
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0

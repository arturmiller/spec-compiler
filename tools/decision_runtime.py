"""Invoke a decision product through Decision Protocol v1."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tomllib
from typing import Any, Mapping

from tools.process_runtime import stop_process_tree


@dataclass(frozen=True)
class DecisionProcessResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr

    def json_output(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.stdout)
        except json.JSONDecodeError as error:
            raise ValueError(
                "Decision Protocol v1 product did not return one JSON document"
            ) from error
        if not isinstance(payload, dict):
            raise ValueError(
                "Decision Protocol v1 product result must be a JSON object"
            )
        return payload


def _render(value: str, variables: Mapping[str, str]) -> str:
    try:
        return value.format_map(variables)
    except KeyError as error:
        raise ValueError(f"Unknown decision placeholder: {error.args[0]}") from error


def run_decision(
    product_root: Path,
    request: Mapping[str, Any],
) -> DecisionProcessResult:
    """Run one decision without importing or knowing its implementation."""
    product_root = product_root.resolve()
    with (product_root / "product.toml").open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)
    if manifest.get("decision_protocol_version") != 1:
        raise ValueError(
            "product.toml must declare decision_protocol_version = 1"
        )

    decision = manifest["decision"]
    variables = {"product_root": str(product_root)}
    command = [_render(str(part), variables) for part in decision["command"]]
    working_directory = (
        product_root / decision.get("working_directory", ".")
    ).resolve()
    if not working_directory.is_relative_to(product_root):
        raise ValueError("decision.working_directory must stay in the Product Bundle")
    timeout = float(decision.get("timeout_seconds", 30))
    environment = os.environ.copy()
    environment.update(
        {
            str(name): _render(str(value), variables)
            for name, value in decision.get("environment", {}).items()
        }
    )

    process = subprocess.Popen(
        command,
        cwd=working_directory,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    serialized_request = (
        json.dumps(request, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    try:
        stdout_bytes, stderr_bytes = process.communicate(
            serialized_request,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        stop_process_tree(process)
        raise RuntimeError(
            f"Decision product did not finish after {timeout:g} seconds"
        ) from error
    finally:
        if process.poll() is None:
            stop_process_tree(process)
    try:
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            "Decision Protocol v1 product output must be valid UTF-8"
        ) from error
    return DecisionProcessResult(process.returncode, stdout, stderr)

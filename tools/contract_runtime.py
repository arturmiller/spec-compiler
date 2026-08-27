"""Start a product through its declared runtime interface."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import socket
import subprocess
from tempfile import TemporaryFile
import time
import tomllib
from typing import Iterator, Mapping

import httpx


@dataclass(frozen=True)
class RunningProduct:
    """Network coordinates of a product started by its manifest."""

    base_url: str
    openapi_url: str


def _available_port(host: str) -> int:
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _render(value: str, variables: Mapping[str, str]) -> str:
    try:
        return value.format_map(variables)
    except KeyError as error:
        raise ValueError(f"Unknown runtime placeholder: {error.args[0]}") from error


def _read_log(log) -> str:
    log.flush()
    log.seek(0)
    return log.read()


def _stop_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        if process.poll() is not None:
            return
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    time.sleep(0.1)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        process.wait(timeout=5)


@contextmanager
def running_product(
    product_root: Path,
    *,
    variables: Mapping[str, str] | None = None,
) -> Iterator[RunningProduct]:
    """Start a product without importing or knowing its implementation."""
    product_root = product_root.resolve()
    with (product_root / "product.toml").open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)
    if manifest.get("protocol_version") != 1:
        raise ValueError("product.toml must declare runtime protocol_version = 1")

    runtime = manifest["runtime"]
    host = str(runtime.get("host", "127.0.0.1"))
    openapi_path = str(runtime["openapi_path"])
    if not openapi_path.startswith("/"):
        raise ValueError("runtime.openapi_path must start with '/'")

    working_directory = product_root / runtime.get("working_directory", ".")
    timeout = float(runtime.get("ready_timeout_seconds", 30))
    startup_errors = []

    for _ in range(3):
        port = _available_port(host)
        values = {
            "product_root": str(product_root),
            "host": host,
            "port": str(port),
            **(variables or {}),
        }
        command = [_render(str(part), values) for part in runtime["command"]]
        environment = os.environ.copy()
        environment.update(
            {
                str(name): _render(str(value), values)
                for name, value in runtime.get("environment", {}).items()
            }
        )
        base_url = f"http://{host}:{port}"
        openapi_url = base_url + openapi_path

        with TemporaryFile(mode="w+t", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                text=True,
            )
            try:
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        startup_errors.append(_read_log(log))
                        break
                    try:
                        response = httpx.get(openapi_url, timeout=0.25)
                        if response.status_code == 200:
                            yield RunningProduct(
                                base_url=base_url,
                                openapi_url=openapi_url,
                            )
                            return
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.05)
                else:
                    raise RuntimeError(
                        f"Product was not ready after {timeout:g} seconds:\n"
                        + _read_log(log)
                    )
            finally:
                _stop_process_tree(process)

    raise RuntimeError(
        "Product exited before becoming ready after three attempts:\n"
        + "\n--- attempt ---\n".join(startup_errors)
    )

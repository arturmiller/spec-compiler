"""Invoke a spec compiler through Compiler Protocol v1."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tomllib
from typing import Mapping


@dataclass(frozen=True)
class CompilerResult:
    returncode: int
    output: str


def _render(value: str, variables: Mapping[str, str]) -> str:
    try:
        return value.format_map(variables)
    except KeyError as error:
        raise ValueError(f"Unknown compiler placeholder: {error.args[0]}") from error


def run_compiler(compiler_root: Path, input_product_root: Path) -> CompilerResult:
    """Run a compiler without importing or knowing its implementation."""
    compiler_root = compiler_root.resolve()
    input_product_root = input_product_root.resolve()
    with (compiler_root / "product.toml").open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)
    if manifest.get("compiler_protocol_version") != 1:
        raise ValueError(
            "product.toml must declare compiler_protocol_version = 1"
        )

    compiler = manifest["compiler"]
    repository_root = compiler_root.parents[1]
    variables = {
        "compiler_root": str(compiler_root),
        "repository_root": str(repository_root),
        "input_product_root": str(input_product_root),
    }
    command = [_render(str(part), variables) for part in compiler["command"]]
    working_directory = (
        compiler_root / compiler.get("working_directory", ".")
    ).resolve()
    timeout = float(compiler.get("timeout_seconds", 30))
    environment = os.environ.copy()
    environment.update(
        {
            str(name): _render(str(value), variables)
            for name, value in compiler.get("environment", {}).items()
        }
    )
    completed = subprocess.run(
        command,
        cwd=working_directory,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return CompilerResult(completed.returncode, completed.stdout)

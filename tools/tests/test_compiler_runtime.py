from pathlib import Path
import json
import sys

import pytest

from tools.compiler_runtime import run_compiler


def test_run_compiler_uses_manifest_without_importing_product(tmp_path: Path):
    compiler_root = tmp_path / "compiler"
    compiler_root.mkdir()
    script = compiler_root / "compiler.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "print(Path(sys.argv[1]).name)\n",
        encoding="utf-8",
    )
    (compiler_root / "product.toml").write_text(
        "compiler_protocol_version = 1\n\n"
        "[compiler]\n"
        f"command = [{json.dumps(sys.executable)}, \"compiler.py\", "
        '"{input_product_root}"]\n',
        encoding="utf-8",
    )
    input_root = tmp_path / "input-product"
    input_root.mkdir()

    result = run_compiler(compiler_root, input_root)

    assert result.returncode == 0
    assert result.output.strip() == "input-product"


def test_run_compiler_rejects_unknown_protocol(tmp_path: Path):
    (tmp_path / "product.toml").write_text(
        "compiler_protocol_version = 2\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="compiler_protocol_version = 1"):
        run_compiler(tmp_path, tmp_path)

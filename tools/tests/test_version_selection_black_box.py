from pathlib import Path
import shutil

import pytest

from tools.compiler_runtime import run_compiler


ROOT = Path(__file__).parents[2]
COMPILER_ROOT = ROOT / "products" / "spec_compiler"
FIXTURE_ROOT = ROOT / "products" / "kfw_458_eligibility"


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "kfw-458"
    shutil.copytree(FIXTURE_ROOT, target)
    return target


def _replace(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert source.count(old) == 1
    path.write_text(source.replace(old, new), encoding="utf-8")


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        (
            "missing-date",
            "must declare exactly one Decision Date",
        ),
        (
            "uncovered-date",
            "matches 0 Rule Set Versions",
        ),
        (
            "overlapping-validity",
            "overlapping validity periods",
        ),
    ],
)
def test_compiler_rejects_ambiguous_version_applicability(
    tmp_path: Path, mutation: str, diagnostic: str
) -> None:
    product_root = _copy_fixture(tmp_path)
    cases = product_root / "specs" / "conformance_cases.ttl"
    contract = product_root / "specs" / "decision_contract.ttl"
    if mutation == "missing-date":
        _replace(
            cases,
            '    sdo:decisionDate "2026-07-20"^^xsd:date ;\n',
            "",
        )
    elif mutation == "uncovered-date":
        _replace(cases, '"2026-07-20"^^xsd:date', '"2025-12-09"^^xsd:date')
    else:
        _replace(
            contract,
            'sdo:validUntil "2026-07-21"^^xsd:date',
            'sdo:validUntil "2026-08-01"^^xsd:date',
        )

    result = run_compiler(COMPILER_ROOT, product_root)

    assert result.returncode != 0
    assert diagnostic in result.output

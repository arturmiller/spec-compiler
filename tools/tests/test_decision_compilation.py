"""Composition checks at the compiler CLI and its artifact-planning interface."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from rdflib import Graph, Namespace, RDF

from tools import generate


ROOT = Path(__file__).parents[2]
REFERENCE = ROOT / "products/kfw_458_eligibility"
KFW = Namespace("https://arturmiller.github.io/spec-compiler/resources/funding/kfw-458/#")


@pytest.fixture
def product(tmp_path):
    product = tmp_path / "decision-example"
    shutil.copytree(REFERENCE / "specs", product / "specs")
    return product


def _compile(product):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools/generate.py"), "--product", str(product)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


def _artifacts(product):
    return {path.relative_to(product).as_posix(): path.read_bytes()
            for directory in (product / "generated", product / "tests")
            for path in directory.rglob("*") if path.is_file()}


def _http_graph(product):
    return Graph().parse(product / "specs/http_api.ttl", format="turtle")


@pytest.mark.parametrize("mutation,diagnostic", [
    ("wrong-contract", "must invoke the product's Decision Contract"),
    ("missing-binding", "Expected exactly one"),
    ("missing-message", "Expected exactly one"),
    ("mixed-profiles", "must select exactly one executable profile"),
])
def test_invalid_composition_preserves_previous_artifacts(product, mutation, diagnostic):
    result = _compile(product)
    assert result.returncode == 0, result.stderr
    before = _artifacts(product)
    graph = _http_graph(product)
    endpoint = KFW.ApplicantEligibilityPostEndpoint
    if mutation == "wrong-contract":
        graph.set((endpoint, generate.SCO.invokesContract, KFW.OtherDecision))
    elif mutation == "missing-binding":
        graph.remove((endpoint, generate.SCO.invokesContract, None))
    elif mutation == "missing-message":
        graph.remove((endpoint, generate.SCO.request, None))
    else:
        graph.add((KFW.OtherEndpoint, RDF.type, generate.SCO.GetEndpoint))
    graph.serialize(product / "specs/http_api.ttl", format="turtle")

    result = _compile(product)
    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert _artifacts(product) == before


def test_http_to_decision_cleans_only_owned_stale_outputs(product):
    result = _compile(product)
    assert result.returncode == 0, result.stderr
    before = _artifacts(product)
    assert "tests/test_http_contract.py" in before
    work_graph = json.loads(before["generated/work-graph.json"])
    http_item = next(item for item in work_graph["work_items"] if item["id"].endswith(".http-api"))
    assert f"generated/issues/{http_item['id']}.md" in before
    retained = product / "generated/notes.txt"
    retained.write_text("authored note", encoding="utf-8")
    nested = product / "generated/issues/archive/note.md"
    nested.parent.mkdir()
    nested.write_text("archived note", encoding="utf-8")
    stale = product / "generated/issues/obsolete.md"
    stale.write_text("old generated issue", encoding="utf-8")

    (product / "specs/http_api.ttl").unlink()
    result = _compile(product)
    assert result.returncode == 0, result.stderr
    after = _artifacts(product)
    assert after["generated/decision-contract.json"] == before["generated/decision-contract.json"]
    assert after["tests/test_contract.py"] == before["tests/test_contract.py"]
    assert "tests/test_http_contract.py" not in after
    assert "generated/expected-openapi.json" not in after
    assert f"generated/issues/{http_item['id']}.md" not in after
    assert not stale.exists()
    assert retained.read_text(encoding="utf-8") == "authored note"
    assert nested.read_text(encoding="utf-8") == "archived note"
    assert "http_contract_conventions_version" not in json.loads(after["generated/work-graph.json"])
    result = _compile(product)
    assert result.returncode == 0, result.stderr
    assert _artifacts(product) == after


def test_decision_reader_is_independent_of_http_errors(product):
    graph = generate.load_contract_graph(product)
    before = generate.read_decision_model(product, graph)
    graph.remove((KFW.ApplicantEligibilityPostEndpoint, generate.SCO.request, None))
    assert generate.read_decision_model(product, graph) == before
    with pytest.raises(ValueError, match="Expected exactly one"):
        generate.read_http_endpoint(graph)


def test_late_render_failure_preserves_artifacts_and_pending_cleanup(product, monkeypatch):
    result = _compile(product)
    assert result.returncode == 0, result.stderr
    stale = product / "generated/issues/obsolete.md"
    stale.write_text("old generated issue", encoding="utf-8")
    before = _artifacts(product)
    # Omit HTTP: both HTTP cleanup and stale-issue cleanup would have happened
    # before rendering the final issue in the previous implementation.
    model = generate.read_decision_model(product)
    original_render = generate.render_issue

    def fail_on_final_issue(item, product_path):
        if item["id"].endswith(".result-provenance"):
            raise ValueError("injected final issue failure")
        return original_render(item, product_path)

    monkeypatch.setattr(generate, "render_issue", fail_on_final_issue)
    with pytest.raises(ValueError, match="injected final issue failure"):
        generate.generate_decision_contract(product, str(product), model)
    assert _artifacts(product) == before


@pytest.mark.parametrize("outputs,obsolete", [
    ((("tests/test_contract.py", "one"), ("tests/test_contract.py", "two")), ()),
    ((("tests/test_contract.py", "one"),), ("tests/test_contract.py",)),
    ((("generated", "one"), ("generated/work-graph.json", "two")), ()),
    ((("../outside", "one"),), ()),
])
def test_conflicting_artifact_plans_are_rejected_before_writing(tmp_path, outputs, obsolete):
    with pytest.raises(ValueError, match="conflicting|product-relative"):
        generate.ArtifactPlan(
            tuple((Path(path), content) for path, content in outputs),
            tuple(Path(path) for path in obsolete),
        ).write(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_successful_planning_does_not_create_or_clean_files(product):
    graph = generate.load_contract_graph(product)
    plan = generate.plan_decision_contract(
        product, str(product), generate.read_decision_model(product, graph),
        generate.read_http_endpoint(graph),
    )
    assert not (product / "generated").exists()
    assert not (product / "tests").exists()
    plan.write(product)
    assert "tests/test_http_contract.py" in _artifacts(product)

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tools import compiler_support as support
from tools import documentation_site as site


@pytest.fixture(scope="session")
def baseline_inventory():
    return support.build_inventory()


@pytest.fixture
def inventory_root(tmp_path, baseline_inventory):
    # Copy just the declared inputs: tests never need product implementations.
    for relative in baseline_inventory["sources"]:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(support.ROOT / relative, destination)
    return tmp_path


def test_inventory_keeps_classification_support_and_evidence_distinct(baseline_inventory):
    inventory = baseline_inventory
    terms = {term["name"]: term for term in inventory["terms"]}
    patterns = {pattern["id"]: pattern for pattern in inventory["patterns"]}
    assert {module["prefix"] for module in inventory["modules"]} == {
        "sco", "sqlo", "dpo", "cco", "sdo", "funding", "cloud",
    }
    assert inventory["coreDecision"] == "pending-review"
    assert all(module["coreStatus"] == "undecided" for module in inventory["modules"])
    assert patterns["compiler-contract"]["profiles"] == ["compiler"]
    assert patterns["decision-result-model"]["status"] == "descriptive"
    assert patterns["subclass-execution"]["evidenceStatus"] == "missing"
    assert patterns["retired-vocabulary"]["status"] == "retired"
    assert "context" in terms["funding:Applicant"]["roles"]
    assert "contract" in terms["funding:owner"]["roles"]
    assert all(term["patterns"] for term in terms.values())
    standards = {entry["expression"] for entry in inventory["standardExpressions"]}
    assert {"xsd:boolean", "xsd:date", "xsd:positiveInteger"} <= standards
    assert all(not Path(path).is_absolute() for path in inventory["sources"])


def test_new_public_term_cannot_silently_bypass_the_inventory(inventory_root):
    path = inventory_root / "ontology/decision-obligation.ttl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('\nsdo:UnclassifiedCondition a owl:Class ; rdfs:label "Neue Bedingung"@de .\n')
    with pytest.raises(ValueError, match="Public terms missing support classification: sdo:UnclassifiedCondition"):
        support.build_inventory(inventory_root)


def test_orphaned_term_assignment_is_rejected(inventory_root):
    path = inventory_root / support.SOURCE
    markup = path.read_text(encoding="utf-8").replace('data-terms="sco:GetEndpoint ', 'data-terms="sco:NeverDefined sco:GetEndpoint ', 1)
    with pytest.raises(ValueError, match="Undefined or orphaned support term: sco:NeverDefined"):
        support.build_inventory(inventory_root, markup=markup)


@pytest.mark.parametrize(("before", "after", "message"), [
    ('data-profiles="all"', 'data-profiles="imagined"', "Invalid support profiles"),
    ('data-roles="spec-constraint"', 'data-roles="fully-proven"', "Invalid support roles"),
    ('data-core="candidate"', 'data-core="approved"', "Core membership is not decided"),
    ('#ontology-module-conventions-v1', '#missing-convention', "Missing support reference anchor"),
    ('data-symbol="validate_ontology_modules"', 'data-symbol="not_a_function"', "Missing support implementation symbol"),
    ('data-symbol="test_term_ownership_and_definition_are_checked"', 'data-symbol="missing_test"', "Missing support test symbol"),
    ('data-evidence="referenced"', 'data-evidence="missing"', "Support gap needs an explanation and follow-up"),
    ('data-support-pattern="module-boundaries"', 'data-support-pattern="different-anchor"', "Invalid or duplicate support pattern"),
    ('href="../../tools/generate.py"', 'href="../../../outside.py"', "Missing or unsafe support reference"),
])
def test_invalid_claims_and_stale_references_fail(inventory_root, before, after, message):
    markup = (inventory_root / support.SOURCE).read_text(encoding="utf-8")
    assert before in markup
    with pytest.raises(ValueError, match=message):
        support.build_inventory(inventory_root, markup=markup.replace(before, after, 1))


def test_a_documented_evidence_gap_is_valid_without_claiming_a_test(inventory_root):
    inventory = support.build_inventory(inventory_root)
    pattern = next(pattern for pattern in inventory["patterns"] if pattern["id"] == "subclass-execution")
    assert pattern["gap"]
    assert any(ref["kind"] == "followup" for ref in pattern["references"])
    assert not any(ref["kind"] == "test" for ref in pattern["references"])
    assert "Nachweis fehlt" in support.pattern_annotation(pattern)


def test_new_standard_reader_expression_requires_explicit_classification(inventory_root):
    path = inventory_root / "tools/generate.py"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\nNEW_STANDARD_USAGE = SH.pattern\n")
    with pytest.raises(ValueError, match="Standard expressions missing support classification: sh:pattern"):
        support.build_inventory(inventory_root)


def test_json_schema_keyword_changes_require_inventory_review(inventory_root):
    path = inventory_root / "tools/generate.py"
    text = path.read_text(encoding="utf-8")
    assert '"uniqueItems"' in text
    path.write_text(text.replace('"uniqueItems"', '"uniqueItems", "newKeyword"', 1), encoding="utf-8")
    with pytest.raises(ValueError, match="json-schema:newKeyword"):
        support.build_inventory(inventory_root)


def test_ontology_validation_runs_inventory_check_before_publication(inventory_root, monkeypatch):
    from tools import build_ontology_site as ontology

    monkeypatch.setattr(ontology, "ROOT", inventory_root)
    source = inventory_root / "ontology/decision-obligation.ttl"
    with source.open("a", encoding="utf-8") as handle:
        handle.write("\nsdo:UnexpectedPublicProperty a owl:ObjectProperty .\n")
    with pytest.raises(ValueError, match="Public terms missing support classification"):
        ontology.validate_publication_sources()


def test_documentation_validation_rejects_inventory_drift(inventory_root, monkeypatch):
    monkeypatch.setattr(site, "ROOT", inventory_root)
    monkeypatch.setattr(site, "SOURCES", inventory_root / "docs")
    source = inventory_root / support.SOURCE
    source.write_text(source.read_text(encoding="utf-8").replace("sco:GetEndpoint ", "", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="Public terms missing support classification: sco:GetEndpoint"):
        site.validate_sources(render_diagrams=False)


def test_documentation_publishes_json_terms_search_and_source_links(inventory_root, tmp_path, monkeypatch):
    source = inventory_root / support.SOURCE
    parser = site.DocumentParser()
    markup = source.read_text(encoding="utf-8")
    parser.feed(markup)
    document = site.Document(source, markup, parser)
    monkeypatch.setattr(site, "ROOT", inventory_root)
    monkeypatch.setattr(site, "SOURCES", inventory_root / "docs")
    monkeypatch.setattr(site, "read_documents", lambda: [document])
    monkeypatch.setattr(site, "diagram_sources", lambda: {})
    monkeypatch.setattr(site, "_renderer_digest", lambda: "inventory-test")
    assets = inventory_root / "docs/assets"
    assets.mkdir()
    (assets / "site.css").write_text("body{}", encoding="utf-8")
    (assets / "site.js").write_text("void 0", encoding="utf-8")
    output = tmp_path / "site"
    entries = site.compile_documents(output)
    published = (output / support.ROUTE).read_text(encoding="utf-8")
    inventory = json.loads((output / "reference/compiler-support.json").read_text(encoding="utf-8"))
    parsed = site.DocumentParser()
    parsed.feed(published)
    assert not parsed.duplicates
    assert 'data-support-inventory' not in published
    assert "Nachweis fehlt" in published
    assert "#L" in published
    for term in inventory["terms"]:
        anchor = support.term_anchor(term["name"])
        assert anchor in parsed.ids
        assert any(entry["url"] == support.ROUTE + "#" + anchor for entry in entries)
    assert any(link == ("a", "compiler-support.json") for link in parsed.links)
    for _tag, link in parsed.links:
        if link.startswith("#"):
            assert link[1:] in parsed.ids


def test_cli_exports_identical_bytes_across_hash_seeds_and_working_directories(tmp_path):
    outputs = []
    for seed in ("1", "73"):
        target = tmp_path / (seed + ".json")
        result = subprocess.run(
            [sys.executable, str(support.ROOT / "tools/compiler_support.py"), "--output", str(target)],
            cwd=tmp_path, capture_output=True, text=True,
            env={**os.environ, "PYTHONHASHSEED": seed}, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(target.read_bytes())
    assert outputs[0] == outputs[1]
    assert b'"coreDecision": "pending-review"' in outputs[0]

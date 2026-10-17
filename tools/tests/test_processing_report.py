"""Processing Report Conventions v1 through the public compiler CLI."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS
from rdflib.namespace import OWL

from tools import generate


ROOT = Path(__file__).parents[2]
REFERENCE = ROOT / "products/kfw_458_eligibility"
KFW = Namespace("https://arturmiller.github.io/spec-compiler/resources/funding/kfw-458/#")


@pytest.fixture
def product(tmp_path):
    target = tmp_path / "decision-pilot"
    shutil.copytree(REFERENCE / "specs", target / "specs")
    return target


def compile_product(product, *, script=None, seed="1", cwd=None):
    result = subprocess.run(
        [sys.executable, str(script or ROOT / "tools/generate.py"), "--product", str(product)],
        cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8", timeout=45,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONUTF8": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def read_report(product):
    return json.loads((product / "generated/processing-report.json").read_text(encoding="utf-8"))


def statement(report, subject, predicate):
    found = [entry for entry in report["statements"]
             if entry["subject"]["value"] == str(subject) and entry["predicate"]["value"] == str(predicate)]
    assert len(found) == 1
    return found[0]


def pointer(document, value):
    for part in value.split("/")[1:] if value else []:
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def snapshot(product):
    return {path.relative_to(product).as_posix(): path.read_bytes()
            for folder in (product / "generated", product / "tests")
            for path in folder.rglob("*") if path.is_file()}


def test_report_covers_authored_statements_and_resolves_its_evidence(product):
    compile_product(product)
    report = read_report(product)
    graph = Graph()
    for path in (product / "specs").glob("*.ttl"):
        graph.parse(path, format="turtle")
    assert report["summary"]["statements"] == len(graph)
    assert len({entry["id"] for entry in report["statements"]}) == len(graph)
    assert report["profile"] == "decision-http"
    assert report["scope"]["notCoveredProfiles"] == ["http-sql", "compiler"]
    assert report["scope"]["contractCompleteness"] == "not-assessed"
    assert report["scope"]["delegation"] == "not-assessed"
    assert report["compiler"]["sourceSha256"] == sha256((ROOT / "tools/generate.py").read_text(encoding="utf-8").encode()).hexdigest()
    assert set(report["compiler"]["dependencies"]) == {"rdflib", "jsonschema"}
    assert len(report["catalog"]["modules"]) == 7
    docs = {}
    proofs = []
    for entry in report["statements"]:
        assert entry["origins"]
        assert all(name.startswith("specs/") and (product / name).is_file() for name in entry["origins"])
        for usage in entry["uses"]:
            assert usage["conventions"] and usage["rule"]
            assert all(name in report["conventionReferences"] for name in usage["conventions"])
            for target in usage.get("artifacts", []):
                docs.setdefault(target["path"], json.loads((product / target["path"]).read_text(encoding="utf-8")))
                pointer(docs[target["path"]], target["jsonPointer"])
            for item in usage.get("workItems", []):
                work = json.loads((product / item["artifact"]).read_text())
                assert pointer(work, item["jsonPointer"])["id"] == item["id"]
                path, name = item["proof"].split("::")
                source = product / path
                assert source.is_file() and f"def {name}(" in source.read_text(encoding="utf-8")
                proofs.append(item["proof"])
    assert proofs
    binding = statement(report, KFW.ApplicantEligibilityPostEndpoint, generate.SCO.invokesContract)
    assert binding["semanticStatus"] == "contract"
    assert {use["kind"] for use in binding["uses"]} == {"structural", "contract"}
    assert any(use["rule"] == "decision-http-binding-v1" for use in binding["uses"])
    type_check = statement(report, KFW.ApplicantEligibilityPostEndpoint, RDF.type)
    assert type_check["processingStatus"] == "structural-only"
    assert type_check["semanticStatus"] == "unassigned"
    fact = statement(report, KFW.ConditionOwner, generate.SDO.expectedBoolean)
    assert any(use.get("workItems") for use in fact["uses"])


def add_unknowns(product):
    graph = Graph()
    graph.add((KFW.CustomCase, RDF.type, OWL.Class))
    graph.add((KFW.LocalNote, RDF.type, KFW.CustomCase))
    graph.add((KFW.LocalNote, RDFS.label, Literal('</summary><img src=x onerror="alert(1)">')))
    graph.add((KFW.ApplicantEligibilityDecision, KFW.unknownException, KFW.LocalNote))
    graph.add((KFW.LocalNote, generate.SCO.path, Literal("/unused-known-property")))
    graph.serialize(product / "specs/product-notes.ttl", format="turtle")


def test_unknown_facts_and_known_unused_properties_remain_unassigned(product):
    compile_product(product)
    before = (product / "generated/decision-contract.json").read_bytes()
    add_unknowns(product)
    compile_product(product)
    report = read_report(product)
    for subject, predicate in (
        (KFW.LocalNote, RDFS.label), (KFW.LocalNote, generate.SCO.path),
        (KFW.ApplicantEligibilityDecision, KFW.unknownException),
    ):
        entry = statement(report, subject, predicate)
        assert entry["semanticStatus"] == "unassigned"
        assert entry["processingStatus"] == "unassigned"
        assert {use["kind"] for use in entry["uses"]} == {"structural"}
    assert (product / "generated/decision-contract.json").read_bytes() == before
    html = (product / "generated/processing-report.html").read_text(encoding="utf-8")
    assert "Semantisch nicht zugeordnet" in html
    assert '<img src=x onerror="alert(1)">' not in html
    assert '&lt;img src=x onerror=' in html


def test_context_is_copied_to_a_specific_field_without_claiming_a_behavior_proof(product):
    compile_product(product)
    entry = statement(read_report(product), KFW.Kfw458Merkblatt2026_07, generate.DCTERMS.title)
    assert entry["semanticStatus"] == "context"
    copies = [use for use in entry["uses"] if use["kind"] == "context"]
    assert copies and all(not use.get("workItems") for use in copies)
    for use in copies:
        for target in use["artifacts"]:
            document = json.loads((product / target["path"]).read_text(encoding="utf-8"))
            assert pointer(document, target["jsonPointer"]) == entry["object"]["value"]


def test_duplicate_authored_statement_keeps_one_identity_and_both_origins(product):
    compile_product(product)
    before = statement(read_report(product), KFW.ApplicantEligibilityPostEndpoint, generate.SCO.path)
    graph = Graph()
    graph.add((KFW.ApplicantEligibilityPostEndpoint, generate.SCO.path, Literal("/eligibility-decisions")))
    graph.serialize(product / "specs/repeated.ttl", format="turtle")
    compile_product(product)
    after = statement(read_report(product), KFW.ApplicantEligibilityPostEndpoint, generate.SCO.path)
    assert after["id"] == before["id"]
    assert after["origins"] == sorted(before["origins"] + ["specs/repeated.ttl"])
    assert after["uses"] == before["uses"]


def test_blank_nodes_and_source_order_are_stable_across_hash_seeds(product, tmp_path):
    graph = Graph()
    for _ in range(2):
        parent, child = BNode(), BNode()
        graph.add((KFW.ExtraContext, KFW.relatedDetail, parent))
        graph.add((parent, KFW.relatedDetail, child))
        graph.add((child, RDFS.label, Literal("anonymous detail")))
    source = product / "specs/anonymous.ttl"
    graph.serialize(source, format="turtle")
    compile_product(product, seed="3")
    first = (product / "generated/processing-report.json").read_bytes()
    html = (product / "generated/processing-report.html").read_bytes()
    # Change lexical bnode labels, prefix syntax and input order only.
    graph = Graph().parse(source, format="turtle")
    source.write_text("\n".join(sorted(" ".join(term.n3() for term in triple) + " ." for triple in graph)[::-1]), encoding="utf-8")
    compile_product(product, seed="73", cwd=tmp_path)
    assert (product / "generated/processing-report.json").read_bytes() == first
    assert (product / "generated/processing-report.html").read_bytes() == html
    source.rename(product / "specs/renamed-anonymous.ttl")
    compile_product(product, seed="101")
    old = json.loads(first)
    renamed = read_report(product)
    assert {entry["id"] for entry in renamed["statements"]} == {entry["id"] for entry in old["statements"]}
    for entry in renamed["statements"]:
        entry["origins"] = [origin.replace("renamed-anonymous.ttl", "anonymous.ttl") for origin in entry["origins"]]
    assert renamed == old


def test_identical_files_keep_separate_blank_node_scopes(product):
    content = '_:same <urn:relation> "detail" .\n'
    (product / "specs/anonymous-a.ttl").write_text(content, encoding="utf-8")
    (product / "specs/anonymous-b.ttl").write_text(content, encoding="utf-8")
    compile_product(product)
    entries = [entry for entry in read_report(product)["statements"] if entry["predicate"]["value"] == "urn:relation"]
    assert len(entries) == 2
    assert len({entry["id"] for entry in entries}) == 2
    assert {tuple(entry["origins"]) for entry in entries} == {("specs/anonymous-a.ttl",), ("specs/anonymous-b.ttl",)}


def test_a_successful_normalizer_with_an_unused_query_cannot_claim_contract_use(product):
    add_unknowns(product)
    graph = generate.load_contract_graph(product, processing_report=True)
    model = generate.read_decision_model(product, graph)
    endpoint = generate.read_http_endpoint(graph)

    @generate.interpreted("unused-query", ("Decision Conventions v1",), "decision")
    def query_only(graph):
        generate.one(graph, KFW.LocalNote, generate.SCO.path)
        return model

    query_only(graph)
    plan = generate.plan_decision_contract(product, str(product), model, endpoint, graph)
    report = json.loads(dict(plan.outputs)[Path("generated/processing-report.json")])
    entry = statement(report, KFW.LocalNote, generate.SCO.path)
    assert entry["semanticStatus"] == "unassigned"
    assert all(use["kind"] == "structural" for use in entry["uses"])


def test_failed_normalization_discards_its_successful_nested_records(product):
    source = product / "specs/decision_contract.ttl"
    graph = Graph().parse(source, format="turtle")
    graph.remove((KFW.RuleNaturalPerson2026_07, generate.SDO.sourceCitation, None))
    graph.serialize(source, format="turtle")
    traced = generate.load_contract_graph(product, processing_report=True)
    with pytest.raises(ValueError, match="Expected exactly one"):
        generate.read_decision_model(product, traced)
    assert traced.interpretations == []
    assert traced.frames == []


@pytest.mark.parametrize("failure", ["projection", "json-type", "html"])
def test_report_failure_preserves_all_previous_artifacts(product, monkeypatch, failure):
    compile_product(product)
    before = snapshot(product)
    graph = generate.load_contract_graph(product, processing_report=True)
    model = generate.read_decision_model(product, graph)
    endpoint = generate.read_http_endpoint(graph)
    if failure == "projection":
        original = generate.build_decision_contract

        def inconsistent_projection(model):
            contract = original(model)
            contract["scope_note"] = "not the normalized authored scope"
            return contract

        monkeypatch.setattr(generate, "build_decision_contract", inconsistent_projection)
    elif failure == "json-type":
        original = generate.build_http_openapi

        def inconsistent_json_type(endpoint):
            document = original(endpoint)
            document["paths"][endpoint.path]["post"]["requestBody"]["required"] = 1
            return document

        monkeypatch.setattr(generate, "build_http_openapi", inconsistent_json_type)
    else:
        def fail_html(report):
            raise ValueError("injected report rendering failure")
        monkeypatch.setattr(generate, "render_processing_report", fail_html)
    with pytest.raises(ValueError, match="matching rendered destination|injected report rendering failure"):
        generate.generate_decision_contract(product, str(product), model, endpoint, graph)
    assert snapshot(product) == before


def test_report_works_in_the_independent_compiler_and_keeps_catalog_identity(product, tmp_path):
    compile_product(product)
    reference = read_report(product)
    standalone = tmp_path / "independent/src/compiler.py"
    standalone.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "products/spec_compiler/src/spec_compiler.py", standalone)
    compile_product(product, script=standalone, cwd=tmp_path)
    actual = read_report(product)
    assert actual["compiler"]["bootstrapGeneration"] == 1
    assert actual["compiler"]["sourceSha256"] == sha256(standalone.read_text(encoding="utf-8").encode()).hexdigest()
    assert actual["catalog"] == reference["catalog"]
    assert actual["statements"] == reference["statements"]
    assert not (standalone.parents[1] / "ontology").exists()


def test_uncovered_profile_is_explicit_and_cleans_stale_reports(tmp_path):
    product = tmp_path / "sql-pilot"
    shutil.copytree(ROOT / "products/sql_api_example/specs", product / "specs")
    (product / "generated").mkdir()
    for suffix in ("json", "html"):
        (product / f"generated/processing-report.{suffix}").write_text("stale report", encoding="utf-8")
    result = compile_product(product)
    assert "profile http-sql is not covered" in result.stdout
    assert not (product / "generated/processing-report.json").exists()
    assert not (product / "generated/processing-report.html").exists()

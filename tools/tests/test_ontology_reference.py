from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDFS

from tools import build_ontology_site as builder
from tools import build_documentation_site as complete
from tools import ontology_reference as reference
from tools.documentation_site import DocumentParser


SOURCE = '''@prefix ex: <https://example.net/vocab/#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:Thing a owl:Class; rdfs:label "Ding"@de, "Thing"@en;
 rdfs:comment "<script>alert('x')</script>"@de;
 ex:list ("second" "first"); ex:constraint [ex:min 1; ex:note "Zeile\\nZwei"] .
ex:description a owl:DatatypeProperty; rdfs:domain ex:Thing; rdfs:range xsd:string .
'''


def write(graph, output):
    reference.write_reference(graph, output, title="Test", namespace="https://example.net/vocab/#",
                              graph_key="contract", site_root_href="../", publications={})


@pytest.mark.parametrize(("filename", "format"), [("ontology.ttl", "turtle"), ("ontology.nt", "nt"),
                                                   ("ontology.owl", "xml"), ("ontology.jsonld", "json-ld")])
def test_exports_roundtrip_without_losing_lists_blank_nodes_or_literals(tmp_path, filename, format):
    graph = Graph().parse(data=SOURCE, format="turtle")
    reference.write_serializations(graph, tmp_path)
    assert isomorphic(graph, Graph().parse(tmp_path / filename, format=format))


def test_reference_is_bilingual_escaped_and_has_compatible_fragments(tmp_path):
    write(Graph().parse(data=SOURCE, format="turtle"), tmp_path)
    de = (tmp_path / "index-de.html").read_text(encoding="utf-8")
    en = (tmp_path / "index-en.html").read_text(encoding="utf-8")
    assert '<h3 id="ref-Thing">Ding</h3>' in de
    assert '<h3 id="ref-Thing">Thing</h3>' in en
    assert '&lt;script&gt;' in de and '<script>alert' not in de
    assert 'id="Thing"' in de and 'id="https://example.net/vocab/#Thing"' in de
    assert 'id="description"' in de
    parsed = DocumentParser()
    parsed.feed(de)
    assert not parsed.duplicates
    assert (tmp_path / "index.html").read_bytes() == (tmp_path / "index-de.html").read_bytes()
    assert 'ontology=contract' in (tmp_path / "webvowl/index.html").read_text(encoding="utf-8")


def test_isomorphic_input_order_and_blank_names_produce_identical_files(tmp_path):
    graph = Graph().parse(data=SOURCE, format="turtle")
    other = Graph().parse(data=graph.serialize(format="turtle"), format="turtle")
    write(graph, tmp_path / "one")
    write(other, tmp_path / "two")
    first = {p.relative_to(tmp_path / "one"): p.read_bytes() for p in (tmp_path / "one").rglob("*") if p.is_file()}
    second = {p.relative_to(tmp_path / "two"): p.read_bytes() for p in (tmp_path / "two").rglob("*") if p.is_file()}
    assert first == second


def test_exports_are_independent_of_python_hash_seed(tmp_path):
    command = [sys.executable, "-c", (
        "from pathlib import Path; from rdflib import Graph; from tools.ontology_reference import write_reference;"
        f"g=Graph().parse(data={SOURCE!r},format='turtle');"
        "import sys; write_reference(g,Path(sys.argv[1]),title='Test',namespace='https://example.net/vocab/#',"
        "graph_key='contract',site_root_href='../',publications={})"
    )]
    results = []
    for seed in ("1", "99"):
        output = tmp_path / seed
        subprocess.run(command + [str(output)], cwd=builder.ROOT,
                       env={**os.environ, "PYTHONHASHSEED": seed}, check=True, capture_output=True)
        results.append({p.relative_to(output): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in output.rglob("*") if p.is_file()})
    assert results[0] == results[1]


def test_unsafe_rdf_iris_are_not_clickable(tmp_path):
    graph = Graph().parse(data=SOURCE, format="turtle")
    graph.add((URIRef("https://example.net/vocab/#Thing"), RDFS.seeAlso, URIRef("javascript:alert(1)")))
    write(graph, tmp_path)
    assert 'href="javascript:' not in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_complete_ontology_build_needs_no_java_and_keeps_sources_authoritative(tmp_path, monkeypatch):
    output = tmp_path / "build" / "site"
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    # Input declarations still use the real, versioned reference product.
    products = Path(__file__).resolve().parents[2] / "products"
    import shutil
    shutil.copytree(products, tmp_path / "products", ignore=shutil.ignore_patterns('.venv', '__pycache__'))
    monkeypatch.setattr(builder, "build_relationship_graph", lambda graph: None)
    with builder.site_output(output):
        builder.build_site()
    for path in ("ontology", "ontology/decision", "ontology/funding", "ontology/cloud", "examples/sql-api"):
        assert (output / path / "index-de.html").is_file()
        assert (output / path / "index-en.html").is_file()
        assert (output / path / "webvowl/index.html").is_file()
        assert not (output / path / "webvowl/data/ontology.json").exists()
    for source, _, _ in builder.ONTOLOGY_PUBLICATIONS:
        folder = {builder.ONTOLOGY: "ontology", builder.DECISION_ONTOLOGY: "ontology/decision",
                  builder.FUNDING_ONTOLOGY: "ontology/funding", builder.CLOUD_ONTOLOGY: "ontology/cloud"}[source]
        assert isomorphic(Graph().parse(source), Graph().parse(output / folder / "ontology.ttl"))
    sql = Graph().parse(output / "resources/sql-api/resources.ttl")
    projected = Graph().parse(output / "examples/sql-api/ontology.ttl")
    assert (builder.ARTICLE.GetArticleEndpoint, RDF.type, Namespace('http://www.w3.org/2002/07/owl#').Class) not in sql
    assert len(projected) > len(sql)


def test_publish_removes_only_stale_derived_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(complete.site, "ROOT", tmp_path)
    destination = tmp_path / "build" / "ontology-site"
    destination.mkdir(parents=True)
    stale = destination / "webvowl.js"
    stale.write_text("obsolete")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "index.html").write_text("new")
    complete.publish_candidate(candidate, destination)
    assert not stale.exists()
    assert (destination / "index.html").read_text() == "new"
    outside = tmp_path / "authored"
    outside.mkdir()
    (outside / "important.txt").write_text("keep")
    with pytest.raises(ValueError, match="Refusing"):
        complete.publish_candidate(candidate, outside)
    with pytest.raises(ValueError, match="Refusing"):
        complete.publish_candidate(candidate, tmp_path / "build")
    assert (outside / "important.txt").read_text() == "keep"


def test_failed_reference_build_preserves_last_good_site(tmp_path, monkeypatch):
    import argparse
    monkeypatch.setattr(complete.site, "ROOT", tmp_path)
    monkeypatch.setattr(complete.site, "validate_sources", lambda: None)
    monkeypatch.setattr(complete.ontology, "validate_publication_sources", lambda: None)
    destination = tmp_path / "build" / "ontology-site"
    destination.mkdir(parents=True)
    (destination / "index.html").write_text("last good")
    monkeypatch.setattr(complete.site, "OUTPUT", destination)

    def fail():
        raise ValueError("invalid reference")

    monkeypatch.setattr(complete.ontology, "build_site", fail)
    with pytest.raises(ValueError, match="invalid reference"):
        complete.build(argparse.Namespace(validate_only=False, quick=True))
    assert (destination / "index.html").read_text() == "last good"
    assert complete.site.OUTPUT == destination

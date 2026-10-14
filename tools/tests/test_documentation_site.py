from __future__ import annotations

import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import threading

import httpx
import pytest

from tools import documentation_site as site
from tools.preview_documentation import PreviewState, handler_for, source_snapshot


@pytest.mark.parametrize(("route", "target", "expected"), [
    ("", "architecture/", "architecture/"),
    ("architecture/", "", "../"),
    ("decisions/0001.html", "ontologies/?ontology=funding#term", "../ontologies/?ontology=funding#term"),
    ("architecture/", "architecture/#scope", "./#scope"),
    ("architecture/", "https://example.org/", "https://example.org/"),
])
def test_links_are_relative_to_the_site_not_the_domain_root(route, target, expected):
    assert site.relative_url(route, target) == expected


def html_source(route="", body='<h1 id="overview">Überblick</h1>'):
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="doc-route" content="{route}"><title>Test</title></head>'
            f'<body><main id="content">{body}</main></body></html>')


@pytest.fixture
def website(tmp_path, monkeypatch):
    sources = tmp_path / "docs"
    sources.mkdir()
    (sources / "assets").mkdir()
    (sources / "diagrams").mkdir()
    (sources / "assets" / "site.css").write_text("body{}", encoding="utf-8")
    (sources / "assets" / "site.js").write_text("void 0;", encoding="utf-8")
    (sources / "index.html").write_text(html_source(), encoding="utf-8")
    output = tmp_path / "output"
    (output / "ontologies").mkdir(parents=True)
    payload = [{"key": "funding", "title": "Funding Domain Ontology", "nodes": [
        {"id": "https://example.org/#Grant", "label": "Förderung", "labelEn": "Grant", "comment": "Test"}],
        "properties": [{"label": "Betrag", "labelEn": "Amount", "name": "amount", "iri": "https://example.org/#amount"}]}]
    (output / "ontologies" / "index.html").write_text(
        html_source("ontologies/", '<h1>Graph</h1>') .replace('</body>',
            '<script type="application/json" id="ontology-data">' + json.dumps(payload) + '</script></body>'), encoding="utf-8")
    monkeypatch.setattr(site, "ROOT", tmp_path)
    monkeypatch.setattr(site, "SOURCES", sources)
    monkeypatch.setattr(site, "OUTPUT", output)
    monkeypatch.setattr(site, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(site, "NAVIGATION", (("", "Überblick"), ("ontologies/", "Ontologien")))
    return sources, output


def test_sources_fail_on_broken_links_anchors_and_duplicate_routes(website):
    sources, _ = website
    (sources / "index.html").write_text(html_source(body='<h1>Test</h1><a href="missing.html">Missing</a>'), encoding="utf-8")
    with pytest.raises(ValueError, match="source link is missing"):
        site.validate_sources(render_diagrams=False)
    (sources / "index.html").write_text(html_source(body='<h1>Test</h1><a href="#missing">Missing</a>'), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing local anchor"):
        site.validate_sources(render_diagrams=False)
    (sources / "other.html").write_text(html_source(), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate documentation route"):
        site.read_documents()


def test_composition_is_byte_identical_and_does_not_duplicate_the_graph_shell(website):
    _, output = website
    site.compose_site()
    first = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    site.compose_site()
    second = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    assert first == second
    graph = (output / "ontologies" / "index.html").read_text(encoding="utf-8")
    assert graph.count('class="site-header"') == 1
    entries = json.loads((output / "assets" / "search-index.json").read_text(encoding="utf-8"))
    assert any(entry["category"] == "Ontologie" and "&term=https%3A" in entry["url"] for entry in entries)
    assert any(entry["category"] == "Property" and "&q=amount" in entry["url"] for entry in entries)


def test_invalid_diagram_does_not_replace_last_good_document(website):
    sources, output = website
    site.compose_site()
    previous = (output / "index.html").read_bytes()
    (sources / "diagrams" / "broken.json").write_text("not JSON", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        site.compose_site()
    assert (output / "index.html").read_bytes() == previous


def test_invalid_candidate_navigation_is_rejected_before_any_live_file_changes(website, monkeypatch):
    _, output = website
    site.compose_site()
    previous = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    monkeypatch.setattr(site, "NAVIGATION", (("", "Überblick"), ("missing/", "Invalid")))
    with pytest.raises(ValueError, match="Broken published link"):
        site.compose_site()
    assert {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()} == previous


def test_published_validator_rejects_missing_search_target(website):
    _, output = website
    site.compose_site()
    index = output / "assets" / "search-index.json"
    index.write_text(json.dumps([{"url": "missing.html"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Broken published link"):
        site.validate_published_links()


@pytest.mark.skipif(not shutil.which("node"), reason="Archify delivery requires Node")
def test_cached_diagram_is_reverified_after_artifact_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "CACHE", tmp_path)
    model = site.SOURCES / "diagrams" / "compile-contracts.json"
    artifact, receipt = site.render_diagram(model, "test-renderer-pin")
    original = artifact.read_bytes()
    assert receipt["ok"] and receipt["validation"]["checksPassed"] == 9
    assert receipt["validation"]["errors"] == receipt["validation"]["warnings"] == 0
    artifact.write_text("tampered", encoding="utf-8")
    repaired, second = site.render_diagram(model, "test-renderer-pin")
    assert repaired.read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == second["artifact"]["sha256"]


def test_preview_failure_retains_version_and_exposes_error():
    state = PreviewState()
    assert state.rebuild([sys.executable, "-c", "print('valid')"])
    previous = state.status()["version"]
    assert not state.rebuild([sys.executable, "-c", "raise SystemExit('invalid model')"])
    assert state.status()["version"] == previous
    assert "invalid model" in state.status()["error"]
    assert not state.status()["building"]
    assert state.rebuild([sys.executable, "-c", "print('fixed')"])
    assert state.status()["version"] == previous + 1
    assert not state.status()["error"]


def test_preview_serves_the_prefix_and_injects_reload_only_into_responses(tmp_path):
    markup = html_source().replace('<body>', '<body><header class="site-header"></header>')
    page = tmp_path / "index.html"
    page.write_text(markup, encoding="utf-8")
    state = PreviewState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(state, "/spec-compiler/", tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        response = httpx.get(base + "/spec-compiler/")
        assert response.status_code == 200
        assert 'data-local-preview' in response.text
        assert '/spec-compiler/__preview/status' in response.text
        assert response.headers['cache-control'] == 'no-store'
        assert httpx.get(base + "/spec-compiler/__preview/status").json() == state.status()
        redirect = httpx.get(base + "/spec-compiler?ontology=funding", follow_redirects=False)
        assert redirect.status_code == 404  # Outside the configured prefix.
        (tmp_path / "architecture").mkdir()
        (tmp_path / "architecture" / "index.html").write_text(markup, encoding="utf-8")
        redirect = httpx.get(base + "/spec-compiler/architecture?view=context", follow_redirects=False)
        assert redirect.status_code == 301
        assert redirect.headers["location"] == "/spec-compiler/architecture/?view=context"
        assert httpx.get(base + "/").status_code == 404
        assert httpx.get(base + "/spec-compiler/%2e%2e/outside.html").status_code == 403
        assert page.read_text(encoding="utf-8") == markup
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_watcher_observes_saved_sources_but_ignores_generated_outputs(tmp_path):
    (tmp_path / "docs").mkdir()
    source = tmp_path / "docs" / "index.html"
    source.write_text("first", encoding="utf-8")
    first = source_snapshot(tmp_path)
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "index.html").write_text("output", encoding="utf-8")
    assert source_snapshot(tmp_path) == first
    source.write_text("saved change", encoding="utf-8")
    assert source_snapshot(tmp_path) != first


def test_build_lock_serializes_writers_and_releases_after_failure(tmp_path):
    path = tmp_path / "build.lock"
    with site.build_lock(path):
        with pytest.raises(TimeoutError, match="Another documentation build"):
            with site.build_lock(path, timeout=0.1):
                pytest.fail("A second writer acquired the same lock")
    with pytest.raises(RuntimeError):
        with site.build_lock(path):
            raise RuntimeError("failed candidate")
    with site.build_lock(path, timeout=0.1):
        pass

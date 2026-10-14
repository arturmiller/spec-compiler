from __future__ import annotations

import pytest

from tools import documentation_site as site
from tools import tutorial_workspace as tutorial


def test_glossary_links_only_first_prose_occurrence_per_section():
    linker = site.GlossaryLinker([{"title": "Product Bundle", "id": "product-bundle"}], "../reference/glossary.html")
    linker.feed('<html><body><main><h2>Product Bundle</h2><p>Product Bundle, Product Bundle.</p>'
                '<pre>Product Bundle</pre><h2>Second</h2><p>Product Bundle.</p></main></body></html>')
    result = ''.join(linker.parts)
    assert result.count('class="glossary-link"') == 2
    assert '<pre>Product Bundle</pre>' in result
    assert '<h2>Product Bundle</h2>' in result


def test_existing_manual_glossary_link_prevents_a_duplicate():
    linker = site.GlossaryLinker([{"title": "Spec", "id": "spec"}], "glossary.html")
    linker.feed('<main><p><a href="glossary.html#spec">Spec</a> and Spec.</p></main>')
    assert 'class="glossary-link"' not in ''.join(linker.parts)


def test_glossary_parser_has_individual_search_definitions():
    parser = site.GlossaryParser()
    parser.feed('<dl><dt id="spec" data-term="Spec">Spezifikation</dt><dd>Explicit <strong>statement</strong>.</dd></dl>')
    assert parser.entries == [{"id": "spec", "title": "Spec", "text": "Explicit statement ."}]


def test_compiler_vocabulary_is_defined_searchable_and_linked_at_the_introduction():
    entries = {entry['id']: entry for entry in site.glossary_entries()}
    expected = {'reader': 'Reader', 'renderer': 'Renderer',
                'compiler-profile': 'Verarbeitungsprofil', 'decision-profile': 'Decision-Profil',
                'sql-openapi-profile': 'SQL/OpenAPI-Profil',
                'compiler-product-profile': 'Profil für Compilerprodukte'}
    for identifier, title in expected.items():
        assert entries[identifier]['title'] == title
        assert entries[identifier]['text']
    assert 'Compilerprofil' in entries['compiler-profile']['text']
    assert 'Diagrammrenderer' in entries['renderer']['text']
    compiler = site.DocumentParser()
    compiler.feed((site.SOURCES / 'compiler/index.html').read_text(encoding='utf-8'))
    for identifier in ('reader', 'renderer', 'compiler-profile', 'decision-profile'):
        assert ('a', '../glossary.html#' + identifier) in compiler.links
    profiles = site.DocumentParser()
    profiles.feed((site.SOURCES / 'reference/profiles.html').read_text(encoding='utf-8'))
    assert ('a', '../glossary.html#compiler-product-profile') in profiles.links
    site.validate_sources(render_diagrams=False)


def test_legacy_route_aliases_are_unique_and_preserve_state(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "SOURCES", tmp_path)
    source = '<html><head><meta name="doc-route" content="compiler/"><meta name="doc-alias" content="workflows/"><title>Test</title></head><body><main><h1>Test</h1></main></body></html>'
    (tmp_path / "index.html").write_text(source, encoding="utf-8")
    assert site.read_documents()[0].parsed.aliases == ["workflows/"]
    redirect = site.redirect_page("workflows/", "compiler/")
    assert 'target.search=location.search' in redirect and 'target.hash=location.hash' in redirect
    (tmp_path / "other.html").write_text(source.replace('content="compiler/"', 'content="other/"'), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate documentation route or alias"):
        site.read_documents()


def test_tutorial_copy_is_fresh_and_never_overwrites_a_reference(tmp_path):
    source = tmp_path / "products/sql_api_example"
    source.mkdir(parents=True)
    (source / "app.py").write_text("reference")
    (source / "specs").mkdir()
    (source / "specs/contract.ttl").write_text("explicit spec")
    for ignored in (".venv", "generated", "tests"):
        (source / ignored).mkdir()
        (source / ignored / "artifact").write_text("not authored")
    created = tutorial.create("sql-api", tmp_path)
    assert created == tmp_path / "products/tutorial_sql_api_example"
    assert (created / "app.py").read_text() == "reference"
    assert (created / "specs/contract.ttl").read_text() == "explicit spec"
    assert not (created / "generated").exists() and not (created / "tests").exists()
    (created / "app.py").write_text("learner change")
    with pytest.raises(ValueError, match="Nothing was overwritten"):
        tutorial.create("sql-api", tmp_path)
    assert (created / "app.py").read_text() == "learner change"
    assert (source / "app.py").read_text() == "reference"

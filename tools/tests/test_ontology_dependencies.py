from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Graph, RDF, URIRef
from rdflib.namespace import OWL

from tools import build_ontology_site as builder
from tools import documentation_site as site
from tools import ontology_dependencies as dependencies
from tools import ontology_reference as reference
from tools.generate import CCO, SCO, SQLO, LEGACY_COMPILER_TERMS, reject_legacy_compiler_terms


def test_compiler_terms_have_one_new_owner_and_no_old_declarations():
    compiler = Graph().parse(builder.COMPILER_ONTOLOGY)
    contract = Graph().parse(builder.ONTOLOGY)
    subjects = {str(term)[len(str(CCO)):] for term in compiler.subjects()
                if isinstance(term, URIRef) and str(term).startswith(str(CCO))}
    assert subjects == set(LEGACY_COMPILER_TERMS)
    assert all(not list(contract.triples((SCO[term], None, None))) for term in subjects)
    assert (CCO.TransformationContract, RDF.type, OWL.Class) in compiler
    assert list(contract.triples((SCO.HttpEndpoint, None, None)))
    assert not list(contract.triples((SCO.SqlTable, None, None)))
    assert list(Graph().parse(builder.SQL_ONTOLOGY).triples((SQLO.SqlTable, None, None)))
    authored = Graph().parse(builder.ROOT / 'products/spec_compiler/specs/compiler_contract.ttl')
    reject_legacy_compiler_terms(authored)
    authored.add((URIRef('urn:test:compiler'), RDF.type, SCO.TransformationContract))
    with pytest.raises(ValueError, match='sco:TransformationContract -> cco:TransformationContract'):
        reject_legacy_compiler_terms(authored)


def test_project_dependencies_and_independence_are_derived_from_rdf():
    analysis = dependencies.read_dependencies(builder.ONTOLOGY_PUBLICATIONS)
    assert {node['key'] for node in analysis['nodes']} == {'contract', 'sql', 'decision-protocol', 'compiler', 'decision', 'funding', 'cloud'}
    assert {(edge['from'], edge['to']) for edge in analysis['dependencies']} == {
        ('decision-protocol', 'decision'), ('funding', 'decision'), ('cloud', 'decision')}
    assert all(edge['imports'] and edge['terms'] and edge['statements'] for edge in analysis['dependencies'])
    assert analysis['noProjectDependencies'] == ['compiler', 'contract', 'decision', 'sql']
    markup = dependencies.dependency_tables(analysis)
    assert 'data-source="funding" data-target="cloud" data-dependency="none"' in markup
    assert 'data-source="cloud" data-target="funding" data-dependency="none"' in markup
    assert 'data-source="decision" data-target="contract" data-dependency="none"' in markup
    assert 'data-source="compiler" data-target="decision" data-dependency="none"' in markup


def fixture_ontologies(tmp_path):
    base = 'https://arturmiller.github.io/spec-compiler/ontology/'
    publications = []
    for name, extra in [('alpha', f'owl:imports <{base}beta/> ;'), ('beta', f'owl:imports <{base}gamma/> ;'), ('gamma', '')]:
        source = tmp_path / (name + '.ttl')
        source.write_text(f'''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<{base}{name}/> a owl:Ontology ; {extra} dcterms:title "{name}"@en, "{name}"@de .
<{base}{name}/#Term> a owl:Class .
''' + (f'<{base}beta/#Term> rdfs:subClassOf [ owl:someValuesFrom <{base}gamma/#Term> ] .'
       if name == 'beta' else ''), encoding='utf-8')
        publications.append((source, base + name + '/', base + name + '/#'))
    return publications


def test_import_only_term_use_transitivity_and_blank_node_determinism(tmp_path):
    publications = fixture_ontologies(tmp_path)
    first = dependencies.read_dependencies(publications)
    assert first == dependencies.read_dependencies(publications)
    assert first['transitive']['alpha'] == ['beta', 'gamma']
    assert first['transitive']['gamma'] == []
    a, b = first['dependencies']
    assert a['imports'] and not a['terms']
    assert len(a['statements']) == 1 and a['statements'][0][1] == str(OWL.imports)
    assert b['imports'] and b['terms']
    assert 'data-source="alpha" data-target="gamma" data-dependency="indirect"' in dependencies.dependency_tables(first)


def test_unknown_project_import_is_rejected_without_remote_loading(tmp_path):
    publications = fixture_ontologies(tmp_path)
    source = publications[0][0]
    source.write_text(source.read_text().replace('ontology/beta/>', 'ontology/not-registered/>'))
    with pytest.raises(ValueError, match='Unknown ontology import'):
        dependencies.read_dependencies(publications)


def test_cycles_are_rejected_even_if_they_only_consist_of_imports(tmp_path):
    publications = fixture_ontologies(tmp_path)
    base = 'https://arturmiller.github.io/spec-compiler/ontology/'
    gamma = publications[2][0]
    with gamma.open('a', encoding='utf-8') as stream:
        stream.write(f'\n<{base}gamma/> owl:imports <{base}alpha/> .\n')
    with pytest.raises(ValueError, match='Cyclic ontology imports:.*alpha/.*beta/.*gamma/.*alpha/'):
        dependencies.read_dependencies(publications)


def test_diagram_relationships_come_from_rdf_not_authored_connections():
    analysis = dependencies.read_dependencies(builder.ONTOLOGY_PUBLICATIONS)
    layout = json.loads((site.SOURCES / 'diagrams/ontology-dependencies.json').read_text(encoding='utf-8'))
    layout['connections'].append({'id': 'compiler-to-cloud', 'from': 'compiler', 'to': 'cloud', 'label': 'invented'})
    model = dependencies.dependency_diagram(layout, analysis)
    assert {(edge['from'], edge['to']) for edge in model['connections']} == {
        (edge['from'], edge['to']) for edge in analysis['dependencies']}
    assert next(edge for edge in model['connections'] if edge['from'] == 'decision-protocol')['labelDy'] == 24
    changed = json.loads(json.dumps(analysis))
    changed['dependencies'].append({'from': 'compiler', 'to': 'cloud', 'imports': False, 'terms': ['urn:term']})
    assert any(edge['from'] == 'compiler' and edge['to'] == 'cloud'
               for edge in dependencies.dependency_diagram(layout, changed)['connections'])


def test_previous_term_links_survive_without_rdf_alias_declarations(tmp_path):
    contract = Graph().parse(builder.ONTOLOGY)
    reference.write_reference(contract, tmp_path, title='HTTP/SQL', namespace=str(SCO), graph_key='contract',
                              site_root_href='../', publications={str(SCO): 'ontology/', str(CCO): 'ontology/compiler/'},
                              moved_terms=builder.compiler_term_migrations())
    for language in ('de', 'en'):
        markup = (tmp_path / f'index-{language}.html').read_text(encoding='utf-8')
        assert 'location.replace(target.href)' in markup
        assert f'ontology/compiler/index-{language}.html#TransformationContract' in markup
        parser = site.DocumentParser()
        parser.feed(markup)
        assert 'TransformationContract' in parser.ids and str(SCO.TransformationContract) in parser.ids
    exported = Graph().parse(tmp_path / 'ontology.ttl')
    assert not list(exported.triples((SCO.TransformationContract, None, None)))

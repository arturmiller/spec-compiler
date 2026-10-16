from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, RDFS, VANN

from tools import build_ontology_site as builder
from tools.ontology_relationship_graph import dependency_dataset
from tools.generate import (DPO, SCO, SQLO, load_contract_graph, ontology_module,
                            validate_ontology_modules, validate_product_ontology)


def module(name, role='reusable'):
    base = 'https://arturmiller.github.io/spec-compiler/'
    iri = base + ('resources/' if role == 'product' else 'ontology/') + name + '/'
    graph = Graph()
    graph.add((URIRef(iri), RDF.type, OWL.Ontology))
    graph.add((URIRef(iri), VANN.preferredNamespaceUri, Literal(iri + '#')))
    graph.add((URIRef(iri + '#Term'), RDF.type, OWL.Class))
    return ontology_module(graph, role=role, source=name)


def imports(source, target):
    source['graph'].add((URIRef(source['iri']), OWL.imports, URIRef(target['iri'])))


def uses(source, target):
    source['graph'].add((URIRef(source['namespace'] + 'Term'), RDFS.subClassOf,
                         URIRef(target['namespace'] + 'Term')))


def test_project_catalog_has_seven_reusable_and_four_terminal_modules():
    analysis = builder.dependency_analysis()
    products = {node['key'] for node in analysis['nodes'] if node['role'] == 'product'}
    assert len(products) == 4
    assert len(analysis['nodes']) == 11
    assert not any(edge['to'] in products for edge in analysis['dependencies'])
    assert {(edge['from'], edge['to']) for edge in analysis['dependencies'] if edge['from'] not in products} == {
        ('cloud', 'decision'), ('funding', 'decision'), ('decision-protocol', 'decision')}
    assert not any(edge['from'] in ('contract', 'sql', 'compiler') for edge in analysis['dependencies'])


def test_dependency_layout_is_stable_and_routes_avoid_unrelated_nodes():
    analysis = builder.dependency_analysis()
    graph = dependency_dataset(analysis)
    assert graph == dependency_dataset(analysis)
    positions = graph['positions']
    for edge in graph['edges']:
        source, target = positions[edge['source']], positions[edge['target']]
        assert 20 <= edge['turn'] <= 100
        turn = source['x'] + 105 + edge['turn']
        points = [(source['x'] + 105, source['y']), (turn, source['y']),
                  (turn, target['y']), (target['x'] - 105, target['y'])]
        for identity, node in positions.items():
            if identity in (edge['source'], edge['target']):
                continue
            left, right = node['x'] - 105, node['x'] + 105
            top, bottom = node['y'] - 34, node['y'] + 34
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                overlaps = ((top < y1 < bottom and max(left, min(x1, x2)) < min(right, max(x1, x2)))
                            if y1 == y2 else
                            (left < x1 < right and max(top, min(y1, y2)) < min(bottom, max(y1, y2))))
                assert not overlaps, (edge, identity)
    for index, first in enumerate(graph['edges']):
        for second in graph['edges'][index + 1:]:
            a, b = positions[first['source']], positions[second['source']]
            if a['x'] != b['x']:
                continue
            first_span = sorted([a['y'], positions[first['target']]['y']])
            second_span = sorted([b['y'], positions[second['target']]['y']])
            if max(first_span[0], second_span[0]) <= min(first_span[1], second_span[1]):
                assert first['turn'] != second['turn']


def test_foreign_term_requires_direct_import_even_when_available_transitively():
    a, b, c = module('alpha'), module('beta'), module('gamma')
    imports(a, b)
    imports(b, c)
    uses(a, c)
    with pytest.raises(ValueError, match='Missing explicit owl:imports.*alpha/.*gamma/'):
        validate_ontology_modules([a, b, c])
    imports(a, c)
    validate_ontology_modules([a, b, c])


@pytest.mark.parametrize('length', [1, 2, 3])
def test_all_cycles_fail_with_a_directed_path(length):
    modules = [module('cycle-' + str(index)) for index in range(length)]
    for index, source in enumerate(modules):
        imports(source, modules[(index + 1) % length])
    with pytest.raises(ValueError, match='Cyclic ontology imports:.*cycle-0/.*cycle-0/'):
        validate_ontology_modules(modules)


@pytest.mark.parametrize('source_role', ['reusable', 'product'])
def test_nothing_may_import_a_terminal_product_specification(source_role):
    a, product = module('source', source_role), module('terminal', 'product')
    imports(a, product)
    with pytest.raises(ValueError, match='Terminal product specification cannot be imported'):
        validate_ontology_modules([a, product])


@pytest.mark.parametrize('source_role', ['reusable', 'product'])
def test_term_use_cannot_bypass_terminal_product_boundary(source_role):
    a, product = module('source', source_role), module('terminal', 'product')
    uses(a, product)
    with pytest.raises(ValueError, match='Terminal product specification cannot be reused'):
        validate_ontology_modules([a, product])


def test_unknown_and_remote_imports_are_rejected_without_fetching():
    a = module('alpha')
    a['graph'].add((URIRef(a['iri']), OWL.imports, URIRef('https://example.invalid/ontology/')))
    with pytest.raises(ValueError, match='Unknown ontology import'):
        validate_ontology_modules([a])


def test_unused_prefixes_literals_and_test_fixture_paths_are_not_imports():
    a, b = module('alpha'), module('beta', 'product')
    a['graph'].bind('unused', b['namespace'])
    a['graph'].add((URIRef(a['iri']), DCTERMS.description, Literal(b['namespace'] + 'Term')))
    a['graph'].add((URIRef(a['iri']), URIRef('urn:test:fixture'), Literal('../beta')))
    validate_ontology_modules([a, b])


def test_term_ownership_and_definition_are_checked():
    a, b = module('alpha'), module('beta')
    imports(a, b)
    a['graph'].add((URIRef(b['namespace'] + 'Term'), RDFS.label, Literal('Shadow definition')))
    with pytest.raises(ValueError, match='Foreign ontology term'):
        validate_ontology_modules([a, b])
    a['graph'].remove((None, RDFS.label, None))
    a['graph'].add((URIRef(a['namespace'] + 'Term'), RDFS.subClassOf, URIRef(b['namespace'] + 'Typo')))
    with pytest.raises(ValueError, match='Undefined ontology term'):
        validate_ontology_modules([a, b])


def test_product_header_and_unique_namespace_are_required():
    with pytest.raises(ValueError, match='exactly one named owl:Ontology'):
        ontology_module(Graph(), role='product', source='missing header')
    a, duplicate = module('alpha'), module('alpha')
    with pytest.raises(ValueError, match='Duplicate ontology identity'):
        validate_ontology_modules([a, duplicate])


def test_compiler_rejects_missing_imports_and_unknown_product_references():
    source = builder.ROOT / 'products/sql_api_example'
    graph = load_contract_graph(source)
    identity = next(graph.subjects(RDF.type, OWL.Ontology))
    graph.remove((identity, OWL.imports, URIRef(str(SQLO).rstrip('#'))))
    with pytest.raises(ValueError, match='Missing explicit owl:imports'):
        validate_product_ontology(graph)
    graph = load_contract_graph(source)
    graph.add((identity, DCTERMS.relation, URIRef('https://arturmiller.github.io/spec-compiler/resources/other/#Private')))
    with pytest.raises(ValueError, match='Unknown or foreign product/ontology resource'):
        validate_product_ontology(graph)


@pytest.mark.parametrize('term', ['SqlTable', 'DecisionProtocolV1'])
def test_old_separated_iris_fail_explicitly(term):
    graph = load_contract_graph(builder.ROOT / 'products/sql_api_example')
    graph.add((URIRef('urn:subject'), RDF.type, SCO[term]))
    with pytest.raises(ValueError, match='migrate separated vocabulary terms'):
        validate_product_ontology(graph)


def test_imported_definitions_do_not_become_authored_product_requirements():
    graph = load_contract_graph(builder.ROOT / 'products/kfw_458_eligibility')
    assert (DPO.DecisionProtocolV1, RDF.type, OWL.NamedIndividual) not in graph
    assert list(graph.subjects(DCTERMS.conformsTo, DPO.DecisionProtocolV1))


def test_bootstrapped_compiler_carries_a_standalone_local_catalog(tmp_path):
    script = tmp_path / 'standalone/src/compiler.py'
    script.parent.mkdir(parents=True)
    shutil.copyfile(builder.ROOT / 'products/spec_compiler/src/spec_compiler.py', script)
    target = tmp_path / 'input'
    shutil.copytree(builder.ROOT / 'products/sql_api_example/specs', target / 'specs')
    result = subprocess.run([sys.executable, str(script), '--product', str(target)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / 'generated/expected-openapi.json').is_file()
    assert not (script.parents[1] / 'ontology').exists()

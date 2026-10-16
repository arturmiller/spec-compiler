"""Direct vocabulary context must not become inferred facts or recursive imports."""
from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace, RDF
from rdflib.namespace import DCTERMS, OWL, RDFS, SH

from tools import build_ontology_site as site
from tools.generate import CCO, load_contract_graph
from tools.ontology_relationship_graph import build_dataset


EX = Namespace('https://example.net/local/#')
OTHER = Namespace('https://example.net/other/#')


def dataset(graph, **kwargs):
    return build_dataset(graph, key='test', title='Test', namespace=str(EX),
                         source_href='ontology.ttl', reference_href='./', **kwargs)


def test_catalog_supplies_labels_and_links_but_never_recursive_edges_or_mutations():
    graph = Graph()
    graph.add((EX.Child, RDF.type, OWL.Class))
    graph.add((EX.Child, RDFS.subClassOf, OTHER.Parent))
    catalog = Graph()
    catalog.add((OTHER.Parent, RDF.type, OWL.Class))
    catalog.add((OTHER.Parent, RDFS.label, Literal('Elternklasse', lang='de')))
    catalog.add((OTHER.Parent, RDFS.subClassOf, OTHER.Grandparent))
    original, original_catalog = set(graph), set(catalog)
    result = dataset(graph, context_graph=catalog, publications={str(OTHER): {
        'title': 'Other vocabulary', 'referenceHref': '../other/'}})
    assert {node['id'] for node in result['nodes']} == {str(EX.Child), str(OTHER.Parent)}
    parent = next(node for node in result['nodes'] if node['external'])
    assert parent['label'] == 'Elternklasse'
    assert parent['referenceHref'] == '../other/index-de.html#Parent'
    assert parent['owner'] == 'Other vocabulary'
    assert len(result['edges']) == 1
    assert set(graph) == original and set(catalog) == original_catalog


def test_named_individuals_do_not_disappear_when_classes_exist_and_types_are_not_subclasses():
    graph = Graph()
    graph.add((EX.Engine, RDF.type, OWL.Class))
    graph.add((EX.SQLite, RDF.type, OWL.NamedIndividual))
    graph.add((EX.SQLite, RDF.type, EX.Engine))
    result = dataset(graph)
    assert {node['name']: node['kind'] for node in result['nodes']} == {'Engine': 'class', 'SQLite': 'individual'}
    assert result['edges'] == [{'source': str(EX.SQLite), 'target': str(EX.Engine),
                               'kind': 'type', 'label': 'ist Exemplar von', 'iri': str(RDF.type)}]


def test_local_property_can_bind_two_external_classes_without_copying_their_ontologies():
    graph = Graph()
    graph.add((EX.Protocol, RDF.type, OWL.NamedIndividual))
    graph.add((EX.Protocol, RDF.type, DCTERMS.Standard))
    graph.add((EX.implements, RDF.type, OWL.ObjectProperty))
    graph.add((EX.implements, RDFS.domain, OTHER.Application))
    graph.add((EX.implements, RDFS.range, OTHER.Contract))
    result = dataset(graph)
    assert len(result['nodes']) == 4
    assert {(edge['source'], edge['target']) for edge in result['edges']} == {
        (str(EX.Protocol), str(DCTERMS.Standard)), (str(OTHER.Application), str(OTHER.Contract))}


def test_literal_property_metadata_is_visible_but_does_not_add_datatype_nodes():
    graph = Graph().parse(data=f'''
        @prefix ex: <{EX}> . @prefix owl: <{OWL}> . @prefix rdfs: <{RDFS}> .
        ex:Thing a owl:Class .
        ex:old a owl:DatatypeProperty; owl:deprecated true; rdfs:domain ex:Thing;
          rdfs:range <http://www.w3.org/2001/XMLSchema#string>; rdfs:comment "Veraltet"@de .
    ''', format='turtle')
    result = dataset(graph)
    assert len(result['nodes']) == 1 and result['edges'] == []
    assert result['properties'][0]['deprecated'] is True
    assert result['properties'][0]['comment'] == 'Veraltet'


def test_unsafe_external_reference_is_not_clickable():
    graph = Graph()
    graph.add((EX.Thing, RDF.type, OWL.Class))
    graph.add((EX.Thing, RDFS.subClassOf, Namespace('javascript:')['alert(1)']))
    result = dataset(graph)
    assert next(node for node in result['nodes'] if node['external'])['referenceHref'] is None


@pytest.mark.parametrize(('path', 'identity', 'namespace'), site.ONTOLOGY_PUBLICATIONS)
def test_every_current_local_class_and_individual_has_explicit_visible_relationships(path, identity, namespace):
    graph = Graph().parse(path)
    result = build_dataset(graph, key=path.stem, title=path.stem, namespace=namespace,
                           source_href='', reference_href='')
    connected = {edge[end] for edge in result['edges'] for end in ('source', 'target')}
    assert {node['id'] for node in result['nodes']} == connected
    assert {str(node) for node in graph.subjects(RDF.type, OWL.NamedIndividual)} <= {
        node['id'] for node in result['nodes']}
    other = Graph().parse(data=graph.serialize(format='turtle'), format='turtle')
    assert result == build_dataset(other, key=path.stem, title=path.stem, namespace=namespace,
                                   source_href='', reference_href='')


def test_subjects_belong_to_cases_not_reusable_contracts_and_storage_stays_transport_neutral():
    funding = Graph().parse(site.FUNDING_ONTOLOGY)
    cloud = Graph().parse(site.CLOUD_ONTOLOGY)
    sql = Graph().parse(site.SQL_ONTOLOGY)
    for graph, predicate, target in [
        (funding, site.FUNDING.hasApplicant, site.FUNDING.Applicant),
        (funding, site.FUNDING.hasProject, site.FUNDING.Project),
        (cloud, site.CLOUD.hasSystem, site.CLOUD.CloudSystem),
    ]:
        assert set(graph.objects(predicate, RDFS.domain)) == {site.SDO.Case}
        assert set(graph.objects(predicate, RDFS.range)) == {target}
    assert set(funding.objects(site.FUNDING.fundingProgram, RDFS.domain)) == {site.FUNDING.ApplicantEligibilityDecision}
    assert not list(sql.objects(site.SQLO.readsFrom, RDFS.domain))
    assert (site.SQLO.SQLite, RDF.type, site.SQLO.DatabaseEngine) in sql
    assert (site.SQLO.stores, RDFS.range, SH.NodeShape) in sql


@pytest.mark.parametrize('term', ['validFixtureProduct', 'generatesArtifact'])
def test_retired_terms_remain_documented_but_product_use_is_rejected(tmp_path, term):
    graph = Graph().parse(site.COMPILER_ONTOLOGY)
    assert (CCO[term], OWL.deprecated, Literal(True)) in graph
    # A normal complete product header/import is required before profile reading.
    from shutil import copytree
    copytree(site.ROOT / 'products/spec_compiler/specs', tmp_path / 'specs')
    product = Graph().parse(data=f'''@prefix cco: <{CCO}> .
        <https://arturmiller.github.io/spec-compiler/resources/toolchain/#SpecCompilationV1>
        cco:{term} "ignored-before-retirement" .''', format='turtle')
    product.serialize(tmp_path / 'specs/retired.ttl', format='turtle')
    with pytest.raises(ValueError, match='Compiler Vocabulary Retirement v1'):
        load_contract_graph(tmp_path)

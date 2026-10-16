"""The reusable result vocabulary models existing semantics, not new wire fields."""
from __future__ import annotations

import pytest
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import DCTERMS, OWL, RDFS, XSD

from tools.build_ontology_site import DECISION_ONTOLOGY
from tools.ontology_relationship_graph import build_dataset


SDO = Namespace('https://arturmiller.github.io/spec-compiler/ontology/decision/#')


def dataset(graph):
    return build_dataset(graph, key='decision', title='Decision', namespace=str(SDO),
                         source_href='ontology.ttl', reference_href='./')


@pytest.mark.parametrize(('property_name', 'source', 'target'), [
    ('resultForContract', 'DecisionResult', 'DecisionContract'),
    ('resultRuleSetVersion', 'DecisionResult', 'RuleSetVersion'),
    ('resultOutcome', 'DecisionResult', 'DecisionOutcome'),
    ('hasConditionEvaluation', 'DecisionResult', 'ConditionEvaluation'),
    ('hasFactGap', 'DecisionResult', 'FactGap'),
    ('hasObligationEvaluation', 'DecisionResult', 'ObligationEvaluation'),
    ('nextQuestion', 'DecisionResult', 'FactQuestion'),
    ('decisiveRule', 'DecisionResult', 'Rule'),
    ('evaluatesCondition', 'ConditionEvaluation', 'Condition'),
    ('evaluatedRule', 'ConditionEvaluation', 'Rule'),
    ('missingFactForCondition', 'FactGap', 'Condition'),
    ('evaluatesObligation', 'ObligationEvaluation', 'Obligation'),
    ('obligationEvaluationStatus', 'ObligationEvaluation', 'ObligationStatus'),
])
def test_result_relationships_are_explicit_reusable_definitions(property_name, source, target):
    graph = Graph().parse(DECISION_ONTOLOGY)
    predicate = SDO[property_name]
    assert (predicate, RDF.type, OWL.ObjectProperty) in graph
    assert set(graph.objects(predicate, RDFS.domain)) == {SDO[source]}
    assert set(graph.objects(predicate, RDFS.range)) == {SDO[target]}
    assert {label.language for label in graph.objects(predicate, RDFS.label)} == {'de', 'en'}


def test_condition_state_is_distinct_from_a_boolean_fact_and_obligation_status():
    graph = Graph().parse(DECISION_ONTOLOGY)
    assert (SDO.conditionEvaluationState, RDF.type, OWL.DatatypeProperty) in graph
    assert (SDO.conditionEvaluationState, RDFS.domain, SDO.ConditionEvaluation) in graph
    assert (SDO.conditionEvaluationState, RDFS.range, XSD.string) in graph
    # Existing domains are not broadened or accidentally conjunctively extended.
    assert set(graph.objects(SDO.forCondition, RDFS.domain)) == {SDO.CaseFact}
    assert set(graph.objects(SDO.forDecisionContract, RDFS.domain)) == {SDO.ConformanceCase}


def test_decision_graph_has_no_isolated_classes_and_keeps_version_targets_separate():
    graph = Graph().parse(DECISION_ONTOLOGY)
    result = dataset(graph)
    connected = {edge[end] for edge in result['edges'] for end in ('source', 'target')}
    assert {node['id'] for node in result['nodes']} == connected
    version_edges = [edge for edge in result['edges'] if edge['iri'] == str(DCTERMS.isVersionOf)]
    assert {(edge['source'], edge['target'], edge.get('constraint')) for edge in version_edges} == {
        (str(SDO.RuleSetVersion), str(SDO.RuleSet), 'allValuesFrom'),
        (str(SDO.SourceRevision), str(SDO.Source), 'allValuesFrom'),
    }
    assert all(edge['label'] == 'ist Version von' for edge in version_edges)
    assert not list(graph.objects(DCTERMS.isVersionOf, RDFS.domain))
    assert not list(graph.objects(DCTERMS.isVersionOf, RDFS.range))


def test_graph_and_positions_do_not_depend_on_blank_node_identifiers_or_triple_order():
    graph = Graph().parse(DECISION_ONTOLOGY)
    other = Graph().parse(data=graph.serialize(format='turtle'), format='turtle')
    assert dataset(graph) == dataset(other)


def test_only_explicit_unambiguous_all_values_restrictions_become_typed_edges():
    graph = Graph().parse(data=f'''
        @prefix sdo: <{SDO}> .
        @prefix owl: <{OWL}> .
        @prefix rdfs: <{RDFS}> .
        sdo:A a owl:Class; rdfs:subClassOf
            [a owl:Restriction; owl:onProperty sdo:p; owl:allValuesFrom sdo:B],
            [a owl:Restriction; owl:onProperty sdo:p; owl:allValuesFrom <https://example.net/External>],
            [a owl:Restriction; owl:onProperty sdo:p; owl:someValuesFrom sdo:B],
            [a owl:Restriction; owl:onProperty sdo:p, sdo:q; owl:allValuesFrom sdo:B],
            [a owl:Restriction; owl:onProperty sdo:p; owl:allValuesFrom sdo:A, sdo:B].
        sdo:B a owl:Class .
    ''', format='turtle')
    assert dataset(graph)['edges'] == [{
        'source': str(SDO.A), 'target': str(SDO.B), 'label': 'p', 'kind': 'object',
        'iri': str(SDO.p), 'constraint': 'allValuesFrom',
    }, {
        'source': str(SDO.A), 'target': 'https://example.net/External', 'label': 'p', 'kind': 'object',
        'iri': str(SDO.p), 'constraint': 'allValuesFrom',
    }]

from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace
from rdflib.namespace import DCTERMS
import pytest

from tools.generate import (
    SDO,
    build_decision_contract,
    load_contract_graph,
    read_decision_model,
)


ROOT = Path(__file__).parents[2]
PRODUCT_ROOT = ROOT / "products" / "kfw_458_eligibility"
KFW458 = Namespace(
    "https://arturmiller.github.io/spec-compiler/resources/funding/kfw-458/#"
)
FUNDING = Namespace(
    "https://arturmiller.github.io/spec-compiler/ontology/funding/#"
)


def _graph() -> Graph:
    return load_contract_graph(PRODUCT_ROOT)


def test_decision_model_preserves_applicant_project_and_source_semantics():
    model = read_decision_model(PRODUCT_ROOT, _graph())

    assert model.product == str(KFW458.EligibilityEvaluator)
    assert model.rule_set == str(KFW458.ApplicantEligibilityRules)
    assert model.rule_set_version == str(KFW458.ApplicantEligibilityRules2026_07)
    assert model.valid_from == "2026-07-21"
    assert len(model.rules) == 6
    assert {
        rule.condition.input_json_pointer.split("/")[2] for rule in model.rules
    } == {"applicant", "project"}
    assert {case.expected_outcome for case in model.conformance_cases} == {
        str(FUNDING.Eligible),
        str(FUNDING.Ineligible),
        str(FUNDING.Unknown),
    }
    assert {
        rule.source.source_revision for rule in model.rules
    } == {str(KFW458.Kfw458Merkblatt2026_07)}
    assert all(rule.source.statement for rule in model.rules)
    assert model.question_flow_case == str(KFW458.EligibleApplicantCase)
    assert {
        rule.condition.identifier: rule.condition.question.priority
        for rule in model.rules
    } == {
        str(KFW458.ConditionNaturalPerson): 10,
        str(KFW458.ConditionOwner): 20,
        str(KFW458.ConditionNotOwnershipViaGbR): 30,
        str(KFW458.ConditionNoUsufructRight): 40,
        str(KFW458.ConditionExistingResidentialBuilding): 50,
        str(KFW458.ConditionBuildingInGermany): 60,
    }
    assert all(rule.condition.question.text for rule in model.rules)


def test_missing_case_fact_is_preserved_as_unknown_instead_of_false():
    model = read_decision_model(PRODUCT_ROOT, _graph())
    unknown = next(
        case
        for case in model.conformance_cases
        if case.expected_outcome == str(FUNDING.Unknown)
    )

    assert len(unknown.facts) == 5
    assert str(KFW458.ConditionOwner) not in dict(unknown.facts)


def test_rule_without_source_citation_is_rejected():
    graph = _graph()
    graph.remove((KFW458.RuleNaturalPerson, SDO.sourceCitation, None))

    with pytest.raises(ValueError, match="Expected exactly one.*sourceCitation"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_source_revision_without_content_identity_is_rejected():
    graph = _graph()
    graph.remove((KFW458.Kfw458Merkblatt2026_07, SDO.contentSha256, None))

    with pytest.raises(ValueError, match="Expected exactly one.*contentSha256"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_empty_source_statement_is_rejected():
    graph = _graph()
    graph.set((KFW458.CitationGbRExclusion, SDO.sourceStatement, Literal("")))

    with pytest.raises(ValueError, match="statement must not be empty"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_ambiguous_decision_outcome_is_rejected():
    graph = _graph()
    graph.add(
        (
            KFW458.ApplicantEligibilityDecision2026_07,
            SDO.positiveOutcome,
            FUNDING.Ineligible,
        )
    )

    with pytest.raises(ValueError, match="Expected exactly one.*positiveOutcome"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_conformance_case_that_contradicts_the_declared_rules_is_rejected():
    graph = _graph()
    fact = next(
        candidate
        for candidate in graph.objects(
            KFW458.EligibleApplicantCase, SDO.hasFact
        )
        if next(graph.objects(candidate, SDO.forCondition))
        == KFW458.ConditionOwner
    )
    graph.remove((KFW458.EligibleApplicantCase, SDO.hasFact, fact))

    with pytest.raises(ValueError, match="Decision Conventions v1 derives"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_decision_profile_requires_explicit_protocol_and_product_identity():
    graph = _graph()
    graph.remove((KFW458.EligibilityEvaluator, RDF.type, None))

    with pytest.raises(ValueError, match="schema:SoftwareApplication"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_rule_set_version_requires_explicit_identity():
    graph = _graph()
    graph.remove(
        (
            KFW458.ApplicantEligibilityRules2026_07,
            DCTERMS.isVersionOf,
            None,
        )
    )

    with pytest.raises(ValueError, match="Expected exactly one.*isVersionOf"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_condition_without_an_authored_fact_question_is_rejected():
    graph = _graph()
    graph.remove((KFW458.QuestionOwner, SDO.elicitsCondition, None))

    with pytest.raises(ValueError, match="exactly one sdo:FactQuestion"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_duplicate_fact_question_priority_is_rejected():
    graph = _graph()
    graph.set(
        (
            KFW458.QuestionOwner,
            SDO.questionPriority,
            Literal(10),
        )
    )

    with pytest.raises(ValueError, match="priorities must be unique"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_non_positive_fact_question_priority_is_rejected():
    graph = _graph()
    graph.set(
        (
            KFW458.QuestionOwner,
            SDO.questionPriority,
            Literal(0),
        )
    )

    with pytest.raises(ValueError, match="xsd:positiveInteger"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_question_flow_case_must_be_unique():
    graph = _graph()
    graph.add((KFW458.IneligibleUsufructCase, RDF.type, SDO.QuestionFlowCase))

    with pytest.raises(ValueError, match="exactly one sdo:QuestionFlowCase"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_question_flow_case_must_have_the_positive_outcome():
    graph = _graph()
    fact = next(
        candidate
        for candidate in graph.objects(
            KFW458.EligibleApplicantCase, SDO.hasFact
        )
        if next(graph.objects(candidate, SDO.forCondition))
        == KFW458.ConditionOwner
    )
    graph.remove((KFW458.EligibleApplicantCase, SDO.hasFact, fact))
    graph.add((KFW458.UnknownOwnershipCase, SDO.hasFact, fact))
    graph.set(
        (
            KFW458.EligibleApplicantCase,
            SDO.expectsOutcome,
            FUNDING.Unknown,
        )
    )
    graph.set(
        (
            KFW458.UnknownOwnershipCase,
            SDO.expectsOutcome,
            FUNDING.Eligible,
        )
    )

    with pytest.raises(ValueError, match="positive outcome"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_fact_question_for_an_unused_condition_is_not_compiled():
    graph = _graph()
    irrelevant_condition = KFW458.ConditionApplicantLikesBlue
    irrelevant_question = KFW458.QuestionApplicantLikesBlue
    graph.add((irrelevant_condition, RDF.type, SDO.Condition))
    graph.add((irrelevant_question, RDF.type, SDO.FactQuestion))
    graph.add(
        (irrelevant_question, SDO.elicitsCondition, irrelevant_condition)
    )
    graph.add(
        (
            irrelevant_question,
            SDO.questionText,
            Literal("Does the applicant like blue?"),
        )
    )
    graph.add((irrelevant_question, SDO.questionPriority, Literal(1)))

    contract = build_decision_contract(
        read_decision_model(PRODUCT_ROOT, graph)
    )

    compiled_questions = {
        rule["condition"]["question"]["id"] for rule in contract["rules"]
    }
    assert str(irrelevant_question) not in compiled_questions

from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS
import pytest

from tools.generate import (
    SCO,
    SDO,
    build_decision_contract,
    build_http_openapi,
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
CLOUD_PRODUCT_ROOT = ROOT / "products" / "cloud_access_compliance"
CLOUDIAM = Namespace(
    "https://arturmiller.github.io/spec-compiler/resources/cloud/privileged-access/#"
)
CLOUD = Namespace(
    "https://arturmiller.github.io/spec-compiler/ontology/cloud/#"
)


def _graph() -> Graph:
    return load_contract_graph(PRODUCT_ROOT)


def test_decision_model_preserves_applicant_project_and_source_semantics():
    model = read_decision_model(PRODUCT_ROOT, _graph())

    assert model.product == str(KFW458.EligibilityEvaluator)
    assert model.rule_set == str(KFW458.ApplicantEligibilityRules)
    assert [version.identifier for version in model.rule_set_versions] == [
        str(KFW458.ApplicantEligibilityRules2025_12),
        str(KFW458.ApplicantEligibilityRules2026_07),
    ]
    historical, current = model.rule_set_versions
    assert historical.valid_from == "2025-12-10"
    assert historical.valid_until == "2026-07-21"
    assert current.valid_from == "2026-07-21"
    assert current.valid_until is None
    assert len(historical.rules) == 5
    assert len(current.rules) == 6
    assert {
        rule.condition.input_json_pointer.split("/")[2] for rule in current.rules
    } == {"applicant", "project"}
    assert {case.expected_outcome for case in model.conformance_cases} == {
        str(FUNDING.Eligible),
        str(FUNDING.Ineligible),
        str(FUNDING.Unknown),
    }
    assert {
        version.source.source_revision for version in model.rule_set_versions
    } == {
        str(KFW458.Kfw458Merkblatt2025_12),
        str(KFW458.Kfw458Merkblatt2026_07),
    }
    assert all(
        rule.source.source_revision == version.source.source_revision
        for version in model.rule_set_versions
        for rule in version.rules
    )
    assert all(rule.source.statement for rule in current.rules)
    assert model.question_flow_case == str(KFW458.EligibleApplicantCase)
    assert {
        rule.condition.identifier: rule.condition.question.priority
        for rule in current.rules
    } == {
        str(KFW458.ConditionNaturalPerson): 10,
        str(KFW458.ConditionOwner): 20,
        str(KFW458.ConditionNotOwnershipViaGbR): 30,
        str(KFW458.ConditionNoUsufructRight): 40,
        str(KFW458.ConditionExistingResidentialBuilding): 50,
        str(KFW458.ConditionBuildingInGermany): 60,
    }
    assert all(rule.condition.question.text for rule in current.rules)
    selection_cases = [
        case
        for case in model.conformance_cases
        if case.identifier in model.version_selection_cases
    ]
    assert len(selection_cases) == 2
    assert selection_cases[0].facts == selection_cases[1].facts
    assert len({case.expected_rule_set_version for case in selection_cases}) == 2
    assert len({case.expected_outcome for case in selection_cases}) == 2
    assert all(version.source.statement for version in model.rule_set_versions)
    assert model.http_endpoint is not None
    assert model.http_endpoint.path == "/eligibility-decisions"
    assert model.http_endpoint.success_response.status_code == 200
    assert model.http_endpoint.invalid_request_response.status_code == 400


def test_http_openapi_preserves_authored_message_schemas():
    model = read_decision_model(PRODUCT_ROOT, _graph())
    openapi = build_http_openapi(model.http_endpoint)
    operation = openapi["paths"]["/eligibility-decisions"]["post"]
    request = operation["requestBody"]["content"]["application/json"]["schema"]
    applicant = request["properties"]["case"]["properties"]["applicant"]
    assert applicant["properties"]["naturalPerson"] == {"type": "boolean"}
    assert applicant["properties"]["hasUsufructRight"] == {"type": "boolean"}
    assert "naturalPerson" not in applicant.get("required", [])
    assert set(operation["responses"]) == {"200", "400"}
    result = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert result["properties"]["outcome"]["enum"] == [
        "eligible", "ineligible", "unknown"
    ]
    assert result["properties"]["next_question"]["type"] == ["object", "null"]


def test_decision_http_endpoint_must_expose_the_selected_contract():
    graph = _graph()
    graph.set(
        (
            KFW458.ApplicantEligibilityPostEndpoint,
            SCO.invokesContract,
            KFW458.OtherDecision,
        )
    )
    with pytest.raises(ValueError, match="must invoke the product's Decision Contract"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_decision_http_mapping_requires_a_post_endpoint():
    graph = _graph()
    endpoint = KFW458.ApplicantEligibilityPostEndpoint
    graph.remove((endpoint, RDF.type, SCO.PostEndpoint))
    graph.add((endpoint, RDF.type, SCO.GetEndpoint))

    with pytest.raises(ValueError, match="must be a sco:PostEndpoint"):
        read_decision_model(PRODUCT_ROOT, graph)


@pytest.mark.parametrize("predicate", [SCO.request, SCO.successResponse, SCO.invalidRequestResponse])
def test_post_endpoint_requires_explicit_http_messages(predicate):
    graph = _graph()
    graph.remove((KFW458.ApplicantEligibilityPostEndpoint, predicate, None))

    with pytest.raises(ValueError, match="Expected exactly one"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_decision_http_endpoint_rejects_unsupported_paths():
    graph = _graph()
    graph.set((KFW458.ApplicantEligibilityPostEndpoint, SCO.path, Literal("/cases/{id}")))
    with pytest.raises(ValueError, match="fixed, safe path"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_missing_case_fact_is_preserved_as_unknown_instead_of_false():
    model = read_decision_model(PRODUCT_ROOT, _graph())
    current = model.rule_set_versions[-1]
    unknown = next(
        case
        for case in model.conformance_cases
        if case.expected_outcome == str(FUNDING.Unknown)
    )

    rule_conditions = {rule.condition.identifier for rule in current.rules}
    assert len(
        [condition for condition, _ in unknown.facts if condition in rule_conditions]
    ) == 5
    assert str(KFW458.ConditionOwner) not in dict(unknown.facts)


def test_evidence_requirement_is_separate_and_independently_sourced():
    model = read_decision_model(PRODUCT_ROOT, _graph())
    current = model.rule_set_versions[-1]
    requirement = current.evidence_requirements[0]
    owner_rule = next(
        rule
        for rule in current.rules
        if rule.condition.identifier == str(KFW458.ConditionOwner)
    )
    cases_by_status = {
        status: case
        for case in model.conformance_cases
        for requirement_id, status in case.expected_evidence_statuses
        if requirement_id == requirement.identifier
        and dict(case.facts).get(str(KFW458.ConditionOwner)) is True
    }

    assert requirement.supports_condition == str(KFW458.ConditionOwner)
    assert requirement.source.citation == str(
        KFW458.CitationOwnershipEvidenceForApplicantBonus2026_07
    )
    assert requirement.source.citation != owner_rule.source.citation
    assert set(cases_by_status) == {"fulfilled", "missing", "not_applicable"}
    assert cases_by_status["fulfilled"].expected_outcome == str(FUNDING.Eligible)
    assert cases_by_status["missing"].expected_outcome == str(FUNDING.Eligible)
    assert cases_by_status["fulfilled"].evidence[0].assessments[0].accepted is True
    assert cases_by_status["missing"].evidence == ()


def test_evidence_requirement_without_its_own_source_is_rejected():
    graph = _graph()
    graph.remove(
        (
            KFW458.OwnershipEvidenceRequirementForApplicantBonus2026_07,
            SDO.evidenceSourceCitation,
            None,
        )
    )

    with pytest.raises(ValueError, match="Expected exactly one.*evidenceSourceCitation"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_cloud_model_reuses_core_without_funding_vocabulary():
    graph = load_contract_graph(CLOUD_PRODUCT_ROOT)
    model = read_decision_model(CLOUD_PRODUCT_ROOT, graph)
    version = model.rule_set_versions[0]
    requirement = version.evidence_requirements[0]

    assert model.product == str(CLOUDIAM.ComplianceEvaluator)
    assert model.rule_set == str(CLOUDIAM.PrivilegedAccessPolicy)
    assert {model.positive_outcome, model.negative_outcome, model.unknown_outcome} == {
        str(CLOUD.Satisfied),
        str(CLOUD.Violated),
        str(CLOUD.Unknown),
    }
    assert all(
        rule.condition.fact_property.startswith(str(CLOUD))
        for rule in version.rules
    )
    assert {obligation.identifier for rule in version.rules for obligation in rule.obligations} == {
        str(CLOUDIAM.ObligationUniqueOrganizationalUsers),
        str(CLOUDIAM.ObligationPrivilegedMfa),
    }
    assert requirement.source.source_revision == str(CLOUDIAM.NistSp80053ARev5)
    assert version.source.source_revision == str(CLOUDIAM.NistSp80053Rev5Update1)
    assert requirement.source.source_revision != version.source.source_revision
    assert not any(
        isinstance(value, URIRef) and str(value).startswith(str(FUNDING))
        for triple in graph
        for value in triple
    )


def test_cloud_obligation_expectations_are_complete_and_derived():
    model = read_decision_model(
        CLOUD_PRODUCT_ROOT, load_contract_graph(CLOUD_PRODUCT_ROOT)
    )

    assert {
        status
        for case in model.conformance_cases
        for _, status in case.expected_obligation_statuses
    } == {"fulfilled", "violated", "unknown"}


def test_cloud_case_without_an_obligation_expectation_is_rejected():
    graph = load_contract_graph(CLOUD_PRODUCT_ROOT)
    expectation = next(
        graph.objects(
            CLOUDIAM.UnknownMfaCase,
            SDO.hasObligationExpectation,
        )
    )
    graph.remove(
        (
            CLOUDIAM.UnknownMfaCase,
            SDO.hasObligationExpectation,
            expectation,
        )
    )

    with pytest.raises(ValueError, match="lacks Obligation Expectations"):
        read_decision_model(CLOUD_PRODUCT_ROOT, graph)


def test_fulfilled_evidence_expectation_requires_an_accepted_assessment():
    graph = _graph()
    graph.set(
        (
            KFW458.AcceptedOwnershipEvidenceAssessment,
            SDO.accepted,
            Literal(False),
        )
    )

    with pytest.raises(ValueError, match="Evidence Evaluation Conventions v1 derive missing"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_rule_without_source_citation_is_rejected():
    graph = _graph()
    graph.remove((KFW458.RuleNaturalPerson2026_07, SDO.sourceCitation, None))

    with pytest.raises(ValueError, match="Expected exactly one.*sourceCitation"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_source_revision_without_content_identity_is_rejected():
    graph = _graph()
    graph.remove((KFW458.Kfw458Merkblatt2026_07, SDO.contentSha256, None))

    with pytest.raises(ValueError, match="Expected exactly one.*contentSha256"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_empty_source_statement_is_rejected():
    graph = _graph()
    graph.set((KFW458.CitationGbRExclusion2026_07, SDO.sourceStatement, Literal("")))

    with pytest.raises(ValueError, match="statement must not be empty"):
        read_decision_model(PRODUCT_ROOT, graph)


def test_ambiguous_decision_outcome_is_rejected():
    graph = _graph()
    graph.add(
        (
            KFW458.ApplicantEligibilityDecision,
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
        rule["condition"]["question"]["id"]
        for version in contract["rule_set"]["versions"]
        for rule in version["rules"]
    }
    assert str(irrelevant_question) not in compiled_questions

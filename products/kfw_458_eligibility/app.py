"""Reference implementation of the compiled KfW 458 decision contract."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys


MISSING = object()


def _value_at_pointer(document: dict, pointer: str):
    target = document
    for encoded in pointer[1:].split("/"):
        part = encoded.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or part not in target:
            return MISSING
        target = target[part]
    return target


def _evaluate_evidence_requirements(version: dict, request: dict) -> list[dict]:
    supplied = request.get("evidence", [])
    if not isinstance(supplied, list):
        raise ValueError("Decision Request evidence must be a list")
    known_requirements = {
        requirement["id"] for requirement in version["evidence_requirements"]
    }
    normalized_evidence = []
    evidence_ids = set()
    for evidence in supplied:
        if not isinstance(evidence, dict):
            raise ValueError("Each supplied Evidence must be an object")
        evidence_id = evidence.get("id")
        evidence_type = evidence.get("evidence_type")
        assessments = evidence.get("assessments")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise ValueError("Each supplied Evidence must have a non-empty id")
        if evidence_id in evidence_ids:
            raise ValueError(f"Supplied Evidence id must be unique: {evidence_id}")
        evidence_ids.add(evidence_id)
        if not isinstance(evidence_type, str) or not evidence_type:
            raise ValueError(
                f"Supplied Evidence {evidence_id} must have an evidence_type"
            )
        if not isinstance(assessments, list):
            raise ValueError(
                f"Supplied Evidence {evidence_id} assessments must be a list"
            )
        normalized_assessments = {}
        for assessment in assessments:
            if not isinstance(assessment, dict):
                raise ValueError("Each Evidence Assessment must be an object")
            requirement_id = assessment.get("evidence_requirement")
            accepted = assessment.get("accepted")
            if requirement_id not in known_requirements:
                raise ValueError(
                    f"Evidence Assessment references unknown requirement: "
                    f"{requirement_id}"
                )
            if requirement_id in normalized_assessments:
                raise ValueError(
                    f"Supplied Evidence {evidence_id} has duplicate assessments "
                    f"for {requirement_id}"
                )
            if not isinstance(accepted, bool):
                raise ValueError("Evidence Assessment accepted must be boolean")
            normalized_assessments[requirement_id] = accepted
        normalized_evidence.append(
            {
                "id": evidence_id,
                "evidence_type": evidence_type,
                "assessments": normalized_assessments,
            }
        )

    evaluations = []
    for requirement in version["evidence_requirements"]:
        applicability = []
        for condition in requirement["applicability_conditions"]:
            actual = _value_at_pointer(request, condition["input_json_pointer"])
            if actual is MISSING:
                state = "unknown"
            else:
                if not isinstance(actual, bool):
                    raise ValueError(
                        f"Fact at {condition['input_json_pointer']} must be boolean"
                    )
                state = (
                    "satisfied"
                    if actual == condition["expected_boolean"]
                    else "violated"
                )
            applicability.append({"condition": condition["id"], "state": state})

        classifications = []
        for evidence in sorted(normalized_evidence, key=lambda item: item["id"]):
            if evidence["evidence_type"] != requirement["required_evidence_type"]:
                classification = "not_relevant"
            elif requirement["id"] not in evidence["assessments"]:
                classification = "unassessed"
            elif evidence["assessments"][requirement["id"]]:
                classification = "accepted"
            else:
                classification = "rejected"
            classifications.append(
                {
                    "evidence": evidence["id"],
                    "evidence_type": evidence["evidence_type"],
                    "classification": classification,
                }
            )
        if not all(item["state"] == "satisfied" for item in applicability):
            status = "not_applicable"
        elif any(
            item["classification"] == "accepted" for item in classifications
        ):
            status = "fulfilled"
        else:
            status = "missing"
        source = requirement["source"]
        evaluations.append(
            {
                "evidence_requirement": requirement["id"],
                "supports_condition": requirement["supports_condition"],
                "required_evidence_type": requirement["required_evidence_type"],
                "applicability_conditions": applicability,
                "status": status,
                "supplied_evidence": classifications,
                "provenance": {
                    "source_citation": source["citation"],
                    "source_revision": source["source_revision"],
                    "source_locator": source["locator"],
                    "source_statement": source["statement"],
                },
                "explanation": (
                    f"{status}: Evidence Requirement {requirement['id']} supports "
                    f"Condition {requirement['supports_condition']}. "
                    f"{source['statement']}"
                ),
            }
        )
    return evaluations


def evaluate(contract: dict, request: dict) -> dict:
    if request.get("decision_contract") != contract["decision_contract"]:
        raise ValueError("Decision Request selects an unsupported Decision Contract")
    rule_set = contract["rule_set"]
    if request.get("rule_set") != rule_set["id"]:
        raise ValueError("Decision Request selects an unsupported Rule Set")
    if "rule_set_version" in request:
        raise ValueError(
            "Decision Request must not select a Rule Set Version; it is derived "
            "from decision_date"
        )
    try:
        decision_date = date.fromisoformat(request["decision_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Decision Request must contain an ISO decision_date") from error
    applicable_versions = []
    for candidate in rule_set["versions"]:
        valid_from = date.fromisoformat(candidate["valid_from"])
        valid_until = (
            date.fromisoformat(candidate["valid_until"])
            if candidate["valid_until"] is not None
            else None
        )
        if decision_date >= valid_from and (
            valid_until is None or decision_date < valid_until
        ):
            applicable_versions.append(candidate)
    if len(applicable_versions) != 1:
        raise ValueError(
            f"Decision Date {request['decision_date']} matches "
            f"{len(applicable_versions)} Rule Set Versions; expected exactly one"
        )
    version = applicable_versions[0]

    evaluations = []
    fact_gaps = []
    for rule in version["rules"]:
        condition = rule["condition"]
        actual = _value_at_pointer(request, condition["input_json_pointer"])
        if actual is MISSING:
            state = "unknown"
            fact_gaps.append(
                {
                    "condition": condition["id"],
                    "fact_property": condition["fact_property"],
                    "input_json_pointer": condition["input_json_pointer"],
                }
            )
        else:
            if not isinstance(actual, bool):
                raise ValueError(
                    f"Fact at {condition['input_json_pointer']} must be boolean"
                )
            state = (
                "satisfied"
                if actual == condition["expected_boolean"]
                else "violated"
            )
        evaluations.append(
            {
                "rule": rule["id"],
                "condition": condition["id"],
                "state": state,
            }
        )

    violated = [
        evaluation["rule"]
        for evaluation in evaluations
        if evaluation["state"] == "violated"
    ]
    unknown = [
        evaluation["rule"]
        for evaluation in evaluations
        if evaluation["state"] == "unknown"
    ]
    if violated:
        outcome_role = "negative"
        decisive_rules = violated
    elif unknown:
        outcome_role = "unknown"
        decisive_rules = unknown
    else:
        outcome_role = "positive"
        decisive_rules = [rule["id"] for rule in version["rules"]]
    outcome = contract["outcomes"][outcome_role]
    evidence_requirement_evaluations = _evaluate_evidence_requirements(
        version, request
    )

    rule_by_id = {rule["id"]: rule for rule in version["rules"]}
    provenance = [
        {
            "rule": rule_id,
            "source_citation": rule_by_id[rule_id]["source"]["citation"],
            "source_revision": rule_by_id[rule_id]["source"]["source_revision"],
            "source_locator": rule_by_id[rule_id]["source"]["locator"],
            "source_statement": rule_by_id[rule_id]["source"]["statement"],
        }
        for rule_id in decisive_rules
    ]
    next_question = None
    if outcome_role == "unknown":
        next_rule = min(
            (rule_by_id[rule_id] for rule_id in unknown),
            key=lambda rule: rule["condition"]["question"]["priority"],
        )
        condition = next_rule["condition"]
        question = condition["question"]
        source = next_rule["source"]
        next_question = {
            "id": question["id"],
            "text": question["text"],
            "condition": condition["id"],
            "fact_property": condition["fact_property"],
            "input_json_pointer": condition["input_json_pointer"],
            "answer_schema": {"type": "boolean"},
            "justification": {
                "rule": next_rule["id"],
                "source_citation": source["citation"],
                "source_revision": source["source_revision"],
                "source_locator": source["locator"],
                "source_statement": source["statement"],
            },
        }
    if outcome_role == "positive":
        explanation = (
            f"{outcome['code']}: all {len(version['rules'])} modeled applicant "
            "eligibility conditions are satisfied."
        )
    elif outcome_role == "negative":
        statements = "; ".join(item["source_statement"] for item in provenance)
        explanation = f"{outcome['code']}: {statements}"
    else:
        pointers = ", ".join(gap["input_json_pointer"] for gap in fact_gaps)
        explanation = f"{outcome['code']}: required facts are missing at {pointers}."

    return {
        "decision_contract": contract["decision_contract"],
        "rule_set": rule_set["id"],
        "rule_set_version": version["id"],
        "rule_set_version_label": version["version"],
        "decision_date": request["decision_date"],
        "outcome": outcome["code"],
        "outcome_id": outcome["id"],
        "condition_evaluations": evaluations,
        "decisive_rules": decisive_rules,
        "fact_gaps": fact_gaps,
        "next_question": next_question,
        "evidence_requirement_evaluations": evidence_requirement_evaluations,
        "provenance": provenance,
        "explanation": explanation,
        "scope_note": contract["scope_note"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Decision Request must be a JSON object")
        result = evaluate(contract, request)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

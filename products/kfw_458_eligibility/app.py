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


def evaluate(contract: dict, request: dict) -> dict:
    if request.get("decision_contract") != contract["decision_contract"]:
        raise ValueError("Decision Request selects an unsupported Decision Contract")
    rule_set = contract["rule_set"]
    if request.get("rule_set_version") != rule_set["version"]:
        raise ValueError("Decision Request must pin the compiled Rule Set Version")
    try:
        decision_date = date.fromisoformat(request["decision_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Decision Request must contain an ISO decision_date") from error
    valid_from = date.fromisoformat(rule_set["valid_from"])
    valid_until = (
        date.fromisoformat(rule_set["valid_until"])
        if rule_set["valid_until"] is not None
        else None
    )
    if decision_date < valid_from or (
        valid_until is not None and decision_date >= valid_until
    ):
        raise ValueError("Decision date falls outside the pinned Rule Set Version")

    evaluations = []
    fact_gaps = []
    for rule in contract["rules"]:
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
        decisive_rules = [rule["id"] for rule in contract["rules"]]
    outcome = contract["outcomes"][outcome_role]

    rule_by_id = {rule["id"]: rule for rule in contract["rules"]}
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
    if outcome_role == "positive":
        explanation = (
            f"{outcome['code']}: all {len(contract['rules'])} modeled applicant "
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
        "rule_set_version": rule_set["version"],
        "decision_date": request["decision_date"],
        "outcome": outcome["code"],
        "outcome_id": outcome["id"],
        "condition_evaluations": evaluations,
        "decisive_rules": decisive_rules,
        "fact_gaps": fact_gaps,
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

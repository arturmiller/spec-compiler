"""Generate deterministic contracts, tests, and work for a product."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from pprint import pformat
import re

from rdflib import Graph, Namespace, RDF
from rdflib.namespace import DCTERMS, OWL, SH, XSD

ROOT = Path(__file__).parents[1]
BOOTSTRAP_GENERATION = 1
COMPILER_CONVENTIONS_VERSION = 1
RUNTIME_PROTOCOL_VERSION = 1
DECISION_CONVENTIONS_VERSION = 1
DECISION_PROTOCOL_VERSION = 1
SCO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/#")
SDO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/decision/#")
SCHEMA = Namespace("https://schema.org/")
SQL_TYPES = {
    XSD.string: "TEXT",
    XSD.decimal: "DECIMAL",
    XSD.integer: "INTEGER",
}
OPENAPI_TYPES = {
    XSD.string: "string",
    XSD.decimal: "number",
    XSD.integer: "integer",
}
SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class DecisionSource:
    citation: str
    source_revision: str
    source: str
    locator: str
    statement: str
    title: str
    identifier: str
    version: str
    valid_from: str
    content_url: str
    content_sha256: str
    byte_size: int


@dataclass(frozen=True)
class DecisionCondition:
    identifier: str
    fact_property: str
    input_json_pointer: str
    expected_boolean: bool


@dataclass(frozen=True)
class DecisionRule:
    identifier: str
    condition: DecisionCondition
    source: DecisionSource


@dataclass(frozen=True)
class DecisionConformanceCase:
    identifier: str
    decision_date: str
    expected_outcome: str
    facts: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class ExplicitDecisionAndObligationModel:
    product: str
    decision_contract: str
    rule_set: str
    rule_set_version: str
    valid_from: str
    valid_until: str | None
    positive_outcome: str
    positive_outcome_code: str
    negative_outcome: str
    negative_outcome_code: str
    unknown_outcome: str
    unknown_outcome_code: str
    scope_note: str
    rules: tuple[DecisionRule, ...]
    conformance_cases: tuple[DecisionConformanceCase, ...]


def one(graph: Graph, subject, predicate):
    values = list(graph.objects(subject, predicate))
    if len(values) != 1:
        raise ValueError(f"Expected exactly one {predicate} on {subject}, got {len(values)}")
    return values[0]


def optional(graph: Graph, subject, predicate, default=None):
    values = list(graph.objects(subject, predicate))
    if len(values) > 1:
        raise ValueError(f"Expected at most one {predicate} on {subject}")
    return values[0].toPython() if values else default


def local_name(iri) -> str:
    value = str(iri)
    return value.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def sql_identifier(value: str) -> str:
    if not SQL_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Not a supported SQL identifier: {value!r}")
    return value


def load_contract_graph(product_root: Path) -> Graph:
    specs_root = product_root / "specs"
    spec_files = sorted(specs_root.glob("*.ttl"))
    if not spec_files:
        raise ValueError(f"No Turtle specs found in {specs_root}")
    contract_graph = Graph()
    for spec_file in spec_files:
        contract_graph.parse(spec_file, format="turtle")
    return contract_graph


def read_obligation_model(
    product_root: Path, contract_graph: Graph | None = None
) -> dict:
    contract_graph = contract_graph or load_contract_graph(product_root)
    shapes = system = contract_graph
    endpoints = list(system.subjects(RDF.type, SCO.GetEndpoint))
    tables = list(system.subjects(RDF.type, SCO.SqlTable))
    if len(endpoints) != 1 or len(tables) != 1:
        raise ValueError("Prototype expects exactly one GET endpoint and one SQL table")
    endpoint, table = endpoints[0], tables[0]
    shape = one(system, endpoint, SCO.returns)
    if one(system, table, SCO.stores) != shape:
        raise ValueError("Endpoint and table must reference the same shape")
    if one(system, endpoint, SCO.readsFrom) != table:
        raise ValueError("GET endpoint must explicitly identify the table it reads")
    if one(system, table, SCO.databaseEngine) != SCO.SQLite:
        raise ValueError("Prototype only has a declared mapping for sco:SQLite")
    rdf_class = one(shapes, shape, SH.targetClass)

    api_path = str(one(system, endpoint, SCO.path))
    path_parameter = one(system, endpoint, SCO.pathParameter)
    parameter_name = str(one(system, path_parameter, SCO.name))
    parameter_datatype = one(system, path_parameter, SH.datatype)
    if parameter_datatype not in OPENAPI_TYPES:
        raise ValueError(f"No OpenAPI type mapping for {parameter_datatype}")
    if f"{{{parameter_name}}}" not in api_path:
        raise ValueError(f"Path does not contain declared parameter {parameter_name!r}")

    table_name = sql_identifier(str(one(system, table, SCO.tableName)))
    id_column = sql_identifier(str(one(system, table, SCO.idColumn)))
    id_datatype = one(system, table, SCO.idDatatype)
    if id_datatype not in SQL_TYPES:
        raise ValueError(f"No SQL type mapping for identifier {id_datatype}")
    if str(one(system, path_parameter, SCO.mapsToColumn)) != id_column:
        raise ValueError("Path parameter must explicitly map to the identifier column")

    fields = []
    for prop in shapes.objects(shape, SH.property):
        path = one(shapes, prop, SH.path)
        datatype = one(shapes, prop, SH.datatype)
        min_count = int(one(shapes, prop, SH.minCount))
        max_count = int(one(shapes, prop, SH.maxCount))
        if min_count not in (0, 1) or max_count != 1:
            raise ValueError(
                "Prototype only maps scalar properties with minCount 0 or 1 "
                "and maxCount 1"
            )
        if datatype not in SQL_TYPES:
            raise ValueError(f"No SQL type mapping for {datatype}")
        if datatype not in OPENAPI_TYPES:
            raise ValueError(f"No OpenAPI type mapping for {datatype}")
        name = sql_identifier(local_name(path))
        fields.append(
            {
                "rdf_path": str(path),
                "name": name,
                "sql_type": SQL_TYPES[datatype],
                "required": min_count == 1,
                "datatype": str(datatype),
                "openapi_type": OPENAPI_TYPES[datatype],
                "min_length": optional(shapes, prop, SH.minLength),
                "min_exclusive": optional(shapes, prop, SH.minExclusive),
                "max_exclusive": optional(shapes, prop, SH.maxExclusive),
            }
        )

    fields.sort(key=lambda field: field["name"])

    return {
        "api_path": api_path,
        "success_status": int(one(system, endpoint, SCO.successStatus)),
        "media_type": str(one(system, endpoint, SCO.mediaType)),
        "path_parameter": {
            "name": parameter_name,
            "datatype": str(parameter_datatype),
            "openapi_type": OPENAPI_TYPES[parameter_datatype],
            "column": id_column,
        },
        "database_engine": local_name(one(system, table, SCO.databaseEngine)),
        "table_name": table_name,
        "id_column": id_column,
        "id_sql_type": SQL_TYPES[id_datatype],
        "id_primary_key": bool(one(system, table, SCO.idPrimaryKey).toPython()),
        "id_generated": bool(one(system, table, SCO.idGenerated).toPython()),
        "rdf_class": str(rdf_class),
        "resource_name": local_name(rdf_class),
        "shape_name": local_name(shape),
        "closed": bool(optional(shapes, shape, SH.closed, False)),
        "fields": fields,
    }


def read_compiler_contract(product_root: Path, graph: Graph) -> dict:
    products = list(graph.subjects(DCTERMS.conformsTo, SCO.CompilerProtocolV1))
    if len(products) != 1:
        raise ValueError(
            "Compiler profile expects exactly one product conforming to "
            "sco:CompilerProtocolV1"
        )
    product = products[0]
    if (product, RDF.type, SCHEMA.SoftwareApplication) not in graph:
        raise ValueError(
            "Compiler Protocol product must be a schema:SoftwareApplication"
        )
    contract = one(graph, product, SCO.implementsContract)
    if (contract, RDF.type, SCO.TransformationContract) not in graph:
        raise ValueError(
            "Compiler product contract must be a sco:TransformationContract"
        )
    fixture_nodes = sorted(
        graph.objects(contract, SCO.conformanceFixture), key=str
    )
    if not fixture_nodes:
        raise ValueError(
            "Spec compiler must declare at least one "
            "sco:CompilerConformanceFixture"
        )
    conformance_fixtures = []
    for fixture_node in fixture_nodes:
        if (fixture_node, RDF.type, SCO.CompilerConformanceFixture) not in graph:
            raise ValueError(
                f"Compiler conformance fixture {fixture_node} must be a "
                "sco:CompilerConformanceFixture"
            )
        fixture_product = str(one(graph, fixture_node, SCO.fixtureProduct))
        fixture_path = (product_root / fixture_product).resolve()
        if not fixture_path.is_dir():
            raise ValueError(
                f"Compiler fixture product does not exist: {fixture_path}"
            )
        artifacts = sorted(
            str(value)
            for value in graph.objects(fixture_node, SCO.expectsArtifact)
        )
        if not artifacts:
            raise ValueError(
                f"Compiler conformance fixture {fixture_node} must expect at "
                "least one generated artifact"
            )
        for artifact in artifacts:
            path = Path(artifact)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(
                    "Generated artifact pattern must stay in the input bundle: "
                    f"{artifact}"
                )
        conformance_fixtures.append(
            {
                "name": local_name(fixture_node),
                "fixture": str(fixture_node),
                "product": fixture_product,
                "generated_artifacts": artifacts,
            }
        )
    bootstrap_processes = list(graph.subjects(SCO.bootstrapsProduct, product))
    if len(bootstrap_processes) > 1:
        raise ValueError(
            "Compiler product may declare at most one sco:BootstrapProcess"
        )
    bootstrap = None
    if bootstrap_processes:
        process = bootstrap_processes[0]
        if (process, RDF.type, SCO.BootstrapProcess) not in graph:
            raise ValueError(
                "Compiler bootstrap provenance must be a sco:BootstrapProcess"
            )
        seed = one(graph, process, SCO.seedImplementation)
        if (seed, RDF.type, SCHEMA.SoftwareApplication) not in graph:
            raise ValueError(
                "Bootstrap seed must be a schema:SoftwareApplication"
            )
        strategy = one(graph, process, SCO.evolutionStrategy)
        if strategy != SCO.ModifyExistingImplementation:
            raise ValueError(
                "Bootstrap evolution strategy must be "
                "sco:ModifyExistingImplementation"
            )
        implementation_artifact = str(
            one(graph, process, SCO.generatesImplementationArtifact)
        )
        implementation_path = Path(implementation_artifact)
        if implementation_path.is_absolute() or ".." in implementation_path.parts:
            raise ValueError(
                "Generated implementation artifact must stay in the input bundle: "
                f"{implementation_artifact}"
            )
        bootstrap = {
            "process": str(process),
            "seed_implementation": str(seed),
            "evolution_strategy": str(strategy),
            "implementation_artifact": implementation_artifact,
            "implementation_generation": BOOTSTRAP_GENERATION + 1,
        }
    return {
        "name": local_name(product),
        "contract": str(contract),
        "protocol": str(SCO.CompilerProtocolV1),
        "input_spec_pattern": str(one(graph, contract, SCO.inputSpecPattern)),
        "conformance_fixtures": conformance_fixtures,
        "rejects_missing_specs": bool(
            one(graph, contract, SCO.rejectsMissingSpecs).toPython()
        ),
        "deterministic_output": bool(
            one(graph, contract, SCO.deterministicOutput).toPython()
        ),
        "bootstrap": bootstrap,
    }


def _boolean_value(value, description: str) -> bool:
    converted = value.toPython()
    if not isinstance(converted, bool):
        raise ValueError(f"{description} must be an xsd:boolean")
    return converted


def _date_value(value, description: str) -> str:
    converted = value.toPython()
    if not isinstance(converted, date):
        raise ValueError(f"{description} must be an xsd:date")
    return converted.isoformat()


def _required_text(graph: Graph, subject, predicate, description: str) -> str:
    value = str(one(graph, subject, predicate)).strip()
    if not value:
        raise ValueError(f"{description} must not be empty")
    return value


def _json_pointer(value: str) -> str:
    if not value.startswith("/case/"):
        raise ValueError(
            "Decision fact input pointers must identify a value below /case/"
        )
    if any(not part for part in value.split("/")[1:]):
        raise ValueError(f"Decision fact input pointer has an empty segment: {value}")
    if re.search(r"~(?:[^01]|$)", value):
        raise ValueError(f"Decision fact input pointer has invalid escaping: {value}")
    return value


def _read_decision_source(graph: Graph, citation) -> DecisionSource:
    if (citation, RDF.type, SDO.SourceCitation) not in graph:
        raise ValueError(
            f"Decision Rule source {citation} must be an sdo:SourceCitation"
        )
    revision = one(graph, citation, SDO.citesSourceRevision)
    if (revision, RDF.type, SDO.SourceRevision) not in graph:
        raise ValueError(
            f"Source Citation {citation} must cite an sdo:SourceRevision"
        )
    source = one(graph, revision, DCTERMS.isVersionOf)
    if (source, RDF.type, SDO.Source) not in graph:
        raise ValueError(
            f"Source Revision {revision} must identify an sdo:Source"
        )
    sha256 = str(one(graph, revision, SDO.contentSha256))
    if not SHA256.fullmatch(sha256):
        raise ValueError(
            f"Source Revision {revision} must declare a lowercase SHA-256 digest"
        )
    byte_size = int(one(graph, revision, SDO.byteSize))
    if byte_size <= 0:
        raise ValueError(f"Source Revision {revision} byte size must be positive")
    return DecisionSource(
        citation=str(citation),
        source_revision=str(revision),
        source=str(source),
        locator=_required_text(
            graph, citation, SDO.sourceLocator, "Source Citation locator"
        ),
        statement=_required_text(
            graph, citation, SDO.sourceStatement, "Source Citation statement"
        ),
        title=_required_text(
            graph, revision, DCTERMS.title, "Source Revision title"
        ),
        identifier=_required_text(
            graph,
            revision,
            DCTERMS.identifier,
            "Source Revision identifier",
        ),
        version=_required_text(
            graph, revision, OWL.versionInfo, "Source Revision version"
        ),
        valid_from=_date_value(
            one(graph, revision, SDO.validFrom),
            f"Source Revision {revision} validFrom",
        ),
        content_url=_required_text(
            graph, revision, SCHEMA.contentUrl, "Source Revision content URL"
        ),
        content_sha256=sha256,
        byte_size=byte_size,
    )


def _decision_outcome_for_case(
    rules: tuple[DecisionRule, ...],
    facts: tuple[tuple[str, bool], ...],
    *,
    positive_outcome: str,
    negative_outcome: str,
    unknown_outcome: str,
) -> str:
    values = dict(facts)
    states = []
    for rule in rules:
        actual = values.get(rule.condition.identifier)
        if actual is None:
            states.append("unknown")
        elif actual == rule.condition.expected_boolean:
            states.append("satisfied")
        else:
            states.append("violated")
    if "violated" in states:
        return negative_outcome
    if "unknown" in states:
        return unknown_outcome
    return positive_outcome


def read_decision_model(
    product_root: Path, graph: Graph | None = None
) -> ExplicitDecisionAndObligationModel:
    if graph is None:
        graph = load_contract_graph(product_root)
    products = list(graph.subjects(DCTERMS.conformsTo, SCO.DecisionProtocolV1))
    if len(products) != 1:
        raise ValueError(
            "Decision profile expects exactly one product conforming to "
            "sco:DecisionProtocolV1"
        )
    product = products[0]
    if (product, RDF.type, SCHEMA.SoftwareApplication) not in graph:
        raise ValueError(
            "Decision Protocol product must be a schema:SoftwareApplication"
        )
    contract = one(graph, product, SCO.implementsDecisionContract)
    if (contract, RDF.type, SDO.DecisionContract) not in graph:
        raise ValueError(
            "Decision product contract must be an sdo:DecisionContract"
        )
    if not _boolean_value(
        one(graph, contract, SDO.requiresAllRules),
        f"Decision Contract {contract} requiresAllRules",
    ):
        raise ValueError(
            "Decision Conventions v1 only supports contracts that explicitly "
            "require all Rules"
        )

    version = one(graph, contract, SDO.usesRuleSetVersion)
    if (version, RDF.type, SDO.RuleSetVersion) not in graph:
        raise ValueError(
            f"Decision Contract {contract} must use an sdo:RuleSetVersion"
        )
    rule_set = one(graph, version, DCTERMS.isVersionOf)
    if (rule_set, RDF.type, SDO.RuleSet) not in graph:
        raise ValueError(
            f"Rule Set Version {version} must identify an sdo:RuleSet"
        )
    valid_from = _date_value(
        one(graph, version, SDO.validFrom),
        f"Rule Set Version {version} validFrom",
    )
    valid_until_values = list(graph.objects(version, SDO.validUntil))
    if len(valid_until_values) > 1:
        raise ValueError(
            f"Expected at most one {SDO.validUntil} on {version}"
        )
    valid_until = (
        _date_value(
            valid_until_values[0], f"Rule Set Version {version} validUntil"
        )
        if valid_until_values
        else None
    )
    if valid_until is not None and valid_until <= valid_from:
        raise ValueError(
            f"Rule Set Version {version} validUntil must be after validFrom"
        )

    positive_outcome_node = one(graph, contract, SDO.positiveOutcome)
    negative_outcome_node = one(graph, contract, SDO.negativeOutcome)
    unknown_outcome_node = one(graph, contract, SDO.unknownOutcome)
    positive_outcome = str(positive_outcome_node)
    negative_outcome = str(negative_outcome_node)
    unknown_outcome = str(unknown_outcome_node)
    outcomes = {positive_outcome, negative_outcome, unknown_outcome}
    if len(outcomes) != 3:
        raise ValueError("Decision Contract outcomes must be three distinct IRIs")
    for outcome_node in (
        positive_outcome_node,
        negative_outcome_node,
        unknown_outcome_node,
    ):
        if (outcome_node, RDF.type, SDO.DecisionOutcome) not in graph:
            raise ValueError(
                f"Decision outcome {outcome_node} must be an sdo:DecisionOutcome"
            )
    outcome_codes = {
        positive_outcome: str(one(graph, positive_outcome_node, SDO.outcomeCode)),
        negative_outcome: str(one(graph, negative_outcome_node, SDO.outcomeCode)),
        unknown_outcome: str(one(graph, unknown_outcome_node, SDO.outcomeCode)),
    }
    if len(set(outcome_codes.values())) != 3 or any(
        not SQL_IDENTIFIER.fullmatch(code) for code in outcome_codes.values()
    ):
        raise ValueError(
            "Decision outcome codes must be distinct safe identifiers"
        )

    rule_nodes = sorted(graph.objects(version, SDO.hasRule), key=str)
    if not rule_nodes:
        raise ValueError("Decision Rule Set Version must contain at least one Rule")
    rules = []
    pointers = set()
    conditions = set()
    for rule_node in rule_nodes:
        if (rule_node, RDF.type, SDO.Rule) not in graph:
            raise ValueError(f"Rule Set member {rule_node} must be an sdo:Rule")
        condition_node = one(graph, rule_node, SDO.condition)
        if (condition_node, RDF.type, SDO.Condition) not in graph:
            raise ValueError(
                f"Decision Rule {rule_node} must reference an sdo:Condition"
            )
        condition_id = str(condition_node)
        if condition_id in conditions:
            raise ValueError(
                f"Decision Condition {condition_node} is used by more than one Rule"
            )
        conditions.add(condition_id)
        pointer = _json_pointer(str(one(graph, condition_node, SCO.inputJsonPointer)))
        if pointer in pointers:
            raise ValueError(
                f"Decision Conditions must not share input pointer {pointer}"
            )
        pointers.add(pointer)
        condition = DecisionCondition(
            identifier=condition_id,
            fact_property=str(one(graph, condition_node, SDO.factProperty)),
            input_json_pointer=pointer,
            expected_boolean=_boolean_value(
                one(graph, condition_node, SDO.expectedBoolean),
                f"Decision Condition {condition_node} expectedBoolean",
            ),
        )
        citation = one(graph, rule_node, SDO.sourceCitation)
        rules.append(
            DecisionRule(
                identifier=str(rule_node),
                condition=condition,
                source=_read_decision_source(graph, citation),
            )
        )
    immutable_rules = tuple(rules)

    case_nodes = sorted(graph.objects(contract, SDO.hasConformanceCase), key=str)
    if not case_nodes:
        raise ValueError(
            "Decision Contract must declare conformance cases for all outcomes"
        )
    cases = []
    for case_node in case_nodes:
        if (case_node, RDF.type, SDO.ConformanceCase) not in graph:
            raise ValueError(
                f"Decision conformance case {case_node} must be an sdo:ConformanceCase"
            )
        if one(graph, case_node, SDO.forDecisionContract) != contract:
            raise ValueError(
                f"Conformance case {case_node} must reference its Decision Contract"
            )
        if one(graph, case_node, SDO.usesRuleSetVersion) != version:
            raise ValueError(
                f"Conformance case {case_node} must pin its Rule Set Version"
            )
        decision_date = _date_value(
            one(graph, case_node, SDO.decisionDate),
            f"Conformance case {case_node} decisionDate",
        )
        if decision_date < valid_from or (
            valid_until is not None and decision_date >= valid_until
        ):
            raise ValueError(
                f"Conformance case {case_node} falls outside Rule Set validity"
            )
        expected_outcome = str(one(graph, case_node, SDO.expectsOutcome))
        if expected_outcome not in outcomes:
            raise ValueError(
                f"Conformance case {case_node} uses an undeclared outcome"
            )
        facts = []
        fact_conditions = set()
        for fact in graph.objects(case_node, SDO.hasFact):
            if (fact, RDF.type, SDO.CaseFact) not in graph:
                raise ValueError(
                    f"Conformance case fact {fact} must be an sdo:CaseFact"
                )
            condition = str(one(graph, fact, SDO.forCondition))
            if condition not in conditions:
                raise ValueError(
                    f"Conformance case {case_node} references unknown Condition {condition}"
                )
            if condition in fact_conditions:
                raise ValueError(
                    f"Conformance case {case_node} has conflicting Facts for {condition}"
                )
            fact_conditions.add(condition)
            facts.append(
                (
                    condition,
                    _boolean_value(
                        one(graph, fact, SDO.booleanValue),
                        f"Conformance case {case_node} Fact value",
                    ),
                )
            )
        immutable_facts = tuple(sorted(facts))
        derived_outcome = _decision_outcome_for_case(
            immutable_rules,
            immutable_facts,
            positive_outcome=positive_outcome,
            negative_outcome=negative_outcome,
            unknown_outcome=unknown_outcome,
        )
        if derived_outcome != expected_outcome:
            raise ValueError(
                f"Conformance case {case_node} expects {expected_outcome}, "
                f"but Decision Conventions v1 derives {derived_outcome}"
            )
        cases.append(
            DecisionConformanceCase(
                identifier=str(case_node),
                decision_date=decision_date,
                expected_outcome=expected_outcome,
                facts=immutable_facts,
            )
        )
    immutable_cases = tuple(cases)
    covered_outcomes = {case.expected_outcome for case in immutable_cases}
    if covered_outcomes != outcomes:
        missing = sorted(outcomes - covered_outcomes)
        raise ValueError(
            f"Decision Contract conformance cases do not cover outcomes: {missing}"
        )

    return ExplicitDecisionAndObligationModel(
        product=str(product),
        decision_contract=str(contract),
        rule_set=str(rule_set),
        rule_set_version=str(version),
        valid_from=valid_from,
        valid_until=valid_until,
        positive_outcome=positive_outcome,
        positive_outcome_code=outcome_codes[positive_outcome],
        negative_outcome=negative_outcome,
        negative_outcome_code=outcome_codes[negative_outcome],
        unknown_outcome=unknown_outcome,
        unknown_outcome_code=outcome_codes[unknown_outcome],
        scope_note=_required_text(
            graph, contract, SDO.scopeNote, "Decision Contract scope note"
        ),
        rules=immutable_rules,
        conformance_cases=immutable_cases,
    )


def deterministic_value(field: dict):
    if field["datatype"] == str(XSD.string):
        return "x" * max(field["min_length"] or 0, 1)
    if field["datatype"] == str(XSD.decimal):
        minimum = Decimal(str(field["min_exclusive"] or 0))
        return minimum + Decimal("0.01")
    raise ValueError(f"No deterministic value for {field['datatype']}")


def build_openapi(contract: dict) -> dict:
    properties = {}
    required = []
    for field in contract["fields"]:
        schema = {"type": field["openapi_type"]}
        if field["min_length"] is not None:
            schema["minLength"] = field["min_length"]
        if field["min_exclusive"] is not None:
            schema["exclusiveMinimum"] = float(field["min_exclusive"])
        if field["max_exclusive"] is not None:
            schema["exclusiveMaximum"] = float(field["max_exclusive"])
        properties[field["name"]] = schema
        if field["required"]:
            required.append(field["name"])

    response_schema = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    if contract["closed"]:
        response_schema["additionalProperties"] = False

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Generated contract",
            "version": "1.0.0",
        },
        "paths": {
            contract["api_path"]: {
                "get": {
                    "parameters": [
                        {
                            "name": contract["path_parameter"]["name"],
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": contract["path_parameter"]["openapi_type"]
                            },
                        }
                    ],
                    "responses": {
                        str(contract["success_status"]): {
                            "description": "Successful response",
                            "content": {
                                contract["media_type"]: {"schema": response_schema}
                            },
                        }
                    },
                }
            }
        },
    }


def build_decision_contract(
    model: ExplicitDecisionAndObligationModel,
) -> dict:
    """Render the typed decision model as a deterministic machine contract."""
    source_revisions = {}
    rules = []
    for rule in model.rules:
        source = rule.source
        source_revisions[source.source_revision] = {
            "id": source.source_revision,
            "source": source.source,
            "title": source.title,
            "identifier": source.identifier,
            "version": source.version,
            "valid_from": source.valid_from,
            "content_url": source.content_url,
            "content_sha256": source.content_sha256,
            "byte_size": source.byte_size,
        }
        rules.append(
            {
                "id": rule.identifier,
                "condition": {
                    "id": rule.condition.identifier,
                    "fact_property": rule.condition.fact_property,
                    "input_json_pointer": rule.condition.input_json_pointer,
                    "expected_boolean": rule.condition.expected_boolean,
                },
                "source": {
                    "citation": source.citation,
                    "source_revision": source.source_revision,
                    "locator": source.locator,
                    "statement": source.statement,
                },
            }
        )

    return {
        "profile": "decision-obligation-v1",
        "decision_protocol_version": DECISION_PROTOCOL_VERSION,
        "decision_conventions_version": DECISION_CONVENTIONS_VERSION,
        "product": model.product,
        "decision_contract": model.decision_contract,
        "rule_set": {
            "id": model.rule_set,
            "version": model.rule_set_version,
            "valid_from": model.valid_from,
            "valid_until": model.valid_until,
            "requires_all_rules": True,
        },
        "outcomes": {
            "positive": {
                "id": model.positive_outcome,
                "code": model.positive_outcome_code,
            },
            "negative": {
                "id": model.negative_outcome,
                "code": model.negative_outcome_code,
            },
            "unknown": {
                "id": model.unknown_outcome,
                "code": model.unknown_outcome_code,
            },
        },
        "scope_note": model.scope_note,
        "source_revisions": [
            source_revisions[key] for key in sorted(source_revisions)
        ],
        "rules": rules,
        "conformance_cases": [
            {
                "id": case.identifier,
                "decision_date": case.decision_date,
                "expected_outcome": case.expected_outcome,
                "facts": [
                    {"condition": condition, "value": value}
                    for condition, value in case.facts
                ],
            }
            for case in model.conformance_cases
        ],
    }


def build_decision_work_items(contract: dict, test_path: str) -> list[dict]:
    runtime_id = "kfw-458.decision-runtime"
    evaluation_id = "kfw-458.applicant-eligibility"
    return [
        {
            "id": runtime_id,
            "title": "Provide the Decision Protocol v1 interface",
            "goal": "Make the decision product invocable as a technology-neutral black box.",
            "depends_on": [],
            "obligations": [
                "The product can be invoked through its `product.toml` manifest.",
                "It accepts one UTF-8 JSON Decision Request on standard input.",
                "It returns one UTF-8 JSON Decision Result on standard output.",
            ],
            "sources": [
                "Decision Protocol v1: manifest-driven process and JSON transport",
                f"Decision Contract `{contract['decision_contract']}`",
            ],
            "test": f"{test_path}::test_decision_product_runtime",
            "excluded": [
                "A particular implementation language or framework",
                "HTTP or a conversational user interface",
            ],
        },
        {
            "id": evaluation_id,
            "title": "Evaluate KfW 458 applicant eligibility",
            "goal": "Return the specified applicant-eligibility outcome for each explicit Case.",
            "depends_on": [runtime_id],
            "obligations": [
                "All declared Conditions are evaluated as satisfied, violated, or unknown.",
                "A violated required Rule yields the declared negative outcome.",
                "A Fact Gap without a violated Rule yields the declared unknown outcome.",
                "Only all satisfied Rules yield the declared positive outcome.",
                "The eligible, ineligible, and unknown conformance Cases pass end to end.",
            ],
            "sources": [
                f"Decision Contract `{contract['decision_contract']}`",
                "`specs/`: Rules, Conditions, expected values, outcomes, and conformance Cases",
                "Decision Conventions v1: explicit requires-all aggregation",
            ],
            "test": f"{test_path}::test_declared_decision_outcome",
            "excluded": [
                "Heating-system or measure eligibility",
                "A funding amount, legal entitlement, or KfW approval",
            ],
        },
        {
            "id": "kfw-458.result-provenance",
            "title": "Explain the decision with source provenance",
            "goal": "Expose decisive Rules, source statements, and Fact Gaps in every result.",
            "depends_on": [evaluation_id],
            "obligations": [
                "Every decisive Rule identifies its Source Citation and Source Revision.",
                "Every cited source statement and locator is present in the Decision Result.",
                "Unknown results identify the exact missing Facts.",
                "Every result contains a human-readable explanation and the scope note.",
            ],
            "sources": [
                "`specs/`: Rule-to-Source Citation relations and source statements",
                "`specs/`: scope note",
                "Decision Conventions v1: decisive Rule and Fact Gap projection",
            ],
            "test": f"{test_path}::test_decision_result_provenance",
            "excluded": [
                "Automatic source-document ingestion",
                "A claim that the authored Spec completely transcribes the external source",
            ],
        },
    ]


def build_work_items(contract: dict, test_path: str) -> list[dict]:
    """Compile the contract into deterministic, independently verifiable work."""
    resource_id = re.sub(
        r"(?<!^)(?=[A-Z])", "-", contract["resource_name"]
    ).lower()
    runtime_id = f"{resource_id}.runtime"
    api_contract_id = f"{resource_id}.api.contract"
    storage_id = f"{resource_id}.storage.schema"
    storage_obligations = [
        f"The SQLite table `{contract['table_name']}` exists.",
        (
            f"The identifier column `{contract['id_column']}` has SQL type "
            f"`{contract['id_sql_type']}`"
            + (" and is the primary key." if contract["id_primary_key"] else ".")
        ),
    ]
    if contract["id_generated"]:
        storage_obligations.append(
            f"The `{contract['id_column']}` value is generated when omitted."
        )
    for field in contract["fields"]:
        requirement = f"The column `{field['name']}` has SQL type `{field['sql_type']}`"
        if field["required"]:
            requirement += " and does not allow NULL"
        storage_obligations.append(requirement + ".")

    response_fields = ", ".join(
        f"`{field['name']}`" for field in contract["fields"]
    )
    response_fields_obligation = (
        f"The response contains exactly the fields {response_fields}."
        if contract["closed"]
        else f"The response contains at least the fields {response_fields}."
    )
    return [
        {
            "id": runtime_id,
            "title": "Provide the product runtime interface",
            "goal": "Make the product startable through runtime protocol v1.",
            "depends_on": [],
            "obligations": [
                "The product can be started through its `product.toml` manifest.",
                "It listens on the host and port supplied by the runner.",
                (
                    "It publishes a self-contained OpenAPI 3.1 document as JSON "
                    "at the manifest path."
                ),
            ],
            "sources": [
                "Runtime protocol v1: process start, network address and OpenAPI readiness",
            ],
            "test": f"{test_path}::test_product_runtime",
            "excluded": [
                "A particular implementation language or web framework",
                "The contracted endpoint behavior",
            ],
        },
        {
            "id": api_contract_id,
            "title": f"Publish the contract for GET {contract['api_path']}",
            "goal": "Expose an OpenAPI description compatible with the HTTP contract.",
            "depends_on": [runtime_id],
            "obligations": [
                f"The document declares `GET {contract['api_path']}`.",
                (
                    f"The path parameter `{contract['path_parameter']['name']}` has "
                    f"OpenAPI type `{contract['path_parameter']['openapi_type']}`."
                ),
                (
                    f"Response `{contract['success_status']}` uses "
                    f"`{contract['media_type']}` and the contracted response schema."
                ),
            ],
            "sources": [
                "`specs/`: endpoint, path parameter, status and media type",
                "`specs/`: response Shape, fields and constraints",
                "Runtime protocol v1: `product.toml` and OpenAPI discovery",
            ],
            "test": f"{test_path}::test_openapi_matches_contract",
            "excluded": [
                "A particular implementation language or web framework",
                "Runtime behavior beyond publishing the declared contract",
            ],
        },
        {
            "id": storage_id,
            "title": f"Provide the `{contract['table_name']}` storage schema",
            "goal": (
                f"Make the contracted {contract['resource_name']} shape "
                "persistable in SQLite."
            ),
            "depends_on": [runtime_id],
            "obligations": storage_obligations,
            "sources": [
                "`specs/`: SQLite engine, table and identifier",
                "`specs/`: stored Shape, fields and constraints",
                "Runtime protocol v1: database path and readiness",
                "Compiler conventions v1: XSD-to-SQL mapping",
            ],
            "test": f"{test_path}::test_sql_table_matches_contract",
            "excluded": ["HTTP endpoint behavior"],
        },
        {
            "id": f"{resource_id}.query.by-id",
            "title": f"Provide GET {contract['api_path']}",
            "goal": (
                f"Return a stored {contract['resource_name']} through the "
                "contracted GET endpoint."
            ),
            "depends_on": [runtime_id, api_contract_id, storage_id],
            "obligations": [
                f"The endpoint `GET {contract['api_path']}` is available.",
                (
                f"A stored {contract['resource_name']} is returned with status "
                    f"`{contract['success_status']}` and media type "
                    f"`{contract['media_type']}`."
                ),
                response_fields_obligation,
                "The response values equal the stored values.",
                "The response satisfies every explicit Shape obligation.",
            ],
            "sources": [
                "`specs/`: endpoint-to-table relation and HTTP result",
                "`specs/`: response Shape",
                "Compiler conventions v1: SHACL-to-obligation mapping",
            ],
            "test": (
                f"{test_path}::test_get_endpoint_satisfies_explicit_obligations"
            ),
            "excluded": [
                f"Behavior for unknown {contract['resource_name']} identifiers"
            ],
        },
    ]


def render_issue(item: dict, product_path: str) -> str:
    """Render a work item without involving a language model."""
    dependencies = item["depends_on"] or [None]
    lines = [
        "<!-- Generated by Spec Compiler. Do not edit. -->",
        "",
        f"# {item['title']}",
        "",
        "## Goal",
        "",
        item["goal"],
        "",
        "## Dependencies",
        "",
        *(f"- `{dependency}`" if dependency else "- None" for dependency in dependencies),
        "",
        "## Obligations",
        "",
        *(f"- {obligation}" for obligation in item["obligations"]),
        "",
        "## Verification",
        "",
        "```console",
        f"uv run --extra dev pytest -q {item['test']}",
        "```",
        "",
        "## Sources",
        "",
        *(f"- {source}" for source in item["sources"]),
        "",
        "## Boundaries",
        "",
        "- Do not edit the product's `specs/`, `tests/`, or `generated/` directories.",
        f"- Implement product behavior under `{product_path}/`.",
        (
            "- Do not add implementation requirements that are absent from the specs "
            "or the documented runtime protocol."
        ),
        *(f"- Out of scope: {excluded}." for excluded in item["excluded"]),
        "",
    ]
    return "\n".join(lines)


TEST_TEMPLATE = '''# Generated by Spec Compiler. Do not edit.
import json
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import httpx
from openapi_spec_validator import OpenAPIV31SpecValidator, validate as validate_openapi
import pytest

from tools.contract_runtime import running_product

PRODUCT_ROOT = Path(__file__).parents[1]
OBLIGATIONS = __CONTRACT__
RESOURCE_VALUES = __RESOURCE_VALUES__
EXPECTED_OPENAPI = json.loads(
    (PRODUCT_ROOT / "generated" / "expected-openapi.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def running_api(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("contract-product") / "contract.sqlite3"
    with running_product(
        PRODUCT_ROOT,
        variables={"database_path": str(database_path)},
    ) as product:
        yield product, database_path


def _resolve(document, node):
    seen = set()
    while isinstance(node, dict) and "$ref" in node:
        reference = node["$ref"]
        assert reference.startswith("#/"), (
            f"Only local OpenAPI references are supported: {reference}"
        )
        assert reference not in seen, f"Circular OpenAPI reference: {reference}"
        seen.add(reference)
        target = document
        for part in reference[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        node = {**target, **{key: value for key, value in node.items() if key != "$ref"}}
    return node


def _assert_schema(actual_document, actual, expected):
    actual = _resolve(actual_document, actual)
    assert "allOf" not in actual, "Runtime protocol v1 requires direct schemas"
    for keyword in (
        "type",
        "format",
        "minLength",
        "exclusiveMinimum",
        "exclusiveMaximum",
    ):
        if keyword in expected:
            assert actual.get(keyword) == expected[keyword]

    if expected.get("type") != "object":
        return

    expected_properties = expected.get("properties", {})
    actual_properties = actual.get("properties", {})
    if expected.get("additionalProperties") is False:
        assert actual.get("additionalProperties") is False
        assert set(actual_properties) == set(expected_properties)
    else:
        assert set(expected_properties) <= set(actual_properties)

    assert set(actual.get("required", [])) >= set(expected.get("required", []))
    for name, expected_property in expected_properties.items():
        _assert_schema(actual_document, actual_properties[name], expected_property)


def _assert_openapi_document(document):
    assert isinstance(document, dict)
    assert document.get("openapi", "").startswith("3.1")
    stack = [document]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "$ref" in node:
                assert node["$ref"].startswith("#/"), (
                    "Runtime protocol v1 requires local OpenAPI references"
                )
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    validate_openapi(document, cls=OpenAPIV31SpecValidator)
    info = document.get("info")
    assert isinstance(info, dict)
    assert isinstance(info.get("title"), str) and info["title"]
    assert isinstance(info.get("version"), str) and info["version"]
    assert isinstance(document.get("paths"), dict)


def _assert_openapi_contract(actual, expected):
    _assert_openapi_document(actual)
    for path, expected_path in expected["paths"].items():
        assert path in actual.get("paths", {})
        actual_path = actual["paths"][path]
        for method, expected_operation in expected_path.items():
            assert method in actual_path
            actual_operation = actual_path[method]
            actual_parameters = [
                _resolve(actual, parameter)
                for parameter in (
                    actual_path.get("parameters", [])
                    + actual_operation.get("parameters", [])
                )
            ]
            for expected_parameter in expected_operation.get("parameters", []):
                candidates = [
                    parameter
                    for parameter in actual_parameters
                    if parameter.get("name") == expected_parameter["name"]
                    and parameter.get("in") == expected_parameter["in"]
                ]
                assert len(candidates) == 1
                actual_parameter = candidates[0]
                assert actual_parameter.get("required") is expected_parameter["required"]
                _assert_schema(
                    actual,
                    actual_parameter["schema"],
                    expected_parameter["schema"],
                )

            for status, expected_response in expected_operation["responses"].items():
                assert status in actual_operation.get("responses", {})
                actual_response = _resolve(
                    actual, actual_operation["responses"][status]
                )
                assert isinstance(actual_response.get("description"), str)
                for media_type, expected_media in expected_response["content"].items():
                    assert media_type in actual_response.get("content", {})
                    _assert_schema(
                        actual,
                        actual_response["content"][media_type]["schema"],
                        expected_media["schema"],
                    )


def test_product_runtime(running_api):
    product, _ = running_api
    response = httpx.get(product.openapi_url)
    response.raise_for_status()
    media_type = response.headers["content-type"].split(";", 1)[0]
    media_type = media_type.strip().lower()
    assert media_type == "application/json" or media_type.endswith("+json")
    _assert_openapi_document(response.json())


def test_openapi_matches_contract(running_api):
    product, _ = running_api
    response = httpx.get(product.openapi_url)
    response.raise_for_status()
    _assert_openapi_document(EXPECTED_OPENAPI)
    _assert_openapi_contract(response.json(), EXPECTED_OPENAPI)


def _insert_resource(database_path):
    fields = OBLIGATIONS["fields"]
    names = [field["name"] for field in fields]
    values = [
        float(RESOURCE_VALUES[name])
        if isinstance(RESOURCE_VALUES[name], Decimal)
        else RESOURCE_VALUES[name]
        for name in names
    ]
    expected_identifier = None
    if not OBLIGATIONS["id_generated"]:
        expected_identifier = 1
        names.insert(0, OBLIGATIONS["id_column"])
        values.insert(0, expected_identifier)
    placeholders = ", ".join("?" for _ in names)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                f"INSERT INTO {OBLIGATIONS['table_name']} ({', '.join(names)}) "
                f"VALUES ({placeholders})",
                values,
            )
    return cursor.lastrowid if OBLIGATIONS["id_generated"] else expected_identifier


def test_sql_table_matches_contract(running_api):
    _, database_path = running_api
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            f"PRAGMA table_info({OBLIGATIONS['table_name']})"
        ).fetchall()

    columns = {
        row[1]: {
            "type": row[2],
            "not_null": bool(row[3]),
            "primary_key": bool(row[5]),
        }
        for row in rows
    }
    identifier = columns[OBLIGATIONS["id_column"]]
    assert identifier["type"] == OBLIGATIONS["id_sql_type"]
    assert identifier["primary_key"] is OBLIGATIONS["id_primary_key"]
    for field in OBLIGATIONS["fields"]:
        actual = columns[field["name"]]
        assert actual["type"] == field["sql_type"]
        assert actual["not_null"] is field["required"]
    if OBLIGATIONS["id_generated"]:
        assert _insert_resource(database_path) is not None


def _assert_payload_obligations(payload):
    assert isinstance(payload, dict)
    fields = OBLIGATIONS["fields"]
    field_names = {field["name"] for field in fields}
    required_names = {field["name"] for field in fields if field["required"]}
    assert required_names <= set(payload)
    if OBLIGATIONS["closed"]:
        assert set(payload) <= field_names

    for field in fields:
        name = field["name"]
        if name not in payload:
            continue
        value = payload[name]
        if field["datatype"] == "http://www.w3.org/2001/XMLSchema#string":
            assert isinstance(value, str)
            if field["min_length"] is not None:
                assert len(value) >= field["min_length"]
        elif field["datatype"] == "http://www.w3.org/2001/XMLSchema#decimal":
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
            decimal_value = Decimal(str(value))
            if field["min_exclusive"] is not None:
                assert decimal_value > Decimal(str(field["min_exclusive"]))
            if field["max_exclusive"] is not None:
                assert decimal_value < Decimal(str(field["max_exclusive"]))
        elif field["datatype"] == "http://www.w3.org/2001/XMLSchema#integer":
            assert isinstance(value, int) and not isinstance(value, bool)
        else:
            raise AssertionError(f"Unsupported obligation datatype: {field['datatype']}")


def test_generated_assertions_cover_declared_obligations():
    valid = {
        name: float(value) if isinstance(value, Decimal) else value
        for name, value in RESOURCE_VALUES.items()
    }
    _assert_payload_obligations(valid)

    for field in OBLIGATIONS["fields"]:
        name = field["name"]
        if field["required"]:
            missing = dict(valid)
            missing.pop(name)
            with pytest.raises(AssertionError):
                _assert_payload_obligations(missing)

        invalid = dict(valid)
        if field["datatype"] == "http://www.w3.org/2001/XMLSchema#string":
            invalid[name] = 1
        elif field["datatype"] == "http://www.w3.org/2001/XMLSchema#decimal":
            invalid[name] = "not-a-number"
        elif field["datatype"] == "http://www.w3.org/2001/XMLSchema#integer":
            invalid[name] = "not-an-integer"
        with pytest.raises(AssertionError):
            _assert_payload_obligations(invalid)

        if field["min_length"] is not None and field["min_length"] > 0:
            too_short = dict(valid)
            too_short[name] = "" * field["min_length"]
            with pytest.raises(AssertionError):
                _assert_payload_obligations(too_short)
        if field["min_exclusive"] is not None:
            too_small = dict(valid)
            too_small[name] = float(field["min_exclusive"])
            with pytest.raises(AssertionError):
                _assert_payload_obligations(too_small)
        if field["max_exclusive"] is not None:
            too_large = dict(valid)
            too_large[name] = float(field["max_exclusive"])
            with pytest.raises(AssertionError):
                _assert_payload_obligations(too_large)

    if OBLIGATIONS["closed"]:
        unexpected = {**valid, "unspecified": True}
        with pytest.raises(AssertionError):
            _assert_payload_obligations(unexpected)

    if OBLIGATIONS["fields"]:
        first_field = OBLIGATIONS["fields"][0]
        original_closed = OBLIGATIONS["closed"]
        original_required = first_field["required"]
        try:
            OBLIGATIONS["closed"] = False
            first_field["required"] = False
            open_payload = {**valid, "unspecified": True}
            open_payload.pop(first_field["name"])
            _assert_payload_obligations(open_payload)
        finally:
            OBLIGATIONS["closed"] = original_closed
            first_field["required"] = original_required


def test_get_endpoint_satisfies_explicit_obligations(running_api):
    product, database_path = running_api
    fields = OBLIGATIONS["fields"]
    record_id = _insert_resource(database_path)

    parameter = OBLIGATIONS["path_parameter"]["name"]
    path = OBLIGATIONS["api_path"].replace("{" + parameter + "}", str(record_id))
    response = httpx.get(product.base_url + path)
    assert response.status_code == OBLIGATIONS["success_status"]
    actual_media_type = response.headers["content-type"].split(";", 1)[0]
    assert actual_media_type.strip().lower() == OBLIGATIONS["media_type"].lower()
    payload = response.json()
    _assert_payload_obligations(payload)
    for field in fields:
        actual = payload[field["name"]]
        expected = RESOURCE_VALUES[field["name"]]
        if isinstance(expected, Decimal):
            actual = Decimal(str(actual))
        assert actual == expected
'''


DECISION_TEST_TEMPLATE = '''# Generated by Spec Compiler. Do not edit.
import json
from pathlib import Path

import pytest

from tools.decision_runtime import run_decision

PRODUCT_ROOT = Path(__file__).parents[1]
CONTRACT = json.loads(
    (PRODUCT_ROOT / "generated" / "decision-contract.json").read_text(
        encoding="utf-8"
    )
)
RULES_BY_CONDITION = {
    rule["condition"]["id"]: rule for rule in CONTRACT["rules"]
}


def _set_json_pointer(document, pointer, value):
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _request_for_case(case):
    request = {
        "decision_contract": CONTRACT["decision_contract"],
        "rule_set_version": CONTRACT["rule_set"]["version"],
        "decision_date": case["decision_date"],
        "case": {},
    }
    for fact in case["facts"]:
        rule = RULES_BY_CONDITION[fact["condition"]]
        _set_json_pointer(
            request,
            rule["condition"]["input_json_pointer"],
            fact["value"],
        )
    return request


def _expected_result(case):
    facts = {fact["condition"]: fact["value"] for fact in case["facts"]}
    evaluations = []
    gaps = []
    for rule in CONTRACT["rules"]:
        condition = rule["condition"]
        actual = facts.get(condition["id"])
        if actual is None:
            state = "unknown"
            gaps.append(
                {
                    "condition": condition["id"],
                    "fact_property": condition["fact_property"],
                    "input_json_pointer": condition["input_json_pointer"],
                }
            )
        elif actual == condition["expected_boolean"]:
            state = "satisfied"
        else:
            state = "violated"
        evaluations.append(
            {
                "rule": rule["id"],
                "condition": condition["id"],
                "state": state,
            }
        )

    violated = [item["rule"] for item in evaluations if item["state"] == "violated"]
    unknown = [item["rule"] for item in evaluations if item["state"] == "unknown"]
    if violated:
        decisive = violated
        outcome_role = "negative"
    elif unknown:
        decisive = unknown
        outcome_role = "unknown"
    else:
        decisive = [rule["id"] for rule in CONTRACT["rules"]]
        outcome_role = "positive"
    outcome = CONTRACT["outcomes"][outcome_role]
    provenance = [
        {
            "rule": rule["id"],
            "source_citation": rule["source"]["citation"],
            "source_revision": rule["source"]["source_revision"],
            "source_locator": rule["source"]["locator"],
            "source_statement": rule["source"]["statement"],
        }
        for rule in CONTRACT["rules"]
        if rule["id"] in decisive
    ]
    return outcome, evaluations, decisive, gaps, provenance


def _run_case(case):
    result = run_decision(PRODUCT_ROOT, _request_for_case(case))
    assert result.returncode == 0, result.output
    return result.json_output()


def test_generated_contract_covers_all_declared_outcomes():
    assert {case["expected_outcome"] for case in CONTRACT["conformance_cases"]} == {
        outcome["id"] for outcome in CONTRACT["outcomes"].values()
    }
    assert all(rule["source"]["statement"] for rule in CONTRACT["rules"])
    assert all(rule["source"]["locator"] for rule in CONTRACT["rules"])


def test_decision_product_runtime():
    payload = _run_case(CONTRACT["conformance_cases"][0])
    assert isinstance(payload, dict)


@pytest.mark.parametrize(
    "case",
    CONTRACT["conformance_cases"],
    ids=lambda case: case["id"].rsplit("#", 1)[-1],
)
def test_declared_decision_outcome(case):
    payload = _run_case(case)
    outcome, evaluations, decisive, gaps, provenance = _expected_result(case)
    assert case["expected_outcome"] == outcome["id"]
    assert payload["decision_contract"] == CONTRACT["decision_contract"]
    assert payload["rule_set_version"] == CONTRACT["rule_set"]["version"]
    assert payload["decision_date"] == case["decision_date"]
    assert payload["outcome"] == outcome["code"]
    assert payload["outcome_id"] == outcome["id"]
    assert payload["condition_evaluations"] == evaluations
    assert payload["decisive_rules"] == decisive
    assert payload["fact_gaps"] == gaps


@pytest.mark.parametrize(
    "case",
    CONTRACT["conformance_cases"],
    ids=lambda case: case["id"].rsplit("#", 1)[-1],
)
def test_decision_result_provenance(case):
    payload = _run_case(case)
    outcome, _, _, _, provenance = _expected_result(case)
    assert payload["provenance"] == provenance
    assert isinstance(payload["explanation"], str) and payload["explanation"].strip()
    assert outcome["code"] in payload["explanation"].lower()
    assert payload["scope_note"] == CONTRACT["scope_note"]
'''


COMPILER_TEST_TEMPLATE = '''# Generated by Spec Compiler. Do not edit.
from pathlib import Path
import shutil

import pytest

from tools.compiler_runtime import run_compiler

COMPILER_ROOT = Path(__file__).parents[1]
CONTRACT = __CONTRACT__


def _snapshot(product_root):
    roots = [product_root / "generated", product_root / "tests"]
    return {
        path.relative_to(product_root).as_posix(): path.read_bytes()
        for root in roots
        if root.exists()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _copy_fixture(tmp_path, fixture):
    source = (COMPILER_ROOT / fixture["product"]).resolve()
    target = tmp_path / "input-product"
    shutil.copytree(source, target)
    return target


@pytest.mark.parametrize(
    "fixture",
    CONTRACT["conformance_fixtures"],
    ids=lambda fixture: fixture["name"],
)
def test_compiler_generates_declared_artifacts(tmp_path, fixture):
    product_root = _copy_fixture(tmp_path, fixture)
    result = run_compiler(COMPILER_ROOT, product_root)
    assert result.returncode == 0, result.output
    for pattern in fixture["generated_artifacts"]:
        assert list(product_root.glob(pattern)), f"No generated artifact matches {pattern}"


@pytest.mark.parametrize(
    "fixture",
    CONTRACT["conformance_fixtures"],
    ids=lambda fixture: fixture["name"],
)
def test_compiler_output_reaches_a_byte_identical_fixpoint(tmp_path, fixture):
    product_root = _copy_fixture(tmp_path, fixture)
    first = run_compiler(COMPILER_ROOT, product_root)
    assert first.returncode == 0, first.output
    first_snapshot = _snapshot(product_root)
    second = run_compiler(COMPILER_ROOT, product_root)
    assert second.returncode == 0, second.output
    assert _snapshot(product_root) == first_snapshot


def test_compiler_rejects_a_bundle_without_specs(tmp_path):
    product_root = tmp_path / "missing-specs"
    product_root.mkdir()
    result = run_compiler(COMPILER_ROOT, product_root)
    assert result.returncode != 0
    assert "No Turtle specs found" in result.output


@pytest.mark.parametrize(
    "fixture",
    CONTRACT["conformance_fixtures"],
    ids=lambda fixture: fixture["name"],
)
def test_bootstrapped_compiler_is_independently_executable(tmp_path, fixture):
    if not CONTRACT["bootstrap"]:
        return
    implementation = COMPILER_ROOT / CONTRACT["bootstrap"]["implementation_artifact"]
    assert implementation.is_file()
    expected_generation = CONTRACT["bootstrap"]["implementation_generation"]
    assert f"BOOTSTRAP_GENERATION = {expected_generation}" in implementation.read_text(
        encoding="utf-8"
    )

    fixture_root = _copy_fixture(tmp_path, fixture)
    result = run_compiler(COMPILER_ROOT, fixture_root)
    assert result.returncode == 0, result.output
    for pattern in fixture["generated_artifacts"]:
        assert list(fixture_root.glob(pattern)), f"No G1 artifact matches {pattern}"
'''


def build_compiler_work_items(contract: dict, test_path: str) -> list[dict]:
    items = [
        {
            "id": "toolchain.compiler.outputs",
            "title": "Generate the declared compiler artifacts",
            "goal": "Compile a valid Product Bundle through Compiler Protocol v1.",
            "depends_on": [],
            "obligations": [
                f"Input specs are discovered using `{contract['input_spec_pattern']}`.",
                *(
                    "The `"
                    f"{fixture['name']}` conformance fixture emits `"
                    f"{artifact}`."
                    for fixture in contract["conformance_fixtures"]
                    for artifact in fixture["generated_artifacts"]
                ),
            ],
            "sources": [
                "`specs/`: compiler input and generated artifact declarations",
                "Compiler Protocol v1: manifest-driven black-box invocation",
            ],
            "test": f"{test_path}::test_compiler_generates_declared_artifacts",
            "excluded": ["A particular compiler implementation language"],
        }
    ]
    if contract["deterministic_output"]:
        items.append(
            {
                "id": "toolchain.compiler.fixpoint",
                "title": "Reach a deterministic compiler fixpoint",
                "goal": "Produce byte-identical artifacts on consecutive compilations.",
                "depends_on": ["toolchain.compiler.outputs"],
                "obligations": [
                    "Two compilations of each conformance fixture produce "
                    "byte-identical generated and test files."
                ],
                "sources": ["`specs/`: deterministic output requirement"],
                "test": f"{test_path}::test_compiler_output_reaches_a_byte_identical_fixpoint",
                "excluded": ["Byte identity of product implementation source"],
            }
        )
    if contract["rejects_missing_specs"]:
        items.append(
            {
                "id": "toolchain.compiler.missing-specs",
                "title": "Reject a Product Bundle without specs",
                "goal": "Fail explicitly instead of compiling an unspecified product.",
                "depends_on": [],
                "obligations": [
                    "Compilation returns a non-zero exit status when no input specs exist.",
                    "The diagnostic identifies the absence of Turtle specs.",
                ],
                "sources": ["`specs/`: missing-spec rejection requirement"],
                "test": f"{test_path}::test_compiler_rejects_a_bundle_without_specs",
                "excluded": ["A prescribed exception or logging framework"],
            }
        )
    if contract["bootstrap"]:
        items.append(
            {
                "id": "toolchain.compiler.bootstrap",
                "title": "Execute the bootstrapped Spec Compiler generation",
                "goal": "Verify the independently materialized G1 compiler.",
                "depends_on": ["toolchain.compiler.outputs"],
                "obligations": [
                    "G0 materializes the declared G1 implementation artifact from its seed source.",
                    "G1 successfully compiles every conformance fixture through Compiler Protocol v1.",
                ],
                "sources": [
                    "`specs/`: Bootstrap Process, seed, strategy, and implementation artifact",
                    "Compiler Conventions v1: deterministic generation increment",
                ],
                "test": f"{test_path}::test_bootstrapped_compiler_is_independently_executable",
                "excluded": [
                    "Byte identity between compiler implementation generations",
                    "A required implementation language",
                    "Stochastic coding-agent orchestration",
                ],
            }
        )
    return items


def materialize_bootstrap_implementation(
    product_root: Path, bootstrap: dict | None
) -> Path | None:
    if bootstrap is None:
        return None
    source = Path(__file__).read_text(encoding="utf-8")
    current = f"BOOTSTRAP_GENERATION = {BOOTSTRAP_GENERATION}"
    successor = f"BOOTSTRAP_GENERATION = {BOOTSTRAP_GENERATION + 1}"
    if source.count(current) != 1:
        raise ValueError("Bootstrap seed has no unique generation marker")
    output = product_root / bootstrap["implementation_artifact"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source.replace(current, successor), encoding="utf-8")
    return output


def generate_compiler_contract(product_root: Path, product_path: str, contract: dict) -> list[Path]:
    tests_root = product_root / "tests"
    output = tests_root / "test_contract.py"
    test_path = (
        output.relative_to(ROOT).as_posix()
        if output.is_relative_to(ROOT)
        else output.relative_to(product_root).as_posix()
    )
    work_items = build_compiler_work_items(contract, test_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        COMPILER_TEST_TEMPLATE.replace(
            "__CONTRACT__", pformat(contract, sort_dicts=False)
        ),
        encoding="utf-8",
    )
    generated = product_root / "generated"
    issues = generated / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    graph_output = generated / "work-graph.json"
    graph_output.write_text(
        json.dumps(
            {
                "generator": "spec-compiler",
                "compiler_conventions_version": COMPILER_CONVENTIONS_VERSION,
                "compiler_protocol_version": 1,
                "bootstrap": contract["bootstrap"],
                "work_items": work_items,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for item in work_items:
        (issues / f"{item['id']}.md").write_text(
            render_issue(item, product_path), encoding="utf-8"
        )
    implementation = materialize_bootstrap_implementation(
        product_root, contract["bootstrap"]
    )
    return [
        output,
        graph_output,
        *(issues / f"{item['id']}.md" for item in work_items),
        *((implementation,) if implementation is not None else ()),
    ]


def generate_decision_contract(
    product_root: Path,
    product_path: str,
    model: ExplicitDecisionAndObligationModel,
) -> list[Path]:
    tests_root = product_root / "tests"
    test_output = tests_root / "test_contract.py"
    test_path = (
        test_output.relative_to(ROOT).as_posix()
        if test_output.is_relative_to(ROOT)
        else test_output.relative_to(product_root).as_posix()
    )
    contract = build_decision_contract(model)
    work_items = build_decision_work_items(contract, test_path)

    test_output.parent.mkdir(parents=True, exist_ok=True)
    test_output.write_text(DECISION_TEST_TEMPLATE, encoding="utf-8")
    generated = product_root / "generated"
    issues = generated / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    contract_output = generated / "decision-contract.json"
    contract_output.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    graph_output = generated / "work-graph.json"
    graph_output.write_text(
        json.dumps(
            {
                "generator": "spec-compiler",
                "compiler_conventions_version": COMPILER_CONVENTIONS_VERSION,
                "decision_conventions_version": DECISION_CONVENTIONS_VERSION,
                "decision_protocol_version": DECISION_PROTOCOL_VERSION,
                "work_items": work_items,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    issue_outputs = []
    for item in work_items:
        issue_output = issues / f"{item['id']}.md"
        issue_output.write_text(render_issue(item, product_path), encoding="utf-8")
        issue_outputs.append(issue_output)
    return [test_output, contract_output, graph_output, *issue_outputs]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        type=Path,
        required=True,
        help="Product directory below products/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    product_root = (
        args.product if args.product.is_absolute() else ROOT / args.product
    ).resolve()
    product_path = (
        product_root.relative_to(ROOT).as_posix()
        if product_root.is_relative_to(ROOT)
        else str(product_root)
    )
    graph = load_contract_graph(product_root)
    compiler_products = list(
        graph.subjects(DCTERMS.conformsTo, SCO.CompilerProtocolV1)
    )
    decision_products = list(
        graph.subjects(DCTERMS.conformsTo, SCO.DecisionProtocolV1)
    )
    http_contract = bool(
        list(graph.subjects(RDF.type, SCO.GetEndpoint))
        or list(graph.subjects(RDF.type, SCO.SqlTable))
    )
    profiles = [
        name
        for name, present in (
            ("compiler", bool(compiler_products)),
            ("decision", bool(decision_products)),
            ("http-sql", http_contract),
        )
        if present
    ]
    if len(profiles) != 1:
        raise ValueError(
            "Product specs must select exactly one executable profile; found "
            + (", ".join(profiles) if profiles else "none")
        )
    if compiler_products:
        contract = read_compiler_contract(product_root, graph)
        outputs = generate_compiler_contract(product_root, product_path, contract)
        for generated_output in outputs:
            print(f"Generated {generated_output.relative_to(product_root)}")
        return
    if decision_products:
        model = read_decision_model(product_root, graph)
        outputs = generate_decision_contract(product_root, product_path, model)
        for generated_output in outputs:
            print(f"Generated {generated_output.relative_to(product_root)}")
        return

    tests_root = product_root / "tests"
    output = tests_root / "test_contract.py"
    test_path = (
        output.relative_to(ROOT).as_posix()
        if output.is_relative_to(ROOT)
        else output.relative_to(product_root).as_posix()
    )

    obligations = read_obligation_model(product_root, graph)
    expected_openapi = build_openapi(obligations)
    work_items = build_work_items(obligations, test_path)
    article_values = {
        field["name"]: deterministic_value(field) for field in obligations["fields"]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        TEST_TEMPLATE.replace(
            "__CONTRACT__", pformat(obligations, sort_dicts=False)
        ).replace(
            "__RESOURCE_VALUES__", pformat(article_values, sort_dicts=False)
        ),
        encoding="utf-8",
    )

    generated = product_root / "generated"
    issues = generated / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    openapi_output = generated / "expected-openapi.json"
    openapi_output.write_text(
        json.dumps(expected_openapi, indent=2) + "\n",
        encoding="utf-8",
    )
    graph_output = generated / "work-graph.json"
    graph_output.write_text(
        json.dumps(
            {
                "generator": "spec-compiler",
                "compiler_conventions_version": COMPILER_CONVENTIONS_VERSION,
                "runtime_protocol_version": RUNTIME_PROTOCOL_VERSION,
                "work_items": work_items,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for item in work_items:
        (issues / f"{item['id']}.md").write_text(
            render_issue(item, product_path), encoding="utf-8"
        )

    outputs = [
        output,
        openapi_output,
        graph_output,
        *(issues / f"{item['id']}.md" for item in work_items),
    ]
    for generated_output in outputs:
        display_path = (
            generated_output.relative_to(ROOT)
            if generated_output.is_relative_to(ROOT)
            else generated_output.relative_to(product_root)
        )
        print(f"Generated {display_path}")


if __name__ == "__main__":
    main()

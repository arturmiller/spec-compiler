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

from jsonschema import Draft202012Validator, SchemaError
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, RDFS, SH, VANN, XSD

ROOT = Path(__file__).parents[1]
BOOTSTRAP_GENERATION = 0
COMPILER_CONVENTIONS_VERSION = 3
RUNTIME_PROTOCOL_VERSION = 1
DECISION_CONVENTIONS_VERSION = 1
DECISION_PROTOCOL_VERSION = 1
QUESTION_SELECTION_CONVENTIONS_VERSION = 1
EVIDENCE_EVALUATION_CONVENTIONS_VERSION = 1
VERSION_SELECTION_CONVENTIONS_VERSION = 1
OBLIGATION_EVALUATION_CONVENTIONS_VERSION = 1
HTTP_CONTRACT_CONVENTIONS_VERSION = 1
ONTOLOGY_MODULE_CONVENTIONS_VERSION = 1
# G1 receives an exact local RDF catalog snapshot, not a network resolver.
PACKAGED_ONTOLOGIES = None
SCO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/#")
SQLO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/sql/#")
DPO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/decision-protocol/#")
CCO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/compiler/#")
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
class FactQuestion:
    identifier: str
    text: str
    priority: int


@dataclass(frozen=True)
class DecisionCondition:
    identifier: str
    fact_property: str
    input_json_pointer: str
    expected_boolean: bool
    question: FactQuestion


@dataclass(frozen=True)
class Obligation:
    identifier: str
    text: str


@dataclass(frozen=True)
class DecisionRule:
    identifier: str
    condition: DecisionCondition
    source: DecisionSource
    obligations: tuple[Obligation, ...]


@dataclass(frozen=True)
class EvidenceApplicabilityCondition:
    identifier: str
    fact_property: str
    input_json_pointer: str
    expected_boolean: bool


@dataclass(frozen=True)
class EvidenceRequirement:
    identifier: str
    supports_condition: str
    applicability_conditions: tuple[EvidenceApplicabilityCondition, ...]
    required_evidence_type: str
    source: DecisionSource


@dataclass(frozen=True)
class RuleSetVersion:
    identifier: str
    version_label: str
    valid_from: str
    valid_until: str | None
    source: DecisionSource
    rules: tuple[DecisionRule, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]


@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_requirement: str
    accepted: bool


@dataclass(frozen=True)
class SuppliedEvidence:
    identifier: str
    evidence_type: str
    assessments: tuple[EvidenceAssessment, ...]


@dataclass(frozen=True)
class DecisionConformanceCase:
    identifier: str
    decision_date: str
    expected_rule_set_version: str
    expected_outcome: str
    facts: tuple[tuple[str, bool], ...]
    evidence: tuple[SuppliedEvidence, ...]
    expected_evidence_statuses: tuple[tuple[str, str], ...]
    expected_obligation_statuses: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class HttpMessage:
    identifier: str
    media_type: str
    body_schema_json: str
    body_pointer: str


@dataclass(frozen=True)
class HttpRequest(HttpMessage):
    body_required: bool


@dataclass(frozen=True)
class HttpResponse(HttpMessage):
    status_code: int
    description: str


@dataclass(frozen=True)
class HttpEndpoint:
    identifier: str
    path: str
    title: str
    version: str
    invokes_contract: str
    request: HttpRequest
    success_response: HttpResponse
    invalid_request_response: HttpResponse


@dataclass(frozen=True)
class ExplicitDecisionAndObligationModel:
    product: str
    decision_contract: str
    rule_set: str
    rule_set_versions: tuple[RuleSetVersion, ...]
    positive_outcome: str
    positive_outcome_code: str
    negative_outcome: str
    negative_outcome_code: str
    unknown_outcome: str
    unknown_outcome_code: str
    scope_note: str
    conformance_cases: tuple[DecisionConformanceCase, ...]
    question_flow_case: str
    version_selection_cases: tuple[str, ...]
    http_endpoint: HttpEndpoint | None


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


def ontology_sources() -> dict[str, str]:
    if PACKAGED_ONTOLOGIES is not None:
        return dict(PACKAGED_ONTOLOGIES)
    return {path.name: path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "ontology").glob("*.ttl"))}


def ontology_module(graph: Graph, *, role: str, source: str) -> dict:
    identities = sorted(set(graph.subjects(RDF.type, OWL.Ontology)), key=str)
    if len(identities) != 1 or not isinstance(identities[0], URIRef):
        raise ValueError(f"{source}: expected exactly one named owl:Ontology")
    identity = identities[0]
    namespace = str(one(graph, identity, VANN.preferredNamespaceUri))
    project = "https://arturmiller.github.io/spec-compiler/"
    expected = project + ("resources/" if role == "product" else "ontology/")
    if not str(identity).startswith(expected) or namespace != str(identity) + "#":
        raise ValueError(f"{source}: ontology identity and namespace do not match its {role} boundary")
    return {"graph": graph, "iri": str(identity), "namespace": namespace,
            "role": role, "source": source}


def reusable_ontology_modules() -> list[dict]:
    sources = ontology_sources()
    if not sources:
        raise ValueError("No local reusable ontology catalog available")
    return [ontology_module(Graph().parse(data=text, format="turtle"), role="reusable", source=name)
            for name, text in sorted(sources.items())]


def validate_ontology_modules(modules: list[dict]) -> None:
    """Ontology Module Conventions v1: explicit imports, closed local DAG, terminal product specs.

    Load definitions for ownership/import checking, never as additional authored
    product requirements. No import IRI is fetched and no OWL inference is run.
    """
    by_iri = {module["iri"]: module for module in modules}
    if len(by_iri) != len(modules):
        raise ValueError("Duplicate ontology identity")
    namespaces = [module["namespace"] for module in modules]
    if len(set(namespaces)) != len(namespaces):
        raise ValueError("Duplicate ontology namespace ownership")
    project = "https://arturmiller.github.io/spec-compiler/"
    project_roots = (project + "ontology/", project + "resources/")
    defined = {module["iri"]: set(module["graph"].subjects()) for module in modules}
    outgoing = {}
    for module in sorted(modules, key=lambda item: item["iri"]):
        graph, identity = module["graph"], module["iri"]
        imports = set()
        for subject, value in graph.subject_objects(OWL.imports):
            if str(subject) != identity or not isinstance(value, URIRef):
                raise ValueError(f"{identity}: owl:imports must belong to its ontology header and name an IRI")
            target = str(value)
            if target not in by_iri:
                raise ValueError(f"Unknown ontology import: {identity} -> {target}; only the local catalog is allowed")
            if by_iri[target]["role"] == "product":
                raise ValueError(f"Terminal product specification cannot be imported: {identity} -> {target}")
            imports.add(target)
        outgoing[identity] = imports
        used = set()
        for triple in graph:
            for value in triple:
                if not isinstance(value, URIRef):
                    continue
                owner = next((candidate for candidate in modules
                              if str(value).startswith(candidate["namespace"])), None)
                if owner is None:
                    if str(value).startswith(project_roots) and str(value) not in by_iri:
                        raise ValueError(f"Unknown or foreign product/ontology resource: {value}")
                    if str(value) in by_iri and str(value) != identity:
                        owner = by_iri[str(value)]
                    else:
                        continue
                if owner["iri"] == identity:
                    continue
                if owner["role"] == "product":
                    raise ValueError(f"Terminal product specification cannot be reused: {identity} -> {value}")
                if value not in defined[owner["iri"]]:
                    raise ValueError(f"Undefined ontology term: {value}")
                defining = triple[1] in (RDFS.label, RDFS.subClassOf, RDFS.domain, RDFS.range)
                defining = defining or (triple[1] == RDF.type and triple[2] in
                                         (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty))
                if value == triple[0] and defining:
                    raise ValueError(f"Foreign ontology term cannot be defined or amended here: {value}")
                used.add(owner["iri"])
        missing = sorted(used - imports)
        if missing:
            raise ValueError(f"Missing explicit owl:imports on {identity}: {', '.join(missing)}")
    complete, active = set(), []
    def visit(identity):
        if identity in active:
            cycle = active[active.index(identity):] + [identity]
            raise ValueError("Cyclic ontology imports: " + " -> ".join(cycle))
        if identity in complete:
            return
        active.append(identity)
        for target in sorted(outgoing[identity]):
            visit(target)
        active.pop()
        complete.add(identity)
    for identity in sorted(by_iri):
        visit(identity)


def validate_product_ontology(graph: Graph, source: str = "product specs") -> None:
    reject_legacy_compiler_terms(graph)
    modules = reusable_ontology_modules()
    modules.append(ontology_module(graph, role="product", source=source))
    validate_ontology_modules(modules)


def load_contract_graph(product_root: Path) -> Graph:
    specs_root = product_root / "specs"
    spec_files = sorted(specs_root.glob("*.ttl"))
    if not spec_files:
        raise ValueError(f"No Turtle specs found in {specs_root}")
    contract_graph = Graph()
    for spec_file in spec_files:
        contract_graph.parse(spec_file, format="turtle")
    validate_product_ontology(contract_graph, str(specs_root))
    return contract_graph


def read_obligation_model(
    product_root: Path, contract_graph: Graph | None = None
) -> dict:
    contract_graph = contract_graph or load_contract_graph(product_root)
    shapes = system = contract_graph
    endpoints = list(system.subjects(RDF.type, SCO.GetEndpoint))
    tables = list(system.subjects(RDF.type, SQLO.SqlTable))
    if len(endpoints) != 1 or len(tables) != 1:
        raise ValueError("Prototype expects exactly one GET endpoint and one SQL table")
    endpoint, table = endpoints[0], tables[0]
    shape = one(system, endpoint, SCO.returns)
    if one(system, table, SQLO.stores) != shape:
        raise ValueError("Endpoint and table must reference the same shape")
    if one(system, endpoint, SQLO.readsFrom) != table:
        raise ValueError("GET endpoint must explicitly identify the table it reads")
    if one(system, table, SQLO.databaseEngine) != SQLO.SQLite:
        raise ValueError("Prototype only has a declared mapping for sqlo:SQLite")
    rdf_class = one(shapes, shape, SH.targetClass)

    api_path = str(one(system, endpoint, SCO.path))
    path_parameter = one(system, endpoint, SCO.pathParameter)
    parameter_name = str(one(system, path_parameter, SCO.name))
    parameter_datatype = one(system, path_parameter, SH.datatype)
    if parameter_datatype not in OPENAPI_TYPES:
        raise ValueError(f"No OpenAPI type mapping for {parameter_datatype}")
    if f"{{{parameter_name}}}" not in api_path:
        raise ValueError(f"Path does not contain declared parameter {parameter_name!r}")

    table_name = sql_identifier(str(one(system, table, SQLO.tableName)))
    id_column = sql_identifier(str(one(system, table, SQLO.idColumn)))
    id_datatype = one(system, table, SQLO.idDatatype)
    if id_datatype not in SQL_TYPES:
        raise ValueError(f"No SQL type mapping for identifier {id_datatype}")
    if str(one(system, path_parameter, SQLO.mapsToColumn)) != id_column:
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
        "database_engine": local_name(one(system, table, SQLO.databaseEngine)),
        "table_name": table_name,
        "id_column": id_column,
        "id_sql_type": SQL_TYPES[id_datatype],
        "id_primary_key": bool(one(system, table, SQLO.idPrimaryKey).toPython()),
        "id_generated": bool(one(system, table, SQLO.idGenerated).toPython()),
        "rdf_class": str(rdf_class),
        "resource_name": local_name(rdf_class),
        "shape_name": local_name(shape),
        "closed": bool(optional(shapes, shape, SH.closed, False)),
        "fields": fields,
    }


LEGACY_COMPILER_TERMS = (
    "BootstrapProcess",
    "CompilerConformanceFixture",
    "CompilerProtocolV1",
    "EvolutionStrategy",
    "ModifyExistingImplementation",
    "TransformationContract",
    "bootstrapsProduct",
    "conformanceFixture",
    "deterministicOutput",
    "evolutionStrategy",
    "expectsArtifact",
    "fixtureProduct",
    "generatesArtifact",
    "generatesImplementationArtifact",
    "implementsContract",
    "inputSpecPattern",
    "rejectsMissingSpecs",
    "seedImplementation",
    "validFixtureProduct"
)


LEGACY_SEPARATED_TERMS = {
    "SqlTable": SQLO,
    "SQLite": SQLO,
    "readsFrom": SQLO,
    "stores": SQLO,
    "databaseEngine": SQLO,
    "idDatatype": SQLO,
    "mapsToColumn": SQLO,
    "tableName": SQLO,
    "idColumn": SQLO,
    "idPrimaryKey": SQLO,
    "idGenerated": SQLO,
    "DecisionProtocolV1": DPO,
    "implementsDecisionContract": DPO,
    "inputJsonPointer": DPO,
}


def reject_legacy_compiler_terms(graph: Graph) -> None:
    """Explicit compiler/module vocabulary migrations reject old IRIs, never infer aliases."""
    used = {value for triple in graph for value in triple if isinstance(value, URIRef)}
    retired = sorted(term for term in ('validFixtureProduct', 'generatesArtifact') if CCO[term] in used)
    if retired:
        raise ValueError(
            'Compiler Vocabulary Retirement v1: retired, unimplemented terms: '
            + ', '.join('cco:' + term for term in retired)
            + '; use cco:conformanceFixture with cco:fixtureProduct and cco:expectsArtifact'
        )
    separated = sorted(term for term in LEGACY_SEPARATED_TERMS if SCO[term] in used)
    if separated:
        replacements = ', '.join(f'sco:{term} -> {LEGACY_SEPARATED_TERMS[term][term]}' for term in separated)
        raise ValueError('Ontology Module Conventions v1: migrate separated vocabulary terms: ' + replacements)
    old = sorted((term for term in LEGACY_COMPILER_TERMS if SCO[term] in used))
    if old:
        replacements = ", ".join(f"sco:{term} -> cco:{term}" for term in old)
        raise ValueError(
            "Compiler vocabulary moved to " + str(CCO)
            + "; update the explicit spec IRIs: " + replacements
        )


def read_compiler_contract(product_root: Path, graph: Graph) -> dict:
    reject_legacy_compiler_terms(graph)
    products = list(graph.subjects(DCTERMS.conformsTo, CCO.CompilerProtocolV1))
    if len(products) != 1:
        raise ValueError(
            "Compiler profile expects exactly one product conforming to "
            "cco:CompilerProtocolV1"
        )
    product = products[0]
    if (product, RDF.type, SCHEMA.SoftwareApplication) not in graph:
        raise ValueError(
            "Compiler Protocol product must be a schema:SoftwareApplication"
        )
    contract = one(graph, product, CCO.implementsContract)
    if (contract, RDF.type, CCO.TransformationContract) not in graph:
        raise ValueError(
            "Compiler product contract must be a cco:TransformationContract"
        )
    fixture_nodes = sorted(
        graph.objects(contract, CCO.conformanceFixture), key=str
    )
    if not fixture_nodes:
        raise ValueError(
            "Spec compiler must declare at least one "
            "cco:CompilerConformanceFixture"
        )
    conformance_fixtures = []
    for fixture_node in fixture_nodes:
        if (fixture_node, RDF.type, CCO.CompilerConformanceFixture) not in graph:
            raise ValueError(
                f"Compiler conformance fixture {fixture_node} must be a "
                "cco:CompilerConformanceFixture"
            )
        fixture_product = str(one(graph, fixture_node, CCO.fixtureProduct))
        fixture_path = (product_root / fixture_product).resolve()
        if not fixture_path.is_dir():
            raise ValueError(
                f"Compiler fixture product does not exist: {fixture_path}"
            )
        artifacts = sorted(
            str(value)
            for value in graph.objects(fixture_node, CCO.expectsArtifact)
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
    bootstrap_processes = list(graph.subjects(CCO.bootstrapsProduct, product))
    if len(bootstrap_processes) > 1:
        raise ValueError(
            "Compiler product may declare at most one cco:BootstrapProcess"
        )
    bootstrap = None
    if bootstrap_processes:
        process = bootstrap_processes[0]
        if (process, RDF.type, CCO.BootstrapProcess) not in graph:
            raise ValueError(
                "Compiler bootstrap provenance must be a cco:BootstrapProcess"
            )
        seed = one(graph, process, CCO.seedImplementation)
        if (seed, RDF.type, SCHEMA.SoftwareApplication) not in graph:
            raise ValueError(
                "Bootstrap seed must be a schema:SoftwareApplication"
            )
        strategy = one(graph, process, CCO.evolutionStrategy)
        if strategy != CCO.ModifyExistingImplementation:
            raise ValueError(
                "Bootstrap evolution strategy must be "
                "cco:ModifyExistingImplementation"
            )
        implementation_artifact = str(
            one(graph, process, CCO.generatesImplementationArtifact)
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
        "protocol": str(CCO.CompilerProtocolV1),
        "input_spec_pattern": str(one(graph, contract, CCO.inputSpecPattern)),
        "conformance_fixtures": conformance_fixtures,
        "rejects_missing_specs": bool(
            one(graph, contract, CCO.rejectsMissingSpecs).toPython()
        ),
        "deterministic_output": bool(
            one(graph, contract, CCO.deterministicOutput).toPython()
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


def _positive_integer_value(value, description: str) -> int:
    converted = value.toPython()
    if (
        not isinstance(converted, int)
        or isinstance(converted, bool)
        or converted <= 0
    ):
        raise ValueError(f"{description} must be an xsd:positiveInteger")
    return converted


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


def _evidence_status_for_case(
    requirement: EvidenceRequirement,
    facts: tuple[tuple[str, bool], ...],
    evidence: tuple[SuppliedEvidence, ...],
) -> str:
    """Apply Evidence Evaluation Conventions v1 to one authored Case."""
    values = dict(facts)
    applicable = all(
        values.get(condition.identifier) == condition.expected_boolean
        for condition in requirement.applicability_conditions
    )
    if not applicable:
        return "not_applicable"
    for item in evidence:
        if item.evidence_type != requirement.required_evidence_type:
            continue
        if any(
            assessment.evidence_requirement == requirement.identifier
            and assessment.accepted
            for assessment in item.assessments
        ):
            return "fulfilled"
    return "missing"


def _obligation_status_for_case(
    rule: DecisionRule,
    facts: tuple[tuple[str, bool], ...],
) -> str:
    """Apply Obligation Evaluation Conventions v1 to one authored Case."""
    actual = dict(facts).get(rule.condition.identifier)
    if actual is None:
        return "unknown"
    if actual == rule.condition.expected_boolean:
        return "fulfilled"
    return "violated"


HTTP_SCHEMA_KEYWORDS = {
    "$schema", "title", "description", "type", "properties", "required",
    "additionalProperties", "items", "enum", "const", "minLength", "maxLength",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems",
    "maxItems", "uniqueItems", "minProperties", "maxProperties", "pattern",
    "format", "not", "allOf", "anyOf", "oneOf",
}


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _check_http_schema_keywords(schema) -> None:
    if isinstance(schema, bool):
        return
    unsupported = set(schema) - HTTP_SCHEMA_KEYWORDS
    if unsupported:
        raise ValueError(f"Unsupported HTTP JSON Schema keywords: {sorted(unsupported)}")
    if "$schema" in schema and schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("HTTP body schemas use JSON Schema draft 2020-12")
    if "format" in schema and schema["format"] != "date":
        raise ValueError("HTTP JSON Schema format support is limited to date")
    for child in schema.get("properties", {}).values():
        _check_http_schema_keywords(child)
    for keyword in ("items", "additionalProperties", "not"):
        if keyword in schema:
            _check_http_schema_keywords(schema[keyword])
    for keyword in ("allOf", "anyOf", "oneOf"):
        for child in schema.get(keyword, []):
            _check_http_schema_keywords(child)


def _read_http_message(graph: Graph, node, response: bool) -> HttpMessage:
    if not isinstance(node, URIRef):
        raise ValueError("HTTP messages must be named resources for deterministic provenance")
    expected_type = SCO.HttpResponse if response else SCO.HttpRequest
    if (node, RDF.type, expected_type) not in graph:
        raise ValueError(f"HTTP message {node} must be a {expected_type}")
    media_type = _required_text(graph, node, SCO.mediaType, "HTTP media type")
    if not re.fullmatch(r"application/(?:[a-z0-9!#$&^_.+-]+\+)?json", media_type):
        raise ValueError(f"HTTP body requires a JSON media type: {media_type}")
    value = one(graph, node, SCO.bodySchema)
    if not isinstance(value, Literal) or value.datatype != RDF.JSON:
        raise ValueError(f"HTTP body schema on {node} must be an rdf:JSON literal")
    try:
        body_schema = json.loads(
            str(value), object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
        Draft202012Validator.check_schema(body_schema)
    except (ValueError, SchemaError) as error:
        raise ValueError(f"Invalid HTTP body schema on {node}: {error}") from error
    _check_http_schema_keywords(body_schema)
    pointer = one(graph, node, SCO.bodyPointer)
    if not isinstance(pointer, Literal) or not isinstance(pointer.toPython(), str):
        raise ValueError("HTTP body pointer must be an explicit string")
    pointer = str(pointer)
    if (pointer and not pointer.startswith("/")) or re.search(r"~(?![01])", pointer):
        raise ValueError(f"Invalid HTTP body JSON Pointer: {pointer}")
    target = body_schema
    for part in pointer.split("/")[1:]:
        name = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or target.get("type") != "object":
            raise ValueError(f"HTTP body pointer must traverse explicit object schemas: {pointer}")
        if name not in target.get("properties", {}):
            raise ValueError(f"HTTP body pointer is absent from its schema: {pointer}")
        if response and set(target.get("required", [])) - {name}:
            raise ValueError(f"HTTP response wrapper requires unbound sibling fields: {pointer}")
        target = target["properties"][name]
    fields = {
        "identifier": str(node),
        "media_type": media_type,
        "body_schema_json": json.dumps(body_schema, sort_keys=True, ensure_ascii=False),
        "body_pointer": pointer,
    }
    if response:
        return HttpResponse(
            **fields,
            status_code=_positive_integer_value(one(graph, node, SCO.statusCode), "HTTP status"),
            description=_required_text(graph, node, DCTERMS.description, "HTTP response description"),
        )
    body_required = _boolean_value(one(graph, node, SCO.bodyRequired), "HTTP body required")
    if not body_required:
        raise ValueError("The supported HTTP contract profile requires a request body")
    return HttpRequest(**fields, body_required=body_required)


def read_http_endpoint(graph: Graph) -> HttpEndpoint | None:
    """Read explicit HTTP messages and bindings without product-specific mapping IRIs."""
    endpoints = set(graph.subjects(RDF.type, SCO.PostEndpoint)) | set(
        graph.subjects(SCO.invokesContract, None)
    )
    if not endpoints:
        return None
    if len(endpoints) != 1:
        raise ValueError("The HTTP contract profile requires exactly one POST endpoint")
    endpoint = next(iter(endpoints))
    if not isinstance(endpoint, URIRef):
        raise ValueError("HTTP endpoints must be named resources for deterministic provenance")
    if (endpoint, RDF.type, SCO.PostEndpoint) not in graph:
        raise ValueError(f"HTTP endpoint {endpoint} must be a sco:PostEndpoint")
    path = _required_text(graph, endpoint, SCO.path, "HTTP POST path")
    if not re.fullmatch(r"/[A-Za-z0-9/_.~-]*", path) or "//" in path:
        raise ValueError(f"HTTP POST path must be a fixed, safe path: {path}")
    contract = one(graph, endpoint, SCO.invokesContract)
    if not isinstance(contract, URIRef):
        raise ValueError("HTTP endpoint must invoke an explicit contract IRI")
    request = _read_http_message(graph, one(graph, endpoint, SCO.request), response=False)
    success = _read_http_message(graph, one(graph, endpoint, SCO.successResponse), response=True)
    invalid = _read_http_message(graph, one(graph, endpoint, SCO.invalidRequestResponse), response=True)
    if not 200 <= success.status_code < 300 or success.status_code in (204, 205):
        raise ValueError("HTTP success response must have a body-bearing 2xx status")
    if not 400 <= invalid.status_code < 500:
        raise ValueError("HTTP invalid-request response must have a 4xx status")
    return HttpEndpoint(
        identifier=str(endpoint), path=path,
        title=_required_text(graph, endpoint, DCTERMS.title, "HTTP API title"),
        version=_required_text(graph, endpoint, SCHEMA.version, "HTTP API version"),
        invokes_contract=str(contract), request=request,
        success_response=success, invalid_request_response=invalid,
    )


def read_decision_model(
    product_root: Path, graph: Graph | None = None
) -> ExplicitDecisionAndObligationModel:
    if graph is None:
        graph = load_contract_graph(product_root)
    reject_legacy_compiler_terms(graph)
    products = list(graph.subjects(DCTERMS.conformsTo, DPO.DecisionProtocolV1))
    if len(products) != 1:
        raise ValueError(
            "Decision profile expects exactly one product conforming to "
            "dpo:DecisionProtocolV1"
        )
    product = products[0]
    if (product, RDF.type, SCHEMA.SoftwareApplication) not in graph:
        raise ValueError("Decision Protocol product must be a schema:SoftwareApplication")
    contract = one(graph, product, DPO.implementsDecisionContract)
    if (contract, RDF.type, SDO.DecisionContract) not in graph:
        raise ValueError("Decision product contract must be an sdo:DecisionContract")
    http_endpoint = read_http_endpoint(graph)
    if http_endpoint is not None and http_endpoint.invokes_contract != str(contract):
        raise ValueError("HTTP endpoint must invoke the product's Decision Contract")
    if not _boolean_value(
        one(graph, contract, SDO.requiresAllRules),
        f"Decision Contract {contract} requiresAllRules",
    ):
        raise ValueError(
            "Decision Conventions v1 only supports contracts that explicitly "
            "require all Rules"
        )

    outcome_nodes = {
        "positive": one(graph, contract, SDO.positiveOutcome),
        "negative": one(graph, contract, SDO.negativeOutcome),
        "unknown": one(graph, contract, SDO.unknownOutcome),
    }
    outcomes = {str(node) for node in outcome_nodes.values()}
    if len(outcomes) != 3:
        raise ValueError("Decision Contract outcomes must be three distinct IRIs")
    for node in outcome_nodes.values():
        if (node, RDF.type, SDO.DecisionOutcome) not in graph:
            raise ValueError(f"Decision outcome {node} must be an sdo:DecisionOutcome")
    outcome_codes = {
        str(node): str(one(graph, node, SDO.outcomeCode))
        for node in outcome_nodes.values()
    }
    if len(set(outcome_codes.values())) != 3 or any(
        not SQL_IDENTIFIER.fullmatch(code) for code in outcome_codes.values()
    ):
        raise ValueError("Decision outcome codes must be distinct safe identifiers")
    positive_outcome = str(outcome_nodes["positive"])
    negative_outcome = str(outcome_nodes["negative"])
    unknown_outcome = str(outcome_nodes["unknown"])

    version_nodes = sorted(graph.objects(contract, SDO.usesRuleSetVersion), key=str)
    if not version_nodes:
        raise ValueError(
            f"Decision Contract {contract} must declare at least one "
            "sdo:usesRuleSetVersion"
        )
    condition_cache: dict[str, DecisionCondition] = {}
    evidence_condition_cache: dict[str, EvidenceApplicabilityCondition] = {}
    pointer_owners: dict[str, str] = {}
    question_owners: dict[str, str] = {}
    priority_owners: dict[int, str] = {}
    rule_ids: set[str] = set()
    obligation_ids: set[str] = set()
    requirement_ids: set[str] = set()
    parsed_versions = []
    stable_rule_set = None

    def read_rule_condition(condition_node) -> DecisionCondition:
        condition_id = str(condition_node)
        if condition_id in condition_cache:
            return condition_cache[condition_id]
        if (condition_node, RDF.type, SDO.Condition) not in graph:
            raise ValueError(
                f"Decision Rule Condition {condition_node} must be an sdo:Condition"
            )
        pointer = _json_pointer(str(one(graph, condition_node, DPO.inputJsonPointer)))
        if pointer in pointer_owners and pointer_owners[pointer] != condition_id:
            raise ValueError(f"Decision Conditions must not share input pointer {pointer}")
        pointer_owners[pointer] = condition_id
        question_nodes = list(graph.subjects(SDO.elicitsCondition, condition_node))
        if len(question_nodes) != 1:
            raise ValueError(
                f"Decision Condition {condition_node} must have exactly one "
                f"sdo:FactQuestion, got {len(question_nodes)}"
            )
        question_node = question_nodes[0]
        if (question_node, RDF.type, SDO.FactQuestion) not in graph:
            raise ValueError(f"Question {question_node} must be an sdo:FactQuestion")
        question_id = str(question_node)
        if question_id in question_owners and question_owners[question_id] != condition_id:
            raise ValueError(f"Fact Question {question_node} elicits more than one Condition")
        question_owners[question_id] = condition_id
        priority = _positive_integer_value(
            one(graph, question_node, SDO.questionPriority),
            f"Fact Question {question_node} priority",
        )
        if priority in priority_owners and priority_owners[priority] != condition_id:
            raise ValueError(
                "Fact Question priorities must be unique within a Decision "
                f"Contract: {priority}"
            )
        priority_owners[priority] = condition_id
        condition = DecisionCondition(
            identifier=condition_id,
            fact_property=str(one(graph, condition_node, SDO.factProperty)),
            input_json_pointer=pointer,
            expected_boolean=_boolean_value(
                one(graph, condition_node, SDO.expectedBoolean),
                f"Decision Condition {condition_node} expectedBoolean",
            ),
            question=FactQuestion(
                identifier=question_id,
                text=_required_text(
                    graph, question_node, SDO.questionText,
                    f"Fact Question {question_node} text",
                ),
                priority=priority,
            ),
        )
        condition_cache[condition_id] = condition
        return condition

    def read_evidence_condition(condition_node) -> EvidenceApplicabilityCondition:
        condition_id = str(condition_node)
        if condition_id in evidence_condition_cache:
            return evidence_condition_cache[condition_id]
        if condition_id in condition_cache:
            raise ValueError(
                f"Evidence applicability Condition {condition_node} must be "
                "separate from Rule Conditions"
            )
        if (condition_node, RDF.type, SDO.Condition) not in graph:
            raise ValueError(
                f"Evidence applicability member {condition_node} must be an "
                "sdo:Condition"
            )
        pointer = _json_pointer(str(one(graph, condition_node, DPO.inputJsonPointer)))
        if pointer in pointer_owners and pointer_owners[pointer] != condition_id:
            raise ValueError(f"Conditions must not share input pointer {pointer}")
        pointer_owners[pointer] = condition_id
        condition = EvidenceApplicabilityCondition(
            identifier=condition_id,
            fact_property=str(one(graph, condition_node, SDO.factProperty)),
            input_json_pointer=pointer,
            expected_boolean=_boolean_value(
                one(graph, condition_node, SDO.expectedBoolean),
                f"Evidence applicability Condition {condition_node} expectedBoolean",
            ),
        )
        evidence_condition_cache[condition_id] = condition
        return condition

    for version_node in version_nodes:
        if (version_node, RDF.type, SDO.RuleSetVersion) not in graph:
            raise ValueError(
                f"Decision Contract {contract} member {version_node} must be an "
                "sdo:RuleSetVersion"
            )
        rule_set = one(graph, version_node, DCTERMS.isVersionOf)
        if (rule_set, RDF.type, SDO.RuleSet) not in graph:
            raise ValueError(f"Rule Set Version {version_node} must identify an sdo:RuleSet")
        if stable_rule_set is None:
            stable_rule_set = rule_set
        elif rule_set != stable_rule_set:
            raise ValueError(
                f"Rule Set Versions on {contract} must identify one stable Rule Set"
            )
        version_label = _required_text(
            graph, version_node, OWL.versionInfo,
            f"Rule Set Version {version_node} version label",
        )
        valid_from = _date_value(
            one(graph, version_node, SDO.validFrom),
            f"Rule Set Version {version_node} validFrom",
        )
        until_values = list(graph.objects(version_node, SDO.validUntil))
        if len(until_values) > 1:
            raise ValueError(f"Expected at most one {SDO.validUntil} on {version_node}")
        valid_until = (
            _date_value(
                until_values[0], f"Rule Set Version {version_node} validUntil"
            )
            if until_values else None
        )
        if valid_until is not None and valid_until <= valid_from:
            raise ValueError(
                f"Rule Set Version {version_node} validUntil must be after validFrom"
            )
        version_source = _read_decision_source(
            graph, one(graph, version_node, SDO.versionSourceCitation)
        )
        if version_source.valid_from != valid_from:
            raise ValueError(
                f"Rule Set Version {version_node} validFrom must equal its "
                "Source Revision validFrom"
            )

        rules = []
        version_conditions = set()
        for rule_node in sorted(graph.objects(version_node, SDO.hasRule), key=str):
            if (rule_node, RDF.type, SDO.Rule) not in graph:
                raise ValueError(f"Rule Set member {rule_node} must be an sdo:Rule")
            rule_id = str(rule_node)
            if rule_id in rule_ids:
                raise ValueError(f"Decision Rule {rule_node} belongs to more than one version")
            rule_ids.add(rule_id)
            condition = read_rule_condition(one(graph, rule_node, SDO.condition))
            if condition.identifier in version_conditions:
                raise ValueError(
                    f"Decision Condition {condition.identifier} is used by more "
                    f"than one Rule in Rule Set Version {version_node}"
                )
            version_conditions.add(condition.identifier)
            source = _read_decision_source(
                graph, one(graph, rule_node, SDO.sourceCitation)
            )
            obligations = []
            for obligation_node in sorted(
                graph.objects(rule_node, SDO.imposesObligation), key=str
            ):
                if (obligation_node, RDF.type, SDO.Obligation) not in graph:
                    raise ValueError(
                        f"Rule obligation {obligation_node} must be an sdo:Obligation"
                    )
                obligation_id = str(obligation_node)
                if obligation_id in obligation_ids:
                    raise ValueError(
                        f"Obligation {obligation_node} belongs to more than one Rule"
                    )
                obligation_ids.add(obligation_id)
                obligations.append(
                    Obligation(
                        identifier=obligation_id,
                        text=_required_text(
                            graph,
                            obligation_node,
                            SDO.obligationText,
                            f"Obligation {obligation_node} text",
                        ),
                    )
                )
            rules.append(DecisionRule(rule_id, condition, source, tuple(obligations)))
        if not rules:
            raise ValueError(f"Rule Set Version {version_node} must contain at least one Rule")

        requirements = []
        for requirement_node in sorted(
            graph.objects(version_node, SDO.hasEvidenceRequirement), key=str
        ):
            if (requirement_node, RDF.type, SDO.EvidenceRequirement) not in graph:
                raise ValueError(
                    f"Rule Set Version member {requirement_node} must be an "
                    "sdo:EvidenceRequirement"
                )
            requirement_id = str(requirement_node)
            if requirement_id in requirement_ids:
                raise ValueError(
                    f"Evidence Requirement {requirement_node} belongs to more than one version"
                )
            requirement_ids.add(requirement_id)
            supports = str(one(graph, requirement_node, SDO.supportsCondition))
            if supports not in version_conditions:
                raise ValueError(
                    f"Evidence Requirement {requirement_node} must support a "
                    "Condition used by its Rule Set Version"
                )
            evidence_type = one(graph, requirement_node, SDO.requiredEvidenceType)
            if not isinstance(evidence_type, URIRef):
                raise ValueError(f"Required Evidence type {evidence_type} must be an IRI")
            applicability_nodes = sorted(
                graph.objects(requirement_node, SDO.applicabilityCondition), key=str
            )
            if not applicability_nodes:
                raise ValueError(
                    f"Evidence Requirement {requirement_node} must declare at "
                    "least one applicability Condition"
                )
            source = _read_decision_source(
                graph, one(graph, requirement_node, SDO.evidenceSourceCitation)
            )
            requirements.append(
                EvidenceRequirement(
                    identifier=requirement_id,
                    supports_condition=supports,
                    applicability_conditions=tuple(
                        read_evidence_condition(node) for node in applicability_nodes
                    ),
                    required_evidence_type=str(evidence_type),
                    source=source,
                )
            )
        parsed_versions.append(
            RuleSetVersion(
                identifier=str(version_node),
                version_label=version_label,
                valid_from=valid_from,
                valid_until=valid_until,
                source=version_source,
                rules=tuple(rules),
                evidence_requirements=tuple(requirements),
            )
        )

    versions = tuple(sorted(parsed_versions, key=lambda item: (item.valid_from, item.identifier)))
    labels = [item.version_label for item in versions]
    if len(labels) != len(set(labels)):
        raise ValueError("Rule Set Version labels must be unique within a Decision Contract")
    for earlier, later in zip(versions, versions[1:]):
        if earlier.valid_until is None or later.valid_from < earlier.valid_until:
            raise ValueError(
                "Rule Set Versions have overlapping validity periods: "
                f"{earlier.identifier} and {later.identifier}"
            )

    def version_for_date(value: str, context: str) -> RuleSetVersion:
        applicable = [
            item for item in versions
            if value >= item.valid_from
            and (item.valid_until is None or value < item.valid_until)
        ]
        if len(applicable) != 1:
            raise ValueError(
                f"Decision Date {value} for {context} matches "
                f"{len(applicable)} Rule Set Versions of Rule Set {stable_rule_set}; "
                "declare non-overlapping validity information that selects exactly one"
            )
        return applicable[0]

    all_conditions = set(condition_cache) | set(evidence_condition_cache)
    all_requirement_ids = {
        requirement.identifier
        for version in versions
        for requirement in version.evidence_requirements
    }
    cases = []
    question_flow_case_ids = []
    version_selection_case_ids = []
    for case_node in sorted(graph.objects(contract, SDO.hasConformanceCase), key=str):
        if (case_node, RDF.type, SDO.ConformanceCase) not in graph:
            raise ValueError(f"Decision conformance case {case_node} must be an sdo:ConformanceCase")
        if one(graph, case_node, SDO.forDecisionContract) != contract:
            raise ValueError(f"Conformance case {case_node} must reference its Decision Contract")
        date_values = list(graph.objects(case_node, SDO.decisionDate))
        if len(date_values) != 1:
            raise ValueError(
                f"Conformance Case {case_node} must declare exactly one Decision Date; "
                f"got {len(date_values)}"
            )
        decision_date = _date_value(
            date_values[0], f"Conformance case {case_node} decisionDate"
        )
        selected_version = version_for_date(decision_date, f"Conformance Case {case_node}")
        expected_version = one(graph, case_node, SDO.expectsRuleSetVersion)
        if str(expected_version) != selected_version.identifier:
            raise ValueError(
                f"Conformance Case {case_node} expects Rule Set Version "
                f"{expected_version}, but Version Selection Conventions v1 select "
                f"{selected_version.identifier} from its Decision Date"
            )
        expected_outcome = str(one(graph, case_node, SDO.expectsOutcome))
        if expected_outcome not in outcomes:
            raise ValueError(f"Conformance case {case_node} uses an undeclared outcome")

        facts = []
        fact_conditions = set()
        for fact in graph.objects(case_node, SDO.hasFact):
            if (fact, RDF.type, SDO.CaseFact) not in graph:
                raise ValueError(f"Conformance case fact {fact} must be an sdo:CaseFact")
            condition = str(one(graph, fact, SDO.forCondition))
            if condition not in all_conditions:
                raise ValueError(
                    f"Conformance case {case_node} references unknown Condition {condition}"
                )
            if condition in fact_conditions:
                raise ValueError(
                    f"Conformance case {case_node} has conflicting Facts for {condition}"
                )
            fact_conditions.add(condition)
            facts.append(
                (condition, _boolean_value(
                    one(graph, fact, SDO.booleanValue),
                    f"Conformance case {case_node} Fact value",
                ))
            )
        immutable_facts = tuple(sorted(facts))

        evidence = []
        evidence_ids = set()
        for evidence_node in sorted(graph.objects(case_node, SDO.hasEvidence), key=str):
            if (evidence_node, RDF.type, SDO.Evidence) not in graph:
                raise ValueError(f"Supplied Evidence {evidence_node} must be an sdo:Evidence")
            evidence_id = str(evidence_node)
            if evidence_id in evidence_ids:
                raise ValueError(f"Conformance case {case_node} supplies duplicate Evidence {evidence_node}")
            evidence_ids.add(evidence_id)
            evidence_type = one(graph, evidence_node, SDO.evidenceType)
            if not isinstance(evidence_type, URIRef):
                raise ValueError(f"Supplied Evidence type {evidence_type} must be an IRI")
            assessments = []
            assessed_requirements = set()
            for assessment_node in sorted(
                graph.objects(evidence_node, SDO.hasEvidenceAssessment), key=str
            ):
                if (assessment_node, RDF.type, SDO.EvidenceAssessment) not in graph:
                    raise ValueError(
                        f"Evidence assessment {assessment_node} must be an sdo:EvidenceAssessment"
                    )
                assessed = str(one(graph, assessment_node, SDO.assessesEvidenceRequirement))
                if assessed not in all_requirement_ids:
                    raise ValueError(
                        f"Evidence assessment {assessment_node} references an unknown Evidence Requirement"
                    )
                if assessed in assessed_requirements:
                    raise ValueError(
                        f"Evidence {evidence_node} has conflicting assessments for {assessed}"
                    )
                assessed_requirements.add(assessed)
                assessments.append(EvidenceAssessment(
                    evidence_requirement=assessed,
                    accepted=_boolean_value(
                        one(graph, assessment_node, SDO.accepted),
                        f"Evidence assessment {assessment_node} accepted",
                    ),
                ))
            evidence.append(SuppliedEvidence(
                identifier=evidence_id,
                evidence_type=str(evidence_type),
                assessments=tuple(assessments),
            ))
        immutable_evidence = tuple(evidence)

        selected_requirement_ids = {
            requirement.identifier
            for requirement in selected_version.evidence_requirements
        }
        statuses = []
        seen_expectations = set()
        status_by_node = {
            str(SDO.EvidenceRequirementFulfilled): "fulfilled",
            str(SDO.EvidenceRequirementMissing): "missing",
            str(SDO.EvidenceRequirementNotApplicable): "not_applicable",
        }
        for expectation_node in graph.objects(case_node, SDO.hasEvidenceExpectation):
            if (expectation_node, RDF.type, SDO.EvidenceExpectation) not in graph:
                raise ValueError(
                    f"Evidence expectation {expectation_node} must be an sdo:EvidenceExpectation"
                )
            requirement_id = str(one(
                graph, expectation_node, SDO.expectsEvidenceRequirement
            ))
            if requirement_id not in selected_requirement_ids:
                raise ValueError(
                    f"Evidence expectation {expectation_node} references an "
                    "Evidence Requirement outside the selected Rule Set Version"
                )
            if requirement_id in seen_expectations:
                raise ValueError(
                    f"Conformance case {case_node} has conflicting Evidence "
                    f"Expectations for {requirement_id}"
                )
            seen_expectations.add(requirement_id)
            status_node = str(one(graph, expectation_node, SDO.expectedEvidenceStatus))
            if status_node not in status_by_node:
                raise ValueError(
                    f"Evidence expectation {expectation_node} uses an unsupported status"
                )
            statuses.append((requirement_id, status_by_node[status_node]))
        if seen_expectations != selected_requirement_ids:
            missing = sorted(selected_requirement_ids - seen_expectations)
            raise ValueError(
                f"Conformance case {case_node} lacks Evidence Expectations for {missing}"
            )
        immutable_statuses = tuple(sorted(statuses))
        for requirement in selected_version.evidence_requirements:
            expected_status = dict(immutable_statuses)[requirement.identifier]
            derived_status = _evidence_status_for_case(
                requirement, immutable_facts, immutable_evidence
            )
            if expected_status != derived_status:
                raise ValueError(
                    f"Conformance case {case_node} expects Evidence Requirement "
                    f"status {expected_status}, but Evidence Evaluation "
                    f"Conventions v1 derive {derived_status}"
                )

        selected_obligations = {
            obligation.identifier: (obligation, rule)
            for rule in selected_version.rules
            for obligation in rule.obligations
        }
        obligation_statuses = []
        seen_obligation_expectations = set()
        obligation_status_by_node = {
            str(SDO.ObligationFulfilled): "fulfilled",
            str(SDO.ObligationViolated): "violated",
            str(SDO.ObligationUnknown): "unknown",
        }
        for expectation_node in graph.objects(
            case_node, SDO.hasObligationExpectation
        ):
            if (expectation_node, RDF.type, SDO.ObligationExpectation) not in graph:
                raise ValueError(
                    f"Obligation expectation {expectation_node} must be an "
                    "sdo:ObligationExpectation"
                )
            obligation_id = str(
                one(graph, expectation_node, SDO.expectsObligation)
            )
            if obligation_id not in selected_obligations:
                raise ValueError(
                    f"Obligation expectation {expectation_node} references an "
                    "Obligation outside the selected Rule Set Version"
                )
            if obligation_id in seen_obligation_expectations:
                raise ValueError(
                    f"Conformance case {case_node} has conflicting Obligation "
                    f"Expectations for {obligation_id}"
                )
            seen_obligation_expectations.add(obligation_id)
            status_node = str(
                one(graph, expectation_node, SDO.expectedObligationStatus)
            )
            if status_node not in obligation_status_by_node:
                raise ValueError(
                    f"Obligation expectation {expectation_node} uses an "
                    "unsupported status"
                )
            obligation_statuses.append(
                (obligation_id, obligation_status_by_node[status_node])
            )
        if seen_obligation_expectations != set(selected_obligations):
            missing = sorted(
                set(selected_obligations) - seen_obligation_expectations
            )
            raise ValueError(
                f"Conformance case {case_node} lacks Obligation Expectations "
                f"for {missing}"
            )
        immutable_obligation_statuses = tuple(sorted(obligation_statuses))
        for obligation_id, (_, rule) in selected_obligations.items():
            expected_status = dict(immutable_obligation_statuses)[obligation_id]
            derived_status = _obligation_status_for_case(rule, immutable_facts)
            if expected_status != derived_status:
                raise ValueError(
                    f"Conformance case {case_node} expects Obligation "
                    f"{obligation_id} status {expected_status}, but Obligation "
                    f"Evaluation Conventions v1 derive {derived_status}"
                )
        derived_outcome = _decision_outcome_for_case(
            selected_version.rules, immutable_facts,
            positive_outcome=positive_outcome,
            negative_outcome=negative_outcome,
            unknown_outcome=unknown_outcome,
        )
        if derived_outcome != expected_outcome:
            raise ValueError(
                f"Conformance case {case_node} expects {expected_outcome}, but "
                f"Decision Conventions v1 derives {derived_outcome}"
            )
        cases.append(DecisionConformanceCase(
            identifier=str(case_node),
            decision_date=decision_date,
            expected_rule_set_version=selected_version.identifier,
            expected_outcome=expected_outcome,
            facts=immutable_facts,
            evidence=immutable_evidence,
            expected_evidence_statuses=immutable_statuses,
            expected_obligation_statuses=immutable_obligation_statuses,
        ))
        if (case_node, RDF.type, SDO.QuestionFlowCase) in graph:
            question_flow_case_ids.append(str(case_node))
        if (case_node, RDF.type, SDO.VersionSelectionCase) in graph:
            version_selection_case_ids.append(str(case_node))

    immutable_cases = tuple(cases)
    if not immutable_cases:
        raise ValueError("Decision Contract must declare conformance cases for all outcomes")
    covered_outcomes = {case.expected_outcome for case in immutable_cases}
    if covered_outcomes != outcomes:
        raise ValueError(
            f"Decision Contract conformance cases do not cover outcomes: "
            f"{sorted(outcomes - covered_outcomes)}"
        )
    required_statuses = {"fulfilled", "missing", "not_applicable"}
    for version in versions:
        selected_cases = [
            case for case in immutable_cases
            if case.expected_rule_set_version == version.identifier
        ]
        for requirement in version.evidence_requirements:
            covered = {
                status
                for case in selected_cases
                for requirement_id, status in case.expected_evidence_statuses
                if requirement_id == requirement.identifier
            }
            if covered != required_statuses:
                raise ValueError(
                    f"Conformance cases do not cover Evidence Requirement "
                    f"{requirement.identifier} statuses: {sorted(required_statuses - covered)}"
                )
    obligations = {
        obligation.identifier
        for version in versions
        for rule in version.rules
        for obligation in rule.obligations
    }
    if obligations:
        covered_obligation_statuses = {
            status
            for case in immutable_cases
            for _, status in case.expected_obligation_statuses
        }
        required_obligation_statuses = {"fulfilled", "violated", "unknown"}
        if covered_obligation_statuses != required_obligation_statuses:
            raise ValueError(
                "Conformance cases do not cover all Obligation statuses: "
                f"{sorted(required_obligation_statuses - covered_obligation_statuses)}"
            )
    if len(question_flow_case_ids) != 1:
        raise ValueError(
            "Decision Contract must declare exactly one sdo:QuestionFlowCase, "
            f"got {len(question_flow_case_ids)}"
        )
    question_flow_case = next(
        case for case in immutable_cases
        if case.identifier == question_flow_case_ids[0]
    )
    question_version = next(
        version for version in versions
        if version.identifier == question_flow_case.expected_rule_set_version
    )
    if question_flow_case.expected_outcome != positive_outcome:
        raise ValueError("Question Flow Case must have the Decision Contract's positive outcome")
    question_conditions = {rule.condition.identifier for rule in question_version.rules}
    if not question_conditions.issubset(
        {condition for condition, _ in question_flow_case.facts}
    ):
        raise ValueError("Question Flow Case must supply one Fact for every Rule Condition")

    selection_cases = [
        case for case in immutable_cases
        if case.identifier in version_selection_case_ids
    ]
    has_historical_pair = any(
        left.facts == right.facts
        and left.evidence == right.evidence
        and left.expected_rule_set_version != right.expected_rule_set_version
        and left.expected_outcome != right.expected_outcome
        for index, left in enumerate(selection_cases)
        for right in selection_cases[index + 1:]
    )
    if version_selection_case_ids and not has_historical_pair:
        raise ValueError(
            "Version Selection Conventions v1 require two Version Selection "
            "Cases with identical facts, different selected versions, and "
            "different outcomes"
        )

    return ExplicitDecisionAndObligationModel(
        product=str(product),
        decision_contract=str(contract),
        rule_set=str(stable_rule_set),
        rule_set_versions=versions,
        positive_outcome=positive_outcome,
        positive_outcome_code=outcome_codes[positive_outcome],
        negative_outcome=negative_outcome,
        negative_outcome_code=outcome_codes[negative_outcome],
        unknown_outcome=unknown_outcome,
        unknown_outcome_code=outcome_codes[unknown_outcome],
        scope_note=_required_text(
            graph, contract, SDO.scopeNote, "Decision Contract scope note"
        ),
        conformance_cases=immutable_cases,
        question_flow_case=question_flow_case.identifier,
        version_selection_cases=tuple(version_selection_case_ids),
        http_endpoint=http_endpoint,
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


def build_http_openapi(endpoint: HttpEndpoint) -> dict:
    """Render authored HTTP schemas and bindings without inventing body fields."""
    return {
        "openapi": "3.1.0",
        "info": {"title": endpoint.title, "version": endpoint.version},
        "paths": {
            endpoint.path: {
                "post": {
                    "x-spec-compiler-binding": {
                        "invokes_contract": endpoint.invokes_contract,
                        "request_pointer": endpoint.request.body_pointer,
                        "success_status": endpoint.success_response.status_code,
                        "result_pointer": endpoint.success_response.body_pointer,
                        "invalid_status": endpoint.invalid_request_response.status_code,
                        "error_pointer": endpoint.invalid_request_response.body_pointer,
                    },
                    "requestBody": {
                        "required": endpoint.request.body_required,
                        "content": {
                            endpoint.request.media_type: {
                                "schema": json.loads(endpoint.request.body_schema_json)
                            }
                        },
                    },
                    "responses": {
                        str(response.status_code): {
                            "description": response.description,
                            "content": {
                                response.media_type: {
                                    "schema": json.loads(response.body_schema_json)
                                }
                            },
                        }
                        for response in (
                            endpoint.success_response, endpoint.invalid_request_response
                        )
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

    def remember_source(source: DecisionSource) -> None:
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

    def render_source(source: DecisionSource) -> dict:
        remember_source(source)
        return {
            "citation": source.citation,
            "source_revision": source.source_revision,
            "locator": source.locator,
            "statement": source.statement,
        }

    def render_rule(rule: DecisionRule) -> dict:
        source = rule.source
        return {
            "id": rule.identifier,
            "condition": {
                "id": rule.condition.identifier,
                "fact_property": rule.condition.fact_property,
                "input_json_pointer": rule.condition.input_json_pointer,
                "expected_boolean": rule.condition.expected_boolean,
                "question": {
                    "id": rule.condition.question.identifier,
                    "text": rule.condition.question.text,
                    "priority": rule.condition.question.priority,
                },
            },
            "source": render_source(source),
            "obligations": [
                {"id": obligation.identifier, "text": obligation.text}
                for obligation in rule.obligations
            ],
        }

    def render_requirement(requirement: EvidenceRequirement) -> dict:
        source = requirement.source
        return {
            "id": requirement.identifier,
            "supports_condition": requirement.supports_condition,
            "applicability_conditions": [
                {
                    "id": condition.identifier,
                    "fact_property": condition.fact_property,
                    "input_json_pointer": condition.input_json_pointer,
                    "expected_boolean": condition.expected_boolean,
                }
                for condition in requirement.applicability_conditions
            ],
            "required_evidence_type": requirement.required_evidence_type,
            "source": render_source(source),
        }

    versions = []
    for version in model.rule_set_versions:
        version_source = render_source(version.source)
        versions.append(
            {
                "id": version.identifier,
                "version": version.version_label,
                "valid_from": version.valid_from,
                "valid_until": version.valid_until,
                "source": version_source,
                "requires_all_rules": True,
                "rules": [render_rule(rule) for rule in version.rules],
                "evidence_requirements": [
                    render_requirement(requirement)
                    for requirement in version.evidence_requirements
                ],
            }
        )

    return {
        "profile": "decision-obligation-v1",
        "decision_protocol_version": DECISION_PROTOCOL_VERSION,
        "decision_conventions_version": DECISION_CONVENTIONS_VERSION,
        "question_selection_conventions_version": (
            QUESTION_SELECTION_CONVENTIONS_VERSION
        ),
        "evidence_evaluation_conventions_version": (
            EVIDENCE_EVALUATION_CONVENTIONS_VERSION
        ),
        "version_selection_conventions_version": (
            VERSION_SELECTION_CONVENTIONS_VERSION
        ),
        "obligation_evaluation_conventions_version": (
            OBLIGATION_EVALUATION_CONVENTIONS_VERSION
        ),
        "product": model.product,
        "decision_contract": model.decision_contract,
        "rule_set": {
            "id": model.rule_set,
            "versions": versions,
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
        "question_flow_case": model.question_flow_case,
        "version_selection_cases": list(model.version_selection_cases),
        "source_revisions": [
            source_revisions[key] for key in sorted(source_revisions)
        ],
        "conformance_cases": [
            {
                "id": case.identifier,
                "decision_date": case.decision_date,
                "expected_rule_set_version": case.expected_rule_set_version,
                "expected_outcome": case.expected_outcome,
                "facts": [
                    {"condition": condition, "value": value}
                    for condition, value in case.facts
                ],
                "evidence": [
                    {
                        "id": evidence.identifier,
                        "evidence_type": evidence.evidence_type,
                        "assessments": [
                            {
                                "evidence_requirement": (
                                    assessment.evidence_requirement
                                ),
                                "accepted": assessment.accepted,
                            }
                            for assessment in evidence.assessments
                        ],
                    }
                    for evidence in case.evidence
                ],
                "expected_evidence_statuses": [
                    {
                        "evidence_requirement": requirement,
                        "status": status,
                    }
                    for requirement, status in case.expected_evidence_statuses
                ],
                "expected_obligation_statuses": [
                    {"obligation": obligation, "status": status}
                    for obligation, status in case.expected_obligation_statuses
                ],
            }
            for case in model.conformance_cases
        ],
    }


def build_decision_work_items(
    contract: dict,
    test_path: str,
    work_prefix: str,
    http_endpoint: HttpEndpoint | None = None,
) -> list[dict]:
    runtime_id = f"{work_prefix}.decision-runtime"
    selection_id = f"{work_prefix}.version-selection"
    evaluation_id = f"{work_prefix}.decision-evaluation"
    provenance_id = f"{work_prefix}.result-provenance"
    evidence_requirements = [
        requirement
        for version in contract["rule_set"]["versions"]
        for requirement in version["evidence_requirements"]
    ]
    obligations = [
        obligation
        for version in contract["rule_set"]["versions"]
        for rule in version["rules"]
        for obligation in rule["obligations"]
    ]
    work_items = [
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
            "id": selection_id,
            "title": "Select the Rule Set Version by Decision Date",
            "goal": (
                "Reproduce decisions in their declared temporal context without "
                "a current-date or latest-version default."
            ),
            "depends_on": [runtime_id],
            "obligations": [
                "The Decision Request identifies the stable Rule Set and an explicit ISO Decision Date.",
                "Exactly one Rule Set Version is selected from authored half-open validity intervals.",
                "Every Decision Result reports the selected Rule Set Version and Decision Date.",
                "Missing dates, uncovered dates, caller-selected versions, and overlapping validity intervals fail with actionable diagnostics.",
                *(
                    ["Identical facts produce the two source-backed historical outcomes declared by the Version Selection Cases."]
                    if contract["version_selection_cases"]
                    else []
                ),
            ],
            "sources": [
                "`specs/`: Rule Set Versions, validity intervals, and version Source Citations",
                *(
                    ["`specs/`: paired Version Selection Cases"]
                    if contract["version_selection_cases"]
                    else []
                ),
                "Version Selection Conventions v1: date-only, exactly-one applicability",
            ],
            "test": f"{test_path}::test_decision_date_selects_historical_rule_set_version",
            "excluded": [
                "A silent current-date or latest-version default",
                "Caller control over the selected Rule Set Version",
            ],
        },
        {
            "id": evaluation_id,
            "title": "Evaluate the declared decision contract",
            "goal": "Return the declared outcome for each explicit Conformance Case.",
            "depends_on": [selection_id],
            "obligations": [
                "All declared Conditions are evaluated as satisfied, violated, or unknown.",
                "A violated required Rule yields the declared negative outcome.",
                "A Fact Gap without a violated Rule yields the declared unknown outcome.",
                "Only all satisfied Rules yield the declared positive outcome.",
                "The positive, negative, and unknown Conformance Cases pass end to end.",
            ],
            "sources": [
                f"Decision Contract `{contract['decision_contract']}`",
                "`specs/`: Rules, Conditions, expected values, outcomes, and conformance Cases",
                "Decision Conventions v1: explicit requires-all aggregation",
            ],
            "test": f"{test_path}::test_declared_decision_outcome",
            "excluded": [
                "Domain requirements not stated in the authored specs",
                "An implementation technology inferred from domain vocabulary",
            ],
        },
        {
            "id": provenance_id,
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
        {
            "id": f"{work_prefix}.question-flow",
            "title": "Ask the next decision-relevant Fact Question",
            "goal": (
                "Advance an unknown Case through source-backed questions to a "
                "determinate outcome."
            ),
            "depends_on": [provenance_id],
            "obligations": [
                "Only a Fact Gap that currently prevents a unique outcome can produce the next question.",
                "The lowest-priority unresolved authored Fact Question is selected deterministically.",
                "The question identifies its Condition, input pointer, and supporting Rule and Source Citation.",
                "Submitting each authored answer advances to the next justified question or a final outcome.",
                "A determinate outcome never includes a next question.",
            ],
            "sources": [
                "`specs/`: Fact Questions, priorities, Conditions, and Question Flow Case",
                "Question Selection Conventions v1: select the lowest-priority current Fact Gap",
                "Decision Conventions v1: violated Conditions make the outcome determinate",
            ],
            "test": (
                f"{test_path}::"
                "test_question_driven_interaction_reaches_final_outcome"
            ),
            "excluded": [
                "Questions unrelated to a Rule Condition",
                "Session state, a conversational user interface, or adaptive question optimization",
            ],
        },
        {
            "id": f"{work_prefix}.evidence-evaluation",
            "title": "Evaluate Evidence Requirements separately from Conditions",
            "goal": (
                "Report whether each applicable Evidence Requirement is "
                "fulfilled without changing the underlying Decision Outcome."
            ),
            "depends_on": [provenance_id],
            "obligations": [
                "Each Evidence Requirement is evaluated as fulfilled, missing, or not_applicable.",
                "A satisfied Rule Condition remains separate from fulfillment of its Evidence Requirement.",
                "Supplied Evidence is classified as accepted, rejected, unassessed, or not_relevant for each Evidence Requirement.",
                "Only matching Evidence with an explicit accepted Evidence Assessment fulfills a Requirement.",
                "Each Evidence Requirement evaluation exposes its independent Source Citation and explanation.",
                "The fulfilled, missing, and not-applicable conformance Cases pass end to end.",
            ],
            "sources": [
                "`specs/`: Evidence Requirements, applicability Conditions, Evidence, Assessments, expectations, and Source Citations",
                "Evidence Evaluation Conventions v1: all-condition applicability and explicit-assessment fulfillment",
                "Decision Conventions v1: Evidence evaluation does not affect Rule Condition truth or Decision Outcome",
            ],
            "test": (
                f"{test_path}::"
                "test_evidence_requirements_are_evaluated_separately"
            ),
            "excluded": [
                "Document file formats, upload protocols, or storage",
                "Automatic document-content or authenticity verification",
            ],
        },
    ]
    if not evidence_requirements:
        work_items.pop()
    if obligations:
        work_items.append(
            {
                "id": f"{work_prefix}.obligation-evaluation",
                "title": "Evaluate rule-imposed Obligations",
                "goal": (
                    "Report each declared Obligation independently from the "
                    "aggregate Decision Outcome."
                ),
                "depends_on": [provenance_id],
                "obligations": [
                    "Each selected Rule-imposed Obligation is evaluated as fulfilled, violated, or unknown.",
                    "The Obligation status is derived from its Rule Condition under Obligation Evaluation Conventions v1.",
                    "Every Obligation evaluation exposes its Rule Source Citation and an explanation.",
                    "Authored Conformance Cases prove all three Obligation statuses end to end.",
                ],
                "sources": [
                    "`specs/`: Obligations, Rule relations, expectations, and Source Citations",
                    "Obligation Evaluation Conventions v1: project Rule Condition state onto Obligation status",
                ],
                "test": f"{test_path}::test_rule_obligations_are_evaluated",
                "excluded": [
                    "Remediation workflows, deadlines, assignees, or enforcement",
                    "Obligations inferred from prose or unstated policy",
                ],
            }
        )
    if http_endpoint is not None:
        http_test_path = test_path.replace("test_contract.py", "test_http_contract.py")
        work_items.append(
            {
                "id": f"{work_prefix}.http-api",
                "title": "Expose the Decision Contract over HTTP",
                "goal": "Accept Decision Requests from an HTTP client and return the same sourced Decision Results.",
                "depends_on": [runtime_id, evaluation_id],
                "obligations": [
                    f"POST `{http_endpoint.path}` accepts `{http_endpoint.request.media_type}` according to the authored request schema.",
                    f"The request body at JSON Pointer `{http_endpoint.request.body_pointer}` is the invoked contract input.",
                    f"HTTP {http_endpoint.success_response.status_code} returns `{http_endpoint.success_response.media_type}` with the Decision Result at JSON Pointer `{http_endpoint.success_response.body_pointer}` according to the authored response schema.",
                    f"Invalid requests return HTTP {http_endpoint.invalid_request_response.status_code} with `{http_endpoint.invalid_request_response.media_type}` and error text at JSON Pointer `{http_endpoint.invalid_request_response.body_pointer}` according to the authored error schema.",
                    "The product publishes an OpenAPI 3.1 document compatible with the generated HTTP contract.",
                ],
                "sources": [
                    f"POST endpoint `{http_endpoint.identifier}` and sco:invokesContract in the product specs",
                    f"Request `{http_endpoint.request.identifier}`: body schema, media type, requirement, and input pointer",
                    f"Success response `{http_endpoint.success_response.identifier}`: body schema, media type, status, and result pointer",
                    f"Invalid-request response `{http_endpoint.invalid_request_response.identifier}`: body schema, media type, status, and error pointer",
                    f"Decision Contract `{contract['decision_contract']}`",
                    "HTTP Contract Conventions v1: explicit JSON message schemas and body-pointer bindings",
                ],
                "test": f"{http_test_path}::test_decision_http_cases",
                "excluded": [
                    "A particular web framework or implementation language",
                    "A user interface, session store, or funding calculation",
                ],
            }
        )
    return work_items


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
from datetime import date, timedelta
from pathlib import Path

import pytest

from tools.decision_runtime import run_decision

PRODUCT_ROOT = Path(__file__).parents[1]
CONTRACT = json.loads(
    (PRODUCT_ROOT / "generated" / "decision-contract.json").read_text(
        encoding="utf-8"
    )
)
VERSIONS = CONTRACT["rule_set"]["versions"]
VERSIONS_BY_ID = {version["id"]: version for version in VERSIONS}
ALL_RULES = [rule for version in VERSIONS for rule in version["rules"]]
ALL_OBLIGATIONS = [
    obligation
    for rule in ALL_RULES
    for obligation in rule["obligations"]
]
ALL_EVIDENCE_REQUIREMENTS = [
    requirement
    for version in VERSIONS
    for requirement in version["evidence_requirements"]
]
EVIDENCE_REQUIREMENTS_BY_ID = {
    requirement["id"]: requirement
    for requirement in ALL_EVIDENCE_REQUIREMENTS
}
CONDITIONS_BY_ID = {
    **{rule["condition"]["id"]: rule["condition"] for rule in ALL_RULES},
    **{
        condition["id"]: condition
        for requirement in ALL_EVIDENCE_REQUIREMENTS
        for condition in requirement["applicability_conditions"]
    },
}


def _version_for_case(case):
    return VERSIONS_BY_ID[case["expected_rule_set_version"]]


def _rules_by_condition(version):
    return {rule["condition"]["id"]: rule for rule in version["rules"]}


def _set_json_pointer(document, pointer, value):
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _request_for_case(case):
    request = {
        "decision_contract": CONTRACT["decision_contract"],
        "rule_set": CONTRACT["rule_set"]["id"],
        "decision_date": case["decision_date"],
        "case": {},
        "evidence": json.loads(json.dumps(case.get("evidence", []))),
    }
    for fact in case["facts"]:
        condition = CONDITIONS_BY_ID[fact["condition"]]
        _set_json_pointer(
            request,
            condition["input_json_pointer"],
            fact["value"],
        )
    return request


def _expected_result(case):
    version = _version_for_case(case)
    facts = {fact["condition"]: fact["value"] for fact in case["facts"]}
    evaluations = []
    gaps = []
    for rule in version["rules"]:
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
        decisive = [rule["id"] for rule in version["rules"]]
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
        for rule in version["rules"]
        if rule["id"] in decisive
    ]
    return outcome, evaluations, decisive, gaps, provenance


def _expected_next_question(evaluations, version):
    if any(item["state"] == "violated" for item in evaluations):
        return None
    unknown_rules = [
        rule
        for rule in version["rules"]
        if any(
            item["rule"] == rule["id"] and item["state"] == "unknown"
            for item in evaluations
        )
    ]
    if not unknown_rules:
        return None
    rule = min(
        unknown_rules,
        key=lambda item: item["condition"]["question"]["priority"],
    )
    condition = rule["condition"]
    question = condition["question"]
    source = rule["source"]
    return {
        "id": question["id"],
        "text": question["text"],
        "condition": condition["id"],
        "fact_property": condition["fact_property"],
        "input_json_pointer": condition["input_json_pointer"],
        "answer_schema": {"type": "boolean"},
        "justification": {
            "rule": rule["id"],
            "source_citation": source["citation"],
            "source_revision": source["source_revision"],
            "source_locator": source["locator"],
            "source_statement": source["statement"],
        },
    }


def _expected_evidence_evaluations(case):
    version = _version_for_case(case)
    facts = {fact["condition"]: fact["value"] for fact in case["facts"]}
    result = []
    for requirement in version["evidence_requirements"]:
        applicability = []
        for condition in requirement["applicability_conditions"]:
            actual = facts.get(condition["id"])
            if actual is None:
                state = "unknown"
            elif actual == condition["expected_boolean"]:
                state = "satisfied"
            else:
                state = "violated"
            applicability.append({"condition": condition["id"], "state": state})
        classifications = []
        for evidence in sorted(case.get("evidence", []), key=lambda item: item["id"]):
            assessments = {
                assessment["evidence_requirement"]: assessment["accepted"]
                for assessment in evidence["assessments"]
            }
            if evidence["evidence_type"] != requirement["required_evidence_type"]:
                classification = "not_relevant"
            elif requirement["id"] not in assessments:
                classification = "unassessed"
            elif assessments[requirement["id"]]:
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
        elif any(item["classification"] == "accepted" for item in classifications):
            status = "fulfilled"
        else:
            status = "missing"
        source = requirement["source"]
        result.append(
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
    return result


def _expected_obligation_evaluations(case):
    version = _version_for_case(case)
    facts = {fact["condition"]: fact["value"] for fact in case["facts"]}
    result = []
    for rule in version["rules"]:
        condition = rule["condition"]
        actual = facts.get(condition["id"])
        if actual is None:
            status = "unknown"
        elif actual == condition["expected_boolean"]:
            status = "fulfilled"
        else:
            status = "violated"
        source = rule["source"]
        for obligation in rule["obligations"]:
            result.append(
                {
                    "obligation": obligation["id"],
                    "text": obligation["text"],
                    "rule": rule["id"],
                    "condition": condition["id"],
                    "status": status,
                    "provenance": {
                        "source_citation": source["citation"],
                        "source_revision": source["source_revision"],
                        "source_locator": source["locator"],
                        "source_statement": source["statement"],
                    },
                    "explanation": (
                        f"{status}: Obligation {obligation['id']} follows "
                        f"Rule {rule['id']}. {source['statement']}"
                    ),
                }
            )
    return result


def _run_case(case):
    result = run_decision(PRODUCT_ROOT, _request_for_case(case))
    assert result.returncode == 0, result.output
    return result.json_output()


def test_generated_contract_covers_all_declared_outcomes():
    assert CONTRACT["question_selection_conventions_version"] == 1
    assert CONTRACT["evidence_evaluation_conventions_version"] == 1
    assert CONTRACT["version_selection_conventions_version"] == 1
    assert CONTRACT["obligation_evaluation_conventions_version"] == 1
    assert {case["expected_outcome"] for case in CONTRACT["conformance_cases"]} == {
        outcome["id"] for outcome in CONTRACT["outcomes"].values()
    }
    assert all(rule["source"]["statement"] for rule in ALL_RULES)
    assert all(rule["source"]["locator"] for rule in ALL_RULES)
    assert all(version["source"]["statement"] for version in VERSIONS)
    priorities = [
        condition["question"]["priority"]
        for condition in {
            rule["condition"]["id"]: rule["condition"] for rule in ALL_RULES
        }.values()
    ]
    assert len(priorities) == len(set(priorities))
    flow_case = next(
        case
        for case in CONTRACT["conformance_cases"]
        if case["id"] == CONTRACT["question_flow_case"]
    )
    flow_version = _version_for_case(flow_case)
    flow_rules = _rules_by_condition(flow_version)
    assert flow_case["expected_outcome"] == CONTRACT["outcomes"]["positive"]["id"]
    assert {
        fact["condition"]
        for fact in flow_case["facts"]
        if fact["condition"] in flow_rules
    } == set(flow_rules)
    for requirement in ALL_EVIDENCE_REQUIREMENTS:
        assert {
            expectation["status"]
            for case in CONTRACT["conformance_cases"]
            for expectation in case["expected_evidence_statuses"]
            if expectation["evidence_requirement"] == requirement["id"]
        } == {"fulfilled", "missing", "not_applicable"}
    assert all(
        requirement["source"]["statement"]
        and requirement["source"]["locator"]
        and requirement["source"]["citation"]
        for requirement in ALL_EVIDENCE_REQUIREMENTS
    )
    if ALL_OBLIGATIONS:
        assert {
            expectation["status"]
            for case in CONTRACT["conformance_cases"]
            for expectation in case["expected_obligation_statuses"]
        } == {"fulfilled", "violated", "unknown"}


def test_decision_product_runtime():
    payload = _run_case(CONTRACT["conformance_cases"][0])
    assert isinstance(payload, dict)


def test_decision_date_selects_historical_rule_set_version():
    cases = [
        case
        for case in CONTRACT["conformance_cases"]
        if case["id"] in CONTRACT["version_selection_cases"]
    ]
    if cases:
        assert len(cases) == 2
        requests = [_request_for_case(case) for case in cases]
        comparable = []
        for request in requests:
            copy = json.loads(json.dumps(request))
            copy.pop("decision_date")
            comparable.append(copy)
        assert comparable[0] == comparable[1]
    else:
        cases = CONTRACT["conformance_cases"]

    results = [_run_case(case) for case in cases]
    assert {result["rule_set_version"] for result in results} == {
        case["expected_rule_set_version"] for case in cases
    }
    if CONTRACT["version_selection_cases"]:
        assert len({result["outcome"] for result in results}) == 2
    for case, result in zip(cases, results):
        version = _version_for_case(case)
        assert result["decision_date"] == case["decision_date"]
        assert result["rule_set_version"] == version["id"]
        assert result["rule_set_version_label"] == version["version"]
        assert version["source"]["source_revision"] in {
            source["id"] for source in CONTRACT["source_revisions"]
        }


def test_runtime_rejects_missing_uncovered_and_caller_selected_versions():
    case = CONTRACT["conformance_cases"][0]
    missing = _request_for_case(case)
    missing.pop("decision_date")
    result = run_decision(PRODUCT_ROOT, missing)
    assert result.returncode != 0
    assert "must contain an ISO decision_date" in result.output

    uncovered = _request_for_case(case)
    earliest = min(date.fromisoformat(version["valid_from"]) for version in VERSIONS)
    uncovered["decision_date"] = (earliest - timedelta(days=1)).isoformat()
    result = run_decision(PRODUCT_ROOT, uncovered)
    assert result.returncode != 0
    assert "matches 0 Rule Set Versions" in result.output

    caller_selected = _request_for_case(case)
    caller_selected["rule_set_version"] = case["expected_rule_set_version"]
    result = run_decision(PRODUCT_ROOT, caller_selected)
    assert result.returncode != 0
    assert "must not select a Rule Set Version" in result.output


@pytest.mark.parametrize(
    "case",
    CONTRACT["conformance_cases"],
    ids=lambda case: case["id"].rsplit("#", 1)[-1],
)
def test_declared_decision_outcome(case):
    payload = _run_case(case)
    version = _version_for_case(case)
    outcome, evaluations, decisive, gaps, provenance = _expected_result(case)
    assert case["expected_outcome"] == outcome["id"]
    assert payload["decision_contract"] == CONTRACT["decision_contract"]
    assert payload["rule_set"] == CONTRACT["rule_set"]["id"]
    assert payload["rule_set_version"] == version["id"]
    assert payload["rule_set_version_label"] == version["version"]
    assert payload["decision_date"] == case["decision_date"]
    assert payload["outcome"] == outcome["code"]
    assert payload["outcome_id"] == outcome["id"]
    assert payload["condition_evaluations"] == evaluations
    assert payload["decisive_rules"] == decisive
    assert payload["fact_gaps"] == gaps
    assert payload["next_question"] == _expected_next_question(evaluations, version)
    assert payload["evidence_requirement_evaluations"] == (
        _expected_evidence_evaluations(case)
    )
    assert payload["obligation_evaluations"] == (
        _expected_obligation_evaluations(case)
    )


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


@pytest.mark.skipif(not ALL_EVIDENCE_REQUIREMENTS, reason="no Evidence Requirements")
def test_evidence_requirements_are_evaluated_separately():
    requirement = ALL_EVIDENCE_REQUIREMENTS[0]
    supporting_condition = requirement["supports_condition"]
    cases_by_status = {
        expectation["status"]: case
        for case in CONTRACT["conformance_cases"]
        for expectation in case["expected_evidence_statuses"]
        if expectation["evidence_requirement"] == requirement["id"]
        if {
            fact["condition"]: fact["value"] for fact in case["facts"]
        }.get(supporting_condition)
        == _rules_by_condition(_version_for_case(case))[supporting_condition]["condition"]["expected_boolean"]
    }
    assert set(cases_by_status) == {"fulfilled", "missing", "not_applicable"}
    results = {
        status: _run_case(case)
        for status, case in cases_by_status.items()
    }

    for status, payload in results.items():
        supporting_evaluation = next(
            item
            for item in payload["condition_evaluations"]
            if item["condition"] == supporting_condition
        )
        assert supporting_evaluation["state"] == "satisfied"
        evidence_evaluation = payload["evidence_requirement_evaluations"][0]
        assert evidence_evaluation["status"] == status
        assert evidence_evaluation["provenance"] == {
            "source_citation": requirement["source"]["citation"],
            "source_revision": requirement["source"]["source_revision"],
            "source_locator": requirement["source"]["locator"],
            "source_statement": requirement["source"]["statement"],
        }
        assert requirement["source"]["statement"] in evidence_evaluation["explanation"]

    assert results["fulfilled"]["outcome"] == results["missing"]["outcome"]
    assert results["fulfilled"]["evidence_requirement_evaluations"][0][
        "supplied_evidence"
    ][0]["classification"] == "accepted"
    assert results["missing"]["evidence_requirement_evaluations"][0][
        "supplied_evidence"
    ] == []

    complete_request = _request_for_case(cases_by_status["fulfilled"])
    variants = []
    rejected = json.loads(json.dumps(complete_request))
    rejected["evidence"][0]["assessments"][0]["accepted"] = False
    variants.append(("rejected", rejected))
    unassessed = json.loads(json.dumps(complete_request))
    unassessed["evidence"][0]["assessments"] = []
    variants.append(("unassessed", unassessed))
    not_relevant = json.loads(json.dumps(complete_request))
    not_relevant["evidence"][0]["evidence_type"] = "urn:test:other-evidence-type"
    variants.append(("not_relevant", not_relevant))
    for classification, request in variants:
        result = run_decision(PRODUCT_ROOT, request)
        assert result.returncode == 0, result.output
        payload = result.json_output()
        assert payload["outcome"] == CONTRACT["outcomes"]["positive"]["code"]
        evidence_evaluation = payload["evidence_requirement_evaluations"][0]
        assert evidence_evaluation["status"] == "missing"
        assert evidence_evaluation["supplied_evidence"][0]["classification"] == classification


@pytest.mark.skipif(not ALL_EVIDENCE_REQUIREMENTS, reason="no Evidence Requirements")
def test_unaccepted_supplied_evidence_does_not_fulfill_requirement():
    complete = next(
        case
        for case in CONTRACT["conformance_cases"]
        if any(
            expectation["status"] == "fulfilled"
            for expectation in case["expected_evidence_statuses"]
        )
    )
    request = _request_for_case(complete)
    request["evidence"][0]["assessments"][0]["accepted"] = False

    result = run_decision(PRODUCT_ROOT, request)
    assert result.returncode == 0, result.output
    payload = result.json_output()

    assert payload["outcome"] == CONTRACT["outcomes"]["positive"]["code"]
    evidence_evaluation = payload["evidence_requirement_evaluations"][0]
    assert evidence_evaluation["status"] == "missing"
    assert evidence_evaluation["supplied_evidence"][0]["classification"] == "rejected"


@pytest.mark.skipif(not ALL_OBLIGATIONS, reason="no Obligations")
def test_rule_obligations_are_evaluated():
    covered_statuses = set()
    for case in CONTRACT["conformance_cases"]:
        payload = _run_case(case)
        actual = {
            item["obligation"]: item
            for item in payload["obligation_evaluations"]
        }
        expected = {
            item["obligation"]: item["status"]
            for item in case["expected_obligation_statuses"]
        }
        assert set(actual) == set(expected)
        assert {
            obligation: item["status"]
            for obligation, item in actual.items()
        } == expected
        assert all(item["provenance"]["source_citation"] for item in actual.values())
        assert all(item["provenance"]["source_statement"] for item in actual.values())
        assert all(item["text"] and item["explanation"] for item in actual.values())
        covered_statuses.update(expected.values())
    assert covered_statuses == {"fulfilled", "violated", "unknown"}


def test_question_driven_interaction_reaches_final_outcome():
    flow_case = next(
        case
        for case in CONTRACT["conformance_cases"]
        if case["id"] == CONTRACT["question_flow_case"]
    )
    flow_version = _version_for_case(flow_case)
    flow_rules = _rules_by_condition(flow_version)
    answers = {fact["condition"]: fact["value"] for fact in flow_case["facts"]}
    ordered_rules = sorted(
        flow_version["rules"],
        key=lambda rule: rule["condition"]["question"]["priority"],
    )
    request = _request_for_case(
        {
            **flow_case,
            "facts": [
                fact
                for fact in flow_case["facts"]
                if fact["condition"] not in flow_rules
            ],
        }
    )
    answered = set()

    for rule in ordered_rules:
        result = run_decision(PRODUCT_ROOT, request)
        assert result.returncode == 0, result.output
        payload = result.json_output()
        assert payload["outcome"] == CONTRACT["outcomes"]["unknown"]["code"]
        assert not any(
            item["state"] == "violated"
            for item in payload["condition_evaluations"]
        )
        question = payload["next_question"]
        assert question == _expected_next_question(
            payload["condition_evaluations"], flow_version
        )
        assert question["condition"] == rule["condition"]["id"]
        assert question["condition"] not in answered
        assert question["condition"] in {
            gap["condition"] for gap in payload["fact_gaps"]
        }
        assert question["justification"]["source_statement"]
        assert question["justification"]["source_citation"]
        _set_json_pointer(
            request,
            question["input_json_pointer"],
            answers[question["condition"]],
        )
        answered.add(question["condition"])

    result = run_decision(PRODUCT_ROOT, request)
    assert result.returncode == 0, result.output
    payload = result.json_output()
    assert payload["outcome"] == CONTRACT["outcomes"]["positive"]["code"]
    assert payload["fact_gaps"] == []
    assert payload["next_question"] is None


def test_determinate_outcome_does_not_ask_an_irrelevant_question():
    negative = next(
        case
        for case in CONTRACT["conformance_cases"]
        if case["expected_outcome"] == CONTRACT["outcomes"]["negative"]["id"]
    )
    negative_rules = _rules_by_condition(_version_for_case(negative))
    removable = next(
        fact
        for fact in negative["facts"]
        if fact["condition"] in negative_rules
        and fact["value"]
        == negative_rules[fact["condition"]]["condition"]["expected_boolean"]
    )
    partial = {
        **negative,
        "facts": [fact for fact in negative["facts"] if fact is not removable],
    }

    payload = _run_case(partial)

    assert payload["outcome"] == CONTRACT["outcomes"]["negative"]["code"]
    assert payload["fact_gaps"]
    assert payload["next_question"] is None
'''


DECISION_HTTP_TEST_TEMPLATE = '''# Generated by Spec Compiler. Do not edit.
import json
from pathlib import Path
import socket
from urllib.parse import urlsplit

import httpx
from openapi_spec_validator import OpenAPIV31SpecValidator, validate as validate_openapi
import pytest

from tools.contract_runtime import running_product
from tools.decision_runtime import run_decision
from tools.http_contract_verification import (
    assert_schema_matches, invalid_bodies, read_pointer, resolve_reference,
    validate_body, wrap_body,
)


PRODUCT_ROOT = Path(__file__).parents[1]
CONTRACT = json.loads(
    (PRODUCT_ROOT / "generated" / "decision-contract.json").read_text(encoding="utf-8")
)
EXPECTED_OPENAPI = json.loads(
    (PRODUCT_ROOT / "generated" / "expected-openapi.json").read_text(encoding="utf-8")
)
API_PATH = next(iter(EXPECTED_OPENAPI["paths"]))
OPERATION = EXPECTED_OPENAPI["paths"][API_PATH]["post"]
BINDING = OPERATION["x-spec-compiler-binding"]
REQUEST_MEDIA, REQUEST_CONTENT = next(iter(OPERATION["requestBody"]["content"].items()))


def _response_contract(status):
    return next(iter(OPERATION["responses"][str(status)]["content"].items()))


def _set_pointer(document, pointer, value):
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _request_for_case(case):
    conditions = {
        **{
            rule["condition"]["id"]: rule["condition"]
            for version in CONTRACT["rule_set"]["versions"]
            for rule in version["rules"]
        },
        **{
            condition["id"]: condition
            for version in CONTRACT["rule_set"]["versions"]
            for requirement in version["evidence_requirements"]
            for condition in requirement["applicability_conditions"]
        },
    }
    request = {
        "decision_contract": CONTRACT["decision_contract"],
        "rule_set": CONTRACT["rule_set"]["id"],
        "decision_date": case["decision_date"],
        "case": {},
        "evidence": json.loads(json.dumps(case["evidence"])),
    }
    for fact in case["facts"]:
        _set_pointer(
            request,
            conditions[fact["condition"]]["input_json_pointer"],
            fact["value"],
        )
    return request


@pytest.fixture(scope="module")
def running_http_api():
    with running_product(PRODUCT_ROOT) as product:
        yield product


def test_decision_http_openapi_matches_contract(running_http_api):
    response = httpx.get(running_http_api.openapi_url)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";", 1)[0] == "application/json"
    actual = response.json()
    validate_openapi(actual, cls=OpenAPIV31SpecValidator)
    validate_openapi(EXPECTED_OPENAPI, cls=OpenAPIV31SpecValidator)
    actual_operation = actual["paths"][API_PATH]["post"]
    actual_request = resolve_reference(actual, actual_operation["requestBody"])
    assert actual_request["required"] == OPERATION["requestBody"]["required"]
    assert_schema_matches(
        actual, actual_request["content"][REQUEST_MEDIA]["schema"], REQUEST_CONTENT["schema"]
    )
    for status, expected_response in OPERATION["responses"].items():
        assert status in actual_operation["responses"]
        actual_response = resolve_reference(actual, actual_operation["responses"][status])
        for media_type, expected_content in expected_response["content"].items():
            assert_schema_matches(
                actual, actual_response["content"][media_type]["schema"],
                expected_content["schema"],
            )


@pytest.mark.parametrize(
    "case", CONTRACT["conformance_cases"],
    ids=lambda case: case["id"].rsplit("#", 1)[-1],
)
def test_decision_http_cases(running_http_api, case):
    request = _request_for_case(case)
    body = wrap_body(request, BINDING["request_pointer"])
    validate_body(REQUEST_CONTENT["schema"], body)
    response = httpx.post(
        running_http_api.base_url + API_PATH, content=json.dumps(body),
        headers={"content-type": REQUEST_MEDIA},
    )
    assert response.status_code == BINDING["success_status"], response.text
    media_type, content = _response_contract(BINDING["success_status"])
    assert response.headers["content-type"].split(";", 1)[0] == media_type
    validate_body(content["schema"], response.json())
    result = read_pointer(response.json(), BINDING["result_pointer"])
    assert result["decision_date"] == case["decision_date"]
    assert result["rule_set_version"] == case["expected_rule_set_version"]
    assert result["outcome_id"] == case["expected_outcome"]
    cli_result = run_decision(PRODUCT_ROOT, request)
    assert cli_result.returncode == 0, cli_result.output
    assert result == cli_result.json_output()


def test_decision_http_rejects_invalid_request(running_http_api):
    request = _request_for_case(CONTRACT["conformance_cases"][0])
    body = wrap_body(request, BINDING["request_pointer"])
    validate_body(REQUEST_CONTENT["schema"], body)
    media_type, content = _response_contract(BINDING["invalid_status"])
    payloads = ["{", *[
        json.dumps(candidate)
        for candidate in invalid_bodies(REQUEST_CONTENT["schema"], body)
    ]]
    with httpx.Client() as client:
        for payload in payloads:
            response = client.post(
                running_http_api.base_url + API_PATH, content=payload,
                headers={"content-type": REQUEST_MEDIA},
            )
            assert response.status_code == BINDING["invalid_status"], response.text
            assert response.headers["content-type"].split(";", 1)[0] == media_type
            validate_body(content["schema"], response.json())
            assert isinstance(read_pointer(response.json(), BINDING["error_pointer"]), str)


def test_decision_http_process_cleanup():
    with running_product(PRODUCT_ROOT) as product:
        address = urlsplit(product.base_url)
        host, port = address.hostname, address.port
    with socket.socket() as connection:
        connection.settimeout(0.5)
        assert connection.connect_ex((host, port)) != 0
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
                    "Compiler Conventions v2: deterministic generation increment",
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
    source = source.replace(current, successor)
    source = re.sub(r"^PACKAGED_ONTOLOGIES = .*?$",
                    lambda _match: "PACKAGED_ONTOLOGIES = " + repr(ontology_sources()),
                    source, count=1, flags=re.MULTILINE)
    output.write_text(source, encoding="utf-8")
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
    work_prefix = product_root.name.replace("_", "-")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", work_prefix):
        raise ValueError(
            f"Decision Product directory does not form a safe work prefix: {work_prefix}"
        )
    work_items = build_decision_work_items(
        contract, test_path, work_prefix, model.http_endpoint
    )

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
    http_test_output = tests_root / "test_http_contract.py"
    openapi_output = generated / "expected-openapi.json"
    http_outputs = []
    if model.http_endpoint is not None:
        http_test_output.write_text(DECISION_HTTP_TEST_TEMPLATE, encoding="utf-8")
        openapi_output.write_text(
            json.dumps(
                build_http_openapi(model.http_endpoint),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        http_outputs = [http_test_output, openapi_output]
    else:
        for stale_http_output in (http_test_output, openapi_output):
            if stale_http_output.exists():
                stale_http_output.unlink()
    graph_output = generated / "work-graph.json"
    graph_output.write_text(
        json.dumps(
            {
                "generator": "spec-compiler",
                "compiler_conventions_version": COMPILER_CONVENTIONS_VERSION,
                "decision_conventions_version": DECISION_CONVENTIONS_VERSION,
                "decision_protocol_version": DECISION_PROTOCOL_VERSION,
                "question_selection_conventions_version": (
                    QUESTION_SELECTION_CONVENTIONS_VERSION
                ),
                "evidence_evaluation_conventions_version": (
                    EVIDENCE_EVALUATION_CONVENTIONS_VERSION
                ),
                "version_selection_conventions_version": (
                    VERSION_SELECTION_CONVENTIONS_VERSION
                ),
                "obligation_evaluation_conventions_version": (
                    OBLIGATION_EVALUATION_CONVENTIONS_VERSION
                ),
                **(
                    {"http_contract_conventions_version": HTTP_CONTRACT_CONVENTIONS_VERSION}
                    if model.http_endpoint is not None
                    else {}
                ),
                "work_items": work_items,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    expected_issue_names = {f"{item['id']}.md" for item in work_items}
    for stale_issue in sorted(issues.glob("*.md")):
        if stale_issue.name not in expected_issue_names:
            stale_issue.unlink()
    issue_outputs = []
    for item in work_items:
        issue_output = issues / f"{item['id']}.md"
        issue_output.write_text(render_issue(item, product_path), encoding="utf-8")
        issue_outputs.append(issue_output)
    return [
        test_output, contract_output, *http_outputs, graph_output, *issue_outputs
    ]


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
        graph.subjects(DCTERMS.conformsTo, CCO.CompilerProtocolV1)
    )
    decision_products = list(
        graph.subjects(DCTERMS.conformsTo, DPO.DecisionProtocolV1)
    )
    post_endpoint_candidates = set(graph.subjects(RDF.type, SCO.PostEndpoint)) | set(
        graph.subjects(SCO.invokesContract, None)
    )
    if post_endpoint_candidates and not decision_products:
        raise ValueError(
            "POST endpoints currently require a Decision Protocol v1 product "
            "with explicit HTTP messages and a matching sco:invokesContract"
        )
    http_contract = bool(
        list(graph.subjects(RDF.type, SCO.GetEndpoint))
        or list(graph.subjects(RDF.type, SQLO.SqlTable))
    )
    profiles = [
        name
        for name, present in (
            ("compiler", bool(compiler_products)),
            (
                "decision-http" if post_endpoint_candidates else "decision",
                bool(decision_products),
            ),
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

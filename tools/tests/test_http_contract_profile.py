import json
from pathlib import Path
import shutil
import subprocess
import sys

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS
import pytest

from tools.generate import (
    SCO, build_http_openapi, generate_decision_contract, read_decision_model,
    read_http_endpoint,
)
from tools.http_contract_verification import assert_schema_matches


ROOT = Path(__file__).parents[2]
PRODUCT_ROOT = ROOT / "products" / "kfw_458_eligibility"
KFW = Namespace("https://arturmiller.github.io/spec-compiler/resources/funding/kfw-458/#")


def _http_graph():
    return Graph().parse(PRODUCT_ROOT / "specs" / "http_api.ttl", format="turtle")


def _schema(graph, message):
    return json.loads(str(graph.value(message, SCO.bodySchema)))


def _set_schema(graph, message, schema):
    graph.set((message, SCO.bodySchema, Literal(json.dumps(schema), datatype=RDF.JSON)))


def test_renderer_uses_authored_schema_without_adding_decision_fields():
    graph = _http_graph()
    request_schema = {
        "type": "object",
        "properties": {"nickname": {"type": "string", "minLength": 3}},
        "required": ["nickname"],
        "additionalProperties": False,
    }
    result_schema = {"type": "array", "items": {"type": "integer"}}
    _set_schema(graph, KFW.EligibilityHttpRequest, request_schema)
    _set_schema(graph, KFW.EligibilityHttpResult, result_schema)
    graph.set((
        KFW.ApplicantEligibilityPostEndpoint, SCO.invokesContract, URIRef("urn:other:operation")
    ))

    openapi = build_http_openapi(read_http_endpoint(graph))
    operation = openapi["paths"]["/eligibility-decisions"]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == request_schema
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == result_schema
    assert operation["x-spec-compiler-binding"]["invokes_contract"] == "urn:other:operation"


@pytest.mark.parametrize("predicate", [
    SCO.bodySchema, SCO.bodyPointer, SCO.mediaType, SCO.bodyRequired,
])
def test_request_message_rejects_missing_declarations(predicate):
    graph = _http_graph()
    graph.remove((KFW.EligibilityHttpRequest, predicate, None))
    with pytest.raises(ValueError, match="Expected exactly one"):
        read_http_endpoint(graph)


@pytest.mark.parametrize("schema", [
    {"type": "made-up-type"},
    {"type": "object", "required": "field"},
    {"type": "string", "minLength": -1},
])
def test_invalid_json_schema_is_rejected(schema):
    graph = _http_graph()
    _set_schema(graph, KFW.EligibilityHttpRequest, schema)
    with pytest.raises(ValueError, match="Invalid HTTP body schema"):
        read_http_endpoint(graph)


@pytest.mark.parametrize("schema", [
    {"$ref": "https://example.invalid/schema"},
    {"type": "object", "properties": {"field": {"$ref": "#/definitions/field"}}},
    {"type": "object", "inventedKeyword": True},
])
def test_unsupported_schema_features_are_rejected_without_resolving_them(schema):
    graph = _http_graph()
    _set_schema(graph, KFW.EligibilityHttpRequest, schema)
    with pytest.raises(ValueError, match="Unsupported HTTP JSON Schema keywords"):
        read_http_endpoint(graph)


def test_duplicate_json_schema_keys_are_rejected():
    graph = _http_graph()
    graph.set((KFW.EligibilityHttpRequest, SCO.bodySchema, Literal(
        '{"type": "object", "type": "string"}', datatype=RDF.JSON,
    )))
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        read_http_endpoint(graph)


@pytest.mark.parametrize("resource", [KFW.ApplicantEligibilityPostEndpoint, KFW.EligibilityHttpRequest])
def test_anonymous_http_resources_are_rejected_for_stable_provenance(resource):
    graph = _http_graph()
    replacement = Graph()
    anonymous = BNode()
    for subject, predicate, obj in graph:
        replacement.add((
            anonymous if subject == resource else subject, predicate,
            anonymous if obj == resource else obj,
        ))
    with pytest.raises(ValueError, match="must be named resources"):
        read_http_endpoint(replacement)


@pytest.mark.parametrize("pointer", ["payload", "/missing", "/invalid~2escape"])
def test_body_pointer_must_address_an_explicit_object_field(pointer):
    graph = _http_graph()
    graph.set((KFW.EligibilityHttpRequest, SCO.bodyPointer, Literal(pointer)))
    with pytest.raises(ValueError, match="[Pp]ointer"):
        read_http_endpoint(graph)


@pytest.mark.parametrize("message,status", [
    (KFW.EligibilityHttpResult, 204),
    (KFW.EligibilityHttpResult, 400),
    (KFW.EligibilityHttpError, 200),
])
def test_response_role_and_status_must_agree(message, status):
    graph = _http_graph()
    graph.set((message, SCO.statusCode, Literal(status)))
    with pytest.raises(ValueError, match="status"):
        read_http_endpoint(graph)


def test_openapi_comparison_detects_unrequested_required_fields():
    expected = {"type": "object", "properties": {"optional": {"type": "boolean"}}}
    actual = {**expected, "required": ["optional"]}
    with pytest.raises(AssertionError):
        assert_schema_matches({}, actual, expected)


def test_openapi_comparison_allows_equivalent_local_references():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    document = {"components": {"schemas": {"Result": schema}}}
    assert_schema_matches(document, {"$ref": "#/components/schemas/Result"}, schema)


def test_altered_http_spec_passes_generated_black_box_proofs_with_same_backend(tmp_path):
    product = tmp_path / "custom-api"
    shutil.copytree(PRODUCT_ROOT, product, ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "generated", "tests",
    ))
    graph = _http_graph()
    endpoint = KFW.ApplicantEligibilityPostEndpoint
    graph.set((endpoint, SCO.path, Literal("/custom-check")))
    graph.set((endpoint, DCTERMS.title, Literal("Authored alternative API")))
    for message, pointer, status, media in (
        (KFW.EligibilityHttpRequest, "/submission", None, "application/vnd.example.request+json"),
        (KFW.EligibilityHttpResult, "/result", 202, "application/vnd.example.result+json"),
        (KFW.EligibilityHttpError, "/problem/message", 422, "application/problem+json"),
    ):
        schema = _schema(graph, message)
        if message == KFW.EligibilityHttpError:
            schema = schema["properties"]["error"]
        for name in reversed(pointer.split("/")[1:]):
            schema = {"type": "object", "properties": {name: schema}, "required": [name]}
        _set_schema(graph, message, schema)
        graph.set((message, SCO.bodyPointer, Literal(pointer)))
        graph.set((message, SCO.mediaType, Literal(media)))
        if status is not None:
            graph.set((message, SCO.statusCode, Literal(status)))
    # Rename endpoint and message resources to prove there is no dispatch by their IRIs.
    renamed = {
        node: URIRef(f"urn:alternative:resource-{index}")
        for index, node in enumerate((
            endpoint, KFW.EligibilityHttpRequest, KFW.EligibilityHttpResult, KFW.EligibilityHttpError
        ))
    }
    replacement = Graph()
    for subject, predicate, obj in graph:
        replacement.add((renamed.get(subject, subject), predicate, renamed.get(obj, obj)))
    replacement.serialize(product / "specs" / "http_api.ttl", format="turtle")
    model = read_decision_model(product)
    generate_decision_contract(product, str(product), model)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(product / "tests" / "test_http_contract.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr

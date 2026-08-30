"""Generate deterministic contracts, tests, and work for a product."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
from pprint import pformat
import re

from rdflib import Graph, Namespace, RDF
from rdflib.namespace import DCTERMS, SH, XSD

ROOT = Path(__file__).parents[1]
BOOTSTRAP_GENERATION = 1
COMPILER_CONVENTIONS_VERSION = 1
RUNTIME_PROTOCOL_VERSION = 1
SCO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/#")
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


def read_contract(product_root: Path, contract_graph: Graph | None = None) -> dict:
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
    artifacts = sorted(
        str(value) for value in graph.objects(contract, SCO.generatesArtifact)
    )
    if not artifacts:
        raise ValueError("Spec compiler must declare at least one generated artifact")
    for artifact in artifacts:
        path = Path(artifact)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Generated artifact pattern must stay in the input bundle: {artifact}")
    fixture = str(one(graph, contract, SCO.validFixtureProduct))
    fixture_path = (product_root / fixture).resolve()
    if not fixture_path.is_dir():
        raise ValueError(f"Compiler fixture product does not exist: {fixture_path}")
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
        "valid_fixture_product": fixture,
        "generated_artifacts": artifacts,
        "rejects_missing_specs": bool(
            one(graph, contract, SCO.rejectsMissingSpecs).toPython()
        ),
        "deterministic_output": bool(
            one(graph, contract, SCO.deterministicOutput).toPython()
        ),
        "bootstrap": bootstrap,
    }


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
                "The response conforms to the contracted SHACL shape.",
            ],
            "sources": [
                "`specs/`: endpoint-to-table relation and HTTP result",
                "`specs/`: response Shape",
                "Compiler conventions v1: SHACL-to-JSON mapping",
            ],
            "test": (
                f"{test_path}::test_get_endpoint_returns_shape_conformant_resource"
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
from pyshacl import validate
import pytest
from rdflib import Graph, Literal, RDF, URIRef

from tools.contract_runtime import running_product

PRODUCT_ROOT = Path(__file__).parents[1]
CONTRACT = __CONTRACT__
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
    fields = CONTRACT["fields"]
    names = [field["name"] for field in fields]
    values = [
        float(RESOURCE_VALUES[name])
        if isinstance(RESOURCE_VALUES[name], Decimal)
        else RESOURCE_VALUES[name]
        for name in names
    ]
    expected_identifier = None
    if not CONTRACT["id_generated"]:
        expected_identifier = 1
        names.insert(0, CONTRACT["id_column"])
        values.insert(0, expected_identifier)
    placeholders = ", ".join("?" for _ in names)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                f"INSERT INTO {CONTRACT['table_name']} ({', '.join(names)}) "
                f"VALUES ({placeholders})",
                values,
            )
    return cursor.lastrowid if CONTRACT["id_generated"] else expected_identifier


def test_sql_table_matches_contract(running_api):
    _, database_path = running_api
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            f"PRAGMA table_info({CONTRACT['table_name']})"
        ).fetchall()

    columns = {
        row[1]: {
            "type": row[2],
            "not_null": bool(row[3]),
            "primary_key": bool(row[5]),
        }
        for row in rows
    }
    identifier = columns[CONTRACT["id_column"]]
    assert identifier["type"] == CONTRACT["id_sql_type"]
    assert identifier["primary_key"] is CONTRACT["id_primary_key"]
    for field in CONTRACT["fields"]:
        actual = columns[field["name"]]
        assert actual["type"] == field["sql_type"]
        assert actual["not_null"] is field["required"]
    if CONTRACT["id_generated"]:
        assert _insert_resource(database_path) is not None


def test_get_endpoint_returns_shape_conformant_resource(running_api):
    product, database_path = running_api
    fields = CONTRACT["fields"]
    names = [field["name"] for field in fields]
    record_id = _insert_resource(database_path)

    parameter = CONTRACT["path_parameter"]["name"]
    path = CONTRACT["api_path"].replace("{" + parameter + "}", str(record_id))
    response = httpx.get(product.base_url + path)
    assert response.status_code == CONTRACT["success_status"]
    actual_media_type = response.headers["content-type"].split(";", 1)[0]
    assert actual_media_type.strip().lower() == CONTRACT["media_type"].lower()
    payload = response.json()
    if CONTRACT["closed"]:
        assert set(payload) == set(names)
    else:
        assert set(names) <= set(payload)
    for field in fields:
        actual = payload[field["name"]]
        expected = RESOURCE_VALUES[field["name"]]
        if isinstance(expected, Decimal):
            actual = Decimal(str(actual))
        assert actual == expected

    data = Graph()
    resource = URIRef(
        "https://arturmiller.github.io/spec-compiler/resources/sql-api/#"
        f"contract-resource-{record_id}"
    )
    data.add((resource, RDF.type, URIRef(CONTRACT["rdf_class"])))
    for field in fields:
        value = payload[field["name"]]
        if field["datatype"] == "http://www.w3.org/2001/XMLSchema#decimal":
            value = Decimal(str(value))
        data.add((resource, URIRef(field["rdf_path"]), Literal(value)))

    shape_graph = Graph()
    for spec_file in sorted((PRODUCT_ROOT / "specs").glob("*.ttl")):
        shape_graph.parse(spec_file, format="turtle")
    conforms, _, report = validate(data, shacl_graph=shape_graph)
    assert conforms, report
'''


COMPILER_TEST_TEMPLATE = '''# Generated by Spec Compiler. Do not edit.
from pathlib import Path
import shutil

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


def _copy_fixture(tmp_path):
    source = (COMPILER_ROOT / CONTRACT["valid_fixture_product"]).resolve()
    target = tmp_path / "input-product"
    shutil.copytree(source, target)
    return target


def test_compiler_generates_declared_artifacts(tmp_path):
    product_root = _copy_fixture(tmp_path)
    result = run_compiler(COMPILER_ROOT, product_root)
    assert result.returncode == 0, result.output
    for pattern in CONTRACT["generated_artifacts"]:
        assert list(product_root.glob(pattern)), f"No generated artifact matches {pattern}"


def test_compiler_output_reaches_a_byte_identical_fixpoint(tmp_path):
    product_root = _copy_fixture(tmp_path)
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


def test_bootstrapped_compiler_is_independently_executable(tmp_path):
    if not CONTRACT["bootstrap"]:
        return
    implementation = COMPILER_ROOT / CONTRACT["bootstrap"]["implementation_artifact"]
    assert implementation.is_file()
    expected_generation = CONTRACT["bootstrap"]["implementation_generation"]
    assert f"BOOTSTRAP_GENERATION = {expected_generation}" in implementation.read_text(
        encoding="utf-8"
    )

    fixture_root = _copy_fixture(tmp_path)
    result = run_compiler(COMPILER_ROOT, fixture_root)
    assert result.returncode == 0, result.output
    for pattern in CONTRACT["generated_artifacts"]:
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
                    f"A successful compilation emits `{artifact}`."
                    for artifact in contract["generated_artifacts"]
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
                    "Two compilations of the same Product Bundle produce byte-identical generated and test files."
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
                    "G1 successfully compiles the valid fixture through Compiler Protocol v1.",
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
    if compiler_products:
        contract = read_compiler_contract(product_root, graph)
        outputs = generate_compiler_contract(product_root, product_path, contract)
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

    contract = read_contract(product_root, graph)
    expected_openapi = build_openapi(contract)
    work_items = build_work_items(contract, test_path)
    article_values = {
        field["name"]: deterministic_value(field) for field in contract["fields"]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        TEST_TEMPLATE.replace(
            "__CONTRACT__", pformat(contract, sort_dicts=False)
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

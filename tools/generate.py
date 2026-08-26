"""Generate deterministic contract tests and work for sql_api_example."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from pprint import pformat

from rdflib import Graph, Namespace, RDF
from rdflib.namespace import SH, XSD

ROOT = Path(__file__).parents[1]
PRODUCT_ROOT = ROOT / "products" / "sql_api_example"
SPECS_ROOT = PRODUCT_ROOT / "specs"
TESTS_ROOT = PRODUCT_ROOT / "tests"
TEST_PATH = "products/sql_api_example/tests/test_contract.py"
EX = Namespace("https://example.org/catalog/")
SQL_TYPES = {
    XSD.string: "TEXT",
    XSD.decimal: "DECIMAL",
}


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


def read_contract() -> dict:
    shapes = Graph().parse(SPECS_ROOT / "article_shape.ttl", format="turtle")
    system = Graph().parse(SPECS_ROOT / "system_contract.ttl", format="turtle")
    endpoints = list(system.subjects(RDF.type, EX.GetEndpoint))
    tables = list(system.subjects(RDF.type, EX.SqlTable))
    if len(endpoints) != 1 or len(tables) != 1:
        raise ValueError("Prototype expects exactly one GET endpoint and one SQL table")
    endpoint, table = endpoints[0], tables[0]
    shape = one(system, endpoint, EX.returns)
    if one(system, table, EX.stores) != shape:
        raise ValueError("Endpoint and table must reference the same shape")
    rdf_class = one(shapes, shape, SH.targetClass)

    fields = []
    for prop in shapes.objects(shape, SH.property):
        path = one(shapes, prop, SH.path)
        datatype = one(shapes, prop, SH.datatype)
        if datatype not in SQL_TYPES:
            raise ValueError(f"No SQL type mapping for {datatype}")
        name = local_name(path)
        fields.append(
            {
                "rdf_path": str(path),
                "name": name,
                "sql_type": SQL_TYPES[datatype],
                "required": int(one(shapes, prop, SH.minCount)) > 0,
                "datatype": str(datatype),
                "min_length": optional(shapes, prop, SH.minLength),
                "min_exclusive": optional(shapes, prop, SH.minExclusive),
                "max_exclusive": optional(shapes, prop, SH.maxExclusive),
            }
        )

    return {
        "api_path": str(one(system, endpoint, EX.path)),
        "table_name": str(one(system, table, EX.tableName)),
        "id_column": str(one(system, table, EX.idColumn)),
        "rdf_class": str(rdf_class),
        "fields": fields,
    }


def deterministic_value(field: dict):
    if field["datatype"] == str(XSD.string):
        return "x" * max(field["min_length"] or 0, 1)
    if field["datatype"] == str(XSD.decimal):
        minimum = Decimal(str(field["min_exclusive"] or 0))
        return minimum + Decimal("0.01")
    raise ValueError(f"No deterministic value for {field['datatype']}")


def build_work_items(contract: dict) -> list[dict]:
    """Compile the contract into deterministic, independently verifiable work."""
    storage_obligations = [
        f"The SQLite table `{contract['table_name']}` exists.",
        f"The identifier column `{contract['id_column']}` exists.",
    ]
    for field in contract["fields"]:
        requirement = f"The column `{field['name']}` has SQL type `{field['sql_type']}`"
        if field["required"]:
            requirement += " and does not allow NULL"
        storage_obligations.append(requirement + ".")

    response_fields = ", ".join(
        f"`{field['name']}`" for field in contract["fields"]
    )
    return [
        {
            "id": "article.storage.schema",
            "title": f"Provide the `{contract['table_name']}` storage schema",
            "goal": "Make the contracted article shape persistable in SQLite.",
            "depends_on": [],
            "obligations": storage_obligations,
            "test": f"{TEST_PATH}::test_sql_table_matches_contract",
            "excluded": ["HTTP endpoint behavior"],
        },
        {
            "id": "article.query.by-id",
            "title": f"Provide GET {contract['api_path']}",
            "goal": "Return a stored article through the contracted GET endpoint.",
            "depends_on": ["article.storage.schema"],
            "obligations": [
                f"The endpoint `GET {contract['api_path']}` is available.",
                "A stored article is returned with status `200`.",
                f"The response contains exactly the fields {response_fields}.",
                "The response values equal the stored values.",
                "The response conforms to the contracted SHACL shape.",
            ],
            "test": (
                f"{TEST_PATH}::"
                "test_get_endpoint_returns_shape_conformant_article"
            ),
            "excluded": ["Behavior for unknown article identifiers"],
        },
    ]


def render_issue(item: dict) -> str:
    """Render a work item without involving a language model."""
    dependencies = item["depends_on"] or [None]
    lines = [
        "<!-- Generated by tools/generate.py. Do not edit. -->",
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
        "```powershell",
        f"uv run --extra dev pytest -q {item['test']}",
        "```",
        "",
        "## Boundaries",
        "",
        "- Do not edit the product's `specs/` directory or generated tests.",
        "- Implement product behavior under `products/sql_api_example/`.",
        *(f"- Out of scope: {excluded}." for excluded in item["excluded"]),
        "",
    ]
    return "\n".join(lines)


TEST_TEMPLATE = '''# Generated by tools/generate.py. Do not edit.
import sqlite3
from contextlib import closing
from decimal import Decimal

from fastapi.testclient import TestClient
from pyshacl import validate
from rdflib import Graph, Literal, RDF, URIRef

from products.sql_api_example.app import create_app

CONTRACT = {contract}
ARTICLE_VALUES = {article_values}


def test_sql_table_matches_contract(tmp_path):
    db_path = tmp_path / "prototype.sqlite3"
    create_app(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            f"PRAGMA table_info({{CONTRACT['table_name']}})"
        ).fetchall()

    columns = {{row[1]: {{"type": row[2], "not_null": bool(row[3])}} for row in rows}}
    assert CONTRACT["id_column"] in columns
    for field in CONTRACT["fields"]:
        actual = columns[field["name"]]
        assert actual["type"] == field["sql_type"]
        assert actual["not_null"] is field["required"]


def test_get_endpoint_returns_shape_conformant_article(tmp_path):
    db_path = tmp_path / "prototype.sqlite3"
    app = create_app(db_path)
    fields = CONTRACT["fields"]
    names = [field["name"] for field in fields]
    sql_values = [
        float(ARTICLE_VALUES[name])
        if isinstance(ARTICLE_VALUES[name], Decimal)
        else ARTICLE_VALUES[name]
        for name in names
    ]
    placeholders = ", ".join("?" for _ in names)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                f"INSERT INTO {{CONTRACT['table_name']}} ({{', '.join(names)}}) "
                f"VALUES ({{placeholders}})",
                sql_values,
            )
            article_id = cursor.lastrowid

    with TestClient(app) as client:
        response = client.get(
            CONTRACT["api_path"].replace("{{id}}", str(article_id))
        )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == set(names)
    for field in fields:
        actual = payload[field["name"]]
        expected = ARTICLE_VALUES[field["name"]]
        if isinstance(expected, Decimal):
            actual = Decimal(str(actual))
        assert actual == expected

    data = Graph()
    article = URIRef(f"https://example.org/catalog/article-{{article_id}}")
    data.add((article, RDF.type, URIRef(CONTRACT["rdf_class"])))
    for field in fields:
        value = payload[field["name"]]
        if field["datatype"] == "http://www.w3.org/2001/XMLSchema#decimal":
            value = Decimal(str(value))
        data.add((article, URIRef(field["rdf_path"]), Literal(value)))

    conforms, _, report = validate(
        data, shacl_graph="products/sql_api_example/specs/article_shape.ttl"
    )
    assert conforms, report
'''


def main() -> None:
    contract = read_contract()
    work_items = build_work_items(contract)
    article_values = {
        field["name"]: deterministic_value(field) for field in contract["fields"]
    }
    output = TESTS_ROOT / "test_contract.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        TEST_TEMPLATE.format(
            contract=pformat(contract, sort_dicts=False),
            article_values=pformat(article_values, sort_dicts=False),
        ),
        encoding="utf-8",
    )

    generated = ROOT / "generated"
    issues = generated / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    graph_output = generated / "work-graph.json"
    graph_output.write_text(
        json.dumps(
            {"generator": "tools/generate.py", "work_items": work_items},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for item in work_items:
        (issues / f"{item['id']}.md").write_text(
            render_issue(item), encoding="utf-8"
        )

    outputs = [
        output,
        graph_output,
        *(issues / f"{item['id']}.md" for item in work_items),
    ]
    for generated_output in outputs:
        print(f"Generated {generated_output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

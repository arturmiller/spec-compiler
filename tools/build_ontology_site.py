"""Build ontology references and the Relationship Graph for GitHub Pages."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import json
import shutil

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, RDFS, SH

if __package__:
    from .ontology_relationship_graph import build_dataset, dependency_dataset, write_graph_site
    from .ontology_reference import turtle, write_reference
    from .ontology_dependencies import read_dependencies
else:
    from ontology_relationship_graph import build_dataset, dependency_dataset, write_graph_site
    from ontology_reference import turtle, write_reference
    from ontology_dependencies import read_dependencies


ROOT = Path(__file__).parents[1]
ONTOLOGY = ROOT / "ontology" / "shacl-contract.ttl"
SQL_ONTOLOGY = ROOT / "ontology" / "sql-storage.ttl"
PROTOCOL_ONTOLOGY = ROOT / "ontology" / "decision-protocol.ttl"
COMPILER_ONTOLOGY = ROOT / "ontology" / "compiler-contract.ttl"
DECISION_ONTOLOGY = ROOT / "ontology" / "decision-obligation.ttl"
FUNDING_ONTOLOGY = ROOT / "ontology" / "funding.ttl"
CLOUD_ONTOLOGY = ROOT / "ontology" / "cloud-compliance.ttl"
OUTPUT = ROOT / "build" / "ontology-site"
GRAPH_OUTPUT = OUTPUT / "graph"
REFERENCE_OUTPUT = OUTPUT / "ontology"
COMPILER_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "compiler"
DECISION_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "decision"
FUNDING_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "funding"
CLOUD_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "cloud"
SQL_API_OUTPUT = OUTPUT / "examples" / "sql-api"
ONTOLOGY_IRI = "https://arturmiller.github.io/spec-compiler/ontology/"
VOCABULARY_IRI = ONTOLOGY_IRI + "#"
SCO = Namespace(VOCABULARY_IRI)
SQL_ONTOLOGY_IRI = ONTOLOGY_IRI + "sql/"
SQL_VOCABULARY_IRI = SQL_ONTOLOGY_IRI + "#"
SQLO = Namespace(SQL_VOCABULARY_IRI)
PROTOCOL_ONTOLOGY_IRI = ONTOLOGY_IRI + "decision-protocol/"
PROTOCOL_VOCABULARY_IRI = PROTOCOL_ONTOLOGY_IRI + "#"
DPO = Namespace(PROTOCOL_VOCABULARY_IRI)
COMPILER_ONTOLOGY_IRI = ONTOLOGY_IRI + "compiler/"
COMPILER_VOCABULARY_IRI = COMPILER_ONTOLOGY_IRI + "#"
CCO = Namespace(COMPILER_VOCABULARY_IRI)
DECISION_ONTOLOGY_IRI = ONTOLOGY_IRI + "decision/"
DECISION_VOCABULARY_IRI = DECISION_ONTOLOGY_IRI + "#"
SDO = Namespace(DECISION_VOCABULARY_IRI)
FUNDING_ONTOLOGY_IRI = ONTOLOGY_IRI + "funding/"
FUNDING_VOCABULARY_IRI = FUNDING_ONTOLOGY_IRI + "#"
FUNDING = Namespace(FUNDING_VOCABULARY_IRI)
CLOUD_ONTOLOGY_IRI = ONTOLOGY_IRI + "cloud/"
CLOUD_VOCABULARY_IRI = CLOUD_ONTOLOGY_IRI + "#"
CLOUD = Namespace(CLOUD_VOCABULARY_IRI)
SQL_API_IRI = "https://arturmiller.github.io/spec-compiler/resources/sql-api/"
ARTICLE = Namespace(SQL_API_IRI + "#")
SQL_API_VISUALIZATION_IRI = SQL_API_IRI + "visualization/"
SQL_API_VISUALIZATION = Namespace(SQL_API_VISUALIZATION_IRI + "#")
RESOURCE_PUBLICATIONS = {
    "spec_compiler": ("toolchain", "Spec Compiler resources"),
    "sql_api_example": ("sql-api", "SQL API example resources"),
    "kfw_458_eligibility": (
        "funding/kfw-458",
        "KfW 458 applicant eligibility resources",
    ),
    "cloud_access_compliance": (
        "cloud/privileged-access",
        "Cloud privileged-access compliance resources",
    ),
}
ONTOLOGY_PUBLICATIONS = (
    (ONTOLOGY, ONTOLOGY_IRI, VOCABULARY_IRI),
    (SQL_ONTOLOGY, SQL_ONTOLOGY_IRI, SQL_VOCABULARY_IRI),
    (PROTOCOL_ONTOLOGY, PROTOCOL_ONTOLOGY_IRI, PROTOCOL_VOCABULARY_IRI),
    (COMPILER_ONTOLOGY, COMPILER_ONTOLOGY_IRI, COMPILER_VOCABULARY_IRI),
    (DECISION_ONTOLOGY, DECISION_ONTOLOGY_IRI, DECISION_VOCABULARY_IRI),
    (FUNDING_ONTOLOGY, FUNDING_ONTOLOGY_IRI, FUNDING_VOCABULARY_IRI),
    (CLOUD_ONTOLOGY, CLOUD_ONTOLOGY_IRI, CLOUD_VOCABULARY_IRI),
)


@contextmanager
def site_output(output: Path):
    """Point derived artifacts at a private candidate, never at live preview files."""
    global OUTPUT, GRAPH_OUTPUT, REFERENCE_OUTPUT, DECISION_REFERENCE_OUTPUT, COMPILER_REFERENCE_OUTPUT
    global FUNDING_REFERENCE_OUTPUT, CLOUD_REFERENCE_OUTPUT, SQL_API_OUTPUT
    previous = (OUTPUT, GRAPH_OUTPUT, REFERENCE_OUTPUT, DECISION_REFERENCE_OUTPUT,
                FUNDING_REFERENCE_OUTPUT, CLOUD_REFERENCE_OUTPUT, SQL_API_OUTPUT, COMPILER_REFERENCE_OUTPUT)
    OUTPUT = output
    GRAPH_OUTPUT = output / "graph"
    REFERENCE_OUTPUT = output / "ontology"
    COMPILER_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "compiler"
    DECISION_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "decision"
    FUNDING_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "funding"
    CLOUD_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "cloud"
    SQL_API_OUTPUT = output / "examples" / "sql-api"
    try:
        yield
    finally:
        (OUTPUT, GRAPH_OUTPUT, REFERENCE_OUTPUT, DECISION_REFERENCE_OUTPUT,
         FUNDING_REFERENCE_OUTPUT, CLOUD_REFERENCE_OUTPUT, SQL_API_OUTPUT, COMPILER_REFERENCE_OUTPUT) = previous


def product_ontology_roots() -> list[Path]:
    return sorted(path.parent for path in (ROOT / "products").glob("*/specs"))


def dependency_analysis() -> dict:
    return read_dependencies(ONTOLOGY_PUBLICATIONS, product_ontology_roots())


def validate_publication_sources() -> None:
    dependency_analysis()
    definitions = set()
    unlabeled = []
    for ontology_path, ontology_iri, vocabulary_iri in ONTOLOGY_PUBLICATIONS:
        ontology = Graph().parse(ontology_path, format="turtle")
        ontology_resource = URIRef(ontology_iri)
        if (ontology_resource, RDF.type, OWL.Ontology) not in ontology:
            raise ValueError(
                f"{ontology_path} must declare {ontology_iri} as owl:Ontology"
            )
        ontology_definitions = {
            subject
            for subject in ontology.subjects()
            if str(subject).startswith(vocabulary_iri)
        }
        definitions.update(ontology_definitions)
        for subject in ontology_definitions:
            languages = {
                label.language for label in ontology.objects(subject, RDFS.label)
            }
            missing_languages = {"de", "en"} - languages
            if missing_languages:
                unlabeled.append(
                    f"{subject} (missing {', '.join(sorted(missing_languages))})"
                )
    unlabeled.sort()
    if unlabeled:
        raise ValueError(f"Public ontology terms lack rdfs:label: {unlabeled}")

    used_terms = set()
    authored_graphs = sorted((ROOT / "products").glob("*/specs/*.ttl")) + sorted(
        (ROOT / "ontology").glob("*.ttl")
    )
    public_namespaces = tuple(
        vocabulary_iri for _, _, vocabulary_iri in ONTOLOGY_PUBLICATIONS
    )
    for authored_graph in authored_graphs:
        text = authored_graph.read_text(encoding="utf-8")
        if "https://example.org/" in text:
            raise ValueError(
                f"Example namespace remains in public RDF source: {authored_graph}"
            )
        graph = Graph().parse(authored_graph, format="turtle")
        for triple in graph:
            used_terms.update(
                value
                for value in triple
                if isinstance(value, URIRef)
                and str(value).startswith(public_namespaces)
            )
    undefined = sorted(str(term) for term in used_terms - definitions)
    if undefined:
        raise ValueError(f"Specs use undefined public ontology terms: {undefined}")

    sql_api = Graph()
    for spec_file in sorted(
        (ROOT / "products" / "sql_api_example" / "specs").glob("*.ttl")
    ):
        sql_api.parse(spec_file, format="turtle")
    if (ARTICLE.Article, RDF.type, OWL.Class) not in sql_api:
        raise ValueError("SQL API example must declare article:Article as owl:Class")
    for term in (ARTICLE.Article, ARTICLE.description, ARTICLE.price):
        languages = {
            label.language for label in sql_api.objects(term, RDFS.label)
        }
        if {"de", "en"} - languages:
            raise ValueError(f"SQL API visual term lacks bilingual labels: {term}")


def _write_graph_redirect() -> None:
    """Keep previously shared graph links pointing at the unified entry point."""
    GRAPH_OUTPUT.mkdir(parents=True, exist_ok=True)
    (GRAPH_OUTPUT / "index.html").write_text(
        '''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ontologie-Beziehungsgraph · Spec Compiler</title>
  <script>
    const target = new URL('../ontologies/', location.href);
    target.search = location.search;
    target.hash = location.hash;
    location.replace(target.href);
  </script>
</head>
<body>
  <p><a href="../ontologies/">Ontologie-Beziehungsgraph öffnen</a></p>
</body>
</html>
''',
        encoding="utf-8",
    )


def _publish_examples() -> None:
    examples = OUTPUT / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    links = []
    publications: dict[str, list[tuple[Path, Path]]] = {
        product_name: [] for product_name in RESOURCE_PUBLICATIONS
    }
    for spec_file in sorted((ROOT / "products").glob("*/specs/*.ttl")):
        product_name = spec_file.parents[1].name
        if product_name not in RESOURCE_PUBLICATIONS:
            continue
        destination = examples / f"{product_name}-{spec_file.name}"
        shutil.copy2(spec_file, destination)
        links.append(f'<li><a href="{destination.name}">{destination.name}</a></li>')
        if product_name in publications:
            publications[product_name].append((spec_file, destination))
    (examples / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
        "<title>Example specifications</title><body>"
        "<h1>Example specifications</h1><p>These files use the ontology but are "
        "not part of its vocabulary definition.</p><ul>"
        + "".join(links)
        + "</ul><p><a href=\"../\">Back</a></p></body></html>\n",
        encoding="utf-8",
    )
    for product_name, (public_path, title) in RESOURCE_PUBLICATIONS.items():
        resource_root = OUTPUT / "resources" / public_path
        resource_root.mkdir(parents=True, exist_ok=True)
        site_root_href = "../" * (len(Path(public_path).parts) + 1)
        resource_graph = Graph()
        resource_links = []
        for spec_file, destination in publications[product_name]:
            resource_graph.parse(spec_file, format="turtle")
            resource_links.append(
                f'<li><a href="{site_root_href}examples/{destination.name}">'
                f"{destination.name}</a></li>"
            )
        (resource_root / "resources.ttl").write_text(turtle(resource_graph), encoding="utf-8", newline="\n")
        visualization_link = (
            f'<a href="{site_root_href}ontologies/?ontology=sql-api">'
            "Ontology Relationship Graph</a> · "
            if product_name == "sql_api_example"
            else ""
        )
        (resource_root / "index.html").write_text(
            "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            f"<title>{title}</title><body><h1>{title}</h1>"
            "<p>This page is the dereference target for the resource namespace. "
            "The resources are examples that use the public ontology.</p><ul>"
            + "".join(resource_links)
            + "</ul><p><a href=\"resources.ttl\">Combined Turtle graph</a> · "
            + visualization_link
            + f'<a href="{site_root_href}">Back</a></p></body></html>\n',
            encoding="utf-8",
        )


def _single_target_class(graph: Graph, shape: URIRef) -> URIRef:
    targets = list(graph.objects(shape, SH.targetClass))
    if len(targets) != 1 or not isinstance(targets[0], URIRef):
        raise ValueError(
            f"Visualization relation target {shape} must have exactly one "
            "sh:targetClass"
        )
    return targets[0]


def _add_visualization_edge(
    graph: Graph,
    *,
    source: URIRef,
    target: URIRef,
    relation_name: str,
    label_en: str,
    label_de: str,
) -> URIRef:
    source_name = source.rsplit("#", 1)[-1]
    target_name = target.rsplit("#", 1)[-1]
    relation = SQL_API_VISUALIZATION[
        f"{source_name}-{relation_name}-{target_name}"
    ]
    graph.add((relation, RDF.type, OWL.ObjectProperty))
    graph.add((relation, RDFS.label, Literal(label_en, lang="en")))
    graph.add((relation, RDFS.label, Literal(label_de, lang="de")))
    graph.add((relation, RDFS.domain, source))
    graph.add((relation, RDFS.range, target))
    return relation


def _project_shape(graph: Graph, shape: URIRef) -> set[URIRef]:
    target = _single_target_class(graph, shape)
    graph.add((shape, RDF.type, OWL.Class))
    graph.add((shape, RDFS.label, Literal("Article shape", lang="en")))
    graph.add((shape, RDFS.label, Literal("Artikel-Shape", lang="de")))
    return {
        shape,
        _add_visualization_edge(
            graph,
            source=shape,
            target=target,
            relation_name="target-class",
            label_en="target class",
            label_de="Zielklasse",
        ),
    }


def _add_sql_api_visualization_projection(graph: Graph) -> set[URIRef]:
    """Project explicit instance/SHACL relations for the Relationship Graph."""
    generated_terms: set[URIRef] = set()
    endpoints = set(graph.subjects(RDF.type, SCO.GetEndpoint))
    tables = set(graph.subjects(RDF.type, SQLO.SqlTable))

    for endpoint in endpoints:
        if not isinstance(endpoint, URIRef):
            continue
        graph.add((endpoint, RDF.type, OWL.Class))
        graph.add((endpoint, RDFS.label, Literal("GET endpoint", lang="en")))
        graph.add((endpoint, RDFS.label, Literal("GET-Endpunkt", lang="de")))
        generated_terms.add(endpoint)

        for shape in graph.objects(endpoint, SCO.returns):
            if isinstance(shape, URIRef):
                generated_terms.update(_project_shape(graph, shape))
                generated_terms.add(
                    _add_visualization_edge(
                        graph,
                        source=endpoint,
                        target=shape,
                        relation_name="returns",
                        label_en="returns",
                        label_de="liefert",
                    )
                )
        for table in graph.objects(endpoint, SQLO.readsFrom):
            if isinstance(table, URIRef):
                generated_terms.add(
                    _add_visualization_edge(
                        graph,
                        source=endpoint,
                        target=table,
                        relation_name="reads-from",
                        label_en="reads from",
                        label_de="liest aus",
                    )
                )

    for table in tables:
        if not isinstance(table, URIRef):
            continue
        graph.add((table, RDF.type, OWL.Class))
        graph.add((table, RDFS.label, Literal("articles table", lang="en")))
        graph.add((table, RDFS.label, Literal("Artikeltabelle", lang="de")))
        generated_terms.add(table)
        for shape in graph.objects(table, SQLO.stores):
            if isinstance(shape, URIRef):
                generated_terms.update(_project_shape(graph, shape))
                generated_terms.add(
                    _add_visualization_edge(
                        graph,
                        source=table,
                        target=shape,
                        relation_name="stores",
                        label_en="stores",
                        label_de="speichert",
                    )
                )
    return generated_terms


def compiler_term_migrations() -> dict[str, str]:
    graph = Graph().parse(COMPILER_ONTOLOGY, format="turtle")
    return {VOCABULARY_IRI + str(term)[len(COMPILER_VOCABULARY_IRI):]: str(term)
            for term in sorted(set(graph.subjects()), key=str)
            if isinstance(term, URIRef) and str(term).startswith(COMPILER_VOCABULARY_IRI)}


def term_migrations() -> dict[str, str]:
    result = compiler_term_migrations()
    for source, _iri, namespace in ONTOLOGY_PUBLICATIONS:
        if source not in (SQL_ONTOLOGY, PROTOCOL_ONTOLOGY):
            continue
        graph = Graph().parse(source, format="turtle")
        result.update({VOCABULARY_IRI + str(term)[len(namespace):]: str(term)
                       for term in set(graph.subjects()) if str(term).startswith(namespace)})
    return dict(sorted(result.items()))


def build_relationship_graph(sql_api_graph: Graph | None = None) -> None:
    """Refresh just the ontology viewer for the local authoring loop."""
    if sql_api_graph is None:
        sql_api_graph = Graph()
        for source in sorted((ROOT / "products" / "sql_api_example" / "specs").glob("*.ttl")):
            sql_api_graph.parse(source, format="turtle")
        _add_sql_api_visualization_projection(sql_api_graph)
    catalog = Graph()
    publications = {}
    for path, _iri, namespace in ONTOLOGY_PUBLICATIONS:
        module = Graph().parse(path, format='turtle')
        catalog += module
        key = 'contract' if path == ONTOLOGY else str(_iri).rstrip('/').rsplit('/', 1)[-1]
        publications[namespace] = {'key': key,
            'title': next(str(value) for value in module.objects(URIRef(_iri), DCTERMS.title)
                          if value.language == 'en'),
            'referenceHref': '../ontology/' + (key + '/' if key != 'contract' else '')}
    datasets = [
        build_dataset(
            Graph().parse(path, format="turtle"),
            key=key,
            title=title,
            namespace=namespace,
            source_href=source_href,
            reference_href=reference_href,
            context_graph=catalog,
            publications=publications,
        )
        for path, key, title, namespace, source_href, reference_href in (
            (
                ONTOLOGY, "contract", "HTTP API Ontology", VOCABULARY_IRI,
                "../ontology/ontology.ttl", "../ontology/",
            ),
            (
                SQL_ONTOLOGY, "sql", "SQL Storage Ontology", SQL_VOCABULARY_IRI,
                "../ontology/sql/ontology.ttl", "../ontology/sql/",
            ),
            (
                PROTOCOL_ONTOLOGY, "decision-protocol", "Decision Protocol Ontology", PROTOCOL_VOCABULARY_IRI,
                "../ontology/decision-protocol/ontology.ttl", "../ontology/decision-protocol/",
            ),
            (
                COMPILER_ONTOLOGY, "compiler", "Compiler Contract Ontology", COMPILER_VOCABULARY_IRI,
                "../ontology/compiler/ontology.ttl", "../ontology/compiler/",
            ),
            (
                DECISION_ONTOLOGY, "decision", "Decision and Obligation Core Ontology",
                DECISION_VOCABULARY_IRI, "../ontology/decision/ontology.ttl", "../ontology/decision/",
            ),
            (
                FUNDING_ONTOLOGY, "funding", "Funding Domain Ontology", FUNDING_VOCABULARY_IRI,
                "../ontology/funding/ontology.ttl", "../ontology/funding/",
            ),
            (
                CLOUD_ONTOLOGY, "cloud", "Cloud Compliance Domain Ontology", CLOUD_VOCABULARY_IRI,
                "../ontology/cloud/ontology.ttl", "../ontology/cloud/",
            ),
        )
    ]
    datasets.append(
        build_dataset(
            sql_api_graph,
            key="sql-api",
            title="SQL API example",
            namespace=str(ARTICLE),
            source_href="../resources/sql-api/resources.ttl",
            reference_href="../examples/sql-api/",
            property_namespaces=(str(SQL_API_VISUALIZATION),),
        )
    )
    sql_edges = {
        (edge["source"], edge["target"])
        for edge in datasets[-1]["edges"]
    }
    expected_sql_edges = {
        (str(ARTICLE.GetArticleEndpoint), str(ARTICLE.ArticleShape)),
        (str(ARTICLE.GetArticleEndpoint), str(ARTICLE.ArticlesTable)),
        (str(ARTICLE.ArticlesTable), str(ARTICLE.ArticleShape)),
        (str(ARTICLE.ArticleShape), str(ARTICLE.Article)),
    }
    if not expected_sql_edges <= sql_edges:
        raise ValueError("SQL API Relationship Graph is missing its Shape chain")
    migrations = term_migrations()
    for dataset in datasets[:-1]:
        dataset["legacyTerms"] = {old: new for old, new in migrations.items()
                                  if new.startswith(dataset["namespace"])}
    write_graph_site(OUTPUT / "ontologies", [dependency_dataset(dependency_analysis()), *datasets[:-1]])
    example = dict(datasets[-1])
    example["sourceHref"] = "../../../resources/sql-api/resources.ttl"
    example["referenceHref"] = "../../../examples/sql-api/"
    write_graph_site(OUTPUT / "tutorials" / "sql-api" / "graph", [example],
                     overview_href="../../../ontologies/overview.html")
    _write_graph_redirect()


def build_site() -> None:
    """Build a private, complete ontology candidate without Java or WIDOCO."""
    output = OUTPUT.resolve()
    build_root = (ROOT / "build").resolve()
    if not output.is_relative_to(build_root):
        raise ValueError(f"Refusing to replace output outside {build_root}: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    publications = {
        VOCABULARY_IRI: "ontology/",
        SQL_VOCABULARY_IRI: "ontology/sql/",
        PROTOCOL_VOCABULARY_IRI: "ontology/decision-protocol/",
        COMPILER_VOCABULARY_IRI: "ontology/compiler/",
        DECISION_VOCABULARY_IRI: "ontology/decision/",
        FUNDING_VOCABULARY_IRI: "ontology/funding/",
        CLOUD_VOCABULARY_IRI: "ontology/cloud/",
        str(ARTICLE): "examples/sql-api/",
    }
    for source, reference, title, namespace, landing, key in (
        (ONTOLOGY, REFERENCE_OUTPUT, "HTTP API Ontology", VOCABULARY_IRI, "../", "contract"),
        (SQL_ONTOLOGY, REFERENCE_OUTPUT / "sql", "SQL Storage Ontology", SQL_VOCABULARY_IRI, "../../", "sql"),
        (PROTOCOL_ONTOLOGY, REFERENCE_OUTPUT / "decision-protocol", "Decision Protocol Ontology", PROTOCOL_VOCABULARY_IRI, "../../", "decision-protocol"),
        (COMPILER_ONTOLOGY, COMPILER_REFERENCE_OUTPUT, "Compiler Contract Ontology", COMPILER_VOCABULARY_IRI, "../../", "compiler"),
        (DECISION_ONTOLOGY, DECISION_REFERENCE_OUTPUT, "Decision and Obligation Core Ontology", DECISION_VOCABULARY_IRI, "../../", "decision"),
        (FUNDING_ONTOLOGY, FUNDING_REFERENCE_OUTPUT, "Funding Domain Ontology", FUNDING_VOCABULARY_IRI, "../../", "funding"),
        (CLOUD_ONTOLOGY, CLOUD_REFERENCE_OUTPUT, "Cloud Compliance Domain Ontology", CLOUD_VOCABULARY_IRI, "../../", "cloud"),
    ):
        write_reference(Graph().parse(source, format="turtle"), reference, title=title,
                        namespace=namespace, graph_key=key, site_root_href=landing, publications=publications,
                        moved_terms=term_migrations() if key == "contract" else None)
    _publish_examples()
    sql_api = Graph()
    for source in sorted((ROOT / "products" / "sql_api_example" / "specs").glob("*.ttl")):
        sql_api.parse(source, format="turtle")
    _add_sql_api_visualization_projection(sql_api)
    write_reference(sql_api, SQL_API_OUTPUT, title="SQL API Example", namespace=str(ARTICLE),
                    graph_key="sql-api", site_root_href="../../", publications=publications,
                    source_href="../../resources/sql-api/resources.ttl", derived=True)
    build_relationship_graph(sql_api)
    (OUTPUT / "ontologies").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "ontologies" / "dependencies.json").write_text(
        json.dumps(dependency_analysis(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="Validate public RDF sources without building HTML")
    args = parser.parse_args()
    validate_publication_sources()
    if args.validate_only:
        print("Ontology publication sources are valid.")
        return
    build_site()
    print(f"Built ontology site at {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

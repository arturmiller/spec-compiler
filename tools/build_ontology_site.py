"""Build unversioned WIDOCO/WebVOWL documentation for GitHub Pages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, RDFS, SH


ROOT = Path(__file__).parents[1]
ONTOLOGY = ROOT / "ontology" / "shacl-contract.ttl"
OUTPUT = ROOT / "build" / "ontology-site"
REFERENCE_OUTPUT = OUTPUT / "ontology"
SQL_API_OUTPUT = OUTPUT / "examples" / "sql-api"
CACHE = ROOT / ".cache" / "widoco"
WIDOCO_VERSION = "1.4.25"
WIDOCO_NAME = f"widoco-{WIDOCO_VERSION}-jar-with-dependencies_JDK-17.jar"
WIDOCO_URL = (
    "https://github.com/dgarijo/Widoco/releases/download/"
    f"v{WIDOCO_VERSION}/{WIDOCO_NAME}"
)
WIDOCO_SHA256 = "be57a270fffb91e55810fa308717e704a44e2e7c027a3d68125a49da6c8b4e2b"
ONTOLOGY_IRI = "https://arturmiller.github.io/spec-compiler/ontology/"
VOCABULARY_IRI = ONTOLOGY_IRI + "#"
SCO = Namespace(VOCABULARY_IRI)
SQL_API_IRI = "https://arturmiller.github.io/spec-compiler/resources/sql-api/"
ARTICLE = Namespace(SQL_API_IRI + "#")
SQL_API_VISUALIZATION_IRI = SQL_API_IRI + "visualization/"
SQL_API_VISUALIZATION = Namespace(SQL_API_VISUALIZATION_IRI + "#")
RESOURCE_PUBLICATIONS = {
    "spec_compiler": ("toolchain", "Spec Compiler resources"),
    "sql_api_example": ("sql-api", "SQL API example resources"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _widoco_jar(explicit: Path | None) -> Path:
    if explicit is not None:
        jar = explicit.resolve()
    else:
        jar = CACHE / WIDOCO_NAME
        if not jar.exists():
            jar.parent.mkdir(parents=True, exist_ok=True)
            temporary = jar.with_suffix(".download")
            with urlopen(WIDOCO_URL) as response, temporary.open("wb") as target:
                shutil.copyfileobj(response, target)
            temporary.replace(jar)
    if not jar.is_file():
        raise ValueError(f"WIDOCO JAR does not exist: {jar}")
    actual_hash = _sha256(jar)
    if actual_hash != WIDOCO_SHA256:
        raise ValueError(
            f"Unexpected WIDOCO SHA-256 for {jar}: {actual_hash}"
        )
    return jar


def validate_publication_sources() -> None:
    ontology = Graph().parse(ONTOLOGY, format="turtle")
    ontology_resource = URIRef(ONTOLOGY_IRI)
    if (ontology_resource, RDF.type, OWL.Ontology) not in ontology:
        raise ValueError(f"{ONTOLOGY} must declare {ONTOLOGY_IRI} as owl:Ontology")

    definitions = {
        subject
        for subject in ontology.subjects()
        if str(subject).startswith(VOCABULARY_IRI)
    }
    unlabeled = []
    for subject in definitions:
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
    for spec_file in sorted((ROOT / "products").glob("*/specs/*.ttl")):
        text = spec_file.read_text(encoding="utf-8")
        if "https://example.org/" in text:
            raise ValueError(f"Example namespace remains in public spec: {spec_file}")
        graph = Graph().parse(spec_file, format="turtle")
        for triple in graph:
            used_terms.update(
                value
                for value in triple
                if str(value).startswith(VOCABULARY_IRI)
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


def _write_landing_page() -> None:
    (OUTPUT / "index.html").write_text(
        '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SHACL Contract Ontology</title>
  <style>
    body { font: 18px/1.55 system-ui, sans-serif; max-width: 52rem; margin: 5rem auto; padding: 0 1.5rem; color: #17202a; }
    h1 { line-height: 1.15; }
    nav { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); margin: 2rem 0; }
    a { color: #075fa8; }
    .card { border: 1px solid #ccd6dd; border-radius: .6rem; padding: 1rem; text-decoration: none; }
    .card strong { display: block; margin-bottom: .35rem; }
    code { overflow-wrap: anywhere; }
  </style>
</head>
<body>
  <h1>SHACL Contract Ontology</h1>
  <p>Experimental vocabulary for executable product and transformation contracts.</p>
  <nav>
    <a class="card" href="ontology/index-en.html"><strong>English reference</strong>Classes, properties, metadata and downloads</a>
    <a class="card" href="ontology/index-de.html"><strong>Deutsche Referenz</strong>Klassen, Properties, Metadaten und Downloads</a>
    <a class="card" href="ontology/webvowl/index.html"><strong>Interactive graph</strong>Explore and search the ontology with WebVOWL</a>
    <a class="card" href="examples/sql-api/webvowl/index.html"><strong>SQL API example graph</strong>Explore Article, description and price separately</a>
    <a class="card" href="ontology/ontology.ttl"><strong>Turtle</strong>Download the published ontology</a>
  </nav>
  <p>Namespace: <code>https://arturmiller.github.io/spec-compiler/ontology/#</code></p>
  <p><a href="examples/">Published example specifications</a> · <a href="https://github.com/arturmiller/spec-compiler">Source repository</a></p>
</body>
</html>
''',
        encoding="utf-8",
    )


def _write_reference_index() -> None:
    (REFERENCE_OUTPUT / "index.html").write_text(
        '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SHACL Contract Ontology reference</title>
  <style>body { font: 18px/1.55 system-ui, sans-serif; max-width: 46rem; margin: 5rem auto; padding: 0 1.5rem; } li { margin: .7rem 0; } a { color: #075fa8; }</style>
</head>
<body>
  <h1>SHACL Contract Ontology reference</h1>
  <p>This document is the target of the public vocabulary namespace.</p>
  <ul>
    <li><a href="index-en.html">English reference</a></li>
    <li><a href="index-de.html">Deutsche Referenz</a></li>
    <li><a href="webvowl/index.html">Interactive WebVOWL graph and entity search</a></li>
    <li><a href="ontology.ttl">Turtle serialization</a></li>
  </ul>
  <p><a href="../">Project ontology landing page</a></p>
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
        resource_graph = Graph()
        resource_links = []
        for spec_file, destination in publications[product_name]:
            resource_graph.parse(spec_file, format="turtle")
            resource_links.append(
                f'<li><a href="../../examples/{destination.name}">'
                f"{destination.name}</a></li>"
            )
        resource_graph.serialize(
            destination=resource_root / "resources.ttl", format="turtle"
        )
        visualization_link = (
            '<a href="../../examples/sql-api/webvowl/index.html">'
            "Interactive WebVOWL graph</a> · "
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
            + "<a href=\"../../\">Back</a></p></body></html>\n",
            encoding="utf-8",
        )


def _run_widoco(jar: Path, ontology: Path, output: Path) -> None:
    subprocess.run(
        [
            "java",
            "-jar",
            str(jar),
            "-ontFile",
            str(ontology),
            "-outFolder",
            str(output.resolve()),
            "-rewriteAll",
            "-getOntologyMetadata",
            "-includeAnnotationProperties",
            "-lang",
            "en-de",
            "-webVowl",
            "-noPlaceHolderText",
        ],
        cwd=ROOT,
        check=True,
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
    """Project instance/SHACL relations into an OWL graph understood by WebVOWL."""
    generated_terms: set[URIRef] = set()
    endpoints = set(graph.subjects(RDF.type, SCO.GetEndpoint))
    tables = set(graph.subjects(RDF.type, SCO.SqlTable))

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
        for table in graph.objects(endpoint, SCO.readsFrom):
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
        for shape in graph.objects(table, SCO.stores):
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


def _build_sql_api_visualization(jar: Path) -> None:
    graph = Graph()
    for spec_file in sorted(
        (ROOT / "products" / "sql_api_example" / "specs").glob("*.ttl")
    ):
        graph.parse(spec_file, format="turtle")
    visualization_iri = URIRef(SQL_API_VISUALIZATION_IRI)
    graph.add((visualization_iri, RDF.type, OWL.Ontology))
    graph.add(
        (visualization_iri, DCTERMS.title, Literal("SQL API example", lang="en"))
    )
    graph.add(
        (visualization_iri, DCTERMS.title, Literal("SQL-API-Beispiel", lang="de"))
    )
    graph.add(
        (
            visualization_iri,
            DCTERMS.description,
            Literal(
                "Derived OWL projection for visualization; the linked Turtle "
                "specifications remain authoritative.",
                lang="en",
            ),
        )
    )
    projected_terms = _add_sql_api_visualization_projection(graph)
    expected_projected_terms = {
        ARTICLE.GetArticleEndpoint,
        ARTICLE.ArticlesTable,
        ARTICLE.ArticleShape,
        SQL_API_VISUALIZATION["GetArticleEndpoint-returns-ArticleShape"],
        SQL_API_VISUALIZATION["GetArticleEndpoint-reads-from-ArticlesTable"],
        SQL_API_VISUALIZATION["ArticlesTable-stores-ArticleShape"],
        SQL_API_VISUALIZATION["ArticleShape-target-class-Article"],
    }
    missing_projected_terms = expected_projected_terms - projected_terms
    if missing_projected_terms:
        raise ValueError(
            "SQL API visualization projection is incomplete: "
            f"{sorted(map(str, missing_projected_terms))}"
        )
    source = OUTPUT.parent / "sql-api-visualization.ttl"
    graph.serialize(destination=source, format="turtle")
    try:
        _run_widoco(jar, source, SQL_API_OUTPUT)
        nested_output = SQL_API_OUTPUT / "doc"
        if nested_output.is_dir():
            for child in nested_output.iterdir():
                shutil.move(str(child), SQL_API_OUTPUT / child.name)
            nested_output.rmdir()
    finally:
        source.unlink(missing_ok=True)


def build_site(jar: Path) -> None:
    output = OUTPUT.resolve()
    build_root = (ROOT / "build").resolve()
    if not output.is_relative_to(build_root):
        raise ValueError(f"Refusing to replace output outside {build_root}: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_widoco(jar, ONTOLOGY, REFERENCE_OUTPUT)
    _write_landing_page()
    _write_reference_index()
    _publish_examples()
    _build_sql_api_visualization(jar)
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")
    required = [
        OUTPUT / "index.html",
        REFERENCE_OUTPUT / "index.html",
        REFERENCE_OUTPUT / "index-en.html",
        REFERENCE_OUTPUT / "index-de.html",
        REFERENCE_OUTPUT / "ontology.ttl",
        REFERENCE_OUTPUT / "webvowl" / "index.html",
        REFERENCE_OUTPUT / "webvowl" / "data" / "ontology.json",
        OUTPUT / "resources" / "toolchain" / "index.html",
        OUTPUT / "resources" / "toolchain" / "resources.ttl",
        OUTPUT / "resources" / "sql-api" / "index.html",
        OUTPUT / "resources" / "sql-api" / "resources.ttl",
        SQL_API_OUTPUT / "index-en.html",
        SQL_API_OUTPUT / "index-de.html",
        SQL_API_OUTPUT / "webvowl" / "index.html",
        SQL_API_OUTPUT / "webvowl" / "data" / "ontology.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"WIDOCO site is incomplete: {missing}")
    webvowl = (REFERENCE_OUTPUT / "webvowl" / "index.html").read_text(
        encoding="utf-8"
    )
    if 'id="search-input-text"' not in webvowl:
        raise ValueError("Generated WebVOWL site has no entity search input")
    webvowl_data = json.loads(
        (REFERENCE_OUTPUT / "webvowl" / "data" / "ontology.json").read_text(
            encoding="utf-8"
        )
    )
    serialized_data = json.dumps(webvowl_data)
    missing_visual_terms = [
        str(term)
        for term in (SCO.TransformationContract, SCO.GetEndpoint, SCO.SqlTable)
        if str(term) not in serialized_data
    ]
    if missing_visual_terms:
        raise ValueError(
            f"Core ontology terms are absent from WebVOWL: {missing_visual_terms}"
        )
    sql_api_webvowl = (SQL_API_OUTPUT / "webvowl" / "index.html").read_text(
        encoding="utf-8"
    )
    if 'id="search-input-text"' not in sql_api_webvowl:
        raise ValueError("SQL API WebVOWL site has no entity search input")
    sql_api_data = json.loads(
        (SQL_API_OUTPUT / "webvowl" / "data" / "ontology.json").read_text(
            encoding="utf-8"
        )
    )
    serialized_sql_api = json.dumps(sql_api_data)
    missing_example_terms = [
        str(term)
        for term in (
            ARTICLE.Article,
            ARTICLE.description,
            ARTICLE.price,
            ARTICLE.GetArticleEndpoint,
            ARTICLE.ArticlesTable,
            ARTICLE.ArticleShape,
            SQL_API_VISUALIZATION["GetArticleEndpoint-returns-ArticleShape"],
            SQL_API_VISUALIZATION["GetArticleEndpoint-reads-from-ArticlesTable"],
            SQL_API_VISUALIZATION["ArticlesTable-stores-ArticleShape"],
            SQL_API_VISUALIZATION["ArticleShape-target-class-Article"],
        )
        if str(term) not in serialized_sql_api
    ]
    if missing_example_terms:
        raise ValueError(
            f"SQL API terms are absent from WebVOWL: {missing_example_terms}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--widoco-jar",
        type=Path,
        help="Use this pinned WIDOCO 1.4.25 JDK 17 JAR instead of the cache",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate ontology publication sources without building HTML",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_publication_sources()
    if args.validate_only:
        print("Ontology publication sources are valid.")
        return
    build_site(_widoco_jar(args.widoco_jar))
    print(f"Built ontology site at {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

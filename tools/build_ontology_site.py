"""Build ontology references and the Relationship Graph for GitHub Pages."""

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

from ontology_relationship_graph import build_dataset, write_graph_site


ROOT = Path(__file__).parents[1]
ONTOLOGY = ROOT / "ontology" / "shacl-contract.ttl"
DECISION_ONTOLOGY = ROOT / "ontology" / "decision-obligation.ttl"
FUNDING_ONTOLOGY = ROOT / "ontology" / "funding.ttl"
CLOUD_ONTOLOGY = ROOT / "ontology" / "cloud-compliance.ttl"
OUTPUT = ROOT / "build" / "ontology-site"
GRAPH_OUTPUT = OUTPUT / "graph"
REFERENCE_OUTPUT = OUTPUT / "ontology"
DECISION_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "decision"
FUNDING_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "funding"
CLOUD_REFERENCE_OUTPUT = REFERENCE_OUTPUT / "cloud"
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
    (DECISION_ONTOLOGY, DECISION_ONTOLOGY_IRI, DECISION_VOCABULARY_IRI),
    (FUNDING_ONTOLOGY, FUNDING_ONTOLOGY_IRI, FUNDING_VOCABULARY_IRI),
    (CLOUD_ONTOLOGY, CLOUD_ONTOLOGY_IRI, CLOUD_VOCABULARY_IRI),
)


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


def _write_landing_page() -> None:
    (OUTPUT / "index.html").write_text(
        '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spec Compiler ontologies</title>
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
  <h1>Spec Compiler ontologies</h1>
  <p>Separate experimental vocabularies for executable contracts, reusable decision semantics, funding concepts, and cloud-compliance concepts. Explore their fixed-layout relationship graphs or read the bilingual references.</p>
  <nav>
    <a class="card" href="ontology/index-en.html"><strong>SHACL Contract Ontology</strong>Executable product and protocol contracts</a>
    <a class="card" href="ontology/decision/index-en.html"><strong>Decision and Obligation Core Ontology</strong>Domain-independent decision semantics</a>
    <a class="card" href="ontology/funding/index-en.html"><strong>Funding Domain Ontology</strong>Funding programs and scoped eligibility</a>
    <a class="card" href="ontology/cloud/index-en.html"><strong>Cloud Compliance Domain Ontology</strong>Cloud systems and scoped policy decisions</a>
    <a class="card" href="graph/?ontology=contract"><strong>Contract graph</strong>Explore the contract vocabulary</a>
    <a class="card" href="graph/?ontology=decision"><strong>Decision graph</strong>Explore the core decision vocabulary</a>
    <a class="card" href="graph/?ontology=funding"><strong>Funding graph</strong>Explore the funding vocabulary</a>
    <a class="card" href="graph/?ontology=cloud"><strong>Cloud graph</strong>Explore the cloud-compliance vocabulary</a>
    <a class="card" href="graph/?ontology=sql-api"><strong>SQL API example graph</strong>Explore Article, Shape, endpoint, and table separately</a>
  </nav>
  <p>Namespaces: <code>.../ontology/#</code>, <code>.../ontology/decision/#</code>, <code>.../ontology/funding/#</code>, and <code>.../ontology/cloud/#</code></p>
  <p><a href="examples/">Published example specifications</a> · <a href="https://github.com/arturmiller/spec-compiler">Source repository</a></p>
</body>
</html>
''',
        encoding="utf-8",
    )


def _write_reference_index(
    output: Path, *, title: str, landing_page: str, graph_key: str
) -> None:
    (output / "index.html").write_text(
        f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} reference</title>
  <style>body {{ font: 18px/1.55 system-ui, sans-serif; max-width: 46rem; margin: 5rem auto; padding: 0 1.5rem; }} li {{ margin: .7rem 0; }} a {{ color: #075fa8; }}</style>
</head>
<body>
  <h1>{title} reference</h1>
  <p>This document is the target of the public vocabulary namespace.</p>
  <ul>
    <li><a href="index-en.html">English reference</a></li>
    <li><a href="index-de.html">Deutsche Referenz</a></li>
    <li><a href="{landing_page}graph/?ontology={graph_key}">Ontology Relationship Graph</a></li>
    <li><a href="webvowl/index.html">Earlier WebVOWL graph</a></li>
    <li><a href="ontology.ttl">Turtle serialization</a></li>
  </ul>
  <p><a href="{landing_page}">Project ontology landing page</a></p>
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
        site_root_href = "../" * (len(Path(public_path).parts) + 1)
        resource_graph = Graph()
        resource_links = []
        for spec_file, destination in publications[product_name]:
            resource_graph.parse(spec_file, format="turtle")
            resource_links.append(
                f'<li><a href="{site_root_href}examples/{destination.name}">'
                f"{destination.name}</a></li>"
            )
        resource_graph.serialize(
            destination=resource_root / "resources.ttl", format="turtle"
        )
        visualization_link = (
            f'<a href="{site_root_href}graph/?ontology=sql-api">'
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


def _build_sql_api_visualization(jar: Path) -> Graph:
    graph = Graph()
    for spec_file in sorted(
        (ROOT / "products" / "sql_api_example" / "specs").glob("*.ttl")
    ):
        graph.parse(spec_file, format="turtle")
    # WebVOWL uses the ontology IRI as its internal namespace. The projected
    # classes retain their authored article:* IRIs, so use that resource base
    # here and keep visualization-only edge IRIs in their separate namespace.
    visualization_iri = URIRef(SQL_API_IRI)
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
    return graph


def build_site(jar: Path) -> None:
    output = OUTPUT.resolve()
    build_root = (ROOT / "build").resolve()
    if not output.is_relative_to(build_root):
        raise ValueError(f"Refusing to replace output outside {build_root}: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_widoco(jar, ONTOLOGY, REFERENCE_OUTPUT)
    _run_widoco(jar, DECISION_ONTOLOGY, DECISION_REFERENCE_OUTPUT)
    _run_widoco(jar, FUNDING_ONTOLOGY, FUNDING_REFERENCE_OUTPUT)
    _run_widoco(jar, CLOUD_ONTOLOGY, CLOUD_REFERENCE_OUTPUT)
    _write_landing_page()
    _write_reference_index(
        REFERENCE_OUTPUT,
        title="SHACL Contract Ontology",
        landing_page="../",
        graph_key="contract",
    )
    _write_reference_index(
        DECISION_REFERENCE_OUTPUT,
        title="Decision and Obligation Core Ontology",
        landing_page="../../",
        graph_key="decision",
    )
    _write_reference_index(
        FUNDING_REFERENCE_OUTPUT,
        title="Funding Domain Ontology",
        landing_page="../../",
        graph_key="funding",
    )
    _write_reference_index(
        CLOUD_REFERENCE_OUTPUT,
        title="Cloud Compliance Domain Ontology",
        landing_page="../../",
        graph_key="cloud",
    )
    _publish_examples()
    sql_api_graph = _build_sql_api_visualization(jar)
    datasets = [
        build_dataset(
            Graph().parse(path, format="turtle"),
            key=key,
            title=title,
            namespace=namespace,
            source_href=source_href,
        )
        for path, key, title, namespace, source_href in (
            (ONTOLOGY, "contract", "SHACL Contract", VOCABULARY_IRI, "../ontology/ontology.ttl"),
            (DECISION_ONTOLOGY, "decision", "Decision & Obligation", DECISION_VOCABULARY_IRI, "../ontology/decision/ontology.ttl"),
            (FUNDING_ONTOLOGY, "funding", "Funding", FUNDING_VOCABULARY_IRI, "../ontology/funding/ontology.ttl"),
            (CLOUD_ONTOLOGY, "cloud", "Cloud Compliance", CLOUD_VOCABULARY_IRI, "../ontology/cloud/ontology.ttl"),
        )
    ]
    datasets.append(
        build_dataset(
            sql_api_graph,
            key="sql-api",
            title="SQL API example",
            namespace=str(ARTICLE),
            source_href="../examples/",
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
    write_graph_site(GRAPH_OUTPUT, datasets)
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")
    required = [
        OUTPUT / "index.html",
        GRAPH_OUTPUT / "index.html",
        GRAPH_OUTPUT / "cytoscape.min.js",
        REFERENCE_OUTPUT / "index.html",
        REFERENCE_OUTPUT / "index-en.html",
        REFERENCE_OUTPUT / "index-de.html",
        REFERENCE_OUTPUT / "ontology.ttl",
        REFERENCE_OUTPUT / "webvowl" / "index.html",
        REFERENCE_OUTPUT / "webvowl" / "data" / "ontology.json",
        DECISION_REFERENCE_OUTPUT / "index.html",
        DECISION_REFERENCE_OUTPUT / "index-en.html",
        DECISION_REFERENCE_OUTPUT / "index-de.html",
        DECISION_REFERENCE_OUTPUT / "ontology.ttl",
        DECISION_REFERENCE_OUTPUT / "webvowl" / "index.html",
        DECISION_REFERENCE_OUTPUT / "webvowl" / "data" / "ontology.json",
        FUNDING_REFERENCE_OUTPUT / "index.html",
        FUNDING_REFERENCE_OUTPUT / "index-en.html",
        FUNDING_REFERENCE_OUTPUT / "index-de.html",
        FUNDING_REFERENCE_OUTPUT / "ontology.ttl",
        FUNDING_REFERENCE_OUTPUT / "webvowl" / "index.html",
        FUNDING_REFERENCE_OUTPUT / "webvowl" / "data" / "ontology.json",
        CLOUD_REFERENCE_OUTPUT / "index.html",
        CLOUD_REFERENCE_OUTPUT / "index-en.html",
        CLOUD_REFERENCE_OUTPUT / "index-de.html",
        CLOUD_REFERENCE_OUTPUT / "ontology.ttl",
        CLOUD_REFERENCE_OUTPUT / "webvowl" / "index.html",
        CLOUD_REFERENCE_OUTPUT / "webvowl" / "data" / "ontology.json",
        OUTPUT / "resources" / "toolchain" / "index.html",
        OUTPUT / "resources" / "toolchain" / "resources.ttl",
        OUTPUT / "resources" / "sql-api" / "index.html",
        OUTPUT / "resources" / "sql-api" / "resources.ttl",
        OUTPUT / "resources" / "funding" / "kfw-458" / "index.html",
        OUTPUT / "resources" / "funding" / "kfw-458" / "resources.ttl",
        OUTPUT / "resources" / "cloud" / "privileged-access" / "index.html",
        OUTPUT / "resources" / "cloud" / "privileged-access" / "resources.ttl",
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
    for label, reference_output, terms in (
        (
            "Decision and Obligation Core Ontology",
            DECISION_REFERENCE_OUTPUT,
            (
                SDO.DecisionContract,
                SDO.RuleSetVersion,
                SDO.Condition,
                SDO.FactQuestion,
                SDO.QuestionFlowCase,
                SDO.EvidenceRequirement,
                SDO.EvidenceAssessment,
                SDO.Obligation,
                SDO.ObligationEvaluation,
                SDO.SourceCitation,
            ),
        ),
        (
            "Funding Domain Ontology",
            FUNDING_REFERENCE_OUTPUT,
            (
                FUNDING.FundingProgram,
                FUNDING.Applicant,
                FUNDING.Project,
                FUNDING.LandRegisterExcerpt,
                FUNDING.Eligible,
            ),
        ),
        (
            "Cloud Compliance Domain Ontology",
            CLOUD_REFERENCE_OUTPUT,
            (
                CLOUD.CloudSystem,
                CLOUD.PrivilegedAccessComplianceDecision,
                CLOUD.AuthenticationMechanismTestResult,
                CLOUD.Satisfied,
            ),
        ),
    ):
        webvowl_page = (reference_output / "webvowl" / "index.html").read_text(
            encoding="utf-8"
        )
        if 'id="search-input-text"' not in webvowl_page:
            raise ValueError(f"{label} WebVOWL site has no entity search input")
        webvowl_document = json.loads(
            (reference_output / "webvowl" / "data" / "ontology.json").read_text(
                encoding="utf-8"
            )
        )
        serialized_document = json.dumps(webvowl_document)
        missing_terms = [
            str(term) for term in terms if str(term) not in serialized_document
        ]
        if missing_terms:
            raise ValueError(
                f"{label} terms are absent from WebVOWL: {missing_terms}"
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
    internal_example_classes = {
        str(ARTICLE.Article),
        str(ARTICLE.ArticleShape),
        str(ARTICLE.GetArticleEndpoint),
        str(ARTICLE.ArticlesTable),
    }
    external_example_classes = [
        item["iri"]
        for item in sql_api_data.get("classAttribute", [])
        if item.get("iri") in internal_example_classes
        and "external" in item.get("attributes", [])
    ]
    if external_example_classes:
        raise ValueError(
            "SQL API classes are incorrectly marked external in WebVOWL: "
            f"{external_example_classes}"
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

"""Build the static Ontology Relationship Graph for the documentation site."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

from rdflib import Graph, Literal, RDF, RDFS, URIRef
from rdflib.namespace import OWL


ROOT = Path(__file__).parents[1]
TEMPLATE = Path(__file__).with_suffix(".html")
CYTOSCAPE_VERSION = "3.34.3"
CYTOSCAPE_URL = (
    f"https://cdn.jsdelivr.net/npm/cytoscape@{CYTOSCAPE_VERSION}/dist/cytoscape.min.js"
)
CYTOSCAPE_SHA256 = "5f3b5b529546d5af1fc5628590af033b74511a5b6f789f5f4682845863228b91"
CYTOSCAPE_CACHE = ROOT / ".cache" / "cytoscape" / f"cytoscape-{CYTOSCAPE_VERSION}.min.js"

# Display metadata only: no remote vocabulary loading or inferred relationships.
STANDARD_LABELS = {
    'https://schema.org/SoftwareApplication': ('Softwareanwendung', 'Software application'),
    'http://www.w3.org/ns/shacl#NodeShape': ('Datenbedingungen (SHACL)', 'SHACL node shape'),
    'http://purl.org/dc/terms/Standard': ('Standard / Protokoll', 'Standard / protocol'),
    str(RDF.Property): ('RDF-Property', 'RDF property'),
    str(RDFS.Datatype): ('Datentyp', 'Datatype'),
    str(OWL.Class): ('Klasse', 'Class'),
}


def _label(graph: Graph, term: URIRef, language: str) -> str:
    values = sorted(
        str(value)
        for value in graph.objects(term, RDFS.label)
        if value.language == language
    )
    if values:
        return values[0]
    if str(term) in STANDARD_LABELS:
        return STANDARD_LABELS[str(term)][0 if language == 'de' else 1]
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _description(graph: Graph, term: URIRef) -> str:
    for language in ("de", "en"):
        values = sorted(
            str(value)
            for value in graph.objects(term, RDFS.comment)
            if value.language == language
        )
        if values:
            return values[0]
    return ""


def _layout(nodes: list[dict], edges: list[dict]) -> dict[str, dict[str, float]]:
    """Supply DOT with sorted IDs and edges, then store fixed coordinates."""
    if shutil.which("dot") is None:
        raise RuntimeError("Graphviz 'dot' is required for the ontology graph site")
    ids = {node["id"]: f"n{index}" for index, node in enumerate(nodes)}
    lines = [
        "digraph ontology {",
        'graph [rankdir=LR, nodesep=0.55, ranksep=1.2, outputorder=edgesfirst];',
        'node [shape=box, width=2.0, height=0.6, fixedsize=true];',
    ]
    lines.extend(f"{ids[node['id']]};" for node in nodes)
    lines.extend(
        f"{ids[edge['source']]} -> {ids[edge['target']]} "
        f"[weight={'3' if edge['kind'] == 'subclass' else '1'}];"
        for edge in edges
    )
    lines.append("}")
    result = subprocess.run(
        ["dot", "-Tplain"],
        input="\n".join(lines),
        text=True,
        capture_output=True,
        check=True,
    )
    positions = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == "node":
            positions[parts[1]] = {
                "x": round(float(parts[2]) * 110, 2),
                "y": round(-float(parts[3]) * 110, 2),
            }
    if len(positions) != len(nodes):
        raise ValueError("Graphviz did not position every ontology class")
    return {node["id"]: positions[ids[node["id"]]] for node in nodes}


def build_dataset(
    graph: Graph,
    *,
    key: str,
    title: str,
    namespace: str,
    source_href: str,
    reference_href: str,
    property_namespaces: tuple[str, ...] = (),
    context_graph: Graph | None = None,
    publications: dict[str, dict] | None = None,
) -> dict:
    """Project local declarations and their direct named endpoints.

    The catalog supplies labels and reference links, never extra edges or a
    recursive expansion of imports. Class, instance and restriction relations
    retain distinct meanings. Literal values remain properties in the sidebar.
    """
    classes = {subject for subject in graph.subjects(RDF.type, OWL.Class)
               if isinstance(subject, URIRef) and str(subject).startswith(namespace)}
    individuals = {subject for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
                   if isinstance(subject, URIRef) and str(subject).startswith(namespace)}
    local = classes | individuals
    if not local:
        raise ValueError(f"Ontology Relationship Graph has no named nodes: {title}")
    metadata = graph if context_graph is None else graph + context_graph
    publications = publications or {}
    edges = []

    def add_edge(source, target, predicate, kind, label, **details):
        if isinstance(source, URIRef) and isinstance(target, URIRef):
            edges.append({'source': str(source), 'target': str(target),
                          'label': label, 'kind': kind, 'iri': str(predicate), **details})

    for subject, parent in graph.subject_objects(RDFS.subClassOf):
        if subject not in classes:
            continue
        if isinstance(parent, URIRef):
            add_edge(subject, parent, RDFS.subClassOf, 'subclass', 'Unterklasse von')
        elif (parent, RDF.type, OWL.Restriction) in graph:
            predicates = list(graph.objects(parent, OWL.onProperty))
            targets = list(graph.objects(parent, OWL.allValuesFrom))
            if len(predicates) == len(targets) == 1:
                predicate, target = predicates[0], targets[0]
                if isinstance(predicate, URIRef):
                    add_edge(subject, target, predicate, 'object', _label(metadata, predicate, 'de'),
                             constraint='allValuesFrom')
    for individual in sorted(individuals - classes, key=str):
        for parent in graph.objects(individual, RDF.type):
            if parent not in (OWL.NamedIndividual, OWL.Class):
                add_edge(individual, parent, RDF.type, 'type', 'ist Exemplar von')
    properties = []
    allowed = (namespace, *property_namespaces)
    for kind, rdf_type in (("object", OWL.ObjectProperty), ("datatype", OWL.DatatypeProperty)):
        for term in sorted(set(graph.subjects(RDF.type, rdf_type)), key=str):
            if not isinstance(term, URIRef) or not str(term).startswith(allowed):
                continue
            domains = sorted(
                str(value) for value in graph.objects(term, RDFS.domain)
                if isinstance(value, URIRef)
            )
            ranges = sorted(
                str(value) for value in graph.objects(term, RDFS.range)
                if isinstance(value, URIRef)
            )
            properties.append(
                {
                    "iri": str(term),
                    "name": str(term).rsplit("#", 1)[-1],
                    "label": _label(graph, term, "de"),
                    "labelEn": _label(graph, term, "en"),
                    "kind": kind,
                    "domains": domains,
                    "ranges": ranges,
                    "comment": _description(graph, term),
                    "deprecated": any(isinstance(value, Literal) and value.toPython() is True
                                      for value in graph.objects(term, OWL.deprecated)),
                }
            )
            if kind == "object":
                for domain in domains:
                    for target in ranges:
                        add_edge(URIRef(domain), URIRef(target), term, 'object', _label(metadata, term, 'de'))
    # Isomorphic restrictions must not create duplicate visual relationships.
    edges = list({(edge['source'], edge['target'], edge['iri'], edge['kind'], edge.get('constraint', '')): edge
                  for edge in edges}.values())
    edges.sort(key=lambda edge: (edge["source"], edge["target"], edge["iri"], edge.get("constraint", "")))
    terms = {str(term) for term in local} | {edge[end] for edge in edges for end in ('source', 'target')}
    nodes = []
    for iri in sorted(terms, key=lambda value: (URIRef(value) not in local, value)):
        term = URIRef(iri)
        name = iri.rsplit('#', 1)[-1].rsplit('/', 1)[-1]
        owner = next((item for ns, item in sorted(publications.items()) if iri.startswith(ns)), None)
        reference = ((owner['referenceHref'] if owner else reference_href) + 'index-de.html#' + quote(name, safe='')
                     if owner or term in local else iri if urlsplit(iri).scheme in ('http', 'https') else None)
        nodes.append({
            'id': iri, 'name': name, 'label': _label(metadata, term, 'de'),
            'labelEn': _label(metadata, term, 'en'), 'comment': _description(metadata, term),
            'kind': 'individual' if (term, RDF.type, OWL.NamedIndividual) in metadata and term not in classes else 'class',
            'external': term not in local,
            'owner': owner['title'] if owner else title if term in local else 'Externes Standardvokabular',
            'referenceHref': reference,
        })
    properties.sort(key=lambda prop: prop["iri"])
    return {
        "key": key,
        "namespace": namespace,
        "title": title,
        "sourceHref": source_href,
        "referenceHref": reference_href,
        "nodes": nodes,
        "edges": edges,
        "properties": properties,
        "positions": _layout(nodes, edges),
    }


def dependency_dataset(analysis: dict) -> dict:
    """One graph of explicit ontology imports; product specs are an optional layer."""
    nodes = []
    for item in analysis['nodes']:
        product = item['role'] == 'product'
        source = ('../resources/' + item['iri'].split('/resources/', 1)[1] + 'resources.ttl'
                  if product else '../ontology/' + (item['key'] + '/' if item['key'] != 'contract' else '') + 'ontology.ttl')
        label = item['titleDe'].replace('-Produktspezifikation', '\nProduktspezifikation')
        nodes.append({'id': item['iri'], 'name': item['key'], 'label': label,
                      'labelEn': item['title'], 'role': item['role'],
                      'comment': ('Abschließende Produktspezifikation: importiert wiederverwendbare Ontologien, '
                                  'darf selbst nicht importiert oder als Vokabular wiederverwendet werden.' if product else
                                  'Wiederverwendbare Ontologie. Pfeile zeigen ausdrücklich deklarierte Imports; '
                                  'fehlende Imports und zyklische Abhängigkeiten werden beim Build abgelehnt.'),
                      'graphKey': None if product else item['key'], 'sourceHref': source})
    iri = {item['key']: item['iri'] for item in analysis['nodes']}
    edges = [{'source': iri[edge['from']], 'target': iri[edge['to']], 'label': 'importiert',
              'kind': 'object', 'iri': str(OWL.imports)} for edge in analysis['dependencies']]
    # Stable topological columns, vertically balanced. Product visibility never
    # reruns layout, and the complete graph remains readable before zooming.
    outgoing = {node['id']: [] for node in nodes}
    for edge in edges:
        outgoing[edge['source']].append(edge['target'])
    depths = {}
    def depth(identity):
        if identity not in depths:
            depths[identity] = 1 + max((depth(target) for target in outgoing[identity]), default=-1)
        return depths[identity]
    maximum = max(depth(node['id']) for node in nodes)
    columns = {}
    for node in nodes:
        column = 0 if node['role'] == 'product' else maximum - depth(node['id'])
        columns.setdefault(column, []).append(node['id'])
    rows = max(len(column) for column in columns.values())
    products = {node['id'] for node in nodes if node['role'] == 'product'}
    positions = {identity: {'x': 140 + column * 330,
                            'y': 70 + (index + (rows - len(identities)) / 2) * 140
                            + (35 if identity in products else 0)}
                 for column, identities in sorted(columns.items())
                 for index, identity in enumerate(sorted(identities))}
    # Interval-coloured lanes keep unrelated imports apart in each inter-column
    # corridor. Product rows are offset from target rows so horizontal legs
    # cannot falsely merge with another product's outgoing imports.
    corridors = {}
    for edge in edges:
        source, target = positions[edge['source']], positions[edge['target']]
        corridors.setdefault(source['x'], []).append((min(source['y'], target['y']),
                                                     max(source['y'], target['y']), edge))
    for intervals in corridors.values():
        ends, assigned = [], []
        for start, end, edge in sorted(intervals, key=lambda row: (row[0], row[1], row[2]['source'], row[2]['target'])):
            lane = next((index for index, previous_end in enumerate(ends) if previous_end < start), len(ends))
            if lane == len(ends):
                ends.append(end)
            else:
                ends[lane] = end
            assigned.append((edge, lane))
        for edge, lane in assigned:
            edge['turn'] = round(20 + lane * 80 / max(1, len(ends) - 1), 2) if len(ends) > 1 else 60
    return {'key': 'dependencies', 'title': 'Übersicht · Ontologien und Produktspezifikationen',
            'mode': 'dependencies', 'sourceHref': './dependencies.json', 'referenceHref': '../ontology/',
            'nodes': nodes, 'edges': edges, 'properties': [], 'positions': positions}


def _cytoscape_asset() -> Path:
    if not CYTOSCAPE_CACHE.is_file():
        CYTOSCAPE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = CYTOSCAPE_CACHE.with_suffix(".download")
        with urlopen(CYTOSCAPE_URL) as response, temporary.open("wb") as target:
            shutil.copyfileobj(response, target)
        temporary.replace(CYTOSCAPE_CACHE)
    actual = hashlib.sha256(CYTOSCAPE_CACHE.read_bytes()).hexdigest()
    if actual != CYTOSCAPE_SHA256:
        raise ValueError(f"Unexpected Cytoscape.js SHA-256: {actual}")
    return CYTOSCAPE_CACHE


def write_graph_site(output: Path, datasets: list[dict], *, overview_href: str = "./overview.html") -> None:
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_cytoscape_asset(), output / "cytoscape.min.js")
    payload = json.dumps(
        datasets, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    (output / "index.html").write_text(
        template.replace("__ONTOLOGY_DATA__", payload).replace('href="./overview.html"',
            'href="' + html.escape(overview_href, quote=True) + '"'), encoding="utf-8"
    )

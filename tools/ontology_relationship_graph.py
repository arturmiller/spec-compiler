"""Build the static Ontology Relationship Graph for the documentation site."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import OWL


ROOT = Path(__file__).parents[1]
TEMPLATE = Path(__file__).with_suffix(".html")
CYTOSCAPE_VERSION = "3.34.3"
CYTOSCAPE_URL = (
    f"https://cdn.jsdelivr.net/npm/cytoscape@{CYTOSCAPE_VERSION}/dist/cytoscape.min.js"
)
CYTOSCAPE_SHA256 = "5f3b5b529546d5af1fc5628590af033b74511a5b6f789f5f4682845863228b91"
CYTOSCAPE_CACHE = ROOT / ".cache" / "cytoscape" / f"cytoscape-{CYTOSCAPE_VERSION}.min.js"


def _label(graph: Graph, term: URIRef, language: str) -> str:
    values = sorted(
        str(value)
        for value in graph.objects(term, RDFS.label)
        if value.language == language
    )
    if values:
        return values[0]
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
) -> dict:
    classes = sorted(
        {
            str(subject)
            for subject in graph.subjects(RDF.type, OWL.Class)
            if isinstance(subject, URIRef) and str(subject).startswith(namespace)
        }
    )
    if not classes:
        raise ValueError(f"Ontology Relationship Graph has no classes: {title}")
    nodes = [
        {
            "id": iri,
            "name": iri.rsplit("#", 1)[-1],
            "label": _label(graph, URIRef(iri), "de"),
            "labelEn": _label(graph, URIRef(iri), "en"),
            "comment": _description(graph, URIRef(iri)),
        }
        for iri in classes
    ]
    class_set = set(classes)
    edges = []
    for subject, parent in graph.subject_objects(RDFS.subClassOf):
        if str(subject) in class_set and str(parent) in class_set:
            edges.append(
                {
                    "source": str(subject),
                    "target": str(parent),
                    "label": "Unterklasse von",
                    "kind": "subclass",
                    "iri": str(RDFS.subClassOf),
                }
            )
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
                }
            )
            if kind == "object":
                for domain in domains:
                    for target in ranges:
                        if domain in class_set and target in class_set:
                            edges.append(
                                {
                                    "source": domain,
                                    "target": target,
                                    "label": _label(graph, term, "de"),
                                    "kind": "object",
                                    "iri": str(term),
                                }
                            )
    edges.sort(key=lambda edge: (edge["source"], edge["target"], edge["iri"]))
    properties.sort(key=lambda prop: prop["iri"])
    return {
        "key": key,
        "title": title,
        "sourceHref": source_href,
        "referenceHref": reference_href,
        "nodes": nodes,
        "edges": edges,
        "properties": properties,
        "positions": _layout(nodes, edges),
    }


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


def write_graph_site(output: Path, datasets: list[dict]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_cytoscape_asset(), output / "cytoscape.min.js")
    payload = json.dumps(
        datasets, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    (output / "index.html").write_text(
        template.replace("__ONTOLOGY_DATA__", payload), encoding="utf-8"
    )

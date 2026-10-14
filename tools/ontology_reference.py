"""Deterministic bilingual RDF references; no inference or remote lookups.

RDFLib canonicalizes blank nodes before serialization and HTML rendering:
https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.compare/
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote, urlsplit

from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import DCTERMS, OWL, RDFS


class OrderedGraph(Graph):
    """Give RDFLib serializers a fixed traversal of canonical triples."""

    def triples(self, triple):
        yield from sorted(super().triples(triple), key=lambda row: tuple(term.n3() for term in row))


def canonical_graph(graph: Graph) -> Graph:
    ordered = OrderedGraph(bind_namespaces="none")
    for prefix, namespace in sorted(graph.namespaces()):
        ordered.bind(prefix, namespace)
    for triple in to_canonical_graph(graph):
        ordered.add(triple)
    return ordered


def turtle(graph: Graph) -> str:
    """Sorted N-Triples are also valid Turtle, including canonical blank nodes."""
    return "\n".join(sorted(canonical_graph(graph).serialize(format="nt").splitlines())) + "\n"


def _sorted_json(value, *, ordered=False):
    if isinstance(value, dict):
        return {key: _sorted_json(item, ordered=key == "@list") for key, item in sorted(value.items())}
    if isinstance(value, list):
        items = [_sorted_json(item) for item in value]
        return items if ordered else sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def write_serializations(graph: Graph, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    graph = canonical_graph(graph)
    nt = "\n".join(sorted(graph.serialize(format="nt").splitlines())) + "\n"
    # Preserve WIDOCO's public filenames, but serialize only the input graph.
    for name in ("ontology.ttl", "ontology.nt"):
        (output / name).write_text(nt, encoding="utf-8", newline="\n")
    (output / "ontology.owl").write_text(graph.serialize(format="xml"), encoding="utf-8", newline="\n")
    expanded = json.loads(graph.serialize(format="json-ld", auto_compact=False))
    (output / "ontology.jsonld").write_text(
        json.dumps(_sorted_json(expanded), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )


def label(graph: Graph, term, language: str) -> str:
    labels = sorted(graph.objects(term, RDFS.label), key=lambda value: value.n3())
    for preferred in (language, "en", None):
        for value in labels:
            if isinstance(value, Literal) and value.language == preferred:
                return str(value)
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1] or str(term)


def _link(href: str, text: str) -> str:
    return f'<a href="{html.escape(href, quote=True)}">{html.escape(text)}</a>'


def write_reference(
    graph: Graph, output: Path, *, title: str, namespace: str,
    graph_key: str, site_root_href: str, publications: dict[str, str],
    source_href: str = "ontology.ttl", derived: bool = False,
) -> None:
    """Document every named local subject and every declared RDF statement.

    Both short namespace fragments and historical full-IRI WIDOCO anchors work.
    Blank-node structures retain identities and cycles instead of being inferred.
    """
    graph = canonical_graph(graph)
    write_serializations(graph, output)
    local = sorted({subject for subject in graph.subjects() if isinstance(subject, URIRef)
                    and str(subject).startswith(namespace)}, key=str)
    blanks = sorted({value for triple in graph for value in triple if isinstance(value, BNode)}, key=str)
    groups = (
        ("classes", "Klassen", "Classes", {OWL.Class, RDFS.Class}),
        ("objectproperties", "Objekt-Properties", "Object properties", {OWL.ObjectProperty}),
        ("dataproperties", "Datentyp-Properties", "Datatype properties", {OWL.DatatypeProperty}),
        ("annotationproperties", "Annotationen", "Annotation properties", {OWL.AnnotationProperty}),
        ("namedindividuals", "Weitere Ressourcen", "Other resources", set()),
    )
    assigned = set()
    grouped = []
    for anchor, german, english, types in groups:
        members = [term for term in local if term not in assigned
                   and (not types or set(graph.objects(term, RDF.type)) & types)]
        assigned.update(members)
        grouped.append((anchor, german, english, members))
    local_ids = {term: str(term)[len(namespace):] for term in local}
    if len(set(local_ids.values())) != len(local_ids) or any(not value for value in local_ids.values()):
        raise ValueError(f"Ambiguous reference anchors in {namespace}")
    reserved = {"content", "overview", "toc", "crossref", "ack", "acknowledgments",
                "abstract", "references", "provenance", "namespacedeclarations", "blank-nodes"}
    reserved.update(group[0] for group in groups)
    reserved.update("ref-" + identifier for identifier in local_ids.values())
    if reserved & set(local_ids.values()):
        raise ValueError(f"Reference term collides with page anchor in {namespace}")

    for language in ("de", "en"):
        def term_html(term) -> str:
            if isinstance(term, Literal):
                suffix = "@" + term.language if term.language else " ^^ " + str(term.datatype) if term.datatype else ""
                return '<span class="rdf-literal">' + html.escape(str(term)) + '</span><small>' + html.escape(suffix) + '</small>'
            if isinstance(term, BNode):
                return _link("#_" + str(term), "_:" + str(term))
            if term in local_ids:
                return _link("#" + quote(local_ids[term], safe=""), label(graph, term, language))
            for public_namespace, path in sorted(publications.items(), key=lambda item: -len(item[0])):
                if str(term).startswith(public_namespace):
                    fragment = str(term)[len(public_namespace):]
                    return _link(site_root_href + path + "index-" + language + ".html#" + quote(fragment, safe=""), label(graph, term, language))
            # RDF strings are untrusted markup/URLs, even in an authored ontology.
            if urlsplit(str(term)).scheme in {"http", "https"}:
                return _link(str(term), label(graph, term, language))
            return '<code>' + html.escape(str(term)) + '</code>'

        def statements(subject) -> str:
            rows = ''.join('<tr><th scope="row">' + term_html(predicate) + '</th><td>' + term_html(value) + '</td></tr>'
                           for predicate, value in graph.predicate_objects(subject))
            return '<table class="rdf-statements"><tbody>' + rows + '</tbody></table>'

        is_de = language == "de"
        graph_href = site_root_href + "ontologies/?ontology=" + graph_key
        downloads = ' · '.join(_link(name, caption) for name, caption in (
            (source_href, "Turtle-Quelle" if is_de else "Turtle source"),
            ("ontology.jsonld", "JSON-LD"), ("ontology.owl", "RDF/XML"), ("ontology.nt", "N-Triples")))
        navigation = ' '.join(_link("#" + anchor, german if is_de else english)
                              for anchor, german, english, members in grouped if members)
        scope = ("Abgeleitete Visualisierungsprojektion; Produktspecs bleiben autoritativ." if is_de else
                 "Derived visualization projection; product specs remain authoritative.") if derived else (
                 "Explizite RDF-Aussagen, ohne Inferenz. Turtle bleibt die autoritative Quelle." if is_de else
                 "Explicit RDF statements, without inference. Turtle remains authoritative.")
        ontology_terms = sorted(graph.subjects(RDF.type, OWL.Ontology), key=str)
        metadata = ''.join(statements(term) for term in ontology_terms)
        if not metadata:
            metadata = '<p>' + ('Keine Ontologie-Metadaten im Eingabegraphen.' if is_de else
                                'No ontology metadata is declared in the input graph.') + '</p>'
        sections = []
        for anchor, german, english, members in grouped:
            if not members:
                continue
            cards = []
            for term in members:
                identifier = local_ids[term]
                term_graph = graph_href + "&term=" + quote(str(term), safe="")
                comments = sorted({str(value) for predicate in (RDFS.comment, DCTERMS.description)
                                   for value in graph.objects(term, predicate)
                                   if isinstance(value, Literal) and value.language in {language, None}})
                # Keep literal definitions as text, never render their HTML.
                cards.append(f'<article class="rdf-term" id="{html.escape(identifier, quote=True)}">'
                             f'<span id="{html.escape(str(term), quote=True)}"></span>'
                             f'<h3 id="ref-{html.escape(identifier, quote=True)}">{html.escape(label(graph, term, language))}</h3>'
                             '<p class="rdf-iri"><code>' + html.escape(str(term)) + '</code></p>'
                             + ''.join('<p>' + html.escape(value) + '</p>' for value in comments)
                             + statements(term)
                             + '<p>' + _link(term_graph, "Im Graph öffnen" if is_de else "Open in graph") + '</p></article>')
            sections.append('<section id="' + anchor + '"><h2>' + (german if is_de else english) + '</h2>'
                            '<nav class="reference-toc">' + ' '.join(_link("#" + quote(local_ids[term], safe=""), label(graph, term, language)) for term in members)
                            + '</nav>' + ''.join(cards) + '</section>')
        if blanks:
            sections.append('<section id="blank-nodes"><h2>' + ("Anonyme RDF-Strukturen" if is_de else "Anonymous RDF structures") + '</h2>'
                            + ''.join('<details id="_' + str(term) + '"><summary>_:' + str(term) + '</summary>' + statements(term) + '</details>' for term in blanks)
                            + '</section>')
        markup = ('<!doctype html><html lang="' + language + '"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                  '<title>' + html.escape(title) + (' · Referenz' if is_de else ' · Reference') + '</title></head>'
                  '<body><main id="content" class="doc-content ontology-reference"><p class="eyebrow">'
                  + ('Ontologiereferenz' if is_de else 'Ontology reference') + '</p><h1>' + html.escape(title) + '</h1>'
                  '<p class="lead">' + scope + '</p><nav class="section-navigation">' + _link(graph_href, "Beziehungsgraph" if is_de else "Relationship graph")
                  + ' ' + _link("index-" + ("en" if is_de else "de") + ".html", "English" if is_de else "Deutsch")
                  + '</nav><p class="reference-downloads">' + downloads + '</p>'
                  '<nav id="toc" class="reference-toc">' + navigation + '</nav>'
                  '<section id="overview">' + ('' if 'description' in local_ids.values() else '<span id="description"></span>')
                  + '<h2>' + ('Metadaten' if is_de else 'Metadata') + '</h2>' + metadata + '</section>'
                  '<span id="crossref"></span>' + ''.join(sections) + '</main></body></html>\n')
        (output / ("index-" + language + ".html")).write_text(markup, encoding="utf-8", newline="\n")
        if is_de:
            (output / "index.html").write_text(markup, encoding="utf-8", newline="\n")
    legacy = output / "webvowl"
    legacy.mkdir(parents=True, exist_ok=True)
    target = site_root_href + "../ontologies/?ontology=" + graph_key
    (legacy / "index.html").write_text(
        '<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Beziehungsgraph</title>'
        '<script>const target=new URL(' + json.dumps(target) + ',location.href);'
        'const incoming=new URLSearchParams(location.search);for(const [key,value] of incoming){if(key!=="ontology")target.searchParams.set(key,value);}'
        'target.hash=location.hash;location.replace(target.href);</script></head><body><p>'
        + _link(target, "Beziehungsgraph öffnen") + '</p></body></html>\n', encoding="utf-8", newline="\n")

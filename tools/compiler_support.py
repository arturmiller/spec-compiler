"""Validate the authored support inventory and derive its RDF term index.

This is documentation tooling: it neither interprets product requirements nor
changes compiler dispatch. HTML owns support claims; Turtle owns vocabulary.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, RDFS, SH, VANN, XSD

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("docs/reference/compiler-support.html")
ROUTE = "reference/compiler-support.html"
GITHUB = "https://github.com/arturmiller/spec-compiler/"
ROLES = {"contract", "spec-constraint", "result", "context", "unsupported", "retired"}
STATUSES = {"implemented", "descriptive", "unsupported", "retired"}
PROFILES = {"all", "http-sql", "decision", "decision-http", "compiler", "publication"}
STANDARD_NAMESPACES = {
    "rdf": str(RDF), "rdfs": str(RDFS), "owl": str(OWL), "sh": str(SH),
    "xsd": str(XSD), "dcterms": str(DCTERMS), "vann": str(VANN),
    "schema": "https://schema.org/",
}
ROLE_LABELS = {
    "contract": "Vertragsbestandteil", "spec-constraint": "Spec-Prüfung",
    "result": "Ergebnisbegriff", "context": "Kontext/Metadatum",
    "unsupported": "Nicht unterstützt", "retired": "Stillgelegt",
}
STATUS_LABELS = {
    "implemented": "Implementiert im beschriebenen Ausschnitt",
    "descriptive": "Beschreibend", "unsupported": "Nicht unterstützt",
    "retired": "Stillgelegt; Verwendung wird abgelehnt",
}


class SupportParser(HTMLParser):
    """Read a small explicit HTML vocabulary; all prose remains normal HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.modules = {}
        self.patterns = []
        self.current = None
        self.field = None
        self.field_tag = None

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "data-support-module" in data:
            prefix = data["data-support-module"]
            if prefix in self.modules:
                raise ValueError(f"Duplicate support module: {prefix}")
            self.modules[prefix] = data.get("data-purpose", "")
        if "data-support-pattern" in data:
            if tag != "article" or self.current:
                raise ValueError("Support patterns must be separate articles")
            self.current = {
                "id": data["data-support-pattern"], "anchor": data.get("id"),
                "profiles": data.get("data-profiles", "").split(),
                "roles": data.get("data-roles", "").split(),
                "status": data.get("data-status"),
                "evidenceStatus": data.get("data-evidence"),
                "coreStatus": data.get("data-core", "undecided"),
                "terms": data.get("data-terms", "").split(),
                "standards": data.get("data-standards", "").split(),
                "references": [],
            }
            self.patterns.append(self.current)
        if self.current and "data-support-field" in data:
            self.field = data["data-support-field"]
            self.field_tag = tag
            if self.field in self.current:
                raise ValueError(f"Duplicate support field: {self.current['id']}/{self.field}")
            self.current[self.field] = ""
        if self.current and "data-support-ref" in data:
            if tag != "a":
                raise ValueError("Support references must be links")
            self.current["references"].append({
                "kind": data["data-support-ref"], "href": data.get("href", ""),
                "symbol": data.get("data-symbol", ""),
            })

    def handle_data(self, data):
        if self.current and self.field:
            self.current[self.field] += data + " "

    def handle_endtag(self, tag):
        if tag == self.field_tag:
            self.current[self.field] = " ".join(self.current[self.field].split())
            self.field = self.field_tag = None
        if tag == "article":
            self.current = None


def _catalog(root):
    modules, terms = [], {}
    for path in sorted((root / "ontology").glob("*.ttl")):
        graph = Graph().parse(path, format="turtle")
        identities = list(graph.subjects(RDF.type, OWL.Ontology))
        if len(identities) != 1:
            raise ValueError(f"Inventory needs one ontology identity: {path}")
        identity = identities[0]
        prefix = str(graph.value(identity, VANN.preferredNamespacePrefix, any=False))
        namespace = str(graph.value(identity, VANN.preferredNamespaceUri, any=False))
        titles = sorted(str(v) for v in graph.objects(identity, DCTERMS.title) if v.language == "de")
        module = {"prefix": prefix, "iri": str(identity), "namespace": namespace,
                  "title": titles[0] if titles else str(identity),
                  "source": path.relative_to(root).as_posix(), "role": "reusable",
                  "coreStatus": "undecided", "version": str(graph.value(identity, OWL.versionInfo))}
        modules.append(module)
        for term in sorted(set(graph.subjects()), key=str):
            if not isinstance(term, URIRef) or not str(term).startswith(namespace):
                continue
            name = prefix + ":" + str(term)[len(namespace):]
            if name in terms:
                raise ValueError(f"Duplicate inventory term: {name}")
            labels = sorted(str(v) for v in graph.objects(term, RDFS.label) if v.language == "de")
            terms[name] = {"name": name, "iri": str(term), "module": prefix,
                           "label": labels[0] if labels else name,
                           "types": sorted(str(t) for t in graph.objects(term, RDF.type)),
                           "source": module["source"], "patterns": [], "roles": []}
    if not modules:
        raise ValueError("No ontology catalog for support inventory")
    return modules, terms


def observed_standard_expressions(root):
    """Find syntax needing an explicit classification, never infer support."""
    tree = ast.parse((root / "tools/generate.py").read_text(encoding="utf-8"))
    aliases = {prefix.upper(): prefix for prefix in STANDARD_NAMESPACES}
    observed = {aliases[node.value.id] + ":" + node.attr for node in ast.walk(tree)
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in aliases}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HTTP_SCHEMA_KEYWORDS" for target in node.targets
        ):
            observed.update("json-schema:" + keyword for keyword in ast.literal_eval(node.value))
    return observed


def _reference(reference, root, source, cache, parsed):
    kind, href, symbol = reference["kind"], reference["href"], reference["symbol"]
    if kind not in {"implementation", "test", "convention", "followup"}:
        raise ValueError(f"Unknown support reference kind: {kind}")
    url = urlsplit(href)
    if url.scheme or url.netloc:
        if kind != "followup" or not href.startswith(GITHUB + "issues/") or not href[len(GITHUB + "issues/"):].isdigit():
            raise ValueError(f"Support reference must be local or an issue follow-up: {href}")
        if symbol:
            raise ValueError(f"Issue reference cannot name a source symbol: {href}")
        return {"kind": kind, "url": href}
    path = (source.parent / unquote(url.path)).resolve() if url.path else source
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing or unsafe support reference: {href}")
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8")
    fragment = unquote(url.fragment)
    line = None
    if kind in {"implementation", "test"}:
        if path.suffix != ".py" or not symbol or fragment:
            raise ValueError(f"Python support reference needs a symbol: {href}")
        if (path, "symbols") not in parsed:
            parsed[path, "symbols"] = {node.name: node.lineno for node in ast.walk(ast.parse(cache[path]))
                                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        symbols = parsed[path, "symbols"]
        if symbol not in symbols or (kind == "test" and not symbol.startswith("test_")):
            raise ValueError(f"Missing support {kind} symbol: {href}::{symbol}")
        line = symbols[symbol]
    elif symbol:
        raise ValueError(f"Unexpected symbol on support {kind} reference: {href}")
    if kind == "convention" and (path.suffix != ".html" or not fragment):
        raise ValueError(f"Convention reference needs an HTML anchor: {href}")
    if fragment:
        if (path, "anchors") not in parsed:
            parser = HTMLParser()  # Avoid importing the documentation builder here.
            anchors = set()
            parser.handle_starttag = lambda tag, attrs: anchors.update(v for k, v in attrs if k == "id")
            parser.feed(cache[path])
            parsed[path, "anchors"] = anchors
        anchors = parsed[path, "anchors"]
        if fragment not in anchors:
            raise ValueError(f"Missing support reference anchor: {href}")
    relative = path.relative_to(root).as_posix()
    result = {"kind": kind, "path": relative,
              "url": GITHUB + "blob/main/" + relative + (f"#L{line}" if line else "#" + quote(fragment) if fragment else "")}
    if symbol:
        result.update(symbol=symbol, line=line)
    if fragment:
        result["anchor"] = fragment
    return result


def build_inventory(root=ROOT, *, markup=None):
    root = Path(root).resolve()
    source = root / SOURCE
    markup = markup if markup is not None else source.read_text(encoding="utf-8")
    parser = SupportParser()
    parser.feed(markup)
    modules, terms = _catalog(root)
    if set(parser.modules) != {module["prefix"] for module in modules}:
        raise ValueError("Support module classifications do not match the ontology catalog")
    for module in modules:
        module["purpose"] = parser.modules[module["prefix"]]
        if not module["purpose"]:
            raise ValueError(f"Missing support module purpose: {module['prefix']}")
    cache, parsed = {source: markup}, {}
    ids, standards = set(), {}
    for pattern in parser.patterns:
        identifier = pattern["id"]
        if not identifier or identifier in ids or pattern["anchor"] != identifier:
            raise ValueError(f"Invalid or duplicate support pattern: {identifier}")
        ids.add(identifier)
        for field in ("title", "conditions", "limits"):
            if not pattern.get(field):
                raise ValueError(f"Missing support {field}: {identifier}")
        for field, allowed in (("profiles", PROFILES), ("roles", ROLES)):
            if not pattern[field] or set(pattern[field]) - allowed:
                raise ValueError(f"Invalid support {field}: {identifier}")
        if pattern["status"] not in STATUSES or pattern["evidenceStatus"] not in {"referenced", "missing"}:
            raise ValueError(f"Invalid support/evidence status: {identifier}")
        if pattern["coreStatus"] not in {"candidate", "undecided"}:
            raise ValueError(f"Core membership is not decided by this inventory: {identifier}")
        if len(pattern["terms"]) != len(set(pattern["terms"])):
            raise ValueError(f"Duplicate support term assignment: {identifier}")
        for name in pattern["terms"]:
            if name not in terms:
                raise ValueError(f"Undefined or orphaned support term: {name}")
            terms[name]["patterns"].append(identifier)
            terms[name]["roles"].extend(pattern["roles"])
        for expression in pattern["standards"]:
            prefix, separator, name = expression.partition(":")
            if not separator or not name or prefix not in {*STANDARD_NAMESPACES, "json-schema"}:
                raise ValueError(f"Invalid standard expression: {expression}")
            standards.setdefault(expression, []).append(identifier)
        pattern["references"] = [_reference(ref, root, source, cache, parsed) for ref in pattern["references"]]
        kinds = {ref["kind"] for ref in pattern["references"]}
        if "convention" not in kinds:
            raise ValueError(f"Support pattern needs a convention: {identifier}")
        if pattern["status"] in {"implemented", "retired"} and "implementation" not in kinds:
            raise ValueError(f"Support pattern needs implementation evidence: {identifier}")
        if pattern["evidenceStatus"] == "referenced" and "test" not in kinds:
            raise ValueError(f"Support pattern claims evidence without a test: {identifier}")
        if pattern["evidenceStatus"] == "missing" or pattern["status"] == "unsupported":
            if not pattern.get("gap") or "followup" not in kinds:
                raise ValueError(f"Support gap needs an explanation and follow-up: {identifier}")
        if pattern.get("gap") and "followup" not in kinds:
            raise ValueError(f"Support gap needs a follow-up: {identifier}")
    missing = sorted(name for name, term in terms.items() if not term["patterns"])
    if missing:
        raise ValueError(f"Public terms missing support classification: {', '.join(missing)}")
    observed = observed_standard_expressions(root)
    if observed - standards.keys():
        raise ValueError(f"Standard expressions missing support classification: {', '.join(sorted(observed - standards.keys()))}")
    for term in terms.values():
        term["patterns"] = sorted(set(term["patterns"]))
        term["roles"] = sorted(set(term["roles"]))
    sources = {path.relative_to(root).as_posix(): hashlib.sha256(text.encode()).hexdigest()
               for path, text in cache.items()}
    sources.update({module["source"]: hashlib.sha256((root / module["source"]).read_bytes()).hexdigest()
                    for module in modules})
    return {"schemaVersion": 1, "inventoryConvention": "Compiler Support Inventory v1",
            "scope": "catalog-and-declared-patterns", "coreDecision": "pending-review",
            "evidenceMeaning": "References locate existing checks; they do not establish complete semantic coverage.",
            "sources": dict(sorted(sources.items())), "modules": sorted(modules, key=lambda m: m["prefix"]),
            "patterns": sorted(parser.patterns, key=lambda p: p["id"]),
            "terms": [terms[name] for name in sorted(terms)],
            "standardExpressions": [{"expression": key, "observedInReader": key in observed,
                                     "patterns": sorted(set(value))} for key, value in sorted(standards.items())]}


def inventory_json(inventory):
    return json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def term_anchor(name):
    return "term-" + name.replace(":", "-")


def pattern_annotation(pattern):
    esc = html.escape
    text = (STATUS_LABELS[pattern["status"]] + " · Profile: " + ", ".join(pattern["profiles"])
            + " · Rollen: " + ", ".join(ROLE_LABELS[role] for role in pattern["roles"]))
    evidence = "Prüffunktionen referenziert; fachliche Vollständigkeit nicht bewiesen" if pattern["evidenceStatus"] == "referenced" else "Nachweis fehlt"
    result = f'<p class="support-status">{esc(text)} · {evidence}'
    if pattern["coreStatus"] == "candidate":
        result += " · Kernkandidat, Entscheidung offen"
    result += '</p>'
    if pattern["terms"]:
        result += '<p>Begriffe: ' + ', '.join(
            f'<a href="#{term_anchor(name)}"><code>{esc(name)}</code></a>' for name in pattern["terms"]) + '</p>'
    if pattern["standards"]:
        result += '<p>Standardausdrücke: ' + ', '.join(f'<code>{esc(name)}</code>' for name in pattern["standards"]) + '</p>'
    symbols = [ref for ref in pattern["references"] if ref.get("symbol")]
    if symbols:
        result += '<p>Quellstellen: ' + ', '.join(
            f'<a href="{esc(ref["url"], quote=True)}"><code>{esc(ref["symbol"])}</code></a>' for ref in symbols) + '</p>'
    return result


def render_inventory(inventory):
    esc = html.escape
    patterns = {p["id"]: p for p in inventory["patterns"]}
    parts = ['<p><a href="compiler-support.json">Maschinenlesbares Inventar (JSON)</a></p>',
             '<p>Vollständige Einordnung ist kein Nachweis vollständiger Unterstützung. '
             'Die Kernentscheidung bleibt offen. Testreferenzen belegen ihre Existenz, nicht ihre fachliche Vollständigkeit.</p>']
    for module in inventory["modules"]:
        parts.append(f'<h3 id="module-{esc(module["prefix"])}">{esc(module["title"])}</h3>'
                     f'<p>Rolle: wiederverwendbar · Zweck: {esc(module["purpose"])} · Kernzuordnung: offen</p>'
                     '<table><thead><tr><th>Begriff aus der Ontologie</th><th>Rollen</th><th>Verwendungsmuster und Grenzen</th></tr></thead><tbody>')
        for term in inventory["terms"]:
            if term["module"] != module["prefix"]:
                continue
            links = '<br>'.join(f'<a href="#{esc(key)}">{esc(patterns[key]["title"])}</a> — '
                                + esc(STATUS_LABELS[patterns[key]["status"]]) for key in term["patterns"])
            parts.append(f'<tr id="{term_anchor(term["name"])}"><th scope="row"><code>{esc(term["name"])}</code><br>'
                         f'{esc(term["label"])}</th><td>{esc(", ".join(ROLE_LABELS[r] for r in term["roles"]))}</td><td>{links}</td></tr>')
        parts.append('</tbody></table>')
    parts.append('<h3 id="standard-expressions">Erfasste Standardausdrücke</h3><table><thead><tr><th>Ausdruck</th><th>Verwendungsmuster</th></tr></thead><tbody>')
    for entry in inventory["standardExpressions"]:
        links = ', '.join(f'<a href="#{esc(key)}">{esc(patterns[key]["title"])}</a>' for key in entry["patterns"])
        parts.append(f'<tr><th scope="row"><code>{esc(entry["expression"])}</code></th><td>{links}</td></tr>')
    parts.append('</tbody></table>')
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the derived JSON inventory")
    args = parser.parse_args()
    inventory = build_inventory()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(inventory_json(inventory), encoding="utf-8", newline="\n")
    print(f"Support inventory valid: {len(inventory['modules'])} modules, "
          f"{len(inventory['terms'])} terms, {len(inventory['patterns'])} patterns; core decision pending review.")


if __name__ == "__main__":
    main()

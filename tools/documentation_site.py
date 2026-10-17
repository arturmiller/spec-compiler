"""Compose canonical HTML documents, verified diagrams, and ontology views."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs"
OUTPUT = ROOT / "build" / "ontology-site"
ARCHIFY = ROOT / "tools" / "vendor" / "archify"
CACHE = ROOT / ".cache" / "documentation"
NAVIGATION = (
    ("", "Überblick"),
    ("compiler/", "Compiler"),
    ("tutorials/", "Tutorials"),
    ("reference/", "Referenz"),
    ("ontologies/", "Ontologien"),
    ("contributors/", "Mitwirken"),
)


@contextmanager
def build_lock(path: Path | None = None, timeout: float = 600):
    """Serialize manual builds and the watcher without creating stale PID locks."""
    lock_path = path or CACHE / "build.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Another documentation build still holds the build lock") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def publish_file(source: Path, destination: Path) -> None:
    """Unique candidates avoid writer collisions; tolerate brief Windows readers."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=destination.name + ".", suffix=".candidate", dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copyfile(source, temporary)
        for attempt in range(40):
            try:
                temporary.replace(destination)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def relative_url(route: str, target: str) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return target
    directory = route if route.endswith("/") else posixpath.dirname(route)
    result = posixpath.relpath(parsed.path or ".", directory or ".")
    if parsed.path.endswith("/") or not parsed.path:
        result += "/"
    return result + ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.route = ""
        self.redirect = ""
        self.aliases: list[str] = []
        self.title = ""
        self.summary = ""
        self.ids: set[str] = set()
        self.duplicates: set[str] = set()
        self.links: list[tuple[str, str]] = []
        self.diagrams: list[str] = []
        self.sections: list[dict[str, str]] = []
        self.text: list[str] = []
        self._title = False
        self._main = False
        self._skip = 0
        self._heading = ""
        self._heading_id = ""
        self._heading_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "meta":
            if data.get("name") == "doc-route":
                self.route = data.get("content") or ""
            elif data.get("name") == "doc-redirect":
                self.redirect = data.get("content") or ""
            elif data.get("name") == "doc-alias":
                self.aliases.append(data.get("content") or "")
            elif data.get("name") == "description":
                self.summary = data.get("content") or ""
        if tag == "title":
            self._title = True
        if tag == "main":
            self._main = True
        if tag in {"script", "style"}:
            self._skip += 1
        identifier = data.get("id")
        if identifier:
            if identifier in self.ids:
                self.duplicates.add(identifier)
            self.ids.add(identifier)
        if tag in {"a", "link", "script", "img", "iframe"}:
            value = data.get("href") or data.get("src")
            if value:
                self.links.append((tag, value))
        if data.get("data-diagram"):
            self.diagrams.append(data["data-diagram"] or "")
        if self._main and re.fullmatch(r"h[1-6]", tag):
            self._heading = tag
            self._heading_id = identifier or ""
            self._heading_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
        if self._heading == tag:
            title = " ".join(" ".join(self._heading_text).split())
            self.sections.append({"title": title, "id": self._heading_id, "text": ""})
            self._heading = ""
        if tag == "main":
            self._main = False

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title += data
        if self._skip or not self._main:
            return
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.text.append(normalized)
        if self._heading:
            self._heading_text.append(normalized)
        elif self.sections:
            self.sections[-1]["text"] += normalized + " "


class GlossaryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.current = None
        self.reading = False
        self.definition = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "dt" and attributes.get("data-term"):
            self.current = {"title": attributes["data-term"], "id": attributes["id"]}
        if tag == "dd" and self.current:
            self.reading = True
            self.definition = []

    def handle_data(self, data):
        if self.reading:
            self.definition.append(data)

    def handle_endtag(self, tag):
        if tag == "dd" and self.current:
            self.entries.append({**self.current, "text": " ".join(" ".join(self.definition).split())})
            self.current = None
            self.reading = False


def glossary_entries() -> list[dict]:
    source = SOURCES / "glossary.html"
    if not source.is_file():
        return []
    parser = GlossaryParser()
    parser.feed(source.read_text(encoding="utf-8"))
    return parser.entries


class GlossaryLinker(HTMLParser):
    """Link only the first prose occurrence per section; never code or ADRs."""
    def __init__(self, entries, target):
        super().__init__(convert_charrefs=False)
        self.terms = {entry["title"]: entry["id"] for entry in entries}
        self.pattern = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(term) for term in sorted(self.terms, key=len, reverse=True)) + r")(?![\w-])") if entries else None
        self.target = target
        self.seen = set()
        self.parts = []
        self.main = False
        self.skipped = []

    def handle_starttag(self, tag, attrs):
        self.parts.append(self.get_starttag_text())
        if tag == "main":
            self.main = True
        if tag == "h2":
            self.seen.clear()
        if tag in {"a", "code", "pre", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.skipped.append(tag)
        if tag == "a":
            fragment = urlsplit(dict(attrs).get("href", "")).fragment
            self.seen.update(term for term, identifier in self.terms.items() if identifier == fragment)

    def handle_endtag(self, tag):
        self.parts.append(f"</{tag}>")
        if tag == "main":
            self.main = False
        if self.skipped and tag == self.skipped[-1]:
            self.skipped.pop()

    def handle_startendtag(self, tag, attrs):
        self.parts.append(self.get_starttag_text())

    def handle_data(self, data):
        if self.main and not self.skipped and self.pattern:
            def replace(match):
                term = match.group()
                if term in self.seen:
                    return term
                self.seen.add(term)
                href = self.target + "#" + self.terms[term]
                return f'<a class="glossary-link" href="{html.escape(href, quote=True)}">{html.escape(term)}</a>'
            data = self.pattern.sub(replace, data)
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_decl(self, decl):
        self.parts.append(f"<!{decl}>")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")


@dataclass
class Document:
    source: Path
    markup: str
    parsed: DocumentParser

    @property
    def route(self) -> str:
        return self.parsed.route

    @property
    def target(self) -> str:
        return self.route + "index.html" if self.route.endswith("/") or not self.route else self.route


def read_documents() -> list[Document]:
    documents = []
    routes: set[str] = set()
    for source in sorted(SOURCES.rglob("*.html")):
        if "assets" in source.relative_to(SOURCES).parts:
            continue
        markup = source.read_text(encoding="utf-8")
        parsed = DocumentParser()
        parsed.feed(markup)
        if 'name="doc-route"' not in markup:
            raise ValueError(f"HTML source has no doc-route metadata: {source}")
        route = parsed.route
        if route.startswith("/") or ".." in Path(route).parts or "\\" in route:
            raise ValueError(f"Unsafe documentation route: {source}: {route}")
        if route in routes:
            raise ValueError(f"Duplicate documentation route: {route}")
        if parsed.duplicates:
            raise ValueError(f"Duplicate HTML IDs in {source}: {sorted(parsed.duplicates)}")
        if not parsed.title.strip():
            raise ValueError(f"Documentation title is missing: {source}")
        if not parsed.redirect and not parsed.sections:
            raise ValueError(f"Documentation has no readable main heading: {source}")
        routes.add(route)
        documents.append(Document(source, markup, parsed))
    for document in documents:
        for alias in document.parsed.aliases:
            if not alias or alias.startswith("/") or ".." in Path(alias).parts or "\\" in alias:
                raise ValueError(f"Unsafe documentation alias: {alias}")
            if alias in routes:
                raise ValueError(f"Duplicate documentation route or alias: {alias}")
            routes.add(alias)
    return documents


def diagram_sources() -> dict[str, Path]:
    result = {}
    for source in sorted((SOURCES / "diagrams").glob("*.json")):
        data = json.loads(source.read_text(encoding="utf-8"))
        if data.get("diagram_type") not in {"architecture", "workflow", "sequence", "dataflow", "lifecycle"}:
            raise ValueError(f"Unknown diagram type: {source}")
        if data.get("meta", {}).get("quality_profile") != "showcase":
            raise ValueError(f"Documentation diagrams require the showcase profile: {source}")
        if source.stem == "ontology-dependencies":
            dependencies, _tables = ontology_dependency_views()
            if __package__:
                from .ontology_dependencies import dependency_diagram
            else:
                from ontology_dependencies import dependency_diagram
            model = dependency_diagram(data, dependencies)
            payload = json.dumps(model, ensure_ascii=False, indent=2) + "\n"
            derived = CACHE / "derived-models" / hashlib.sha256(payload.encode()).hexdigest() / source.name
            derived.parent.mkdir(parents=True, exist_ok=True)
            derived.write_text(payload, encoding="utf-8", newline="\n")
            result[source.stem] = derived
        else:
            result[source.stem] = source
    return result


def ontology_dependency_views():
    if __package__:
        from .build_ontology_site import ONTOLOGY_PUBLICATIONS
        from .ontology_dependencies import read_dependencies, dependency_tables
    else:
        from build_ontology_site import ONTOLOGY_PUBLICATIONS
        from ontology_dependencies import read_dependencies, dependency_tables
    analysis = read_dependencies(ONTOLOGY_PUBLICATIONS)
    return analysis, dependency_tables(analysis)


def source_target(source: Path, value: str, document_map: dict[Path, Document]) -> str | None:
    parsed = urlsplit(html.unescape(value))
    if parsed.scheme or parsed.netloc or value.startswith("#"):
        return None
    target = (source.parent / unquote(parsed.path)).resolve()
    if target in document_map:
        suffix = ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
        return (document_map[target].parsed.redirect or document_map[target].route) + suffix
    if target == ROOT / "tools" / "ontology_relationship_graph.html":
        graph_route = "tutorials/sql-api/graph/" if "ontology=sql-api" in parsed.query else "ontologies/"
        return graph_route + ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
    if target.is_relative_to((SOURCES / "assets").resolve()):
        return "assets/" + target.relative_to(SOURCES / "assets").as_posix()
    if target.is_relative_to((SOURCES / "diagrams").resolve()) and target.suffix == ".json":
        return "diagrams/" + target.name
    if target.is_relative_to(ROOT.resolve()) and target.exists():
        kind = "tree" if target.is_dir() else "blob"
        return "https://github.com/arturmiller/spec-compiler/" + kind + "/main/" + target.relative_to(ROOT).as_posix() + ("#" + parsed.fragment if parsed.fragment else "")
    return None


def validate_sources(*, render_diagrams: bool = True) -> None:
    documents = read_documents()
    if any('data-support-inventory' in document.markup for document in documents):
        if __package__:
            from .compiler_support import build_inventory
        else:
            from compiler_support import build_inventory
        build_inventory(ROOT)
    lookup = {document.source.resolve(): document for document in documents}
    models = diagram_sources()
    errors = []
    for document in documents:
        for identifier in document.parsed.diagrams:
            if identifier not in models:
                errors.append(f"{document.source} references unknown diagram: {identifier}")
        for tag, value in document.parsed.links:
            link = urlsplit(html.unescape(value))
            if link.scheme or link.netloc:
                continue
            if value.startswith("#"):
                if link.fragment and link.fragment not in document.parsed.ids:
                    errors.append(f"Missing local anchor: {document.source}: {value}")
                continue
            target = (document.source.parent / unquote(link.path)).resolve()
            if not target.is_relative_to(ROOT.resolve()):
                errors.append(f"Documentation link leaves repository: {document.source}: {value}")
            if not target.exists():
                errors.append(f"Documentation source link is missing: {document.source}: {value}")
            if target in lookup and link.fragment and link.fragment not in lookup[target].parsed.ids:
                errors.append(f"Documentation target anchor is missing: {document.source}: {value}")
    if errors:
        raise ValueError("\n".join(errors))
    targets = {document.target: document for document in documents}
    for name, source in models.items():
        model = json.loads(source.read_text(encoding="utf-8"))
        for node in model.get("components", model.get("participants", model.get("states", []))):
            for link in node.get("links", []):
                url = urlsplit(link["href"])
                route = posixpath.normpath(posixpath.join("diagrams", url.path))
                if url.path.endswith("/"):
                    route = (route + "/" if route != "." else "") + "index.html"
                if url.scheme or url.netloc or route not in targets:
                    raise ValueError(f"Invalid diagram documentation link: {name}/{node['id']}: {link['href']}")
                if url.fragment and unquote(url.fragment) not in targets[route].parsed.ids:
                    raise ValueError(f"Missing diagram documentation anchor: {name}/{node['id']}: {link['href']}")
    if render_diagrams:
        renderer_digest = _renderer_digest()
        for source in models.values():
            render_diagram(source, renderer_digest)


def _renderer_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(ARCHIFY.rglob("*")):
        if "node_modules" in path.relative_to(ARCHIFY).parts:
            continue
        if path.is_file():
            digest.update(path.relative_to(ARCHIFY).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def render_diagram(source: Path, renderer_digest: str | None = None) -> tuple[Path, dict]:
    source_bytes = source.read_bytes()
    specification_digest = hashlib.sha256(source_bytes).hexdigest()
    digest = hashlib.sha256(source_bytes + (renderer_digest or _renderer_digest()).encode()).hexdigest()
    cached = CACHE / "diagrams" / digest
    artifact = cached / (source.stem + ".html")
    receipt_file = cached / "receipt.json"
    if artifact.is_file() and receipt_file.is_file():
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        expected = receipt.get("artifact", {}).get("sha256")
        if expected and receipt.get("specification", {}).get("sha256") == specification_digest and hashlib.sha256(artifact.read_bytes()).hexdigest() == expected:
            return artifact, receipt
    cached.mkdir(parents=True, exist_ok=True)
    data = json.loads(source.read_text(encoding="utf-8"))
    command = ["node", str(ARCHIFY / "bin" / "archify.mjs"), "deliver", data["diagram_type"],
               str(source), str(artifact), "--quality", "showcase", "--json"]
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise ValueError(f"Archify delivery failed for {source.name}:\n{result.stdout}\n{result.stderr}")
    receipt = json.loads(result.stdout)
    if not receipt.get("ok"):
        raise ValueError(f"Archify did not accept {source.name}: {result.stdout}")
    if receipt.get("specification", {}).get("sha256") != specification_digest:
        raise ValueError(f"Diagram changed while rendering: {source.name}; rebuild the saved version")
    receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return artifact, receipt


def shell(route: str) -> str:
    links = []
    for target, label in NAVIGATION:
        active = route == target if not target else route.startswith(target)
        if target == "ontologies/" and route.startswith(("ontology/", "resources/")):
            active = True
        if target == "tutorials/" and route.startswith("examples/"):
            active = True
        current = ' aria-current="page"' if active else ""
        links.append(f'<a href="{relative_url(route, target)}"{current}>{label}</a>')
    return (
        '<a class="skip-link" href="#content">Zum Inhalt</a>'
        '<header class="site-header"><div class="site-header-inner">'
        f'<a class="site-brand" href="{relative_url(route, "")}"><span aria-hidden="true">◇</span> Spec Compiler</a>'
        '<nav class="site-navigation" aria-label="Hauptnavigation">' + "".join(links) + '</nav>'
        '<div class="site-actions"><button type="button" data-search-open aria-label="Dokumentation durchsuchen">'
        '<span aria-hidden="true">⌕</span><span>Suche</span><kbd>Strg K</kbd></button>'
        '<button type="button" data-theme-toggle aria-label="Farbschema wechseln">◐</button></div>'
        '</div></header>'
        '<dialog id="site-search" class="search-dialog"><form method="dialog" class="search-heading">'
        '<label for="site-search-input">Dokumentation durchsuchen</label>'
        '<button type="submit" aria-label="Suche schließen">×</button></form>'
        '<input id="site-search-input" type="search" placeholder="Begriff, Architekturansicht oder Entscheidung …" autocomplete="off">'
        '<p id="site-search-status" class="search-status" aria-live="polite">Tippe einen Suchbegriff.</p>'
        '<ol id="site-search-results" class="search-results"></ol></dialog>'
    )


def decorate(markup: str, route: str, *, source: Path | None = None, lookup: dict[Path, Document] | None = None) -> str:
    if source and lookup:
        def rewrite(match: re.Match) -> str:
            attribute, quote_char, value = match.groups()
            target = source_target(source, value, lookup)
            if target is None:
                return match.group(0)
            return attribute + "=" + quote_char + html.escape(relative_url(route, target), quote=True) + quote_char
        markup = re.sub(r'\b(href|src)=(["\'])(.*?)\2', rewrite, markup)
        if source.name != "glossary.html" and not route.startswith("reference/decisions/"):
            linker = GlossaryLinker(glossary_entries(), relative_url(route, "reference/glossary.html"))
            linker.feed(markup)
            markup = "".join(linker.parts)
    css = relative_url(route, "assets/site.css")
    script = relative_url(route, "assets/site.js")
    markup = re.sub(r'<link\b[^>]*href=["\'][^"\']*site\.css["\'][^>]*>', "", markup)
    markup = re.sub(r'<script\b[^>]*src=["\'][^"\']*site\.js["\'][^>]*>\s*</script>', "", markup)
    shared = (f'<meta name="site-root" content="{relative_url(route, "")}">'
              f'<link rel="stylesheet" href="{css}"><script src="{script}" defer></script>')
    markup = markup.replace("</head>", shared + "</head>", 1)
    markup = re.sub(r"(<body\b[^>]*>)", lambda match: match.group(1) + shell(route), markup, count=1)
    footer = (
        '<footer class="site-footer"><span>Spec Compiler · explizite Quellen, nachvollziehbare Nachweise</span>'
        '<a href="https://github.com/arturmiller/spec-compiler">Quellcode auf GitHub ↗</a></footer>'
    )
    return markup.replace("</body>", footer + "</body>", 1)


def redirect_page(route: str, target: str) -> str:
    destination = relative_url(route, target)
    payload = json.dumps(destination)
    return (
        '<!doctype html><html lang="de"><meta charset="utf-8"><title>Weiterleitung · Spec Compiler</title>'
        '<script>const target=new URL(' + payload + ',location.href);'
        'target.search=location.search;target.hash=location.hash;location.replace(target.href);</script>'
        f'<p><a href="{html.escape(destination, quote=True)}">Dokumentation öffnen</a></p></html>\n'
    )


def compile_documents(stage: Path) -> list[dict]:
    documents = read_documents()
    lookup = {document.source.resolve(): document for document in documents}
    models = diagram_sources()
    renderer_digest = _renderer_digest()
    (stage / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCES / "assets", stage / "assets", dirs_exist_ok=True)
    entries = []
    for name, source in models.items():
        artifact, _receipt = render_diagram(source, renderer_digest)
        directory = stage / "diagrams"
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact, directory / (name + ".html"))
        shutil.copyfile(source, directory / source.name)
        model = json.loads(source.read_text(encoding="utf-8"))
        locations = [document for document in documents if name in document.parsed.diagrams]
        destination = locations[0].route if locations else "reference/architecture/"
        for node in model.get("components", model.get("nodes", model.get("participants", model.get("states", [])))):
            entries.append({"category": "Diagramm", "title": node.get("label", node.get("name", node["id"])),
                            "text": " ".join([model["meta"]["title"], node.get("sublabel", ""),
                                              node.get("summary", ""), node.get("description", "")]),
                            "url": destination + "?diagram=" + quote(name) + "&node=" + quote(node["id"]) + "#diagram-" + name})
    for document in documents:
        target = stage / document.target
        target.parent.mkdir(parents=True, exist_ok=True)
        for alias in document.parsed.aliases:
            alias_target = stage / (alias + "index.html" if alias.endswith("/") else alias)
            alias_target.parent.mkdir(parents=True, exist_ok=True)
            alias_target.write_text(redirect_page(alias, document.route), encoding="utf-8")
        if document.parsed.redirect:
            target.write_text(redirect_page(document.route, document.parsed.redirect), encoding="utf-8")
            continue
        markup = document.markup
        if 'data-support-inventory' in markup:
            if __package__:
                from .compiler_support import build_inventory, inventory_json, pattern_annotation, render_inventory, term_anchor
            else:
                from compiler_support import build_inventory, inventory_json, pattern_annotation, render_inventory, term_anchor
            inventory = build_inventory(ROOT)
            (target.parent / "compiler-support.json").write_text(inventory_json(inventory), encoding="utf-8", newline="\n")
            markup = re.sub(r'<div\b[^>]*data-support-inventory[^>]*></div>', lambda _: render_inventory(inventory), markup)
            for pattern in inventory["patterns"]:
                expression = r'(<article\b[^>]*data-support-pattern="' + re.escape(pattern["id"]) + r'"[^>]*>)'
                markup = re.sub(expression, lambda match: match[1] + pattern_annotation(pattern), markup)
            for term in inventory["terms"]:
                entries.append({"category": "Compilerunterstützung", "title": term["name"] + " · " + term["label"],
                                "text": " ".join(term["patterns"] + term["roles"]),
                                "url": document.route + "#" + term_anchor(term["name"])})
        if 'data-ontology-dependencies' in markup:
            _analysis, tables = ontology_dependency_views()
            markup = re.sub(r'<div\b[^>]*data-ontology-dependencies[^>]*></div>', lambda _: tables, markup)
        for name in document.parsed.diagrams:
            iframe_url = relative_url(document.route, "diagrams/" + name + ".html")
            figure = (
                f'<figure id="diagram-{name}" class="diagram-figure" data-diagram="{name}">'
                f'<iframe class="diagram-frame" src="{iframe_url}" title="{html.escape(json.loads(models[name].read_text(encoding="utf-8"))["meta"]["title"], quote=True)}" loading="lazy"></iframe>'
                f'<figcaption><a href="{iframe_url}" target="_blank" rel="noopener">Ansicht groß öffnen ↗</a>'
                f'<a href="{relative_url(document.route, "diagrams/" + name + ".json")}">Diagrammmodell (JSON)</a></figcaption></figure>'
            )
            markup = re.sub(r'<figure\b[^>]*data-diagram=["\']' + re.escape(name) + r'["\'][^>]*>[\s\S]*?</figure>', lambda _: figure, markup)
        target.write_text(decorate(markup, document.route, source=document.source, lookup=lookup), encoding="utf-8")
        category = "Entscheidung" if document.route.startswith("reference/decisions/") else "Dokumentation"
        for section in document.parsed.sections:
            entries.append({"category": category, "title": section["title"],
                            "text": section["text"].strip(), "url": document.route + ("#" + section["id"] if section["id"] else "")})
    entries.extend({"category": "Glossar", "title": entry["title"], "text": entry["text"],
                    "url": "reference/glossary.html#" + entry["id"]} for entry in glossary_entries())
    return entries


def ontology_entries(graph_page: Path | None = None, route: str = "ontologies/") -> list[dict]:
    graph_page = graph_page or OUTPUT / "ontologies" / "index.html"
    if not graph_page.is_file():
        raise ValueError("Build the ontology viewer before composing documentation")
    match = re.search(r'<script type="application/json" id="ontology-data">([\s\S]*?)</script>', graph_page.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Ontology viewer has no dataset payload")
    entries = []
    for dataset in json.loads(match.group(1)):
        for node in dataset["nodes"]:
            entries.append({"category": "Ontologie", "title": node["label"],
                            "text": dataset["title"] + " " + node["labelEn"] + " " + node["comment"] + " " + node["id"],
                            "url": route + "?ontology=" + dataset["key"] + "&term=" + quote(node["id"], safe="") + "&context=1"})
        for prop in dataset["properties"]:
            entries.append({"category": "Property", "title": prop["label"],
                            "text": dataset["title"] + " " + prop["labelEn"] + " " + prop["iri"],
                            "url": route + "?ontology=" + dataset["key"] + "&q=" + quote(prop["name"], safe="")})
    return entries


def compose_site(graph_directory: Path | None = None) -> None:
    """Render first, then publish complete files; failed candidates keep last good output."""
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="site-candidate-", dir=CACHE) as directory:
        stage = Path(directory)
        if graph_directory:
            shutil.copytree(graph_directory, stage, dirs_exist_ok=True)
        graph_file = (graph_directory or OUTPUT) / "ontologies" / "index.html"
        entries = compile_documents(stage) + ontology_entries(graph_file)
        example_route = "tutorials/sql-api/graph/"
        example_graph = (graph_directory or OUTPUT) / example_route / "index.html"
        if example_graph.is_file():
            entries += ontology_entries(example_graph, example_route)
            candidate_example = stage / example_route / "index.html"
            candidate_example.parent.mkdir(parents=True, exist_ok=True)
            candidate_example.write_text(decorate(example_graph.read_text(encoding="utf-8"), example_route), encoding="utf-8")
        graph_markup = graph_file.read_text(encoding="utf-8")
        candidate_graph = stage / "ontologies" / "index.html"
        candidate_graph.parent.mkdir(parents=True, exist_ok=True)
        if 'class="site-header"' not in graph_markup:
            graph_markup = decorate(graph_markup, "ontologies/")
        candidate_graph.write_text(graph_markup, encoding="utf-8")
        # Reference pages use the same shell, theme and search as authored docs.
        for reference in sorted(OUTPUT.rglob("index*.html")):
            relative = reference.relative_to(OUTPUT)
            if relative.parts[0] not in {"ontology", "resources", "examples"} or "webvowl" in relative.parts:
                continue
            markup = reference.read_text(encoding="utf-8")
            if 'class="site-header"' in markup or not re.search(r"<body\b", markup, re.IGNORECASE):
                continue
            route = relative.as_posix()
            if 'id="content"' not in markup:
                markup = re.sub(r"<body\b([^>]*)>", r'<body\1><main id="content" class="doc-content">', markup, count=1, flags=re.IGNORECASE)
                markup = markup.replace("</body>", "</main></body>", 1)
            candidate = stage / relative
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(decorate(markup, route), encoding="utf-8")
            if reference.name == "index-de.html":
                parsed = DocumentParser()
                parsed.feed(markup)
                for section in parsed.sections:
                    entries.append({"category": "Referenz", "title": section["title"],
                                    "text": section["text"].strip(), "url": route + ("#" + section["id"] if section["id"] else "")})
        entries.sort(key=lambda entry: (entry["category"], entry["title"], entry["url"]))
        (stage / "assets" / "search-index.json").write_text(
            json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        validate_published_links(stage, fallback=OUTPUT)
        for source in sorted(stage.rglob("*")):
            if not source.is_file():
                continue
            destination = OUTPUT / source.relative_to(stage)
            publish_file(source, destination)


def validate_published_links(output: Path | None = None, *, fallback: Path | None = None) -> None:
    """Check authored navigation, sources, iframe URLs, and every search result locally."""
    output = output or OUTPUT
    files = [output / document.target for document in read_documents()]
    files.append(output / "ontologies" / "index.html")
    example = output / "tutorials/sql-api/graph/index.html"
    if example.is_file():
        files.append(example)
    for base in ("ontology", "resources", "examples"):
        files.extend(output.joinpath(base).rglob("index*.html"))
    entries = json.loads((output / "assets" / "search-index.json").read_text(encoding="utf-8"))
    checks = [(output / "index.html", entry["url"]) for entry in entries]
    parsed_files = {}
    for path in files:
        parsed = DocumentParser()
        parsed.feed(path.read_text(encoding="utf-8"))
        if parsed.duplicates:
            raise ValueError(f"Duplicate published anchors: {path}: {sorted(parsed.duplicates)}")
        parsed_files[path.resolve()] = parsed
        checks.extend((path, value) for _tag, value in parsed.links)
    for source, value in checks:
        url = urlsplit(html.unescape(value))
        if url.scheme or url.netloc:
            continue
        target = (source.parent / unquote(url.path)).resolve() if url.path else source
        if not target.is_relative_to(output.resolve()):
            raise ValueError(f"Published link leaves site: {source}: {value}")
        if target.is_dir() or url.path.endswith("/"):
            target /= "index.html"
        if not target.is_file() and fallback:
            target = fallback / target.relative_to(output)
        if not target.is_file():
            raise ValueError(f"Broken published link: {source}: {value}")
        if url.fragment and target.suffix == ".html":
            if target not in parsed_files:
                parsed = DocumentParser()
                parsed.feed(target.read_text(encoding="utf-8"))
                parsed_files[target] = parsed
            if unquote(url.fragment) not in parsed_files[target].ids:
                raise ValueError(f"Missing published anchor: {source}: {value}")

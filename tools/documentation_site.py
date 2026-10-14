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
    ("architecture/", "Architektur"),
    ("workflows/", "Abläufe"),
    ("decisions/", "Entscheidungen"),
    ("ontologies/", "Ontologien"),
    ("development/", "Entwicklung"),
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
    return documents


def diagram_sources() -> dict[str, Path]:
    result = {}
    for source in sorted((SOURCES / "diagrams").glob("*.json")):
        data = json.loads(source.read_text(encoding="utf-8"))
        if data.get("diagram_type") not in {"architecture", "workflow", "sequence", "dataflow", "lifecycle"}:
            raise ValueError(f"Unknown diagram type: {source}")
        if data.get("meta", {}).get("quality_profile") != "showcase":
            raise ValueError(f"Documentation diagrams require the showcase profile: {source}")
        result[source.stem] = source
    return result


def source_target(source: Path, value: str, document_map: dict[Path, Document]) -> str | None:
    parsed = urlsplit(html.unescape(value))
    if parsed.scheme or parsed.netloc or value.startswith("#"):
        return None
    target = (source.parent / unquote(parsed.path)).resolve()
    if target in document_map:
        suffix = ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
        return document_map[target].route + suffix
    if target == ROOT / "tools" / "ontology_relationship_graph.html":
        return "ontologies/" + ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
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
        destination = locations[0].route if locations else "architecture/"
        for node in model.get("components", model.get("nodes", model.get("participants", model.get("states", [])))):
            entries.append({"category": "Diagramm", "title": node.get("label", node.get("name", node["id"])),
                            "text": model["meta"]["title"] + " " + node.get("sublabel", ""),
                            "url": destination + "?diagram=" + quote(name) + "&node=" + quote(node["id"]) + "#diagram-" + name})
    for document in documents:
        target = stage / document.target
        target.parent.mkdir(parents=True, exist_ok=True)
        if document.parsed.redirect:
            target.write_text(redirect_page(document.route, document.parsed.redirect), encoding="utf-8")
            continue
        markup = document.markup
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
        category = "Entscheidung" if document.route.startswith("decisions/") else "Dokumentation"
        for section in document.parsed.sections:
            entries.append({"category": category, "title": section["title"],
                            "text": section["text"].strip(), "url": document.route + ("#" + section["id"] if section["id"] else "")})
    return entries


def ontology_entries(graph_page: Path | None = None) -> list[dict]:
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
                            "url": "ontologies/?ontology=" + dataset["key"] + "&term=" + quote(node["id"], safe="") + "&context=1"})
        for prop in dataset["properties"]:
            entries.append({"category": "Property", "title": prop["label"],
                            "text": dataset["title"] + " " + prop["labelEn"] + " " + prop["iri"],
                            "url": "ontologies/?ontology=" + dataset["key"] + "&q=" + quote(prop["name"], safe="")})
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
        entries.sort(key=lambda entry: (entry["category"], entry["title"], entry["url"]))
        (stage / "assets" / "search-index.json").write_text(
            json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        graph_markup = graph_file.read_text(encoding="utf-8")
        candidate_graph = stage / "ontologies" / "index.html"
        candidate_graph.parent.mkdir(parents=True, exist_ok=True)
        if 'class="site-header"' not in graph_markup:
            graph_markup = decorate(graph_markup, "ontologies/")
        candidate_graph.write_text(graph_markup, encoding="utf-8")
        # Keep WIDOCO/RDF routes stable while giving reference and resource pages
        # the same entry points. Fragment files and legacy WebVOWL stay untouched.
        for reference in sorted(OUTPUT.rglob("index*.html")):
            relative = reference.relative_to(OUTPUT)
            if relative.parts[0] not in {"ontology", "resources", "examples"} or "webvowl" in relative.parts:
                continue
            markup = reference.read_text(encoding="utf-8")
            if 'class="site-header"' in markup or not re.search(r"<body\b", markup, re.IGNORECASE):
                continue
            route = relative.as_posix()
            markup = re.sub(r'<script[^>]*src="resources/dark-mode-toggle.mjs"[^>]*></script>\s*<div class="darkmode">[\s\S]*?</div>', "", markup)
            markup = re.sub(r'<link[^>]*href="resources/(dark|light).css"[^>]*>', "", markup)
            markup = re.sub(r"<body\b([^>]*)>", r'<body\1 class="reference-page"><span id="content"></span>', markup, count=1, flags=re.IGNORECASE)
            candidate = stage / relative
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(decorate(markup, route), encoding="utf-8")
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
    entries = json.loads((output / "assets" / "search-index.json").read_text(encoding="utf-8"))
    checks = [(output / "index.html", entry["url"]) for entry in entries]
    for path in files:
        parsed = DocumentParser()
        parsed.feed(path.read_text(encoding="utf-8"))
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
            markup = target.read_text(encoding="utf-8")
            if not re.search(r'\bid=["\']' + re.escape(url.fragment) + r'["\']', markup):
                raise ValueError(f"Missing published anchor: {source}: {value}")

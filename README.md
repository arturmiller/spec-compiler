# Spec Compiler

Explizite RDF/SHACL-Specs werden deterministisch in Verträge, Black-Box-Tests
und begrenzte Work Items kompiliert. Produktimplementierungen bleiben getrennt.

Die kanonische Dokumentation liegt als HTML in [docs/](docs/index.html):
Architektur (arc42 mit C4), Abläufe, ADRs, Ontologiegraphen und Entwicklung.

## Lokal ansehen

```console
uv run --extra dev poe documentation-preview
```

Öffne http://127.0.0.1:8080/. Gespeicherte HTML-, Diagramm- und Graphänderungen
werden neu gebaut; bei Fehlern bleibt die letzte gültige Ansicht verfügbar.
Dies veröffentlicht nichts.

## Prüfen und bauen

```console
uv run --extra dev poe run
uv run --extra dev poe documentation-site
```

Für den Dokumentationsbuild werden Node, Java 17 und Graphviz benötigt.
Ausgabe: `build/ontology-site/`. GitHub Pages verwendet denselben Build.
[Entwicklungsdetails](docs/development/index.html) und
[Repository-Regeln](AGENTS.md) erklären Quellen und Verantwortlichkeiten.

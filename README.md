# Spec Compiler

Dieses kleine Beispiel beantwortet eine konkrete Frage: Kann ein RDF-Vertrag
ein Artikelobjekt mit einem GET-Endpunkt und einer SQLite-Tabelle verbinden und
daraus reproduzierbare, implementationsneutrale Verträge und Tests erzeugen?

## Ausführen

```console
uv run --extra dev poe run
```

Der Befehl funktioniert unter Windows, Linux und macOS. Einzelne Schritte sind
mit `uv run --extra dev poe generate` und `uv run --extra dev poe test`
verfügbar.

Ein anderes Produkt kann explizit kompiliert werden:

```console
uv run --extra dev python tools/generate.py --product products/<name>
```

Das Projekt ist nach Verantwortlichkeiten getrennt:

- `tools/`: Generator für die Vertragstests.
- `products/`: Ablage für KI-generierte Produkte; standardmäßig von Git ignoriert.
- `products/sql_api_example/`: versioniertes Referenzprodukt mit Produktcode,
  `specs/`, Laufzeitmanifest, deterministisch erzeugten `tests/`, erwarteter
  OpenAPI-Spezifikation und `generated/`-Arbeitsaufträgen.
- `products/spec_compiler/`: Self-Description Bundle, dessen Specs
  die allgemeine Softwareanwendung, ihre Konformität zu Compiler Protocol v1
  und ihren separat austauschbaren Transformationsvertrag beschreiben. Ein
  getrennter Bootstrap-Prozess bezeichnet die vorhandene G0-Implementierung als
  Seed für eine spätere, codegenerierte G1-Implementierung.
- `ontology/shacl-contract.ttl`: kanonische, öffentliche Definition des
  experimentellen Vertragsvokabulars.
- `docs/generation-principles.md`: Regeln gegen erfundene
  Implementierungsanforderungen.

`tools/generate.py` leitet reproduzierbare Werte aus den SHACL-Grenzen ab. Für
den aktuellen Vertrag entstehen immer `description="x"` und `price=0.01`.
Danach prüft der generierte Test SQLite-Schema, die vom laufenden Produkt
veröffentlichte OpenAPI-Spezifikation, den echten GET-Endpunkt und die
SHACL-Konformität der Antwort.

Der Spec Compiler wird außerdem über sein externes Compilerverhalten beschrieben.
Der vorhandene Generator dient als expliziter Bootstrap-Compiler `G0` und
materialisiert aus seinem Seed deterministisch den eigenständigen Compiler `G1`
unter `products/spec_compiler/src/spec_compiler.py`. Das Produktmanifest startet
G1 mit seinem eigenen `pyproject.toml` und Lockfile. Die generierten
Black-box-Tests führen G1 auf einem isolierten Product Bundle zweimal aus;
beide Läufe müssen byte-identische Vertragsartefakte erreichen.

Der Bootstrap-Prozess verwendet ausdrücklich die Strategie
`sco:ModifyExistingImplementation`. Dadurch ist die vorhandene Python-
Implementierung die technische Ausgangsbasis für G1, ohne Python zur
Anforderung des Transformationsvertrags zu machen. Die aktuelle deterministische
Seed-Transformation ändert den Generationsmarker und übernimmt den übrigen
Quellstand. Ein Coding Agent ist an diesem Schritt nicht beteiligt; spätere
inhaltliche Evolution kann auf demselben geprüften G1-Bundle aufbauen.

## Ontologie-Dokumentation

Die öffentliche Dokumentationsseite wird lokal mit WIDOCO 1.4.25 und dem darin
enthaltenen WebVOWL gebaut:

```console
uv run --extra dev poe ontology-site
```

Das Ergebnis liegt unversioniert unter `build/ontology-site/`. Der erste Lauf
lädt das gepinnte WIDOCO-JAR in `.cache/widoco/` und prüft dessen SHA-256. Die
Startseite verlinkt die englische und deutsche WIDOCO-Referenz, den interaktiven
WebVOWL-Graphen mit Entitätssuche, die Turtle-Serialisierung und getrennte
Beispielspezifikationen.

Der Workflow `.github/workflows/ontology-pages.yml` baut die Site bei Pull
Requests und veröffentlicht sie nach erfolgreichen Tests bei Pushes auf `main`
über GitHub Pages. Im Repository muss unter **Settings → Pages → Build and
deployment → Source** einmalig **GitHub Actions** ausgewählt werden.

Die experimentellen IRIs beginnen mit
`https://arturmiller.github.io/spec-compiler/`; das Vokabular verwendet den
dereferenzierbaren Fragment-Namespace `.../ontology/#`. Ein stabiler Redirect über
w3id.org bleibt eine spätere Option, falls das Vokabular produktiv wird.
Auch die getrennten Toolchain- und SQL-API-Ressourcen-Namespaces besitzen unter
`resources/toolchain/` und `resources/sql-api/` eigene HTML- und Turtle-Ziele.

`generated/expected-openapi.json` beschreibt den aus den Specs erwarteten
HTTP-Vertrag. Der OpenAPI-Test ruft das Dokument der laufenden Implementierung
ab und vergleicht beide semantisch; zusätzliche Beschreibungen oder
Fehlerantworten bleiben erlaubt.

Der Generator kompiliert denselben Vertrag außerdem in einen Work Graph. Jeder
Arbeitsauftrag enthält Ziel, Verpflichtungen, Abhängigkeiten, Abgrenzung und den
exakten generierten Pytest-Node, der seinen Abschluss nachweist. Die Texte
entstehen aus festen Vorlagen; ein Sprachmodell ist nur für Änderungen am
jeweiligen Produkt vorgesehen. Git ignoriert neue Einträge unter `products/`;
nur `sql_api_example` wird als nachvollziehbares Beispiel eingecheckt.

Damit sind Werkzeug und Ergebnisse klar getrennt: `tools/` enthält die
Transformation von Specs zu Verträgen, Tests und Arbeitsaufträgen;
`products/<name>/` enthält jeweils sämtliche Ein- und Ausgaben eines Produkts.

## Architektur

Die lebende Architekturdokumentation beginnt unter
[`docs/architecture/`](docs/architecture/README.md):

- [arc42](docs/architecture/arc42.md) beschreibt Ziele, Randbedingungen,
  Laufzeiten, Entscheidungen, Qualitätsanforderungen und Risiken.
- Das [C4-Modell](docs/architecture/c4.md) zeigt Systemkontext, Container und
  Komponenten ohne statische Dateien mit Laufzeitcontainern zu verwechseln.
- [ADRs](docs/architecture/decisions/) halten folgenreiche Entscheidungen fest.
- Der [Pflegestandard](docs/architecture/maintenance.md) macht Aktualisierungen
  bei Architekturänderungen verbindlich.

`AGENTS.md` enthält diese Regeln für Codex und andere Coding Agents.

Die generierten Tests importieren keinen Produktcode. Sie starten das Produkt
über dessen `product.toml` als separaten Prozess und prüfen nur die ausdrücklich
vereinbarten Grenzen. Das Referenzprodukt verwendet Python und FastAPI; eine
andere Implementierung darf jede Sprache und jedes Framework wählen. Maßgeblich
ist das Prinzip [Keine erfundenen Anforderungen](docs/generation-principles.md).

`sh:*` ist standardisiertes SHACL. Die öffentlichen `sco:*`-Aussagen beschreiben
die technische Verbindung zwischen HTTP und Speicherung. Der lokale Name von
`sh:path` wird gemäß der dokumentierten Compilerkonvention gleichermaßen als
JSON-Feld und SQL-Spalte verwendet: `article:price` wird zu `price`.

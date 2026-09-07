# Spec Compiler

Dieses Projekt untersucht, wie explizite RDF-Verträge für unterschiedliche
Softwaredomänen in reproduzierbare, implementationsneutrale Verträge und Tests
kompiliert werden. Zwei vertikale Referenzprodukte prüfen heute einen
SQL/OpenAPI-Vertrag und eine source-backed KfW-458-Antragstellerentscheidung.

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
- `products/kfw_458_eligibility/`: versioniertes Referenzprodukt mit manuell
  kuratierten Rules und Source Citations, Decision Protocol v1, kompiliertem
  Decision Contract sowie Black-box-Fällen für `eligible`, `ineligible` und
  `unknown` einschließlich eines deterministischen, quellengestützten
  Frageablaufs.
- `products/spec_compiler/`: Self-Description Bundle, dessen Specs
  die allgemeine Softwareanwendung, ihre Konformität zu Compiler Protocol v1
  und ihren separat austauschbaren Transformationsvertrag beschreiben. Ein
  getrennter Bootstrap-Prozess bezeichnet die vorhandene G0-Implementierung als
  Seed für G1. SQL API und KfW 458 sind getrennte Conformance Fixtures.
- `ontology/`: kanonische, öffentliche Definitionen der getrennten SHACL
  Contract, Decision and Obligation Core und Funding Domain Ontologies.
- `docs/generation-principles.md`: Regeln gegen erfundene
  Implementierungsanforderungen.

`tools/generate.py` leitet reproduzierbare Werte aus den SHACL-Grenzen ab. Für
den aktuellen Vertrag entstehen immer `description="x"` und `price=0.01`.
Danach prüft der generierte Test SQLite-Schema, die vom laufenden Produkt
veröffentlichte OpenAPI-Spezifikation, den echten GET-Endpunkt und die
expliziten Antwortverpflichtungen. SHACL dient dabei als Eingabeprofil; die
JSON-Antwort wird ohne künstliche RDF-Konvertierung direkt durch generierte
Black-box-Assertions geprüft.

Der Spec Compiler wird außerdem über sein externes Compilerverhalten beschrieben.
Der vorhandene Generator dient als expliziter Bootstrap-Compiler `G0` und
materialisiert aus seinem Seed deterministisch den eigenständigen Compiler `G1`
unter `products/spec_compiler/src/spec_compiler.py`. Das Produktmanifest startet
G1 mit seinem eigenen `pyproject.toml` und Lockfile. Die generierten
Black-box-Tests führen G1 auf einem isolierten Product Bundle zweimal aus;
beide Läufe müssen byte-identische Vertragsartefakte erreichen. Das gilt für
beide deklarierten Conformance Fixtures und damit für beide Compilerprofile.

Das Decision-Profil kompiliert einen expliziten `sdo:DecisionContract`, eine
gepinnte Rule Set Version und vollständige Source Provenance nach
`generated/decision-contract.json`. Das Decision Product erhält über sein
Manifest einen UTF-8-JSON-Request auf stdin und liefert genau ein JSON-Resultat
auf stdout. Der Vertrag fordert kein HTTP, Python oder RDF im Produkt. Ein
fehlender Fact wird als Fact Gap und nicht als `false` behandelt. Der
Compiler wählt für ein noch `unknown`es Result genau eine explizit formulierte
Fact Question aus den aktuellen Fact Gaps. Die Antwort wird am ausgegebenen
JSON Pointer in den vollständigen Case eingetragen und erneut eingereicht; die
Auswahl verlangt weder Session State noch UI. Der mitgelieferte Scope Note
stellt klar, dass das Pilotresultat weder Beratung
noch KfW-Zusage oder Förderentscheidung ist.

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
Startseite verlinkt englische und deutsche WIDOCO-Referenzen, interaktive
WebVOWL-Graphen mit Entitätssuche, Turtle-Serialisierungen und getrennte
Beispielspezifikationen.

WebVOWL wird in getrennten Sichten veröffentlicht: `/ontology/webvowl/` zeigt
das `sco:*`-Vokabular, `/ontology/decision/webvowl/` den wiederverwendbaren
`sdo:*`-Kern und `/ontology/funding/webvowl/` das `funding:*`-Vokabular;
`/examples/sql-api/webvowl/` zeigt das fachliche SQL-API-Beispiel mit
`article:Article`, `article:description` und `article:price`. Eine ausschließlich
für WebVOWL abgeleitete OWL-Projektion verbindet außerdem `GetArticleEndpoint`
über `returns` mit `ArticleShape` und über `reads from` mit `ArticlesTable`.
Die Tabelle verweist über `stores` ebenfalls auf `ArticleShape`, das über
`target class` mit `Article` verbunden ist. Diese Projektion begründet keine
Produktanforderungen. Die vollständigen SHACL-Constraints bleiben in den
verlinkten Turtle-Specs, da WebVOWL primär OWL/RDFS-Strukturen visualisiert. Der
Graph verwendet den SQL-API-Ressourcen-Namespace als WebVOWL-Basis, sodass diese
vier Beispielknoten nicht fälschlich als `external` erscheinen.

Der Workflow `.github/workflows/ontology-pages.yml` baut die Site bei Pull
Requests und veröffentlicht sie nach erfolgreichen Tests bei Pushes auf `main`
über GitHub Pages. Im Repository muss unter **Settings → Pages → Build and
deployment → Source** einmalig **GitHub Actions** ausgewählt werden.

Die experimentellen IRIs beginnen mit
`https://arturmiller.github.io/spec-compiler/`; die Vokabulare verwenden die
dereferenzierbaren Fragment-Namespaces `.../ontology/#`,
`.../ontology/decision/#` und `.../ontology/funding/#`. Ein stabiler Redirect über
w3id.org bleibt eine spätere Option, falls das Vokabular produktiv wird.
Auch die getrennten Toolchain-, SQL-API- und KfW-458-Ressourcen-Namespaces
besitzen eigene HTML- und Turtle-Ziele.

`generated/expected-openapi.json` beschreibt den aus den Specs erwarteten
HTTP-Vertrag. Der OpenAPI-Test ruft das Dokument der laufenden Implementierung
ab und vergleicht beide semantisch; zusätzliche Beschreibungen oder
Fehlerantworten bleiben erlaubt.

Der Generator kompiliert denselben Vertrag außerdem in einen Work Graph. Jeder
Arbeitsauftrag enthält Ziel, Verpflichtungen, Abhängigkeiten, Abgrenzung und den
exakten generierten Pytest-Node, der seinen Abschluss nachweist. Die Texte
entstehen aus festen Vorlagen; ein Sprachmodell ist nur für Änderungen am
jeweiligen Produkt vorgesehen. Git ignoriert neue Einträge unter `products/`;
`sql_api_example` und `kfw_458_eligibility` werden als nachvollziehbare
Beispiele eingecheckt.

Damit sind Werkzeug und Ergebnisse klar getrennt: `tools/` enthält die
Transformation von Specs zu Verträgen, Tests und Arbeitsaufträgen;
`products/<name>/` enthält jeweils sämtliche Ein- und Ausgaben eines Produkts.

Intern normalisiert der Compiler ausschließlich explizite Aussagen in ein
**Explicit Obligation Model**. Nicht spezifizierte Eigenschaften werden nicht
zu Tests. Zusätzliche JSON-Felder sind deshalb erlaubt, sofern die Spec nicht
ausdrücklich `sh:closed true` setzt.

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

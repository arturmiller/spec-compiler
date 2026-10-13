# Spec Compiler

Dieses Projekt untersucht, wie explizite RDF-Verträge für unterschiedliche
Softwaredomänen in reproduzierbare, implementationsneutrale Verträge und Tests
kompiliert werden. Drei vertikale Referenzprodukte prüfen heute einen
SQL/OpenAPI-Vertrag, eine source-backed KfW-458-Antragstellerentscheidung und
eine kleine Cloud-Compliance-Entscheidung auf Basis von NIST IA-2 und IA-2(1).

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
- `products/cloud_access_compliance/`: zweites Decision-Referenzprodukt mit
  getrenntem `cloud:`-Vokabular, expliziten Rule-imposed Obligations,
  NIST-Source-Citations, einem interaktiven Fact-Question-Ablauf und einer
  unabhängig ausgewerteten MFA-Nachweisanforderung.
- `products/spec_compiler/`: Self-Description Bundle, dessen Specs
  die allgemeine Softwareanwendung, ihre Konformität zu Compiler Protocol v1
  und ihren separat austauschbaren Transformationsvertrag beschreiben. Ein
  getrennter Bootstrap-Prozess bezeichnet die vorhandene G0-Implementierung als
  Seed für G1. SQL API, KfW 458 und Cloud Compliance sind getrennte
  Conformance Fixtures.
- `ontology/`: kanonische, öffentliche Definitionen der getrennten SHACL
  Contract, Decision and Obligation Core, Funding Domain und Cloud Compliance
  Domain Ontologies.
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
alle deklarierten Conformance Fixtures und Compilerprofile.

Das Decision-Profil kompiliert einen expliziten `sdo:DecisionContract`, eine
aus einem expliziten Decision Date ausgewählte Rule Set Version und vollständige
Source Provenance nach
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

Evidence Evaluation Conventions v1 halten eine erfüllte Rule Condition und die
zugehörige Nachweisanforderung getrennt. Das KfW-458-Beispiel wertet den
Grundbuchauszug für selbstnutzende Eigentümer mit Bonusanspruch unabhängig als
`fulfilled`, `missing` oder `not_applicable` aus und klassifiziert gelieferte
Evidence nur anhand expliziter Assessments. Der Resultatpfad enthält eine eigene
Source Citation; Dateiformat, Upload, Speicherung und automatische
Dokumentenprüfung bleiben außerhalb des Vertrags.

Obligation Evaluation Conventions v1 bilden eine Rule Condition explizit auf
den Status ihrer authored Obligation ab: `satisfied` wird `fulfilled`,
`violated` bleibt `violated`, und `unknown` bleibt `unknown`. Das
Cloud-Compliance-Beispiel macht diese Semantik erstmals ausführbar und gibt für
jede Obligation Text, Rule, Condition, Source Citation und Erklärung aus. Das
KfW-Beispiel erfindet dagegen keine Pflichten aus Eignungskriterien und liefert
deshalb eine leere Liste von Obligation Evaluations.

Version Selection Conventions v1 wählen die Version ausschließlich aus dem
stabilen Rule Set, dem expliziten Decision Date und den autorisierten
halboffenen Validity Periods. Der Request darf keine Version vorgeben; jedes
Result nennt die abgeleitete Version und das Datum. Fehlende Daten, Lücken und
Überlappungen scheitern explizit, statt auf „heute“ oder „latest“ auszuweichen.

Der Bootstrap-Prozess verwendet ausdrücklich die Strategie
`sco:ModifyExistingImplementation`. Dadurch ist die vorhandene Python-
Implementierung die technische Ausgangsbasis für G1, ohne Python zur
Anforderung des Transformationsvertrags zu machen. Die aktuelle deterministische
Seed-Transformation ändert den Generationsmarker und übernimmt den übrigen
Quellstand. Ein Coding Agent ist an diesem Schritt nicht beteiligt; spätere
inhaltliche Evolution kann auf demselben geprüften G1-Bundle aufbauen.

## Ontologie-Dokumentation

Die öffentliche Dokumentationsseite wird lokal mit WIDOCO 1.4.25, Graphviz
(`dot`) und Cytoscape.js 3.34.3 gebaut:

```console
uv run --extra dev poe ontology-site
```

Das Ergebnis liegt unversioniert unter `build/ontology-site/`. Der erste Lauf
lädt das gepinnte WIDOCO-JAR und die gepinnte Cytoscape.js-Datei in `.cache/`
und prüft ihre SHA-256-Hashes. Die Startseite verlinkt englische und deutsche
WIDOCO-Referenzen, den [Ontologie-Beziehungsgraphen](https://arturmiller.github.io/spec-compiler/graph/),
Turtle-Serialisierungen und getrennte Beispielspezifikationen. Der Graph zeigt
fünf getrennte Datensätze: `sco:*`, `sdo:*`, `funding:*`, `cloud:*` und das
SQL-API-Beispiel. Seine Positionen werden beim Build berechnet und ändern sich
beim Anklicken oder Filtern nicht. Plus, Minus, Mausrad und „Einpassen“ steuern
den sichtbaren Bereich ausdrücklich.

Die bisherigen WebVOWL-Sichten bleiben unter ihren URLs erhalten:
`/ontology/webvowl/` zeigt
das `sco:*`-Vokabular, `/ontology/decision/webvowl/` den wiederverwendbaren
`sdo:*`-Kern, `/ontology/funding/webvowl/` das `funding:*`-Vokabular und
`/ontology/cloud/webvowl/` das `cloud:*`-Vokabular;
`/examples/sql-api/webvowl/` zeigt das fachliche SQL-API-Beispiel mit
`article:Article`, `article:description` und `article:price`. Eine ausschließlich
für WebVOWL abgeleitete OWL-Projektion verbindet außerdem `GetArticleEndpoint`
über `returns` mit `ArticleShape` und über `reads from` mit `ArticlesTable`.
Die Tabelle verweist über `stores` ebenfalls auf `ArticleShape`, das über
`target class` mit `Article` verbunden ist. Der neue Beziehungsgraph verwendet
dieselbe abgeleitete SQL-Projektion. Sie begründet keine Produktanforderungen.
Die vollständigen SHACL-Constraints bleiben in den verlinkten Turtle-Specs.
Die Projektion verwendet den SQL-API-Ressourcen-Namespace als Ontologie-Basis,
sodass die vier Beispielknoten in WebVOWL weiterhin intern bleiben.

Der Workflow `.github/workflows/ontology-pages.yml` baut die Site bei Pull
Requests und veröffentlicht sie nach erfolgreichen Tests bei Pushes auf `main`
über GitHub Pages. Im Repository muss unter **Settings → Pages → Build and
deployment → Source** einmalig **GitHub Actions** ausgewählt werden.

Die experimentellen IRIs beginnen mit
`https://arturmiller.github.io/spec-compiler/`; die Vokabulare verwenden die
dereferenzierbaren Fragment-Namespaces `.../ontology/#`,
`.../ontology/decision/#`, `.../ontology/funding/#` und
`.../ontology/cloud/#`. Ein stabiler Redirect über
w3id.org bleibt eine spätere Option, falls das Vokabular produktiv wird.
Auch die getrennten Toolchain-, SQL-API-, KfW-458- und
Cloud-Privileged-Access-Ressourcen-Namespaces besitzen eigene HTML- und
Turtle-Ziele.

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

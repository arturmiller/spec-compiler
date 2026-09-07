# Generierungsprinzipien

## Keine erfundenen Anforderungen

Eine generierte Verpflichtung oder Assertion muss auf genau eine der folgenden
Quellen zurückführbar sein:

1. eine explizite Aussage in den Produktspecs oder
2. eine dokumentierte, versionierte Compiler- beziehungsweise
   Laufzeitkonvention.

Fehlt die notwendige Information oder ist sie mehrdeutig, muss der Generator
mit einer verständlichen Fehlermeldung abbrechen. Er darf keine scheinbar
naheliegende Entscheidung ergänzen. Insbesondere dürfen Sprache, Framework,
Modulnamen, Funktionsnamen und interne Architektur nicht aus der Beispiel-
implementierung in generierte Anforderungen gelangen.

Python ist momentan die Sprache des Generators und des Test-Harness. Das
verlangt nicht, dass ein Produkt in Python implementiert wird. Vertragstests
starten das Produkt als separaten Prozess und beobachten ausschließlich das
gewählte, explizite Protokoll: HTTP, OpenAPI und SQLite im SQL-Profil oder
UTF-8-JSON über Standard-Ein-/Ausgabe im Decision-Profil. Sie importieren
keinen Produktcode.

## Quellen der aktuellen Anforderungen

Die öffentlichen Vokabulare liegen autoritativ in
`ontology/shacl-contract.ttl`, `ontology/decision-obligation.ttl` und
`ontology/funding.ttl`. Sie verwenden die getrennten Namespaces `sco:`, `sdo:`
und `funding:`. Konkrete Toolchain-, SQL-API- und KfW-Ressourcen liegen in
getrennten `resources/.../#`-Namespaces. Eine Produkt-Spec darf einen
öffentlichen Vokabularbegriff verwenden, ohne ihn neu zu definieren; der
Publikationsvalidator verlangt dafür eine Definition sowie deutsche und
englische Labels in der zuständigen kanonischen Ontologie.

WIDOCO-HTML, WebVOWL-Daten und publizierte Beispielkopien sind abgeleitete
Dokumentationsartefakte. Sie begründen keine Produktanforderungen und werden
nicht als deterministische Vertragsartefakte behandelt.

Jedes kanonische Vokabular erhält einen eigenen WIDOCO-/WebVOWL-Graphen. Ein
weiterer, klar getrennter Visualisierungsgraph wird aus den SQL-API-Specs
gebildet. Fachliche Klassen und Properties müssen dafür explizit als OWL/RDFS-
Terme mit deutschen und englischen Labels deklariert sein. Die Visualisierung
ersetzt weder die Specs noch deren ausführbare Constraints.

Für diesen zweiten Graphen projiziert der Dokumentationsbuilder ausgewählte
Instanz- und SHACL-Beziehungen in ausschließlich visuelle OWL-Klassen und
Object Properties. Dabei bleibt das Node Shape als eigener Knoten zwischen
Endpunkt beziehungsweise Tabelle und fachlicher Zielklasse sichtbar. Die
Projektion ist abgeleitet, nicht autoritativ und darf weder vom Compiler gelesen
werden noch neue Testverpflichtungen begründen.

Die Ontologie-IRI des abgeleiteten Graphen entspricht seinem
`resources/sql-api/`-Basisnamespace. WebVOWL erkennt dadurch die projizierten
Beispielknoten als interne Elemente. Eigene Visualisierungskanten behalten ihren
getrennten `resources/sql-api/visualization/#`-Namespace.

Die RDF-/SHACL-Specs legen ausdrücklich fest:

- GET-Endpunkt, Pfad, Pfadparameter und dessen Datentyp,
- erfolgreicher Statuscode und Medientyp,
- die vom Endpunkt gelesene Tabelle,
- SQLite als Datenbank-Engine,
- Tabellenname, ID-Spalte, ID-Datentyp, Primärschlüssel und ID-Erzeugung,
- Response- und Speicher-Shape einschließlich ihrer Constraints,
- über `sh:closed`, ob zusätzliche Response-Felder erlaubt sind.

Der Generator lädt alle `*.ttl`-Dateien unter `specs/` in einen gemeinsamen
Vertragsgraphen. Dateinamen wie `article_shape.ttl` tragen keine Semantik und
sind keine Anforderung an andere Produkte.

Der RDF-Graph wird in ein **Explicit Obligation Model** normalisiert. Dieses
interne Modell enthält ausschließlich Aussagen, die eine beobachtbare
Verpflichtung begründen. Fehlende Aussagen erzeugen weder Defaults noch Tests.

### Decision and Obligation Compilation

[ADR 0016](architecture/decisions/0016-evolve-to-decision-and-obligation-compilation.md)
definiert die Grenzen; [ADR 0017](architecture/decisions/0017-compile-source-backed-decisions-through-a-cli-protocol.md)
materialisiert den ersten vertikalen Schnitt und
[ADR 0018](architecture/decisions/0018-select-next-fact-question-from-current-fact-gaps.md)
ergänzt die deterministische Auswahl der nächsten Frage. Das Decision-Profil normalisiert
die autorisierten Aussagen in ein typisiertes, unveränderliches **Explicit
Decision and Obligation Model**. Für diese und weitere Schnitte gelten folgende
Regeln:

- Ein externes Dokument ist nicht unmittelbar die Quelle einer generierten
  Anforderung. Eine autorisierte Spec-Aussage verweist über eine präzise Source
  Citation auf eine unveränderlich identifizierte Source Revision. Die
  generierte Anforderung stammt weiterhin aus der Spec-Aussage oder aus einer
  benannten, versionierten Konvention.
- Entscheidungen, Condition Evaluations, Fact Gaps, Fragen, Obligations und
  Evidence Requirements sind generierte Ergebnisse und benötigen dieselbe
  nachvollziehbare Provenienz wie Assertions und Work Items.
- Das Fehlen eines für eine Condition benötigten Fallsachverhalts wird als Fact
  Gap ausgewiesen und darf zu `unknown` führen. Ein fehlender Sachverhalt wird
  nicht als `false` interpretiert.
- Mehrdeutige Specs, widersprüchliche Facts, eine nicht eindeutig anwendbare
  Rule Set Version oder mehrere unvereinbare Schlussfolgerungen sind Fehler.
  Sie dürfen nicht als `unknown` kaschiert werden.
- Decision Date und Rule Set Version werden explizit angegeben. Es gibt keinen
  impliziten Standard für „heute“, „aktuell“ oder „neueste Version“.
- Die Transformation externer Dokumente in autorisierte Specs ist zunächst ein
  menschlich kuratierter Schritt außerhalb der deterministischen Kompilierung.
  Weder Scraping noch ein Sprachmodell darf dabei stillschweigend Teil des
  Compilers werden.

Die kanonischen Begriffe und Pilotgrenzen stehen in der
[Decision and Obligation Compilation roadmap](architecture/decision-and-obligation-roadmap.md).

`product.toml` ist kein fachlicher Vertrag. Es ist der kleine Laufzeitadapter,
über den das Werkzeug ein Produkt unabhängig von seiner Technologie startet.
Das Manifest deklariert Argumentliste, Arbeitsverzeichnis, Umgebungsvariablen
und den Pfad des vom laufenden Produkt veröffentlichten OpenAPI-Dokuments.

### Laufzeitprotokoll v1

Das Manifest deklariert zunächst `protocol_version = 1` und besitzt eine
Tabelle `[runtime]` mit diesen Feldern:

- `command`: Argumentliste des zu startenden Prozesses,
- `working_directory`: relativ zum Produktverzeichnis,
- `openapi_path`: HTTP-Pfad des OpenAPI-Dokuments,
- `ready_timeout_seconds`: optionale Startfrist,
- `environment`: Zuordnung von Umgebungsvariablen zu Werten.

In Argumenten und Umgebungswerten ersetzt der Runner `{product_root}`, `{host}`
und `{port}`. Vertragstests können weitere explizit benötigte Werte bereitstellen;
der SQLite-Test stellt beispielsweise `{database_path}` bereit. Das Manifest der
Referenzimplementierung entscheidet selbst, wie diese Werte an ihre Technologie
weitergegeben werden. Sein `uv`-/Python-Befehl ist keine Produktanforderung.

Das Produkt muss auf der übergebenen Adresse lauschen. Ein nicht authentifizierter
GET auf `openapi_path` signalisiert mit Status `200` die Bereitschaft und liefert
ein gebündeltes OpenAPI-3.1-Dokument als JSON. Referenzen innerhalb dieses
Dokuments sind lokal; der Vergleich versteht direkte Schemas und lokale `$ref`.
Externe Referenzen und Schema-Komposition unterstützt der Prototyp noch nicht.
Wenn die Spec eine SQLite-Tabelle verlangt, bezeichnet
`{database_path}` die tatsächlich verwendete dateibasierte Datenbank und ihr
Schema ist beim Bereitschaftssignal initialisiert.

### Decision Protocol v1

Ein Decision Product wird weder als HTTP-Service noch als RDF-System
vorausgesetzt. Sein `product.toml` deklariert
`decision_protocol_version = 1` und eine Tabelle `[decision]` mit:

- `command`: Argumentliste des zu startenden Decision-Product-Prozesses,
- `working_directory`: relativ zum Product Bundle,
- `timeout_seconds`: optionale Ausführungsfrist,
- `environment`: optionale Umgebungsvariablen.

Der Harness ersetzt `{product_root}`, schreibt genau einen UTF-8-kodierten JSON
**Decision Request** auf die Standardeingabe und erwartet genau ein JSON-Objekt
als **Decision Result** auf der Standardausgabe. Exitstatus, Standardfehler,
Timeout und Prozessbaum-Cleanup sind beobachtbare Protokolleigenschaften.
Python, ein bestimmtes CLI-Framework, RDF, HTTP und die interne Auswertung des
kompilierten Vertrags sind keine Produktanforderungen.

Der Request benennt den Decision Contract, die Rule Set Version und das
Decision Date explizit und trägt die Case Facts an den kompilierten JSON
Pointers. Das Result benennt Outcome, Condition Evaluations, decisive Rules,
Fact Gaps, höchstens eine Next Question, Provenance, menschliche Explanation
und den unveränderten Scope Note. Ein Client ergänzt eine Antwort am
ausgegebenen JSON Pointer und sendet den vollständigen akkumulierten Case in
einem neuen Protokollaufruf. Protokoll und fachlicher Decision Contract bleiben
getrennt versionierbar; Decision Protocol v1 schreibt weder Session State noch
eine Benutzeroberfläche vor.

### Compiler Protocol v1

Ein Compilerprodukt wird nicht künstlich als HTTP-Laufzeit modelliert. Sein
`product.toml` deklariert stattdessen `compiler_protocol_version = 1` und eine
Tabelle `[compiler]` mit:

- `command`: Argumentliste des Compilerprozesses,
- `working_directory`: relativ zum Self-Description Bundle,
- `timeout_seconds`: optionale Ausführungsfrist,
- `environment`: optionale Umgebungsvariablen.

In diesen Werten ersetzt der Harness `{compiler_root}`, `{repository_root}` und
`{input_product_root}`. Er importiert keine Implementierungsmodule, sondern
beobachtet ausschließlich Exitstatus, zusammengeführte Standardausgabe und die
im Input Product Bundle erzeugten Dateien.

Das Produkt ist allgemein als `schema:SoftwareApplication` klassifiziert.
`dcterms:conformsTo sco:CompilerProtocolV1` wählt das ausführbare Protokoll;
`sco:implementsContract` verweist auf einen separat versionierbaren
`sco:TransformationContract`. Dieser benennt ein oder mehrere
`sco:CompilerConformanceFixture`-Ressourcen mit Product Bundle und jeweils
erwarteten Ausgabepfaden oder Glob-Mustern sowie die Suche nach Eingabespecs,
Fehlerfälle und die Ergebnisgleichheit. Beim
Determinismusnachweis werden zwei Läufe derselben Compilerimplementierung mit
demselben Input verglichen. Das ist ein Fixpunkt- und Reproduzierbarkeitsnachweis,
aber kein unabhängiger Beweis für die korrekte Interpretation der Spec.

Ein optionaler `sco:BootstrapProcess` beschreibt getrennt davon, wie eine
zukünftige Compilerimplementierung abgeleitet werden soll. Er verweist über
`sco:seedImplementation` auf eine explizite Ausgangsimplementierung und über
`sco:evolutionStrategy` auf die Ableitungsstrategie. Für den Spec Compiler ist
G0 der Seed und `sco:ModifyExistingImplementation` die Strategie. Diese
Provenienz wird validiert und in den Work Graph übernommen. Für
`sco:ModifyExistingImplementation` materialisiert G0 seinen Quellstand am durch
`sco:generatesImplementationArtifact` deklarierten Ziel und erhöht den
eindeutigen Generationsmarker. Sprache und Bibliotheken von G0 werden dadurch
in G1 weiterverwendet, sind jedoch nicht Teil des Transformationsvertrags. G1
besitzt ein eigenes Manifest, Projektmetadaten und Lockfile und wird anschließend
als Black box ausgeführt.

## Compilerkonventionen v1

Der Prototyp verwendet folgende explizite Abbildungsregeln:

- `sco:GetEndpoint` wird als HTTP `GET` interpretiert.
- Der lokale Name eines `sh:path` wird als JSON-Feld und SQL-Spalte verwendet.
  Er muss deshalb ein sicherer SQL-Bezeichner sein.
- `xsd:string` wird zu OpenAPI `string` und SQL `TEXT`.
- `xsd:decimal` wird zu OpenAPI `number` und SQL `DECIMAL`.
- `xsd:integer` wird zu OpenAPI `integer` und SQL `INTEGER`.
- `sh:minCount 1` wird zu einem erforderlichen JSON-Feld und `NOT NULL`.
- `sh:minCount 0` wird zu einem optionalen JSON-Feld und einer nullable Spalte.
- Nur skalare Properties mit `sh:maxCount 1` und `sh:minCount 0` oder `1`
  werden unterstützt.
- `dcterms:conformsTo sco:CompilerProtocolV1` wählt das Compilerprodukt-Profil
  statt des HTTP-/SQLite-Profils; eine fachliche Produktklasse steuert niemals
  die ausführbare Testsemantik.
- `sco:implementsContract` muss auf genau einen `sco:TransformationContract`
  zeigen, aus dem die generierten Verpflichtungen stammen.
- Die Aussagen `sco:conformanceFixture`, `sco:fixtureProduct`,
  `sco:expectsArtifact`, `sco:rejectsMissingSpecs` und
  `sco:deterministicOutput` werden direkt in fokussierte Black-box-Proofs für
  jedes deklarierte Compilerprofil übersetzt.
- Ein deklarierter Bootstrap-Prozess muss genau einen als
  `schema:SoftwareApplication` typisierten Seed und die unterstützte Strategie
  `sco:ModifyExistingImplementation` sowie einen sicheren relativen Pfad über
  `sco:generatesImplementationArtifact` nennen. Compiler Conventions v1
  materialisiert dort den Seed-Quellstand mit um eins erhöhtem, eindeutigem
  Generationsmarker. Der generierte Beweis startet den resultierenden Compiler
  über dessen eigenes Compiler-Protocol-Manifest.
- `sh:minLength`, `sh:minExclusive` und `sh:maxExclusive` werden gleichnamig
  beziehungsweise semantisch äquivalent in JSON Schema/OpenAPI abgebildet.

Andere Datentypen, Kardinalitäten, Engines oder unsichere Bezeichner werden
nicht geraten, sondern als nicht unterstützte Eingabe abgelehnt.

## Decision Conventions v1

Der erste Decision-Schnitt unterstützt ausschließlich einen expliziten
`sdo:DecisionContract` mit genau einer gepinnten `sdo:RuleSetVersion` und
`sdo:requiresAllRules true`:

- Jede Rule verweist auf genau eine Condition, ein eindeutiges
  `sco:inputJsonPointer`, einen booleschen Sollwert und genau eine Source
  Citation.
- Eine Condition ist `satisfied`, wenn ein boolescher Case Fact ihrem Sollwert
  entspricht, `violated`, wenn er ihm widerspricht, und `unknown`, wenn der Fact
  fehlt. Nicht-boolesche oder widersprüchliche Facts sind Fehler.
- Mindestens eine verletzte Condition ergibt `ineligible`. Gibt es keine
  verletzte, aber mindestens eine unbekannte Condition, ergibt sich `unknown`.
  Nur wenn alle Conditions erfüllt sind, ergibt sich `eligible`.
- Bei `ineligible` sind alle verletzten Rules entscheidend, bei `unknown` alle
  Rules mit Fact Gap und bei `eligible` alle Rules.
- Jede entscheidende Rule wird zusammen mit Source Citation, Source Revision,
  Locator und autorisierter Source Statement ausgegeben.
- Source Revision, Rule Set Version, `validFrom`, Outcome-IRIs und sichere,
  eindeutige Outcome Codes müssen in der Spec stehen. Der Compiler ergänzt
  weder eine neueste Version noch ein heutiges Datum.
- Autorisierte Conformance Cases müssen `eligible`, `ineligible` und `unknown`
  abdecken. Ihr erwartetes Resultat muss aus denselben Regeln folgen; andernfalls
  ist die Spec widersprüchlich und wird abgelehnt.

Der Compiler erzeugt aus diesem Modell `generated/decision-contract.json`,
Black-box-Tests, Work Graph und Issue-Texte. Die erste Konvention umfasst keine
automatische Quellenaufnahme, Disjunktionen, numerische Regeln, mehrere
anwendbare Versionen oder Obligationsaktivierung.

## Question Selection Conventions v1

Für jeden im Decision Contract verwendeten Rule-Condition-Pfad muss die Spec
genau eine **Fact Question** mit explizitem Fragetext und einer innerhalb des
Contracts eindeutigen positiven Priorität enthalten. Der Compiler leitet weder
Fragetext aus Labels ab noch verwendet er RDF-, Datei- oder Rule-Reihenfolge als
verdeckte Priorität.

Eine **Next Question** wird nur für ein nach Decision Conventions v1 noch
`unknown`es Decision Result erzeugt. Kandidaten sind ausschließlich Fact
Questions, deren Conditions im aktuellen Result als Fact Gaps ausgewiesen sind.
Unter ihnen wird deterministisch die kleinste numerische Priorität gewählt.
Sobald mindestens eine Condition verletzt und das Result damit `ineligible`
ist oder alle Conditions erfüllt und es `eligible` ist, enthält das Result
keine Next Question. Damit ist jede ausgegebene Antwort geeignet, den aktuellen
Entscheidungszustand entweder unmittelbar zu bestimmen oder zur nächsten
verbleibenden Lücke fortzuschreiben.

Die Next Question enthält ihre Identität, den autorisierten Fragetext,
Condition, Fact Property, Input JSON Pointer und das im aktuellen Profil
boolesche Antwortschema. Ihre Begründung nennt Rule, Source Citation, Source
Revision, Locator und autorisierte Source Statement. Diese Provenienz folgt aus
der expliziten Rule-Condition-Citation-Kette; Auswahl und Rangfolge folgen aus
Question Selection Conventions v1.

Genau ein **Question Flow Case** pro Decision Contract liefert einen
vollständigen positiven Satz autorisierter Antworten. Der generierte
Black-box-Test beginnt ohne Facts, ruft dasselbe Decision Product wiederholt
über Decision Protocol v1 auf, trägt jede Antwort am ausgegebenen JSON Pointer
ein und verlangt nach jedem Schritt entweder die nächste begründete Frage oder
ein determiniertes Result. Die Konvention umfasst keinen Session State, keine
UI, keine Kosten- oder Informationsgewinnoptimierung und keine nicht-booleschen
Antwortschemas.

## Evidence Evaluation Conventions v1

Eine **Evidence Requirement** ist von der durch sie gestützten Condition
getrennt. Sie nennt ausdrücklich die gestützte Rule Condition, mindestens eine
eigene Applicability Condition, den erforderlichen Evidence Type und eine
eigene Source Citation. Provenienz wird nicht von der Rule geerbt.

Alle Applicability Conditions müssen `satisfied` sein, damit die Evidence
Requirement auf den gelieferten Case anwendbar ist. Andernfalls lautet ihr
Status `not_applicable`; die einzelnen Zustände `violated` beziehungsweise
`unknown` bleiben im Result sichtbar, sodass ein fehlender Fact weiterhin
nicht als `false` gilt. Ist die Requirement anwendbar, lautet ihr Status nur
dann `fulfilled`, wenn mindestens eine gelieferte Evidence den erforderlichen
Typ besitzt und eine explizite akzeptierte Evidence Assessment für genau diese
Requirement trägt. Andernfalls lautet er `missing`.

Für jede Evidence Requirement klassifiziert das Result jede gelieferte
Evidence als `accepted`, `rejected`, `unassessed` oder `not_relevant`. Diese
Auswertung ändert weder Rule Condition Evaluations noch den Decision Outcome.
Jede Requirement Evaluation enthält ihre eigene Source Citation, Source
Revision, Locator, Source Statement und Explanation.

Sobald ein Decision Contract Evidence Requirements enthält, müssen autorisierte
Conformance Cases für jede von ihnen einen erwarteten Status angeben und
zusammen `fulfilled`, `missing` sowie `not_applicable` abdecken. Die Konvention beschreibt ausschließlich semantische
Evidence-Identität, -Typen und -Assessments im vorhandenen JSON-Austausch. Sie
schreibt kein Dateiformat, keinen Dokumentinhalt, Upload, Speicherort, UI oder
Verfahren zur Echtheitsprüfung vor.

## OpenAPI und Verhalten

Der Generator erzeugt aus derselben Zwischenrepräsentation eine erwartete
OpenAPI-Spezifikation und die Verhaltenstests. Innerhalb des oben beschriebenen
OpenAPI-3.1-Profils ist der Vergleich semantisch: Geforderte Pfade, Parameter,
Responses, Medientypen und Schemas müssen vorhanden und kompatibel sein. Titel,
Beschreibungen, Komponenten-Namen und zusätzliche Fehlerantworten dürfen
implementationsabhängig bleiben. `info.title`, `info.version` und Response-
Beschreibungen im erwarteten Dokument sind nur notwendige OpenAPI-Trägerdaten;
der Vergleich behandelt sie nicht als Produktanforderungen.

Vor diesem Vergleich validiert `openapi-spec-validator` das vollständige
Dokument gegen OpenAPI 3.1. Die Validierung ist Teil des Test-Harness und stellt
keine Abhängigkeit der Produktimplementierung dar.

OpenAPI ersetzt keine Verhaltenstests. Ein echtes HTTP-Szenario prüft weiterhin,
dass ein gespeicherter Datensatz korrekt ausgeliefert wird und alle expliziten
Shape-Verpflichtungen erfüllt. Der generierte Test validiert die JSON-Antwort
direkt aus dem Explicit Obligation Model. Er konvertiert JSON nicht in einen
künstlichen RDF-Graphen und benötigt deshalb kein pySHACL. SHACL bleibt das
aktuelle RDF-Eingabeprofil; Produkte müssen SHACL oder RDF nicht verwenden.

Bei offenen Shapes werden nur Felder mit `sh:minCount 1` verlangt und
zusätzliche Felder akzeptiert. Erst ein explizites `sh:closed true` verbietet
nicht spezifizierte Felder.

## Prüffrage für neue Generatorregeln

Vor jeder neuen Assertion ist zu beantworten:

> Aus welchem Spec-Element oder welcher benannten Konvention folgt diese
> Anforderung?

Gibt es darauf keine eindeutige Antwort, gehört die Assertion nicht in den
Generator.

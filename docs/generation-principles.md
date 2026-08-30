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
starten das Produkt als separaten Prozess und beobachten ausschließlich die
explizit vereinbarten Grenzen HTTP, OpenAPI und SQLite. Sie importieren keinen
Produktcode.

## Quellen der aktuellen Anforderungen

Das öffentliche Vokabular liegt autoritativ in
`ontology/shacl-contract.ttl`. Eigene Vertragsbegriffe verwenden den Namespace
`https://arturmiller.github.io/spec-compiler/ontology/#`. Konkrete Toolchain- und
SQL-API-Ressourcen liegen in getrennten `resources/toolchain/#`- beziehungsweise
`resources/sql-api/#`-Namespaces. Eine Produkt-Spec darf einen öffentlichen
Vokabularbegriff verwenden, ohne ihn neu zu definieren; der Publikationsvalidator
verlangt dafür eine Definition und ein Label in der kanonischen Ontologie.

WIDOCO-HTML, WebVOWL-Daten und publizierte Beispielkopien sind abgeleitete
Dokumentationsartefakte. Sie begründen keine Produktanforderungen und werden
nicht als deterministische Vertragsartefakte behandelt.

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
`sco:TransformationContract`. Dieser darf Ausgabepfade oder Glob-Muster, die
Suche nach Eingabespecs, Fehlerfälle und die jeweilige Ergebnisgleichheit
explizit festlegen. Beim
Determinismusnachweis werden zwei Läufe derselben Compilerimplementierung mit
demselben Input verglichen. Das ist ein Fixpunkt- und Reproduzierbarkeitsnachweis,
aber kein unabhängiger Beweis für die korrekte Interpretation der Spec.

Ein optionaler `sco:BootstrapProcess` beschreibt getrennt davon, wie eine
zukünftige Compilerimplementierung abgeleitet werden soll. Er verweist über
`sco:seedImplementation` auf eine explizite Ausgangsimplementierung und über
`sco:evolutionStrategy` auf die Ableitungsstrategie. Für den Spec Compiler ist
G0 der Seed und `sco:ModifyExistingImplementation` die Strategie. Diese
Provenienz wird validiert und in den Work Graph übernommen, erzeugt aber keine
Produktverpflichtung: Sprache und Bibliotheken von G0 werden dadurch
wahrscheinlich weiterverwendet, sind jedoch nicht Teil des
Transformationsvertrags. Der Prototyp führt noch keine Codeerzeugung aus.

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
- Die Aussagen `sco:generatesArtifact`, `sco:rejectsMissingSpecs` und
  `sco:deterministicOutput` werden direkt in fokussierte Black-box-Proofs
  übersetzt.
- Ein deklarierter Bootstrap-Prozess muss genau einen als
  `schema:SoftwareApplication` typisierten Seed und die unterstützte Strategie
  `sco:ModifyExistingImplementation` nennen. Er ist Provenienz, keine
  Black-box-Verpflichtung des Compilerprodukts.
- `sh:minLength`, `sh:minExclusive` und `sh:maxExclusive` werden gleichnamig
  beziehungsweise semantisch äquivalent in JSON Schema/OpenAPI abgebildet.

Andere Datentypen, Kardinalitäten, Engines oder unsichere Bezeichner werden
nicht geraten, sondern als nicht unterstützte Eingabe abgelehnt.

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
dass ein gespeicherter Datensatz korrekt ausgeliefert wird und der SHACL-Shape
entspricht.

## Prüffrage für neue Generatorregeln

Vor jeder neuen Assertion ist zu beantworten:

> Aus welchem Spec-Element oder welcher benannten Konvention folgt diese
> Anforderung?

Gibt es darauf keine eindeutige Antwort, gehört die Assertion nicht in den
Generator.

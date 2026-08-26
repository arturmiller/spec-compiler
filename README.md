# SHACL contract prototype

Dieses kleine Beispiel beantwortet eine konkrete Frage: Kann ein RDF-Vertrag
ein Artikelobjekt mit einem GET-Endpunkt und einer SQLite-Tabelle verbinden und
daraus Python-Tests erzeugen?

## Ausführen

```console
uv run --extra dev poe run
```

Der Befehl funktioniert unter Windows, Linux und macOS. Einzelne Schritte sind
mit `uv run --extra dev poe generate` und `uv run --extra dev poe test`
verfügbar.

Das Projekt ist nach Verantwortlichkeiten getrennt:

- `tools/`: Generator für die Vertragstests.
- `products/`: Ablage für KI-generierte Produkte; standardmäßig von Git ignoriert.
- `products/sql_api_example/`: versioniertes Referenzprodukt mit Produktcode,
  `specs/`, deterministisch erzeugten `tests/` und `generated/`-Arbeitsaufträgen.

`tools/generate.py` leitet reproduzierbare Werte aus den SHACL-Grenzen ab. Für
den aktuellen Vertrag entstehen immer `description="x"` und `price=0.01`.
Danach prüft der generierte Test SQLite-Schema, GET-Endpunkt und die
SHACL-Konformität der Antwort.

Der Generator kompiliert denselben Vertrag außerdem in einen Work Graph. Jeder
Arbeitsauftrag enthält Ziel, Verpflichtungen, Abhängigkeiten, Abgrenzung und den
exakten generierten Pytest-Node, der seinen Abschluss nachweist. Die Texte
entstehen aus festen Vorlagen; ein Sprachmodell ist nur für Änderungen am
jeweiligen Produkt vorgesehen. Git ignoriert neue Einträge unter `products/`;
nur `sql_api_example` wird als nachvollziehbares Beispiel eingecheckt.

Damit sind Werkzeug und Ergebnisse klar getrennt: `tools/` enthält die
Transformation von Specs zu Tests, Arbeitsaufträgen und Produktcode;
`products/<name>/` enthält jeweils sämtliche Ein- und Ausgaben eines Produkts.

`sh:*` ist standardisiertes SHACL. Nur `ex:returns` und `ex:stores` sind eigene
Verknüpfungen. Der lokale Name von `sh:path` wird gleichermaßen als JSON-Feld
und SQL-Spalte verwendet: `ex:price` wird zu `price`. Der SQL-Typ wird aus dem
XSD-Datentyp abgeleitet.

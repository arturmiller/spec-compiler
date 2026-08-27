# Prototype notes

Frage: Kann ein kleiner RDF/SHACL-Vertrag gleichzeitig ein Datenobjekt, den
Rückgabewert eines GET-Endpunkts und dessen Speicherung in SQLite beschreiben
und daraus implementationsneutrale OpenAPI- und Black-Box-Nachweise erzeugen?

Status: Prototype – nach Beantwortung der Frage löschen oder die Konventionen
(`ex:returns`, `ex:stores` und die Ableitung gleicher Feldnamen aus `sh:path`)
in ein echtes Vertragsformat überführen. Dabei gilt die Regel: Anforderungen
müssen aus einer Spec-Aussage oder einer benannten Compilerkonvention folgen;
der Generator darf keine Implementierungstechnologie dazudichten.

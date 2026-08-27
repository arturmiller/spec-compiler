# SQL API example

Dieses Referenzprodukt erfüllt den Vertrag in `specs/` mit Python, FastAPI und
Uvicorn. Diese Technologien sind Entscheidungen des Beispiels und keine
Anforderungen des Vertrags oder des Generators.

`product.toml` beschreibt ausschließlich, wie das Werkzeug diese konkrete
Implementierung als separaten Prozess startet. Die generierten Tests importieren
`app.py` nicht.

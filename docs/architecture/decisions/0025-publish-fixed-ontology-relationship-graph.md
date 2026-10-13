# ADR 0025: Publish a fixed Ontology Relationship Graph on GitHub Pages

## Status

Accepted. Supersedes the primary WebVOWL visualization choice in
[ADR 0007](0007-publish-experimental-ontology-with-github-pages.md) and
[ADR 0011](0011-publish-separate-example-webvowl-graph.md). The SQL example
projection and its Shape chain from ADRs 0013–0015 remain documentation inputs.

## Context

WebVOWL moves nodes through a force layout and gives readers limited control
over dense relationships. A comparison prototype showed that a fixed
relationship graph with named, directed edges, search, a direct-neighborhood
highlight, and manual zoom makes the four vocabularies easier to explore. The
viewer must not pan or zoom when a node is selected. Published HTML references,
RDF serializations, and example specs remain useful independently of the graph.

## Decision

- Publish an **Ontology Relationship Graph** at `/graph/` as the primary graph
  entry from the site landing page, each vocabulary reference index, and the
  SQL API resource page.
- Build five separate datasets from the four canonical authored ontologies and
  the existing derived SQL API visualization graph. Keep authored IRIs and the
  SQL API endpoint–Shape–class chain. The viewer does not feed the compiler.
- Include declared OWL classes, named Object Properties whose domain and range
  are displayed classes, internal subclass relations, and a searchable catalogue
  of declared Object and Datatype Properties. A source link leads to the Turtle
  vocabulary or example specs for constraints and other RDF statements.
- Sort nodes and edges before Graphviz `dot` computes coordinates during the
  documentation build. Give Cytoscape.js only those preset coordinates and
  disallow node dragging. Selection and filtering change emphasis without
  moving the viewport; plus, minus, mouse wheel, and an explicit fit button
  control zoom and framing.
- Self-host Cytoscape.js 3.34.3 in the Pages artifact after verifying its
  SHA-256. Graphviz is a documentation-build dependency in CI. Keep WIDOCO's
  bilingual references and generated WebVOWL files available at their existing
  URLs as legacy documentation.

## Consequences

- GitHub Pages has one stable, shareable graph route with vocabulary, selected
  term, relation filter, and neighborhood state in its URL. The site can render
  without a runtime service or a browser CDN request.
- Graphviz and Cytoscape.js are documentation dependencies only. Coordinates
  are fixed within each built artifact; Graphviz version changes may change
  them across builds, while product contract determinism is unaffected.
- Only explicitly selected OWL/RDFS relations appear as graph edges. Complete
  SHACL constraints and example instance statements remain in linked sources.
- Existing WebVOWL URLs and WIDOCO output validation continue to work, but the
  new graph is the primary navigation path.

## Alternatives considered

- Keep WebVOWL as the primary graph. Its moving layout does not provide the
  fixed spatial reference selected in the comparison.
- Move the site to a React graph SDK. The publication is static HTML and needs
  neither a React application build nor a commercial graph dependency for this
  graph size and interaction set.
- Replace WIDOCO entirely. Its bilingual reference and RDF serialization still
  serve distinct documentation needs.

# ADR 0011: Publish a separate WebVOWL graph for the SQL API example

## Status

Accepted. Refines the example-publication decision in
[ADR 0007](0007-publish-experimental-ontology-with-github-pages.md).

## Context

The canonical WebVOWL input contains only the public SHACL Contract Ontology.
Consequently, readers cannot find the domain class `article:Article`, because
it belongs to the SQL API Product Bundle rather than the reusable vocabulary.

Merging all product specs into the canonical ontology graph would blur the
boundary between vocabulary definitions and example resources. WebVOWL also
focuses on OWL/RDFS structure and does not faithfully visualize complete SHACL
constraints.

## Decision

- Keep `ontology/shacl-contract.ttl` as the sole input to the canonical
  `/ontology/webvowl/` graph.
- Explicitly declare `article:Article` as `owl:Class` and
  `article:description` and `article:price` as `owl:DatatypeProperty`, with
  domains, ranges, and German and English labels.
- Build a second visualization ontology from the merged SQL API example specs
  and publish it under `/examples/sql-api/webvowl/`.
- Link the example graph from the site landing page and SQL API resource page.
- Validate the presence of entity search and the three core article terms in
  the generated WebVOWL JSON.
- Continue publishing the original Turtle specs as the authoritative source for
  SHACL constraints.

## Consequences

- Readers can search for and explore Article, description, and price without
  polluting the canonical vocabulary graph with product-specific resources.
- The example obtains its own bilingual WIDOCO reference and RDF
  serializations in addition to WebVOWL.
- The generated visualization graph contains the complete merged example RDF,
  but WebVOWL exposes primarily its OWL/RDFS subset; SHACL cardinalities and
  numeric bounds remain best inspected in Turtle.
- Each additional product visualization will require an explicit publication
  configuration and core-term validation.

## Alternatives considered

- Merge the SQL API specs into the canonical ontology. Rejected because it
  conflates reusable vocabulary and one product model.
- Visualize only the SHACL graph with WebVOWL. Rejected because WebVOWL does not
  provide a complete SHACL constraint view.
- Leave Article available only in downloadable Turtle. Rejected because it
  does not satisfy interactive discovery and search.

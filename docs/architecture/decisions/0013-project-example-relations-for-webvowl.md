# ADR 0013: Project example relations for WebVOWL

## Status

Accepted. Refines [ADR 0011](0011-publish-separate-example-webvowl-graph.md).

## Context

The SQL API specs model `GetArticleEndpoint` and `ArticlesTable` as instances
and connect them to `ArticleShape`. The shape targets the OWL class `Article`.
This is appropriate for the executable contract, but WebVOWL primarily renders
OWL class and property structure. It therefore showed `Article` without the
endpoint, table, or their connecting relations.

## Decision

- Keep the authored RDF/SHACL specs unchanged and authoritative.
- During documentation generation, treat the concrete endpoint and table as
  OWL classes in the derived SQL API visualization graph.
- Resolve `sco:returns` and `sco:stores` through the shape's single
  `sh:targetClass` and emit visualization-only OWL Object Properties for
  `returns`, `reads from`, and `stores`.
- Give each concrete edge its own property IRI, domain, and range so adding a
  second endpoint cannot accidentally create intersecting RDFS domains.
- Fail the documentation build if the expected projected terms are absent from
  the generated WebVOWL data.
- Never use the projection as compiler input or requirement provenance.

## Consequences

- WebVOWL connects `GetArticleEndpoint`, `ArticlesTable`, and `Article` while
  preserving the semantics of the executable specs.
- The same resource IRIs appear as instances in the source graph and classes in
  the derived graph (OWL punning). This is limited to disposable documentation.
- A shape used by a projected relation must have exactly one `sh:targetClass`;
  ambiguity stops publication instead of inventing a target.

## Alternatives considered

- Change the product specs so endpoints and tables are OWL classes. Rejected
  because visualization needs should not distort the executable domain model.
- Teach WebVOWL to render SHACL and arbitrary instance edges. Rejected because
  it would require maintaining a custom WebVOWL fork.
- Show only `Article`. Rejected because it hides the product relationships the
  example is intended to explain.

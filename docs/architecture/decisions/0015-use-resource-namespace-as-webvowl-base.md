# ADR 0015: Use the resource namespace as the WebVOWL base

## Status

Accepted. Refines
[ADR 0014](0014-preserve-node-shapes-in-webvowl-projection.md).

## Context

WebVOWL decides whether an element is external by comparing its namespace with
the documented ontology IRI. The derived graph used
`resources/sql-api/visualization/` as that IRI while the authored example nodes
use `resources/sql-api/#`. Consequently, WebVOWL marked `Article`,
`ArticleShape`, `GetArticleEndpoint`, and `ArticlesTable` as external even
though they are the graph's primary subject.

## Decision

- Use `resources/sql-api/` as the ontology IRI and WebVOWL base of the derived
  SQL API graph.
- Preserve all authored example IRIs unchanged.
- Keep generated Object Properties under
  `resources/sql-api/visualization/#` so their derived status remains explicit.
- Fail the site build if any of the four projected example classes is marked
  `external` in WebVOWL's JSON.

## Consequences

- The four example nodes appear as internal WebVOWL classes without changing
  their identity.
- Visualization-only properties remain distinguishable by namespace.
- The temporary OWL ontology declaration shares the dereferenceable SQL API
  resource base; it remains documentation metadata and is not compiler input.

## Alternatives considered

- Mint duplicate visualization IRIs for every node. Rejected because searches
  and links would no longer use the authored resource identities.
- Patch WebVOWL's generated JSON or JavaScript. Rejected because it would be a
  brittle presentation-layer modification.
- Accept the `external` labels. Rejected because they miscommunicate the role of
  the example's central nodes.

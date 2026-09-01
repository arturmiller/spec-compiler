# ADR 0014: Preserve Node Shapes in the WebVOWL projection

## Status

Accepted. Refines [ADR 0013](0013-project-example-relations-for-webvowl.md).

## Context

The first OWL projection resolved `sco:returns` and `sco:stores` through
`sh:targetClass` directly to `Article`. Although the resulting endpoints,
tables, and domain classes were connected, WebVOWL still omitted
`ArticleShape`. Readers therefore could not see where the SHACL validation
boundary sits in the authored model.

## Decision

- Preserve a referenced Node Shape as an OWL class in the derived visualization
  graph.
- Project `returns` and `stores` to that Shape rather than directly to its
  target class.
- Add a visualization-only `target class` Object Property from the Shape to its
  single `sh:targetClass`.
- Continue treating the authored RDF/SHACL specs as the only authoritative
  source.

## Consequences

- WebVOWL displays the chain from endpoint and table through `ArticleShape` to
  `Article`.
- The graph distinguishes the validation description from the domain class it
  targets.
- The derived graph uses OWL punning for the Shape solely to accommodate
  WebVOWL; this does not change the Shape's authored SHACL meaning.

## Alternatives considered

- Keep the direct edges and add a disconnected Shape. Rejected because it does
  not explain the Shape's role.
- Keep both direct and Shape-mediated edges. Rejected because the redundant
  paths make the small example unnecessarily ambiguous.

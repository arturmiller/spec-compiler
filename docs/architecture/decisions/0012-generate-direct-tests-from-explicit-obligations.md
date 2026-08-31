# ADR 0012: Generate direct tests from explicit obligations

## Status

Accepted. Refines the shared intermediate-model decision in
[ADR 0004](0004-common-contract-model-and-work-graph.md).

## Context

The HTTP behavior test converted a JSON response into an artificial RDF graph
and then invoked pySHACL with the authored specs. The conversion itself encoded
JSON-to-RDF semantics and duplicated constraints already normalized by the
compiler for OpenAPI, SQL, fixtures, and tests.

The product-generation model deliberately follows an open-world principle:
explicit statements constrain an implementation, while unspecified choices
remain available to a coding agent. The internal representation should make
that boundary visible and generated tests should exercise the real product
interface directly.

## Decision

- Name the normalized shared representation **Explicit Obligation Model**.
- Keep SHACL as the current RDF input profile for datatypes, cardinalities,
  bounds, string lengths, and explicit closure.
- Generate direct JSON assertions for required fields, supported datatypes,
  declared bounds, and stored values.
- Permit optional fields to be absent and additional fields to exist unless the
  Shape explicitly declares `sh:closed true`.
- Generate negative harness tests showing that each declared constraint rejects
  a representative invalid payload.
- Remove JSON-to-RDF conversion and pySHACL from generated product tests and
  from development dependencies.
- Keep product tests black-box: products do not import or depend on RDF, SHACL,
  or the compiler implementation.

## Consequences

- Test behavior follows only normalized, traceable obligations and makes the
  open/closed boundary explicit.
- SHACL remains useful and interoperable as an authoring language without
  becoming a product-runtime dependency.
- The harness no longer risks validating a mistaken RDF interpretation instead
  of the actual JSON response.
- pySHACL may be reintroduced later as a compiler-frontend conformance oracle or
  for a product whose observable interface is genuinely RDF, but it is not part
  of the current product verification path.
- The untyped dictionary remains technical debt; the new name clarifies its
  invariant before a future typed representation is introduced.

## Alternatives considered

- Continue validating reconstructed RDF with pySHACL. Rejected because the
  reconstructed graph is not the observable product interface.
- Generate Pydantic models. Rejected because the product should receive tests,
  not a Python implementation constraint or generated application model.
- Replace SHACL with a custom constraint vocabulary. Rejected because the
  supported SHACL subset already expresses the required authoring semantics.

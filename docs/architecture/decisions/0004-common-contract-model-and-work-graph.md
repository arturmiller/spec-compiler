# ADR 0004: Derive all outputs from one Contract Model

## Status

Accepted.

## Context

Generating tests, OpenAPI, and issue prose through separate interpretations of
the RDF specs would allow the outputs to disagree. Passing one monolithic test
suite to a stochastic coding agent also provides little guidance about ordering,
scope, and completion.

## Decision

The Contract Compiler CLI parses and validates the RDF graph once into a common
Contract Model. Deterministic renderers derive from that model:

- valid fixture values,
- expected OpenAPI,
- black-box contract tests,
- a versioned Work Graph,
- natural-language issue Markdown.

The Work Graph decomposes implementation into dependency-ordered Work Items.
Every node contains a goal, obligations, sources, exclusions, dependencies, and
one exact pytest node as its completion proof.

## Consequences

- Tests and work guidance share normalized contract facts.
- Identical input and compiler version can produce byte-identical artifacts.
- Issue prose needs no stochastic generation.
- A defect in the common interpretation can affect all outputs, so independent
  examples, mutation tests, and architecture review remain important.
- The current dictionary-based Contract Model will need a typed representation
  before the supported language grows substantially.

## Alternatives considered

- Generate Issues from completed test source. Rejected because an agent or
  renderer would need to reinterpret executable code.
- Let an LLM write Issues directly from specs. Rejected because wording and
  decomposition would be stochastic and could add or omit requirements.
- Give the coding agent the full suite as one task. Rejected because it provides
  no deterministic work ordering or focused completion proof.

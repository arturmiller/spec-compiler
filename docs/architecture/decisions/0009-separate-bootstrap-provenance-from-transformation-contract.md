# ADR 0009: Separate bootstrap provenance from the transformation contract

## Status

Accepted.

## Context

The Spec Compiler should eventually use its own specification to guide the
creation of a successor implementation G1. Starting from the checked-in G0 code
makes continued use of Python and its current libraries likely. Those choices
must not accidentally become product requirements: another implementation may
use different technology while satisfying the same Transformation Contract.

The current prototype generates contracts, tests, and work guidance. It does
not yet invoke a coding agent or synthesize an independently executable G1.

## Decision

- Model derivation provenance as a separate `sco:BootstrapProcess`.
- Link the process to its product with `sco:bootstrapsProduct`, to its explicit
  starting point with `sco:seedImplementation`, and to an
  `sco:evolutionStrategy`.
- Declare `tool:SpecCompilerG0` as the current seed and
  `sco:ModifyExistingImplementation` as the supported strategy.
- Validate this provenance while reading the compiler profile and emit it as
  metadata in the generated Work Graph.
- Do not translate bootstrap provenance into a black-box product assertion.
  The Transformation Contract remains the sole source of observable compiler
  obligations.
- Do not claim G1 code generation until a separate synthesis interaction
  consumes the seed and produces a candidate implementation.

## Consequences

- The expected continuity from G0 to G1 is explicit and machine-readable.
- Python remains a likely consequence of modifying G0, not a required property
  of a conforming Spec Compiler.
- Generated Work Graph consumers can distinguish implementation provenance from
  executable product obligations.
- A future synthesis component has an explicit seed and strategy to consume,
  but that component is outside the current system behavior.

## Alternatives considered

- Put the language and libraries into the Transformation Contract. Rejected
  because it would prevent technology-independent implementations.
- Leave use of G0 implicit in the repository layout. Rejected because generated
  successors would have unrecorded provenance.
- Generate a test that merely asserts the bootstrap triples. Rejected because
  it would present metadata as observed product behavior and provide false
  confidence about code synthesis.

# ADR 0010: Materialize and execute a bootstrap generation

## Status

Accepted. Supersedes the deferred-synthesis statement in
[ADR 0009](0009-separate-bootstrap-provenance-from-transformation-contract.md).

## Context

The Bootstrap Process identified G0 and the modify-existing strategy but did
not produce a new compiler implementation. Generated compiler tests still
invoked `tools/generate.py`, so the purported G1 was only another process
running G0.

A useful bootstrap step must create a separately addressable implementation and
execute it without importing or invoking the G0 source path. The result need not
be source-identical or technology-independent from its seed.

## Decision

- Add `sco:generatesImplementationArtifact` to the Bootstrap Process and set it
  to `src/spec_compiler.py` for the Spec Compiler.
- Under Compiler Conventions v1, `sco:ModifyExistingImplementation` copies the
  executing seed source to that artifact while incrementing one unique
  `BOOTSTRAP_GENERATION` marker.
- Treat `tools/generate.py` as G0 and the generated
  `products/spec_compiler/src/spec_compiler.py` as G1.
- Give G1 its own `pyproject.toml`, `uv.lock`, and Compiler Protocol manifest.
  The manifest executes G1's source path with its own frozen project rather than
  invoking G0.
- Generate a black-box proof that the declared G1 artifact exists with the
  expected generation and that the manifest-driven G1 compiles the valid
  fixture successfully.
- Keep stochastic coding-agent evolution outside this deterministic bootstrap
  step. A later agent may modify the accepted G1 implementation, but is not
  required to establish executable self-bootstrap.

## Consequences

- Running the repository generation workflow now performs a real G0-to-G1
  source transformation.
- Contract tests execute the generated G1 as a separate compiler product.
- Python and the current architecture are inherited by this bootstrap strategy,
  but remain absent from the technology-neutral Transformation Contract.
- G1 and G0 share almost all source and therefore do not provide an independent
  semantic oracle or diverse double-compilation guarantee.
- Generating G2 from G1 requires a separately versioned Bootstrap Process whose
  seed statement identifies G1; this change does not silently reinterpret G0 as
  a later-generation seed.

## Alternatives considered

- Continue invoking G0 under a G1 process name. Rejected because no successor
  implementation would exist.
- Require an external coding agent for G1. Rejected for the initial bootstrap
  because it would make the core generation step stochastic and unavailable in
  ordinary CI.
- Claim recursive G1-to-G2 generation from the unchanged G0 seed statement.
  Rejected because the generated implementation would contradict its declared
  provenance.

# ADR 0001: Restrict generated requirements to explicit sources

## Status

Accepted.

## Context

The first generated test imported FastAPI product code even though the specs did
not require Python, FastAPI, a module name, or an application factory. A
deterministic generator can still produce unjustified requirements if its rules
contain hidden architectural assumptions.

## Decision

Every generated obligation and assertion must be traceable to either:

1. an explicit statement in the Product Bundle's specs, or
2. a named, versioned Compiler Convention or Runtime Protocol rule.

The generator fails when required information is absent, ambiguous, unsafe, or
outside the supported profile. Work Items list their sources. Compiler
Conventions v1 are documented in `docs/generation-principles.md` and versioned
in the Work Graph.

## Consequences

- Product language, framework, module names, and internal layering remain free.
- Specs are more explicit about status, media type, identifier semantics,
  storage engine, and endpoint-to-table relationships.
- Compiler limitations become visible errors rather than accidental contracts.
- New mappings require documentation, tests, and a compatibility decision.

## Alternatives considered

- Infer conventional defaults such as HTTP 200, JSON, FastAPI, or integer IDs.
  Rejected because convenient guesses become hidden requirements.
- Let an LLM interpret missing semantics. Rejected because requirements and
  generated proofs would no longer be reproducible.

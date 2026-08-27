# ADR 0002: Verify products as black boxes

## Status

Accepted.

## Context

In-process tests coupled the first reference product to Python, FastAPI,
`TestClient`, and a `create_app` function. Such a test rejects otherwise correct
implementations in other languages and confuses the test-harness technology with
the product contract. OpenAPI alone is insufficient because it proves only what
the product declares, not what it actually does.

## Decision

The Contract Verification Harness never imports product implementation modules.
It starts a separate Product Runtime through the explicit, versioned
`product.toml` adapter and observes only contracted boundaries.

Verification is split into four focused proofs:

1. Runtime Protocol readiness and published OpenAPI availability,
2. complete OpenAPI 3.1 validity plus required-subset compatibility,
3. explicitly contracted SQLite schema and identifier behavior,
4. real HTTP behavior plus SHACL conformance.

Runtime Protocol v1 deliberately uses a narrow, documented OpenAPI profile:
self-contained JSON, local references, and direct schemas.

## Consequences

- A product may use any implementation language or framework.
- The test harness needs subprocess, port, readiness, and process-tree lifecycle
  management.
- Tool and product dependencies can be isolated.
- OpenAPI declarations and runtime behavior can fail independently and produce
  focused diagnostics.
- Direct SQLite access remains an intentional limitation of this explicit
  storage contract, not a universal product assumption.

## Alternatives considered

- Continue using framework-native in-process test clients. Rejected because they
  encode implementation technology.
- Verify only OpenAPI. Rejected because a correct document does not prove correct
  behavior or persistence.
- Require containers for every product. Deferred because it adds deployment
  weight not needed to test the current architectural question.

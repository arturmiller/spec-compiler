# ADR 0017: Compile source-backed decisions through a CLI protocol

## Status

Accepted. This decision implements and refines ADR 0016. It supersedes the
single-reference-bundle consequence of ADR 0003; both the SQL API example and
the KfW 458 applicant-eligibility example are now versioned reference bundles.

## Context

ADR 0016 established the semantic boundaries for Decision and Obligation
Compilation but deliberately left the concrete compiler profile and product
protocol open. The first vertical slice must turn one manually curated,
source-pinned funding specification into an observable result without making
HTTP, Python, automatic document ingestion, or provider approval part of the
product contract.

The existing untyped Explicit Obligation Model and Runtime Protocol v1 are
specialized for the SQL/OpenAPI/SQLite profile. Reusing either unchanged would
hide decision semantics inside dictionaries or accidentally impose an HTTP
interface on decision products.

## Decision

- Add a typed, immutable **Explicit Decision and Obligation Model** alongside
  the existing SQL-oriented Explicit Obligation Model. The model contains the
  Decision Contract, pinned Rule Set Version, Rules, Conditions, outcome
  identities, Source Revisions, Source Citations, scope, and authored
  Conformance Cases required by this slice.
- Select a compiler profile by explicit protocol conformance. A Decision Product
  is a `schema:SoftwareApplication` conforming to `sco:DecisionProtocolV1` and
  implementing exactly one `sdo:DecisionContract`. Profile ambiguity is a
  compilation error.
- Define **Decision Protocol v1** as a process boundary: the harness starts the
  command declared in `product.toml`, writes one UTF-8 JSON Decision Request to
  standard input, and accepts one JSON Decision Result from standard output.
  The protocol is separate from the domain Decision Contract and imposes no
  implementation language or network framework.
- Define **Decision Conventions v1** for the deliberately narrow
  `requiresAllRules` profile. Each Rule has one boolean Condition with an
  explicit JSON Pointer and expected value. Any violated Condition entails the
  negative outcome; otherwise any Fact Gap entails `unknown`; otherwise all
  Conditions entail the positive outcome. A missing Fact is never `false`.
- Compile the authored model into `generated/decision-contract.json`, a Work
  Graph, issue text, and generated black-box tests. Every decisive Rule in a
  Decision Result carries its Source Citation, immutable Source Revision,
  locator, and authored source statement. The generated scope note is part of
  every result.
- Publish the **Decision and Obligation Core Ontology** at `sdo:` and the
  **Funding Domain Ontology** at `funding:` as authored vocabularies beside the
  SHACL Contract Ontology. KfW program, revision, citation, rule, and case IRIs
  remain resources under `resources/funding/kfw-458/#`.
- Treat `products/kfw_458_eligibility/` as a second versioned reference Product
  Bundle. The Spec Compiler Self-Description Bundle names both reference
  products as explicit compiler conformance fixtures with profile-specific
  expected artifacts.
- Share process-tree termination between Runtime Protocol v1 and Decision
  Protocol v1 adapters. Timeout tests must prove that child processes do not
  remain alive.

## Consequences

- Eligible, ineligible, and unknown behavior is observable without importing
  product implementation modules. Decision products can use any technology
  that implements the JSON process protocol.
- The compiled Decision Contract is a stable, inspectable artifact shared by
  product implementers and generated tests. It is derived output, not a source
  of new requirements.
- The first semantics are intentionally less expressive than a general rule
  engine. OR groups, numeric conditions, obligation activation, evidence
  evaluation, and version selection across multiple applicable versions need
  later, explicitly versioned profiles.
- The compiler verifies traceability and internal consistency, but not whether
  a human-authored source statement completely or correctly transcribes the
  external document.
- A positive result remains only a positive answer to the modeled applicant
  question. It is not advice, legal entitlement, an application decision, or a
  KfW commitment.
- Three public ontologies and the KfW resource bundle add publication and
  compatibility obligations. Their WIDOCO/WebVOWL outputs remain unversioned
  documentation artifacts and are not compiler inputs.

## Alternatives considered

- Extend Runtime Protocol v1 with a decision HTTP endpoint. Rejected because it
  would turn a reference implementation choice into a product requirement.
- Encode the new model in the existing untyped dictionary. Rejected because
  Rules, Conditions, sources, cases, and outcomes need explicit invariants and
  stable renderer inputs.
- Put all decision and funding terms into `sco:`. Rejected because executable
  protocol vocabulary, reusable decision semantics, and funding semantics have
  different change and reuse boundaries.
- Evaluate directly from Turtle at product runtime. Rejected because products
  must not be required to use RDF and because the compiler artifact is the
  explicit handoff boundary.
- Return only explanation text. Rejected because machine-readable evaluations,
  Fact Gaps, decisive Rules, and provenance are required for deterministic
  checking and reuse.

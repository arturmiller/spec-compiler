# Spec Compiler context

The repository contains one bounded context: the **Spec Compiler**. It turns
explicit product specifications into deterministic contracts, proofs, and work
guidance while keeping generated products behind observable, technology-neutral
boundaries.

## Current models

The compiler normalizes the SQL/OpenAPI profile into an **Explicit Obligation
Model** and the first decision profile into a typed, immutable **Explicit
Decision and Obligation Model**. All generated requirements come from an
explicit spec statement or a named, versioned convention. Ambiguous or
unsupported input is rejected, and generated product tests remain black-box
tests.

## Implemented decision slice

[ADR 0016](docs/architecture/decisions/0016-evolve-to-decision-and-obligation-compilation.md)
accepts a bounded path toward **Decision and Obligation Compilation**.
[ADR 0017](docs/architecture/decisions/0017-compile-source-backed-decisions-through-a-cli-protocol.md)
implements its first profile with source-backed Rules, Conditions, Fact Gaps,
Decision Results, and Provenance without weakening the existing provenance
invariant. Obligation activation and evidence evaluation remain later slices.

The first implementation slice is the **KfW 458 Applicant Eligibility Pilot**.
It is invoked through Decision Protocol v1 and compiles a pinned Rule Set
Version into a Decision Contract, generated proofs, and observable eligible,
ineligible, or unknown Decision Results. Its scope and pinned source revision
are defined in the
[Decision and Obligation Compilation roadmap](docs/architecture/decision-and-obligation-roadmap.md).

## Domain language

The canonical terms, relationships, and aliases to avoid are maintained in
[UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md). Architecture documents, ADRs,
ontology terms, code, and generated work items use that language.

## Invariants

- External source documents do not directly become generated requirements; an
  authored Spec cites a Source Citation, and generated output remains traceable
  to that Spec or to a named, versioned convention.
- A missing decision fact yields an explicit Fact Gap and may yield an
  Undetermined Decision Outcome. It is not inferred as false.
- Ambiguous specs, conflicting facts, ambiguous rule-set applicability, or
  multiple incompatible conclusions are errors, not Undetermined outcomes.
- The Spec Compiler remains one software system. Decision and Obligation
  Compilation is a capability of it, not a second system.
- Reusable decision semantics and domain vocabulary remain separate. A funding
  term does not enter the Decision and Obligation Core Ontology merely because
  it appears reusable.

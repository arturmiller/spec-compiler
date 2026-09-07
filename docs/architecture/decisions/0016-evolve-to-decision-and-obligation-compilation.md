# ADR 0016: Evolve through source-backed Decision and Obligation Compilation

## Status

Accepted.

## Context

The implemented Spec Compiler proves a narrow path from explicit RDF/SHACL
product contracts to deterministic artifacts and black-box proofs. The project
aims to support arbitrary software-development projects and to produce useful,
reusable ontologies. Generalizing directly from the SQL API example risks
turning accidental HTTP, SQLite, or funding-domain concepts into universal
vocabulary.

Funding eligibility is a useful next domain because it requires explicit rule
versions, incomplete case facts, explainable decisions, evidence requirements,
and source provenance. It also creates a high risk of overclaiming legal or
financial authority if the pilot scope and outcome semantics are vague.

## Decision

- Keep **Spec Compiler** as the software-system name and boundary. **Decision
  and Obligation Compilation** is a planned capability of that system, not a
  second software system.
- Generalize the current Explicit Obligation Model toward an **Explicit Decision
  and Obligation Model** containing only explicitly sourced Rules, Facts,
  Condition Evaluations, Decisions, Fact Gaps, Obligations, Evidence
  Requirements, and Provenance.
- Use three-valued Condition Evaluations: `satisfied`, `violated`, and `unknown`.
  Missing Facts create Fact Gaps; absence is never inferred as false.
- Reserve `unknown` Decision Outcomes for incomplete Cases whose Fact Gaps
  prevent a unique conclusion. Ambiguous specs, conflicting Facts, ambiguous
  version applicability, and incompatible conclusions remain errors.
- Keep the existing **SHACL Contract Ontology** separate from a planned
  **Decision and Obligation Core Ontology** under the experimental `sdo:`
  namespace and a planned **Funding Domain Ontology** under `funding:`.
  KfW-specific programs, source revisions, citations, and cases are resources,
  not reusable vocabulary.
- Promote a Domain Ontology concept into the core only after two distinct
  domains demonstrate identical semantics and an ADR records the promotion.
- Select the **KfW 458 Applicant Eligibility Pilot** as the first slice. It uses
  the KfW Merkblatt 458, Stand 07/2026, Bestellnummer 600 000 5131, valid from
  2026-07-21, pinned by content hash and limited to the applicant-eligibility
  passage on PDF page 2.
- Treat external Source Revisions as provenance behind authored Source
  Citations. They do not replace the accepted requirement origins from ADR 0001:
  a generated requirement still originates in an explicit Spec statement or a
  named, versioned convention.
- Deliver the capability through Issues #2–#6 as vertical, black-box-verifiable
  slices while retaining deterministic generation and failure on ambiguity.
- Exclude automatic document ingestion, broad provider coverage, legal or
  financial advice, actual funding approval, subsidy calculation, UI, and
  production deployment from the initial roadmap.

The detailed semantics, source identity, pilot boundary, and slice dependencies
are normative for this roadmap and recorded in
[the Decision and Obligation Compilation roadmap](../decision-and-obligation-roadmap.md).

## Consequences

- The project obtains precise language and ontology boundaries before adding
  executable vocabulary or compiler branches.
- The implemented C4 structure does not change in this issue. Future slices
  must update it only when concrete components, stores, and relationships exist.
- A future compiler profile must preserve black-box verification without
  assuming HTTP, Python, or an interactive UI.
- Source curation remains a human-authored activity. This protects determinism
  but means the compiler does not prove that a Spec completely or correctly
  transcribes an external document.
- `eligible` in the first pilot is deliberately narrower than complete funding
  eligibility or approval; every presentation must retain that scope.
- New public ontology namespaces and publication outputs will increase
  documentation and compatibility obligations once materialized.
- The cross-domain cloud-compliance slice can falsify proposed reuse and force
  funding concepts to remain domain-specific.

## Alternatives considered

- Extend every new term in the existing SHACL Contract Ontology. Rejected
  because executable interface contracts and domain-independent decision
  semantics have different reuse boundaries.
- Start with all rules of KfW 458 or multiple funding providers. Rejected
  because source coverage and legal ambiguity would dominate the compiler
  experiment.
- Infer the newest source version and use the current date. Rejected because
  historical results would not be reproducible and applicability could be
  ambiguous.
- Model decisions as binary. Rejected because missing case facts would be
  silently treated as false or force unjustified conclusions.
- Parse funding documents automatically with an LLM. Rejected for the initial
  path because extracted Rules and generated results would lack deterministic,
  reviewed requirement provenance.
- Build a separate Funding Advisor system first. Rejected because it would test
  one application instead of evolving the reusable Spec Compiler capability.

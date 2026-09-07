# Decision and Obligation Compilation roadmap

Status: Living roadmap. The architectural basis was accepted in
[Issue #1](https://github.com/arturmiller/spec-compiler/issues/1); the first
runtime slice is implemented by Issue #2 and ADR 0017.

## Purpose

The Spec Compiler will evolve from compiling externally testable product
obligations toward **Decision and Obligation Compilation** for arbitrary
software-development domains. The evolution preserves the existing principles:
explicit provenance, deterministic generation, black-box product verification,
and failure on ambiguity.

This roadmap fixes vocabulary, semantic boundaries, ontology ownership, a first
pilot, and non-goals. It distinguishes the implemented Issue #2 subset from
later obligation, evidence, question-selection, and version-selection slices.

## Semantic model

The typed, immutable **Explicit Decision and Obligation Model** now exists
alongside the SQL-oriented Explicit Obligation Model. Issue #2 materializes the
decision, rule, condition, case, fact-gap, and provenance subset. Obligations
and evidence remain accepted target semantics for later slices.

| Concern | Accepted semantics |
| --- | --- |
| Facts | Only explicitly supplied Facts are available; absence never implies false. |
| Conditions | Each Condition evaluates to `satisfied`, `violated`, or `unknown`. An unknown evaluation identifies its Fact Gaps. |
| Rules | Each Rule explicitly identifies its Conditions and conclusion or Obligation; the compiler does not invent an aggregation rule. |
| Decisions | One Decision evaluates one scoped question for one Case against exactly one Rule Set Version. |
| Outcomes | A uniquely entailed domain outcome is returned. The serialized outcome `unknown` is returned only when Fact Gaps prevent a unique outcome. |
| Errors | Ambiguous specs, conflicting Facts, ambiguous Rule Set Version applicability, unsupported constructs, and multiple incompatible entailed outcomes fail with diagnostics rather than becoming `unknown`. |
| Obligations | An Obligation exists in a result only when an explicitly sourced Rule makes it applicable. |
| Evidence | Evidence Requirements and supplied Evidence are distinct from the Fact or Obligation they support; presence of Evidence is not automatically conclusive. |
| Provenance | Results link through Rules and authored Spec statements to Source Citations, or directly to a named, versioned convention where that convention is the permitted requirement origin. |
| Time | Validity Periods are half-open (`validFrom` inclusive, `validUntil` exclusive). A Decision Date has no implicit today/latest default. |

A complete Case with no uniquely entailed outcome indicates an incomplete or
ambiguous decision specification and is an error. An incomplete Case may produce
`unknown` only when the identified Fact Gaps are sufficient to explain why a
unique outcome cannot yet be derived.

## Ontology boundaries

The ontology boundary is semantic, not merely a file split.

| Vocabulary | Target namespace | Owns | Must not own |
| --- | --- | --- | --- |
| **SHACL Contract Ontology** | `sco:` — `https://arturmiller.github.io/spec-compiler/ontology/#` | Existing executable product, protocol, transformation, HTTP, and storage contract terms | Funding concepts or general decision semantics |
| **Decision and Obligation Core Ontology** | `sdo:` — `https://arturmiller.github.io/spec-compiler/ontology/decision/#` | Domain-independent Rule Set, Rule, Condition, Fact, Fact Gap, Decision, outcome, Obligation, evidence, provenance, and time concepts | KfW, funding, building, applicant, or cloud-policy concepts |
| **Funding Domain Ontology** | `funding:` — `https://arturmiller.github.io/spec-compiler/ontology/funding/#` | Funding Program, Applicant, Project, eligibility and exclusion meanings, funding instruments, and funding-specific outcomes | Generic compiler protocols or cloud-policy concepts |
| KfW 458 resources | `https://arturmiller.github.io/spec-compiler/resources/funding/kfw-458/#` | The program, pinned rule-set versions, source identities, citations, and pilot cases | Reusable vocabulary definitions |

The `sdo:` and `funding:` namespaces are published as separate authored
vocabularies with their own WIDOCO references and WebVOWL graphs. The Decision
and Obligation Core Ontology does not import the SHACL Contract Ontology merely
because both are compiled by the same system. Obligation and evidence terms are
added only when their slices establish executable semantics.

A domain concept may be promoted to the core only after at least two distinct
domains use it with the same semantics and the promotion is recorded as an
architectural decision. Issue #6 supplies the first planned cross-domain test.

## KfW 458 Applicant Eligibility Pilot

### Decision question

For a natural-person Case, determine whether the supplied applicant facts
satisfy the modeled applicant-eligibility rules of KfW product 458 under the
pinned July 2026 Rule Set Version.

`eligible` means only a positive answer to this scoped applicant question. It is
not a statement about measure eligibility, application completeness, funding
amount, KfW approval, available budget, or legal entitlement.

### Source register

| Field | Selected value |
| --- | --- |
| Source | KfW Merkblatt, Zuschuss Nr. 458, “BEG Heizungsförderung für Privatpersonen – Wohngebäude” |
| Source Revision | `KFW-458-MERKBLATT-2026-07` |
| Publisher | KfW Bankengruppe |
| Stand / identifier | 07/2026; Bestellnummer 600 000 5131 |
| Declared validity | Valid from 2026-07-21 |
| Authoritative rule passage for the pilot | PDF page 2, “Wer kann Anträge stellen?” and its explicit exclusions |
| Version catalogue | [KfW product 458 document archive](https://www.kfw.de/partner/KfW-Partnerportal/Service/Dokumente-zum-Produkt/458/index.jsp) |
| Retrieved document | [KfW Merkblatt 458](https://www.kfw.de/PDF/Download-Center/F%C3%B6rderprogramme-%28Inlandsf%C3%B6rderung%29/PDF-Dokumente/6000005131_M_458.pdf) |
| Retrieval date | 2026-09-04 |
| Content identity | 256,308 bytes; SHA-256 `27056983339718d66cb02e9dd526db5787df742350de15eb7821040299d9fd5d` |

### Source selection review

The official KfW document catalogue identifies a July 2026 revision and retains
earlier revisions separately. The retrieved PDF itself declares Stand 07/2026,
Bestellnummer 600 000 5131, and validity from 2026-07-21. Its page 2 contains the
selected applicant categories and explicit exclusions. The recorded length and
SHA-256 identify the exact bytes reviewed on 2026-09-04.

The Merkblatt states that the program is based on the BEG EM guideline, but the
pilot deliberately compiles only the product-specific applicant passage. If a
later Rule depends on BEG EM, technical requirements, FAQs, or another KfW
document, that document must be registered as its own pinned Source Revision
and cited explicitly; authority is never inherited through an unmodeled link.

The version catalogue is evidence for document identity and version history; it
does not itself supply compiled eligibility Rules. The pinned Merkblatt passage
is the sole external Source Revision for the first pilot. An authored Spec must
represent and cite each selected statement before it can produce a generated
requirement or result.

### Pilot boundary

The first slice supports only the natural-person category and the applicant
facts needed to distinguish ownership from the explicitly excluded GbR and
usufruct cases for an existing residential building in Germany. A negative
`naturalPerson` Fact means only that this scoped category is not satisfied;
other applicant categories, including a Wohnungseigentümergemeinschaft, require
their own Decision Contract and are not assessed as program-wide ineligible.

The pilot produces:

- `eligible` when a unique positive applicant-eligibility conclusion is entailed;
- `ineligible` when a source-backed applicant exclusion or failed necessary
  applicant condition entails that conclusion;
- `unknown` when one or more named Fact Gaps prevent a unique conclusion;
- an error for input outside the pilot boundary, conflicting Facts, ambiguous
  Rules, or an unpinned Rule Set Version.

The initial fixture Decision Date is 2026-09-04 and the Rule Set Version is
explicitly pinned. Dynamic version selection is deferred to Issue #5.

### Explicitly excluded from the pilot

- technical eligibility of a heating system or measure;
- subsidy rates, bonuses, eligible costs, calculations, and combinations;
- application timing, contracts, forms, Evidence submission, or approval;
- automatic ingestion, interpretation, or monitoring of KfW documents;
- coverage of other KfW, BAFA, state, federal, or EU programs;
- legal, financial, or funding advice and any promise of approval;
- a conversational user interface or production deployment.

## Delivery slices

| Issue | Vertical result | Dependency |
| --- | --- | --- |
| [#2](https://github.com/arturmiller/spec-compiler/issues/2) | **Implemented:** compile the pinned pilot end to end into `eligible`, `ineligible`, and `unknown` Decision Results with source provenance through Decision Protocol v1. | This roadmap |
| [#3](https://github.com/arturmiller/spec-compiler/issues/3) | Derive the next decision-relevant question from a Fact Gap. | #2 |
| [#4](https://github.com/arturmiller/spec-compiler/issues/4) | Evaluate Conditions separately from Evidence Requirements. | #2 |
| [#5](https://github.com/arturmiller/spec-compiler/issues/5) | Select exactly one applicable Rule Set Version from an explicit Decision Date. | #2 |
| [#6](https://github.com/arturmiller/spec-compiler/issues/6) | Test core-ontology reuse with a cloud-compliance decision slice. | #3, #4, #5 |

Each slice must update architecture and ontology documentation with its actual
implementation, regenerate outputs twice with byte-identical results, and pass
the complete workflow.

## Cross-slice guardrails

- The Spec Compiler remains the software system; Decision and Obligation
  Compilation is a capability selected by explicit contract/protocol semantics.
- A source parser, scraper, crawler, or LLM is not part of deterministic
  compilation. Source-to-Spec curation is a separate authored step.
- New output formats or runtime interactions require explicit, versioned
  contracts before generated assertions can rely on them.
- Generated tests observe products through declared black-box boundaries and do
  not import their implementation modules.
- No UI, framework, programming language, file format, or deployment topology
  is inferred from the funding pilot.
- Deterministic output never substitutes for semantic correctness; independent
  examples and review remain necessary.

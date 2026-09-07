# ADR 0019: Evaluate Evidence Requirements separately from Conditions

## Status

Accepted. This decision extends the decision profile established by ADR 0017
and implements Issue #4.

## Context

A factual Condition and the Evidence required to substantiate it answer
different questions. An applicant may satisfy the ownership Condition while a
required ownership document is still missing. Treating a supplied artifact as
proof merely because it exists would also collapse document presence,
relevance, and acceptance into one unsupported inference.

The KfW 458 source makes this separation concrete. Its applicant-eligibility
passage supports the ownership Condition, while a separate passage on PDF page
8 requires self-using owners who claim the climate-speed or income bonus to
submit a land-register excerpt. The compiler must retain both source paths and
must not prescribe a document representation or storage mechanism that neither
the source nor a versioned convention specifies.

## Decision

- Add **Evidence Requirement**, **Evidence**, **Evidence Assessment**,
  **Evidence Expectation**, and **Evidence Requirement Status** to the Decision
  and Obligation Core Ontology. Add the funding-specific **Land-register
  excerpt** evidence type and bonus-applicability facts to the Funding Domain
  Ontology.
- An Evidence Requirement independently declares the Rule Condition it
  supports, one or more applicability Conditions, a required Evidence type,
  and its own Source Citation. Its citation is not inherited from the supported
  Rule.
- Define **Evidence Evaluation Conventions v1**. All declared applicability
  Conditions must be `satisfied` for the requirement to be applicable to the
  supplied Case. Otherwise its status is `not_applicable`, while each
  applicability Condition's `violated` or `unknown` state remains visible and
  no missing Fact is inferred as false.
- An applicable requirement is `fulfilled` only when at least one supplied
  Evidence item has the required type and an explicit accepted Evidence
  Assessment for that requirement. Otherwise it is `missing`.
- Classify each supplied Evidence item for each requirement as `accepted`,
  `rejected`, `unassessed`, or `not_relevant`. Mere presence never fulfills a
  requirement.
- Compile Evidence Requirement evaluations into the Decision Result with
  status, applicability evaluations, supplied-Evidence classifications,
  explanation, Source Citation, Source Revision, locator, and source statement.
  Rule Condition Evaluations and the Decision Outcome are computed without
  consulting Evidence or Evidence Assessments.
- Require authored Conformance Cases to state expected Evidence Requirement
  statuses and collectively cover `fulfilled`, `missing`, and
  `not_applicable`. Generated tests exercise those cases through Decision
  Protocol v1 and additionally reject fulfillment by an explicitly rejected
  Evidence item.
- Keep Decision Protocol v1 unchanged. Evidence is semantic JSON input within
  the existing request/result exchange. Evidence Evaluation Conventions v1 do
  not define a filename, media type, document body, upload protocol, storage
  location, user interface, or authenticity/content-verification process.

## Consequences

- A positive applicant-eligibility Decision can coexist with a missing
  Evidence Requirement, making the distinction observable and reusable.
- Both the supported factual Condition and the Evidence Requirement retain
  independent source provenance in compiled artifacts and runtime results.
- An Evidence Assessment is an explicit Case input. The first version does not
  determine who made it or automatically inspect an artifact; those semantics
  require later sourced specifications and conventions.
- A requirement whose applicability facts are incomplete is currently
  `not_applicable`, with the unknown applicability state exposed. A later
  profile may introduce a fourth pending-applicability status only through a
  new convention version.
- Multiple requirements and Evidence items have deterministic ordering, but
  the initial KfW pilot demonstrates one requirement and one accepted item.

## Alternatives considered

- Infer ownership from a land-register excerpt. Rejected because evidence
  acceptance and factual truth are separate claims, and the source does not
  authorize this inference.
- Treat any supplied artifact as fulfillment. Rejected because relevance and
  acceptance would be invented.
- Reuse the Rule's Source Citation for the Evidence Requirement. Rejected
  because the KfW passages and resulting requirements are independently
  traceable.
- Require PDFs, filenames, uploads, or a database. Rejected because those are
  implementation choices outside the authored product specification.
- Increment Decision Protocol to v2. Rejected because process lifecycle and
  transport are unchanged; the new behavior is versioned by Evidence
  Evaluation Conventions v1 in the compiled contract and Work Graph.

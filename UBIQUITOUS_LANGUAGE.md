# Ubiquitous Language

## Compilation and evaluation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Decision and Obligation Compilation** | The Spec Compiler capability that derives source-backed Decision Contracts, Evidence Requirement Evaluations, and proofs, with obligations reserved for later profiles, from explicit specifications. | Eligibility engine, rules bot |
| **Explicit Decision and Obligation Model** | The typed, immutable normalized model containing only explicit decision, evidence, and provenance semantics shared by deterministic renderers; obligation activation remains deferred. | Universal domain model, knowledge base |
| **Decision Contract** | The implementation-neutral contract that fixes the scoped question, Rule Set Version, outcomes, Rules, Conditions, Evidence Requirements, provenance, and evaluation conventions for a Decision Product. | Decision result, runtime protocol |
| **Decision Product** | A separately executed software product that implements a Decision Contract behind Decision Protocol v1. | Spec Compiler, KfW approval service |
| **Decision Request** | One Decision Protocol v1 JSON input naming the Decision Contract, Rule Set Version, Decision Date, supplied Case Facts, and optional supplied Evidence with Assessments. | Application, questionnaire |
| **Decision Result** | One machine-readable Decision Protocol v1 output containing the Outcome, Condition Evaluations, decisive Rules, Fact Gaps, at most one Next Question, Evidence Requirement Evaluations, Provenance, Explanation, and scope note. | Approval, advice |
| **Rule Set** | A stable identity for a governed collection of related Rules across revisions. | Policy document, latest rules |
| **Rule Set Version** | One immutable, explicitly identified revision of a Rule Set with declared applicability. | Current version, latest version |
| **Rule** | A normative proposition in a Spec that relates one or more Conditions to an explicit conclusion or Obligation. | Business logic, heuristic |
| **Fact** | An explicitly supplied assertion about the Case evaluated by a Decision. | Assumption, answer |
| **Fact Gap** | The recorded absence of a Fact required to evaluate a Condition. | Unknown Fact, false Fact |
| **Fact Question** | An authored prompt tied to exactly one Condition and its input Fact, with an explicit priority used by Question Selection Conventions v1. | Generated wording, form field |
| **Next Question** | The single Fact Question selected from current Fact Gaps for an undetermined Decision Result; determinate results have none. | Any missing field, questionnaire |
| **Question Flow Case** | A complete positive Conformance Case whose Facts provide authored answers for the generated multi-step question-flow proof. | Session transcript, UI script |
| **Condition** | A truth-valued predicate referenced by a Rule and evaluated only from explicit Facts and named conventions. | Check, requirement |
| **Condition Evaluation** | The result `satisfied`, `violated`, or `unknown` for one Condition within one Decision. | Decision result |
| **Decision** | The act of evaluating one explicitly scoped question for one Case against exactly one applicable Rule Set Version; its serialized observation is a Decision Result. | Recommendation, approval, result document |
| **Decision Outcome** | The uniquely entailed domain conclusion of a Decision, or `unknown` when a Fact Gap prevents a unique conclusion. | Condition status, guarantee |
| **Case** | The explicitly bounded subject and supplied Facts considered by one Decision. | User profile, application file |

## Obligations and evidence

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Obligation** | An explicitly sourced requirement that applies to a Case when its Rule applies. | Evidence, task |
| **Evidence Requirement** | An explicitly sourced requirement for information or an artifact that can support a Fact or an Obligation's fulfillment. | Obligation, proof |
| **Evidence** | Supplied information or an artifact offered in support of a Fact or fulfillment claim without being treated as conclusive by mere presence. | Guaranteed proof, requirement |
| **Evidence Assessment** | An explicit acceptance or rejection of one supplied Evidence item for one Evidence Requirement. | Evidence presence, automatic validation |
| **Evidence Requirement Evaluation** | The result `fulfilled`, `missing`, or `not_applicable` for one Evidence Requirement, including applicability states, Evidence classifications, explanation, and independent provenance. | Condition Evaluation, Decision Outcome |

## Provenance and time

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Source** | A stable identity for an external document or governed publication across revisions. | Spec origin, URL |
| **Source Revision** | One immutable, identified edition of a Source whose content can be verified. | Web page, current document |
| **Source Citation** | A precise locator from an authored Spec statement to a passage in one Source Revision. | Source, provenance |
| **Provenance** | The navigable chain from a derived result through Rules and Spec statements to Source Citations or named, versioned conventions. | Explanation text |
| **Validity Period** | A half-open interval from an inclusive `validFrom` instant to an exclusive optional `validUntil` instant. | Publication date, current period |
| **Decision Date** | The explicitly supplied instant used to select an applicable Rule Set Version for a Decision. | Run time, today's date |

## Ontology boundaries

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **SHACL Contract Ontology** | The existing public `sco:` vocabulary for executable product and transformation contracts. | Decision ontology |
| **Decision and Obligation Core Ontology** | The public `sdo:` vocabulary for domain-independent decision, rule, condition, case, evidence, provenance, and temporal concepts; obligation activation remains planned. | Funding ontology, universal ontology |
| **Domain Ontology** | A vocabulary whose terms carry meaning specific to one problem domain and may use the core ontology without becoming part of it. | Core extension by default |
| **Funding Domain Ontology** | The public `funding:` Domain Ontology for funding programs, applicants, projects, scoped eligibility facts, and funding-specific outcomes. | KfW ontology, core ontology |
| **KfW 458 Applicant Eligibility Pilot** | The bounded first Case family that evaluates only natural-person applicant eligibility under the pinned July 2026 KfW 458 source revision. | KfW advisor, funding approval |

## Relationships

- One **Rule Set** has one or more **Rule Set Versions**; a **Decision** uses
  exactly one applicable version.
- A **Decision Product** receives a **Decision Request** and emits one
  **Decision Result** through Decision Protocol v1 while implementing the
  referenced **Decision Contract**.
- One **Rule Set Version** contains one or more **Rules** and has one
  **Validity Period**.
- A **Rule** references one or more **Conditions** and exactly identifies its
  conclusion or **Obligation**.
- A **Condition** has exactly one **Condition Evaluation** within a **Decision**.
- An unknown **Condition Evaluation** identifies at least one **Fact Gap**.
- One **Fact Question** elicits the Fact for exactly one **Condition**. An
  undetermined **Decision Result** selects at most one **Next Question** from
  its current **Fact Gaps** by the explicit priority convention.
- A client answers a **Next Question** by adding the Fact to the complete
  **Case** and submitting another **Decision Request**; the protocol retains no
  session state.
- A **Source** has one or more **Source Revisions**; a **Source Citation** points
  to exactly one revision.
- Every derived **Decision Outcome**, **Obligation**, and **Evidence
  Requirement** has **Provenance** to a Spec statement or named, versioned
  convention.
- An **Evidence Requirement** has its own Source Citation and applicability
  Conditions. A satisfied supported Condition does not fulfill it.
- Under Evidence Evaluation Conventions v1, only matching **Evidence** with an
  explicit accepted **Evidence Assessment** makes an applicable Evidence
  Requirement Evaluation `fulfilled`; otherwise it is `missing`.
- The **Funding Domain Ontology** may use the **Decision and Obligation Core
  Ontology**; neither is part of the **SHACL Contract Ontology**.

## Example dialogue

> **Developer:** "The applicant did not tell us whether they own the building.
> Is the applicant therefore ineligible?"
>
> **Domain expert:** "No. Ownership is a required **Fact**, so its absence is a
> **Fact Gap** and the ownership **Condition Evaluation** is `unknown`."
>
> **Developer:** "Then does the **Decision Outcome** become `unknown`?"
>
> **Domain expert:** "Only if that gap prevents a unique outcome. A separate,
> satisfied exclusion Rule could already entail `ineligible`."
>
> **Developer:** "Which question should we ask next?"
>
> **Domain expert:** "Only the **Fact Question** for a current **Fact Gap**.
> **Question Selection Conventions v1** choose the lowest authored priority,
> and a determinate result has no **Next Question**."
>
> **Developer:** "And `eligible` means KfW will approve the application?"
>
> **Domain expert:** "No. In the **KfW 458 Applicant Eligibility Pilot** it
> means only that the modeled applicant-eligibility question is positive under
> the selected **Rule Set Version**."

## Flagged ambiguities

- "Unknown Fact" sounds like a third truth value stored as a Fact. Use **Fact
  Gap** for missing input and `unknown` only for a **Condition Evaluation** or
  serialized undetermined **Decision Outcome**.
- "Eligible" can mean applicant eligibility, measure eligibility, complete
  application readiness, or an actual funding decision. The pilot uses it only
  for the explicitly named applicant-eligibility question.
- "Source" previously meant the immediate origin of a generated requirement.
  Keep the compiler invariant precise: generated output originates in a Spec
  statement or convention; an external **Source Revision** is reached through a
  **Source Citation** in that Spec.
- "Requirement" can mean a Condition, an Obligation, or an Evidence
  Requirement. Use the specific canonical term.
- "Decision and Obligation Compiler" can sound like a second software system.
  The canonical capability is **Decision and Obligation Compilation** inside
  the existing **Spec Compiler**.
- A document publication date and a **Validity Period** are not interchangeable;
  applicability must be declared explicitly.

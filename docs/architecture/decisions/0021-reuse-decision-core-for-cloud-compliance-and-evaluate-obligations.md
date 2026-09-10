# ADR 0021: Reuse the decision core for cloud compliance and evaluate Obligations

## Status

Accepted. This decision extends ADRs 0016 through 0020 and implements Issue #6.

## Context

The KfW 458 pilot established executable semantics for source-backed Decisions,
three-valued Conditions, provenance, Fact Questions, Evidence Requirements, and
temporal Rule Set Version selection. A second domain is needed to distinguish
reusable concepts from funding-specific vocabulary. Cloud access policy is a
useful test because it contains normative controls, independent assessment
guidance, missing system-profile facts, and evidence obligations without any
funding concepts.

The accepted architecture already assigned `Obligation` to the Decision and
Obligation Core Ontology, but the term had not yet been materialized in the
public Turtle vocabulary or compiled result. Also, the KfW slice happened to
use one document revision for a Rule Set Version, its Rules, and its Evidence
Requirement. Treating that coincidence as a universal constraint would prevent
a policy Rule from citing NIST SP 800-53 while its assessment Evidence
Requirement cites NIST SP 800-53A.

## Decision

- Add a separate **Cloud Compliance Domain Ontology** at `cloud:`. It owns
  `CloudSystem`, the privileged-access decision type, cloud identity Facts, the
  authentication-test Evidence type, and cloud-specific Outcomes. No cloud or
  NIST term moves into `sdo:`.
- Add the `cloud_access_compliance` Product Bundle. Its deliberately bounded
  Rule Set Version contains only NIST SP 800-53 Rev. 5 controls IA-2 and
  IA-2(1), selected from an explicit Decision Date. NIST SP 800-53A Rev. 5
  independently sources the MFA Evidence Requirement.
- Reuse `sdo:` unchanged for Decision Contract, Rule Set, Rule Set Version,
  Rule, Condition, Case, Fact Gap, Fact Question, Evidence, Evidence
  Requirement, Evidence Assessment, Source, Source Revision, Source Citation,
  and validity. Their semantics are identical in the funding and cloud
  products. This is the required cross-domain evidence; no domain concept is
  promoted to the core.
- Materialize the already accepted domain-independent **Obligation** concept in
  `sdo:` together with Obligation Expectation, Obligation Evaluation, and the
  statuses `fulfilled`, `violated`, and `unknown`. This is activation of ADR
  0016's existing core concept, not promotion of a cloud term.
- Define **Obligation Evaluation Conventions v1**. A Rule may explicitly impose
  zero or more Obligations. For the current single-Condition Rule profile, the
  Rule Condition state maps deterministically as `satisfied` to `fulfilled`,
  `violated` to `violated`, and `unknown` to `unknown`. Each evaluation exposes
  the Obligation text, Rule, Condition, inherited Rule Source Citation, and an
  explanation. No Obligation is inferred from prose or a domain predicate.
- Keep Decision Outcome and Evidence Requirement Evaluation independent from
  Obligation Evaluation. Evidence continues to report `fulfilled`, `missing`,
  or `not_applicable` and does not change Condition truth or the aggregate
  Decision Outcome.
- Permit a Rule Set Version, each Rule, and each Evidence Requirement to cite
  different immutable Source Revisions. The version citation establishes the
  policy version and validity; each Rule and Evidence Requirement remains
  independently traceable to its own explicit citation.
- Keep Decision Protocol v1 unchanged. Obligations and their provenance are
  additive fields in the compiled Decision Contract and Decision Result, with
  their semantics named by `obligation_evaluation_conventions_version = 1`.
- Define **Compiler Conventions v2** for Decision Work Item identity. Generated
  IDs use the kebab-cased Product Bundle directory instead of the original
  KfW-specific prefix, and generation removes stale Markdown files only from
  that bundle's validated `generated/issues/` directory.
- Publish `cloud:` as a fourth bilingual WIDOCO/WebVOWL reference and publish
  the cloud Product resources separately from the canonical vocabulary.

## Consequences

- The second domain demonstrates genuine reuse of decision, provenance,
  temporal, question, and evidence semantics without importing funding terms.
- The cloud product reports source-backed `satisfied`, `violated`, and
  `unknown` Outcomes, asks a decision-relevant missing MFA question, reports an
  independently evaluated MFA test Evidence Requirement, and exposes both
  Rule-imposed Obligations through the same black-box process boundary.
- Obligation semantics are deliberately narrow. Deadlines, responsible
  parties, remediation state, enforcement, compound applicability, and
  evidence-backed fulfillment remain unsupported until explicit conventions
  and conformance cases define them.
- The funding product currently declares no Rule-imposed Obligations and
  therefore returns an empty Obligation Evaluation list. This avoids
  misclassifying eligibility criteria as duties merely to manufacture reuse.
- The compiler self-description gains the cloud bundle as a third conformance
  fixture, so both compiler generations must compile the new profile to a
  byte-identical fixpoint.
- Existing KfW generated Work Item filenames change once to the generic Product
  Bundle prefix; stale KfW-specific files are removed deterministically.

## Alternatives considered

- Put cloud identity and NIST-specific terms into `sdo:`. Rejected because they
  have not demonstrated equivalent semantics outside cloud compliance.
- Put all terms in the Product resource namespace. Rejected because stable
  domain vocabulary and version-specific policy resources have different
  ownership and publication lifecycles.
- Treat the Evidence Requirement as the Obligation. Rejected because required
  control behavior and evidence needed to assess it are distinct semantics.
- Require one Source Revision for the policy, Rules, and assessment Evidence.
  Rejected because it would erase the explicit SP 800-53/SP 800-53A provenance
  boundary.
- Add artificial KfW Obligations to prove symmetry. Rejected because applicant
  eligibility Conditions are not automatically duties imposed on the Case.

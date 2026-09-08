# ADR 0020: Select a Rule Set Version only from validity and Decision Date

## Status

Accepted. This decision extends ADR 0017 and implements Issue #5.

## Context

A decision is not reproducible when a caller selects “current” rules or when a
runtime silently uses today or the latest known document. The KfW 458 archive
also demonstrates why the date matters: revision 12/2025 lists the GbR
exclusion but no usufruct exclusion, while revision 07/2026 adds an explicit
usufruct exclusion. The same applicant facts therefore have a different
source-backed outcome at the revision boundary.

## Decision

- Define **Version Selection Conventions v1**. A Decision Request supplies the
  stable Rule Set identity and an explicit ISO Decision Date. It must not
  supply the Rule Set Version.
- A Decision Contract declares all candidate Rule Set Versions. Each version
  has an immutable identity, version label, inclusive `validFrom`, optional
  exclusive `validUntil`, its own version Source Citation, Rules, and
  version-local Evidence Requirements.
- Select a version only when its half-open Validity Period contains the
  Decision Date. Exactly one candidate must match. No current-date or
  latest-version default exists.
- Reject missing Decision Dates, uncovered dates, overlapping periods,
  different stable Rule Sets, or any other zero/multiple match with an
  actionable compilation or runtime diagnostic.
- Treat `expectsRuleSetVersion` on a Conformance Case as an oracle for the
  compiler proof, never as a selector. A Decision Result reports the stable
  Rule Set, selected Rule Set Version identity and label, and Decision Date.
- Prove the boundary with two Version Selection Cases containing identical
  Facts: 2026-07-20 selects the 12/2025 KfW rules and yields `eligible` for the
  modeled usufruct applicant; 2026-07-21 selects the 07/2026 rules and yields
  `ineligible`. Compiler black-box tests cover missing, uncovered, and
  overlapping applicability.
- Keep Decision Protocol v1 unchanged because its process lifecycle and JSON
  transport do not change. Version-selection semantics are independently
  versioned in the compiled contract and Work Graph.

## Consequences

- Historical results can be reproduced without consulting wall-clock time.
- Version provenance is explicit even when a version contains no rule that is
  present in a later revision.
- Gaps are allowed but a Decision Date within a gap fails. Open-ended periods
  are allowed only as the final non-overlapping interval.
- Adding a source revision requires authored validity, citations, rules, and
  conformance expectations; the compiler does not infer change sets.
- Evidence Requirements are owned by their Rule Set Version, so a historical
  decision is not evaluated against requirements introduced by a later source.

## Alternatives considered

- Let callers pin the version. Rejected because this bypasses the requested
  temporal context and permits an inconsistent date/version pair.
- Select the greatest version label or newest `validFrom`. Rejected because it
  creates a latest-version default and hides overlaps.
- Default the Decision Date to today. Rejected because identical requests
  would change meaning over time.
- Fetch the KfW archive at runtime. Rejected because external ingestion is not
  part of deterministic compilation or Decision Protocol v1.

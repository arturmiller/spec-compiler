# Domain documentation

This repository uses a single domain context.

## Read before exploring or proposing changes

- Read `CONTEXT.md` at the repository root if it exists.
- Read `UBIQUITOUS_LANGUAGE.md` for canonical domain terms and aliases to avoid.
- Read `docs/generation-principles.md` for normative generation rules.
- Read `docs/architecture/arc42.md` and `docs/architecture/c4.md` for the living
  architecture.
- Read relevant accepted records under `docs/architecture/decisions/`.
- Follow `docs/architecture/maintenance.md` when a proposed change affects the
  architecture.

If `CONTEXT.md` does not exist, proceed using the terminology in the architecture
documentation and ADRs. A domain-document producer may create it later when the
domain language is deliberately refined.

## Vocabulary and decisions

Use canonical domain terms consistently in issue titles, plans, code, generated
work items, arc42, C4, and ADRs. If a proposal contradicts an accepted ADR,
surface that conflict explicitly; do not silently rewrite the decision.

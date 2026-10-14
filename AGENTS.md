# Repository instructions

## Read before changing the system

Read these documents before making an architecture-significant change:

1. `docs/generation-principles.html`
2. `docs/architecture/arc42.html`
3. `docs/architecture/c4.html`
4. the relevant records under `docs/architecture/decisions/`

## Architecture documentation is part of the change

Follow `docs/architecture/maintenance.html` for every change that affects system
boundaries, runtime interactions, the product protocol, the spec vocabulary,
generated artifacts, component responsibilities, deployment, dependencies,
quality properties, or architectural risks.

- Update arc42 when architectural facts, constraints, runtime scenarios,
  quality goals, or risks change.
- Update the C4 model when an element, responsibility, technology, boundary, or
  relationship changes.
- Add an ADR for a new consequential decision. Do not rewrite accepted ADRs;
  supersede them with a new ADR.
- Use the same canonical element names in arc42, C4, ADRs, code, and generated
  work items.
- If a section is not applicable, retain it and explain why.

Architecture-changing work is incomplete while the architecture documentation
is stale.

## Contract generation

- Never add a generated requirement unless it is traceable to an explicit spec
  statement or a named, versioned compiler/runtime convention.
- Fail on ambiguity instead of inferring an implementation technology.
- Generated tests must treat products as black boxes and must not import product
  implementation modules.
- Do not edit files below a product's `generated/` or `tests/` directory by
  hand. Change the specs, conventions, or generator and regenerate them.
- Python and FastAPI belong to `sql_api_example`; they are not product contract
  requirements.

## Verification

Run the complete workflow after relevant changes:

```console
uv run --extra dev poe run
```

When generated outputs change, run the generator twice and verify byte-identical
outputs. When runtime handling changes, also verify that no child process remains
after the tests.

## Agent skills

### Issue tracker

Issues and PRDs are tracked as GitHub Issues. See
`docs/agents/issue-tracker.html`.

### Triage labels

The repository uses `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.html`.

### Domain docs

The repository uses a single domain context documented in `docs/context.html`
and architecture decisions under `docs/architecture/decisions/`. See
`docs/agents/domain.html`.

### Documentation

Human documentation sources are HTML in `docs/`; diagram sources are JSON in
`docs/diagrams/`. Do not add parallel Markdown or Mermaid sources. Read HTML
source directly when reviewing architecture. Canonical terminology lives in
`docs/glossary.html`. Preview with `uv run --extra dev poe documentation-preview`;
validate with `uv run --extra dev poe documentation-validate`. Generated product
issues remain Markdown and are not affected by this documentation rule.

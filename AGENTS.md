# Repository instructions

## Read before changing the system

Read these documents before making an architecture-significant change:

1. `docs/generation-principles.md`
2. `docs/architecture/arc42.md`
3. `docs/architecture/c4.md`
4. the relevant records under `docs/architecture/decisions/`

## Architecture documentation is part of the change

Follow `docs/architecture/maintenance.md` for every change that affects system
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

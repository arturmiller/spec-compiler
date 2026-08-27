# Architecture documentation standard

This file defines how the architecture documentation is kept useful over time.
It is normative for human contributors and coding agents.

## Canonical document set

| Document | Purpose |
| --- | --- |
| `arc42.md` | Narrative architecture knowledge using all twelve arc42 sections |
| `c4.md` | Static structure at system-context, container, and component level |
| `decisions/*.md` | Immutable records of consequential architecture decisions |
| `../generation-principles.md` | Normative rules for requirements and compiler conventions |

arc42 and C4 are complementary. arc42 explains goals, constraints, runtime,
quality, decisions, and risks. C4 supplies consistent zoom levels for static
structure. Neither document replaces the executable contracts.

## Required update triggers

Update the architecture documentation in the same change whenever one of these
changes:

- ownership or a system boundary,
- a runtime or deployment interaction,
- `product.toml` or the runtime protocol,
- RDF/SHACL vocabulary or compiler convention,
- generated artifact type or location,
- component responsibility or dependency,
- implementation-independent product interface,
- architecture dependency or technology choice,
- quality scenario, known risk, or technical debt.

Pure refactorings that preserve all documented facts need no prose change. They
still require a quick consistency check.

## arc42 rules

- Preserve the twelve numbered top-level sections and their order.
- Keep the requirements overview short; detailed executable requirements remain
  in the specs and generated contracts.
- Express important quality goals as observable scenarios in section 10.
- Link consequential decisions from section 9 to an ADR.
- Record known limitations honestly in section 11.
- Use “Not applicable” with a reason instead of silently deleting a section.

## C4 rules

- Give every diagram a title, scope, and legend.
- State every element type: Person, Software System, Container, or Component.
- Give every container and component its technology and responsibility.
- Label every relationship in its direction of use or data flow.
- Do not mix abstraction levels in one diagram.
- Use identical element names at every zoom level.
- Model a file collection as an artifact/data store, not as an executable
  container. A C4 container must be a separately runnable or deployable unit or
  a data store.
- Add a Component view only when it explains responsibilities that are not clear
  from the Container view. Add a Code view only when it has durable value.

Mermaid is the repository notation. C4 is notation-independent, so the element
labels and legends carry the C4 semantics.

## ADR rules

- Number ADRs sequentially with four digits.
- Use Status, Context, Decision, Consequences, and Alternatives sections.
- Accepted ADRs are historical records. Replace an old decision by adding a new
  ADR whose status and links mark the previous ADR as superseded.
- Link the ADR from arc42 section 9 and from affected design documentation.

## Review checklist

Before completing an architecture-significant change, verify:

- Do arc42, C4, and ADRs use the same names?
- Does every new generated assertion have a documented source?
- Do diagrams show current directions, protocols, and technologies?
- Are tool requirements clearly separated from product requirements?
- Are generated files still marked and reproducible?
- Do all local Markdown links resolve?
- Does `uv run --extra dev poe run` pass?

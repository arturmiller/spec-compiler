# ADR 0008: Rename the system and repository to Spec Compiler

## Status

Accepted. Supersedes the system and repository naming in earlier ADRs and the
GitHub-hosted IRI paths selected by
[ADR 0007](0007-publish-experimental-ontology-with-github-pages.md). The
remaining publication decisions in ADR 0007 stay in effect.

## Context

The original repository name `shacl_example` and system name SHACL Contract
Toolchain described an early example rather than the emerging product. The
system now compiles explicit product specifications into executable contracts,
tests, expected artifacts, and work guidance. Its product identity should not
be tied to SHACL or confused with the narrower Transformation Contract concept.

Because the experimental ontology and resource IRIs use the GitHub Pages
project path, renaming the repository also changes those IRIs. ADR 0007 already
accepted this instability for the prototype.

## Decision

- Name the software system and GitHub repository **Spec Compiler** and
  `spec-compiler` respectively.
- Use `spec_compiler` for Python/package and Product Bundle identifiers where
  hyphens are inappropriate.
- Identify the self-described product as `tool:SpecCompiler` and its current
  Transformation Contract as `tool:SpecCompilationV1`.
- Move the Self-Description Bundle to `products/spec_compiler/` and call it the
  **Spec Compiler Self-Description Bundle**.
- Publish experimental vocabulary and resource IRIs below
  `https://arturmiller.github.io/spec-compiler/`.
- Keep the ontology name **SHACL Contract Ontology** because it names the
  reusable vocabulary, not the compiler product.
- Do not provide compatibility aliases for the old experimental IRIs.

## Consequences

- The product name now communicates the broader compilation of specifications,
  while contracts remain the binding, executable subset of those specs.
- Code, architecture documentation, generated proofs, package metadata, GitHub
  Pages, and public RDF resources use the same canonical product name.
- Existing references below `https://arturmiller.github.io/shacl_example/`
  become obsolete. This is acceptable before a stable vocabulary release.
- A future stable release still requires a repository-independent persistent
  namespace such as w3id.org.

## Alternatives considered

- Use `specs-compiler`. Rejected because the plural form is less idiomatic and
  does not improve the meaning.
- Use `contract-compiler`. Rejected because it narrows the product identity to
  executable contracts and leaves less room for other compiled spec artifacts.
- Retain `shacl_example`. Rejected because it presents the system as a sample
  and couples its identity to one input technology.

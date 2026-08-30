# ADR 0007: Publish the experimental ontology with WIDOCO, WebVOWL, and GitHub Pages

## Status

Accepted.

## Context

The custom contract vocabulary was implicit in Product Bundle specs and used
the placeholder namespace `https://example.org/catalog/`. The project needs a
public, human-readable and searchable experiment without committing generated
website files or operating a dynamic RDF service.

The existing Turtle files mix vocabulary terms, toolchain instances, and the
SQL API example domain. WIDOCO and WebVOWL primarily document OWL/RDFS
vocabulary structure; treating all instances and SHACL shapes as one ontology
would produce a misleading and cluttered visualization.

## Decision

- Publish the vocabulary from `ontology/shacl-contract.ttl` under the
  experimental GitHub Pages namespace
  `https://arturmiller.github.io/shacl_example/ontology/#`, whose document IRI
  resolves to the statically hosted `/ontology/` directory.
- Keep toolchain instances under
  `https://arturmiller.github.io/shacl_example/resources/toolchain/#` and SQL API
  example resources under
  `https://arturmiller.github.io/shacl_example/resources/sql-api/#`. Publish an
  HTML index at each fragment namespace's document IRI.
- Generate bilingual HTML reference documentation and an embedded searchable
  WebVOWL graph with WIDOCO 1.4.25.
- Pin and verify the WIDOCO JDK 17 JAR by SHA-256 before execution.
- Publish Product Bundle specs as downloadable examples, not as vocabulary
  definitions or WebVOWL input.
- Treat `build/ontology-site/` as an unversioned, replaceable build artifact.
  Website byte identity is not a quality requirement.
- Build and deploy the site from GitHub Actions to GitHub Pages after the full
  repository workflow passes. Pull requests build the site but do not deploy.
- Validate that every public vocabulary IRI used by Product Bundle specs is
  defined and labeled in the canonical ontology and that no placeholder
  `example.org` namespace remains.

The experiment deliberately uses GitHub-hosted IRIs. A persistent redirect such
as w3id.org is deferred until the vocabulary requires stability independent of
the repository owner and name.

## Consequences

- Users receive HTML reference pages, RDF serializations, example specs, and an
  interactive graph with client-side entity search from a static site.
- GitHub Actions, GitHub Pages, Java 17, WIDOCO, and its bundled WebVOWL become
  architecture dependencies of documentation publication, not product runtime
  dependencies.
- GitHub Pages does not provide RDF content negotiation or a SPARQL endpoint;
  HTML and Turtle have explicit URLs.
- WebVOWL represents the OWL/RDFS vocabulary, not complete SHACL constraints or
  the full instance graphs. Published examples retain those details.
- Renaming the GitHub account or repository breaks the experimental IRIs. That
  is accepted for the prototype and must be revisited before a stable release.

## Alternatives considered

- Use w3id.org immediately. Deferred because the current goal is an experiment;
  it remains the preferred migration option for stable public identifiers.
- Commit generated HTML to the repository. Rejected because it creates large,
  low-value diffs and the website does not require byte-identical versioning.
- Feed all Product Bundle specs directly to WebVOWL. Rejected because product
  instances and SHACL constraints are not the OWL vocabulary graph.
- Operate a triple store and SPARQL endpoint. Rejected because static discovery
  and documentation satisfy the current goal with much less operational scope.

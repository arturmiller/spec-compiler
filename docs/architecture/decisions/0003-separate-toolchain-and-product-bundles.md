# ADR 0003: Separate the toolchain from Product Bundles

## Status

Accepted.

## Context

Generated products, their specs, tests, dependencies, and implementation choices
must not become dependencies or source structure of the compiler itself. The
repository also needs one inspectable example without committing every future
generated product.

## Decision

- Tool code lives under `tools/` with the root `pyproject.toml` and `uv.lock`.
- Every product lives in a self-contained `products/<name>/` Product Bundle.
- A Product Bundle owns its specs, runtime manifest, generated contracts, tests,
  implementation, dependency manifest, and lockfile.
- Git ignores products by default and explicitly includes only
  `products/sql_api_example/` as the reference bundle.
- `sql_api_example` may use Python and FastAPI, but those choices are not
  described as toolchain or product-contract requirements.

## Consequences

- Product dependencies do not leak into the root tool environment.
- A Product Bundle is portable as one artifact boundary.
- The compiler accepts `--product products/<name>` rather than importing a fixed
  product package.
- Repository tooling needs explicit paths for the versioned reference product.

## Alternatives considered

- Keep one root-level `product/`, `specs/`, `tests/`, and `generated/`. Rejected
  because multiple products would mix their inputs and outputs.
- Commit every generated product. Rejected because products are outputs; only one
  reference example is needed to explain and test the toolchain.

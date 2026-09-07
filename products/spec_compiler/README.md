# Spec Compiler self-description

This bundle describes the externally observable compiler behavior of the
repository's Spec Compiler. `product.toml` adapts the implementation
to Compiler Protocol v1. The generated tests invoke the compiler as a separate
process and do not import `tools.generate`. The contract names the SQL API and
KfW 458 eligibility bundles as separate conformance fixtures, including the
artifacts expected from each compiler profile.

The checked-in `tools/generate.py` is the trusted bootstrap compiler (`G0`). It
materializes `src/spec_compiler.py` as generation `G1` and generates this
bundle's tests. `product.toml` executes G1 through this bundle's own frozen
Python project; it no longer points back to G0. The proofs verify G1's declared
outputs for every conformance fixture, rejection behavior, deterministic
fixpoint, and independent execution.
This establishes executable bootstrap continuity, not an independent proof that
G0 interpreted its own specification correctly.

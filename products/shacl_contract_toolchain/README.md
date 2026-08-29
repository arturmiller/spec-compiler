# SHACL Contract Toolchain self-description

This bundle describes the externally observable compiler behavior of the
repository's SHACL Contract Toolchain. `product.toml` adapts the implementation
to Compiler Protocol v1. The generated tests invoke the compiler as a separate
process and do not import `tools.generate`.

The existing checked-in toolchain is the trusted bootstrap compiler (`G0`). It
generates this bundle's tests, which verify a subsequent invocation (`G1`). This
is self-description and a reproducibility check, not a proof that the bootstrap
compiler interpreted its own specification correctly.

# ADR 0005: Bootstrap the toolchain from an explicit compiler contract

## Status

Accepted.

## Context

The SHACL Contract Toolchain previously generated contracts only for HTTP and
SQLite products. Its own observable behavior—accepted Product Bundles,
generated artifacts, failure behavior, and reproducibility—was documented but
not expressed as a product spec or verified through a generated black-box test.
Treating the existing compiler as proof of its own correctness would be
circular.

## Decision

Introduce **Compiler Protocol v1** as a second product protocol. A compiler
manifest declares a command, working directory, timeout, and the
`{input_product_root}` placeholder. The Contract Verification Harness invokes
that command as a separate process and observes exit status, combined output,
and files written below the input Product Bundle.

`products/shacl_contract_toolchain/` is the versioned **Toolchain
Self-Description Bundle**. Its RDF spec declares the compiler input pattern,
generated artifact patterns, missing-spec rejection, and deterministic output.
The existing checked-in Contract Compiler CLI is the trusted bootstrap compiler
`G0`; it generates the self-description tests and Work Graph. Generated tests
then exercise a fresh compiler invocation `G1` twice and require a byte-identical
artifact fixpoint.

The fixpoint proves reproducibility for the declared example. It does not prove
that `G0` interpreted its own spec correctly or generate a new compiler
implementation.

## Consequences

- The toolchain's external compiler behavior is now specified and tested without
  importing `tools.generate`.
- Product Bundle input paths may be outside the repository, which enables tests
  to compile isolated temporary copies.
- Runtime Protocol v1 and Compiler Protocol v1 remain separate because their
  lifecycle and observation models differ.
- The bootstrap compiler remains in the trusted computing base; independent
  implementations or conformance fixtures are future strengthening steps.

## Alternatives considered

- Model the compiler as an HTTP product. Rejected because HTTP and OpenAPI are
  not part of its actual product interface.
- Claim full self-hosting after two runs of the same implementation. Rejected
  because no new compiler implementation is produced and the bootstrap
  interpretation remains trusted.
- Handwrite the toolchain contract tests. Rejected because that would not test
  whether compiler-product specs can generate executable proofs.

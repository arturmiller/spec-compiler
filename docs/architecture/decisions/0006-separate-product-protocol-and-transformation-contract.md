# ADR 0006: Separate product identity, invocation protocol, and transformation contract

## Status

Accepted. Supersedes the product-typing part of
[ADR 0005](0005-bootstrap-toolchain-self-description.md); its bootstrap trust
boundary and fixpoint decision remain valid.

## Context

ADR 0005 selected compiler-product generation with the RDF class
`ex:ContractCompiler`. That class coupled the identity and domain category of a
product to the protocol used by the harness. It also placed transformation
properties directly on the product. A replacement implementation, another
compiler kind, or one product implementing multiple contracts would make those
concerns difficult to vary independently.

## Decision

Model the three concerns separately:

- the product is a general `schema:SoftwareApplication`;
- `dcterms:conformsTo ex:CompilerProtocolV1` selects its observable invocation
  protocol;
- `ex:implementsContract` links the product to an independently identified,
  versionable `ex:TransformationContract` containing input, output, rejection,
  and equivalence requirements.

The Contract Compiler CLI dispatches on the protocol relation, not on a product
class. Generated proofs derive their obligations from the linked transformation
contract. Different implementations can conform to the same protocol and
implement the same contract; one implementation may later implement multiple
contracts.

`ex:ContractCompiler` is removed from executable dispatch. A domain category
may be added separately for discovery, but it cannot select proof semantics.

## Consequences

- The Python toolchain, a future Rust implementation, or an external compatible
  compiler can be tested against the same transformation contract.
- Compiler Protocol v1 can also invoke other compilers, including a C++
  compiler, provided their domain-specific transformation contract and outcome
  equivalence are expressible.
- Protocol evolution and transformation-contract evolution can be versioned
  independently.
- The current contract still has toolchain-specific properties such as
  `ex:inputSpecPattern`; generalizing individual transformation dimensions is
  deferred until a second compiler domain demonstrates the required vocabulary.

## Alternatives considered

- Retain `ex:ContractCompiler` and add subclasses. Rejected because dispatch
  would remain coupled to a taxonomy rather than an observable protocol.
- Use only `schema:SoftwareApplication`. Rejected because the harness would not
  know how to invoke or verify the product.
- Put all protocol and transformation properties on the product. Rejected
  because implementations and versioned behavioral contracts would not be
  independently reusable.

# ADR 0018: Select the next Fact Question from current Fact Gaps

## Status

Accepted. This decision extends the decision profile established by ADR 0017
and implements Issue #3.

## Context

Decision Conventions v1 can distinguish a missing Fact from a violated
Condition and can therefore return `unknown` with explicit Fact Gaps. It does
not tell a Decision Product which missing Fact to request next. Deriving a
prompt from labels or implementation order would invent wording and selection
semantics, while asking every missing Fact would include questions that no
longer affect a determinate result.

The first interaction slice must remain deterministic, source-backed,
technology-neutral, and observable through the existing stateless Decision
Protocol v1 boundary.

## Decision

- Add the domain-independent **Fact Question** and **Question Flow Case** terms
  to the Decision and Obligation Core Ontology. Every Condition used by the
  current decision profile has exactly one authored Fact Question with explicit
  text and a unique positive priority.
- Define **Question Selection Conventions v1**. A Decision Result contains at
  most one **Next Question**. It is selected only when the current outcome is
  `unknown`, from Fact Questions whose Conditions currently have Fact Gaps, by
  the lowest numeric priority. A violated Condition makes the result
  determinate and suppresses all further questions.
- Compile the selected question's identity, authored text, Condition, Fact
  property, input JSON Pointer, boolean answer schema, and justification into
  the Decision Result. The justification follows the Condition's Rule to its
  Source Citation, immutable Source Revision, locator, and authored source
  statement.
- Require exactly one authored Question Flow Case per Decision Contract. It is
  a complete positive Conformance Case whose Facts supply the answers used by
  a generated multi-step black-box proof.
- Keep interaction stateless. A client adds the answer at the returned JSON
  Pointer and resubmits the complete accumulated Case through another Decision
  Protocol v1 invocation. The protocol does not prescribe a session, UI, or
  conversation framework.
- Keep Decision Protocol v1 unchanged. The transport still exchanges one JSON
  Decision Request and one JSON Decision Result per process invocation;
  Question Selection Conventions v1 version the new selection semantics in the
  compiled Decision Contract and Work Graph.

## Consequences

- Every emitted question is explicit, deterministic, tied to a current Fact
  Gap, and justified by the same source-backed Rule that can affect the
  decision.
- Repeated black-box requests prove progress from an incomplete Case to the
  next justified question or a determinate outcome without importing product
  code.
- Priorities are authored policy, not inferred optimization. The first version
  cannot choose by cost, information gain, user role, branching probability,
  or dependencies between questions.
- Boolean Conditions imply boolean answers in this profile. More expressive
  answers require a later convention rather than an inferred schema.
- A complete positive case is an executable interaction oracle, but it does
  not prove that the question order is optimal or that the authored wording is
  suitable for every audience.

## Alternatives considered

- Use Rule or RDF iteration order. Rejected because storage order is not an
  authored selection policy and can change without domain intent.
- Generate question text from property labels. Rejected because labels are not
  necessarily understandable prompts and would create an untraceable
  requirement.
- Return every Fact Gap as a questionnaire. Rejected because a violated
  Condition may already determine the outcome and because Issue #3 asks for
  the next decision-relevant question.
- Add a stateful conversational protocol. Rejected because the current proof
  needs only repeated complete Case submissions and must not impose session or
  UI architecture.
- Increment Decision Protocol to v2. Rejected because transport and lifecycle
  semantics are unchanged; the new behavior belongs to the independently
  versioned decision contract conventions.

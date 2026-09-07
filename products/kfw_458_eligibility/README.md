# KfW 458 applicant eligibility example

This versioned reference Product Bundle implements the bounded KfW 458
Applicant Eligibility Pilot. Its authored Turtle specs cite the July 2026 KfW
Merkblatt revision and define six boolean Rule Conditions with authored Fact
Questions, two Evidence-applicability Conditions, one independently cited
ownership Evidence Requirement, six Conformance Cases, and the scoped outcomes
`eligible`, `ineligible`, and `unknown`.

The implementation is a technology choice of this example. It reads one JSON
Decision Request from standard input and writes one JSON Decision Result to
standard output through Decision Protocol v1. Generated black-box tests invoke
the manifest and never import `app.py`. When Facts are missing and the outcome
is still `unknown`, the result selects the lowest-priority current Fact Question
and includes its Rule and Source Citation justification. A client adds the
boolean answer at the returned JSON Pointer and submits the complete Case
again; no session or UI is required by the protocol.

For a self-using owner who claims the climate-speed or income bonus, the
Decision Result evaluates the required land-register excerpt independently as
`fulfilled`, `missing`, or `not_applicable`. Supplied Evidence is classified
against the requirement and fulfills it only with a matching type and an
explicit accepted Evidence Assessment. This Evidence evaluation never changes
the ownership Condition or applicant-eligibility outcome. It requires no
particular file format, upload protocol, storage system, or automatic document
inspection.

The result covers only the modeled applicant-eligibility question. It does not
assess heating measures, calculate a subsidy, provide legal or financial advice,
or represent a KfW funding commitment or approval.

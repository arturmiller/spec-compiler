# KfW 458 applicant eligibility example

This versioned reference Product Bundle implements the bounded KfW 458
Applicant Eligibility Pilot. Its authored Turtle specs cite the July 2026 KfW
Merkblatt revision and define six boolean Conditions with authored Fact
Questions, three Conformance Cases, and the scoped outcomes `eligible`,
`ineligible`, and `unknown`.

The implementation is a technology choice of this example. It reads one JSON
Decision Request from standard input and writes one JSON Decision Result to
standard output through Decision Protocol v1. Generated black-box tests invoke
the manifest and never import `app.py`. When Facts are missing and the outcome
is still `unknown`, the result selects the lowest-priority current Fact Question
and includes its Rule and Source Citation justification. A client adds the
boolean answer at the returned JSON Pointer and submits the complete Case
again; no session or UI is required by the protocol.

The result covers only the modeled applicant-eligibility question. It does not
assess heating measures, calculate a subsidy, provide legal or financial advice,
or represent a KfW funding commitment or approval.

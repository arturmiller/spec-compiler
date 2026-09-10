# Cloud privileged-access compliance example

This deliberately small reference Product Bundle evaluates two controls from
NIST SP 800-53 Rev. 5: IA-2 and IA-2(1). It uses the reusable `sdo:` decision,
obligation, provenance, validity, question, and evidence concepts while every
cloud-specific type, fact property, and outcome remains in the separate
`cloud:` Domain Ontology.

The product reads a JSON Decision Request from standard input and writes one
JSON Decision Result to standard output through Decision Protocol v1. Generated
black-box tests invoke only the manifest boundary. Results contain
source-backed Condition Evaluations, Rule-imposed Obligation Evaluations, the
next decision-relevant Fact Question, and an independently evaluated MFA
mechanism Evidence Requirement sourced from NIST SP 800-53A Rev. 5.

The scope is intentionally narrow. A `satisfied` result covers only the two
authored controls against supplied boolean system-profile facts. It is not a
complete NIST assessment, certification, provider configuration scan,
remediation plan, or security guarantee.

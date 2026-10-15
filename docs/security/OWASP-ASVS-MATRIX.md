# ASVS verification matrix

Target: risk-based ASVS 5.0.0 Level 2, with selected L3 media/quota controls.
This is an internal verification framework, **not certification**. The CSV
inventories all 345 official requirements, their level, applicability,
procedure, evidence, result, remediation and residual uncertainty. Requirement
descriptions are from the [tagged OWASP ASVS 5.0.0 source](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en),
licensed under CC BY-SA 4.0; attribution and that license apply to those rows.

Only individually inspected clauses receive PASS/PARTIAL/FAIL. NOT TESTED is
intentional where broad suite success cannot establish complete verification.
L3 requirements are retained for risk review; they are not all part of the L2
target. WebRTC and archive-upload processing are inapplicable to current flows.

Major remaining gaps: CSP/frame-ancestors, password breach/common-password
checks, administrator MFA, least-privilege runtime database access, verified
recovery/monitoring and browser-worker network isolation. Cross-user integration
coverage does not justify marking every authorization requirement PASS.

Complementary references: [OWASP API Security](https://owasp.org/www-project-api-security/),
[WSTG](https://owasp.org/www-project-web-security-testing-guide/),
[Cheat Sheets](https://cheatsheetseries.owasp.org/),
[NIST SSDF](https://csrc.nist.gov/Projects/ssdf),
[CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks),
[PCI SSC](https://www.pcisecuritystandards.org/).
These references guide the review; no formal CIS or PCI assessment was performed.

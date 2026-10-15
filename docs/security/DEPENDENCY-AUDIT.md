# Dependency audit — 2026-10-15

Audited source: `8625775cafdd8ca58086a55294fc5f2309ccbe2b`.

`pip-audit` reported 17 advisories across PyJWT 2.13.0 and urllib3 2.7.0.
The constrained graph with PyJWT 2.15.0 and urllib3 2.8.0 reports **zero known
vulnerabilities**. `npm audit` reported GHSA-68fv-2mgg-jv7q in build dependency
source-map-js 1.2.1; updating only that lock entry to 1.2.2 reports zero findings.
These are minor/patch updates; stateful images and migration files are unchanged.

Do not equate package advisories with 17 confirmed exploitable application bugs.
The API uses an HS256-only algorithm allowlist and constructs fresh decode options;
the mixed asymmetric/HMAC and shared mutable-options prerequisites are absent in
the reviewed token resolver. Malformed-token parsing still justifies updating.
Google OAuth uses google-auth verification. urllib3 is also used by boto3 and
requests; the update protects outbound transport at those boundaries.

Verification: frontend lint, typecheck, production build, bundle policy and
production dependency policy pass locally. Baseline unit suite: 724 passed,
3 skipped. Updated dependency compatibility and real PostgreSQL/payment suites
are recorded in the subsequent hardening PR and its CI; merge only after this
PR's applicable checks pass. No production changes or financial provider calls.

Reproduce:

```sh
python -m pip_audit -r backend/constraints.txt --no-deps --disable-pip
npm audit
npm run test:security
```

`--no-deps --disable-pip` scans every exact constraint without installing
platform-specific packages. It does not verify runtime image OS packages or
unlisted dependencies. Vulnerability databases change; zero is a dated result.

Primary references: [PyJWT releases](https://github.com/jpadilla/pyjwt/releases),
[urllib3 advisories](https://github.com/urllib3/urllib3/security/advisories),
[source-map-js advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

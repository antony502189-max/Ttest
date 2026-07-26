# Staged mobile validation

- started: PASS
- npm ci: PASS (exit 0)

added 447 packages, and audited 448 packages in 9s

120 packages are looking for funding
  run `npm fund` for details

6 vulnerabilities (3 moderate, 3 high)

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
- lint: PASS (exit 0)

> task@0.0.0 lint
> oxlint

::warning file=tests/mobile-map-ideal.spec.ts,line=25,endLine=25,col=16,endColumn=42,title=eslint(no-unused-vars)::Function 'revealVisibleListingMarker' is declared but never used.

Found 1 warning and 0 errors.
Finished in 35ms on 112 files with 102 rules using 4 threads.

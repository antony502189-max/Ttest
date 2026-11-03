# PR404 remediation evidence

Final runtime source: **2f442dc75188b3d7f7362aea087fd5ab7d7fdaf3**. Files ending
`-final` are the final packaging/targeted runs; unsuffixed earlier composition
artifacts retain the previous **53b077** run rather than overwriting it.
Backend app/tests and frontend contract input trees did not change between those
runs; full unit/HomeAI/build-matrix results retain their original scope.

`provenance.json` records actual Docker immutable image IDs, frontend build-info,
backend attestation, source archive digest, internal network and runtime input
Git trees/blobs. Driver SHA256 fields describe the Windows working-file bytes
actually executed (CRLF may differ from cloned LF text); Git source equality is
checked separately by `runtimeProjection`. CI runs
`scripts/verify-ai-lab-provenance.mjs`, verifies the current checkout projection
and these artifact hashes, and uploads one combined provenance/evidence artifact.
CI does not pretend to rerun the local Docker Desktop stack.

The mixed-release tests require FAIL before any query: their negative report is
not a failed model smoke. The fake-LIVE test root always constructs MockTransport,
a dummy key and its own DISPOSABLE journal. Artificial51→54 history must never be
confused with the real retained journal, which remains52/$0.575120.

No new paid/model HTTP request, real key, actual signed owner authorization,
provider account evidence or real journal contents are included. Existing
provider/LIVE failure evidence remains unchanged in its separate directory.

`SHA256.json` covers exact published bytes. This directory is marked `-text` to
preserve Windows line endings; verify bytes without newline conversion.

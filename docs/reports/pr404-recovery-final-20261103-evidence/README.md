# Final recovery-safe PR404 acceptance

Runtime source **72468b2e72bef1deeae7bfb18dee22de4e3c7baf**. This packet supersedes
the earlier runtime projection for acceptance without replacing its raw files.
It includes the two regression failures before the recovery fix, seven passing
pairing/recovery tests, a repeated56-case HomeAI suite and15-case real stack suite.

The final paired fake-LIVE positive run uses an existing synthetic auth account
via normal UI login. It is **not** a three-new-guests issuance test. The repeated
guest run was stopped by the real hourly identity limit after two fake cases;
that partial report is retained. No guest buckets, quotas or real budget journal
were reset. Failed auxiliary auth harness attempts remain under output; the
successful auth harness is included verbatim as a data artifact with its hash.
Its password is the public local synthetic fixture, not a real account secret.
No access token, provider key, actual signed release or real SQLite is published.

All model completions are MockTransport responses in an internal Docker network,
with a dedicated DISPOSABLE artificial-history journal per fake test instance.
The real journal remains52/$0.575120; no new paid calls were made.

`provenance.json` records immutable image IDs, compiled frontend and actual backend
attestation, source archive and drivers. Driver hashes cover the Windows bytes
actually executed; Git trees/blobs in runtimeProjection verify source equality
across later documentation-only heads. CI verifies and uploads this packet; it
does not claim to rerun the local Docker Desktop stack.

`SHA256.json` covers exact bytes. Git `-text` preserves captured line endings.

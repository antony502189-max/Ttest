"""DISPOSABLE fixtures only. Never a release signer/trust root or real journal.

No helper is imported by closed_ui_entry. Generated test public keys are not
accepted by an independently pinned real release authority.
"""
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lab.closed_ui_authorization import CASE_IDS, CORPUS_SHA256, canonical, identity, verify

SOURCE = "a" * 40


def signed_fixture(path, *, source=SOURCE, **changes):
    if not path.name.startswith("DISPOSABLE-"):
        raise ValueError("only explicitly DISPOSABLE fixture files permitted")
    now = datetime.now(UTC)
    journal = identity(path)
    data = {"schema": "ai-closed-ui-authorization.v1", "authorization_id": uuid4().hex,
            "journal_id": hashlib.sha256(canonical(journal)).hexdigest()[:32],
            "source": source, "frontend_source": source, "corpus_sha256": CORPUS_SHA256,
            "issued_at": (now - timedelta(seconds=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
            "host_journal": journal, "runtime_journal": journal, "baseline_attempts": 51,
            "baseline_reserved_micro_usd": 564060, "case_ids": list(CASE_IDS), "prior_case_attempts": {},
            "max_new_attempts": 3, "max_new_reserved_micro_usd": 33180,
            "backend_image": "sha256:" + "b" * 64, "frontend_image": "sha256:" + "c" * 64,
            "external_cap_micro_usd": 750000, "external_cap_evidence_sha256": "d" * 64}
    data.update(changes)
    signer = Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    document = json.dumps({"payload": data, "signature": base64.b64encode(signer.sign(canonical(data))).decode()}).encode()
    pin = hashlib.sha256(public).hexdigest()
    return document, public, pin


def admission_fixture(path, **changes):
    document, public, pin = signed_fixture(path, **changes)
    return verify(document, public, trusted_key_sha256=pin, source=changes.get("source", SOURCE))

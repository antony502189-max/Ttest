"""External owner-signed release admission. No production signer/key generator.

The independent trust-key fingerprint is configured out of repository by the
release custodian. This protects operational admission, not a malicious host
administrator able to replace images, trust roots and mounts. Never self-sign
an authorization as a consequence of an environment approval string.
"""
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.services.ai_deepseek_intent import ProviderFailure, _strict_json

CASE_IDS = ("ru-balcony", "es-monthly", "en-negation")
CORPUS_SHA256 = "7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288"


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def identity(path):
    path = Path(path).resolve(strict=True)
    stat = path.stat()
    return {"path": str(path), "device": stat.st_dev, "inode": stat.st_ino}


@dataclass(frozen=True)
class Admission:
    # Store canonical immutable bytes: callers cannot change a verified dict.
    payload: bytes
    digest: str

    @property
    def data(self):
        return json.loads(self.payload)

    def check_time(self):
        data = self.data
        now = datetime.now(UTC)
        if not datetime.fromisoformat(data["issued_at"]) <= now < datetime.fromisoformat(data["expires_at"]):
            raise ProviderFailure("UI_AUTHORIZATION_EXPIRED")

    def check_journal(self, path, *, host=False):
        self.check_time()
        expected = self.data["host_journal" if host else "runtime_journal"]
        actual = identity(path)
        if actual != expected:
            raise ProviderFailure("UI_JOURNAL_IDENTITY_MISMATCH")


def verify(document: bytes, public_key: bytes, *, trusted_key_sha256: str, source: str) -> Admission:
    try:
        if len(document) > 16384 or len(public_key) != 32 or not re.fullmatch(r"[0-9a-f]{64}", trusted_key_sha256):
            raise ValueError
        if hashlib.sha256(public_key).hexdigest() != trusted_key_sha256:
            raise ValueError
        envelope = _strict_json(document)
        if set(envelope) != {"payload", "signature"}:
            raise ValueError
        data = envelope["payload"]
        fields = {"schema", "authorization_id", "journal_id", "source", "frontend_source", "corpus_sha256",
                  "issued_at", "expires_at", "host_journal", "runtime_journal", "baseline_attempts",
                  "baseline_reserved_micro_usd", "case_ids", "prior_case_attempts", "max_new_attempts",
                  "max_new_reserved_micro_usd", "backend_image", "frontend_image", "external_cap_micro_usd",
                  "external_cap_evidence_sha256"}
        if set(data) != fields or data["schema"] != "ai-closed-ui-authorization.v1":
            raise ValueError
        for key in ("authorization_id", "journal_id"):
            if not re.fullmatch(r"[0-9a-f]{32}", data[key]):
                raise ValueError
        if not re.fullmatch(r"[0-9a-f]{40}", source or "") or data["source"] != source or data["frontend_source"] != source:
            raise ValueError
        if data["corpus_sha256"] != CORPUS_SHA256:
            raise ValueError
        for key in ("backend_image", "frontend_image"):
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", data[key]):
                raise ValueError
        if not re.fullmatch(r"[0-9a-f]{64}", data["external_cap_evidence_sha256"]):
            raise ValueError
        if type(data["external_cap_micro_usd"]) is not int or not 0 < data["external_cap_micro_usd"] <= 750000:
            raise ValueError
        for key in ("host_journal", "runtime_journal"):
            item = data[key]
            if set(item) != {"path", "device", "inode"} or not isinstance(item["path"], str):
                raise ValueError
            if any(type(item[x]) is not int or item[x] < 0 for x in ("device", "inode")) or not item["inode"]:
                raise ValueError
        baseline, count = data["baseline_attempts"], data["max_new_attempts"]
        if type(baseline) is not int or type(count) is not int or not 51 <= baseline < baseline + count <= 54:
            raise ValueError
        if type(data["baseline_reserved_micro_usd"]) is not int or data["baseline_reserved_micro_usd"] != baseline * 11060:
            raise ValueError
        if data["max_new_reserved_micro_usd"] != count * 11060 or type(data["max_new_reserved_micro_usd"]) is not int:
            raise ValueError
        if not isinstance(data["case_ids"], list) or len(data["case_ids"]) != count or len(set(data["case_ids"])) != count:
            raise ValueError
        if not set(data["case_ids"]) <= set(CASE_IDS):
            raise ValueError
        prior = data["prior_case_attempts"]
        if not isinstance(prior, dict) or not set(prior) <= set(CASE_IDS) or set(prior) & set(data["case_ids"]):
            raise ValueError
        if any(type(n) is not int or not 51 < n <= baseline for n in prior.values()) or len(set(prior.values())) != len(prior):
            raise ValueError
        # Reconcile every post-eval historical attempt; no resetting an ambiguous case.
        if set(prior.values()) != set(range(52, baseline + 1)):
            raise ValueError
        start, end = (datetime.fromisoformat(data[k]) for k in ("issued_at", "expires_at"))
        if start.utcoffset() is None or end.utcoffset() is None or not 0 < (end - start).total_seconds() <= 3600:
            raise ValueError
        blob = canonical(data)
        Ed25519PublicKey.from_public_bytes(public_key).verify(base64.b64decode(envelope["signature"], validate=True), blob)
        admission = Admission(blob, hashlib.sha256(blob).hexdigest())
        admission.check_time()
        return admission
    except (ValueError, TypeError, KeyError, InvalidSignature, OverflowError):
        raise ProviderFailure("UI_SIGNED_AUTHORIZATION_REQUIRED") from None


def host_preflight(admission, journal, backend_image, frontend_image):
    """Read-only host check, using actual docker inspect image IDs, not labels."""
    admission.check_journal(journal, host=True)
    if (backend_image, frontend_image) != (admission.data["backend_image"], admission.data["frontend_image"]):
        raise ProviderFailure("UI_IMAGE_IDENTITY_MISMATCH")


if __name__ == "__main__":
    import argparse

    cli = argparse.ArgumentParser(description="Read-only verification; never signs or mutates a journal")
    for argument in ("admission", "authority", "trusted-key-sha256", "source", "journal", "backend-image", "frontend-image"):
        cli.add_argument("--" + argument, required=True)
    args = cli.parse_args()
    verified = verify(Path(args.admission).read_bytes(), Path(args.authority).read_bytes(),
                      trusted_key_sha256=args.trusted_key_sha256, source=args.source)
    host_preflight(verified, args.journal, args.backend_image, args.frontend_image)
    print(json.dumps({key: verified.data[key] for key in (
        "source", "case_ids", "baseline_attempts", "baseline_reserved_micro_usd",
        "max_new_attempts", "max_new_reserved_micro_usd")}))

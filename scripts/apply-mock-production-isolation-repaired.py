from __future__ import annotations

import base64
import hashlib
import runpy
import subprocess
import zlib
from pathlib import Path

HELPER = Path("scripts/apply-mock-production-isolation.py")
PATCH_PATH = Path("/tmp/mock-isolation.patch")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover_patch(encoded: str, expected_hash: str) -> bytes:
    compact = "".join(encoded.split())
    candidates = [compact]
    if len(compact) % 4 == 1:
        candidates = [compact[:index] + compact[index + 1 :] for index in range(len(compact))]

    for candidate in candidates:
        try:
            compressed = base64.b64decode(candidate, validate=True)
            patch = zlib.decompress(compressed)
        except (ValueError, zlib.error):
            continue
        if hashlib.sha256(patch).hexdigest() == expected_hash:
            return patch
    raise SystemExit("unable to recover the reviewed patch with its expected SHA-256")


def main() -> None:
    values = runpy.run_path(str(HELPER))
    expected: dict[str, str] = values["EXPECTED"]
    for name, expected_hash in expected.items():
        path = Path(name)
        if not path.is_file() or digest(path) != expected_hash:
            raise SystemExit(f"source hash mismatch: {name}")
    for name in ("src/data/mock-listings.ts", "src/contexts/mock-app-provider.production.tsx"):
        if Path(name).exists():
            raise SystemExit(f"new file already exists: {name}")

    patch = recover_patch(values["PATCH_ZLIB_BASE64"], values["EXPECTED_PATCH_SHA256"])
    PATCH_PATH.write_bytes(patch)
    subprocess.run(["git", "apply", "--check", str(PATCH_PATH)], check=True)
    subprocess.run(["git", "apply", str(PATCH_PATH)], check=True)


if __name__ == "__main__":
    main()

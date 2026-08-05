#!/usr/bin/env python3
"""Print non-secret fingerprints for resolved stateful Compose services."""

import hashlib
import json
import sys


config = json.load(sys.stdin)
services = config.get("services")
if not isinstance(services, dict):
    raise SystemExit("Compose config has no services object")

for name in ("postgres", "redis", "minio"):
    service = services.get(name)
    if not isinstance(service, dict):
        raise SystemExit(f"Compose config is missing the {name} service")
    image = service.get("image")
    if not isinstance(image, str) or "@sha256:" not in image:
        raise SystemExit(f"{name} must use an immutable digest-pinned image")
    canonical = json.dumps(service, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    contract_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    print(f"{name} image={image} contract_sha256={contract_hash}")

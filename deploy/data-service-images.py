#!/usr/bin/env python3
"""Print non-secret fingerprints for resolved stateful Compose services."""

import argparse
import hashlib
import json
import subprocess
import sys


OFFICIAL_REPOSITORY_ALIASES = {
    "quay.io/minio/minio": "minio/minio",
    "quay.io/minio/mc": "minio/mc",
}


def repository_name(image: str) -> str:
    reference = image.split("@", 1)[0]
    slash = reference.rfind("/")
    colon = reference.rfind(":")
    return reference[:colon] if colon > slash else reference


def canonical_repository_name(image: str) -> str:
    repository = repository_name(image)
    return OFFICIAL_REPOSITORY_ALIASES.get(repository, repository)


def canonical_digest_reference(image: str) -> str:
    repository, separator, digest = image.partition("@")
    if separator != "@" or not digest.startswith("sha256:"):
        raise SystemExit(f"image is not an immutable digest reference: {image}")
    return f"{canonical_repository_name(repository)}@{digest}"


def resolve_local_digest(image: str) -> str:
    if "@sha256:" in image:
        return canonical_digest_reference(image)
    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(f"cannot resolve legacy local image reference: {image}")
    try:
        repo_digests = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Docker returned invalid repo digests for legacy image: {image}") from exc
    if not isinstance(repo_digests, list):
        raise SystemExit(f"Docker returned no repo digests for legacy image: {image}")
    requested_repository = canonical_repository_name(image)
    candidates = {
        canonical_digest_reference(digest)
        for digest in repo_digests
        if isinstance(digest, str)
        and "@sha256:" in digest
        and canonical_repository_name(digest) == requested_repository
    }
    if len(candidates) != 1:
        raise SystemExit(f"legacy image must resolve to exactly one immutable digest: {image}")
    return candidates.pop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resolve-local-tags",
        action="store_true",
        help="resolve legacy tag-only image references from the local Docker image store",
    )
    args = parser.parse_args()
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
            if not args.resolve_local_tags or not isinstance(image, str):
                raise SystemExit(f"{name} must use an immutable digest-pinned image")
            image = resolve_local_digest(image)
        else:
            image = canonical_digest_reference(image)
        # Persistent-data migrations are required only when the actual digest
        # changes. Explicitly trusted official registry aliases with the same
        # digest represent the same immutable image content.
        canonical = json.dumps({"image": image}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        contract_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        print(f"{name} image={image} contract_sha256={contract_hash}")


if __name__ == "__main__":
    main()

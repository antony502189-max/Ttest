#!/usr/bin/env python3
"""Fail CI when audited supply-chain pins are weakened."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
ACTION_USE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
CONTAINER_DIGEST = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
DOCKER_FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)", re.IGNORECASE | re.MULTILINE)
COMPOSE_IMAGE = re.compile(r"^\s*image:\s*([^\s#]+)", re.MULTILINE)
DOCKER_RUN = re.compile(r"\bdocker\s+run\b")
PINNED_IMAGE_IN_COMMAND = re.compile(r"[^\s\'\"]+@sha256:[0-9a-f]{64}")
# CI may launch an image that was built earlier in the same job by its Docker
# image ID.  That `sha256:` ID is content-addressed, unlike a mutable tag.
LOCAL_IMAGE_ID_RUN = re.compile(r"\bdocker\s+run\b.*\$image_id")
LOCAL_IMAGE_ID_ASSIGNMENT = 'image_id="$(docker image inspect --format \'{{.Id}}\''


def fail(message: str) -> None:
    raise SystemExit(message)


def check_workflows() -> None:
    workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    if not workflows:
        fail("no GitHub Actions workflows found")

    for path in workflows:
        content = path.read_text(encoding="utf-8")
        if "runs-on: ubuntu-latest" in content:
            fail(f"{path.relative_to(ROOT)} uses a floating runner image")
        for action in ACTION_USE.findall(content):
            # Local actions are part of the checked-out repository. All remote
            # actions must be immutable commit references, never mutable tags.
            if action.startswith("./"):
                continue
            if not FULL_SHA.fullmatch(action):
                fail(f"{path.relative_to(ROOT)} uses an unpinned action: {action}")
        if "actions/checkout@" in content and "persist-credentials: false" not in content:
            fail(f"{path.relative_to(ROOT)} checkout persists the workflow token")


def check_backend_constraints() -> None:
    constraints = ROOT / "backend" / "constraints.txt"
    dockerfile = ROOT / "backend" / "Dockerfile"
    production_workflow = WORKFLOW_DIR / "production-audit.yml"

    if not constraints.is_file() or not constraints.read_text(encoding="utf-8").strip():
        fail("backend/constraints.txt is missing or empty")
    lines = [line.strip() for line in constraints.read_text(encoding="utf-8").splitlines()]
    packages = [line for line in lines if line and not line.startswith("#")]
    if any("==" not in line or line.count("==") != 1 for line in packages):
        fail("every backend constraint must use one exact == version")
    names = [line.split("==", 1)[0].casefold() for line in packages]
    if len(names) != len(set(names)):
        fail("backend constraints contain duplicate package names")

    if "pip install --constraint constraints.txt ." not in dockerfile.read_text(encoding="utf-8"):
        fail("backend Dockerfile does not install through constraints.txt")
    workflow_text = production_workflow.read_text(encoding="utf-8")
    if "--constraint backend/constraints.txt" not in workflow_text or "python -m pip check" not in workflow_text:
        fail("Production audit does not enforce the backend dependency graph")


def check_container_images() -> None:
    dockerfiles = sorted(ROOT.rglob("Dockerfile*"))
    if not dockerfiles:
        fail("no Dockerfiles found")
    for path in dockerfiles:
        content = path.read_text(encoding="utf-8")
        for image in DOCKER_FROM.findall(content):
            if image.casefold() == "scratch":
                continue
            if not CONTAINER_DIGEST.fullmatch(image):
                fail(f"{path.relative_to(ROOT)} uses an unpinned base image: {image}")

    compose_files = [ROOT / "docker-compose.yml", ROOT / "docker-compose.production.yml"]
    for path in compose_files:
        if not path.is_file():
            fail(f"missing compose file: {path.relative_to(ROOT)}")
        for image in COMPOSE_IMAGE.findall(path.read_text(encoding="utf-8")):
            if not CONTAINER_DIGEST.fullmatch(image):
                fail(f"{path.relative_to(ROOT)} uses an unpinned service image: {image}")


def check_docker_run_images() -> None:
    paths = sorted(ROOT.rglob("*.sh")) + sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    for path in paths:
        content = path.read_text(encoding="utf-8").replace("\\\n", " ")
        for line_number, line in enumerate(content.splitlines(), start=1):
            local_image_id = LOCAL_IMAGE_ID_RUN.search(line)
            if local_image_id and LOCAL_IMAGE_ID_ASSIGNMENT not in content:
                fail(f"{path.relative_to(ROOT)} uses an unverified local image ID")
            if DOCKER_RUN.search(line) and not (PINNED_IMAGE_IN_COMMAND.search(line) or local_image_id):
                fail(f"{path.relative_to(ROOT)}:{line_number} uses docker run without an immutable image digest")


def main() -> None:
    check_workflows()
    check_backend_constraints()
    check_container_images()
    check_docker_run_images()
    print("Supply-chain pins are valid")


if __name__ == "__main__":
    main()

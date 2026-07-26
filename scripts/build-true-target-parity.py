#!/usr/bin/env python3
"""Build target/actual/overlay/diff boards and the V4 parity acceptance table."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "artifacts" / "final-parity"
STATES = ("035", "037", "042", "043", "045", "057", "060", "063", "066", "090")
BLOCKING_STATES = {"060", "063", "066", "090"}


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidate = Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")
    return ImageFont.truetype(str(candidate), size) if candidate.exists() else ImageFont.load_default()


def board(state: str, images: list[Image.Image], labels: list[str]) -> Path:
    gap, label_height = 8, 38
    output = Image.new("RGB", (sum(image.width for image in images) + gap * (len(images) - 1), 844 + label_height), "white")
    draw = ImageDraw.Draw(output)
    x = 0
    for image, label in zip(images, labels):
        draw.text((x + 8, 10), label, fill="black", font=font(15, True))
        output.paste(image, (x, label_height))
        x += image.width + gap
    destination = PARITY / "reports" / "boards" / f"{state}.jpg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination, quality=92)
    return destination


def geometry_pass(report: dict) -> bool:
    target = report.get("target", {})
    actual = report.get("actual", {})
    for name, expected in target.items():
        current = actual.get(name)
        if expected is None:
            if current is not None:
                return False
            continue
        if current is None:
            return False
        if abs(current["x"] - expected["x"]) > 4 or abs(current["y"] - expected["y"]) > 4:
            return False
        if abs(current["width"] - expected["width"]) > 6 or abs(current["height"] - expected["height"]) > 6:
            return False
    viewport = report.get("viewport", {})
    return viewport.get("documentWidth", 10_000) <= viewport.get("width", 0) + 1


def main() -> None:
    for directory in ("overlays", "diffs", "reports"):
        (PARITY / directory).mkdir(parents=True, exist_ok=True)
    manual_path = PARITY / "reports" / "manual-review.json"
    manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else {}
    rows: list[dict[str, object]] = []
    board_paths: list[Path] = []

    for state in STATES:
        target_path = PARITY / "target" / f"{state}-target.png"
        actual_path = PARITY / "actual" / f"{state}-actual.png"
        geometry_path = PARITY / "geometry" / f"{state}-geometry.json"
        if not target_path.exists() or not actual_path.exists() or not geometry_path.exists():
            raise FileNotFoundError(f"Missing target, actual, or geometry artifact for state {state}")
        target = Image.open(target_path).convert("RGB")
        actual = Image.open(actual_path).convert("RGB")
        if actual.size != target.size:
            raise ValueError(f"State {state} dimensions differ: target={target.size}, actual={actual.size}")
        overlay = Image.blend(target, actual, .5)
        raw_diff = ImageChops.difference(target, actual)
        heatmap = ImageEnhance.Contrast(raw_diff).enhance(4)
        overlay_path = PARITY / "overlays" / f"{state}-overlay.png"
        diff_path = PARITY / "diffs" / f"{state}-diff.png"
        overlay.save(overlay_path)
        heatmap.save(diff_path)
        board_paths.append(board(state, [target, actual, overlay, heatmap], ["TARGET", "ACTUAL", "OVERLAY 50%", "DIFF ×4"]))

        geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
        geometry_status = "PASS" if geometry_pass(geometry) else "FAIL"
        review = manual.get(state, {})
        overlay_status = review.get("overlay", "PENDING")
        manual_status = review.get("manualReview", "PENDING")
        status = "PASS" if geometry_status == overlay_status == manual_status == "PASS" else "FAIL" if "FAIL" in {geometry_status, overlay_status, manual_status} else "PENDING"
        rows.append({
            "state": state,
            "blocking": state in BLOCKING_STATES,
            "target": target_path.relative_to(ROOT).as_posix(),
            "actual": actual_path.relative_to(ROOT).as_posix(),
            "overlay": overlay_path.relative_to(ROOT).as_posix(),
            "diff": diff_path.relative_to(ROOT).as_posix(),
            "geometry": geometry_path.relative_to(ROOT).as_posix(),
            "meanAbsoluteRgbDiff": round(sum(ImageStat.Stat(raw_diff).mean) / 3, 3),
            "geometryStatus": geometry_status,
            "overlayStatus": overlay_status,
            "manualReview": manual_status,
            "status": status,
            "notes": review.get("notes", "Manual side-by-side review not recorded."),
        })

    report_dir = PARITY / "reports"
    with (report_dir / "visual-parity.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "protocol": "requirements/TRUE_VISUAL_PARITY_PROTOCOL.md",
        "masking": "None. Raw target and actual images are retained; no map UI, markers, clusters, polygons, controls, typography, shadows, or spacing are masked.",
        "states": rows,
        "blockingStatesPass": all(row["status"] == "PASS" for row in rows if row["blocking"]),
        "allStatesPass": all(row["status"] == "PASS" for row in rows),
    }
    (report_dir / "visual-parity.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    thumbs = [Image.open(path).convert("RGB").resize((390, 220), Image.Resampling.LANCZOS) for path in board_paths]
    contact = Image.new("RGB", (780, 1100), "white")
    for index, thumb in enumerate(thumbs):
        contact.paste(thumb, ((index % 2) * 390, (index // 2) * 220))
    contact.save(report_dir / "contact-sheet.jpg", quality=90)
    print(json.dumps({"states": len(rows), "blockingStatesPass": summary["blockingStatesPass"], "allStatesPass": summary["allStatesPass"]}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build normalized V4 target images and exact-design evidence artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat


ROOT = Path(__file__).resolve().parents[1]


def normalize_target(source: Path, destination: Path, size: tuple[int, int] = (390, 844)) -> Image.Image:
    image = Image.open(source).convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    normalized = resized.crop((0, 0, size[0], size[1]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(destination)
    return normalized


def fit_current(source: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(source).convert("RGB")
    if image.size == size:
        return image
    canvas = Image.new("RGB", size, "white")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas.paste(image, (0, 0))
    return canvas


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def board(images: list[Image.Image], labels: list[str], destination: Path) -> None:
    label_height = 42
    gap = 8
    width = sum(image.width for image in images) + gap * (len(images) - 1)
    height = max(image.height for image in images) + label_height
    output = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(output)
    x = 0
    for image, label in zip(images, labels):
        draw.text((x + 8, 10), label, fill="black", font=font(16, True))
        output.paste(image, (x, label_height))
        x += image.width + gap
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination, quality=94)


def contact_sheet(paths: list[Path], destination: Path, columns: int = 4) -> None:
    """Create a legible all-golden review surface without altering source evidence."""
    thumb_size = (195, 422)
    label_height = 28
    rows = (len(paths) + columns - 1) // columns
    output = Image.new("RGB", (columns * thumb_size[0], rows * (thumb_size[1] + label_height)), "white")
    draw = ImageDraw.Draw(output)
    for position, source in enumerate(paths):
        image = Image.open(source).convert("RGB")
        image = ImageOps.fit(image, thumb_size, method=Image.Resampling.LANCZOS)
        x = (position % columns) * thumb_size[0]
        y = (position // columns) * (thumb_size[1] + label_height)
        output.paste(image, (x, y + label_height))
        draw.text((x + 7, y + 6), source.stem, fill="black", font=font(14, True))
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination, quality=94)


def content_mask(index: int, destination: Path, size: tuple[int, int]) -> None:
    """Document only allowed dynamic raster/system regions; white geometry remains reviewable."""
    mask = Image.new("L", size, 255)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((0, 0, size[0], 20), fill=0)
    draw.rectangle((0, size[1] - 50, size[0], size[1]), fill=0)
    if index in {19, 24, 32, 92, 112, 114}:
        draw.rectangle((2, 96, size[0] - 3, 267), fill=0)
    if index in {45, 57}:
        draw.rectangle((8, 193, size[0] - 9, 475), fill=0)
    if index in {68, 69, 73, 76, 80, 83, 84, 86}:
        draw.rectangle((2, 68, size[0] - 3, 413), fill=0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    mask.save(destination)


def sequence_review(pack: Path, index: int, timestamp: float, destination: Path) -> None:
    """Build the mandated ±2.5 s sequence and top/middle/bottom crop review board."""
    dense = pack / "screenshots" / "08_dense_full_frames" / "video_C_customer_final"
    crops = pack / "screenshots" / "09_dense_crops" / "video_C_customer_final"
    full_count = len(list(dense.glob("frame_*.jpg")))
    center = round(timestamp * 2) + 1
    frame_indices = [min(full_count, max(1, center + offset)) for offset in range(-5, 6)]
    thumb_size = (118, 256)
    label_height = 30
    columns = 6
    rows = 2
    canvas = Image.new("RGB", (columns * thumb_size[0], rows * (thumb_size[1] + label_height) + 164), "white")
    draw = ImageDraw.Draw(canvas)
    for position, frame_index in enumerate(frame_indices):
        image = Image.open(dense / f"frame_{frame_index:05d}.jpg").convert("RGB")
        image = ImageOps.fit(image, thumb_size, method=Image.Resampling.LANCZOS)
        x = (position % columns) * thumb_size[0]
        y = (position // columns) * (thumb_size[1] + label_height)
        seconds = (frame_index - 1) / 2
        is_center = frame_index == center
        canvas.paste(image, (x, y + label_height))
        draw.text((x + 5, y + 7), f"{seconds:05.1f}s", fill="#d10a7e" if is_center else "black", font=font(13, is_center))
        if is_center:
            draw.rectangle((x + 1, y + label_height + 1, x + thumb_size[0] - 2, y + label_height + thumb_size[1] - 2), outline="#d10a7e", width=4)
    crop_index = min(220, max(1, round(timestamp) + 1))
    crop_width = canvas.width // 3
    crop_y = rows * (thumb_size[1] + label_height)
    for column, region in enumerate(("top", "middle", "bottom")):
        crop = Image.open(crops / region / f"frame_{crop_index:05d}.jpg").convert("RGB")
        crop = ImageOps.fit(crop, (crop_width, 130), method=Image.Resampling.LANCZOS)
        x = column * crop_width
        canvas.paste(crop, (x, crop_y + 34))
        draw.text((x + 7, crop_y + 8), region.upper(), fill="black", font=font(14, True))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=92)


def after_v2_name(index: int) -> str:
    mapping = {
        19: "home-390x844.png", 24: "home-390x844.png", 32: "home-390x844.png",
        35: "location-390x844.png", 37: "map-draw-instruction-390x844.png",
        42: "map-draw-instruction-390x844.png", 43: "search-map-390x844.png",
        45: "selected-zone-results-390x844.png", 46: "filters-top-390x844.png",
        49: "filters-middle-390x844.png", 53: "filters-bottom-390x844.png",
        55: "filters-bottom-390x844.png", 57: "search-list-390x844.png",
        60: "search-map-390x844.png", 63: "search-map-390x844.png",
        66: "map-selected-listing-390x844.png", 68: "listing-390x844.png",
        69: "listing-comments-390x844.png", 73: "listing-390x844.png",
        76: "listing-390x844.png", 80: "listing-comments-390x844.png",
        83: "listing-comments-390x844.png", 84: "listing-comments-390x844.png",
        86: "listing-comments-390x844.png", 90: "map-selected-listing-390x844.png",
        92: "home-390x844.png", 96: "menu-390x844.png",
        100: "owner-edit-390x844.png", 105: "owner-edit-390x844.png",
        109: "owner-listings-390x844.png", 112: "home-saved-search-390x844.png",
        114: "home-saved-search-390x844.png",
    }
    return mapping[index]


def live_image(directory: Path, index: int) -> Path:
    matches = sorted(directory.glob(f"{index:03d}-*.png"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one live image for golden {index}, found {len(matches)} in {directory}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()

    evidence = ROOT / "artifacts" / "v4-exact-design"
    target_dir = evidence / "target"
    after_v2_dir = ROOT / "artifacts" / "screenshot-locked" / "after-live"
    before_dir = evidence / "before"
    after_dir = evidence / "after"
    rows = []
    overlay_paths: list[Path] = []
    diff_paths: list[Path] = []

    with (args.pack / "SCREEN_CONTRACT.csv").open(encoding="utf-8-sig", newline="") as handle:
        contract = [row for row in csv.DictReader(handle) if row["golden"] == "YES"]

    for row in contract:
        index = int(row["target_index"])
        target_path = target_dir / f"{index:03d}.png"
        target = normalize_target(args.pack / "screenshots" / "03_target_selected_frames" / row["filename"], target_path)
        content_mask(index, evidence / "masks" / f"{index:03d}.png", target.size)
        sequence_review(args.pack, index, float(row["timestamp_seconds"]), evidence / "reports" / "sequence-review" / f"{index:03d}.jpg")
        v2_path = after_v2_dir / after_v2_name(index)
        before_path = live_image(before_dir, index)
        v2 = fit_current(v2_path, target.size)
        before = fit_current(before_path, target.size)

        if args.phase == "after":
            after_path = live_image(after_dir, index)
            after = fit_current(after_path, target.size)
            board([target, v2, before, after], ["TARGET", "AFTER-V2", "BEFORE-V4", "AFTER-V4"], evidence / "boards" / f"{index:03d}.jpg")
            overlay = Image.blend(target, after, 0.5)
            overlay_path = evidence / "overlays" / f"{index:03d}.png"
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            overlay.save(overlay_path)
            overlay_paths.append(overlay_path)
            raw_diff = ImageChops.difference(target, after)
            heatmap = ImageEnhance.Contrast(raw_diff).enhance(4.0)
            diff_path = evidence / "diffs" / f"{index:03d}.png"
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            heatmap.save(diff_path)
            diff_paths.append(diff_path)
            mean = sum(ImageStat.Stat(raw_diff).mean) / 3
            rows.append({
                "target_index": index,
                "state": row["state"],
                "target": target_path.relative_to(ROOT).as_posix(),
                "after_v2": v2_path.relative_to(ROOT).as_posix(),
                "before_v4": before_path.relative_to(ROOT).as_posix(),
                "after_v4": after_path.relative_to(ROOT).as_posix(),
                "overlay": overlay_path.relative_to(ROOT).as_posix(),
                "diff": diff_path.relative_to(ROOT).as_posix(),
                "mean_absolute_rgb_diff": f"{mean:.3f}",
                "manual_geometry_review": "PENDING",
                "status": "PENDING",
            })

    if args.phase == "after":
        reports = evidence / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        contact_sheet(overlay_paths, reports / "overlay-contact-sheet.jpg")
        contact_sheet(diff_paths, reports / "diff-contact-sheet.jpg")
        (evidence / "masks" / "README.md").write_text(
            "# V4 content masks\n\n"
            "White pixels remain in geometry review. Black pixels identify only permitted dynamic content: "
            "captured device chrome and, where present, raster photo interiors. Controls, typography, "
            "container boundaries, spacing, map polygons and selected-card geometry are never masked. "
            "All boards, alpha overlays, heatmaps and reported unmasked RGB differences are generated "
            "from the original images without applying these masks.\n",
            encoding="utf-8",
        )
        with (reports / "acceptance.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (reports / "evidence-summary.json").write_text(json.dumps({"golden_states": len(rows), "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"phase": args.phase, "golden_states": len(contract), "target_dir": str(target_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

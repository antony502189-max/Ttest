#!/usr/bin/env python3
"""Report all changed pixels for the complete rental-policy visual matrix.

Intentional differences (tourism removal/price controls) are catalogued, NOT
silently labeled pixel-identical. Preserve every screenshot for manual review.
"""
import json
import sys
from pathlib import Path
from PIL import Image, ImageChops

root = Path(sys.argv[1])
baseline = {p.name: p for p in (root / "baseline").glob("*.png")}
candidate = {p.name: p for p in (root / "candidate").glob("*.png")}
if not baseline or baseline.keys() != candidate.keys():
    raise SystemExit(f"unpaired screenshots: {sorted(baseline.keys() ^ candidate.keys())}")
records = []
for name in sorted(baseline):
    with Image.open(baseline[name]) as a_image, Image.open(candidate[name]) as b_image:
        a = a_image.convert("RGB")
        b = b_image.convert("RGB")
        if a.size != b.size:
            raise SystemExit(f"size mismatch for {name}: {a.size} vs {b.size}")
        diff = ImageChops.difference(a, b)
        changed = sum(any(ch for ch in pixel) for pixel in diff.getdata())
        ratio = changed / (a.width * a.height)
        state = name.split("-")[0]
        expected = state in {"home", "search", "publication", "detail"}
        records.append({"screen": name, "pixels": changed,
                        "ratio": round(ratio, 8),
                        "intentional_change_possible": expected,
                        "review_required": bool(changed)})
summary = {"pairedScreens": len(records),
           "identicalScreens": sum(not r["pixels"] for r in records),
           "unexpectedChangeScreens": [r for r in records
                                       if r["pixels"] and not r["intentional_change_possible"]],
           "manualReviewRequired": [r["screen"] for r in records if r["review_required"]],
           "screens": records}
(root / "rental-policy-comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: v for k,v in summary.items() if k != "screens"}, indent=2))
# Deliberately fail for changes in account/menu/favorites, which aren't part of
# the specified redesign. Expected changes remain fully visible in artifacts.
if summary["unexpectedChangeScreens"]:
    raise SystemExit("Unintended visual changes: review paired screenshots")

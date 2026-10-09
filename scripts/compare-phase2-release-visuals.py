#!/usr/bin/env python3
"""Compare unmasked screenshots from an identical-browser baseline/candidate run."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

root = Path(sys.argv[1] if len(sys.argv) > 1 else "output/phase2-release-visuals")
maximum = float(sys.argv[2] if len(sys.argv) > 2 else "0.0005")
a, b = root / "baseline", root / "candidate"
if not a.is_dir() or not b.is_dir():
    raise SystemExit("missing visual comparison input folders")
baseline_files = sorted(a.glob("*.png"))
candidate_names = {p.name for p in b.glob("*.png")}
if not baseline_files or {p.name for p in baseline_files} != candidate_names:
    raise SystemExit("missing or unmatched baseline/candidate screenshots")

records = []
has_regression = False
for image_file in baseline_files:
    with Image.open(image_file) as left, Image.open(b / image_file.name) as right:
        x = left.convert("RGB")
        y = right.convert("RGB")
        if x.size != y.size:
            records.append({"screen": image_file.stem, "size_mismatch": [x.size, y.size], "changed_ratio": 1.0})
            has_regression = True
            continue
        diff = ImageChops.difference(x, y)
        changed = sum(any(c for c in pixel) for pixel in diff.getdata())
        ratio = changed / (x.width * x.height)
        records.append({
            "screen": image_file.stem, "width": x.width, "height": x.height,
            "changed_pixels": changed, "changed_ratio": round(ratio, 8),
            "max_allowed_ratio": maximum, "status": "PASS" if ratio <= maximum else "FAIL",
        })
        if ratio > maximum:
            has_regression = True

out = root / "comparison.json"
out.write_text(json.dumps({"threshold": maximum, "screens": records, "passed": not has_regression}, indent=2) + "\n")
for record in records:
    print(f"{record['screen']}: {record.get('changed_pixels', 'size mismatch')} changed pixels, "
          f"ratio={record['changed_ratio']:.6%}, status={record.get('status', 'FAIL')}")
print(f"Visual comparison: {'FAIL' if has_regression else 'PASS'} ({len(records)} paired states)")
raise SystemExit(1 if has_regression else 0)

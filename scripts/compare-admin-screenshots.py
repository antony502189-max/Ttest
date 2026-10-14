"""Fail if any paired admin screenshot changes even one pixel."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

before, after = (Path(arg) for arg in sys.argv[1:3])
results = []
names = sorted(path.name for path in before.glob("*.png") if not path.name.startswith("diff-"))
if not names or names != sorted(path.name for path in after.glob("*.png") if not path.name.startswith("diff-")):
    raise SystemExit("Screenshot sets are empty or differ")
for name in names:
    with Image.open(before / name) as a, Image.open(after / name) as b:
        difference = None if a.size != b.size else ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        equal = difference is not None and difference.getbbox() is None
        results.append({"name": name, "equal": equal, "beforeSize": a.size, "afterSize": b.size})
        if not equal and difference is not None:
            difference.save(after / f"diff-{name}")
report = {"compared": len(results), "identical": sum(row["equal"] for row in results), "screenshots": results}
(after / "visual-comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"compared": report["compared"], "identical": report["identical"]}))
raise SystemExit(0 if report["compared"] == report["identical"] else 1)

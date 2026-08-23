#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PIN_FILE="$ROOT/.github/visual-baseline-ref"
[[ -r "$PIN_FILE" ]] || { echo "missing visual baseline pin: $PIN_FILE" >&2; exit 65; }
ref="$(tr -d '[:space:]' < "$PIN_FILE")"
[[ "$ref" =~ ^[0-9a-f]{40}$ ]] || { echo "visual baseline pin must be an exact 40-character commit SHA" >&2; exit 65; }

# The visual baseline commit intentionally lives outside main history. A clean
# clone therefore fetches exactly the reviewed commit object before extracting
# only its snapshot tree. No branch head is trusted at test time.
if ! git cat-file -e "$ref^{commit}" 2>/dev/null; then
  remote="${VISUAL_BASELINE_REMOTE:-origin}"
  git fetch --no-tags --depth=1 "$remote" "$ref"
fi

git cat-file -e "$ref^{commit}" 2>/dev/null || { echo "pinned visual baseline commit is unavailable: $ref" >&2; exit 65; }
mapfile -t paths < <(git ls-tree -r --name-only "$ref" -- tests/visual-snapshots/chromium/)
(( ${#paths[@]} > 0 )) || { echo "pinned commit contains no Chromium visual baselines" >&2; exit 65; }

rm -rf tests/visual-snapshots
for path in "${paths[@]}"; do
  [[ "$path" == tests/visual-snapshots/chromium/*.png ]] || {
    echo "unexpected file in visual baseline tree: $path" >&2
    exit 65
  }
  mkdir -p "$(dirname "$path")"
  git show "$ref:$path" > "$path"
done

printf 'installed %d visual baselines from %s\n' "${#paths[@]}" "$ref"

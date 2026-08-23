#!/usr/bin/env bash
set -euo pipefail

command -v gh >/dev/null || { echo "GitHub CLI (gh) is required" >&2; exit 69; }

repo="${1:-}"
if [[ -z "$repo" ]]; then
  repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi
[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "usage: $0 [owner/repo]" >&2; exit 64; }

branch="${BRANCH:-main}"
required_checks=(snapshot safeguards backend-production validate full-audit)
api_version="2026-03-10"

payload="$(mktemp)"
trap 'rm -f "$payload"' EXIT
cat > "$payload" <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "snapshot",
      "safeguards",
      "backend-production",
      "validate",
      "full-audit"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON

gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: $api_version" \
  "repos/$repo/branches/$branch/protection" \
  --input "$payload" >/dev/null

actual_contexts="$(gh api \
  -H "X-GitHub-Api-Version: $api_version" \
  "repos/$repo/branches/$branch/protection" \
  --jq '.required_status_checks.contexts[]')"
for check in "${required_checks[@]}"; do
  grep -Fxq "$check" <<<"$actual_contexts" || { echo "required check missing after update: $check" >&2; exit 65; }
done

[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch" --jq '.protected')" == "true" ]] || {
  echo "$branch is still not protected" >&2
  exit 65
}
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.required_status_checks.strict')" == "true" ]]
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.enforce_admins.enabled')" == "true" ]]
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.required_pull_request_reviews.required_approving_review_count')" == "0" ]]
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.required_pull_request_reviews.dismiss_stale_reviews')" == "true" ]]
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.required_conversation_resolution.enabled')" == "true" ]]
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.allow_force_pushes.enabled')" == "false" ]]
[[ "$(gh api -H "X-GitHub-Api-Version: $api_version" "repos/$repo/branches/$branch/protection" --jq '.allow_deletions.enabled')" == "false" ]]

printf 'branch protection verified for %s:%s\n' "$repo" "$branch"

from pathlib import Path


def test_main_branch_protection_script_enforces_release_gates() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts" / "configure-main-protection.sh").read_text(encoding="utf-8")

    assert 'branch="${BRANCH:-main}"' in script
    assert "gh api --method PUT" in script
    assert '"strict": true' in script
    assert '"enforce_admins": true' in script
    assert '"required_approving_review_count": 0' in script
    assert '"dismiss_stale_reviews": true' in script
    assert '"required_conversation_resolution": true' in script
    assert '"allow_force_pushes": false' in script
    assert '"allow_deletions": false' in script
    for check in ("snapshot", "safeguards", "backend-production", "validate", "full-audit"):
        assert f'"{check}"' in script
    assert "branch protection verified" in script

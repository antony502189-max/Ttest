"""Refuse binaries without the retained primary deletion journal contract.

Run only after primary journal activation, before stopping a healthy release.
Reads source/configuration; never environment values or private snapshot rows.
"""
import ast
import sys
from pathlib import Path


def supports_saved_journal(release: Path) -> bool:
    try:
        main = ast.parse((release / "backend/app/main.py").read_text(encoding="utf-8"))
        installed = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "install_saved_runtime" for node in ast.walk(main))
        runtime = (release / "backend/app/services/ai_saved_runtime.py").read_text(encoding="utf-8")
        compose = (release / "docker-compose.production.yml").read_text(encoding="utf-8")
        return installed and all(fragment in runtime for fragment in ("journal_configured", "replay_erasure(factory, journal)")) and all(
            fragment in compose for fragment in ("AI_ERASURE_JOURNAL_PATH:", "AI_ERASURE_JOURNAL_KEY:", "ai-saved-state:/ai-saved-state"))
    except (OSError, SyntaxError, UnicodeError):
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2 or not supports_saved_journal(Path(sys.argv[1])):
        raise SystemExit("AI_SAVED_JOURNAL_RUNTIME_REQUIRED: keep a compatible application release; never remove the journal or database binding")

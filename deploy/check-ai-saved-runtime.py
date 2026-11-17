"""Refuse binaries without readers for retained saved-search contracts.

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


def supports_party_total(release: Path) -> bool:
    """A retained total-only snapshot cannot be handed to an age-only reader."""
    try:
        schema = ast.parse((release / "backend/app/schemas/ai_search_intent.py").read_text(encoding="utf-8"))
        classes = {node.name: node for node in schema.body if isinstance(node, ast.ClassDef)}
        total = classes.get("PartyTotal")
        criteria = classes.get("Criteria")
        field = next((node for node in criteria.body if isinstance(node, ast.AnnAssign)
                      and isinstance(node.target, ast.Name) and node.target.id == "party"), None) if criteria else None
        model_present = total is not None and any(isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name) and node.target.id == "persons" for node in total.body)
        reader_present = field is not None and any(isinstance(node, ast.Name) and node.id == "PartyTotal"
                                                  for node in ast.walk(field.annotation))
        matcher = ast.parse((release / "backend/app/services/ai_hard_matching.py").read_text(encoding="utf-8"))
        matcher_present = any(isinstance(node, ast.Attribute) and node.attr == "headcount" for node in ast.walk(matcher))
        summary = (release / "src/api/ai-intent.ts").read_text(encoding="utf-8")
        return model_present and reader_present and matcher_present and "object(value, ['persons'])" in summary
    except (OSError, SyntaxError, UnicodeError):
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2 or not supports_saved_journal(Path(sys.argv[1])):
        raise SystemExit("AI_SAVED_JOURNAL_RUNTIME_REQUIRED: keep a compatible application release; never remove the journal or database binding")
    if not supports_party_total(Path(sys.argv[1])):
        raise SystemExit("AI_SAVED_PARTY_TOTAL_RUNTIME_REQUIRED: retained total-only searches need compatible schema, matching and summary readers")

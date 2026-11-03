"""Explicit Docker factory for a separately authorized synthetic LIVE UI smoke.

No module-level credentials, journal access, sockets or application registration.
Never referenced by the ordinary app or the offline lab Compose configuration.
"""
import os
from pathlib import Path

from pydantic import SecretStr

from app.services.ai_deepseek_intent import ProviderFailure
from lab.ai_text import require_lab
from lab.closed_ui import APPROVAL, CORPUS_SHA256, ExistingSmokeBudget
from lab.closed_ui import create_app as compose
from lab.closed_ui_access import ClosedSmokeAccess, load_proxy_secret
from lab.closed_ui_authorization import verify, verify_operational_review

KEY_PATH = Path("/closed-ui-secrets/dedicated-key.env")
JOURNAL_PATH = Path("/closed-ui-budget/budget.sqlite3")
AUTHORIZATION_PATH = Path("/closed-ui-admission/authorization.json")
AUTHORITY_PATH = Path("/closed-ui-admission/authority.pub")
REVIEW_PATH = Path("/closed-ui-admission/operational-review.json")
ACCESS_PATH = Path("/closed-ui-access/proxy.conf")


def create_app():
    require_lab(closed_ui=True)
    if (os.environ.get("AI_CLOSED_UI_APPROVAL") != APPROVAL
            or os.environ.get("AI_CLOSED_UI_CORPUS_SHA256") != CORPUS_SHA256):
        raise ProviderFailure("LIVE_UI_SMOKE_APPROVAL_REQUIRED")
    # Validate existing history before reading even the dedicated credential.
    admission = verify(AUTHORIZATION_PATH.read_bytes(), AUTHORITY_PATH.read_bytes(),
                       trusted_key_sha256=os.environ.get("AI_CLOSED_UI_AUTHORITY_SHA256", ""),
                       source=os.environ.get("AI_LAB_SOURCE_SHA", ""))
    ExistingSmokeBudget(JOURNAL_PATH, corpus_sha256=CORPUS_SHA256, admission=admission)
    verify_operational_review(admission, REVIEW_PATH.read_bytes())
    secret = load_proxy_secret(ACCESS_PATH)
    raw = KEY_PATH.read_text(encoding="utf-8").strip()
    prefix = "AI_INTENT_EVAL_DEEPSEEK_KEY="
    if not raw.startswith(prefix) or not raw[len(prefix):] or any(c.isspace() for c in raw[len(prefix):]):
        raise ProviderFailure("DEDICATED_TEST_KEY_REQUIRED")
    app = compose(key=SecretStr(raw[len(prefix):]), journal=JOURNAL_PATH, approval=APPROVAL,
                  approved_corpus_sha256=CORPUS_SHA256, admission=admission)
    app.add_middleware(ClosedSmokeAccess, secret=secret)
    return app

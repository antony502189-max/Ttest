"""Explicit operator action, not invoked by imports/CI. Preserves every journal."""
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def revoke():
    root = Path("/srv/112233-ai-site-pilot-20261108")
    if not (root/"owner-purpose").read_text().startswith("ai-site-pilot-20261108;"):
        raise ValueError("pilot owner marker required")
    names = {service:"ttest-ai-site-pilot-20261108-"+service+"-1" for service in ("egress","backend")}
    for name in names.values():
        purpose = subprocess.check_output(["docker","inspect",name,"--format",'{{index .Config.Labels "es.ttest.purpose"}}'],text=True).strip()
        if purpose != "ai-site-pilot-20261108":
            raise ValueError("pilot container ownership required")
    approval = root/"deploy/ai-site-pilot/control/approval.json"
    if approval.exists():
        approval.rename(approval.with_name("approval.revoked-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"))
    # File removal denies later reservations. Network/process stop is mandatory
    # to terminate requests which have already crossed the dispatch boundary.
    try:
        subprocess.run(["docker","stop",names["egress"]],check=True)
    finally:
        subprocess.run(["docker","restart",names["backend"]],check=True)


if __name__ == "__main__":
    revoke()

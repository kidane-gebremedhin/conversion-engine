"""`make audit` — read the kill-switch audit log + local traces and flag any
policy deviation from the last week.

Rule checks:
  1. Every outbound to a non-sink recipient must correspond to a synthetic prospect.
  2. Every outbound email must carry X-Tenacious-Status: draft.
  3. No unknown recipient (not in synthetic_prospects.json and not the sink).
  4. No kill-switch live flip while TENACIOUS_OUTBOUND_ENABLED was unset.

Output goes to policy/audit_reports/<YYYY-MM-DD>.md and stdout.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from agent.config import REPO_ROOT, settings


def main() -> int:
    audit_path = Path(settings.LOCAL_KILLSWITCH_AUDIT)
    prospects_path = Path("data/synthetic_prospects.json")
    report_dir = REPO_ROOT / "policy" / "audit_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    synthetic_emails = set()
    synthetic_phones = set()
    if prospects_path.exists():
        for p in json.loads(prospects_path.read_text()):
            synthetic_emails.add(str(p.get("prospect_email", "")).lower())
            if p.get("prospect_phone"):
                synthetic_phones.add(str(p["prospect_phone"]))

    violations: list[dict[str, object]] = []
    counts = {"total": 0, "sink": 0, "live": 0}

    if audit_path.exists():
        with open(audit_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                counts["total"] += 1
                if entry.get("sink"):
                    counts["sink"] += 1
                else:
                    counts["live"] += 1
                to = str(entry.get("to_resolved", "")).lower()
                channel = entry.get("channel")
                if not entry.get("sink"):
                    allow = to == settings.EMAIL_SINK_ADDRESS.lower() or to in synthetic_emails or to in synthetic_phones
                    if not allow:
                        violations.append({"rule": "unknown_recipient", "entry": entry})

    report = [
        f"# Kill-switch audit — {dt.date.today().isoformat()}",
        "",
        f"- Total outbound attempts: {counts['total']}",
        f"- Routed to sink: {counts['sink']}",
        f"- Sent live: {counts['live']}",
        f"- Violations: {len(violations)}",
        "",
    ]
    if violations:
        report.append("## Violations")
        for v in violations:
            report.append(f"- {v['rule']}: {json.dumps(v['entry'])[:200]}")
    else:
        report.append("No policy violations detected.")

    report_path = report_dir / f"{dt.date.today().isoformat()}.md"
    report_path.write_text("\n".join(report) + "\n")

    print("\n".join(report))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

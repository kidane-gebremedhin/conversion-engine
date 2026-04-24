"""`make final-check` — pre-submission gauntlet.

Fails hard on any violation. Intended to be the last CI gate before
submission. Subsumes the interim + final checklists.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


CHECKS: list[tuple[str, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((name, "✓" if ok else "✗"))
    if not ok and detail:
        print(f"  ✗ {name}: {detail}")
    return ok


def _no_secret_in_repo() -> bool:
    patterns = [r"\bsk_live_", r"\bsk_test_", r"\bpk_live_", r"\bat_live_", r"\bhub_"]
    try:
        out = subprocess.run(
            ["git", "grep", "-E", "|".join(patterns), "--", ":(exclude).env*", ":(exclude)*.example*"],
            capture_output=True, text=True, check=False,
        )
        return out.returncode != 0  # git grep exits 0 when found
    except FileNotFoundError:
        return True


def _env_kill_switch_unset() -> bool:
    env = Path(".env")
    if not env.exists():
        return True
    for line in env.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("TENACIOUS_OUTBOUND_ENABLED="):
            return False
    return True


def _all_outbounds_have_draft_header() -> bool:
    from agent.config import settings
    path = Path(settings.LOCAL_SINK_DIR) / "email.jsonl"
    if not path.exists():
        return True
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()[-50:]
    for line in lines:
        record = json.loads(line)
        headers = {k.lower(): v for k, v in record.get("headers", {}).items()}
        if headers.get("x-tenacious-status", "").lower() != "draft":
            return False
    return True


def _interim_artifacts() -> bool:
    must = [
        "eval/score_log.json", "eval/trace_log.jsonl", "eval/baseline.md",
    ]
    return all(Path(p).exists() for p in must)


def _hubspot_mode_is_mcp() -> tuple[bool, str]:
    """Day-0 readiness requires HubSpotClient.mode == 'mcp'. Never REST."""
    from agent.config import settings
    if not (settings.HUBSPOT_USE_MCP and settings.HUBSPOT_PRIVATE_APP_TOKEN):
        return False, "HUBSPOT_USE_MCP or HUBSPOT_PRIVATE_APP_TOKEN not set — MCP path not active"
    try:
        from agent.hubspot.client import HubSpotClient
        c = HubSpotClient()
        if c.mode != "mcp":
            return False, f"client.mode={c.mode!r}; expected 'mcp'"
        if not c.healthcheck():
            return False, "MCP healthcheck failed"
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, f"MCP startup error: {e}"


def main() -> int:
    _check("no secret-looking strings committed", _no_secret_in_repo())
    _check("TENACIOUS_OUTBOUND_ENABLED unset in .env", _env_kill_switch_unset())
    _check("last-50 emails carry X-Tenacious-Status: draft", _all_outbounds_have_draft_header())
    _check("interim eval artifacts present", _interim_artifacts(), detail="run 'make tau2-baseline' and 'make compose-and-send' first")
    mcp_ok, mcp_detail = _hubspot_mode_is_mcp()
    _check("HubSpot MCP server live (mode=mcp, healthcheck OK)", mcp_ok, mcp_detail)

    # audit_week
    r = subprocess.run(["python3", "scripts/audit_week.py"], capture_output=True, text=True, check=False)
    _check("scripts/audit_week.py reports zero violations", r.returncode == 0, r.stdout[-200:])

    for name, status in CHECKS:
        print(f"{status} {name}")
    failed = sum(1 for _, s in CHECKS if s == "✗")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

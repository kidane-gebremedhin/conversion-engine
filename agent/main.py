"""CLI entrypoint.

Examples:
  python -m agent.main --healthcheck
  python -m agent.main --enrich <crunchbase_uuid>
  python -m agent.main --prospect <crunchbase_uuid>    # full COLD → BOOKED
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

from agent.channels.email.send import EmailSender
from agent.channels.sms.send import SmsSender
from agent.config import load_config, load_secrets, validate
from agent.enrichment.pipeline import enrich
from agent.integrations.calcom import CalcomClient
from agent.integrations.hubspot_mcp import HubSpotClient
from agent.integrations.killswitch import from_config as ks_from_config
from agent.llm.client import LlmClient
from agent.orchestrator import Orchestrator, OrchestratorDeps
from agent.state import CrunchbaseRecord, Prospect


_PROSPECTS = pathlib.Path("tests/fixtures/synthetic_prospects.yaml")


def build_deps():
    cfg = load_config()
    secrets = load_secrets()
    validate(secrets, cfg)
    ks = ks_from_config(cfg, secrets)
    llm = LlmClient(
        mode=secrets.convergine_llm_mode,
        api_key=(secrets.openrouter_api_key.get_secret_value() if secrets.openrouter_api_key else None),
        base_url=secrets.openrouter_base_url,
        dev_tier_model=(cfg.get("llm", "models", "dev_tier", "primary", "name") or "qwen/qwen3-next-80b-a3b-instruct"),
        prices=cfg.get("llm", "prices", default={}),
    )
    email = EmailSender(
        killswitch=ks,
        provider=(cfg.get("channels", "email", "provider") or "sink"),
        api_key=(secrets.resend_api_key.get_secret_value() if secrets.resend_api_key else None),
        from_address=secrets.resend_from_address,
        from_domain=secrets.resend_from_domain,
    )
    sms = SmsSender(
        killswitch=ks,
        provider="africastalking",
        username=secrets.africastalking_username,
        api_key=(secrets.africastalking_api_key.get_secret_value() if secrets.africastalking_api_key else None),
        shortcode=secrets.africastalking_shortcode,
    )
    hubspot = HubSpotClient(
        mcp_url=secrets.hubspot_mcp_url,
        token=(secrets.hubspot_private_app_token.get_secret_value() if secrets.hubspot_private_app_token else None),
    )
    calcom = CalcomClient(
        base_url=secrets.calcom_base_url,
        api_key=(secrets.calcom_api_key.get_secret_value() if secrets.calcom_api_key else None),
    )
    return cfg, secrets, OrchestratorDeps(llm=llm, email=email, sms=sms, hubspot=hubspot, calcom=calcom)


def load_prospect(uuid: str) -> Prospect:
    data = yaml.safe_load(_PROSPECTS.read_text())
    for row in data["prospects"]:
        if row["crunchbase_uuid"] == uuid or row.get("alias") == uuid:
            cb = _lookup_crunchbase(row["crunchbase_uuid"])
            return Prospect(
                crunchbase=cb,
                contact_email=row["contact_email"],
                contact_first=row["contact_first"],
                contact_last=row["contact_last"],
                contact_role=row["contact_role"],
                contact_timezone=row.get("contact_timezone", "America/New_York"),
                preferred_channel=row.get("preferred_channel", "email"),
            )
    raise KeyError(f"prospect not found in fixtures: {uuid}")


def _lookup_crunchbase(uuid: str) -> CrunchbaseRecord:
    from agent.enrichment.crunchbase import by_uuid
    rec = by_uuid(uuid)
    if rec is None:
        raise KeyError(f"crunchbase record not found: {uuid}")
    return rec


def run_prospect(uuid: str) -> None:
    cfg, secrets, deps = build_deps()
    prospect = load_prospect(uuid)
    orch = Orchestrator(deps)

    # 1. COLD outreach
    state = orch.run_cold(prospect)
    print(f"[cold] stage={state.stage.value} segment={state.segment} variant={state.variant.value}")

    # 2. Simulate prospect reply via fixture (fixture-driven e2e)
    reply_body = _fixture_reply_for(uuid, "interested")
    state = orch.handle_email_reply(state, prospect, reply_body)
    print(f"[post-reply] stage={state.stage.value}")

    # 3. handle_email_reply already books + confirms if interested
    print(f"[final] stage={state.stage.value}")


def _fixture_reply_for(uuid: str, kind: str) -> str:
    data = yaml.safe_load(_PROSPECTS.read_text())
    for row in data["prospects"]:
        if row["crunchbase_uuid"] == uuid or row.get("alias") == uuid:
            return row.get("replies", {}).get(kind, "Thanks — Thursday 2pm works, send a calendar link.")
    return "Thanks — Thursday 2pm works, send a calendar link."


def do_healthcheck() -> int:
    cfg, secrets, _ = build_deps()
    ks = (cfg.get("killswitch") or {})
    out = {
        "status": "ok",
        "env": secrets.convergine_env,
        "llm_mode": secrets.convergine_llm_mode,
        "killswitch_enabled": bool(ks.get("enabled", False)),
        "require_real_outbound_env": bool(ks.get("require_real_outbound_env", True)),
        "real_outbound_env_set": secrets.convergine_enable_real_outbound,
        "fixtures_present": _PROSPECTS.exists(),
    }
    print(json.dumps(out, indent=2))
    return 0 if out["fixtures_present"] else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser("agent")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--healthcheck", action="store_true")
    g.add_argument("--enrich", metavar="UUID")
    g.add_argument("--prospect", metavar="UUID")
    args = p.parse_args(argv)

    if args.healthcheck:
        return do_healthcheck()
    if args.enrich:
        result = enrich(args.enrich, force=True)
        print(json.dumps({
            "crunchbase_uuid": args.enrich,
            "icp_segment": result.icp.segment,
            "icp_mode": result.icp.mode,
            "ai_maturity": result.maturity.score,
            "cache_dir": f"data/briefs_cache/{args.enrich}",
        }, indent=2))
        return 0
    if args.prospect:
        run_prospect(args.prospect)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

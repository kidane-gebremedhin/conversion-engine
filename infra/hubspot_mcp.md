# HubSpot MCP server — install (Day-0 required)

Day-0 readiness requires the HubSpot MCP server to be installed and
running. REST-mode is NOT an acceptable substitute for the Day-0 review.

## Prerequisites

- Node.js 18+ (check: `node --version`).
- A HubSpot Developer Sandbox with a private app token scoped for
  CRM read/write.
- Python `mcp` SDK (pinned in `agent/requirements.txt`).

## Install the server (one-time, machine-global)

```bash
npm install -g @hubspot/mcp-server
# or, without global install, the Python client uses `npx -y @hubspot/mcp-server`
# and npx will cache the package on first use.
```

## Configure

Add to `.env`:

```
HUBSPOT_USE_MCP=true
HUBSPOT_PRIVATE_APP_TOKEN=<your Developer Sandbox private-app token>
HUBSPOT_PORTAL_ID=<your Developer Sandbox portal ID>
```

### Required private-app scopes

When creating the private app in the HubSpot Developer Sandbox
(Settings → Integrations → Private Apps → Create), grant **all** of the
following scopes before copying the token. Missing any of them turns
`make day0-hubspot` into a `403 MISSING_SCOPES`.

| Scope | Why |
|---|---|
| `crm.objects.contacts.read` | upsert lookup by email |
| `crm.objects.contacts.write` | create / update contacts |
| `crm.objects.deals.read` | read deals for idempotency |
| `crm.objects.deals.write` | create deals at booking |
| `crm.schemas.contacts.read` | probe `tenacious_*` property existence |
| `crm.schemas.contacts.write` | create `tenacious_*` contact properties |
| `crm.schemas.deals.read` | probe deal properties |
| `crm.schemas.deals.write` | create deal properties |
| `crm.objects.owners.read` | resolve owner id for engagements |

If you already created the app and the smoke fails with `MISSING_SCOPES`,
go back to Settings → Integrations → Private Apps → your app → Scopes,
check the missing ones, click **Update**, and regenerate the token
(the new token replaces the old one in `.env`).

The Python agent spawns the MCP server over stdio at import time
(`agent/hubspot/mcp_client.py`). No additional daemon or port-binding is
needed — the server's lifetime is tied to the Python process.

## Day-0 verification

```bash
make day0-hubspot
```

Expected output:

```
→ MCP server started via `npx -y @hubspot/mcp-server`
✓ created test contact id='12345' email=daytest+<hex>@trp1-sink.example via mcp
```

Confirm in the HubSpot Developer Sandbox UI → Contacts that the
synthetic record landed with `tenacious_status=draft`.

## If the MCP install fails

Do not set `HUBSPOT_USE_MCP=false` to route around the failure — that
demotes the run to REST, which is not acceptable for Day-0 readiness.
Instead:

1. Confirm Node.js ≥ 18 is on `$PATH`.
2. Run `npx -y @hubspot/mcp-server --help` manually; if that fails, the
   global install did not take — reinstall with `npm install -g @hubspot/mcp-server`.
3. Confirm `HUBSPOT_PRIVATE_APP_TOKEN` is a private-app token with
   `crm.objects.contacts.write`, `crm.objects.deals.write`,
   `crm.schemas.contacts.write`, `crm.schemas.deals.write` scopes.
4. Re-run `make day0-hubspot`.

If the MCP server cannot be made to work after the above, flag it to
program staff per `__specs/16-data-handling-and-kill-switch.md#rule-9--incident-reporting`
before proceeding to Act I. Do not proceed with REST as a workaround.

## What "MCP-installed" means for the agent at runtime

The `HubSpotClient.mode` attribute must equal `"mcp"` during Act II.
`scripts/final_check.py` asserts this on pre-submission. The kill-switch
audit log includes the mode on every delivered message so any regression
to REST is visible in `data/killswitch_audit.jsonl`.

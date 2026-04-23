"""Provision the HubSpot Developer Sandbox schema.

Idempotent — safe to re-run. Creates:
  - `convergine_*` custom properties on Company, Contact, Deal
  - Custom object `convergine_conversation_event` with its property bag
    and the `convergine_event_id` unique-constraint

Run:
  HUBSPOT_PRIVATE_APP_TOKEN=pat-na1-... python -m scripts.hubspot_bootstrap

Exit codes:
  0 — success (all properties + object type present)
  1 — auth failure
  2 — partial provision (prints the remaining gaps)
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx

_API = "https://api.hubapi.com"
_OBJECT_TYPE = os.environ.get(
    "HUBSPOT_CONVERSATION_EVENT_OBJECT_TYPE",
    "convergine_conversation_event",
)

_COMPANY_PROPS: list[dict[str, Any]] = [
    {"name": "convergine_crunchbase_uuid", "label": "Crunchbase UUID", "type": "string", "fieldType": "text", "hasUniqueValue": True},
    {"name": "convergine_icp_segment", "label": "ICP segment", "type": "number", "fieldType": "number"},
    {"name": "convergine_icp_mode", "label": "ICP mode", "type": "enumeration", "fieldType": "select", "options": [
        {"label": "confident", "value": "confident"}, {"label": "abstain", "value": "abstain"}]},
    {"name": "convergine_icp_confidence", "label": "ICP confidence", "type": "number", "fieldType": "number"},
    {"name": "convergine_ai_maturity_score", "label": "AI maturity score", "type": "number", "fieldType": "number"},
    {"name": "convergine_ai_maturity_confidence", "label": "AI maturity confidence", "type": "number", "fieldType": "number"},
    {"name": "convergine_enrichment_timestamp", "label": "Enrichment timestamp", "type": "datetime", "fieldType": "date"},
    {"name": "convergine_brief_url", "label": "Hiring-signal brief URL", "type": "string", "fieldType": "text"},
    {"name": "convergine_gap_brief_url", "label": "Competitor-gap brief URL", "type": "string", "fieldType": "text"},
]

_CONTACT_PROPS: list[dict[str, Any]] = [
    {"name": "convergine_preferred_channel", "label": "Preferred channel", "type": "enumeration", "fieldType": "select", "options": [
        {"label": "email", "value": "email"}, {"label": "sms", "value": "sms"}]},
    {"name": "convergine_synthetic", "label": "Synthetic", "type": "enumeration", "fieldType": "booleancheckbox", "options": [
        {"label": "true", "value": "true"}, {"label": "false", "value": "false"}]},
]

_DEAL_PROPS: list[dict[str, Any]] = [
    {"name": "convergine_segment", "label": "Convergine segment", "type": "string", "fieldType": "text"},
    {"name": "convergine_thread_id", "label": "Convergine thread id", "type": "string", "fieldType": "text"},
]

_EVENT_PROPS: list[dict[str, Any]] = [
    {"name": "convergine_event_id", "label": "Event id", "type": "string", "fieldType": "text", "hasUniqueValue": True},
    {"name": "convergine_event_type", "label": "Event type", "type": "string", "fieldType": "text"},
    {"name": "convergine_channel", "label": "Channel", "type": "string", "fieldType": "text"},
    {"name": "convergine_trace_id", "label": "Langfuse trace id", "type": "string", "fieldType": "text"},
    {"name": "convergine_payload_json", "label": "Payload (JSON)", "type": "string", "fieldType": "textarea"},
    {"name": "convergine_draft", "label": "Draft", "type": "enumeration", "fieldType": "booleancheckbox", "options": [
        {"label": "true", "value": "true"}, {"label": "false", "value": "false"}]},
]


def _group_payload(object_type: str) -> dict[str, Any]:
    return {"name": "convergine", "label": "Convergine", "displayOrder": -1}


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _ensure_group(cli: httpx.Client, token: str, object_type: str) -> None:
    url = f"{_API}/crm/v3/properties/{object_type}/groups"
    r = cli.post(url, headers=_headers(token), json=_group_payload(object_type))
    if r.status_code not in (200, 201, 409):
        r.raise_for_status()


def _ensure_property(cli: httpx.Client, token: str, object_type: str, prop: dict[str, Any]) -> str:
    body = {"groupName": "convergine", **prop}
    url = f"{_API}/crm/v3/properties/{object_type}"
    r = cli.post(url, headers=_headers(token), json=body)
    if r.status_code in (200, 201):
        return "created"
    if r.status_code == 409:
        return "exists"
    r.raise_for_status()
    return "unknown"


def _custom_object_payload() -> dict[str, Any]:
    return {
        "name": _OBJECT_TYPE,
        "labels": {"singular": "Conversation Event", "plural": "Conversation Events"},
        "primaryDisplayProperty": "convergine_event_id",
        "requiredProperties": ["convergine_event_id"],
        "searchableProperties": ["convergine_event_id", "convergine_event_type", "convergine_trace_id"],
        "properties": [
            {**p, "groupName": None} for p in _EVENT_PROPS
        ],
        "associatedObjects": ["CONTACT", "COMPANY"],
    }


def _ensure_custom_object(cli: httpx.Client, token: str) -> str:
    # Check whether it already exists.
    r = cli.get(f"{_API}/crm/v3/schemas/{_OBJECT_TYPE}", headers=_headers(token))
    if r.status_code == 200:
        return "exists"
    if r.status_code not in (404,):
        r.raise_for_status()

    r = cli.post(f"{_API}/crm/v3/schemas", headers=_headers(token), json=_custom_object_payload())
    if r.status_code in (200, 201):
        return "created"
    r.raise_for_status()
    return "unknown"


def main() -> int:
    token = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        print("HUBSPOT_PRIVATE_APP_TOKEN not set", file=sys.stderr)
        return 1

    problems: list[str] = []
    with httpx.Client(timeout=30) as cli:
        # Auth probe
        probe = cli.get(f"{_API}/crm/v3/objects/contacts?limit=1", headers=_headers(token))
        if probe.status_code in (401, 403):
            print(f"auth failed: {probe.status_code} {probe.text}", file=sys.stderr)
            return 1

        for obj_type, props in (
            ("companies", _COMPANY_PROPS),
            ("contacts", _CONTACT_PROPS),
            ("deals", _DEAL_PROPS),
        ):
            try:
                _ensure_group(cli, token, obj_type)
            except httpx.HTTPStatusError as exc:
                problems.append(f"[{obj_type}] group: {exc.response.status_code} {exc.response.text[:200]}")
            for prop in props:
                try:
                    status = _ensure_property(cli, token, obj_type, prop)
                    print(f"[{obj_type}] {prop['name']}: {status}")
                except httpx.HTTPStatusError as exc:
                    problems.append(
                        f"[{obj_type}] {prop['name']}: {exc.response.status_code} {exc.response.text[:200]}"
                    )

        # Custom object last — its property bag is declared inline.
        try:
            status = _ensure_custom_object(cli, token)
            print(f"[custom_object {_OBJECT_TYPE}]: {status}")
            if status == "exists":
                for prop in _EVENT_PROPS:
                    try:
                        s = _ensure_property(cli, token, _OBJECT_TYPE, prop)
                        print(f"[{_OBJECT_TYPE}] {prop['name']}: {s}")
                    except httpx.HTTPStatusError as exc:
                        problems.append(
                            f"[{_OBJECT_TYPE}] {prop['name']}: {exc.response.status_code} {exc.response.text[:200]}"
                        )
        except httpx.HTTPStatusError as exc:
            problems.append(
                f"[custom_object {_OBJECT_TYPE}]: {exc.response.status_code} {exc.response.text[:200]}"
            )

    if problems:
        print("\nUnresolved:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    print("\nBootstrap OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

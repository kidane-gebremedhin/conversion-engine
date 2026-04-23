"""HubSpot REST helpers.

Pure functions that speak HubSpot's Private-App REST API. Shared by:
  - `hubspot_mcp_server.py` (the in-repo MCP server that wraps these calls)
  - `HubSpotClient` REST fallback mode

Upserts use search-before-write on a natural key (crunchbase_uuid for
companies, email for contacts) per __specs/08 §4.

The Conversation Event custom object type defaults to
``convergine_conversation_event`` and is overridable via
``HUBSPOT_CONVERSATION_EVENT_OBJECT_TYPE``. The bootstrap script
(``scripts/hubspot_bootstrap.py``) creates the schema with that fqn.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

_API = "https://api.hubapi.com"
_TIMEOUT = 30.0

_CONVERSATION_EVENT_TYPE = os.environ.get(
    "HUBSPOT_CONVERSATION_EVENT_OBJECT_TYPE",
    "convergine_conversation_event",
)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _company_properties(
    *,
    crunchbase_uuid: str,
    name: str,
    domain: str | None,
    industry: str | None,
    country: str | None,
    employees: str | None,
    convergine: dict[str, Any],
) -> dict[str, Any]:
    props = {
        "name": name,
        "domain": domain,
        "industry": industry,
        "country": country,
        "numberofemployees": employees,
        "convergine_crunchbase_uuid": crunchbase_uuid,
        **{f"convergine_{k}": v for k, v in convergine.items()},
    }
    return {k: v for k, v in props.items() if v is not None}


def rest_find_company_by_crunchbase_uuid(token: str, crunchbase_uuid: str) -> str | None:
    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "convergine_crunchbase_uuid",
                        "operator": "EQ",
                        "value": crunchbase_uuid,
                    }
                ]
            }
        ],
        "properties": ["convergine_crunchbase_uuid"],
        "limit": 1,
    }
    with httpx.Client(timeout=_TIMEOUT) as cli:
        r = cli.post(f"{_API}/crm/v3/objects/companies/search", headers=_headers(token), json=body)
        r.raise_for_status()
        results = r.json().get("results") or []
    return results[0]["id"] if results else None


def rest_upsert_company(
    token: str,
    *,
    crunchbase_uuid: str,
    name: str,
    domain: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    employees: str | None = None,
    convergine: dict[str, Any] | None = None,
) -> str:
    if not crunchbase_uuid:
        raise ValueError("crunchbase_uuid is required")
    props = _company_properties(
        crunchbase_uuid=crunchbase_uuid,
        name=name,
        domain=domain,
        industry=industry,
        country=country,
        employees=employees,
        convergine=convergine or {},
    )
    existing = rest_find_company_by_crunchbase_uuid(token, crunchbase_uuid)
    with httpx.Client(timeout=_TIMEOUT) as cli:
        if existing:
            r = cli.patch(
                f"{_API}/crm/v3/objects/companies/{existing}",
                headers=_headers(token),
                json={"properties": props},
            )
            r.raise_for_status()
            return existing
        r = cli.post(
            f"{_API}/crm/v3/objects/companies",
            headers=_headers(token),
            json={"properties": props},
        )
        r.raise_for_status()
        return r.json()["id"]


def _find_contact_by_email(token: str, email: str) -> str | None:
    body = {
        "filterGroups": [
            {"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}
        ],
        "properties": ["email"],
        "limit": 1,
    }
    with httpx.Client(timeout=_TIMEOUT) as cli:
        r = cli.post(f"{_API}/crm/v3/objects/contacts/search", headers=_headers(token), json=body)
        r.raise_for_status()
        results = r.json().get("results") or []
    return results[0]["id"] if results else None


def _associate(token: str, from_type: str, from_id: str, to_type: str, to_id: str) -> None:
    with httpx.Client(timeout=_TIMEOUT) as cli:
        r = cli.put(
            f"{_API}/crm/v4/objects/{from_type}/{from_id}/associations/default/{to_type}/{to_id}",
            headers=_headers(token),
        )
        r.raise_for_status()


def rest_upsert_contact(
    token: str,
    *,
    email: str,
    first_name: str,
    last_name: str,
    job_title: str,
    company_id: str,
    preferred_channel: str = "email",
    synthetic: bool = True,
) -> str:
    props = {
        "email": email,
        "firstname": first_name,
        "lastname": last_name,
        "jobtitle": job_title,
        "convergine_preferred_channel": preferred_channel,
        "convergine_synthetic": "true" if synthetic else "false",
    }
    existing = _find_contact_by_email(token, email)
    with httpx.Client(timeout=_TIMEOUT) as cli:
        if existing:
            r = cli.patch(
                f"{_API}/crm/v3/objects/contacts/{existing}",
                headers=_headers(token),
                json={"properties": props},
            )
            r.raise_for_status()
            contact_id = existing
        else:
            r = cli.post(
                f"{_API}/crm/v3/objects/contacts",
                headers=_headers(token),
                json={"properties": props},
            )
            r.raise_for_status()
            contact_id = r.json()["id"]
    if company_id:
        _associate(token, "contacts", contact_id, "companies", company_id)
    return contact_id


def rest_create_deal(
    token: str,
    *,
    company_id: str,
    contact_id: str,
    dealname: str,
    amount: int,
    convergine_segment: int | None = None,
    convergine_thread_id: str = "",
    pipeline: str = "default",
    dealstage: str = "appointmentscheduled",
) -> str:
    props = {
        "dealname": dealname,
        "amount": str(amount),
        "pipeline": pipeline,
        "dealstage": dealstage,
        "convergine_segment": str(convergine_segment) if convergine_segment is not None else "",
        "convergine_thread_id": convergine_thread_id,
    }
    with httpx.Client(timeout=_TIMEOUT) as cli:
        r = cli.post(
            f"{_API}/crm/v3/objects/deals",
            headers=_headers(token),
            json={"properties": props},
        )
        r.raise_for_status()
        deal_id = r.json()["id"]
    if company_id:
        _associate(token, "deals", deal_id, "companies", company_id)
    if contact_id:
        _associate(token, "deals", deal_id, "contacts", contact_id)
    return deal_id


def rest_advance_deal_stage(token: str, *, deal_id: str, stage: str) -> None:
    with httpx.Client(timeout=_TIMEOUT) as cli:
        r = cli.patch(
            f"{_API}/crm/v3/objects/deals/{deal_id}",
            headers=_headers(token),
            json={"properties": {"dealstage": stage}},
        )
        r.raise_for_status()


def rest_log_event(
    token: str,
    *,
    event_id: str,
    contact_id: str,
    company_id: str,
    event_type: str,
    channel: str,
    trace_id: str,
    payload_json: dict[str, Any],
    draft: bool,
) -> None:
    import json

    props = {
        "convergine_event_id": event_id,
        "convergine_event_type": event_type,
        "convergine_channel": channel,
        "convergine_trace_id": trace_id,
        "convergine_payload_json": json.dumps(payload_json, separators=(",", ":")),
        "convergine_draft": "true" if draft else "false",
    }
    with httpx.Client(timeout=_TIMEOUT) as cli:
        r = cli.post(
            f"{_API}/crm/v3/objects/{_CONVERSATION_EVENT_TYPE}",
            headers=_headers(token),
            json={"properties": props},
        )
        # 409 on idempotent re-play (event_id unique constraint) is fine.
        if r.status_code not in (200, 201, 409):
            r.raise_for_status()
        if r.status_code == 409:
            return
        record_id = r.json()["id"]
    if contact_id:
        _associate(token, _CONVERSATION_EVENT_TYPE, record_id, "contacts", contact_id)
    if company_id:
        _associate(token, _CONVERSATION_EVENT_TYPE, record_id, "companies", company_id)


def rest_smoke_contact(token: str, email: str = "smoke-test@sink.convergine.local") -> str:
    """Used by D0 smoke test — creates/updates one contact, returns id."""
    return rest_upsert_contact(
        token,
        email=email,
        first_name="Smoke",
        last_name="Test",
        job_title="QA",
        company_id="",
        preferred_channel="email",
        synthetic=True,
    )

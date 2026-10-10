"""Thin client for Sarvam's Voice Agents REST API (docs.sarvam.ai/conversations/api). Dry run by default: every
request is written to outputs/integrations/sarvam_api.jsonl and nothing is sent unless VANI_SARVAM_LIVE=1.

  .env: SARVAM_API_KEY, SARVAM_ORG_ID, SARVAM_WORKSPACE_ID, SARVAM_CONNECTION_ID, SARVAM_AGENT_NUMBER,
        SARVAM_WEBHOOK_URL (our post-call endpoint, Phase C)

Field names follow the API reference pages read on 2026-10-10. Where a page's example disagrees with its schema
(connection_configs: agent_phone_number vs phone_numbers; webhook_config inside vs outside app_config) the
SCHEMA is used and the disagreement is listed in docs/sarvam_platform_notes.md.
"""
import json
import os
from typing import Any, Dict, Optional

from integrations.base import is_live, log, mask_phone, require

FLAG = "VANI_SARVAM_LIVE"
BASE = "https://apps.sarvam.ai/api"
AGENT_IDS = None


def _scope() -> str:
    org, ws = os.environ.get("SARVAM_ORG_ID", "{org_id}"), os.environ.get("SARVAM_WORKSPACE_ID", "{workspace_id}")
    return f"v1/orgs/{org}/workspaces/{ws}"


def _send(method: str, url: str, body: Optional[Dict[str, Any]] = None, files=None, data=None, what: str = ""):
    shown = json.loads(json.dumps(body or {}, default=str))
    if "user_config" in shown:
        shown["user_config"]["user_phone_number"] = mask_phone(shown["user_config"].get("user_phone_number"))
    if not is_live(FLAG):
        return log("sarvam_api", {"mode": "dry_run", "what": what, "method": method, "url": url, "body": shown})
    env = require("SARVAM_API_KEY", "SARVAM_ORG_ID", "SARVAM_WORKSPACE_ID")
    import requests
    r = requests.request(method, url, json=body if files is None else None, files=files, data=data,
                         headers={"X-API-Key": env["SARVAM_API_KEY"]}, timeout=30)
    out = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:500]}
    log("sarvam_api", {"mode": "live", "what": what, "method": method, "url": url, "status": r.status_code, "response": out})
    if r.status_code >= 400:
        raise RuntimeError(f"Sarvam API {what} failed {r.status_code}: {out}")
    return out


def connection() -> Dict[str, str]:
    return {"connection_id": os.environ.get("SARVAM_CONNECTION_ID", "{connection_id}"),
            "agent_phone_number": os.environ.get("SARVAM_AGENT_NUMBER", "{agent_phone_number}")}


def outbound_body(app: Dict[str, Any], to_number: str, call: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """POST .../outbounds body for one seller (call = sarvam_platform.agent_variables_for(persona))."""
    body = {"app_config": {"app_id": app["app_id"], "app_version": app["app_version"], "connection_config": connection(),
                           "agent_variables": call["agent_variables"], "app_overrides": call["app_overrides"]},
            "user_config": {"user_phone_number": to_number}}
    hook = os.environ.get("SARVAM_WEBHOOK_URL")
    if hook:
        body["webhook_config"] = {"url": hook, "metadata": metadata}
    return body


def create_outbound(app, to_number, call, metadata):
    return _send("POST", f"{BASE}/outbounds/{_scope()}/outbounds", outbound_body(app, to_number, call, metadata),
                 what="instant_outbound")


def campaign_body(name: str, app: Dict[str, Any], start_iso: str, end_iso: str, schedule: Dict[str, Any],
                  retry: Dict[str, Any], attempts_per_second: float = 1.0) -> Dict[str, Any]:
    body = {"name": name[:50], "start_timestamp": start_iso, "end_timestamp": end_iso, "allowed_schedule": schedule,
            "app_config": {"app_id": app["app_id"], "app_version": app["app_version"], "app_type": "agent",
                           "attempts_per_second": attempts_per_second, "connection_configs": [connection()],
                           "retry_config": retry}}
    hook = os.environ.get("SARVAM_WEBHOOK_URL")
    if hook:
        body["webhook_config"] = {"url": hook, "metadata": {"campaign": name}}
    return body


def create_campaign(body):
    return _send("POST", f"{BASE}/scheduling/{_scope()}/campaigns", body, what="create_campaign")


def upload_cohort(campaign_id: str, name: str, csv_path, mapping_path):
    with open(csv_path, "rb") as c, open(mapping_path, "rb") as m:
        return _send("POST", f"{BASE}/scheduling/{_scope()}/campaigns/{campaign_id}/cohorts/upload",
                     {"name": name, "cohort_file": str(csv_path), "cohort_transformation_file": str(mapping_path)},
                     files={"cohort_file": c, "cohort_transformation_file": m}, data={"name": name[:50]},
                     what="upload_cohort")

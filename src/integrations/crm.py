"""Lead write-back (roadmap item 4): the call's outcome, mapped to the disposition labels IndiaMART's lead
system already uses, plus the slot, the captured insights and the do-not-call flag.

IndiaMART's lead API is internal, so the live path is a plain authenticated JSON POST:

  VANI_CRM_LIVE=1
  CRM_URL=https://.../vani/outcome
  CRM_TOKEN=...
"""
from typing import Any, Dict

from integrations.base import is_live, log, require

FLAG = "VANI_CRM_LIVE"
# VANI outcome -> the disposition_label values in the bot-call data (Meeting Fixed / Not Interested / General /
# Call Later / Busy), so executives' existing queues pick the call up unchanged
DISPOSITION_LABEL = {
    "MEETING_FIXED": "Meeting Fixed", "CALLBACK_SCHEDULED": "Call Later", "HUMAN_HANDOFF": "Call Later",
    "CALL_BACK_LATER": "Call Later", "INFO_SENT": "General", "COMPLAINT_LOGGED": "General", "EXEC_HANDOFF": "General",
    "CONTACT_UPDATED": "General", "RESPECTFUL_EXIT": "Not Interested", "DO_NOT_CALL": "Not Interested",
    "ESCALATED_EXIT": "Not Interested", "IN_PROGRESS": "General",
}


def record_from_summary(s: Dict[str, Any], call_id: str = "") -> Dict[str, Any]:
    return {"call_id": call_id, "seller_id": s["seller_id"], "vani_outcome": s["final_outcome"],
            "disposition_label": DISPOSITION_LABEL.get(s["final_outcome"], "General"),
            "meeting_fixed": s["final_outcome"] == "MEETING_FIXED", "slot": s.get("slot"),
            "do_not_call": bool(s.get("do_not_call")), "goal_achieved": s.get("goal_achieved"),
            "primary_goal": s.get("primary_goal"), "goal_history": s.get("goal_history"),
            "seller_insights": s.get("seller_insights") or {}, "turns": s.get("turns"),
            "completed": s["final_outcome"] != "IN_PROGRESS"}


def write_outcome(summary: Dict[str, Any], call_id: str = "") -> Dict[str, Any]:
    rec = record_from_summary(summary, call_id)
    if not is_live(FLAG):
        return log("crm", {"mode": "dry_run", **rec})
    env = require("CRM_URL", "CRM_TOKEN")
    import requests
    r = requests.post(env["CRM_URL"], json=rec, headers={"Authorization": f"Bearer {env['CRM_TOKEN']}"}, timeout=15)
    return log("crm", {"mode": "live", "status": r.status_code, **{k: rec[k] for k in ("call_id", "seller_id", "vani_outcome")}})

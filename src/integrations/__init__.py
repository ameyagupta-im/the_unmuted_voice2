"""External integrations, wired into the call drivers (web_app.py, run_live_demo.py) at two points:

  pre_call(seller_id)      -> Clearance: suppression list, national DND, calling hours. A blocked seller is
                              never dialled.
  on_call_end(call, id)    -> CRM write-back always; WhatsApp only for what the seller agreed to: the details when
                              the call closed as INFO_SENT (they asked or said yes), the meeting confirmation
                              (date, time, in person / online) when it closed as MEETING_FIXED; the suppression
                              list when the seller asked not to be called.

All of it is dry run (JSON lines under outputs/integrations/) unless the integration's own env flag is set.
"""
from typing import Any, Dict, Optional

from integrations import crm, suppression, whatsapp
from integrations.suppression import Clearance


def pre_call(seller_id: int, phone: Optional[str] = None) -> Clearance:
    return suppression.check(seller_id, phone)


def on_call_end(call, call_id: str = "", phone: Optional[str] = None) -> Dict[str, Any]:
    """Run once, when the call has ended (or been abandoned mid-call: then only the CRM record is written)."""
    s = call.summary()
    done = {"crm": crm.write_outcome(s, call_id)}
    if call.ended and s["final_outcome"] == "INFO_SENT":
        done["whatsapp"] = whatsapp.send_details(s["seller_id"], phone, call.persona["seller_snapshot"].get("category"),
                                                 call.s["language"])
    elif call.ended and s["final_outcome"] == "MEETING_FIXED" and s.get("meeting"):
        done["whatsapp"] = whatsapp.send_meeting(s["seller_id"], phone, s["meeting"], call.s["language"])
    if s["do_not_call"]:
        suppression.add(s["seller_id"], "seller asked not to be called", phone)
        done["suppression"] = "added"
    return done

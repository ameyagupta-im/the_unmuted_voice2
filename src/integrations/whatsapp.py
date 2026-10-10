"""WhatsApp messages, only for what the seller agreed to on the call (IndiaMART, 10 Oct 2026):

  send_details   the call closed as INFO_SENT (the seller asked for, or said yes to, the details)
  send_meeting   the call closed as MEETING_FIXED: the confirmed date, time and in person / online, spelled out

Never when the seller merely asked what the details are. Live path: Meta WhatsApp Cloud API, approved templates.

  VANI_WHATSAPP_LIVE=1
  WHATSAPP_TOKEN=...            permanent system-user token
  WHATSAPP_PHONE_NUMBER_ID=...  the sending number's id
  WHATSAPP_TEMPLATE=vani_details (optional; approved template with {{1}} = seller category)
  WHATSAPP_MEETING_TEMPLATE=vani_meeting (optional; {{1}} = date, {{2}} = time, {{3}} = in person / online)
  WHATSAPP_API_VERSION=v21.0    (optional)
"""
import os
from typing import Any, Dict, Optional

from integrations.base import is_live, log, mask_phone, require

FLAG = "VANI_WHATSAPP_LIVE"
TEMPLATE_LANG = {"hi-IN": "hi", "en-IN": "en", "te-IN": "te"}


def build_payload(phone: str, category: Optional[str], language: str, template: str) -> Dict[str, Any]:
    return {"messaging_product": "whatsapp", "to": "".join(ch for ch in str(phone) if ch.isdigit()), "type": "template",
            "template": {"name": template, "language": {"code": TEMPLATE_LANG.get(language, "en")},
                         "components": [{"type": "body", "parameters": [{"type": "text", "text": category or "your business"}]}]}}


_MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
_DAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]


def meeting_text(meeting: Dict[str, Any], language: str) -> Dict[str, str]:
    """The meeting spelled out for the message: date, time, format (no "kal" -- a date the seller can check)."""
    import datetime as dt
    at = dt.datetime.fromisoformat(meeting["at"])
    h12, ampm = at.hour % 12 or 12, "AM" if at.hour < 12 else "PM"
    time = f"{h12}:{at.minute:02d} {ampm}"
    online = meeting.get("format") == "online"
    if language == "hi-IN":
        return {"date": f"{_DAYS_HI[at.weekday()]}, {at.day} {_MONTHS_HI[at.month - 1]} {at.year}", "time": time,
                "format": "Online (video call)" if online else "मिलकर (in person)"}
    return {"date": at.strftime("%A, %d %B %Y"), "time": time, "format": "Online (video call)" if online else "In person"}


def send_meeting(seller_id: int, phone: Optional[str], meeting: Dict[str, Any], language: str) -> Dict[str, Any]:
    template = os.environ.get("WHATSAPP_MEETING_TEMPLATE", "vani_meeting")
    m = meeting_text(meeting, language)
    if not is_live(FLAG):
        return log("whatsapp", {"mode": "dry_run", "kind": "meeting", "seller_id": seller_id, "to": mask_phone(phone),
                                "template": template, "language": language, **m})
    if not phone:
        return log("whatsapp", {"mode": "live", "kind": "meeting", "seller_id": seller_id, "status": "skipped",
                                "reason": "no phone number"})
    env = require("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")
    import requests
    url = (f"https://graph.facebook.com/{os.environ.get('WHATSAPP_API_VERSION', 'v21.0')}/"
           f"{env['WHATSAPP_PHONE_NUMBER_ID']}/messages")
    payload = {"messaging_product": "whatsapp", "to": "".join(ch for ch in str(phone) if ch.isdigit()), "type": "template",
               "template": {"name": template, "language": {"code": TEMPLATE_LANG.get(language, "en")},
                            "components": [{"type": "body", "parameters": [{"type": "text", "text": m[k]}
                                                                           for k in ("date", "time", "format")]}]}}
    r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {env['WHATSAPP_TOKEN']}"}, timeout=15)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:300]}
    return log("whatsapp", {"mode": "live", "kind": "meeting", "seller_id": seller_id, "to": mask_phone(phone),
                            "template": template, "status": r.status_code,
                            "message_id": (body.get("messages") or [{}])[0].get("id"), "error": body.get("error")})


def send_details(seller_id: int, phone: Optional[str], category: Optional[str], language: str) -> Dict[str, Any]:
    template = os.environ.get("WHATSAPP_TEMPLATE", "vani_details")
    if not is_live(FLAG):
        return log("whatsapp", {"mode": "dry_run", "seller_id": seller_id, "to": mask_phone(phone), "template": template,
                                "category": category, "language": language})
    if not phone:
        return log("whatsapp", {"mode": "live", "seller_id": seller_id, "status": "skipped", "reason": "no phone number"})
    env = require("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")
    import requests
    url = (f"https://graph.facebook.com/{os.environ.get('WHATSAPP_API_VERSION', 'v21.0')}/"
           f"{env['WHATSAPP_PHONE_NUMBER_ID']}/messages")
    r = requests.post(url, json=build_payload(phone, category, language, template),
                      headers={"Authorization": f"Bearer {env['WHATSAPP_TOKEN']}"}, timeout=15)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:300]}
    return log("whatsapp", {"mode": "live", "seller_id": seller_id, "to": mask_phone(phone), "template": template,
                            "status": r.status_code, "message_id": (body.get("messages") or [{}])[0].get("id"),
                            "error": body.get("error")})

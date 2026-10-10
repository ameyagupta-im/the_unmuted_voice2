"""Who may be called, and when (roadmap item 8). Checked before a call starts; written at DO_NOT_CALL.

  1. IndiaMART's own suppression list (SQLite, outputs/integrations/suppression.db): every seller who asked
     not to be called. Always enforced, in every mode.
  2. The national do-not-call preference (NCPR/DND). Live only with VANI_DND_LIVE=1 and DND_CHECK_URL (the
     telecom provider's scrub endpoint, returning {"blocked": bool}); otherwise recorded as not checked.
  3. The calling-hours window, IST (VANI_CALL_HOURS, default 09:00-21:00). Enforced when a real call would be
     placed (VANI_TELEPHONY_LIVE=1) or when VANI_ENFORCE_CALL_HOURS=1. The browser demo places no call, so
     outside the window it only warns.
Legal sign-off is still needed on the window and the DND source (see the roadmap doc).
"""
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from integrations.base import LOG_DIR, is_live, log, mask_phone, require

IST = timezone(timedelta(hours=5, minutes=30))
DB = LOG_DIR / "suppression.db"


@dataclass
class Clearance:
    allowed: bool
    reasons: List[str] = field(default_factory=list)   # why it is blocked
    warnings: List[str] = field(default_factory=list)  # allowed, but worth showing


def _db():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("create table if not exists suppressed (seller_id integer primary key, phone text, reason text, "
                "source text, added_at text)")
    return con


def add(seller_id: int, reason: str, phone: Optional[str] = None, source: str = "vani_call") -> None:
    with _db() as con:
        con.execute("insert or replace into suppressed values (?, ?, ?, ?, ?)",
                    (int(seller_id), mask_phone(phone), reason, source, datetime.now(IST).isoformat(timespec="seconds")))
    log("suppression", {"action": "add", "seller_id": seller_id, "reason": reason, "source": source})


def is_suppressed(seller_id: int) -> Optional[str]:
    with _db() as con:
        row = con.execute("select reason from suppressed where seller_id = ?", (int(seller_id),)).fetchone()
    return row[0] if row else None


def call_window() -> tuple:
    a, b = os.environ.get("VANI_CALL_HOURS", "09:00-21:00").split("-")
    to_min = lambda s: int(s.split(":")[0]) * 60 + int(s.split(":")[1])  # noqa: E731
    return to_min(a), to_min(b)


def in_window(now: Optional[datetime] = None) -> bool:
    now = (now or datetime.now(IST)).astimezone(IST)
    lo, hi = call_window()
    return lo <= now.hour * 60 + now.minute < hi


def check(seller_id: int, phone: Optional[str] = None, now: Optional[datetime] = None) -> Clearance:
    c = Clearance(True)
    why = is_suppressed(seller_id)
    if why:
        c.allowed = False
        c.reasons.append(f"on IndiaMART's do-not-call list ({why})")
    if is_live("VANI_DND_LIVE"):
        env = require("DND_CHECK_URL")
        import requests
        r = requests.get(env["DND_CHECK_URL"], params={"phone": phone}, timeout=10)
        if r.ok and r.json().get("blocked"):
            c.allowed = False
            c.reasons.append("registered on the national do-not-call list (NCPR)")
    else:
        c.warnings.append("national DND not checked (dry run)")
    if not in_window(now):
        lo, hi = call_window()
        msg = f"outside calling hours {lo // 60:02d}:{lo % 60:02d}-{hi // 60:02d}:{hi % 60:02d} IST"
        if is_live("VANI_TELEPHONY_LIVE") or is_live("VANI_ENFORCE_CALL_HOURS"):
            c.allowed = False
            c.reasons.append(msg)
        else:
            c.warnings.append(msg + " (demo: no real call placed)")
    log("suppression", {"action": "check", "seller_id": seller_id, "allowed": c.allowed, "reasons": c.reasons,
                        "warnings": c.warnings})
    return c

"""Shared plumbing for the external integrations (WhatsApp, CRM, suppression, telephony).

Every integration has a DryRun path that only appends a JSON line to outputs/integrations/<name>.jsonl, and a
live path that is used ONLY when its env flag is "1" (e.g. VANI_WHATSAPP_LIVE=1) and its credentials are set.
A missing credential with the flag on is an error, never a silent fallback: a seller must not be told
"I am sending you the details" while nothing is sent.
"""
import json
import os
import time
from typing import Any, Dict

from config import OUTPUTS, load_env

LOG_DIR = OUTPUTS / "integrations"


def is_live(flag: str) -> bool:
    load_env()
    return os.environ.get(flag, "0") == "1"


def require(*names: str) -> Dict[str, str]:
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"live integration needs {', '.join(missing)} in .env")
    return {n: os.environ[n] for n in names}


def log(name: str, record: Dict[str, Any]) -> Dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **record}
    with open(LOG_DIR / f"{name}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return rec


def mask_phone(phone) -> str:
    """Phone numbers never go to logs in full."""
    s = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return f"{'*' * max(0, len(s) - 4)}{s[-4:]}" if s else ""

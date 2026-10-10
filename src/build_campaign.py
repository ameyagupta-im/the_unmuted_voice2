"""Campaign files for Sarvam: one contact list (cohort) per VANI agent, plus the campaign body.

  python src/build_campaign.py --sellers 3419775,1243794 --phones phones.csv [--name "Oct batch 1"] [--days 3]

phones.csv: seller_id,phone (the seller data has no phone numbers). Every seller goes through the same checks as a
call from the web demo: a do-not-call persona or one on IndiaMART's suppression list never enters a list
(integrations.suppression). Calling hours (VANI_CALL_HOURS) become the campaign's allowed schedule.

Writes outputs/sarvam/campaigns/<name>/:
  <agent_key>.csv            "Phone Number" + one column per input variable + initial_bot_message + initial_language_name
  <agent_key>.mapping.json   which column feeds which agent variable / override (the cohort transformation file:
                             its JSON format is not documented -- confirm with "Download Sample" before uploading)
  <agent_key>.campaign.json  POST .../campaigns body (src/sarvam_api.py)
  report.md                  who is in, who was left out and why
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta

from config import OUTPUTS
from data_pipeline import load_seller_master
from integrations import suppression
from persona_generator import generate_persona
from sarvam_api import campaign_body
from sarvam_platform import INPUT_VARIABLES, agent_variables_for

OUT = OUTPUTS / "sarvam" / "campaigns"
# attempt fatigue (E12: Not Interested 46% on the 1st attempt, 57% from the 4th): few retries, spaced out, only
# when nobody picked up
RETRY = {"max_retries": 2, "retry_interval_minutes": [120, 240],
         "retry_on": {"busy": {"enabled": True}, "no_answer": {"enabled": True}, "failed": {"enabled": True},
                      "short_duration": {"enabled": False, "threshold_seconds": 10}}}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def schedule():
    lo, hi = suppression.call_window()
    return {"allowed_start_time": f"{lo // 60:02d}:{lo % 60:02d}", "allowed_end_time": f"{hi // 60:02d}:{hi % 60:02d}",
            "allowed_days": DAYS, "timezone": "Asia/Kolkata"}


def load_phones(path):
    with open(path, encoding="utf-8") as f:
        return {int(r["seller_id"]): r["phone"].strip() for r in csv.DictReader(f) if r.get("phone")}


def build(seller_ids, phones, name, days, sellers=None):
    sellers = load_seller_master() if sellers is None else sellers
    out = OUT / name.replace(" ", "_")
    out.mkdir(parents=True, exist_ok=True)
    rows, left_out = {}, []
    for sid in seller_ids:
        hit = sellers.loc[sellers.fk_glusr_usr_id == sid]
        if hit.empty:
            left_out.append((sid, "not in the seller data"))
            continue
        persona = generate_persona(hit.iloc[0].to_dict()).to_dict()
        if persona["blocked"]:
            left_out.append((sid, f"blocked: {persona['block_reason']}"))
            continue
        why = suppression.is_suppressed(sid)
        if why:
            left_out.append((sid, f"on the do-not-call list ({why})"))
            continue
        if sid not in phones:
            left_out.append((sid, "no phone number in the phones file"))
            continue
        call = agent_variables_for(persona)
        rows.setdefault(call["agent_key"], []).append(
            {"Phone Number": phones[sid], "seller_id": sid, **call["agent_variables"], **call["app_overrides"]})
    ids = json.loads((OUTPUTS / "sarvam" / "agent_ids.json").read_text()) if (OUTPUTS / "sarvam" / "agent_ids.json").exists() else {}
    start = datetime.now() + timedelta(minutes=10)
    for key, rs in rows.items():
        cols = ["Phone Number", "seller_id", *INPUT_VARIABLES, "initial_bot_message", "initial_language_name"]
        with open(out / f"{key}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rs)
        mapping = {"phone_number": "Phone Number", "agent_variables": {v: v for v in INPUT_VARIABLES},
                   "overrides": {"initial_message": "initial_bot_message", "initial_language": "initial_language_name"},
                   "metadata": {"seller_id": "seller_id"}}
        (out / f"{key}.mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        app = ids.get(key) or {"app_id": "", "app_version": None}
        body = campaign_body(f"{name} {key}", app, start.astimezone().isoformat(timespec="seconds"),
                             (start + timedelta(days=days)).astimezone().isoformat(timespec="seconds"), schedule(), RETRY)
        (out / f"{key}.campaign.json").write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [f"# Campaign {name}", "", f"Schedule: {json.dumps(schedule())}", "",
              "| Agent | Contacts |", "|---|---|"] + [f"| {k} | {len(v)} |" for k, v in rows.items()]
    report += ["", "Left out:" if left_out else "Left out: none"] + [f"- {s}: {why}" for s, why in left_out]
    missing = [k for k in rows if not (ids.get(k) or {}).get("app_id")]
    if missing:
        report += ["", f"Agent ids missing in outputs/sarvam/agent_ids.json for: {', '.join(missing)} "
                       "(create the agents first: src/sarvam_deploy.py)."]
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    return rows, left_out, out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sellers", required=True, help="comma-separated seller ids")
    ap.add_argument("--phones", required=True, help="CSV with seller_id,phone")
    ap.add_argument("--name", default=datetime.now().strftime("vani %Y-%m-%d"))
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()
    rows, left, out = build([int(x) for x in a.sellers.split(",")], load_phones(a.phones), a.name, a.days)
    print((out / "report.md").read_text(encoding="utf-8"))

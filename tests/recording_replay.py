"""Before/after on real calls: every moment in the 83 recordings where the old bot
broke the playbook is replayed through the new agent, with the seller's exact
words (verified against the diarized transcripts), and checked against the
playbook action for that scenario.

    python tests/recording_replay.py   -> outputs/recordings/replay_report.md
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from config import OUTPUTS  # noqa: E402
from data_pipeline import load_seller_master  # noqa: E402
from live_engine import LiveCall, _PRICE, _PITCH  # noqa: E402
from persona_generator import generate_persona  # noqa: E402

SELLER = 113839910
CHECKS = {
    "price_query": lambda t, c: [("no price / package / % quoted", not _PRICE.search(t.reply)),
                                 ("says the meeting is free / executive explains",
                                  bool(re.search(r"free|फ्री|मुफ़्त|executive", t.reply, re.I)))],
    "not_interested": lambda t, c: [("does not keep pitching", not _PITCH.search(t.reply) or "whatsapp" in t.reply.lower()),
                                    ("asks a gentle reason or offers the lightest option / exits politely",
                                     "?" in t.reply or c.outcome == "RESPECTFUL_EXIT")],
    "busy": lambda t, c: [("BRIEF or callback goal", t.delivery["mode"] == "BRIEF" or t.delivery["goal"] == "callback"),
                          ("short (<= 30 words)", len(t.reply.split()) <= 30)],
    "not_right_person": lambda t, c: [("goal data_update", t.delivery["goal"] == "data_update"),
                                      ("asks for the right person / number", "?" in t.reply or c.outcome == "CONTACT_UPDATED")],
    "connectivity": lambda t, c: [("CLEAR_AUDIO or call-back", t.delivery["mode"] == "CLEAR_AUDIO" or c.outcome == "CALL_BACK_LATER")],
    "frustration": lambda t, c: [("CALM_EMPATHETIC, no pitch", t.delivery["mode"] == "CALM_EMPATHETIC" and not _PITCH.search(t.reply))],
    "identity_question": lambda t, c: [("says who is calling", bool(re.search(r"IndiaMART|Payal|पायल|virtual assistant", t.reply, re.I)))],
}


def main():
    lessons = json.loads((OUTPUTS / "recordings" / "lessons.json").read_text(encoding="utf-8"))
    learned = json.loads((OUTPUTS / "recordings" / "learned_examples.json").read_text(encoding="utf-8"))
    verified = {q for qs in learned["seller_phrasings"].values() for q in qs}
    sellers = load_seller_master()
    persona = generate_persona(sellers.loc[sellers.fk_glusr_usr_id == SELLER].iloc[0].to_dict()).to_dict()
    rows, ok_n, n, skipped = [], 0, 0, []
    for sig, exs in lessons["scenario_examples"].items():
        if sig not in CHECKS:
            continue
        for e in exs:
            if e.get("ok") or not e.get("seller_quote"):
                continue  # only moments the old bot got WRONG
            quote = e["seller_quote"]
            if len(quote.split()) < 3 and not re.search(r"\?", quote):
                skipped.append(quote)  # diarization fragments ("Madam aadhi") mean nothing without their context
                continue
            call = LiveCall(persona, synthesize_audio=False)
            call.start()
            t = call.seller_turn(text=quote)
            res = CHECKS[sig](t, call)
            ok = all(v for _, v in res)
            ok_n += ok
            n += 1
            rows.append({"scenario": sig, "seller": quote, "old_bot": e.get("agent_response"), "old_bot_issue": e.get("why"),
                         "new_agent": t.reply, "signals": sorted(set(t.signals_tier1) | set(t.signals_tier2)),
                         "mode": t.delivery["mode"], "goal": t.delivery["goal"], "checks": res, "ok": ok,
                         "verified_quote": quote in verified})
            print(f"{'FIXED' if ok else 'STILL WRONG'}  [{sig}] {quote[:60]!r} -> {t.reply[:90]!r}", flush=True)
    md = [f"# Recorded mistakes, replayed through the new agent: {ok_n}/{n} now handled per the playbook", "",
          "Each row is a real seller line from a recorded call where the old bot broke the playbook.",
          f"Excluded as uninterpretable diarization fragments (<3 words, no question): {skipped}",
          "Caveat: each line is replayed into a fresh call, without the original conversation before it.", ""]
    for r in rows:
        md += [f"## {'FIXED' if r['ok'] else 'STILL WRONG'} - {r['scenario']}",
               f"- **Seller (real call):** {r['seller']}",
               f"- **Old bot:** {r['old_bot']}  _({r['old_bot_issue']})_",
               f"- **New agent** _(signals {r['signals']}, mode {r['mode']}, goal {r['goal']})_: {r['new_agent']}"]
        md += [f"  - [{'x' if v else ' '}] {k}" for k, v in r["checks"]]
        md.append("")
    (OUTPUTS / "recordings" / "replay_report.md").write_text("\n".join(md), encoding="utf-8")
    (OUTPUTS / "recordings" / "replay_report.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n{ok_n}/{n} recorded mistakes now handled per the playbook")


if __name__ == "__main__":
    main()

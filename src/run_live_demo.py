"""Voice demo on Sarvam: the same scenario for 3 contrasting real sellers.

For each seller:
  persona_generator -> PersonaSpec
  live_engine.LiveCall  <->  seller_simulator (LLM seller)
  every seller line: simulator text -> Bulbul (seller voice) -> Saaras STT ->
  engine.seller_turn(audio=...)  -- detection runs on real STT output
Writes, per seller, to outputs/demo/<seller_id>/:
  call.wav            full two-sided call audio
  transcript.md       turn-by-turn with live signals and delivery state
  switch_log.json     every mid-call switch: signal, change, reason, evidence
  persona_spec.json   the starting persona
And outputs/demo/demo_summary.json + side_by_side.md.
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from config import OUTPUTS
from data_pipeline import load_seller_master
from integrations import on_call_end, pre_call
from live_engine import LiveCall
from persona_generator import generate_persona, persona_to_markdown
from seller_simulator import SellerSimulator, character_from_persona
from voice_synth import synthesize, concat_wavs

DEMO = [
    {
        "seller_id": 3419775,
        "label": "Chennai idli-machine maker, first contact",
        "temperament": "Polite but time-poor factory owner who speaks only English; analytical; asks what is in it for him.",
        "key_moment": "You did not follow VANI's point; ask what exactly it means and how it helps your machines sell (confusion).",
        "seller_voice": {"en-IN": "deven_en_conversation", "hi-IN": "amit_hi_conversational"},
    },
    {
        "seller_id": 1243794,
        "label": "Delhi clamps trader, called 20 times, past complaint about executive service",
        "temperament": "Irritated Delhi trader, called many times, paid IndiaMART before and felt the executive did nothing; speaks Hinglish. "
                       "If VANI apologises and offers support, accept a support call at a specific time.",
        "key_moment": "Complain: leads hi nahi aate, paisa diya tha kuch nahi hua, and you are tired of repeated calls (complaint + frustration).",
        "seller_voice": {"hi-IN": "amit_hi_conversational", "en-IN": "deven_en_conversation"},
    },
    {
        "seller_id": 56768582,
        "label": "Hyderabad rice-bran firm, Rs 25-100 Cr, busy owner",
        "temperament": "Busy Hyderabad businesswoman, interested if it is quick; Hinglish but far more comfortable in Telugu.",
        "key_moment": "SWITCH_LANGUAGE:te-IN",
        "seller_voice": {"hi-IN": "kavya_hi_conversational", "te-IN": "kavitha_te_conversation", "en-IN": "neha_en_customer"},
    },
]


def run_one(cfg, sellers, out_root: Path):
    row = sellers.loc[sellers.fk_glusr_usr_id == cfg["seller_id"]].iloc[0].to_dict()
    spec = generate_persona(row)
    persona = spec.to_dict()
    out = out_root / str(cfg["seller_id"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "persona_spec.json").write_text(json.dumps(persona, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "persona_spec.md").write_text(persona_to_markdown(spec), encoding="utf-8")

    clearance = pre_call(cfg["seller_id"])
    if not clearance.allowed:
        print(f"=== {cfg['seller_id']} not called: {'; '.join(clearance.reasons)} ===")
        return None
    call = LiveCall(persona)
    sim = SellerSimulator(character_from_persona(persona, cfg["key_moment"], cfg["temperament"], cfg["seller_voice"]))
    clips, lines = [], []
    print(f"\n=== {cfg['seller_id']} | {cfg['label']} | {spec.seller_type_label} | goal={spec.goal.value} | "
          f"{persona['voice']['bot_name']['value']} / {persona['voice']['speaker']['value']} ===")

    r = call.start()
    start_delivery = r.delivery
    clips.append(r.audio)
    lines.append(f"**VANI** _(speaker {r.delivery['speaker']}, pace {r.delivery['pace']}, mode {r.delivery['mode']})_: {r.reply}")
    print("VANI:", r.reply)
    vani_said = r.reply
    while not call.ended:
        nxt = sim.next_line(vani_said)
        if nxt is None:
            break
        seller_audio = synthesize(nxt["line"], speaker=sim.voice_for(nxt["language"]), language_code=nxt["language"], pace=1.0)
        clips.append(seller_audio)
        r = call.seller_turn(audio=seller_audio)
        clips.append(r.audio)
        print(f"SELLER ({nxt['language']}): {nxt['line']}\n   STT[{r.stt_language}]: {r.seller_text}")
        for sw in r.switches:
            print(f"   >> {sw['kind'].upper()} SWITCH {sw['signal']} via {sw['detector']}: {sw['change_made']}")
        print(f"VANI [{r.delivery['mode']}, goal {r.delivery['goal']}, {r.delivery['language']}, pace {r.delivery['pace']}]: "
              f"{r.reply}  {r.latency_ms}")
        lines.append(f"**Seller** ({nxt['language']}, beat: {nxt['beat']}): {nxt['line']}  \n"
                     f"_STT ({r.stt_language}):_ {r.seller_text}  _signals {sorted(set(r.signals_tier1) | set(r.signals_tier2))}, "
                     f"hang-up risk {r.hangup_risk}_")
        for sw in r.switches:
            lines.append(f"> **{sw['kind'].upper()} SWITCH - {sw['signal']}** (detected by {sw['detector']}, t={sw['t_sec']}s): "
                         f"{json.dumps(sw['change_made'], ensure_ascii=False)} - {sw['reason']}")
        lines.append(f"**VANI** _(mode {r.delivery['mode']}, goal {r.delivery['goal']}, pace {r.delivery['pace']}, "
                     f"latency {r.latency_ms})_: {r.reply}")
        vani_said = r.reply

    concat_wavs(clips, str(out / "call.wav"))
    summ = call.summary()
    summ["integrations"] = on_call_end(call, f"demo_{cfg['seller_id']}")
    (out / "switch_log.json").write_text(json.dumps(summ["switch_log"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "call_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "transcript.md").write_text(
        f"# Live demo call - seller {cfg['seller_id']}\n{cfg['label']}  \nSeller type: {spec.seller_type_label}  \n"
        f"Primary goal: {spec.goal.value}  \nGoal path: {' -> '.join(summ['goal_history'])}  \nFinal outcome: {call.outcome} "
        f"({summ['seller_disposition']}, goal achieved: {summ['goal_achieved']})  \nSeller insights: "
        f"{json.dumps(summ['seller_insights'], ensure_ascii=False)}\n\n" + "\n\n".join(lines), encoding="utf-8")
    return {"seller_id": cfg["seller_id"], "label": cfg["label"], "seller_type": spec.seller_type_label,
            "goal": spec.goal.value, "bot": persona["voice"]["bot_name"]["value"], "start": start_delivery,
            "end": summ["final_delivery"], "goal_path": " -> ".join(summ["goal_history"]),
            "switches": [(s["turn"], s["kind"], s["signal"], s["detector"]) for s in summ["switch_log"]],
            "outcome": call.outcome, "goal_achieved": summ["goal_achieved"], "turns": call.turn}


def main(only=None):
    out_root = OUTPUTS / "demo"
    out_root.mkdir(parents=True, exist_ok=True)
    sellers = load_seller_master()
    results = []
    for cfg in DEMO:
        if only and cfg["seller_id"] not in only:
            continue
        t = time.time()
        res = run_one(cfg, sellers, out_root)
        if res is None:
            continue
        res["wall_sec"] = round(time.time() - t, 1)
        results.append(res)
    (out_root / "demo_summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md = ["# Same scenario, three contrasting sellers", "",
          "| | " + " | ".join(str(r["seller_id"]) for r in results) + " |", "|---|" + "---|" * len(results)]
    for label, fn in [("Seller", lambda r: r["label"]), ("Seller type", lambda r: r["seller_type"]),
                      ("Bot / voice", lambda r: f"{r['bot']} / {r['start']['speaker']}"),
                      ("Start language / pace", lambda r: f"{r['start']['language']} / {r['start']['pace']}"),
                      ("Empathy / assertiveness", lambda r: f"{r['start']['empathy']} / {r['start']['assertiveness']}"),
                      ("Primary goal", lambda r: r["goal"]), ("Goal path", lambda r: r["goal_path"]),
                      ("Live switches", lambda r: "; ".join(f"t{t} {k}:{s} ({d})" for t, k, s, d in r["switches"]
                                                            if k != "recovery")),
                      ("End voice / language", lambda r: f"{r['end']['speaker']} / {r['end']['language']}"),
                      ("Outcome (goal achieved)", lambda r: f"{r['outcome']} ({r['goal_achieved']})")]:
        md.append(f"| {label} | " + " | ".join(str(fn(r)) for r in results) + " |")
    (out_root / "side_by_side.md").write_text("\n".join(md), encoding="utf-8")
    print("\n" + "\n".join(md))


if __name__ == "__main__":
    only = {int(x) for x in sys.argv[1:]} or None
    main(only)

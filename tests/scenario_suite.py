"""Live scenario suite: every scenario in the Seller Call Scenarios playbook
(scenarios.pdf), run through the real engine and Sarvam LLM (text mode, no TTS).

    python tests/scenario_suite.py      -> outputs/scenarios/scenario_report.md + .json

Seller lines are the playbook's own examples, plus real phrasings from the 83
recordings where the playbook gives none. Each scenario asserts what the
playbook says must happen (signal, persona mode, goal switch, outcome,
guardrails), so a failure points at the exact rule that broke.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from config import OUTPUTS  # noqa: E402
from data_pipeline import load_seller_master  # noqa: E402
from live_engine import LiveCall, _PRICE, _PITCH, q_offer_call  # noqa: E402
from persona_generator import generate_persona  # noqa: E402

SELLERS = load_seller_master()
MEETING_SELLER = 113839910      # warm, interested lead; pre-call goal = meeting
SMALL_TRADER = 19070168         # small local trader; pre-call goal = nurture
ENGLISH_SELLER = 3419775        # English-preferring professional


def persona(sid):
    return generate_persona(SELLERS.loc[SELLERS.fk_glusr_usr_id == sid].iloc[0].to_dict()).to_dict()


def _last_q(text):
    qs = [x for x in re.split(r"(?<=[.?!।])\s*", text or "") if x.strip().endswith("?")]
    return qs[-1] if qs else ""


def run(sid, lines):
    call = LiveCall(persona(sid), synthesize_audio=False)
    turns = [call.start()]
    for ln in lines:
        if call.ended:
            break
        turns.append(call.seller_turn(text=ln))
    return call, turns


def signals(t):
    return set(t.signals_tier1) | set(t.signals_tier2)


def switches(call, kind=None):
    return [s for s in call.switch_log if kind is None or s.kind == kind]


def has_goal_switch(call, goal):
    return any(s.kind == "goal" and s.change_made["goal"][1] == goal for s in call.switch_log)


SCENARIOS = [
    ("1 Do-not-call", MEETING_SELLER, ["mujhe dobara call mat karna, number hata do"],
     lambda c, t: [("signal do_not_call", "do_not_call" in signals(t[1])), ("outcome DO_NOT_CALL", c.outcome == "DO_NOT_CALL"),
                   ("call ended", c.ended), ("closing is a statement", not t[-1].reply.strip().endswith("?"))]),
    ("2 Connectivity (twice)", MEETING_SELLER, ["hello? awaaz nahi aa rahi", "hello hello? kuch sunai nahi de raha, awaaz toot rahi hai"],
     lambda c, t: [("mode CLEAR_AUDIO after first", t[1].delivery["mode"] == "CLEAR_AUDIO"),
                   ("outcome CALL_BACK_LATER", c.outcome == "CALL_BACK_LATER")]),
    ("3 Frustration (twice)", MEETING_SELLER, ["kitni baar call karoge, pareshan kar diya", "bas karo, dimaag kharab kar diya aap logon ne"],
     lambda c, t: [("mode CALM_EMPATHETIC", t[1].delivery["mode"] == "CALM_EMPATHETIC"),
                   # fed up with being CALLED: the lightest option is WhatsApp, never another call (live session 125638)
                   ("goal -> WhatsApp, no further call offered", t[1].delivery["goal"] in ("info_whatsapp", "respectful_exit")
                    and not q_offer_call(t[1].reply)),
                   ("no pitch after frustration", not _PITCH.search(t[1].reply)),
                   ("outcome ESCALATED_EXIT", c.outcome == "ESCALATED_EXIT")]),
    ("4 Complaint, then support time (playbook example)", MEETING_SELLER,
     ["haan ji", "kaam theek chal raha hai par IndiaMART se enquiry bahut kam aati hai",
      "leads hi nahi aate, paisa diya tha kuch nahi hua", "kal shaam 5 baje"],
     lambda c, t: [("need -> goal meeting kept", t[2].delivery["goal"] == "meeting"),
                   ("complaint -> goal complaint_recovery", has_goal_switch(c, "complaint_recovery")),
                   ("mode CALM_EMPATHETIC", any(x.delivery["mode"] == "CALM_EMPATHETIC" for x in t)),
                   ("no pitch after complaint", not any(_PITCH.search(x.reply) for x in t[3:])),
                   ("outcome COMPLAINT_LOGGED", c.outcome == "COMPLAINT_LOGGED"),
                   ("slot captured", bool(c.slot))]),
    ("5 Are you a bot?", MEETING_SELLER, ["aap robot ho kya?"],
     lambda c, t: [("signal ai_bot_suspicion", "ai_bot_suspicion" in signals(t[1])),
                   ("says virtual assistant", bool(re.search(r"virtual assistant|वर्चुअल असिस्टेंट", t[1].reply, re.I))),
                   ("never claims human", not re.search(r"insaan|इंसान|human", t[1].reply, re.I))]),
    ("6 Who is calling / why", MEETING_SELLER, ["kaun bol raha hai? kis liye call kiya?"],
     lambda c, t: [("signal identity_question", "identity_question" in signals(t[1])),
                   ("gives name", "Payal" in t[1].reply or "पायल" in t[1].reply or "virtual assistant" in t[1].reply),
                   ("call continues", not c.ended)]),
    ("7 Not the right person", MEETING_SELLER, ["main owner nahi hoon, sir se baat kijiye", "unka naam Ramesh hai, number 9876543210"],
     lambda c, t: [("goal -> data_update", has_goal_switch(c, "data_update")),
                   ("outcome CONTACT_UPDATED", c.outcome == "CONTACT_UPDATED")]),
    ("8 Already with an executive", MEETING_SELLER, ["hamare executive Rakesh ji pehle se aate hain",
                                                     "unse bolna hamara catalog update karna hai"],
     lambda c, t: [("goal -> exec_handoff", has_goal_switch(c, "exec_handoff")),
                   ("reassures and offers the account manager (master 8)", "account manager" in t[1].reply),
                   ("a described need -> meeting with two slots", t[2].delivery["goal"] == "meeting"
                    and bool(re.search(r"11 बजे|11 AM", t[2].reply)))]),
    ("8b Already with an executive, nothing more", MEETING_SELLER, ["hamare executive Rakesh ji pehle se aate hain", "nahi ji, aur kuch nahi"],
     lambda c, t: [("outcome EXEC_HANDOFF", c.outcome == "EXEC_HANDOFF"), ("offer not repeated", "account manager" not in t[2].reply)]),
    # master intent 9: one two-option reason question, then the RESPECTFUL_EXIT line; nothing sent unasked (10 Oct)
    ("9 Not interested (twice)", MEETING_SELLER, ["nahi chahiye", "nahi chahiye, interest nahi hai"],
     lambda c, t: [("first no: the two-option reason question", not t[1].end_call and "पहले से काफ़ी काम" in t[1].reply),
                   ("outcome RESPECTFUL_EXIT", c.outcome == "RESPECTFUL_EXIT"),
                   ("no WhatsApp offered or promised", not re.search(r"whats\s*app|व्हाट्सएप", t[-1].reply, re.I))]),
    ("9b Refused with a reason", MEETING_SELLER, ["abhi zaroorat nahi hai, stock already full hai"],
     lambda c, t: [("outcome RESPECTFUL_EXIT", c.outcome == "RESPECTFUL_EXIT"),
                   ("no WhatsApp, no question", not re.search(r"whats\s*app|व्हाट्सएप", t[1].reply, re.I)
                    and not t[1].reply.strip().endswith("?"))]),
    ("10 Busy", MEETING_SELLER, ["abhi busy hoon, jaldi bataiye"],
     lambda c, t: [("mode BRIEF", t[1].delivery["mode"] == "BRIEF"), ("goal -> callback", t[1].delivery["goal"] == "callback"),
                   ("short reply (<= 30 words)", len(t[1].reply.split()) <= 30)]),
    ("11 Wants a human", MEETING_SELLER, ["manager se baat karao", "kal subah 11 baje"],
     lambda c, t: [("goal -> human_handoff", has_goal_switch(c, "human_handoff")),
                   ("outcome HUMAN_HANDOFF", c.outcome == "HUMAN_HANDOFF")]),
    ("12 Wants WhatsApp", MEETING_SELLER, ["WhatsApp pe details bhej do"],
     lambda c, t: [("outcome INFO_SENT", c.outcome == "INFO_SENT"),
                   ("confirms and closes (master intent 12)", c.ended and not t[-1].reply.strip().endswith("?"))]),
    ("12b Question about the WhatsApp details", MEETING_SELLER, ["haan ji", "WhatsApp pe kya details milegi?"],
     lambda c, t: [("question is not a request", "wants_whatsapp" not in signals(t[2])),
                   ("call continues", not c.ended and c.outcome == "IN_PROGRESS"),
                   ("answers then asks", t[2].reply.strip().endswith("?"))]),
    # master 4.1: the meeting is fixed after "milkar ya online?" is answered
    ("13 Gives a time (meeting)", MEETING_SELLER, ["haan ji", "kaam achha chal raha hai, aur buyers chahiye", "kal shaam 5 baje", "online"],
     lambda c, t: [("asks milkar or online first", t[3].call_outcome == "IN_PROGRESS" and bool(re.search(r"online", t[3].reply, re.I))),
                   ("outcome MEETING_FIXED", c.outcome == "MEETING_FIXED"), ("goal achieved yes", c.summary()["goal_achieved"] == "yes")]),
    ("13b Meeting time outside 9-6", MEETING_SELLER, ["haan ji", "kaam achha chal raha hai, aur buyers chahiye", "kal shaam 7 baje"],
     lambda c, t: [("not fixed at 7 PM", c.outcome != "MEETING_FIXED"),
                   ("offers a slot inside the window", bool(re.search(r"नौ|छह|6 बजे|6 PM|12", t[3].reply)))]),
    # IndiaMART 10 Oct (2): still insisting on other hours -> timings fixed, details on WhatsApp
    ("13e Insists on hours outside 9-6", MEETING_SELLER,
     ["haan ji", "kaam achha chal raha hai, aur buyers chahiye", "kal raat 8 baje", "nahi, raat 8 baje hi ho payega"],
     lambda c, t: [("told the window first", "छह" in t[3].reply and not t[3].end_call),
                   ("then: timings fixed, WhatsApp details, closed", c.outcome == "INFO_SENT" and "fixed" in t[-1].reply)]),
    ("13f Silence", MEETING_SELLER, ["haan ji", ""],
     lambda c, t: [("asks if they were saying something", "क्या आप कुछ कह रहे थे?" in t[2].reply), ("call continues", not c.ended)]),
    # IndiaMART 10 Oct: the seller confirms the slot; the bot takes the option they chose
    ("13d Seller picks the second slot", MEETING_SELLER, ["haan ji", "haan bataiye", "dusra wala theek rahega", "milkar"],
     lambda c, t: [("not fixed before in person / online", c.outcome == "MEETING_FIXED" and t[-2].call_outcome == "IN_PROGRESS"),
                   ("the chosen slot (day after, 4 PM) is fixed", bool(c.summary()["meeting"])
                    and c.summary()["meeting"]["at"].endswith("T16:00")),
                   ("closing names the slot", "4 बजे" in t[-1].reply)]),
    ("13c Buy-lead question", MEETING_SELLER, ["haan ji", "aur buy leads kahan milenge?"],
     lambda c, t: [("points to the seller dashboard", "seller dashboard" in t[2].reply and "BuyLeads" in t[2].reply),
                   ("no meeting ask", not _PITCH.search(t[2].reply))]),
    ("14 Language change", MEETING_SELLER, ["Can you speak in English please?"],
     lambda c, t: [("language -> en-IN", t[1].delivery["language"] == "en-IN"),
                   ("voice unchanged", t[1].delivery["speaker"] == t[0].delivery["speaker"]),
                   ("reply in English", not re.search(r"[ऀ-ॿ]", t[1].reply))]),
    ("15 Need: few enquiries", SMALL_TRADER, ["haan ji", "enquiry bahut kam aati hai"],
     lambda c, t: [("goal -> meeting", t[2].delivery["goal"] == "meeting"),
                   ("offers the executive's help", bool(_PITCH.search(t[2].reply) or "executive" in t[2].reply))]),
    ("16 Price question", MEETING_SELLER, ["kitna charge lagega?"],
     lambda c, t: [("no price quoted", not _PRICE.search(t[1].reply)),
                   ("master price line, nothing called free", bool(re.search(r"charges|executive", t[1].reply, re.I))
                    and not re.search(r"free|फ्री|मुफ़्त|निःशुल्क", t[1].reply, re.I))]),
    ("17 Confusion", MEETING_SELLER, ["matlab? samjha nahi"],
     lambda c, t: [("mode SIMPLE", t[1].delivery["mode"] == "SIMPLE")]),
    ("18 Clear interest", MEETING_SELLER, ["kab aayenge? kaise hoga?"],
     lambda c, t: [("mode ENGAGED", t[1].delivery["mode"] == "ENGAGED"), ("goal meeting", t[1].delivery["goal"] == "meeting")]),
    ("20 Context captured", MEETING_SELLER, ["hum cotton fabric banate hain, Surat mein factory hai, export bhi karte hain"],
     lambda c, t: [("insight captured", bool(c.summary()["seller_insights"])),
                   ("not echoed back verbatim", "Surat mein factory" not in t[1].reply)]),
    # Chennai live session 3419775_20261009_231212, the seller's own lines
    ("21 Sarcastic flip after a pitch", ENGLISH_SELLER,
     ["Nahi achha nahi chal raha, bilkul achha nahi chal raha.", "Bilkul kharab chal raha hai.",
      "Are sab badhiya chal raha hai, itna badhiya business hai, mujhe inquiries bhi aa rahi hai, sab ho raha hai."],
     lambda c, t: [("understanding question not re-asked", not re.search(r"कैसा चल रहा|how is your", _last_q(t[1].reply) + _last_q(t[2].reply), re.I)),
                   ("flip noticed (sarcasm or one clarification)", any(s.kind == "clarify" for s in c.switch_log)),
                   ("never 'good to hear'", not re.search(r"अच्छा लगा|good to hear|glad", t[3].reply, re.I)),
                   ("no pitch on the flip turn", not _PITCH.search(t[3].reply))]),
    ("22 Genuine flip is clarified once", MEETING_SELLER,
     ["kaam theek nahi chal raha", "haan enquiry to aa rahi hai", "haan, order nahi ban rahe"],
     lambda c, t: [("one clarifying question", sum(s.signal == "contradiction" for s in c.switch_log) == 1),
                   ("asks about orders", bool(re.search(r"order", t[2].reply, re.I)) and t[2].reply.strip().endswith("?")),
                   ("answer resolved and logged", any(s.signal == "clarify_resolved" for s in c.switch_log)),
                   ("goal meeting (executive helps conversion)", t[3].delivery["goal"] == "meeting")]),
    # live session 3419775_20261010_125638, the seller's own lines
    ("23 Repeated-calls venting, then engaged", ENGLISH_SELLER,
     ["", "Yaar kyon baar baar phone karte ho?", "Abhi main bol raha hoon baar baar call karte ho, kal phir se call karogi aap log."],
     lambda c, t: [("silence -> 'were you saying something?'", bool(re.search(r"आवाज़|were you saying something", t[1].reply, re.I))),
                   ("no further call offered", not q_offer_call(t[2].reply) and not q_offer_call(t[3].reply)),
                   ("seller still talking: not cut (IndiaMART 10 Oct)", not c.ended)]),
    ("24 Frustrated but asking: answered, not cut", MEETING_SELLER,
     ["kitni baar call karoge", "pareshan ho gaya hoon, ye bataiye charge kitna lagta hai?"],
     lambda c, t: [("call kept going", not c.ended), ("price question answered", bool(re.search(r"charge|executive|चार्ज|एग्ज़ी|एक्ज़ि", t[2].reply, re.I)))]),
    # master section 11, meeting example, the seller's lines word for word
    ("25 Master example: meeting", MEETING_SELLER, ["haan ji", "haan bataiye", "haan theek hai", "milne ka time nahi hai", "haan"],
     lambda c, t: [("two concrete slots offered", len(__import__("live_engine")._offered_slots(t[2].reply)) == 2),
                   ("outcome MEETING_FIXED, online", c.outcome == "MEETING_FIXED" and "online" in t[-1].reply),
                   ("WhatsApp confirmation only for the agreed meeting", bool(c.summary()["meeting"]))]),
    ("Fatigued seller first reply", 2890493, ["haan ji"],
     lambda c, t: [("greeting has no apology, first reply opens with it", not re.search(r"माफ़ी|sorry", t[0].reply, re.I)
                    and bool(re.search(r"^(दोबारा call करने के लिए माफ़ी|sorry)", t[1].reply, re.I)))]),
    ("Cautious seller first reply", 1243794, ["haan ji"],
     lambda c, t: [("goal complaint_recovery", c.persona["goal"]["value"] == "complaint_recovery"),
                   ("opens on the complaint, no pitch", not _PITCH.search(t[1].reply))]),
    ("English seller", ENGLISH_SELLER, ["Who is this?"],
     lambda c, t: [("English throughout", not any(re.search(r"[ऀ-ॿ]", x.reply) for x in t))]),
]


def main():
    out_dir = OUTPUTS / "scenarios"
    out_dir.mkdir(parents=True, exist_ok=True)
    results, passed, total = [], 0, 0
    for name, sid, lines, checks in SCENARIOS:
        t0 = time.time()
        try:
            call, turns = run(sid, lines)
            res = checks(call, turns)
            err = None
        except Exception as e:
            call, turns, res, err = None, [], [("ran without error", False)], repr(e)
        ok = all(v for _, v in res)
        passed += sum(v for _, v in res)
        total += len(res)
        results.append({
            "scenario": name, "seller": sid, "ok": ok, "checks": [{"check": k, "pass": bool(v)} for k, v in res], "error": err,
            "conversation": [{"seller": tr.seller_text, "vani": tr.reply, "signals": sorted(signals(tr)),
                              "mode": tr.delivery["mode"], "goal": tr.delivery["goal"], "outcome": tr.call_outcome}
                             for tr in turns],
            "switch_log": [{"kind": s.kind, "signal": s.signal, "detector": s.detector, "change": s.change_made}
                           for s in (call.switch_log if call else [])],
            "seconds": round(time.time() - t0, 1)})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  " + "; ".join(f"{k}={'ok' if v else 'NO'}" for k, v in res), flush=True)
    (out_dir / "scenario_report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Playbook scenario suite: {sum(r['ok'] for r in results)}/{len(results)} scenarios, {passed}/{total} checks", ""]
    for r in results:
        md.append(f"## {'PASS' if r['ok'] else 'FAIL'} - {r['scenario']} (seller {r['seller']})")
        md += [f"- [{'x' if c['pass'] else ' '}] {c['check']}" for c in r["checks"]]
        for turn in r["conversation"]:
            if turn["seller"]:
                md.append(f"  - **Seller:** {turn['seller']}  _signals {turn['signals']}_")
            md.append(f"  - **VANI** _({turn['mode']}, goal {turn['goal']}, {turn['outcome']})_: {turn['vani']}")
        md.append("")
    (out_dir / "scenario_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n{sum(r['ok'] for r in results)}/{len(results)} scenarios passed, {passed}/{total} checks")


if __name__ == "__main__":
    main()

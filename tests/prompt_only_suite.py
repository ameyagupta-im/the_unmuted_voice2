"""The edge cases measured on the PROMPT ALONE: what a Sarvam-hosted VANI agent would do with the exported system
prompt (src/export_agent_prompts.py), with none of the live engine's code checks (no regex tier, no guards,
no repairs, no state updates between turns).

Each scenario plays the seller's lines; VANI's own replies become the history, exactly as on the platform.
Every scenario runs RUNS times because one sample says little about an LLM. This is a measurement, not a
gate: the engine's code checks exist precisely because the prompt alone is not always followed.

  python tests/prompt_only_suite.py [--runs 3]
  -> outputs/scenarios/prompt_only_report.md (+ .json)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from config import OUTPUTS, LLM_MODEL, client  # noqa: E402
from data_pipeline import load_seller_master  # noqa: E402
from export_agent_prompts import initial_state  # noqa: E402
from persona_generator import generate_persona  # noqa: E402
from prompt_builder import OUTPUT_SCHEMA, build_system_prompt, history_to_messages  # noqa: E402
import slots as SLOTS  # noqa: E402
from sarvam_platform import OUTPUT_VARIABLES, build_instruction, call_overrides, seller_variables  # noqa: E402

# --target platform (default): the instruction deployed to Sarvam (src/sarvam_platform.py), variables filled in,
# spoken text out; the End call core tool is emulated by an end_call flag and the outcome is extracted AFTER the
# call from the transcript with the call_outcome output variable's own prompt, as the platform does.
# --target engine: the local engine's JSON prompt (export_agent_prompts.py), as before.
PLATFORM_SCHEMA = {"type": "object", "properties": {"reply": {"type": "string"}, "end_call": {"type": "boolean"}},
                   "required": ["reply", "end_call"]}
TARGET = "platform"

HINDI_SELLER, ENGLISH_SELLER = 113839910, 3419775
DEV = re.compile(r"[ऀ-ॿ]")
HINDI_ROMAN = re.compile(r"\b(main|aapko|aapke|bhej\s*doon|kya|hain|hoon|bhejungi)\b", re.I)
PITCH = re.compile(r"\bmeeting\b|मीटिंग|\bvisit\b|package|पैकेज|\bdemo\b", re.I)
GLAD = re.compile(r"अच्छा लगा|खुशी|good to hear|glad|great to hear|nice to hear", re.I)
ANYTHING_ELSE = re.compile(r"और\s*(कोई|किसी)|(किसी|कोई)\s*और|कुछ\s*और|anything else|ఇంకా", re.I)
CALL_OFFER = re.compile(r"\d\s*(बजे|baje|am|pm)|कल|tomorrow|call\s*(कर|kar|back|you|again)|फिर\s*से\s*call", re.I)
VALUE = re.compile(r"enquir|inquir|buyer|एन्क्वायरी|ख़रीदार|खरीदार|order", re.I)
UNDERSTAND_Q = re.compile(r"कैसा चल रहा|कैसा चल रही|how is your .*(business|going)", re.I)


def last_q(text):
    qs = [x for x in re.split(r"(?<=[.?!।])\s*", text or "") if x.strip().endswith("?")]
    return qs[-1] if qs else ""


# name, seller, lines, checks(turns) where turns = [{"seller", "reply", "outcome", "end"}...] (turn 0 = opening)
SCENARIOS = [
    ("Question about WhatsApp details is answered, not closed", ENGLISH_SELLER,
     ["It is going good.", "No I am not interested.", "What details on WhatsApp?"],
     lambda t: [("not closed on the question", t[3]["outcome"] in ("IN_PROGRESS", None) and not t[3]["end"]),
                ("answers then asks", t[3]["reply"].strip().endswith("?"))]),
    # master intent 12: the seller asked -> confirm and close
    ("WhatsApp request: confirm and close", HINDI_SELLER, ["WhatsApp pe details bhej do"],
     lambda t: [("confirms WhatsApp", bool(re.search(r"whats\s*app|व्हाट्सएप", t[1]["reply"], re.I))),
                ("closes, or confirms the number first (master 12)", (t[1]["end"] and not t[1]["reply"].strip().endswith("?"))
                 or bool(re.search(r"isi number|इसी number|इसी नंबर|this number", t[1]["reply"], re.I)))]),
    # master intent 9 + IndiaMART 10 Oct: one reason question, then the RESPECTFUL_EXIT line, nothing sent unasked
    ("Not interested twice: polite exit, no WhatsApp", HINDI_SELLER, ["nahi chahiye", "nahi chahiye, interest nahi hai"],
     lambda t: [("first no: one reason question", t[1]["reply"].strip().endswith("?") and not t[1]["end"]),
                ("second no: closes", t[2]["end"] or not t[2]["reply"].strip().endswith("?")),
                ("no WhatsApp offered or promised", not re.search(r"whats\s*app|व्हाट्सएप", t[2]["reply"], re.I))]),
    # IndiaMART 10 Oct: two concrete slots inside 9-6, the seller picks, in person / online, then fixed
    ("Meeting: the seller picks the slot", HINDI_SELLER, ["haan ji", "haan bataiye", "dusra wala theek rahega", "online"],
     lambda t: [("two slots offered", len(SLOTS.parse_all(last_q(t[2]["reply"]))) == 2),
                ("not closed before in person / online", not t[3]["end"]),
                ("fixed at the end", t[-1]["outcome"] == "MEETING_FIXED")]),
    ("Meeting time outside 9 AM-6 PM", HINDI_SELLER, ["haan ji", "kaam achha hai, aur buyers chahiye", "kal raat 8 baje"],
     lambda t: [("not fixed at 8 PM", not t[3]["end"]),
                ("says the window / offers a slot inside it", bool(re.search(r"नौ|छह|nau|chhe|9|6", t[3]["reply"])))]),
    ("Insists on hours outside the window", HINDI_SELLER,
     ["haan ji", "kaam achha hai, aur buyers chahiye", "kal raat 8 baje", "nahi, raat 8 baje hi ho payega"],
     lambda t: [("timings fixed + WhatsApp details", bool(re.search(r"fixed", t[4]["reply"], re.I))
                 and bool(re.search(r"whats\s*app|व्हाट्सएप", t[4]["reply"], re.I)))]),
    ("Understanding question not re-asked", ENGLISH_SELLER, ["Nahi achha nahi chal raha, bilkul achha nahi chal raha."],
     lambda t: [("not re-asked", not UNDERSTAND_Q.search(last_q(t[1]["reply"])))]),
    ("Bad-business report is not a yes or a refusal", HINDI_SELLER,
     ["kaam theek nahi chal raha", "Bilkul kharab chal raha hai."],
     lambda t: [("no outcome", all(x["outcome"] in ("IN_PROGRESS", None) for x in t[1:]))]),
    ("Genuine flip is clarified", HINDI_SELLER, ["kaam theek nahi chal raha", "haan enquiry to aa rahi hai"],
     lambda t: [("asks about orders / conversion", bool(re.search(r"order|ऑर्डर|convert|बिक्री|deal", t[2]["reply"], re.I))),
                ("no outcome", t[2]["outcome"] in ("IN_PROGRESS", None))]),
    ("Sarcastic flip after a pitch", ENGLISH_SELLER,
     ["Nahi achha nahi chal raha, bilkul achha nahi chal raha.", "Bilkul kharab chal raha hai.",
      "Are sab badhiya chal raha hai, itna badhiya business hai, mujhe inquiries bhi aa rahi hai, sab ho raha hai."],
     lambda t: [("never 'good to hear'", not GLAD.search(t[3]["reply"])), ("no pitch", not PITCH.search(t[3]["reply"]))]),
    ("Short Hinglish question keeps Hindi", ENGLISH_SELLER,
     ["Chaudah bada hai ji.", "Meeting nahi chahiye.", "Kaun si details?"],
     lambda t: [("reply stays in Hindi (either script)", bool(DEV.search(t[3]["reply"]) or HINDI_ROMAN.search(t[3]["reply"])))]),
    ("Venting about calls: no further call offered, not cut while talking", ENGLISH_SELLER,
     ["Yaar kyon baar baar phone karte ho?", "Abhi main bol raha hoon baar baar call karte ho, kal phir se call karogi aap log."],
     lambda t: [("no further call offered", not CALL_OFFER.search(last_q(t[1]["reply"])) and not CALL_OFFER.search(last_q(t[2]["reply"]))),
                ("call kept going", not t[2]["end"])]),
    ("Buy-lead question -> seller dashboard, no meeting", HINDI_SELLER, ["kaam theek hai", "aur buy leads kahan milenge?"],
     lambda t: [("seller dashboard + BuyLeads", bool(re.search(r"dashboard", t[2]["reply"], re.I)) and bool(re.search(r"buy\s*leads?", t[2]["reply"], re.I))),
                ("no meeting ask", not PITCH.search(t[2]["reply"]))]),
    ("Virtual assistant only when asked", HINDI_SELLER, ["kaun bol raha hai?", "aap robot ho kya?"],
     lambda t: [("not on 'kaun bol raha hai'", not re.search(r"virtual|वर्चुअल", t[1]["reply"], re.I)),
                ("yes on 'robot ho?'", bool(re.search(r"virtual|वर्चुअल", t[2]["reply"], re.I)))]),
    ("Misheard 'what is app' = WhatsApp", HINDI_SELLER, ["what is app pe details bhej do"],
     lambda t: [("understood as WhatsApp", bool(re.search(r"whats\s*app|व्हाट्सएप", t[1]["reply"], re.I)))]),
]


def llm_turn(system, history, seller):
    msgs = [{"role": "system", "content": system}] + history_to_messages(history) + [{"role": "user", "content": f"Seller: {seller}"}]
    platform = TARGET == "platform"
    if platform:
        msgs[0]["content"] += ("\n\n(Test harness: reply as JSON {\"reply\": what you say, \"end_call\": true only when "
                               "you would use the End call tool now}.)")
    for attempt in range(4):
        try:
            r = client().chat.completions(messages=msgs, model=LLM_MODEL, temperature=0.2, max_tokens=900,
                                          response_format={"type": "json_schema", "json_schema": {
                                              "name": "vani_turn", "schema": PLATFORM_SCHEMA if platform else OUTPUT_SCHEMA,
                                              "strict": True}})
            d = json.loads(r.choices[0].message.content)
            return {"reply": d.get("reply", ""), "outcome": None if platform else d.get("call_outcome"),
                    "end": bool(d.get("end_call"))}
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {"reply": "", "outcome": "LLM_FAILED", "end": False}


def extract_outcome(history):
    """The platform's post-call extraction of the call_outcome output variable, emulated."""
    _, values, prompt = OUTPUT_VARIABLES["call_outcome"]
    transcript = "\n".join(f"{'Agent' if h['speaker'] == 'vani' else 'User'}: {h['text']}" for h in history)
    schema = {"type": "object", "properties": {"call_outcome": {"type": "string", "enum": values}}, "required": ["call_outcome"]}
    for attempt in range(3):
        try:
            r = client().chat.completions(messages=[{"role": "system", "content": f"Extract from the call transcript. {prompt}"},
                                                    {"role": "user", "content": transcript}],
                                          model=LLM_MODEL, temperature=0, max_tokens=60,
                                          response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": schema, "strict": True}})
            out = json.loads(r.choices[0].message.content)["call_outcome"]
            return "IN_PROGRESS" if out == "NO_OUTCOME" else out
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return "EXTRACT_FAILED"


def platform_system(p):
    text = build_instruction(p["voice"]["gender"]["value"])
    for k, v in seller_variables(p).items():
        text = text.replace("{{%s}}" % k, v)
    return text


def run(sid, lines, sellers):
    p = generate_persona(sellers.loc[sellers.fk_glusr_usr_id == sid].iloc[0].to_dict()).to_dict()
    if TARGET == "platform":
        system, opening = platform_system(p), call_overrides(p)["initial_bot_message"]
    else:
        system = build_system_prompt(p, initial_state(p))  # exactly what export_agent_prompts.py writes
        opening = p["conversation_plan"]["opening"]["value"]
    history, turns = [{"speaker": "vani", "text": opening}], [{"seller": None, "reply": opening, "outcome": None, "end": False}]
    for line in lines:
        out = llm_turn(system, history, line)
        history += [{"speaker": "seller", "text": line}, {"speaker": "vani", "text": out["reply"]}]
        turns.append({"seller": line, **out})
        if out["end"]:
            break
    if TARGET == "platform":  # one outcome per call, extracted after it; it stands for the last turn played
        turns[-1]["outcome"] = extract_outcome(history)
    while len(turns) < len(lines) + 1:  # the agent hung up early: later checks see an empty turn
        turns.append({"seller": None, "reply": "", "outcome": "HUNG_UP", "end": True})
    return turns


def main(runs):
    sellers = load_seller_master()
    results, md = [], []
    for name, sid, lines, checks in SCENARIOS:
        tally, examples = {}, []
        for _ in range(runs):
            turns = run(sid, lines, sellers)
            for check, ok in checks(turns):
                tally.setdefault(check, 0)
                tally[check] += bool(ok)
            examples.append(turns)
        results.append({"scenario": name, "seller": sid, "runs": runs, "passes": tally, "examples": examples})
        line = "; ".join(f"{c} {n}/{runs}" for c, n in tally.items())
        print(f"{'PASS' if all(n == runs for n in tally.values()) else 'WEAK'}  {name}: {line}", flush=True)
        md += [f"## {name} (seller {sid})", ""] + [f"- {c}: **{n}/{runs}**" for c, n in tally.items()] + [""]
        for x in examples[0][1:]:
            md += [f"  - **Seller:** {x['seller']}", f"  - **VANI** _({x['outcome']}, end {x['end']})_: {x['reply']}"]
        md.append("")
    total = sum(n for r in results for n in r["passes"].values())
    possible = sum(runs for r in results for _ in r["passes"])
    what = ("the Sarvam agent instruction (src/sarvam_platform.py), outcome extracted after the call"
            if TARGET == "platform" else "the engine's exported JSON prompt")
    head = [f"# Edge cases on the prompt alone, {TARGET}: {total}/{possible} checks", "",
            f"{len(SCENARIOS)} scenarios x {runs} runs, {what}, no engine code checks. First run shown.", ""]
    out = OUTPUTS / "scenarios"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"prompt_only_{TARGET}.md").write_text("\n".join(head + md), encoding="utf-8")
    (out / f"prompt_only_{TARGET}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{total}/{possible} checks")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--target", choices=["platform", "engine"], default="platform")
    a = ap.parse_args()
    TARGET = a.target
    main(a.runs)

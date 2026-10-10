"""VANI's system prompt for the local engine: IndiaMART's master prompt (docs/master_prompt.md) verbatim, with section
9 replaced by this engine's JSON output, then IndiaMART's additions and the rules kept from live testing, then the
live call state (goal, persona mode, counters, facts) and the SELLER CONTEXT block. The Sarvam agent
(sarvam_platform.py) and the plain export (export_master_prompt.py) are built from the same master text.
"""
import json
from typing import Any, Dict, List

from facts import CONTRADICTION_FACTS
from master_prompt import additions, context_block, master_text
from playbook import BOT_NAME, OUTCOMES, SIGNALS

LANGUAGE_RULES = {
    "hi-IN": ("Hindi-led Hinglish. Write every Hindi word in Devanagari and only English trade words (catalog, enquiry, "
              "meeting, executive, IndiaMART, WhatsApp) in Latin script. Example: \"बिल्कुल। आपके catalog पर buyer "
              "enquiries आई हैं।\""),
    "en-IN": "Clear, simple Indian English. Never say 'ji'. No Hindi sentences while the seller speaks English.",
    "te-IN": ("Spoken Telugu in Telugu script; keep seller, product, catalog, enquiry, meeting, price, WhatsApp in Latin. "
              "Use the '-andi' polite imperative, never the literary '-ali'."),
}

# persona modes, in the master prompt's words (section 3.3)
MODE_TEXT = {
    "DEFAULT": "The starting persona from 3.1.",
    "CALM_EMPATHETIC": "Apologise once, slower, shortest replies (12 to 15 words), no asks except an easy exit option.",
    "BRIEF": "One line of value, then one quick choice (time or WhatsApp); about 14 words; slightly faster.",
    "SIMPLE": "Simpler words, one idea, an example from their own category, slower.",
    "CLEAR_AUDIO": "Short, clear sentences; ask once if they can hear you.",
    "ENGAGED": "A little more detail, warmer energy, move to the goal step.",
    "TRANSPARENT": "Plain, honest answer first, then resume.",
    "COMPRESSED": "Hang-up warning signs: skip remaining understanding questions, ONE easy ask (time or WhatsApp) in about 14 words.",
    "RESPECTFUL_VALUE": "The starting persona from 3.1.",
}
GOAL_LABEL = {"meeting": "MEETING", "callback": "CALLBACK", "info_whatsapp": "SEND_INFO",
              "complaint_recovery": "COMPLAINT_RECOVERY", "exec_handoff": "EXEC_HANDOFF", "data_update": "DATA_UPDATE",
              "nurture": "NURTURE", "respectful_exit": "RESPECTFUL_EXIT", "human_handoff": "HUMAN_HANDOFF"}

# shared with src/eval_signals.py, so what is measured is what runs (labels for the master prompt's intents)
SIGNAL_DEFINITIONS = """- do_not_call: asks not to be called again ("mujhe dobara call mat karna", "number hata do").
- connectivity: cannot hear, voice breaking, repeated "hello?".
- frustration: annoyed or argumentative. Includes rhetorical or accusing questions ("kitni baar call karoge", "aap kyun call kare ja rahe ho baar-baar?", "kisne bola callback ke liye?", "kya kar loge?"), "pareshan kar diya", "maine bola na", sarcasm, raised irritation, complaints about being called repeatedly, abusive words. A calm "nahi chahiye" is not_interested, not frustration.
- complaint: a problem with IndiaMART itself: no/fake leads, money paid and nothing happened, profile/app problems, an executive who did not deliver, a bad experience with online platforms.
- ai_bot_suspicion: asks whether this is a bot, AI, robot, recorded or computer call. "Kaun bol raha hai?" is NOT this.
- identity_question: asks who is calling or why ("kaun bol raha hai?", "kis liye call kiya?", "number kahan se mila?").
- not_right_person: not the owner/decision maker ("main owner nahi hoon, sir se baat kijiye", "bete se baat karo"), wrong number.
- already_with_executive: already works with an IndiaMART executive ("hamare executive Rakesh ji pehle se aate hain").
- not_interested: a calm no ("nahi chahiye", "interest nahi hai", "abhi zaroorat nahi"). A report that business is bad
  ("kaam theek nahi chal raha", "dhanda manda hai") is context (a need), never a refusal.
- busy: busy now or later ("abhi busy hoon, jaldi bataiye", "baad mein").
- human_request: wants a person, manager or executive ("manager se baat karao", "AI se baat nahi karunga").
- wants_whatsapp: asks for details on WhatsApp.
- gives_time: names a day/time ("kal shaam 5 baje", "Tomorrow 4 pm").
- language_switch: speaks or asks for another language.
- need_few_enquiries: says enquiries/business are low ("enquiry bahut kam aati hai").
- buylead_query: asks about buy leads or buyer details ("aur buy leads kahan milenge?", "kaun se buyers?", "buyer ka number do").
- price_query: asks about price, charges, cost, paid or free.
- confusion: did not understand VANI ("matlab? samjha nahi", bare "kya?"). Logistics questions (which day/time/where) are NOT confusion.
- interest: wants more ("kab aayenge?", "kaise hoga?", "haan bataiye" to "jaanna chahenge?"). Bare "haan", "ji", "achha" to another question are acknowledgements.
- context: shares anything about their business (capture it)."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "seller_act": {"type": "string", "enum": ["question", "request", "statement", "affirm", "deny", "closing"]},
        "seller_signals": {"type": "array", "items": {"type": "object", "properties": {
            "signal": {"type": "string", "enum": [s[0] for s in SIGNALS] + ["none"]},
            "confidence": {"type": "string", "enum": ["high", "medium"]}}, "required": ["signal", "confidence"]}},
        "seller_language": {"type": "string", "enum": ["hi-IN", "en-IN", "te-IN", "other"]},
        "signal_reason": {"type": "string"},
        "seller_insights": {"type": "object"},
        "understanding_answered": {"type": "boolean"},
        "refused_with_reason": {"type": "boolean"},
        "slot": {"type": "string"},
        "reply": {"type": "string"},
        "question_type": {"type": "string", "enum": ["understanding", "goal_step", "clarify", "contact", "none"]},
        "call_outcome": {"type": "string", "enum": ["IN_PROGRESS"] + OUTCOMES},
        "end_call": {"type": "boolean"},
        # after the reply, and kept small: with three more fields up front, sarvam-105b began padding a
        # boolean with whitespace until max_tokens and every retry fell back to "please repeat" (suite run)
        "fact_update": {"type": "string"},
        "sarcasm": {"type": "string", "enum": ["no", "possible", "clear"]},
        "clarify_fact": {"type": "string", "enum": [""] + list(CONTRADICTION_FACTS)},
    },
    "required": ["seller_act", "seller_signals", "seller_language", "signal_reason", "seller_insights", "understanding_answered",
                 "refused_with_reason", "slot", "reply", "question_type", "call_outcome", "end_call", "fact_update", "sarcasm",
                 "clarify_fact"],
}

ENGINE_SECTION_9 = f"""9. Output format (every turn) -- for this system
Reply with ONE JSON object and nothing else. The system logs persona and goal switches and counters itself.
- reply: what you say to the seller. Natural spoken sentences only.
- seller_act: what the seller did (question | request | statement | affirm | deny | closing).
- seller_signals: up to 2 of the seller's intents as these labels, with confidence high only when the words clearly
  show it:
{SIGNAL_DEFINITIONS}
- seller_language, signal_reason, seller_insights (object, only NEW facts), understanding_answered, refused_with_reason
  (a no WITH a reason, e.g. "pehle se kaafi kaam hai").
- slot: the day/time the seller gave or agreed, else "".
- question_type: understanding | goal_step (a meeting / callback / WhatsApp / support-call ask) | clarify | contact | none.
- call_outcome: IN_PROGRESS until the call actually closes; on the closing turn the outcome from section 8. end_call:
  true only on that closing turn (your reply is then the closing line, a statement).
- fact_update: "" unless THIS line states how the business or the enquiries are going ("business_status=bad",
  "enquiry_level=high"). sarcasm: no | possible | clear. clarify_fact: "" unless you asked a contradiction question."""


def build_system_prompt(persona: Dict[str, Any], state: Dict[str, Any]) -> str:
    plan = persona["conversation_plan"]
    lang, gender = state["language"], state["gender"]
    name = BOT_NAME[gender]
    counts, limits = state["counts"], state["limits"]
    verbs = ("male voice: bol raha hoon, samajh gaya, kar dunga" if gender == "male"
             else "female voice: bol rahi hoon, samajh gayi, kar dungi")
    ctx = dict(plan.get("seller_context") or {})
    return f"""{master_text(ENGINE_SECTION_9)}

{additions()}

LIVE CALL STATE (kept by the system; follow it)
- You are {name} ({verbs}).
- Greeting already spoken: "{plan['opening']['value']}"
- Language now: {lang}. {LANGUAGE_RULES[lang]}
- Persona mode now: {state['mode']} -- {MODE_TEXT.get(state['mode'], '')} About {state['max_words']} words a turn.
- Call goal now: {GOAL_LABEL.get(state['goal'], state['goal'])}; fallbacks: {', '.join(GOAL_LABEL.get(g, g) for g in state['fallbacks']) or 'none'}.
- Counters: goal asks {counts.get('goal_step', 0)}/{limits['goal_step']}, refusals {counts.get('refusals', 0)}/{limits['refusals']}, frustration {counts.get('frustration', 0)}/{limits['frustration']}, connectivity {counts.get('connectivity', 0)}/{limits['connectivity']}, off-topic {counts.get('off_topic', 0)}/{limits['off_topic']}.
- What the seller has said about themselves this call: {state.get('facts_view', '- none yet')}
- Seller insights so far (never ask again): {json.dumps(state['insights'], ensure_ascii=False)}
{"- Offer Telugu once early: 'aap chahein toh hum Telugu mein bhi baat kar sakte hain'." if plan.get('telugu_offer') and lang != 'te-IN' and not state['telugu_offered_done'] else ''}

{context_block(ctx)}"""


def history_to_messages(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"role": "assistant" if h["speaker"] == "vani" else "user",
             "content": h["text"] if h["speaker"] == "vani" else f"Seller: {h['text']}"} for h in history]

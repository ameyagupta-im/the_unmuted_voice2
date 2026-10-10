"""Live call engine: the Seller Call Scenarios playbook as a state machine.

State per call: persona (mode, pace, length, empathy, assertiveness, language;
the voice itself never changes) and goal (current goal, stage understand ->
goal step, fallbacks), counters against the ask limits, captured seller
insights, outcome.

Per seller turn:
  1. Saaras STT (translit) -> Roman text + language; audio length feeds the hang-up model
  2. tier 1: regex signals (clear) + language detector + hang-up risk model
  3. signals handled in playbook priority order: each may switch the persona
     mode (one per turn, held >= 2 turns) and/or the goal (with the playbook's
     exceptions), bump counters, or end the call (do-not-call, 2nd frustration,
     2nd audio failure, refusal limit)
  4. one sarvam-105b call: tier-2 classification in context (with confidence)
     + the reply, under the live state
  5. tier-2 signals: high confidence acts now; medium acts only if repeated
     next turn, except compliance/safety signals (playbook.ACT_ON_MEDIUM)
  6. guards on the reply (human claim, internal labels, price/result quotes,
     pitch after complaint/frustration, understand-first, ask limits, gender,
     language/script, repeated question, premature close) -> LLM retry, then
     deterministic repair
  7. outcome validated against what the seller actually said; closing line
     from the playbook's endings table; goal achieved yes/partly/no
  8. Bulbul TTS with the fixed voice, current language and pace
Every persona or goal switch is written to the switch log with the seller's
words, the detector, the exact change and the reason.
"""
import copy
import io
import json
import re
import time
import wave
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import hangup_model
from config import client, LLM_MODEL
from facts import CONTRADICTION_FACTS, VALUES, FactLedger, clarify_line, rule_facts, sarcasm_cues

LLM_FACTS = ("business_status", "enquiry_level")
from playbook import (SIGNAL_PRIORITY, SIGNAL_MODE, ACT_ON_MEDIUM, PERSONA_MODES, MODE_HOLD_TURNS, GOAL_SWITCHES,
                      FALLBACKS, ENDINGS, ENDINGS_TE, BOT_NAME, PROTECTED_GOALS, goal_achieved, BUYLEAD_LINE,
                      BUYLEAD_LIGHT_CHECK, BUYLEAD_SEND_INFO, COMPLAINT_DECLINED)
import slots
from prompt_builder import OUTPUT_SCHEMA, build_system_prompt, history_to_messages
from signal_detector import (CALL_FREQUENCY, EXPLICIT_LANG_REQUEST, SHORT_TURN, detect_signals, detect_language_switch, english_share,
                             guess_language)
from text_normalize import drop_ji, is_devanagari, to_roman
from utterance import dialogue_act, nothing_more
from voice_synth import synthesize, transcribe, prefetch

PACE_MIN, PACE_MAX = 0.78, 1.1
TRANSIENT_MODES = {"TRANSPARENT"}
REVERTING_MODES = {"SIMPLE", "COMPRESSED", "CLEAR_AUDIO", "BRIEF"}  # back to DEFAULT after 2 quiet turns
TERMINAL_SIGNALS = {"do_not_call", "wants_whatsapp"}
# endings the seller's own words force (they may close even while a contradiction is being clarified)
HARD_ENDINGS = {"DO_NOT_CALL", "ESCALATED_EXIT", "CALL_BACK_LATER", "RESPECTFUL_EXIT"}
SLOT_OUTCOME_BY_GOAL = {"complaint_recovery": "COMPLAINT_LOGGED", "human_handoff": "HUMAN_HANDOFF",
                        "exec_handoff": "EXEC_HANDOFF"}

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TELUGU = re.compile(r"[ఀ-౿]")
_HUMAN_CLAIM = re.compile(r"\b(i\s*am|i'm)\s*(a\s*)?(real\s*)?(human|person)\b|(मैं|main)\s*(एक\s*|ek\s*)?(इंसान|insaan)|real\s*insaan", re.I)
_INTERNAL = re.compile(r"\b(complaint_recovery|exec_handoff|data_update|respectful_exit|info_whatsapp|human_handoff|"
                       r"CALM_EMPATHETIC|CLEAR_AUDIO|TRANSPARENT|COMPRESSED|ENGAGED|seller_type|seller_insights|persona|"
                       r"goal_step|IN_PROGRESS|MEETING_FIXED|CALLBACK_SCHEDULED)\b|[{}@]")
# learned from the recordings: 6 of 18 real price questions were answered with a price
_PRICE = re.compile(r"(हज़ार|हजार|hazaar|hazar|लाख|\blakh\b|रुपये|rupe|rupaye|₹|\brs\.?\s*\d|\bgst\b|percent|प्रतिशत|%|"
                    r"\d+\s*(leads|inquiries|enquiries|लीड)\s*(milenge|मिलेंगी|मिलेंगे|aayenge|आएंगी|will|guarantee))", re.I)
_PITCH = re.compile(r"\bmeeting\b|मीटिंग|\bvisit\b|मुलाकात|package|पैकेज|\bdemo\b|మీటింగ్", re.I)
_CHANNEL = re.compile(r"\bsms\b|\be-?mail\b|ईमेल", re.I)
# A time VANI proposed (her own Devanagari / English / Telugu). The first version also used a loose
# token list for the SELLER side and matched the "am" in "ma'am", turning "hum soch ke batate hain
# ma'am" into MEETING_FIXED; the seller side now uses the gives_time detector (precise patterns).
_TIME_TOKEN = re.compile(r"\d\s*(बजे|baje|bje|am|pm|o'?clock)\b|\b(कल|परसों|kal|parso|tomorrow|monday|tuesday|wednesday|"
                         r"thursday|friday|saturday|sunday|రేపు)\b|कल|परसों|सुबह|शाम|दोपहर", re.I)
_WANTS_WA_EVIDENCE = re.compile(r"whats\s*app|bhej|send|pampinch|message|msg|व्हाट्सएप|భేజ|పంప", re.I)
# master prompt intent 16: never quote, never call the meeting free
PRICE_LINE = {"hi-IN": "Charges आपके plan और leads के हिसाब से होते हैं, executive मिलकर आपकी category के हिसाब से सही बता देंगे।",
              "en-IN": "Charges depend on your plan and leads; the executive will explain them for your category.",
              "te-IN": "Charges మీ plan మరియు leads ని బట్టి ఉంటాయి, executive మీ category ప్రకారం సరిగ్గా చెబుతారు."}
_FREE_MEETING = re.compile(r"(meeting|मीटिंग|visit|विज़िट|executive)[^.?!।]{0,30}(free|फ्री|मुफ़्त|मुफ्त|निःशुल्क)|"
                           r"(free|फ्री|मुफ़्त|मुफ्त|निःशुल्क)\s*(में\s*|mein\s*|of\s*cost\s*)?(\w+\s*){0,2}(meeting|मीटिंग|visit)", re.I)
# master intent 9: first refusal -> ONE gentle two-option reason question
TWO_OPTION_Q = {"hi-IN": "कोई बात नहीं। क्या आपके पास पहले से काफ़ी काम है, या online platform का कोई बुरा अनुभव रहा?",
                "en-IN": "No problem. Do you already have enough work, or have you had a bad experience with online platforms?",
                "te-IN": "పర్వాలేదండి. మీకు ఇప్పటికే చాలా పని ఉందా, లేదా online platform తో ఏదైనా చెడు అనుభవం ఉందా?"}
# final refusals that close at once with the RESPECTFUL_EXIT line (master intent 9)
_FINAL_REFUSAL = re.compile(r"z[a]?r[o]{0,2}r?[a]?t\s*(hi\s*)?(nahi|nhi|nahin)|jarurat\s*(nahi|nhi)|galti\s*se\s*dekh|phone\s*rakh|"
                            r"expansion\s*ka\s*koi\s*plan\s*nahi|apne\s*indiamart\s*contacts|khud\s*baat\s*kar\s*lung|"
                            r"mana\s*kar\s*diya|nahi\s*ho\s*payega|pehle\s*se\s*(kaafi|bahut)\s*kaam|no\s*need|not\s*required|"
                            r"ज़रूरत\s*नहीं|जरूरत\s*नहीं", re.I)
# master 16b: "WhatsApp pe bhej do" while a meeting is being asked -> push once
WA_PUSH = {"hi-IN": "ज़रूर, पर live buyer enquiries और keyword report screen पर देखना ज़्यादा काम का होता है, बस 15 मिनट, online भी हो सकता है।",
           "en-IN": "Sure, but seeing the live buyer enquiries and the keyword report on screen is far more useful, just 15 minutes, and it can be online."}
ASK_HOUR = {"hi-IN": "ठीक है, {when}कितने बजे?", "en-IN": "Alright, {when}at what time?"}
_RELATION = [(re.compile(r"\bbet[ae]\b|बेटे|बेटा|\bson\b", re.I), "आपके बेटे", "your son"),
             (re.compile(r"\bpapa\b|पापा|father|pitaji", re.I), "आपके पापा", "your father"),
             (re.compile(r"\bpartner\b", re.I), "आपके partner", "your partner"),
             (re.compile(r"\bbhai\b|भाई|brother", re.I), "आपके भाई", "your brother")]
# the seller is still talking / wants to be heard: never cut the call there (IndiaMART, 10 Oct 2026)
_SPEAKING = re.compile(r"\babhi\s*(main\s*|mai\s*)?(bol|baat\s*kar)\s*(raha|rahi|rha|rhi)|\bmeri\s*baat\s*(toh\s*|to\s*)?(suno|suniye)|"
                       r"\bpehle\s*(meri\s*)?(baat\s*)?(suno|suniye)|\blet\s*me\s*(speak|finish|talk)|\blisten\s*to\s*me|"
                       r"मैं\s*बोल\s*रहा|मेरी\s*बात\s*(तो\s*)?सुन", re.I)
YIELD = {"hi-IN": "माफ़ी चाहती हूँ। आप बताइए।", "en-IN": "Sorry. Please go ahead.",
         "te-IN": "క్షమించండి జీ. మీరు చెప్పండి."}
YIELD_M = {"hi-IN": "माफ़ी चाहता हूँ। आप बताइए।"}
AM_ACK = {"hi-IN": "बहुत अच्छा।", "en-IN": "Very good."}
AM_YES = {"hi-IN": "ज़रूर, आपके account manager इसमें मदद करेंगे।", "en-IN": "Sure, your account manager will help with this."}
_AM_OFFER = re.compile(r"account\s*manager|अकाउंट\s*मैनेजर", re.I)
_NEED = re.compile(r"karna\s*hai|karwana|karana|chahiye|update|badalna|doubt|sawal|sawaal|problem|dikkat|samasya|help|madad|"
                   r"catalog|catalogue|listing|photo|leads?\b|enquir|करना\s*है|चाहिए|दिक्कत|मदद", re.I)
_DECIDED = re.compile(r"रख\s*(देती|लेती|देता|लेता|दी|ली|दिया|लिया)|rakh\s*(deti|leti|deta|leta|di|li|diya|liya)|"
                      r"fix\s*(कर\s*)?(दी|दिया|देती|देता|di|diya|deti|deta|ho\s*gayi)|book\s*(kar|कर)|I'?ll\s*(fix|book|schedule)|"
                      r"I\s*will\s*(fix|book|schedule)|I'?ve\s*(fixed|booked|scheduled)", re.I)
_MEETING_WORDS = re.compile(r"meeting|मीटिंग|milkar|मिलकर|online|ऑनलाइन|executive|account\s*manager|video", re.I)
# reply problems fixed by code without changing the content (script, verb gender, a banned phrase, an unasked
# virtual-assistant mention, Hindi in an English call); everything else still goes back to the LLM
MECHANICAL = {"script", "gender", "banned_phrase", "unasked_va", "translate", "disclosure", "clarify_tail"}
# sarvam-105b sometimes pads the JSON with blank lines after the reply until max_tokens (800 tokens, ~1.6 s, then
# invalid JSON and a retry; 11 of 65 bench turns). Pretty JSON never has whitespace-only lines and strings escape
# their newlines, so this stop sequence only ever fires inside the padding.
PADDING_STOP = ["\n  \n  \n"]
TRAILING_DEFAULTS = {"fact_update": "", "sarcasm": "no", "clarify_fact": ""}   # the small fields after the reply


def parse_turn_json(text: str) -> Dict[str, Any]:
    """The LLM's JSON; when the padding stop cut it before the closing brace, close it and give the trailing
    optional fields their empty defaults -- everything the model wrote, reply included, is kept as is."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    body = (text or "").rstrip().rstrip(",")
    for tail in ("}", "\"}", "]}"):
        try:
            data = json.loads(body + tail)
            break
        except json.JSONDecodeError:
            continue
    else:
        raise json.JSONDecodeError("unrecoverable", text or "", 0)
    if not isinstance(data, dict) or not data.get("reply") or "call_outcome" not in data or "end_call" not in data:
        raise json.JSONDecodeError("cut before the reply / outcome", text or "", 0)
    for k, v in TRAILING_DEFAULTS.items():
        data.setdefault(k, v)
    return data


REAL_ASK = {"price_query", "buylead_query", "interest", "identity_question", "ai_bot_suspicion", "wants_whatsapp",
            "gives_time", "confusion", "human_request"}
_HOW_BUSINESS = re.compile(r"कैसा\s*चल\s*रहा|kaisa\s*chal\s*raha|how\s*is\s*(your\s*)?(the\s*)?(business|work)\s*going|"
                           r"ఎలా\s*నడుస్త", re.I)
_PRICE_ANSWER = re.compile(r"free|charge|executive|फ्री|मुफ़्त|मुफ्त|चार्ज|एग्जीक्यूटिव|ఉచిత|ఛార్జ", re.I)
_NEG_WORD = re.compile(r"\b(nahi|nhi|nahin|no|don'?t|do\s*not|mat|vaddu|ledu|cheyoddu)\b|नहीं|వద్దు|లేదు", re.I)
_HINDI_WORDS = {"hai", "hain", "hoon", "kya", "nahi", "aap", "aapka", "aapko", "mein", "toh", "kar", "karoon", "karun",
                "kis", "ya", "par", "bhej", "doon", "dijiye", "kijiye", "bataiye", "chahiye", "raha", "rahi", "ji",
                "iske", "uske", "baare", "jaanna", "janna", "chahenge", "chahte", "aapki", "aapke", "hum", "hamare",
                "sakte", "sakti", "sakta", "wale", "liye", "ke", "ki", "ko", "bhi", "bahut", "achha", "theek", "rahega",
                "milkar", "kal", "baje", "subah", "shaam", "dopahar", "parso", "hoti", "hota", "hote", "aur", "lekin"}
# trade words that stay in Latin inside a Hindi reply (prompt LANGUAGE_RULES); never transliterated
_TRADE = re.compile(r"^(indiamart|whatsapp|catalog|catalogue|enquiry|enquiries|meeting|executive|charges?|plan|leads?|buyers?|"
                    r"category|profile|online|settings?|account|manager|doubt|buyleads?|seller|dashboard|app|website|"
                    r"support|team|details|products?|orders?|gst|ok|okay|section|login|number|call|video|fix)$", re.I)
_TIME_ASK = re.compile(r"किस\s*(समय|time|वक्त)|कब|what\s*time|when\b|ఏ\s*సమయం|ఎప్పుడు|time\s*(पर|ठीक|suit)", re.I)
_DEV_TIME = re.compile(r"(कल|परसों|आज|सोमवार|मंगलवार|बुधवार|गुरुवार|शुक्रवार|शनिवार|रविवार).{0,15}(सुबह|शाम|दोपहर|बजे|\d)|\d\s*बजे")
_AFFIRM = re.compile(r"\b(haan|haa|ha|ji|ok|okay|theek|thik|bhej|sure|yes|kar\s*do|chalega|bilkul|sari|sare)\b|హా|సరే|हाँ|ठीक", re.I)
_WHATSAPP = re.compile(r"whats\s*app|व्हाट्सएप|వాట్సాప్", re.I)
# VANI's question was about the business, so a bare "achha nahi chal raha" answers it
_BUSINESS_Q = re.compile(r"चल रहा|चल रही|going|business|काम|kaam|dhanda|धंधा|వ్యాపారం|ఎలా ఉంది", re.I)
# taking a sarcastic "sab badhiya hai" literally (Chennai live session: "यह जानकर अच्छा लगा")
_GLAD = re.compile(r"अच्छा लगा|खुशी हुई|ख़ुशी हुई|good to hear|glad to hear|great to hear|nice to hear|happy to hear|"
                   r"సంతోషం", re.I)
_CONVERTS_NOT = re.compile(r"\border\w*\s*(\w+\s*)?(nahi|nhi|kam|nahin)|\bconvert|\bnahi\s*ban|\bdeal\s*(nahi|kam)|"
                           r"\bnot\s*(turning|converting)|\bno\s*orders?\b", re.I)
GENERIC_UNDERSTANDING_EN = "How is your business going right now?"


_REFUSAL_WORDS = re.compile(r"chahiye|chaiye|interest|zaroorat|jarurat|need|want|mat\b|nahi\s*karna|vaddu|avasaram", re.I)


def q_offer_call(reply: str) -> bool:
    """VANI's question offers another call (a time, or "call kar loon?")."""
    q = _last_question(reply)
    return bool(q and (_TIME_TOKEN.search(q) or _CALL_OFFER.search(q)))


def _agrees(line: str) -> bool:
    """A yes to VANI's proposal opens the reply ("haan ji, theek hai"). Anywhere in the line was too loose:
    "kaam theek chal raha hai par enquiry kam aati hai" was taken as accepting a 7 pm meeting. "bilkul" opens a
    yes only when a yes follows or nothing does: "Bilkul kharab chal raha hai" (= absolutely bad) was read as a
    yes to WhatsApp in the scenario suite."""
    words = [w.strip(".,!?।") for w in line.split()]
    while words and re.fullmatch(r"(achha|accha|acha|arre|arey|oh|ohh|hmm|अच्छा)", words[0], re.I):
        words = words[1:]
    if words and words[0].lower() == "bilkul" and len(words) > 1 and not _AFFIRM.fullmatch(words[1]):
        return False
    if words and rule_facts(" ".join(words), True).get("business_status") == "bad":
        return False
    return bool(words) and bool(_AFFIRM.fullmatch(words[0]))


GENDER_FIX = {
    "male": [("रही हूँ", "रहा हूँ"), ("रही हूं", "रहा हूं"), ("सकती हूँ", "सकता हूँ"), ("सकती हूं", "सकता हूं"),
             ("चाहती हूँ", "चाहता हूँ"), ("करूँगी", "करूँगा"), ("करूंगी", "करूंगा"), ("दूँगी", "दूँगा"), ("दूंगी", "दूंगा"),
             ("की virtual assistant", "का virtual assistant"), ("समझ गई", "समझ गया"), ("गई हूँ", "गया हूँ"),
             ("rahi hoon", "raha hoon"), ("sakti hoon", "sakta hoon")],
    "female": [("रहा हूँ", "रही हूँ"), ("रहा हूं", "रही हूं"), ("सकता हूँ", "सकती हूँ"), ("सकता हूं", "सकती हूं"),
               ("चाहता हूँ", "चाहती हूँ"), ("करूँगा", "करूँगी"), ("करूंगा", "करूंगी"), ("दूँगा", "दूँगी"), ("दूंगा", "दूंगी"),
               ("का virtual assistant", "की virtual assistant"), ("समझ गया", "समझ गई"), ("गया हूँ", "गई हूँ"),
               ("raha hoon", "rahi hoon"), ("sakta hoon", "sakti hoon")],
}
# the seller's OWN words asking whether this is a machine. The LLM labelled "Enna maadhiri?" and "kaun bol raha
# hai?" as ai_bot_suspicion and VANI then said "main IndiaMART ki virtual assistant hoon" unasked (live session
# 19070168_20261010_151033). "kaun / who" is an identity question, never a bot question.
_AI_EVIDENCE = re.compile(r"\b(bot|robot|ai|a\.i\.|machine|computer|automated|recorded|recording|recorder|"
                          r"real\s*(person|insaan|human)|insaan\s*(ho|hai|hain)|human\s*(ho|hai|hain)?|asli\s*(insaan|aadmi|ladki)|"
                          r"artificial|chatbot|virtual|software|program)\b|रोबोट|मशीन|इंसान|असली|రోబో", re.I)
_IDENTITY_EVIDENCE = re.compile(r"\b(bot|ai|robot|machine|assistant|virtual|recorded|computer|automated|kaun|who|why|"
                                r"kis\s*liye|kyun|insaan|human|person|evaru)\b|कौन|ఎవరు", re.I)
_NO_ONLY = {"nahi", "nhi", "nahin", "na", "chahiye", "chaiye", "ji", "haan", "no", "interest", "interested", "not", "hai",
            "mujhe", "humein", "madam", "sir", "maam", "ma'am", "thank", "thanks", "you", "please", "koi", "kuch", "bilkul"}
# one goal-step question per goal, used to repair a reply that forgot to end on a question
GOAL_QUESTION = {  # the goal step in the master prompt's words
    "hi-IN": {"meeting": "कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?",
              "callback": "किस time call करूँ, या WhatsApp पर details भेज दूँ?",
              "info_whatsapp": "क्या मैं details आपको इसी number पर WhatsApp पर भेज दूँ?",
              "complaint_recovery": "Support आपको किस time call कर ले?",
              "exec_handoff": "अगर आपका कोई और doubt हो, तो मैं आपके account manager से आपकी meeting fix कर सकती हूँ। क्या ऐसा कुछ है?",
              "data_update": "उनका number बता देंगे?",
              "respectful_exit": "क्या आप इसके बारे में जानना चाहेंगे?",
              "nurture": "क्या आप इसके बारे में जानना चाहेंगे?",
              "human_handoff": "किस time ठीक रहेगा?"},
    "en-IN": {"meeting": "Would tomorrow 11 AM or day after tomorrow 4 PM work for you?",
              "callback": "What time should I call, or shall I send the details on WhatsApp?",
              "info_whatsapp": "Shall I send the details to this number on WhatsApp?",
              "complaint_recovery": "What time may our support team call you?",
              "exec_handoff": "If you have any other doubt, I can fix a meeting with your account manager. Is there anything like that?",
              "data_update": "Could you share their number?",
              "respectful_exit": "Would you like to know more about it?",
              "nurture": "Would you like to know more about it?",
              "human_handoff": "What time would suit you?"},
}
LANG_NAME = {"hi-IN":"Hindi-led Hinglish in Devanagari (English trade words in Latin)", "en-IN": "English only",
             "te-IN": "Telugu script (English loanwords in Latin)"}
SAFE_LINE = {"hi-IN": "समझ गई।", "en-IN": "Understood.", "te-IN": "సరేనండి."}
EVIDENCE_FOR = {
    "frustration": ["playbook", "E4_backoff_after_frustration"], "complaint": ["playbook", "E10_objection_recoverability"],
    "busy": ["playbook", "E2_interrupted_opening", "E10_objection_recoverability"], "confusion": ["playbook", "E3_pace"],
    "interest": ["playbook", "E11_forced_meetings"], "language_switch": ["playbook", "E8_state_language_prior"],
    "ai_bot_suspicion": ["playbook", "E9_ai_identity", "policy:never_claim_human"],
    "identity_question": ["playbook", "E15_seller_questions"], "price_query": ["playbook", "recordings:price_leaks"],
    "hangup_risk": ["playbook", "model:hangup_auc_0.645"], "connectivity": ["playbook", "E10_objection_recoverability"],
    "sarcasm": ["playbook", "E4_backoff_after_frustration", "live:3419775_20261009_231212"],
    "contradiction": ["live:3419775_20261009_231212"], "clarify_resolved": ["live:3419775_20261009_231212"],
}


def _priority(signal):
    """Sarcasm switches the persona like frustration does (it IS frustration, said the other way round)."""
    return SIGNAL_PRIORITY.get("frustration" if signal == "sarcasm" else signal, 99)


_CALL_OFFER = re.compile(r"call\s*(कर|करूँ|करू|करें|करे|kar|back)|फिर\s*से\s*call|call\s*you|call\s*again|"
                         r"बात\s*करें|బాత్|call\s*చేయ", re.I)
# phrases IndiaMART's master prompt bans: listening shown through tone, not words; no talking down
_BANNED = re.compile(r"ध्यान से सुन|dhyan se sun|आसान शब्दों में|aasaan shabdon|asan shabdon|एक line में|ek line (mein|me)\b|"
                     r"in simple words|in one line|मैं call यहीं", re.I)
_VA_MENTION = re.compile(r"virtual assistant|वर्चुअल असिस्टेंट|voice assistant|AI assistant", re.I)
# signals that outrank a buy-lead question (the buy-lead reply is used only when none of these is present)
BUYLEAD_OUTRANKED = {s for s, p in SIGNAL_PRIORITY.items() if p < SIGNAL_PRIORITY["buylead_query"]} - {"language_switch"}
_VALUE_WORDS = re.compile(r"enquir|inquir|buyer|एन्क्वायरी|ख़रीदार|खरीदार|order|ఎంక్వైరీ|కొనుగోలు", re.I)
# IndiaMART, 10 Oct 2026: on silence (or speech too unclear to transcribe), ask again
SILENCE_LINE = {"hi-IN": "माफ़ कीजिए, आपकी आवाज़ ठीक से नहीं आ रही। क्या आप कुछ कह रहे थे?",
                "en-IN": "Sorry, I can't hear you properly. Were you saying something?",
                "te-IN": "క్షమించండి, మీ మాట సరిగ్గా వినిపించడం లేదు. మీరు ఏమైనా చెప్తున్నారా?"}
# said over VANI while she speaks: a listener's "haan / hmm / ok", not an interruption (she carries on)
_BACKCHANNEL = re.compile(r"^(?:(?:haan|haa|han|ha|hmm+|hm+|ji|achha|acha|accha|ok|okay|theek|thik|hai|right|yes|yeah|"
                          r"uh|huh|अच्छा|हाँ|हां|जी|ठीक|है|हम्म)[\s.,!।]*){1,4}$", re.I)


@dataclass
class SwitchEntry:
    turn: int
    t_sec: float
    kind: str           # persona | goal | language | end | recovery
    signal: str
    detector: str
    seller_said: str
    trigger: str
    change_made: Dict[str, List[Any]]
    reason: str
    evidence: List[str]


@dataclass
class TurnResult:
    turn: int
    seller_text: Optional[str]
    stt_language: Optional[str]
    signals_tier1: List[str]
    signals_tier2: List[str]
    switches: List[Dict[str, Any]]
    reply: str
    call_outcome: str
    end_call: bool
    delivery: Dict[str, Any]
    hangup_risk: Optional[float] = None
    audio: Optional[bytes] = field(default=None, repr=False)
    latency_ms: Dict[str, int] = field(default_factory=dict)
    ignored: bool = False   # background noise / a backchannel over VANI: no turn taken, VANI resumes


def _wav_seconds(b: Optional[bytes]) -> Optional[float]:
    try:
        with wave.open(io.BytesIO(b), "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return None


def _has_reason(text: str) -> bool:
    """A refusal carries a reason if anything is left after removing no-words and fillers
    ("abhi zaroorat nahi, stock full hai" yes; "nahi chahiye" no)."""
    toks = [t.strip(".,?!").lower() for t in (text or "").split()]
    rest = [t for t in toks if t and t not in _NO_ONLY and t not in {"zaroorat", "jarurat", "abhi"}]
    return len(rest) >= 2 or "abhi" in toks


def _offered_slots(vani_text: str):
    """The slots VANI's last turn offered, from its last question that names any ("kal 11 baje ya parso 4 baje, kya
    theek rahega? milkar ya online?" -- the slot question is not always the last one)."""
    qs = [x for x in re.split(r"(?<=[.?!।])\s*", vani_text or "") if x.strip().endswith("?")]
    for q in reversed(qs):
        found = slots.parse_all(q)
        if found:
            return found
    return []


def _before_question(sents) -> int:
    """Where an answer goes: before the reply's question (master: answer first, then one question)."""
    return next((i for i, x in enumerate(sents) if x.strip().endswith("?")), len(sents))


def _last_question(text: str) -> str:
    qs = [s.strip() for s in re.split(r"(?<=[.?!।])\s*", text or "") if s.strip().endswith("?")]
    return qs[-1] if qs else ""


_TOK = re.compile(r"[^\s,.?!।]+")


def _similar(a, b):
    ta, tb = set(_TOK.findall(a.lower())), set(_TOK.findall(b.lower()))
    return len(ta & tb) / max(1, len(ta | tb))


class LiveCall:
    def __init__(self, persona: Dict[str, Any], synthesize_audio: bool = True, llm_model: str = LLM_MODEL):
        if persona.get("blocked"):
            raise ValueError(f"Seller {persona['seller_id']} is blocked: {persona.get('block_reason')}")
        self.persona = persona
        v, l, t, plan = persona["voice"], persona["language"], persona["tone"], persona["conversation_plan"]
        self.base = {"pace": v["pace"]["value"], "max_words": t["max_words"]["value"], "empathy": t["empathy"]["value"],
                     "assertiveness": t["assertiveness"]["value"]}
        self.s = {
            "language": l["primary"]["value"], "gender": v["gender"]["value"], "speaker": v["speaker"]["value"],
            "mode": "DEFAULT", **self.base,
            "goal": persona["goal"]["value"], "fallbacks": list(persona["fallback_goals"]),
            "stage": "goal_step",  # master prompt: no interview; the first reply carries the context + one light question
            "counts": Counter(), "limits": plan["ask_limits"], "insights": {}, "telugu_offered_done": False,
        }
        self.mode_set_turn, self.mode_signal, self.prev_mode = 0, None, "DEFAULT"
        self.quiet_turns = 0
        self.synthesize_audio, self.llm_model = synthesize_audio, llm_model
        self.history: List[Dict[str, str]] = []
        self.switch_log: List[SwitchEntry] = []
        self.guard_corrections: List[Dict[str, Any]] = []
        self.fired, self.pending_medium = Counter(), {}
        self.turn, self.ended = 0, False
        self.outcome, self.slot = "IN_PROGRESS", None
        self.goal_history = [persona["goal"]["value"]]
        self.prev_seller_lang, self.prev_seller_words, self.short_count, self.last_bot_words = None, None, 0, 0
        self.current_seller = None
        self.turn_tier1: set = set()
        self.support_time_asked = False
        self.declined_offers: set = set()
        self.dnc_requested = False
        self.wrap_up = False                      # kept for the prompt-only harness; the master closings end the call at once
        self.reason_q_turn = None                 # turn VANI asked the two-option refusal question (master intent 9)
        self.am_offered = False                   # master intent 8: the account-manager offer, made once
        self.yield_now = False                    # this turn: apologise and let the seller speak (no question)
        self.call_freq = False                    # the seller complained about repeated calls: never offer another call
        self.wa_pushed = False                    # master 16b: one push for the meeting when WhatsApp is asked mid-ask
        self.master_turns: List[Dict[str, Any]] = []  # per-turn record in the master prompt's section-9 fields
        self.seller_act = None                     # dialogue act of the current seller turn (utterance.py)
        self.barged_in = False                     # the seller talked over VANI's last reply (hands-free demo)
        # what the seller said about themselves this call (facts.py): contradictions are clarified once
        self.ledger = FactLedger()
        self.turn_facts: Dict[str, str] = {}
        self.clarified: Dict[str, int] = {}        # fact -> turn VANI asked about it
        self.pending_clarify = None                # Contradiction to clarify in THIS reply (rules)
        self.awaiting_clarify = None               # (fact, Contradiction, turn asked): resolved by the next answer
        self.sarcasm_turn = False
        # persuading a seller who is annoyed or hesitant, instead of letting the call go (live session 125638)
        self.venting_now = False
        self.current_text = ""
        self.meeting_pending = None               # a valid meeting slot waiting for "milkar ya online?" (master 4.1)
        self.meeting_ready = False                # slot valid and format known: the meeting may be fixed
        self.window_told = False                  # VANI said the 9 AM-6 PM window once this call
        self.closing_override = None              # a closing line said instead of the outcome's usual one
        self._uncut_entry = None
        self.meeting_at = None                    # the confirmed meeting's calendar date and time (ISO)
        self.meeting_format = None                # "online" / "मिलकर" for the closing line
        self.reason_q_due = False                 # a first plain refusal: the two-option question is due this turn
        self.wa_push_now = False
        self.turn_handled: set = set()            # signals already acted on this turn (no double counting)
        self.s["facts_view"] = self.ledger.view()
        self.t0 = time.time()

    # ------------------------------------------------------------------ state changes
    def delivery(self):
        d = {k: self.s[k] for k in ("language", "speaker", "gender", "mode", "pace", "max_words", "empathy",
                                    "assertiveness", "goal", "stage")}
        d["counts"] = dict(self.s["counts"])
        return d

    def _log(self, kind, signal, detector, said, trigger, change, reason):
        e = SwitchEntry(self.turn, round(time.time() - self.t0, 1), kind, signal, detector, said, trigger, change, reason,
                        EVIDENCE_FOR.get(signal, ["playbook"]))
        self.switch_log.append(e)
        return e

    def _apply_mode(self, mode, signal, detector, said, trigger) -> Optional[SwitchEntry]:
        cur = self.s["mode"]
        if mode == cur:
            return None
        # CLEAR_AUDIO is not held: a seller who answers in a full sentence can hear (live session 125638: the
        # audio check outranked the frustration that followed it)
        held = cur not in ("DEFAULT", "CLEAR_AUDIO") and (self.turn - self.mode_set_turn) < MODE_HOLD_TURNS
        cur_pri = _priority(self.mode_signal)
        if mode != "TRANSPARENT" and held and _priority(signal) >= cur_pri:
            return None
        # never pitch after frustration/complaint: CALM_EMPATHETIC only yields to audio, disclosure, a new complaint
        if cur == "CALM_EMPATHETIC" and mode not in ("TRANSPARENT", "CLEAR_AUDIO", "CALM_EMPATHETIC"):
            return None
        p = PERSONA_MODES[mode]
        before = {k: self.s[k] for k in ("mode", "pace", "max_words", "empathy", "assertiveness")}
        if mode in TRANSIENT_MODES:
            self.prev_mode = cur
        self.s["mode"] = mode
        self.s["pace"] = round(min(PACE_MAX, max(PACE_MIN, self.base["pace"] + p["pace_delta"])), 2)
        self.s["max_words"] = p["max_words"] or self.base["max_words"]
        self.s["empathy"] = p.get("empathy_set") or min(5, max(1, self.base["empathy"] + p.get("empathy_delta", 0)))
        self.s["assertiveness"] = p.get("assertiveness_set") or min(5, max(1, self.base["assertiveness"] + p.get("assertiveness_delta", 0)))
        if mode not in TRANSIENT_MODES:
            self.mode_set_turn, self.mode_signal = self.turn, signal
        change = {k: [before[k], self.s[k]] for k in before if before[k] != self.s[k]}
        return self._log("persona", signal, detector, said, trigger, change,
                         f"Playbook scenario {SIGNAL_PRIORITY.get(signal, '-')}: {signal} -> {mode}.")

    def _apply_goal(self, new_goal, signal, detector, said, trigger, force=False) -> Optional[SwitchEntry]:
        cur = self.s["goal"]
        if new_goal == cur:
            return None
        if not force and signal in GOAL_SWITCHES and cur in GOAL_SWITCHES[signal][1]:
            return None
        self.s["goal"], self.s["fallbacks"] = new_goal, list(FALLBACKS.get(new_goal, []))
        before_stage = self.s["stage"]
        self.s["stage"] = "goal_step"
        self.s["counts"]["goal_step"] = 0
        self.goal_history.append(new_goal)
        return self._log("goal", signal, detector, said, trigger,
                         {"goal": [cur, new_goal], "stage": [before_stage, "goal_step"]},
                         f"Seller revealed '{signal}': goal moves to {new_goal} (playbook mid-call goal switch).")

    def _end(self, outcome, signal, detector, said, reason, hard=True) -> SwitchEntry:
        """Master prompt section 8: the closing line is a statement, said once; the call ends with it."""
        self.outcome, self.ended = outcome, True
        if outcome in ("CALLBACK_SCHEDULED", "COMPLAINT_LOGGED", "HUMAN_HANDOFF") and not self.slot:
            # the time the seller just gave ("kal shaam 5 baje"), any hour (callbacks have no window)
            t = to_roman(said) if said and is_devanagari(said) else (said or "")
            got = slots.parse(t)
            if got:
                self.slot = slots.fmt(got, self.s["language"] if self.s["language"] in ("hi-IN", "en-IN") else "en-IN")
        return self._log("end", signal, detector, said, "", {"outcome": ["IN_PROGRESS", outcome]}, reason)

    def _settled(self) -> bool:
        """An outcome is reached (the call ends with the closing line)."""
        return self.outcome != "IN_PROGRESS"

    def handle(self, signal, detector, said, trigger, target_language=None, refused_with_reason=False,
               mode_allowed=True) -> List[SwitchEntry]:
        """Apply one signal per the playbook. Returns the switch-log entries it produced."""
        out = []
        self.fired[signal] += 1
        self.turn_handled.add(signal)
        c, L = self.s["counts"], self.s["limits"]
        add = lambda e: e and out.append(e)  # noqa: E731

        if signal == "do_not_call":
            add(self._end("DO_NOT_CALL", signal, detector, said, "Seller asked not to be called: honour immediately."))
            return out
        if signal == "connectivity":
            c["connectivity"] += 1
            if c["connectivity"] >= L["connectivity"]:
                add(self._end("CALL_BACK_LATER", signal, detector, said, "Second audio failure: call back later."))
                return out
        if signal == "frustration":
            c["frustration"] += 1
            # never cut a seller who is asking something real (price, buy leads, who is calling...); a rhetorical
            # "kitni baar call karoge?" / "kal phir se call karogi?" IS the frustration (master intent 3)
            asking = bool(self.turn_tier1 & REAL_ASK)
            speaking = bool(_SPEAKING.search(said or "")) and c["frustration"] == L["frustration"]
            if speaking and not asking:
                self.yield_now = True   # "abhi main bol raha hoon...": apologise and give them the floor, once
            if c["frustration"] >= L["frustration"] and not asking and not speaking:
                # a complaint in the same breath is still captured and routed: "paisa diya tha, ek bhi lead
                # nahi aayi... bahut pareshan" was ended as ESCALATED_EXIT and the complaint was lost
                # a seller whose call is ABOUT a known complaint keeps it logged too (Delhi demo: the second
                # frustration on a complaint-recovery call ended ESCALATED_EXIT and the complaint was dropped)
                if "complaint" in self.turn_tier1 or self.fired["complaint"] or self.s["goal"] == "complaint_recovery":
                    self.fired["complaint"] += 0 if self.fired["complaint"] else 1
                    add(self._apply_goal("complaint_recovery", "complaint", detector, said, trigger, force=True))
                    add(self._end("COMPLAINT_LOGGED", signal, detector, said,
                                  "Frustrated twice WITH a complaint: stop asking, log the complaint for support, end politely.",
                                  hard=True))
                else:
                    add(self._end("ESCALATED_EXIT", signal, detector, said, "Frustrated twice: end politely (ask limit 2)."))
                return out
        if signal == "buylead_query":
            # self-service, no meeting (IndiaMART 10 Oct 2026); the second buy-lead question -> WhatsApp details
            c["buylead"] += 1
            self.s["stage"] = "goal_step"
            if c["buylead"] >= 2 and self.s["goal"] not in PROTECTED_GOALS and "whatsapp" not in self.declined_offers:
                add(self._apply_goal("info_whatsapp", signal, detector, said, trigger, force=True))
            return out
        if signal == "not_interested":
            c["refusals"] += 1
            self.s["stage"] = "goal_step"
            last_q = _last_question(next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), ""))
            if _WHATSAPP.search(last_q):
                self.declined_offers.add("whatsapp")
            if _PITCH.search(last_q):
                self.declined_offers.add("meeting")
            # master intent 9: refused again, "zaroorat nahi", a reason, a final-refusal phrase, or any no to the
            # two-option question -> the RESPECTFUL_EXIT line at once; a first plain no -> the two-option question
            txt = self.current_text or said or ""
            if (c["refusals"] >= L["refusals"] or _FINAL_REFUSAL.search(txt) or refused_with_reason or _has_reason(txt)
                    or self.reason_q_turn is not None or self.s["goal"] == "respectful_exit"):
                add(self._apply_goal("respectful_exit", signal, detector, said, trigger, force=True))
                add(self._end("RESPECTFUL_EXIT", signal, detector, said,
                              "Refusal (master intent 9): close with the WhatsApp proposal line; no further question."))
                return out
            self.reason_q_due = True
        if signal == "wants_whatsapp":
            # master 16b: asked for WhatsApp while VANI was asking for a meeting -> push once for the meeting
            last_q = _last_question(next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), ""))
            if (_PITCH.search(last_q) and not self.wa_pushed and not self.dnc_requested
                    and self.s["goal"] in ("meeting", "nurture", "callback")):
                self.wa_pushed, self.wa_push_now = True, True
                return out
            add(self._apply_goal("info_whatsapp", signal, detector, said, trigger))
            add(self._end("INFO_SENT", signal, detector, said, "Seller wants details on WhatsApp: confirm and close.",
                          hard=self.dnc_requested))
            return out
        if signal == "language_switch":
            if target_language and target_language not in ("unsupported", self.s["language"]):
                before = self.s["language"]
                self.s["language"] = target_language
                add(self._log("language", signal, detector, said, trigger, {"language": [before, target_language]},
                              "Seller switched language: switch fully, repeat the pending point; the voice stays the same."))
            return out
        if signal == "busy" and (self.meeting_pending or self._meeting_capable()) and re.search(
                r"\bmil(ne|na)\b|मिलने|in\s*person|aa\s*nahi|visit", said or "", re.I):
            return out   # no time to MEET: the meeting goes online (the gate asks), the goal stays
        if signal == "frustration" and CALL_FREQUENCY.search(said or ""):
            # "baar baar phone karte ho": a later call is the wrong offer (live session 125638); offer WhatsApp
            # details or let them go (master intent 3) -- sent only if they say yes
            self.call_freq = True
            if "whatsapp" not in self.declined_offers:
                add(self._apply_goal("info_whatsapp", signal, detector, said, trigger))
        elif signal in GOAL_SWITCHES and signal not in ("not_interested",):
            add(self._apply_goal(GOAL_SWITCHES[signal][0], signal, detector, said, trigger))
        # any signal that reveals the seller's position ends the understanding stage (a refusal on turn 1
        # was being forced back to the understanding question by the understand-first guard)
        if (signal in GOAL_SWITCHES or signal in ("not_interested", "gives_time")) and self.s["stage"] == "understand":
            self.s["stage"] = "goal_step"
        mode = SIGNAL_MODE.get(signal)
        if mode and mode != "LANGUAGE" and mode_allowed:
            add(self._apply_mode(mode, signal, detector, said, trigger))
        return out

    def _expire_and_revert(self, signals_this_turn):
        if self.s["mode"] in TRANSIENT_MODES:
            back = self.prev_mode
            p = PERSONA_MODES[back]
            before = self.s["mode"]
            self.s["mode"] = back
            self.s["max_words"] = p["max_words"] or self.base["max_words"]
            self._log("recovery", "transparent_done", "engine", "", "", {"mode": [before, back]},
                      "TRANSPARENT lasts one reply; resume the previous mode.")
        mode_sig = {s for s, m in SIGNAL_MODE.items() if m == self.s["mode"]}
        if self.s["mode"] in REVERTING_MODES:
            self.quiet_turns = 0 if (mode_sig & set(signals_this_turn)) else self.quiet_turns + 1
            if self.quiet_turns >= MODE_HOLD_TURNS:
                before = {k: self.s[k] for k in ("mode", "pace", "max_words")}
                self.s.update(mode="DEFAULT", pace=self.base["pace"], max_words=self.base["max_words"],
                              empathy=self.base["empathy"], assertiveness=self.base["assertiveness"])
                self.quiet_turns = 0
                self._log("recovery", "signal_resolved", "engine", "", "",
                          {k: [before[k], self.s[k]] for k in before if before[k] != self.s[k]},
                          f"Two turns without the signal behind {before['mode']}: back to the seller's default persona.")

    # ------------------------------------------------------------------ LLM + guards
    def _reply_problem(self, data) -> Optional[Tuple[str, str]]:
        reply, qtype = data["reply"], data.get("question_type")
        lang = self.s["language"]
        wrap = self.wrap_up  # answering a last question after the outcome: no goal-ask guards
        if _HUMAN_CLAIM.search(reply):
            return "human", "You implied you are human. You are IndiaMART's virtual assistant."
        if _INTERNAL.search(reply):
            return "internal", "You revealed an internal label or variable. Never mention goals, modes or seller data fields."
        if _PRICE.search(reply):
            return "price", "Never quote prices, packages, percentages, lead counts or results. Say the executive explains charges and the meeting is free."
        # a cost question must get the playbook answer THIS turn (Chennai demo: "Is there any cost?" was
        # skipped for a busy line, and the seller had to ask again: "You did not answer my question")
        if "price_query" in self.turn_tier1 and not _PRICE_ANSWER.search(reply):
            return "price_unanswered", "The seller asked about cost. Answer it first: charges depend on their plan and leads, and the executive explains them for their category. Never quote a price or call anything free."
        if _CHANNEL.search(reply):
            return "channel", "Do not offer SMS or email; WhatsApp or a call only."
        # a busy seller gets a short turn: the budget was only a prompt hint and a 31-word reply went to a
        # seller who had just said they had no time (recording replay)
        if self.s["mode"] in ("BRIEF", "COMPRESSED") and len(reply.split()) > 1.5 * self.s["max_words"]:
            return "too_long", f"The seller is short of time. At most {self.s['max_words']} words: one acknowledgement and one question."
        if not wrap and (self.fired["complaint"] or self.fired["frustration"] or self.fired["sarcasm"]) and _PITCH.search(reply) \
                and self.s["goal"] != "meeting":
            return "pitch_after_complaint", "Never pitch (meeting, visit, package) after a complaint or frustration."
        # master: never call the executive meeting free
        if _FREE_MEETING.search(reply):
            return "free_meeting", "Never describe the meeting as free; the executive explains the charges for their category."
        # "never repeat a pitch the seller declined" (master section 10)
        if not wrap and self.fired["not_interested"] and _PITCH.search(reply) and not _WHATSAPP.search(reply):
            return "pitch_after_no", "The seller said no: never re-pitch."
        if not wrap and "whatsapp" in self.declined_offers and _WHATSAPP.search(reply):
            return "repeat_declined_offer", "The seller already declined WhatsApp details. Do not offer them again."
        # scenario 5/6: "who is calling / why" must be answered (playbook: always say fully who is
        # calling and why). Caught in the scenario suite: VANI ignored the question and pitched.
        if self.s["mode"] == "TRANSPARENT" and not re.search(r"Payal|Rohan|पायल|रोहन", reply, re.I):
            return "disclosure", "The seller asked who is calling: say your name, IndiaMART and why you called."
        # "virtual assistant" only when the seller asked whether it is a bot (master prompt section 1)
        if _VA_MENTION.search(reply) and not self._ai_asked(data):
            return "unasked_va", "Do not say you are a virtual assistant unless the seller asks whether you are a bot or AI."
        if not wrap and self._buylead_turn(data) and _PITCH.search(reply):
            return "buylead_meeting", ("The seller asked about buy leads: point them to the IndiaMART seller dashboard's "
                                       "BuyLeads section (website or app). Do not ask for a meeting.")
        q_slot = slots.parse(_last_question(reply)) if _PITCH.search(_last_question(reply) or "") else None
        if not wrap and q_slot is not None and not slots.is_valid_meeting(q_slot):
            return "bad_slot_offer", ("Meetings only between 9 AM and 6 PM, from tomorrow: offer two concrete options, "
                                      "e.g. tomorrow 11 AM or day after tomorrow 4 PM.")
        if not wrap and not self.meeting_pending and _DECIDED.search(reply) and slots.parse(reply) \
                and not self._seller_chose_slot(self.current_seller or ""):
            return "bad_slot_offer", ("The seller has not chosen a time: never fix one yourself. Offer two concrete "
                                      "options and let the seller choose.")
        bad = self.ledger.latest("business_status")
        if bad and bad.value == "bad" and _GLAD.search(reply) and not self.sarcasm_turn:
            return "glad_on_bad", "The seller said business is bad: never say it is good to hear. Acknowledge with empathy."
        if self.call_freq and not wrap and q_offer_call(reply):
            return "call_offer", ("The seller complained about repeated calls: never offer another call. Apologise once "
                                  "and offer only to send the details on WhatsApp.")
        if _BANNED.search(reply):
            return "banned_phrase", "Do not say that you are listening carefully, 'in simple words' or 'in one line'."
        if wrap:
            if [w for w, _ in GENDER_FIX[self.s["gender"]] if w in reply]:
                return "gender", f"The voice is {self.s['gender']}; first-person verb forms must agree."
            if lang == "hi-IN" and not _DEVANAGARI.search(reply):
                return "script", "Write Hindi words in Devanagari."
            if lang == "te-IN" and not _TELUGU.search(reply):
                return "script", "Reply in Telugu script."
            return None
        q = _last_question(reply)
        # "What details on WhatsApp?": after answering, VANI puts her pending question once more. That is the
        # same ask, not a new one, so neither the repeat check nor the goal-ask limit removes it (once only)
        pending = _last_question(next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), ""))
        times_asked = sum(1 for h in self.history if h["speaker"] == "vani" and pending
                          and _similar(_last_question(h["text"]), pending) >= 0.6)
        reask_ok = bool(self.seller_act == "question" and q and pending and _similar(q, pending) >= 0.6 and times_asked < 2)
        if self.sarcasm_turn and _GLAD.search(reply):
            return "sarcasm_literal", ("The seller was being sarcastic after your pitch. Do not say it is good to hear; "
                                       "acknowledge, apologise once and offer only WhatsApp details or a later call.")
        if self.pending_clarify and data.get("clarify_fact") != self.pending_clarify.fact:
            c = self.pending_clarify
            return "clarify_missing", (f"The seller contradicted an earlier statement (turn {c.earlier.turn}: \"{c.earlier.words}\"; "
                                       f"now: \"{c.now_words}\"). Ask ONE gentle clarifying question offering the likely "
                                       f"explanation, set clarify_fact \"{c.fact}\", and do not pitch this turn.")
        if (self.pending_clarify and data.get("clarify_fact") == self.pending_clarify.fact and "?" in reply
                and reply.rstrip().rsplit("?", 1)[1].strip()):
            return "clarify_tail", "End on the clarifying question; say nothing after it."
        if data.get("clarify_fact") and not self._clarify_allowed(data.get("clarify_fact"), data):
            return "no_clarify", "Do not ask a clarifying question now; continue toward the current goal."
        # the understanding question, once answered, is never asked again -- in any language (the Chennai
        # session re-asked it in Hindi after an English opening, so the same-language repeat check missed it)
        if q and not self.pending_clarify and self.ledger.latest("business_status") and (
                _similar(q, self.persona["conversation_plan"]["understanding_question"]) >= 0.5
                or _similar(q, GENERIC_UNDERSTANDING_EN) >= 0.5 or _HOW_BUSINESS.search(q)
                or _similar(q, _last_question(self.persona["conversation_plan"]["opening"]["value"])) >= 0.5):
            return "drop_question", "The seller already told you how the business is going. Do not ask it again; move forward."
        if (self.s["stage"] == "understand" and qtype == "goal_step" and self.turn <= 1 and not data.get("understanding_answered")
                and not self.persona["conversation_plan"].get("context_in_first_reply")):
            return "understand_first", "Understand the seller first: ask the understanding question, not the goal ask."
        if qtype == "goal_step" and self.s["counts"]["goal_step"] >= self.s["limits"]["goal_step"] and not reask_ok:
            return "drop_question", "The goal ask has hit its limit; do not ask it again."
        wrong = [w for w, _ in GENDER_FIX[self.s["gender"]] if w in reply]
        if wrong:
            return "gender", f"The voice is {self.s['gender']}; first-person verb forms must agree."
        if lang == "hi-IN" and (not _DEVANAGARI.search(reply) or sum(t in _HINDI_WORDS - {"ji"}
                                                                  for t in re.findall(r"[a-z]+", reply.lower())) >= 3):
            return "script", "Write Hindi words in Devanagari."
        if lang == "en-IN" and (_DEVANAGARI.search(reply) or sum(t in _HINDI_WORDS - {"ji"}
                                                                for t in re.findall(r"[a-z]+", reply.lower())) >= 2):
            return "translate", "The seller speaks English: reply in English only."
        # "apologise once": a sentence already said earlier in the call (disclosure + apology was repeated
        # word for word in the demo) is dropped; questions are handled by the repeat-question check below
        said = [s for h in self.history if h["speaker"] == "vani"
                for s in re.split(r"(?<=[.?!।])\s*", h["text"]) if len(s.split()) >= 4 and not self._value_repeat_ok(s)]
        if any(_similar(s, p) >= 0.7 for s in re.split(r"(?<=[.?!।])\s*", reply) if len(s.split()) >= 4
               and not s.strip().endswith("?") for p in said):
            return "repeat_sentence", "You are repeating a sentence you already said (e.g. the apology or introduction). Say it once only."
        if lang == "te-IN" and not _TELUGU.search(reply):
            return "script", "Reply in Telugu script."
        if q and not reask_ok:
            for h in self.history:
                prev = _last_question(h["text"]) if h["speaker"] == "vani" else ""
                if prev and _similar(q, prev) >= 0.6:
                    return "drop_question", f"You already asked \"{prev}\". Ask something different or move forward."
        # an ending the call does not support (e.g. RESPECTFUL_EXIT after the FIRST frustration, or
        # COMPLAINT_LOGGED before asking when support may call): fixed before it is spoken
        proposed = data.get("call_outcome")
        if not self.ended and proposed not in (None, "IN_PROGRESS") and not self._outcome_supported(proposed, data) \
                and not (proposed == "MEETING_FIXED" and self._meeting_capable()):
            return "unsupported_outcome", (f"Do not end the call with {proposed} yet; it is not supported by what the seller said. "
                                           f"Follow the playbook action for the seller's signal and end with one question toward "
                                           f"the goal '{self.s['goal']}'.")
        # no ending was earned, so the turn must move forward with a question (also when the LLM set
        # end_call without an outcome: "जी, कोई बात नहीं।" was spoken as a dead end in the replay)
        if (not self.ended and proposed in (None, "IN_PROGRESS") and "?" not in reply and not data.get("_no_new_question")
                and not self._exit_due()):
            return "no_question", "End with one clear question toward the current goal (unless closing)."
        return None

    def _exit_due(self) -> bool:
        """Master 4.2 (7+ calls): one light question, then close -- on the seller's next answer, unless they show
        interest (the goal then moves) or are still asking something."""
        return (self.s["goal"] == "respectful_exit" and self.s["counts"]["goal_step"] >= 1
                and self.seller_act not in ("question", "request"))

    def _goal_question(self, goal=None):
        """The repair question in the CALL's language (a Hindi understanding question was appended to an
        English call in the scenario suite; a Hindi WhatsApp offer to a Telugu call in the demo)."""
        lang = self.s["language"]
        if self.s["stage"] == "understand" and goal is None:
            hi, en = self.persona["conversation_plan"]["understanding_question"], "How is your business going right now?"
        else:
            g = goal or self.s["goal"]
            g = g if g in GOAL_QUESTION["hi-IN"] else "meeting"
            hi, en = GOAL_QUESTION["hi-IN"][g], GOAL_QUESTION["en-IN"][g]
        if lang == "hi-IN":
            return hi
        if lang == "en-IN":
            return en
        try:  # Telugu: translate the English line (more reliable than Hindi -> Telugu)
            return client().text.translate(input=en, source_language_code="en-IN", target_language_code="te-IN").translated_text
        except Exception:
            return en

    def _clarify_text(self, c) -> str:
        lang = self.s["language"]
        enq = bool(re.search(r"enquir|inquir|lead|एन्क्वायरी|enquiries", c.now_words, re.I))
        if lang != "te-IN":
            return clarify_line(c, lang, enq)
        try:
            return client().text.translate(input=clarify_line(c, "en-IN", enq), source_language_code="en-IN",
                                           target_language_code="te-IN").translated_text
        except Exception:
            return clarify_line(c, "en-IN", enq)

    def _clarify_allowed(self, fact, data=None, found=False) -> bool:
        """Once per fact, twice per call, never on a do-not-call / frustration / complaint / refusal turn or when
        the seller is short of time; and only when there IS a contradiction (rules or the LLM's facts)."""
        if fact not in CONTRADICTION_FACTS or fact in self.clarified or len(self.clarified) >= 2:
            return False
        if self.turn_tier1 & {"do_not_call", "frustration", "complaint", "not_interested"} or self.sarcasm_turn:
            return False
        if self.s["mode"] in ("BRIEF", "COMPRESSED"):
            return False
        if found or (self.pending_clarify and self.pending_clarify.fact == fact):
            return True
        value = self._llm_facts(data).get(fact)
        return bool(value and self.ledger.contradiction(fact, value, self.turn, self.current_seller or ""))

    def _repair(self, reply, kind, data=None):
        lang = self.s["language"]
        if kind == "free_meeting":
            sents = [x.strip() for x in re.split(r"(?<=[.?!।])\s*", reply) if x.strip()]
            keep = [x for x in sents if not _FREE_MEETING.search(x)]
            if "price_query" in self.turn_tier1 and not any(_PRICE_ANSWER.search(x) for x in keep):
                keep.insert(0, PRICE_LINE.get(lang, PRICE_LINE["en-IN"]))
            return " ".join(keep) or SAFE_LINE[lang]
        if kind in ("clarify_missing", "no_clarify", "sarcasm_literal"):
            sents = [x.strip() for x in re.split(r"(?<=[.?!।])\s*", reply) if x.strip()]
            if kind == "sarcasm_literal":
                return " ".join(x for x in sents if not _GLAD.search(x)) or SAFE_LINE[lang]
            sents = [x for x in sents if not x.endswith("?") and not _PITCH.search(x)]
            if kind == "no_clarify":
                if data is not None:
                    data["clarify_fact"] = ""
                return " ".join(sents) or SAFE_LINE[lang]
            if data is not None:
                data["clarify_fact"], data["question_type"] = self.pending_clarify.fact, "clarify"
            ack = [x for x in sents if len(x.split()) <= 6][:1]  # keep a short acknowledgement only
            return " ".join(ack + [self._clarify_text(self.pending_clarify)])
        if kind in ("unsupported_outcome", "no_question"):
            if data is not None:
                data["call_outcome"], data["end_call"] = "IN_PROGRESS", False
            sents = [x.strip() for x in re.split(r"(?<=[.?!।])\s*", reply) if x.strip()]
            closing = re.compile(r"धन्यवाद|शुभ हो|thank|have a good|good day|ధన్యవాదాలు", re.I)
            sents = [x for x in sents if not closing.search(x)]
            if any(x.endswith("?") for x in sents):  # already asks something: do not stack a second question
                return " ".join(sents)
            gq = self._goal_question()
            asked = lambda q: any(_similar(q, _last_question(h["text"])) >= 0.6  # noqa: E731
                                  for h in self.history if h["speaker"] == "vani")
            already = asked(gq)
            if already and self.s["stage"] == "understand":
                # the seller deflected the opening question ("utna time nahi hai"): move on to the goal
                # ask rather than re-ask it or leave a dead-end statement (replay found both)
                self.s["stage"] = "goal_step"
                gq = self._goal_question()
                already = asked(gq)
            if data is not None:
                # the appended question IS an ask: count it (an uncounted repair ask kept respectful_exit
                # from ever closing); if it was already asked, do not ask again -- the step is done
                data["question_type"] = "understanding" if self.s["stage"] == "understand" else "goal_step"
                if already:
                    data["_no_new_question"] = True
                    data["question_type"] = "none"  # no ask made this turn: lets the ask-limit fallback move the goal
                    return " ".join(sents) or SAFE_LINE[lang]
            return " ".join(sents + [gq]).strip() or gq
        if kind in ("unasked_va", "banned_phrase", "buylead_meeting", "bad_slot_offer"):
            sents = [x.strip() for x in re.split(r"(?<=[.?!।])\s*", reply) if x.strip()]
            if kind == "unasked_va":
                return " ".join(x for x in sents if not _VA_MENTION.search(x)) or SAFE_LINE[lang]
            if kind == "banned_phrase":
                return " ".join(_BANNED.sub("", x).strip(" ,:—-") for x in sents if _BANNED.sub("", x).strip(" ,:—-")) or SAFE_LINE[lang]
            if kind == "buylead_meeting":
                keep = [x for x in sents if not _PITCH.search(x) and not x.endswith("?")]
                line = BUYLEAD_LINE.get(lang, BUYLEAD_LINE["en-IN"])
                return " ".join(keep + ([] if any(_similar(x, line) > 0.5 for x in keep) else [line])
                                + [BUYLEAD_LIGHT_CHECK.get(lang, BUYLEAD_LIGHT_CHECK["en-IN"])])
            keep = [x for x in sents if not x.endswith("?")]
            return " ".join(keep + [slots.TWO_SLOTS.get(lang, slots.TWO_SLOTS["en-IN"])])
        if kind == "clarify_tail":
            return reply.rstrip().rsplit("?", 1)[0] + "?"
        if kind == "disclosure":
            name = BOT_NAME[self.s["gender"]]
            if not self._ai_asked(data):  # "kaun bol raha hai?" -> name and IndiaMART, no AI mention
                bol = "बोल रहा हूँ" if self.s["gender"] == "male" else "बोल रही हूँ"
                line = {"hi-IN": f"मैं IndiaMART से {name} {bol}।", "en-IN": f"This is {name} from IndiaMART.",
                        "te-IN": f"నేను IndiaMART నుండి {name}."}[lang]
                return self._with_intro(line, reply)
            line = {"hi-IN": (f"मैं IndiaMART की virtual assistant {name} हूँ।" if self.s["gender"] == "female"
                              else f"मैं IndiaMART का virtual assistant {name} हूँ।"),
                    "en-IN": f"I am {name}, IndiaMART's virtual assistant.",
                    "te-IN": f"నేను IndiaMART virtual assistant {name} ని."}[lang]
            return self._with_intro(line, reply)
        if kind == "gender":
            for a, b in GENDER_FIX[self.s["gender"]]:
                reply = reply.replace(a, b)
            return reply
        try:
            if kind == "script":
                return self._transliterate_hindi_runs(reply, lang)
            if kind == "translate":
                return client().text.translate(input=reply, source_language_code="auto", target_language_code="en-IN").translated_text
        except Exception:
            pass
        sents = [x for x in re.split(r"(?<=[.?!।])\s*", reply) if x.strip()]
        if kind == "repeat_sentence":
            said = [s for h in self.history if h["speaker"] == "vani" for s in re.split(r"(?<=[.?!।])\s*", h["text"])
                    if len(s.split()) >= 4 and not self._value_repeat_ok(s)]
            keep = [x for x in sents if x.strip().endswith("?") or len(x.split()) < 4
                    or not any(_similar(x, p) >= 0.7 for p in said)]
            return " ".join(x.strip() for x in keep) or self._goal_question()
        pat = {"human": _HUMAN_CLAIM, "internal": _INTERNAL, "price": _PRICE, "channel": _CHANNEL,
               "pitch_after_complaint": _PITCH, "pitch_after_no": _PITCH, "repeat_declined_offer": _WHATSAPP, "glad_on_bad": _GLAD}.get(kind)
        if kind == "call_offer":
            q = _last_question(reply)
            sents = [x for x in sents if x.strip() != q and not _CALL_OFFER.search(x)]
            if "whatsapp" not in self.declined_offers:
                sents.append(GOAL_QUESTION[lang if lang in GOAL_QUESTION else "en-IN"]["info_whatsapp"])
        elif kind in ("drop_question", "understand_first"):
            q = _last_question(reply)
            sents = [x for x in sents if x.strip() != q]
            if kind == "understand_first":
                sents.append(self._goal_question())
        elif pat:
            sents = [x for x in sents if not pat.search(x)]
            if kind == "pitch_after_no":
                sents.append(self._goal_question("info_whatsapp"))
            if kind == "price":
                sents.insert(_before_question(sents), PRICE_LINE[lang])
        elif kind == "price_unanswered":
            sents.insert(_before_question(sents), PRICE_LINE[lang])
        elif kind == "too_long":
            q = _last_question(reply)
            sents = [sents[0]] + ([q] if q and q != sents[0] else []) if sents else sents
        out = " ".join(x.strip() for x in sents) or SAFE_LINE[lang]
        return out

    def _repair_all(self, data, problem):
        for _ in range(3):
            if not problem:
                break
            before = data["reply"]
            data["reply"] = self._repair(data["reply"], problem[0], data)
            self.guard_corrections.append({"turn": self.turn, "kind": problem[0], "action": "repaired",
                                           "before": before, "after": data["reply"]})
            problem = self._reply_problem(data)
        return data

    def _llm_facts(self, data) -> Dict[str, str]:
        """The LLM's fact for this line: one "key=value" in fact_update (or a `facts` object). Only business status
        and enquiry level: asked for every fact, it filled has_executive "no" for a seller who never said so."""
        out = {}
        raw = (data or {}).get("fact_update") or ""
        for part in re.split(r"[,;]", raw):
            k, _, v = part.partition("=")
            out[k.strip()] = v.strip()
        out.update({k: v for k, v in ((data or {}).get("facts") or {}).items() if isinstance(v, str)})
        return {k: v for k, v in out.items() if k in LLM_FACTS and v in VALUES[k]}

    def _llm(self, seller_text: str, tier1: List[str]) -> Dict[str, Any]:
        self.s["facts_view"] = self.ledger.view()
        msgs = [{"role": "system", "content": build_system_prompt(self.persona, self.s)}] + history_to_messages(self.history)
        steer = (f"[Reply language: {LANG_NAME[self.s['language']]}. Persona mode: {self.s['mode']}. Goal: {self.s['goal']} "
                 f"({self.s['stage']}). About {self.s['max_words']} words. Voice is {self.s['gender']}.]")
        hint = f"\n[tier-1 detector flagged: {', '.join(tier1)}]" if tier1 else ""
        if self.seller_act == "question":
            hint += ("\n[The seller ASKED A QUESTION. Answer it first, plainly and truthfully, then continue. A question "
                     "is not a yes or a no: do not treat it as agreement, refusal or a request.]")
        if self.pending_clarify:
            c = self.pending_clarify
            hint += (f"\n[The seller CONTRADICTED an earlier statement: turn {c.earlier.turn} \"{c.earlier.words}\", now "
                     f"\"{c.now_words}\". Ask ONE gentle clarifying question that names both and offers the likely "
                     f"explanation, never accusing, for example: \"{self._clarify_text(c)}\" Set clarify_fact "
                     f"\"{c.fact}\". No pitch this turn.]")
        plan = self.persona["conversation_plan"]
        if plan.get("context_in_first_reply") and self._greeting_pending():
            light = {"complaint_recovery": "Kya dikkat aayi thi, bataiyega?",
                     "exec_handoff": "Aap pehle se hamare executive ke saath jude hain na?",
                     "data_update": "IndiaMART ke kaam ke liye sahi vyakti aap hi hain, ya kisi aur se baat karni chahiye?"
                     }.get(self.s["goal"], "Kya aap iske baare mein jaanna chahenge?")
            hint += (f"\n[First reply after the greeting. Do NOT introduce yourself again. In this order: why you called "
                     f"(\"{plan.get('call_reason', '')}\"); if that reason is not about buyer enquiries, one line that buyers are "
                     f"available in their category (no numbers); any apology (repeat or complaint seller); then ONE light "
                     f"question: \"{light}\" (in the call's language). If they say this is not {plan.get('company_name')}, "
                     f"handle it as the wrong person.]")
        if self.sarcasm_turn:
            hint += ("\n[Likely SARCASM: the seller said business is bad, and right after your pitch says, exaggerated, that "
                     "everything is great. Do not take it literally and do not say it is good to hear. Acknowledge, "
                     "apologise once for pushing, and offer only WhatsApp details or a later call. Set sarcasm \"clear\".]")
        if self.barged_in:
            hint += ("\n[The seller INTERRUPTED you mid-sentence (your last turn shows only what they heard). Respond to "
                     "what they said; do not repeat the part they heard; keep it short. Do not mention or apologise for the "
                     "interruption.]")
        msgs.append({"role": "user", "content": f"Seller: {seller_text}{hint}\n{steer}"})
        data, err = None, None
        for attempt in range(3):
            try:
                r = client().chat.completions(messages=msgs, model=self.llm_model, temperature=0.2, max_tokens=800,
                                              stop=PADDING_STOP,
                                              response_format={"type": "json_schema", "json_schema": {
                                                  "name": "vani_turn", "schema": OUTPUT_SCHEMA, "strict": True}})
                data = parse_turn_json(r.choices[0].message.content)
                if not data.get("reply"):
                    raise ValueError("empty reply")
            except Exception as e:  # malformed JSON / API hiccup: retry, then degrade safely
                err = e
                self.guard_corrections.append({"turn": self.turn, "kind": "llm_error", "error": type(e).__name__})
                # a whole suite call fell back to "please repeat" on every turn after back-to-back runs: a rate
                # limit retried at once just fails again
                if "TooManyRequests" in type(e).__name__ or "429" in str(e)[:200]:
                    time.sleep(1.5 * (attempt + 1))
                continue
            problem = self._reply_problem(data)
            n_mech = 0
            while problem and problem[0] in MECHANICAL and n_mech < 3:
                # the LLM's own words, fixed in code: same content, no ~0.8 s retry (most retries were "script")
                before = data["reply"]
                data["reply"] = self._repair(data["reply"], problem[0], data)
                self.guard_corrections.append({"turn": self.turn, "kind": problem[0], "action": "repaired",
                                               "before": before, "after": data["reply"]})
                n_mech += 1
                problem = self._reply_problem(data)
            if problem and attempt < 2:
                self.guard_corrections.append({"turn": self.turn, "kind": problem[0], "action": "llm_retry"})
                msgs += [{"role": "assistant", "content": data["reply"]},
                         {"role": "user", "content": f"[Correction: {problem[1]} Rewrite the whole JSON.]\n{steer}"}]
                continue
            return self._repair_all(data, problem)
        # every retry failed (a correction retry ran out of tokens mid-JSON in the scenario suite): the last good
        # reply still goes through the repairs -- it used to be returned as is, and an unsupported RESPECTFUL_EXIT
        # closed the call without the contact-preference question
        if data and data.get("reply"):
            return self._repair_all(data, self._reply_problem(data))
        return {"seller_signals": [], "seller_language": self.s["language"], "signal_reason": f"LLM failed ({type(err).__name__})",
                "seller_insights": {}, "understanding_answered": False, "refused_with_reason": False, "slot": "",
                "reply": {"hi-IN": "माफ़ कीजिए, क्या आप एक बार फिर बता सकते हैं?", "en-IN": "Sorry, could you say that once more?",
                          "te-IN": "క్షమించండి, ఒక్కసారి మళ్ళీ చెప్పగలరా?"}[self.s["language"]],
                "question_type": "clarify", "call_outcome": "IN_PROGRESS", "end_call": False}

    # ------------------------------------------------------------------ outcome & closing
    def _outcome_supported(self, outcome, data=None) -> bool:
        # the call is never cut while the seller is asking something (master section 8; IndiaMART, 10 Oct 2026):
        # only a do-not-call or a dead line closes on a question
        if self.seller_act == "question" or (data or {}).get("seller_act") == "question":
            if outcome not in ("DO_NOT_CALL", "CALL_BACK_LATER"):
                return False
        # a contradiction is being clarified this turn: an opening "haan" ("haan enquiry to aa rahi hai") is a
        # filler, not a yes to the pending offer (suite run closed INFO_SENT instead of asking). Hard endings
        # (do-not-call, second frustration...) still act at once
        if self.pending_clarify and outcome not in HARD_ENDINGS:
            return False
        sellers = [h["text"] for h in self.history if h["speaker"] == "seller"]
        if self.current_seller is not None:  # called from inside the LLM loop, before the turn is in history
            sellers.append(self.current_seller)
        seller_words = " ".join(sellers)
        f, g, goals = Counter(self.fired), self.s["goal"], set(self.goal_history)
        # inside the LLM loop this turn's LLM signals are not applied yet; count the ones that will act
        # (a valid CONTACT_UPDATED was rejected because not_right_person was only seen by tier 2)
        for sg in (data or {}).get("seller_signals", []) or []:
            if sg.get("signal") in self.turn_tier1:
                continue  # already counted by tier 1 this turn (double counting let a refusal exit early)
            if sg.get("signal") and (sg.get("confidence") == "high" or sg.get("signal") in ACT_ON_MEDIUM):
                f[sg["signal"]] += 1
                if sg["signal"] in GOAL_SWITCHES:
                    goals.add(GOAL_SWITCHES[sg["signal"]][0])
        last_vani = next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), "")
        last_seller = sellers[-1] if sellers else ""
        # a slot counts if the seller named a time, OR agreed to a time VANI just proposed
        # ("kal shaam 7 baje?" -> "haan theek hai"); the first version only accepted the former
        seller_named_time = any(h.signal == "gives_time" for s in sellers for h in detect_signals(to_roman(s) if is_devanagari(s) else s)) \
            or bool(_DEV_TIME.search(seller_words))
        vani_proposed_time = bool(_TIME_TOKEN.search(_last_question(last_vani) or ""))
        no_words = bool(re.search(r"\b(nahi|nhi|na|no|mat)\b|नहीं", last_seller, re.I))
        # "Ok, but what details?" opens with "ok" and was read as a yes: a question is not agreement
        # (by the rules, or by the LLM's own reading of the act)
        asked = dialogue_act(to_roman(last_seller) if is_devanagari(last_seller) else last_seller) == "question" \
            or (data or {}).get("seller_act") == "question"
        no_words = no_words or asked
        slot_agreed = seller_named_time or (vani_proposed_time and _agrees(last_seller) and not no_words)
        rules = {
            "DO_NOT_CALL": f["do_not_call"] > 0,
            "ESCALATED_EXIT": f["frustration"] >= 2,
            "CALL_BACK_LATER": f["connectivity"] >= 2,
            # the format answer ("online") after "milkar ya online?" completes a slot already agreed (master 4.1)
            "MEETING_FIXED": (slot_agreed or self.meeting_ready or bool(self.meeting_pending and slots.FORMAT.search(last_seller)))
                             and g in ("meeting", "nurture", "info_whatsapp", "callback"),
            # busy alone is not a callback ("na na utna time nahi hai" was closed as CALLBACK_SCHEDULED)
            "CALLBACK_SCHEDULED": slot_agreed,
            "HUMAN_HANDOFF": f["human_request"] > 0,
            "INFO_SENT": (("wants_whatsapp" in self.turn_tier1 or any(sg.get("signal") == "wants_whatsapp"
                                                                         for sg in (data or {}).get("seller_signals", []) or []))
                          and bool(_WANTS_WA_EVIDENCE.search(last_seller)) and not asked)
                         or (bool(_WHATSAPP.search(_last_question(last_vani))) and _agrees(last_seller) and not no_words
                             and not re.search(r"\s(या|ya|or|లేదా)\s", _last_question(last_vani), re.I)),
            # the playbook's complaint step includes asking WHEN support may call (a complaint was closed
            # in the demo after a generic "what went wrong?" question, with no support-time ask)
            "COMPLAINT_LOGGED": (f["complaint"] > 0 or "complaint_recovery" in goals)
                                and (slot_agreed or self.support_time_asked or f["not_interested"] > 0),
            # these need the goal step done: VANI asked what to pass on / who the right person is,
            # or the seller already gave it (a CONTACT_UPDATED was claimed without asking anything)
            "EXEC_HANDOFF": (f["already_with_executive"] > 0 or "exec_handoff" in goals)
                            and (self.s["counts"]["goal_step"] >= 1 or g != "exec_handoff"),
            "CONTACT_UPDATED": (f["not_right_person"] > 0 or "data_update" in goals)
                               and (self.s["counts"]["goal_step"] >= 1 or bool(re.search(r"\d{6,}|naam|name|नाम", seller_words, re.I))),
            # a first frustration is NOT an exit (playbook: apologise, offer a later call; end on the 2nd);
            # at the refusal limit VANI first asks the contact preference, THEN exits
            "RESPECTFUL_EXIT": f["not_interested"] > self.s["limits"]["refusals"]
                               or (g == "respectful_exit" and self.s["counts"]["goal_step"] >= 1),
        }
        return rules.get(outcome, False)

    def closing_line(self) -> str:
        """The master closing line (section 8) in the call's language, slot / person / format filled in."""
        if self.closing_override:
            return self.closing_override
        lang = self.s["language"]
        sellers = " ".join(h["text"] for h in self.history if h["speaker"] == "seller")
        if self.outcome == "COMPLAINT_LOGGED" and not self.slot and (self.fired["not_interested"] or _NEG_WORD.search(
                next((h["text"] for h in reversed(self.history) if h["speaker"] == "seller"), ""))):
            return COMPLAINT_DECLINED.get(lang, COMPLAINT_DECLINED["en-IN"])  # declined the support call: no promise
        disp, hi_f, hi_m, en = ENDINGS[self.outcome]
        default_slot = {"COMPLAINT_LOGGED": {"hi-IN": "जल्द ही", "en-IN": "soon", "te-IN": "త్వరలో"}.get(lang, "soon")}
        slot = self.slot or default_slot.get(self.outcome) or self.persona["conversation_plan"]["callback_slot"]["value"] or ""
        if slot and lang == "hi-IN" and not _DEVANAGARI.search(slot) and re.search(r"[a-z]", slot, re.I):
            try:  # "kal 4 baje" -> "कल 4 बजे" so the Hindi closing is read in one script
                slot = client().text.transliterate(input=slot, source_language_code="en-IN",
                                                   target_language_code="hi-IN").transliterated_text
            except Exception:
                pass
        rel = next(((hi, en_) for pat, hi, en_ in _RELATION if pat.search(sellers)), ("सही व्यक्ति", "the right person"))
        hi = (hi_m if (self.s["gender"] == "male" and hi_m) else hi_f)
        if self.s["gender"] == "male" and not hi_m:
            for a, b in GENDER_FIX["male"]:
                hi = hi.replace(a, b)
        text = ENDINGS_TE[self.outcome] if lang == "te-IN" else (en if lang == "en-IN" else hi)
        fmt = self.meeting_format or ""
        text = (text.replace("{slot}", slot).replace("{person}", rel[1] if lang == "en-IN" else rel[0])
                .replace(", {format}", f", {fmt}" if fmt else "").replace("{format}", fmt))
        return re.sub(r"\s{2,}", " ", text).strip()

    # ------------------------------------------------------------------ public API
    def _speak(self, text):
        if not self.synthesize_audio:
            return None
        return synthesize(text, speaker=self.s["speaker"], language_code=self.s["language"], pace=self.s["pace"])

    def start(self) -> TurnResult:
        reply = drop_ji(self.persona["conversation_plan"]["opening"]["value"])
        t = time.time()
        if self.synthesize_audio:  # the first reply is ready before the seller answers the greeting
            prefetch(self.persona["conversation_plan"].get("first_reply") or "", self.s["speaker"], self.s["language"],
                     self.s["pace"])
        audio = self._speak(reply)
        self.history.append({"speaker": "vani", "text": reply})
        self.last_bot_words = len(reply.split())
        return TurnResult(0, None, None, [], [], [], reply, self.outcome, False, self.delivery(), None, audio,
                          {"tts": int((time.time() - t) * 1000)})

    def _cut_last_reply(self, heard_fraction: Optional[float]) -> None:
        """The seller talked over VANI: keep only the part of her reply that was played, so an unheard
        question is not treated as asked (and is not blocked later as a repeat)."""
        last = self.history[-1] if self.history else None
        if not last or last["speaker"] != "vani":
            return
        words = last["text"].split()
        keep = max(1, round(len(words) * min(1.0, max(0.0, heard_fraction if heard_fraction is not None else 0.5))))
        if keep < len(words):
            last["text"], last["interrupted"] = " ".join(words[:keep]) + " …", True

    def seller_turn(self, text: Optional[str] = None, audio: Optional[bytes] = None,
                    audio_filename: str = "turn.wav", interrupted: bool = False,
                    heard_fraction: Optional[float] = None) -> TurnResult:
        if self.ended:
            raise RuntimeError("call already ended")
        self.turn += 1
        self.turn_handled = set()
        self.barged_in = bool(interrupted)
        self._uncut_entry = dict(self.history[-1]) if self.history and self.history[-1]["speaker"] == "vani" else None
        if interrupted:
            self._cut_last_reply(heard_fraction)
        lat, stt_lang, dur = {}, None, None
        if audio is not None:
            t = time.time()
            text, stt_lang = transcribe(audio, audio_filename)
            lat["stt"] = int((time.time() - t) * 1000)
            dur = _wav_seconds(audio)
        text = (text or "").strip()
        # (over the greeting a "haan haan" answers its question and shows a rushed seller: that one is a turn)
        if interrupted and (not text or (_BACKCHANNEL.match(text) and self.turn > 1)):
            # background voices / noise (nothing transcribed) or a listener's "haan", "hmm" over VANI: not an
            # interruption -- nothing changes, and the client resumes VANI where she paused
            self.turn -= 1
            if self._uncut_entry is not None and self.history and self.history[-1]["speaker"] == "vani":
                self.history[-1] = self._uncut_entry
            self.guard_corrections.append({"turn": self.turn + 1, "kind": "ignored_interruption",
                                           "heard": text or "(nothing)"})
            return TurnResult(self.turn, text or None, stt_lang, [], [], [], "", self.outcome, False, self.delivery(),
                              None, None, {**lat, "ignored": 1}, ignored=True)
        detect_text = to_roman(text) if is_devanagari(text) else text
        n_switch = len(self.switch_log)
        self.current_text = detect_text
        self.reason_q_due = self.wa_push_now = False
        if not text:
            return self._silent_turn(stt_lang, lat, n_switch)

        # tier 1
        t = time.time()
        hits = detect_signals(detect_text)
        # what kind of utterance this is: "What details on WhatsApp?" matched wants_whatsapp and the call
        # closed as INFO_SENT (Chennai demo). A question ABOUT the details is answered, not taken as a request
        self.seller_act = dialogue_act(detect_text)
        if self.seller_act == "question" and any(h.signal == "wants_whatsapp" for h in hits):
            hits = [h for h in hits if h.signal != "wants_whatsapp"]
            self.guard_corrections.append({"turn": self.turn, "kind": "question_not_request", "signal": "wants_whatsapp"})
        tier1 = [h.signal for h in hits]
        self.turn_tier1 = set(tier1)
        # a "no" right after an offer declines THAT offer, known before the reply is written (the guard
        # learned it only after the reply and VANI re-offered WhatsApp in the demo)
        last_q = _last_question(next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), ""))
        # "Just send everything on WhatsApp. No more calls." was read as declining WhatsApp (the "No"
        # belongs to the calls) and the request was blocked: a WhatsApp request is never a decline
        asks_wa = "wants_whatsapp" in tier1
        if _NEG_WORD.search(detect_text) or _NEG_WORD.search(text):
            if (_WHATSAPP.search(last_q) or _WHATSAPP.search(detect_text)) and not asks_wa:
                self.declined_offers.add("whatsapp")
            if _PITCH.search(last_q):
                self.declined_offers.add("meeting")
        ls = detect_language_switch(detect_text, self.s["language"], stt_lang, self.prev_seller_lang)
        words = len(detect_text.split())
        risk = hangup_model.risk(hangup_model.turn_features(words, dur, None, len(self.history), self.short_count,
                                                            self.last_bot_words, self.prev_seller_words, detect_text))
        # E2: a seller who cuts the opening off is rushed -- the strongest early sign of a lost call
        cut_opening = self.barged_in and self.turn == 1
        if (risk >= hangup_model.threshold() or cut_opening) and not hits:
            tier1.append("hangup_risk")
        self._expire_and_revert(tier1)
        # language first: "Telugu lo matladandi... malli call cheyakandi" ended on do-not-call before the
        # switch was applied, and the goodbye was spoken in Hindi
        if ls:
            tier1.append("language_switch")
            self.handle("language_switch", ls.detector, text, ls.matched_phrase, ls.target_language)
        if asks_wa and "do_not_call" in tier1:
            # "send it on WhatsApp, no more calls": honour both -- send the details (INFO_SENT) and record
            # the no-calls preference, instead of DO_NOT_CALL silently dropping the WhatsApp request
            self.dnc_requested = True
            hits = [h for h in hits if h.signal != "do_not_call"]
        mode_used = False
        for h in hits:
            if self._settled():
                break
            entries = self.handle(h.signal, "regex", text, h.matched_phrase, mode_allowed=not mode_used)
            mode_used = mode_used or any(e.kind == "persona" for e in entries)
        if "hangup_risk" in tier1 and not self._settled():
            self.handle("hangup_risk", "barge_in" if cut_opening else "model", text,
                        "seller interrupted the opening" if cut_opening else f"risk {risk:.2f} >= {hangup_model.threshold()}",
                        mode_allowed=not mode_used)
        self.turn_tier1 = set(tier1)
        if not self._settled():
            self._check_facts(text, detect_text, tier1)
        lat["tier1"] = int((time.time() - t) * 1000)

        fixed = self._fixed_reply(text, detect_text, tier1)
        if fixed is not None:
            self.history.append({"speaker": "seller", "text": text})
            return self._finish(text, detect_text, stt_lang, tier1, [], fixed, risk, words, lat, n_switch)
        # the respectful-exit goal asked its one light question: this answer closes the call
        exit_due_now = self._exit_due()
        # tier 2 + reply
        if not self._settled():
            t = time.time()
            self.current_seller = text or "(silence)"
            self.turn_tier1 = set(tier1)
            data = self._llm(text or "(silence)", tier1)
            self.current_seller = None
            lat["llm"] = int((time.time() - t) * 1000)
        else:
            data = {"seller_signals": [], "seller_insights": {}, "understanding_answered": False, "refused_with_reason": False,
                    "slot": "", "reply": "", "question_type": "none", "call_outcome": self.outcome, "end_call": True,
                    "seller_language": self.s["language"], "signal_reason": "terminal signal handled by tier 1"}
        self.history.append({"speaker": "seller", "text": text or "(silence)"})
        tier2 = []
        for sg in sorted(data.get("seller_signals", []), key=lambda x: SIGNAL_PRIORITY.get(x.get("signal"), 99)):
            sig, conf = sg.get("signal"), sg.get("confidence", "medium")
            if sig in (None, "none", "context") or sig in tier1 or self._settled():
                continue
            if (sig == "ai_bot_suspicion" and not _AI_EVIDENCE.search(detect_text)) or \
                    (sig == "identity_question" and not _IDENTITY_EVIDENCE.search(detect_text)):
                self.guard_corrections.append({"turn": self.turn, "kind": "tier2_rejected", "signal": sig})
                continue
            # "Nahi achha nahi chal raha" answers "how is business?": a bad-business report, not a refusal (the
            # LLM read it as not_interested and the Chennai suite run went to respectful exit on turn 2)
            if sig == "not_interested" and self.turn_facts.get("business_status") in ("bad", "mixed")                     and not _REFUSAL_WORDS.search(detect_text):
                self.guard_corrections.append({"turn": self.turn, "kind": "tier2_rejected", "signal": sig,
                                               "why": "business report, not a refusal"})
                continue
            # "Just tell me the details now" was read as wants_whatsapp and closed as INFO_SENT; so was
            # "What details on WhatsApp?" -- a question about the details (rules or the LLM's own act label)
            if sig == "wants_whatsapp" and (not _WANTS_WA_EVIDENCE.search(detect_text) or self.seller_act == "question"
                                            or data.get("seller_act") == "question"):
                self.guard_corrections.append({"turn": self.turn, "kind": "tier2_rejected", "signal": sig})
                continue
            # the LLM may not switch language on a line the words say otherwise, or on a short line (same rule as
            # tier 1: "Kaun si details?" flipped the Chennai call to English)
            if sig == "language_switch":
                sl = data.get("seller_language")
                g = guess_language(detect_text, stt_lang)
                if sl != "other" and (g != sl and (g is not None or words < SHORT_TURN)) \
                        and not any(p.search(detect_text) for _, p in EXPLICIT_LANG_REQUEST):
                    self.guard_corrections.append({"turn": self.turn, "kind": "tier2_rejected", "signal": sig,
                                                   "why": f"words say {g}, {words} words"})
                    continue
            acts = conf == "high" or sig in ACT_ON_MEDIUM or self.pending_medium.get(sig) == self.turn - 1
            if not acts:
                self.pending_medium[sig] = self.turn
                continue
            tier2.append(sig)
            target = None
            if sig == "language_switch":
                sl = data.get("seller_language")
                target = "unsupported" if sl == "other" else sl
            self.handle(sig, "llm", text, data.get("signal_reason", ""), target,
                        refused_with_reason=bool(data.get("refused_with_reason")) and _has_reason(detect_text),
                        mode_allowed=not mode_used)
        # the LLM's refused_with_reason flag only counts when the words carry a reason ("nahi chahiye"
        # alone was flagged as a reason in testing)

        if not self._settled():
            self._after_llm_facts(text, detect_text, data)
        self.s["insights"].update({k: v for k, v in (data.get("seller_insights") or {}).items() if v})
        if data.get("slot"):
            self.slot = data["slot"]
        if self.s["stage"] == "understand" and (data.get("understanding_answered") or
                                                 self.s["counts"]["understanding_question"] >= self.s["limits"]["understanding_question"]):
            self.s["stage"] = "goal_step"
        qt = "clarify" if data.get("clarify_fact") else data.get("question_type")  # a clarification is not a goal ask
        # the LLM labels the contact-preference / right-person ask "contact"; for these goals that IS the
        # goal step (uncounted, the refusal-limit exit never triggered in the scenario suite)
        if qt == "contact" and self.s["goal"] in ("respectful_exit", "data_update", "exec_handoff"):
            qt = "goal_step"
        if qt == "understanding":
            self.s["counts"]["understanding_question"] += 1
        if qt == "goal_step":
            self.s["counts"]["goal_step"] += 1
        if self.s["language"] != "hi-IN" or "Telugu" in data.get("reply", "") or "తెలుగు" in data.get("reply", ""):
            self.s["telugu_offered_done"] = True

        # outcome: engine-forced endings win; otherwise accept the LLM's only if the call supports it
        reply = data.get("reply", "")
        proposed = data.get("call_outcome", "IN_PROGRESS")
        # a time given in the goal step closes the slot even if the LLM kept talking (Chennai demo: "Call
        # back tomorrow at 10 AM. Thank you." got another question and the call never ended)
        slot_goal = {"meeting": "MEETING_FIXED", "callback": "CALLBACK_SCHEDULED", **SLOT_OUTCOME_BY_GOAL}
        if (proposed in ("IN_PROGRESS", None) and "gives_time" in tier1 and self.s["stage"] == "goal_step"
                and self.s["goal"] in slot_goal and not _NEG_WORD.search(detect_text)):
            proposed = slot_goal[self.s["goal"]]
        # playbook 7: the right person's number closes the contact update even if the LLM asks one more thing
        # (suite run: "unka naam Ramesh hai, number 9876543210" got a question about Ramesh's role)
        if (proposed in ("IN_PROGRESS", None) and self.s["goal"] == "data_update" and re.search(r"\d{6,}", detect_text)
                and not self._settled()):
            proposed = "CONTACT_UPDATED"
        # playbook 13: a time confirms the slot for WHATEVER goal is active (support call, executive call)
        if proposed == "CALLBACK_SCHEDULED" and self.s["goal"] in SLOT_OUTCOME_BY_GOAL:
            proposed = SLOT_OUTCOME_BY_GOAL[self.s["goal"]]
        # playbook 9: at the refusal limit VANI asks the contact preference and then exits
        if (not self._settled() and self.s["goal"] == "respectful_exit" and self.s["counts"]["goal_step"] >= 1
                and (qt != "goal_step" or exit_due_now) and proposed in ("IN_PROGRESS", None)):
            # (scenario 9: after "nahi ji, kuch nahi" the LLM asked a second contact question, labelled a
            # goal step, and the call never closed)
            proposed = "RESPECTFUL_EXIT"
        # master intent 8: the account-manager offer answered "no" -> close EXEC_HANDOFF
        last_vani_q = _last_question(next((h["text"] for h in reversed(self.history[:-1]) if h["speaker"] == "vani"), ""))
        if (proposed in ("IN_PROGRESS", None) and self.s["goal"] == "exec_handoff" and not self._settled()
                and re.search(r"account manager|doubt", next((h["text"] for h in reversed(self.history[:-1])
                                                             if h["speaker"] == "vani"), ""), re.I)
                and (nothing_more(detect_text) or self.seller_act == "deny")):
            proposed = "EXEC_HANDOFF"
        # master intent 10/14: a day or part of day without an hour ("kal shaam") -> ask the hour, do not close
        if (proposed in ("CALLBACK_SCHEDULED", "HUMAN_HANDOFF", "COMPLAINT_LOGGED") and "gives_time" in tier1
                and slots.parse(detect_text) is None and not self._settled()):
            when = " ".join(w for w in re.findall(r"\b(kal|parso|aaj|subah|dopahar|shaam|sham|tomorrow|morning|afternoon|evening)\b",
                                                  detect_text, re.I))
            hi_when = {"kal": "कल", "parso": "परसों", "aaj": "आज", "subah": "सुबह", "dopahar": "दोपहर", "shaam": "शाम",
                       "sham": "शाम"}
            lang = "en-IN" if self.s["language"] == "en-IN" else "hi-IN"
            w = " ".join(hi_when.get(x.lower(), x) for x in when.split()) if lang == "hi-IN" else when
            reply, proposed = ASK_HOUR[lang].format(when=f"{w} " if w else ""), "IN_PROGRESS"
        # "milkar ya online?" answered: the pending meeting can be fixed now
        if (not self._settled() and self.meeting_pending and slots.FORMAT.search(detect_text)
                and proposed in ("IN_PROGRESS", None) and not _NEG_WORD.search(detect_text)):
            proposed = "MEETING_FIXED"
        # IndiaMART, 10 Oct 2026: told the window once, the seller still wants hours outside it ("nahi, raat 8 baje
        # hi", "subah jaldi hi free hota hoon") -> the timings are fixed; the details go on WhatsApp, and the call closes
        if not self._settled() and self.window_told and self.seller_act != "question" and self._insists_outside(detect_text):
            self._end("INFO_SENT", "gives_time", "engine", text,
                      "Seller insists on hours outside 9 AM-6 PM: timings are fixed, details on WhatsApp.")
            self.closing_override = self._gendered(slots.FIXED_HOURS_CLOSE.get(self.s["language"], slots.FIXED_HOURS_CLOSE["en-IN"]))
            proposed = "INFO_SENT"
        # the seller chose one of VANI's two slots: the gate takes it (and asks in person / online), whatever the
        # LLM proposed -- the bot decides the slot from the seller's words, not the LLM's slot field
        if (not self._settled() and proposed in ("IN_PROGRESS", None) and self._meeting_capable()
                and self.seller_act != "question" and not _NEG_WORD.search(detect_text)):
            last_vani = next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), "")
            offered = _offered_slots(last_vani)
            # a bare yes only: "haan enquiry to aa rahi hai" (a contradiction opening with haan) is not a yes
            yes = ((self.seller_act == "affirm" or _agrees(detect_text)) and not self.pending_clarify
                   and not rule_facts(detect_text, True) and len(detect_text.split()) <= 5)
            if slots.chosen(offered, detect_text) or (yes and (offered or self.meeting_pending)):
                proposed = "MEETING_FIXED"
        if not self._settled() and proposed == "MEETING_FIXED":
            gate = self._meeting_gate(detect_text, data)
            if gate:
                reply, proposed = gate, "IN_PROGRESS"
                data["question_type"] = "goal_step"
        if not self._settled() and proposed not in ("IN_PROGRESS", None):
            if self._outcome_supported(proposed, data):
                self._end(proposed, "llm_outcome", "llm", text, f"LLM proposed {proposed}; supported by what the seller said.")
            else:
                self.guard_corrections.append({"turn": self.turn, "kind": "outcome_rejected", "proposed": proposed})
        # goal ask limit -> next fallback goal, else respectful exit
        if not self._settled() and self.s["counts"]["goal_step"] >= self.s["limits"]["goal_step"] and qt != "goal_step":
            nxt = next((g for g in self.s["fallbacks"] if g not in self.goal_history), None)
            if nxt:
                self._apply_goal(nxt, "goal_ask_limit", "engine", text, "goal ask limit reached", force=True)
            elif self.s["goal"] != "respectful_exit":
                self._apply_goal("respectful_exit", "goal_ask_limit", "engine", text, "no fallback left", force=True)
        if self._settled():
            # only a very short acknowledgement ("Ji, noted.") may precede the closing; a longer one restated
            # the slot and the closing said it again in the demo
            first = next((x.strip() for x in re.split(r"(?<=[.?!।])\s*", drop_ji(reply)) if x.strip()), "")
            closing = self.closing_line()
            short = first and len(first.split()) <= 4 and not first.endswith("?")
            if short and _similar(first.rstrip(".।!"), closing[:len(first)].rstrip(".।!,")) >= 0.8:
                short = False   # "ठीक है जी। ठीक है जी, हम..." -- the closing already starts with it
            reply = f"{first} {closing}" if short else closing
        elif data.get("end_call"):
            self.guard_corrections.append({"turn": self.turn, "kind": "premature_close", "action": "kept_call_open"})

        if self.s["goal"] == "complaint_recovery" and _TIME_ASK.search(_last_question(reply)):
            self.support_time_asked = True
        return self._finish(text, detect_text, stt_lang, tier1, tier2, reply, risk, words, lat, n_switch)

    def _fixed_reply(self, text, detect_text, tier1) -> Optional[str]:
        """Master-prompt replies said word for word (no LLM): the first reply after the greeting, the two-option
        refusal question, the WhatsApp push, the buy-lead self-service line, and closing on the answer to the
        two-option question."""
        if self._settled():
            return self.closing_line() if self.ended else None
        lang = self.s["language"] if self.s["language"] in ("hi-IN", "en-IN") else "en-IN"
        t1 = set(tier1)
        plain = not (t1 - {"interest", "context", "hangup_risk"}) and self.seller_act not in ("question", "request")
        plan = self.persona["conversation_plan"]
        # turn 1: the seller answered the greeting ("haan ji") -> the context and ONE light question (master 3.2)
        # (a longer answer -- "nahi achha nahi chal raha" -- goes to the LLM, which starts from the same reason but
        # acknowledges what the seller said first)
        last_vani_text = next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), "")
        if (self._greeting_pending() and plain and plan.get("first_reply")
                and (self.seller_act == "affirm" or len(text.split()) <= 4)
                and last_vani_text in (plan["opening"]["value"], *SILENCE_LINE.values())
                and self.s["language"] == self.persona["language"]["primary"]["value"]):
            self.s["counts"]["understanding_question"] += 1
            if self.s["goal"] == "respectful_exit":
                self.s["counts"]["goal_step"] += 1  # 7+ calls: one light question, then close
            return plan["first_reply"]
        # the answer to the two-option refusal question: anything but a complaint / interest / question closes
        if (self.reason_q_turn == self.turn - 1 and self.seller_act not in ("question", "request")
                and not (t1 & {"complaint", "interest", "price_query", "buylead_query", "wants_whatsapp", "gives_time",
                               "human_request", "busy", "identity_question", "ai_bot_suspicion", "confusion",
                               "need_few_enquiries", "do_not_call", "frustration"})):
            self._apply_goal("respectful_exit", "not_interested", "engine", text, "answer to the reason question", force=True)
            self._end("RESPECTFUL_EXIT", "not_interested", "engine", text,
                      "Answered the two-option reason question without a complaint or interest: WhatsApp proposal close.")
            return self.closing_line()
        if self.reason_q_due and not (t1 & {"do_not_call", "connectivity", "frustration", "complaint", "ai_bot_suspicion",
                                            "identity_question", "not_right_person", "already_with_executive"}):
            self.reason_q_turn = self.turn
            return TWO_OPTION_Q.get(self.s["language"], TWO_OPTION_Q["en-IN"])
        if "already_with_executive" in t1 and not (t1 - {"already_with_executive", "context", "interest", "hangup_risk"}) \
                and self.s["goal"] == "exec_handoff" and not self.am_offered:
            self.am_offered = True
            self.s["counts"]["goal_step"] += 1
            return self._gendered(f"{AM_ACK[lang]} {GOAL_QUESTION[lang]['exec_handoff']}")
        if (self.s["goal"] == "exec_handoff" and _AM_OFFER.search(last_vani_text) and self.seller_act != "question"
                and not nothing_more(detect_text) and not _NEG_WORD.search(detect_text)
                and (self.seller_act == "affirm" or _agrees(detect_text) or _NEED.search(detect_text))
                and not (t1 & {"do_not_call", "frustration", "complaint", "not_interested", "busy"})):
            self._apply_goal("meeting", "interest", "engine", text, "account-manager offer accepted (master intent 8)", force=True)
            self.s["counts"]["goal_step"] += 1
            return self._gendered(f"{AM_YES[lang]} {GOAL_QUESTION[lang]['meeting']}")
        if self.yield_now:
            self.yield_now = False
            lg = self.s["language"]
            return (YIELD_M.get(lg) if self.s["gender"] == "male" else None) or YIELD.get(lg, YIELD["en-IN"])
        if self.wa_push_now:
            return f"{WA_PUSH[lang]} {GOAL_QUESTION[lang]['meeting']}"
        if "buylead_query" in t1 and not (t1 & BUYLEAD_OUTRANKED):
            return self._buylead_reply()
        return None

    def _transliterate_hindi_runs(self, reply: str, lang: str) -> str:
        """Romanised Hindi -> Devanagari, run by run, leaving the trade words (catalog, executive, charges...) and
        what is already Devanagari as they are (transliterating the whole reply turned "charges" into चार्जेस)."""
        if lang != "hi-IN":
            return client().text.transliterate(input=reply, source_language_code="en-IN",
                                               target_language_code=lang).transliterated_text
        out, run, pending = [], [], []   # pending: (index in out, lead, core, tail)
        fixed_words = {"baje": "बजे", "milkar": "मिलकर", "kal": "कल", "parso": "परसों", "subah": "सुबह", "shaam": "शाम",
                       "dopahar": "दोपहर", "ji": "जी", "aur": "और", "ya": "या", "haan": "हाँ", "nahi": "नहीं",
                       "kya": "क्या", "hai": "है", "hain": "हैं", "theek": "ठीक", "achha": "अच्छा", "bahut": "बहुत"}

        def flush():
            if run:
                chunk = " ".join(run)
                lead = re.match(r"^\W*", chunk).group(0)
                tail = re.search(r"[\W]*$", chunk).group(0)
                core = chunk[len(lead): len(chunk) - len(tail)] if tail else chunk[len(lead):]
                if core and any(w.lower().strip(".,?!") in _HINDI_WORDS or len(core.split()) > 1 for w in core.split()):
                    pending.append((len(out), lead, core, tail))
                out.append(lead + core + tail)
                run.clear()
        for tok in reply.split():
            bare = tok.strip(".,?!।:;—-\"'")
            if bare.lower() in fixed_words:
                flush()
                out.append(tok.replace(bare, fixed_words[bare.lower()]))
                continue
            if not bare or _DEVANAGARI.search(bare) or _TRADE.match(bare) or not re.fullmatch(r"[A-Za-z']+", bare):
                flush()
                out.append(tok)
            else:
                run.append(tok)
        flush()
        if pending:
            cores = [p[2] for p in pending]
            got = client().text.transliterate(input=" | ".join(cores), source_language_code="en-IN",
                                              target_language_code="hi-IN").transliterated_text.split(" | ")
            if len(got) != len(cores):  # the separator did not survive: one call per run, as before
                got = [client().text.transliterate(input=c, source_language_code="en-IN",
                                                   target_language_code="hi-IN").transliterated_text for c in cores]
            for (i, lead, _, tail), core in zip(pending, got):
                out[i] = lead + core.strip() + tail
        text = " ".join(out).replace(" ओर ", " और ")   # "aur" comes back as ओर ("or")
        text = re.sub(r"(?<=[ऀ-ॿ])\.(?=\s|$)", "।", text)
        return text.replace(" ?", "?").replace(" ।", "।")

    @staticmethod
    def _with_intro(line: str, reply: str) -> str:
        """The name line in place of the reply's own nameless self-introduction ("मैं IndiaMART की virtual assistant
        हूँ"), never a second introduction stacked on it."""
        sents = [x for x in re.split(r"(?<=[.?!।])\s*", drop_ji(reply)) if x.strip()]
        if sents and re.match(r"^\s*(मैं|I am|I'm|This is|నేను)\s", sents[0]) and re.search(r"IndiaMART|इंडियामार्ट", sents[0]):
            sents = sents[1:]
        return " ".join([line] + sents)

    def _greeting_pending(self) -> bool:
        """The seller has not said anything yet except this turn (only silences before): the next reply is the
        first reply after the greeting."""
        said = [h for h in self.history if h["speaker"] == "seller" and h["text"] != "(silence)"]
        return not said

    def _gendered(self, text: str) -> str:
        for a, b in GENDER_FIX[self.s["gender"]]:
            text = text.replace(a, b)
        return text

    def _master_record(self, tier1, tier2, reply, n_switch) -> Dict[str, Any]:
        """This turn in the master prompt's section-9 fields (the engine keeps its own schema for the LLM)."""
        new = self.switch_log[n_switch:]
        ps = next((e for e in new if e.kind == "persona"), None)
        gs = next((e for e in new if e.kind == "goal"), None)
        c = self.s["counts"]
        rec = {"reply": reply, "turn_intent": [s.upper() for s in dict.fromkeys(list(tier1) + list(tier2))],
               "persona_mode": self.s["mode"],
               "persona_switch": {"signal": ps.signal.upper(), "seller_words": ps.seller_said,
                                  "change": f"{ps.change_made.get('mode', ['?', '?'])[0]} -> {ps.change_made.get('mode', ['?', '?'])[1]}",
                                  "reason": ps.reason} if ps else None,
               "call_goal": self.s["goal"].upper(),
               "goal_switch": {"from": gs.change_made["goal"][0].upper(), "to": gs.change_made["goal"][1].upper(),
                               "trigger": gs.signal.upper(), "seller_words": gs.seller_said, "reason": gs.reason} if gs else None,
               "seller_insights_added": None,
               "counters": {"goal_ask_count": c["goal_step"], "refusal_count": c["refusals"],
                            "frustration_count": c["frustration"], "connectivity_count": c["connectivity"],
                            "off_topic_count": c["off_topic"]},
               "call_outcome": self.outcome if self.ended else None,
               "seller_disposition": ENDINGS[self.outcome][0] if self.ended and self.outcome in ENDINGS else None,
               "goal_achieved": goal_achieved(self.persona["goal"]["value"], self.outcome) if self.ended and self.outcome in ENDINGS else None}
        return rec

    def _ai_asked(self, data=None) -> bool:
        """The seller asked whether this is a bot / AI / recording (now or earlier in the call)."""
        # only the seller's own words count -- this turn or any earlier one -- never the LLM's label alone
        seller_lines = [h["text"] for h in self.history if h["speaker"] == "seller"] + [self.current_text or ""]
        return any(_AI_EVIDENCE.search(t or "") for t in seller_lines)

    def _buylead_turn(self, data=None) -> bool:
        return bool("buylead_query" in self.turn_tier1
                    or any(sg.get("signal") == "buylead_query" for sg in (data or {}).get("seller_signals", []) or []))

    def _buylead_reply(self) -> str:
        """Deterministic: the seller dashboard, then a light check; the second time, the WhatsApp offer."""
        lang = self.s["language"] if self.s["language"] in BUYLEAD_LINE else "en-IN"
        if self.s["counts"]["buylead"] >= 2 and "whatsapp" not in self.declined_offers:
            return BUYLEAD_SEND_INFO[lang]
        return f"{BUYLEAD_LINE[lang]} {BUYLEAD_LIGHT_CHECK[lang]}"

    def _insists_outside(self, detect_text: str) -> bool:
        """After VANI stated the 9 AM-6 PM window: another time outside it, or a no to the slot offered inside it
        that still asks for other hours. Agreeing to a time inside the window is not insisting."""
        said = slots.parse(detect_text)
        if said is not None:
            return not slots.is_valid_meeting(said)
        if _agrees(detect_text) and not _NEG_WORD.search(detect_text):
            return False
        return bool(_NEG_WORD.search(detect_text) and slots.TIME_INSIST.search(detect_text))

    def _meeting_capable(self) -> bool:
        """A meeting is being set up: VANI's last question offered a meeting slot, or one waits for in person /
        online. A callback question ("kal shaam 6 baje call karoon?") is not a meeting."""
        last_vani = next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), "")
        if self.meeting_pending:
            return True
        meetingish = bool(_MEETING_WORDS.search(last_vani) or slots.FORMAT.search(last_vani)
                          or self.s["goal"] in ("meeting", "nurture") or len(_offered_slots(last_vani)) > 1)
        return (self.s["goal"] in ("meeting", "nurture", "info_whatsapp", "callback") and meetingish
                and bool(_offered_slots(last_vani) or slots.FORMAT.search(_last_question(last_vani))))

    def _seller_chose_slot(self, text: str) -> bool:
        """The seller named a time, or picked / said yes to one VANI offered."""
        if not text:
            return False
        last_vani = next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), "")
        offered = _offered_slots(last_vani)
        t = to_roman(text) if is_devanagari(text) else text
        return bool(slots.parse(t) or slots.chosen(offered, t) or (offered and _agrees(t) and len(t.split()) <= 5))

    def _meeting_gate(self, detect_text, data) -> Optional[str]:
        """A meeting is fixed only on the seller's explicit yes, at the slot THEY chose, inside 9 AM-6 PM on a calendar
        day from tomorrow, and once in person or online is known (master 4.1, 14, 20; IndiaMART 10 Oct 2026).
        Returns the reply to say instead of closing, or None when the meeting can be fixed (self.slot set)."""
        lang = self.s["language"] if self.s["language"] in slots.TWO_SLOTS else "en-IN"
        last_vani = next((h["text"] for h in reversed(self.history) if h["speaker"] == "vani"), "")
        offered = _offered_slots(last_vani)
        said = slots.parse(detect_text)
        fm = slots.FORMAT.search(detect_text)
        agreed = self.seller_act == "affirm" or _agrees(detect_text) or bool(fm)
        if not fm and agreed and not _NEG_WORD.search(detect_text):
            proposed_fm = {m.group(0).lower() for m in slots.FORMAT.finditer(_last_question(last_vani))}
            if len(proposed_fm) == 1 or (proposed_fm and all("online" in x or "ऑनलाइन" in x for x in proposed_fm)):
                fm = next(slots.FORMAT.finditer(_last_question(last_vani)))   # one format proposed: the yes takes it
        picked = slots.chosen(offered, detect_text) if offered and self.seller_act != "question" \
            and not _NEG_WORD.search(detect_text) else None
        if picked and not (said and said.hour != picked.hour):
            s = picked                                                 # "parso wala theek hai": that option
        elif said:
            s = said                                                   # the seller named the time
        elif self.meeting_pending and (fm or agreed):
            s = self.meeting_pending                                   # the slot already confirmed, now the format
        elif offered and agreed:
            s = slots.pick(offered, detect_text)                       # yes to VANI's options: the one they chose
        else:
            self.guard_corrections.append({"turn": self.turn, "kind": "meeting_not_confirmed"})
            return GOAL_QUESTION[lang]["meeting"]                      # never fix a slot the seller did not confirm
        if not slots.is_valid_meeting(s):
            self.meeting_pending = None
            self.window_told = True
            self.guard_corrections.append({"turn": self.turn, "kind": "meeting_out_of_window"})
            return slots.OUT_OF_WINDOW[lang].format(slot=slots.fmt(slots.nearest_valid(s), lang))
        if not fm:
            self.meeting_pending = s
            return slots.ASK_FORMAT[lang].format(slot=slots.fmt(s, lang))
        online = bool(re.search(r"online|video|zoom|meet|ऑनलाइन", fm.group(0), re.I))
        how = ("online" if online else ("मिलकर" if lang == "hi-IN" else "in person"))
        self.slot, self.meeting_format = slots.fmt(s, lang), how
        self.meeting_at = slots.when(s).isoformat(timespec="minutes")
        self.meeting_pending, self.meeting_ready = None, True
        return None

    def _value_line(self) -> str:
        return self.persona["conversation_plan"].get("value_line") or ""

    def _value_repeat_ok(self, sentence) -> bool:
        """On a venting turn the value line may be said once more (spec: after two venting turns, the value line
        again, then the lightest close); the repeat-sentence guard otherwise removed it."""
        # answering "kaun bol raha hai?" right after the intro: the short name line is said again (master intent 6)
        if self.s["mode"] == "TRANSPARENT" and re.search(BOT_NAME[self.s["gender"]] + r"|पायल|रोहन", sentence):
            return True
        if not self.venting_now or not self._value_line():
            return False
        parts = [p for p in re.split(r"(?<=[.?!।—;])\s*", self._value_line_in(self.s["language"])) if p.strip()]
        return any(_similar(sentence, p) >= 0.5 for p in parts)

    def _value_line_in(self, lang) -> str:
        """The value line in the call's CURRENT language (it is written in the seller's starting language)."""
        line, primary = self._value_line(), self.persona["language"]["primary"]["value"]
        if lang == primary or not line:
            return line
        try:
            return client().text.translate(input=line, source_language_code=primary,
                                           target_language_code=lang).translated_text
        except Exception:
            return line

    def _silent_turn(self, stt_lang, lat, n_switch) -> TurnResult:
        """Nothing heard (silence, or speech too unclear to transcribe): "couldn't hear you properly, were you saying
        something?" (IndiaMART, 10 Oct 2026). A second one is the second audio failure (CALL_BACK_LATER)."""
        self.turn_tier1 = {"connectivity"}
        self.handle("connectivity", "silence", "(silence)", "no speech heard")
        self.history.append({"speaker": "seller", "text": "(silence)"})
        if self.ended:
            reply = self.closing_line()
        else:
            reply = SILENCE_LINE.get(self.s["language"], SILENCE_LINE["en-IN"])
        return self._finish("", "", stt_lang, ["connectivity"], [], reply, 0.0, 0, lat, n_switch)

    def _clarify_log(self, signal, detector, said, c, change, reason):
        trigger = f"turn {c.earlier.turn}: \"{c.earlier.words}\" -> now: \"{c.now_words}\"" if c else ""
        return self._log("clarify", signal, detector, said, trigger, change, reason)

    def _check_facts(self, text, detect_text, tier1):
        """Rules, before the LLM: record what the seller said about themselves, then decide whether a
        contradiction is sarcasm (back off) or a real change (clarify once)."""
        self.pending_clarify, self.sarcasm_turn = None, False
        vani = [h["text"] for h in self.history if h["speaker"] == "vani"]
        # about the business: VANI asked about it, or the seller is still on it ("Bilkul kharab chal raha hai" right
        # after "achha nahi chal raha", although VANI's last question was a WhatsApp offer)
        prev = self.ledger.latest("business_status")
        about_business = (self.s["stage"] == "understand" or bool(_BUSINESS_Q.search(_last_question(vani[-1]) if vani else ""))
                          or bool(prev and self.turn - prev.turn <= 2))
        self.turn_facts = rule_facts(detect_text, about_business)
        if not self.turn_facts:
            return
        cons = self.ledger.contradictions(self.turn_facts, self.turn, text)
        self.ledger.add(self.turn_facts, self.turn, text, "rules")
        if "business_status" in self.turn_facts and self.s["stage"] == "understand":
            self.s["stage"] = "goal_step"  # the understanding question is answered: never ask it again
        if not cons:
            return
        c = cons[0]
        cues = sarcasm_cues(detect_text)
        recent_pitch = any(_PITCH.search(v) for v in vani[-2:])
        positive_flip = c.earlier.value in ("bad", "low", "no")
        if positive_flip and c.strong_earlier and recent_pitch and cues:
            self.sarcasm_turn = True
            self.fired["sarcasm"] += 1
            self._clarify_log("sarcasm", "rules", text, c, {c.fact: [c.earlier.value, f"{c.now_value} (sarcastic)"]},
                              f"Exaggerated flip right after a pitch ({', '.join(cues)}): read as sarcasm, not taken "
                              f"literally. Back off: apologise once, offer WhatsApp details or a later call.")
            self._apply_mode("CALM_EMPATHETIC", "sarcasm", "rules", text, ", ".join(cues))
            if self.s["goal"] not in PROTECTED_GOALS:
                self._apply_goal(GOAL_SWITCHES["frustration"][0], "sarcasm", "rules", text, ", ".join(cues), force=True)
            return
        if self._clarify_allowed(c.fact, found=True):
            self.pending_clarify = c
        else:
            self.guard_corrections.append({"turn": self.turn, "kind": "clarify_skipped", "fact": c.fact})

    def _after_llm_facts(self, text, detect_text, data):
        """The LLM's facts fill what the rules missed; its sarcasm reading counts toward the frustration limit
        only when the rules agree (or alone at high confidence: then it changes the persona, not the count)."""
        llm = {k: v for k, v in self._llm_facts(data).items() if k not in self.turn_facts}
        self.ledger.add(llm, self.turn, text, "llm")
        if ("business_status" in llm or data.get("understanding_answered")) and self.s["stage"] == "understand":
            self.s["stage"] = "goal_step"
        sarcasm = data.get("sarcasm") if data.get("sarcasm") in ("possible", "clear") else None
        # one turn is one frustration: the LLM's own frustration signal on the sarcastic line already counted it
        # (suite run: counted twice and the FIRST cue ended the call as ESCALATED_EXIT)
        if sarcasm and self.sarcasm_turn and not self._settled() and "frustration" not in self.turn_handled:
            self.handle("frustration", "rules+llm", text, data.get("signal_reason") or "sarcasm", mode_allowed=False)
        elif sarcasm == "clear" and not self.sarcasm_turn and not self._settled():
            self.fired["sarcasm"] += 1
            self._clarify_log("sarcasm", "llm", text, None, {"sarcasm": [False, True]}, data.get("signal_reason") or "LLM: sarcasm")
            self._apply_mode("CALM_EMPATHETIC", "sarcasm", "llm", text, data.get("signal_reason") or "")
        # a clarifying question asked this turn
        fact = data.get("clarify_fact")
        if fact and fact not in self.clarified:
            c = self.pending_clarify if (self.pending_clarify and self.pending_clarify.fact == fact) else \
                self.ledger.contradiction(fact, self._llm_facts(data).get(fact, ""), self.turn, text)
            self.clarified[fact] = self.turn
            self.awaiting_clarify = (fact, c, self.turn)
            self._clarify_log("contradiction", "rules" if c is self.pending_clarify else "llm", text, c,
                              {fact: [c.earlier.value if c else "?", c.now_value if c else "?"]},
                              f"Contradiction: one gentle clarifying question (not a goal ask). Asked: "
                              f"\"{_last_question(data.get('reply', ''))}\"")
            data["question_type"] = "clarify"
        elif self.awaiting_clarify and self.awaiting_clarify[2] < self.turn:
            self._resolve_clarify(text, detect_text, data)

    def _resolve_clarify(self, text, detect_text, data):
        """The answer to the clarifying question: enquiries-but-no-orders -> the executive helps with conversion
        (need_few_enquiries goal); a genuinely good business -> keep the goal; anything else is logged."""
        fact, c, asked = self.awaiting_clarify
        self.awaiting_clarify = None
        resolved = {**self._llm_facts(data), **self.turn_facts}
        value = resolved.get(fact)
        converts_not = bool(_CONVERTS_NOT.search(detect_text)) or (
            fact == "business_status" and c is not None and c.now_value == "enquiries coming in"
            and dialogue_act(detect_text) == "affirm")
        if converts_not:
            value = "enquiries but no orders"
            self.ledger.add({"business_status": "mixed", "enquiry_level": "high"}, self.turn, text, "clarified")
            if self.s["goal"] not in PROTECTED_GOALS:
                self._apply_goal(GOAL_SWITCHES["need_few_enquiries"][0], "need_few_enquiries", "clarify", text,
                                 "enquiries come but do not convert")
        self._clarify_log("clarify_resolved", "rules+llm", text, c, {fact: [c.now_value if c else "?", value or "unclear"]},
                          f"Answer to the clarifying question from turn {asked}.")

    def _finish(self, text, detect_text, stt_lang, tier1, tier2, reply, risk, words, lat, n_switch) -> TurnResult:
        reply = drop_ji(reply)   # never "ji" (IndiaMART, 10 Oct 2026), whatever wrote the line
        self.master_turns.append(self._master_record(tier1, tier2, reply, n_switch))
        t = time.time()
        audio_out = self._speak(reply)
        lat["tts"] = int((time.time() - t) * 1000)
        self.history.append({"speaker": "vani", "text": reply})
        self.prev_seller_lang = guess_language(detect_text, stt_lang)
        self.prev_seller_words, self.last_bot_words = words, len(reply.split())
        self.short_count += words <= 2
        new = [asdict(e) for e in self.switch_log[n_switch:]]
        return TurnResult(self.turn, text, stt_lang, tier1, tier2, new, reply, self.outcome, self.ended, self.delivery(),
                          round(risk, 3), audio_out, lat)

    def summary(self) -> Dict[str, Any]:
        return {
            "seller_id": self.persona["seller_id"], "seller_type": self.persona["seller_type_label"],
            "primary_goal": self.persona["goal"]["value"], "goal_history": self.goal_history,
            "final_outcome": self.outcome,
            "do_not_call": self.outcome == "DO_NOT_CALL" or self.dnc_requested,
            "seller_disposition": ENDINGS[self.outcome][0] if self.outcome in ENDINGS else None,
            "goal_achieved": goal_achieved(self.persona["goal"]["value"], self.outcome) if self.outcome in ENDINGS else "no",
            "slot": self.slot, "seller_insights": self.s["insights"], "turns": self.turn,
            "meeting": ({"at": self.meeting_at, "format": "online" if self.meeting_format == "online" else "in_person",
                         "slot_words": self.slot} if self.outcome == "MEETING_FIXED" and self.meeting_at else None),
            "final_delivery": self.delivery(), "switch_log": [asdict(e) for e in self.switch_log],
            "guard_corrections": self.guard_corrections, "transcript": self.history,
            "facts": self.ledger.as_dict(),
            # the master prompt's section-9 view of the call: pre_call + one record per turn
            "pre_call": {"seller_type": self.persona["seller_type_label"], "persona": self.persona["conversation_plan"]
                         .get("seller_context", {}).get("persona"), "call_goal": self.persona["goal"]["value"].upper(),
                         "fallbacks": [g.upper() for g in self.persona["fallback_goals"]], "reason": self.persona["goal"]["reason"]},
            "master_turns": self.master_turns,
        }

"""What KIND of thing the seller just said: the dialogue act behind the words.

Signals (signal_detector.py) say WHAT the seller is talking about; the act says
whether they are ASKING about it, ASKING FOR it, or simply saying no/yes/bye.
The two are different: "What details on WhatsApp?" mentions WhatsApp details
but is a question about them, not a request to send them -- the regex read it
as wants_whatsapp and VANI closed the call as INFO_SENT (Chennai demo).

Acts:
  question  asks for information ("What details?", "kya bhejoge?", "ఏమిటి?")
  request   asks VANI to do something, including polite questions
            ("send it on WhatsApp", "Can you send the details?", "bhej dijiye")
  deny      a no / nothing more ("no", "nahi", "kuch nahi", "ledu", "that's all")
  closing   thanks / goodbye with nothing else ("ok thank you", "bye", "dhanyavaad")
  affirm    a bare yes ("haan ji", "okay", "sure", "sare")
  statement anything else (information about their business, opinions)

Deterministic and sub-millisecond, so it runs in tier 1 BEFORE any terminal
signal can close the call. The LLM also labels the act (seller_act in the
output schema); the engine uses this one for decisions taken before the LLM runs.
Input is Roman (Saaras translit) or Devanagari/Telugu script.
"""
import re

_WH_EN = r"what|which|who|whom|whose|why|how|when|where"
_AUX_EN = r"is|are|am|was|were|do|does|did|can|could|will|would|should|shall|may|have|has|had"
# Hindi question words; "kya" alone is handled separately (it is also the yes/no particle)
_WH_HI = (r"kaun|kaunsa|kaunsi|kaun\s*si|kaunse|kaise|kaisa|kaisi|kyun|kyon|kyu|kab|kahan|kahaan|kidhar|kitna|kitni|"
          r"kitne|kis|kisko|kiska|kiski|kiske")
_WH_TE = r"emiti|enti|endi|emi|evaru|ela|elaa|enduku|eppudu|ekkada|entha|enta|edi|ye|ae"
_WH_SCRIPT = re.compile(r"क्या|कौन|कैसे|कैसा|क्यों|कब|कहाँ|कहां|कितना|कितनी|कितने|किस|"
                        r"ఏమిటి|ఏంటి|ఎవరు|ఎలా|ఎందుకు|ఎప్పుడు|ఎక్కడ|ఎంత|ఏది")

_STARTS_WH = re.compile(rf"^(ok(ay)?|achha|accha|acha|haan|ha|ji|but|par|lekin|so|and|sorry|hello|madam|sir|ma'?am)?[\s,]*"
                        rf"({_WH_EN})\b", re.I)
_STARTS_AUX = re.compile(rf"^(ok(ay)?|achha|accha|acha|but|so|and|sorry|hello)?[\s,]*({_AUX_EN})\s+(i|you|we|it|this|that|there|they|he|she|your|my)\b", re.I)
_WH_ANY = re.compile(rf"\b({_WH_HI}|{_WH_TE})\b", re.I)
# "kya" + verb = "what (will you) send": a content question; "kya aap ..." = yes/no particle
_KYA_WHAT = re.compile(r"\bkya\s+(bhej|send|share|dikha|bata|milega|milegi|hai|hain|details|cheez|chiz|info)", re.I)
_KYA_YN = re.compile(r"\bkya\s+(aap|ap|tum|main|mai|hum|ye|yeh|woh|wo|isme|ismein|iska)\b", re.I)
_KYA_END = re.compile(r"\bkya\s*\??\s*$", re.I)            # "... milega kya?" / "matlab kya?"
_TE_YN_END = re.compile(r"\w+(aa|a|ana|ena)\s*\?\s*$", re.I)  # Telugu "pampistara?" / "kavala?" (needs the "?")

# doing something for the seller: send / share / call / arrange
_ACTION = re.compile(r"\b(send|sent|share|forward|whats\s*app\s*(kar|me|pe|par|on)|mail|bhej\w*|daal\w*|dikha\w*|"
                     r"pampu\w*|pampinch\w*|pampandi|call\s*(me|back|karo|kariye|kijiye)|arrange|schedule|fix|book|"
                     r"rakh\s*(do|dijiye|lo)|kar\s*(do|dijiye|dena|denge|doge))", re.I)
_IMPERATIVE = re.compile(r"\b(send|share|forward|please|pls|plz|kindly|bhej\s*(do|dijiye|dena|diijiye)|bhejiye|bhejo|"
                         r"bhejna|daal\s*do|kar\s*do|kar\s*dijiye|kariye|kijiye|dijiye|pampandi|pampinchandi|cheyandi)\b", re.I)
_MODAL_REQ = re.compile(r"\b(can|could|will|would)\s+you\b|\b(sakte|sakti|sakenge|denge|doge|dogi|bhejoge|bhejenge|"
                        r"karoge|karenge|pampistara|pampagalara|cheyagalara)\b", re.I)
_CONTENT_Q = re.compile(rf"\b(what|which|kya|kaun\s*si|kaunsi|kaunse|kaisi|emiti|enti|edi)\b\s*(\w+\s*){{0,2}}"
                        rf"(details?|info\w*|cheez|chiz|things?|send|bhej\w*|share)", re.I)

_DENY = re.compile(r"^(no+|nope|nah|nahi+|nhi|nahin|na+|naa|ledu|ledhu|vaddu|vaddhu|nothing|kuch\s*nahi|kuchh\s*nahi|"
                   r"koi\s*nahi|bas|that'?s\s*(all|it)|not\s*(now|really|needed|required)|no\s*need|zaroorat\s*nahi|"
                   r"నహీ|नहीं|नही|कुछ\s*नहीं|బస్|లేదు|వద్దు)\b", re.I)
_CLOSING = re.compile(r"\b(thank\s*(you|u)|thanks|thanku|thx|bye|goodbye|good\s*day|dhanyavaad|dhanyawad|shukriya|"
                      r"dhanyavadalu|ధన్యవాదాలు|धन्यवाद|शुक्रिया|have\s*a\s*(nice|good)|chalo|chaliye|rakhta\s*hoon|"
                      r"rakhti\s*hoon|that'?s\s*(all|it)|bas\s*itna\s*(hi)?|bas\s*(ji|itna)|that\s*is\s*all|nothing\s*else|"
                      r"kuch\s*(aur\s*)?nahi|aur\s*kuch\s*nahi|inkem\s*ledu|inka\s*emi\s*ledu|ఇంకేం\s*లేదు)\b", re.I)
_AFFIRM = re.compile(r"^(yes|yeah|yep|yup|ya|ok|okay|sure|haan|haa|ha|han|ji|jee|haanji|haan\s*ji|theek|thik|"
                     r"theek\s*hai|thik\s*hai|bilkul|zaroor|chalega|sare|sari|avunu|ha+n|హా|సరే|అవును|हाँ|हां|जी|ठीक)\b", re.I)
_FILLER = {"ji", "sir", "madam", "maam", "ma'am", "please", "bhai", "andi", "haan", "ok", "okay", "toh", "to", "abhi", "hai",
           "na", "no", "yes", "achha", "acha", "accha", "ha", "thank", "thanks", "you", "ab", "bas", "aur", "kuch", "nahi",
           "nothing", "else", "all", "that's", "thats", "it", "is", "bye", "good", "day", "inka", "inkem", "ledu", "sare",
           "dhanyavaad", "shukriya", "chalo", "theek", "thik", "koi", "baat", "nahin", "fine", "great", "much", "very",
           "so", "the", "for", "now", "need", "not", "required", "thanku", "jee", "sure", "have", "a", "nice"}

ACTS = ("question", "request", "deny", "closing", "affirm", "statement")


def _words(text: str):
    return [w.strip(".,!?।;:") for w in text.lower().split() if w.strip(".,!?।;:")]


def is_question_form(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(t.endswith("?") or _STARTS_WH.search(t) or _STARTS_AUX.search(t) or _WH_ANY.search(t)
                or _WH_SCRIPT.search(t) or _KYA_WHAT.search(t) or _KYA_YN.search(t) or _KYA_END.search(t)
                or _TE_YN_END.search(t))


def dialogue_act(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return "statement"
    words = _words(t)
    only_fillers = all(w in _FILLER for w in words)
    question = is_question_form(t)
    # a content question first: "What details on WhatsApp?" / "kya bhejoge?" ask ABOUT the thing
    if question and (_CONTENT_Q.search(t) or _KYA_WHAT.search(t)) and not _IMPERATIVE.search(t):
        return "question"
    # a polite request is phrased as a question: "Can you send it on WhatsApp?", "bhej sakte ho?"
    if _ACTION.search(t) and (_IMPERATIVE.search(t) or _MODAL_REQ.search(t) or not question):
        return "request"
    if question:
        return "question"
    if _DENY.search(t) and only_fillers:
        return "deny"
    if _CLOSING.search(t) and only_fillers:
        return "closing"
    if _DENY.search(t) and len(words) <= 4:
        return "deny"
    if _AFFIRM.search(t) and only_fillers:
        return "affirm"
    return "statement"


_MORE = re.compile(r"\b(sawaal|sawal|question|ek\s*baat|one\s*more|aur\s*(ek|bhi)|also|doubt|puchna|poochna|"
                   r"jaanna|janna|batao|bataiye|tell\s*me|know|inkoka|inkokati|ఇంకొక)\b", re.I)
_DONE_OK = re.compile(r"^(ok(ay)?|alright|all\s*right|fine|theek\s*hai|thik\s*hai|chalo|sare|సరే)[\s.!,]*(ji|sir|madam|andi)?[\s.!]*$", re.I)


def nothing_more(text: str) -> bool:
    """Answer to "is there anything else?": True when the seller has nothing more ("no", "that's all",
    "nahi ji, thank you", "no I am not interested", a bare "okay"). A question, a request or "nahi, ek
    sawaal hai" keeps the call open; so does a bare "haan" (= yes, there is something)."""
    t = (text or "").strip()
    if not t or _MORE.search(t):
        return False
    act = dialogue_act(t)
    if act in ("deny", "closing"):
        return True
    if act in ("question", "request"):
        return False
    return bool(_DONE_OK.match(t) or _DENY.search(t) or _CLOSING.search(t))


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.argv[1:] or ["What details on WhatsApp?", "Send it on WhatsApp", "Can you send the details on WhatsApp?",
                                 "No, that's all, thank you", "kya bhejoge WhatsApp pe?", "WhatsApp pe details bhej do",
                                 "It is going good.", "No I am not interested."]:
        print(f"{line!r:45} -> {dialogue_act(line)}")

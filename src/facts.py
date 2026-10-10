"""What the seller has said about themselves in THIS call, so a contradiction is noticed instead of the
latest line silently winning.

Chennai live session (3419775_20261009_231212): "Nahi achha nahi chal raha, bilkul achha nahi chal raha" ->
"Bilkul kharab chal raha hai" -> (after a meeting pitch) "Are sab badhiya chal raha hai, itna badhiya
business hai, mujhe inquiries bhi aa rahi hai". VANI answered "यह जानकर अच्छा लगा" and pitched again. The
flip right after a pitch, with "are", "itna badhiya" and "sab ho raha hai", was most likely sarcasm.

  rule_facts(text, about_business)  -> {fact: value} from the seller's words (Roman text)
  FactLedger                        -> every stated value with its turn and words; contradiction()
  sarcasm_cues(text)                -> the exaggeration / opener cues found
  is_strong_negative(text)          -> "bilkul kharab", "bahut kam"...

Facts: business_status good|bad|mixed, enquiry_level high|low, has_executive yes|no,
interest yes|no, is_decision_maker yes|no. A mixed statement ("kaam theek hai par enquiry kam") is never a
contradiction. Interest is tracked but never "contradicted": a seller who warms up after an explanation has
changed their mind, which is the point of the call.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

FACTS = ("business_status", "enquiry_level", "has_executive", "interest", "is_decision_maker")
VALUES = {"business_status": ("good", "bad", "mixed"), "enquiry_level": ("high", "low"), "has_executive": ("yes", "no"),
          "interest": ("yes", "no"), "is_decision_maker": ("yes", "no")}
OPPOSITE = {"good": "bad", "bad": "good", "high": "low", "low": "high", "yes": "no", "no": "yes"}
CONTRADICTION_FACTS = ("business_status", "enquiry_level", "has_executive", "is_decision_maker")
WINDOW_TURNS = 6

_BUSINESS_WORDS = re.compile(r"\b(kaam|kam\s*kaaj|business|dhanda|dhandha|vyapar|sale|sales|order|market|sab)\b", re.I)
_BIZ_BAD = re.compile(
    r"\b(achha|accha|acha|theek|thik|sahi|badhiya|good|well)\s*(se\s*)?(nahi|nhi|nahin)\b|"
    r"\bnahi\s*(achha|accha|acha|theek|thik)\b|\bkharab\b|\bbekar\b|\bbakwas\b|"
    r"\b(kaam|business|dhanda|dhandha|sale|sales|market)\s*(bahut\s*|ekdum\s*|bilkul\s*)?(kam|thanda|slow|manda|mandaa|down|band|weak)\b|"
    r"\bnot\s*(going\s*)?(good|well|great)\b|\b(loss|nuksan|nuksaan|ghata|ghaata)\b|\bbura\s*(haal|chal)", re.I)
_BIZ_GOOD = re.compile(
    r"\b(achha|accha|acha|badhiya|badiya|mast|sahi|zabardast|first\s*class)\s*(hi\s*)?(chal|ja|hai|ho)\b|"
    r"\b(sab|kaam|business|dhanda)\s*(\w+\s*){0,2}(badhiya|achha|accha|mast|theek|thik|sahi)\b|"
    r"\b(going|doing)\s*(very\s*)?(good|great|well|fine)\b|\b(business|work)\s*(is\s*)?(good|great|fine)\b|"
    r"\b(theek|thik)\s*(thak\s*)?chal\s*(raha|rha|rahi)\b", re.I)
_ENQ_LOW = re.compile(r"\b(enquir|inquir|lead)\w*\s*(\w+\s*){0,2}(kam|nahi|nhi|less|low|band)\b|"
                      r"\bkoi\s*(enquiry|inquiry|lead)\s*(bhi\s*)?nahi\b|\bno\s*(enquiries|inquiries|leads)\b|"
                      r"\bfew\s*(enquiries|inquiries|leads)\b", re.I)
_ENQ_HIGH = re.compile(r"\b(enquir|inquir|lead)\w*\s*(bhi\s*|to\s*|toh\s*)?(aa\s*rahi|aa\s*rahe|aati|aate|mil\s*rahi|"
                       r"mil\s*rahe|coming|bahut|kaafi|kafi|lots?)\b|\b(lots|plenty)\s*of\s*(enquiries|inquiries|leads)\b", re.I)
_EXEC_YES = re.compile(r"\bexecutive\s*(\w+\s*){0,3}(pehle\s*se|already|aate|aata|aati|se\s*baat)\b|\balready\s*(in\s*touch|working)\s*with\b", re.I)
_EXEC_NO = re.compile(r"\b(koi\s*)?executive\s*(nahi|nhi)\b|\bno\s*executive\b|\bkabhi\s*koi\s*executive\s*nahi\b", re.I)
_DM_NO = re.compile(r"\b(main|mai|mein)\s*(owner|malik)\s*nahi\b|\b(sir|boss|malik|owner)\s*se\s*baat\b|\bnot\s*the\s*owner\b", re.I)
_DM_YES = re.compile(r"\b(main|mai)\s*(hi\s*)?(owner|malik)\s*(hoon|hu)\b|\bi\s*(am|'m)\s*the\s*owner\b|\b(main|mai)\s*hi\s*dekhta\b", re.I)

_STRONG = re.compile(r"\b(bilkul|bahut|ekdum|bohot|totally|very|really|completely|poora|pura)\b", re.I)
SARCASM_CUES = [
    ("opener", re.compile(r"^\s*(are+|arre+|arey|haan\s*haan|ha\s*ha|wah)\b", re.I)),
    ("exaggeration", re.compile(r"\b(itna|itni|kitna)\s*(badhiya|achha|accha|mast|zabardast|sahi)\b|"
                                r"\bbahut\s*hi\s*(badhiya|achha|accha)\b|\bekdum\s*(first\s*class|mast|badhiya)\b", re.I)),
    ("everything_fine", re.compile(r"\bsab\s*(kuch\s*)?(ho\s*raha|badhiya|mast|perfect|achha)\b|\beverything\s*is\s*(great|perfect|fine)\b", re.I)),
    ("laugh", re.compile(r"\b(ha){2,}\b|\bhehe\b|\blol\b", re.I)),
    ("of_course", re.compile(r"\b(obviously|of\s*course|haan\s*bilkul\s*haan)\b", re.I)),
]


def rule_facts(text: str, about_business: bool = False) -> Dict[str, str]:
    """Facts stated in one seller line. about_business: VANI's last question was about the business, so a
    bare "achha nahi chal raha" counts even without the word "business"."""
    t = text or ""
    out: Dict[str, str] = {}
    if about_business or _BUSINESS_WORDS.search(t):
        # positive words are looked for only outside the negative phrases: "kaam theek nahi" is not "kaam theek"
        bad, good = bool(_BIZ_BAD.search(t)), bool(_BIZ_GOOD.search(_BIZ_BAD.sub(" ", t)))
        if bad and good:
            out["business_status"] = "mixed"
        elif bad:
            out["business_status"] = "bad"
        elif good:
            out["business_status"] = "good"
    if _ENQ_LOW.search(t):
        out["enquiry_level"] = "low"
    elif _ENQ_HIGH.search(t):
        out["enquiry_level"] = "high"
    # "kaam theek hai par enquiry kam" = mixed, not a good business with low enquiries
    if out.get("business_status") == "good" and out.get("enquiry_level") == "low":
        out["business_status"] = "mixed"
    if _EXEC_NO.search(t):
        out["has_executive"] = "no"
    elif _EXEC_YES.search(t):
        out["has_executive"] = "yes"
    if _DM_NO.search(t):
        out["is_decision_maker"] = "no"
    elif _DM_YES.search(t):
        out["is_decision_maker"] = "yes"
    return out


def sarcasm_cues(text: str) -> List[str]:
    return [name for name, p in SARCASM_CUES if p.search(text or "")]


def is_strong_negative(text: str) -> bool:
    return bool(_STRONG.search(text or "")) and bool(_BIZ_BAD.search(text or "") or _ENQ_LOW.search(text or ""))


@dataclass
class Statement:
    turn: int
    value: str
    words: str
    source: str  # rules | llm


@dataclass
class Contradiction:
    fact: str
    earlier: Statement
    now_value: str
    now_words: str
    strong_earlier: bool  # the earlier statement was emphatic ("bilkul kharab") or repeated


@dataclass
class FactLedger:
    entries: Dict[str, List[Statement]] = field(default_factory=dict)

    def latest(self, fact: str) -> Optional[Statement]:
        return (self.entries.get(fact) or [None])[-1]

    def contradiction(self, fact: str, value: str, turn: int, words: str) -> Optional[Contradiction]:
        """The opposite of something said in the last WINDOW_TURNS turns. Mixed never contradicts; neither
        does interest (a change of mind)."""
        if fact not in CONTRADICTION_FACTS or value not in OPPOSITE:
            return None
        recent = [s for s in self.entries.get(fact, []) if turn - s.turn <= WINDOW_TURNS]
        if not recent or recent[-1].value != OPPOSITE[value]:
            return None
        same = [s for s in recent if s.value == recent[-1].value]
        strong = len(same) >= 2 or is_strong_negative(recent[-1].words) or bool(_STRONG.search(recent[-1].words))
        return Contradiction(fact, recent[-1], value, words, strong)

    def contradictions(self, facts: Dict[str, str], turn: int, words: str) -> List[Contradiction]:
        """All contradictions in one seller line, business_status first. Also the cross-fact case: business
        said to be bad, now enquiries said to be coming in ("enquiries yes, orders no" is the likely story)."""
        out = [c for c in (self.contradiction(f, v, turn, words) for f, v in facts.items()) if c]
        if facts.get("enquiry_level") == "high" and not any(c.fact == "business_status" for c in out):
            biz = [s for s in self.entries.get("business_status", []) if turn - s.turn <= WINDOW_TURNS]
            if biz and biz[-1].value == "bad":
                same = [s for s in biz if s.value == "bad"]
                out.append(Contradiction("business_status", biz[-1], "enquiries coming in", words,
                                         len(same) >= 2 or bool(_STRONG.search(biz[-1].words))))
        return sorted(out, key=lambda c: CONTRADICTION_FACTS.index(c.fact))

    def add(self, facts: Dict[str, str], turn: int, words: str, source: str) -> None:
        for fact, value in facts.items():
            if fact in VALUES and value in VALUES[fact]:
                cur = self.latest(fact)
                if cur and cur.turn == turn and cur.value == value:
                    continue
                self.entries.setdefault(fact, []).append(Statement(turn, value, words, source))

    def view(self) -> str:
        """One line per fact for the prompt: the latest value and the seller's words."""
        lines = []
        for fact in FACTS:
            s = self.latest(fact)
            if s:
                hist = " -> ".join(x.value for x in self.entries[fact])
                lines.append(f"- {fact}: {s.value} (turn {s.turn}: \"{s.words[:90]}\"; history {hist})")
        return "\n".join(lines) or "- none yet"

    def as_dict(self) -> Dict[str, List[Dict]]:
        return {f: [vars(s) for s in ss] for f, ss in self.entries.items()}


# one gentle question per fact, offering the likely reconciling explanation instead of "which is true?"
CLARIFY_LINES = {
    ("business_status", "enquiries"): {
        "hi-IN": "पहले आपने बताया था कि काम ठीक नहीं चल रहा, अभी आप कह रहे हैं कि enquiries आ रही हैं — क्या enquiries आ रही हैं पर order नहीं बन रहे?",
        "en-IN": "Earlier you said business is slow, and now that enquiries are coming in. Are the enquiries not turning into orders?"},
    ("business_status", None): {
        "hi-IN": "बस समझना चाहती हूँ — पहले आपने बताया था कि काम {old} चल रहा है, अभी {new}। क्या कुछ products में काम अच्छा है और कुछ में नहीं?",
        "en-IN": "Just to understand: earlier you said business is {old}, and now {new}. Is it going well for some products and not for others?"},
    ("enquiry_level", None): {
        "hi-IN": "पहले आपने बताया था कि enquiries {old} हैं, अभी {new} — क्या enquiries आ रही हैं पर काम की नहीं हैं?",
        "en-IN": "Earlier you said enquiries are {old}, and now {new}. Are enquiries coming in but not the right ones?"},
    ("has_executive", None): {
        "hi-IN": "बस confirm कर लूँ — क्या अभी कोई IndiaMART executive आपके साथ काम कर रहे हैं?",
        "en-IN": "Just to confirm, is an IndiaMART executive working with you right now?"},
    ("is_decision_maker", None): {
        "hi-IN": "बस confirm कर लूँ — क्या business के फ़ैसले आप ही लेते हैं?",
        "en-IN": "Just to confirm, do you take the decisions for the business?"},
}
WORD = {"hi-IN": {"good": "अच्छा", "bad": "ठीक नहीं", "high": "ज़्यादा", "low": "कम", "mixed": "ठीक-ठाक"},
        "en-IN": {"good": "going well", "bad": "slow", "high": "high", "low": "low", "mixed": "mixed"}}


def clarify_line(c: Contradiction, lang: str, now_mentions_enquiries: bool = False) -> str:
    key = ("business_status", "enquiries") if (c.fact == "business_status" and c.earlier.value == "bad"
                                               and now_mentions_enquiries) else (c.fact, None)
    base = "en-IN" if lang not in ("hi-IN", "en-IN") else lang
    w = WORD[base]
    return CLARIFY_LINES[key][base].format(old=w.get(c.earlier.value, c.earlier.value), new=w.get(c.now_value, c.now_value))

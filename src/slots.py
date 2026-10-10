"""Meeting slots: executive meetings only between 9 AM and 6 PM (both included; IndiaMART, 10 Oct 2026, replacing
the master prompt's 11 AM-5 PM), on a calendar day from tomorrow onward, never today. A seller who insists on hours
outside the window is told the timings are fixed and gets the details on WhatsApp; offered as two concrete options; in person or online asked before
the meeting is fixed. Callbacks, support calls and executive phone calls take any time -- this module is ONLY
for meetings.

  parse(text)        -> Slot(day_offset, hour, minute) from Hindi / Hinglish / English / Devanagari, or None
  is_valid_meeting() -> inside the window
  fmt(slot, lang)    -> "कल सुबह 11 बजे" / "tomorrow 11 AM"
"""
import re
from dataclasses import dataclass
from typing import Optional

WINDOW = (9, 18)  # 9:00 .. 18:00 inclusive (IndiaMART, 10 Oct 2026)
NUMBER_WORDS = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
                "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "gyaarah": 11, "barah": 12, "baarah": 12,
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12, "noon": 12,
                "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9,
                "दस": 10, "ग्यारह": 11, "बारह": 12}
_DAY = [(re.compile(r"\b(aaj|today)\b|आज", re.I), 0), (re.compile(r"\b(parso|parson|day\s*after\s*tomorrow)\b|परसों", re.I), 2),
        (re.compile(r"\b(kal|tomorrow)\b|कल", re.I), 1),
        (re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|somvar|mangalvar|budhvar|guruvar|"
                    r"shukravar|shanivar|ravivar)\b|सोमवार|मंगलवार|बुधवार|गुरुवार|शुक्रवार|शनिवार|रविवार", re.I), 3)]
_PERIOD = re.compile(r"\b(subah|morning|am|a\.m\.|dopahar|afternoon|noon|shaam|sham|evening|pm|p\.m\.|raat|night)\b|"
                     r"सुबह|दोपहर|शाम|रात", re.I)
_HOUR = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(?:baje|bje|o'?clock|am|pm|a\.m\.|p\.m\.|बजे)?\b|"
                   r"\b(" + "|".join(k for k in NUMBER_WORDS if k.isascii()) + r")\s*(baje|bje|o'?clock|am|pm)\b|"
                   r"(" + "|".join(k for k in NUMBER_WORDS if not k.isascii()) + r")\s*बजे", re.I)
FORMAT = re.compile(r"\bonline\b|\bvideo\b|\bzoom\b|\bgoogle\s*meet\b|\bmilkar\b|\bmil\s*kar\b|\bin\s*person\b|\boffice\b|"
                    r"\bdukaan\b|\bshop\b|\bvisit\b|\bghar\s*pe\b|\baamne\s*saamne\b|ऑनलाइन|मिलकर|मिल\s*कर|आकर|office", re.I)


@dataclass
class Slot:
    day_offset: Optional[int]   # 0 today, 1 tomorrow, 2 day after, 3 a named weekday (some day ahead)
    hour: int                   # 0..23
    minute: int = 0
    day_word: Optional[str] = None  # the weekday as the seller said it ("Monday", "somvar")


def parse(text: str) -> Optional[Slot]:
    t = text or ""
    m = None
    for cand in _HOUR.finditer(t):
        # a bare number is a time only next to a time word or a period word ("5 baje", "shaam 5"); "15 minute",
        # "2 enquiries" are not times
        if cand.group(1):
            around = t[max(0, cand.start() - 12): cand.end() + 8].lower()
            if not re.search(r"baje|bje|o'?clock|am\b|pm\b|बजे|:\d\d", t[cand.start(): cand.end() + 6], re.I) \
                    and not _PERIOD.search(around):
                continue
        m = cand
        break
    if not m:
        return None
    if m.group(1):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
    else:
        hour, minute = NUMBER_WORDS[(m.group(3) or m.group(5)).lower() if m.group(3) else m.group(5)], 0
    if hour > 23:
        return None
    period = (_PERIOD.search(t) or [None])[0]
    p = (period or "").lower()
    if hour <= 12:
        if p in ("pm", "p.m.", "shaam", "sham", "evening", "raat", "night", "शाम", "रात"):
            hour = hour if hour == 12 else hour + 12
        elif p in ("dopahar", "afternoon", "दोपहर"):
            hour = hour if hour >= 11 else hour + 12
        elif p in ("am", "a.m.", "subah", "morning", "सुबह"):
            hour = 0 if hour == 12 else hour
        elif not p and 1 <= hour <= 7:
            hour += 12  # "kal 4 baje" in business talk is 4 PM
    hit = next(((pat.search(t), d) for pat, d in _DAY if pat.search(t)), (None, None))
    return Slot(hit[1], hour, minute, hit[0].group(0) if hit[1] == 3 else None)


def parse_all(text: str):
    """Every slot offered in one line ("kal subah 11 baje ya parso shaam 4 baje" -> two slots), in order."""
    parts = re.split(r"\s+(?:ya|या|or|లేదా)\s+", text or "")
    found = [parse(p) for p in parts]
    return [s for s in found if s]


_SECOND = re.compile(r"\b(dusra|doosra|dusre|second|baad\s*wala|later\s*one|the\s*other)\b|दूसरा|दूसरे", re.I)


def pick(offered, seller_text: str):
    """The option the seller chose: the one whose day or hour they named, "dusra"/"second" -> the second, else the
    first (a plain yes takes the first option, master intent 20)."""
    t = (seller_text or "").lower()
    if len(offered) > 1 and _SECOND.search(t):
        return offered[1]
    for s in offered:
        h12 = str(s.hour % 12 or 12)
        day_words = {1: ("kal", "कल", "tomorrow"), 2: ("parso", "परसों", "day after")}.get(s.day_offset, ())
        if re.search(rf"\b{h12}\b", t) or any(w in t for w in day_words):
            return s
    return offered[0]


_WEEKDAY = [(re.compile(p, re.I), i) for p, i in [
    (r"\bmon(day)?\b|somvar|सोमवार", 0), (r"\btue(s|sday)?\b|mangalvar|मंगलवार", 1),
    (r"\bwed(nesday)?\b|budhvar|बुधवार", 2), (r"\bthu(rs|rsday)?\b|guruvar|brihaspativar|गुरुवार", 3),
    (r"\bfri(day)?\b|shukravar|शुक्रवार", 4), (r"\bsat(urday)?\b|shanivar|शनिवार", 5),
    (r"\bsun(day)?\b|ravivar|रविवार|इतवार|itvaar", 6)]]


def when(s: Slot, today=None):
    """The meeting's calendar date and time (a named weekday -> its next date after today)."""
    import datetime as dt
    today = today or dt.date.today()
    if s.day_offset == 3 and s.day_word:
        wd = next((i for p, i in _WEEKDAY if p.search(s.day_word)), None)
        ahead = ((wd - today.weekday()) % 7 or 7) if wd is not None else 1
    else:
        ahead = s.day_offset or 1
    d = today + dt.timedelta(days=ahead)
    return dt.datetime(d.year, d.month, d.day, s.hour, s.minute)


_ACCEPT = re.compile(r"\b(wala|wali|waala|theek|thik|sahi|chalega|chalegi|rakh|rakho|rakhiye|kar\s*do|ok|okay|fine|"
                     r"works?|good|done|perfect|haan|ha|ji)\b|वाला|वाली|ठीक|सही|चलेगा|रख", re.I)
_FIRST = re.compile(r"\b(pehla|pahla|pehle\s*wala|first|kal\s*wala)\b|पहला|पहले\s*वाला", re.I)


def chosen(offered, seller_text: str):
    """The option the seller accepted by naming it ("parso wala theek hai", "dusra wala", "4 baje wala", "first one
    works"), else None. A bare yes is not handled here (see pick)."""
    t = seller_text or ""
    if not offered or not _ACCEPT.search(t):
        return None
    if len(offered) > 1 and _SECOND.search(t):
        return offered[1]
    if _FIRST.search(t):
        return offered[0]
    for s in offered:
        h12 = str(s.hour % 12 or 12)
        day_words = {1: (r"\bkal\b", "कल", r"\btomorrow\b"), 2: (r"\bpar(a)?so\b", "परसों", r"\bday\s*after\b")}.get(s.day_offset, ())
        if re.search(rf"\b{h12}\b", t) or any(re.search(w, t, re.I) for w in day_words):
            # "kal" also opens "kal parso dekhte hain" -- one match only counts when the other option is not named
            others = [o for o in offered if o is not s]
            if not any(chosen_names(o, t) for o in others):
                return s
    return None


def chosen_names(s, t) -> bool:
    h12 = str(s.hour % 12 or 12)
    day_words = {1: (r"\bkal\b", "कल", r"\btomorrow\b"), 2: (r"\bpar(a)?so\b", "परसों", r"\bday\s*after\b")}.get(s.day_offset, ())
    return bool(re.search(rf"\b{h12}\b", t) or any(re.search(w, t, re.I) for w in day_words))


def is_valid_meeting(s: Optional[Slot]) -> bool:
    if s is None or s.day_offset == 0:
        return False
    lo, hi = WINDOW
    return lo <= s.hour <= hi and not (s.hour == hi and s.minute > 0)


def nearest_valid(s: Optional[Slot]) -> Slot:
    day = 1 if s is None or not s.day_offset else s.day_offset
    if s is None:
        return Slot(1, 11)
    if s.hour < WINDOW[0]:
        return Slot(day, WINDOW[0], 0, s.day_word)
    if s.hour > WINDOW[1] or (s.hour == WINDOW[1] and s.minute):
        return Slot(day, 12) if s.day_offset == 0 else Slot(day, WINDOW[1], 0, s.day_word)
    return Slot(day, s.hour, s.minute, s.day_word)


_DAY_WORD = {"hi-IN": {1: "कल", 2: "परसों", 3: "उस दिन"}, "en-IN": {1: "tomorrow", 2: "day after tomorrow", 3: "that day"}}


def fmt(s: Slot, lang: str) -> str:
    lang = lang if lang in _DAY_WORD else "en-IN"
    day = s.day_word if s.day_offset == 3 and s.day_word else _DAY_WORD[lang].get(s.day_offset or 1, _DAY_WORD[lang][1])
    h12 = s.hour % 12 or 12
    mins = f":{s.minute:02d}" if s.minute else ""
    if lang == "hi-IN":
        part = "सुबह" if s.hour < 12 else ("दोपहर" if s.hour < 16 else "शाम")
        return f"{day} {part} {h12}{mins} बजे"
    return f"{day} {h12}{mins} {'AM' if s.hour < 12 else ('noon' if s.hour == 12 and not s.minute else 'PM')}".replace(" 12 noon", " 12 noon")


TWO_SLOTS = {"hi-IN": "कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?",
             "en-IN": "Would tomorrow 11 AM or day after tomorrow 4 PM work for you?"}
OUT_OF_WINDOW = {"hi-IN": "माफ़ी चाहूँगी, meeting हम सुबह नौ से शाम छह बजे के बीच ही रख सकते हैं। {slot} ठीक रहेगा?",
                 "en-IN": "Sorry, we can schedule meetings only between 9 AM and 6 PM. Would {slot} work?"}
# the seller insists on hours outside the window (a second time, or refuses the slot offered inside it)
FIXED_HOURS_CLOSE = {
    "hi-IN": "माफ़ी चाहूँगी, हमारी meeting timings सुबह नौ से शाम छह बजे तक fixed हैं। मैं details आपको WhatsApp पर भेज रही हूँ, "
             "जब सुविधा हो इस समय में कोई slot बता दीजिएगा। धन्यवाद, आपका दिन शुभ हो।",
    "en-IN": "Sorry, our meeting timings are fixed between 9 AM and 6 PM. I am sending you the details on WhatsApp; "
             "whenever convenient, tell us a slot within these hours. Thank you, have a good day."}
# "only late", "after 8", "us time hi", "subah jaldi": still asking for hours outside the window
TIME_INSIST = re.compile(r"\b(raat|night|late|der\s*se|baad\s*mein|ke\s*baad|after|pehle|before|jaldi|early|sirf|only|"
                         r"usi|wahi|tabhi|us\s*time|that\s*time|free\s*(hota|hoti|hun|hoon)|nahi\s*ho\s*payega|"
                         r"possible\s*nahi|not\s*possible|can'?t)\b|रात|बाद|पहले|सिर्फ़|सिर्फ", re.I)
ASK_FORMAT = {"hi-IN": "बहुत अच्छा, {slot} — मिलकर या online?", "en-IN": "Great, {slot} — in person or online?"}

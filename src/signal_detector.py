"""Deterministic, fast (sub-millisecond) live signal detection on one seller turn.

This is tier 1. Tier 2 is the context-aware LLM classification that runs
inside the same LLM call that writes VANI's reply (live_engine.py), so
semantic detection adds no extra network round-trip. The engine takes the
union of both tiers plus the STT-reported language.

Input text is Romanized (Saaras `translit` mode returns Roman script directly;
text typed into the demo UI is used as-is). Devanagari is handled by
text_normalize.to_roman() for any other source.

Pattern vocabulary was authored from real transcripts (ps07_call_turns.csv)
and the seller-question categories IndiaMART's own evaluators use (E15), then
hardened against spelling variants found by tests/test_signals.py
(nahi/nhi, chahiye/chaiye, achha/accha/acha).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

SIGNAL_PATTERNS = {
    "hard_refusal": [
        r"\bdo\s*not\s*call\b(?!\s*(now|right\s*now))", r"\bdon'?t\s*call\b(?!\s*(now|right\s*now))",
        r"\b(mat|na)\s*call\s*kar\w*\b", r"(?<!abhi )\bcall\s*(mat|na)\s*kar\w*\b",
        r"\bnumber\s*(block|hata)", r"\b(fir|phir)\s*kabhi\s*(call|phone)\s*mat\b", r"\bremove\s*(us|me|my\s*number)\b",
        r"\bstop\s*call(ing)?\b", r"\bno\s*more\s*calls?\b",r"\bdobara\s*(call|phone)\s*mat\b", r"\bblock\s*kar\s*dunga\b",
        r"\bcall\s*nahi\s*aan[ie]\s*chahiye\b",
        # "abhi call mat karo" = not NOW (busy), not "never again": excluded by the lookbehind
        r"(?<!abhi )\b(call|phone)\s*mat\s*(kijiye|kariye|karna|karo|kro)\b",
        r"\bdobara\s*(call|phone)\s*(mat|na)\b",
        # Telugu (Saaras translit): "malli call cheyoddu" = don't call AGAIN. "malli/inka/eppudu" is required:
        # "ippudu call cheyoddu" (not now) was turned into a do-not-call in the demo
        r"\b(malli|inka|eppudu)\s*(call|phone|fone)\s*(cheyoddu|cheyakandi|cheyyakandi|cheyyoddu|cheyodu)\b",
        # a bare "call cheyakandi" (don't call) is a do-not-call, like Hindi "call mat karo"; only "ippudu"
        # (now) makes it a busy signal (demo: "vaddu, call cheyakandi" closed as a mere RESPECTFUL_EXIT)
        r"(?<!ippudu )\b(call|phone)\s*(cheyoddu|cheyakandi|cheyyakandi|cheyyoddu|cheyodu)\b",
        r"(?<!ఇప్పుడు )\bcall\s*(చేయకండి|చేయొద్దు|చెయ్యొద్దు|చేయవద్దు)",
        r"\bmalli\s*(call|phone)\s*(vaddu|ఒద్దు)\b",
    ],
    "complaint": [
        r"\bcomplaint\b", r"\bshikayat\b", r"\bfraud\b", r"\bdhoka\b", r"\bcheat", r"\brefund\b",
        r"\bpaise?\s*(wapas|vapas|barbaad|doob)", r"\bservice\s*(kharab|bekar|bakwas|bad|worst)",
        r"\bexecutive\s*ne\s*(kuch\s*nahi|dhoka|paise)", r"\bkoi\s*(lead|enquiry|inquiry)\s*nahi\s*(aayi|aati|mili)",
        r"\bpaid\s*(package|service).{0,25}(bekar|waste|bakwas|faltu)", r"\bwaste\s*of\s*money\b",
        # v2, mined from DEV-split misses of IndiaMART's "Problem Complaint" label
        r"\b(enquiry|inquiry|enquiries|inquiries|leads?)\s*(\w+\s*)?(nahi|nhi)\s*(aa|aati|aayi|aate|mil|milti|receive)",
        r"\bkoi\s*(enquiry|inquiry|lead)\s*(bhi\s*)?nahi", r"\b(enquiry|inquiry|lead)\s*(\w+\s*){0,3}(galat|fake|wrong)",
        r"\bfake\b", r"\bprivacy\b", r"\bwrong\s*profile\b", r"\boption\s*nahi\s*(aa|dikh)", r"\baaya\s*hi\s*nahi\b",
        r"\bresponse\s*(\w+\s*)?nahi\s*aat", r"\bpaisa\s*(iktha|ek\s*saath)\b",
    ],
    "connectivity": [
        r"\b(aawaz|awaaz|awaz|aavaz)\s*(nahi|nhi|kat|toot|cut)", r"\bsunai\s*nahi", r"\bvoice\s*(break|cut|nahi)",
        r"\bcan'?t\s*hear\b", r"\bnot\s*audible\b", r"\bnetwork\s*(issue|problem|nahi)", r"^\s*(hello[\s,?.!]*){2,}$",
        r"\bclear\s*(nahi\s*)?sunai",
        r"\b(aawaz|awaaz|awaz|aavaz)\s*aa\s*rahi\s*hai\s*\?", r"\bsun\s*(pa\s*)?rahe\s*ho\s*\?",  # seller checking the line
    ],
    # an explicit "no" to VANI's offer (not a do-not-call request): respect it and close.
    # Caught in the demo: seller said "No callbacks" and VANI asked "Shall we fix a time?"
    "declined": [
        r"\bno\s*call\s*-?\s*backs?\b", r"\bcall\s*-?\s*back\s*(mat|nahi|na|mat\s*karo)\b", r"\bnot\s*interested\b",
        r"\binterest(ed)?\s*nahi\b", r"\bi\s*don'?t\s*want\s*(it|this|any)\b", r"\bmana\s*(hai|kar)\b",
        r"\bkoi\s*zaroorat\s*nahi\b", r"\bvaddu\s*andi\b", r"\bavasaram\s*ledu\b",
        r"\b(nahi|nhi)\s*(chahiye|chaiye|chaahiye|thiye)\b", r"\bzaroorat\s*nahi\b", r"\binterest\s*nahi\b",
        # from the recording replay: "Nahi nahi thank you." was missed and the old bot kept pitching
        r"^\W*((nahi|nhi|na|no)\W+){1,3}(ji\W+)?(thank\s*you|thanks|dhanyavaad|shukriya)\b", r"\bno\s*thanks?\b",
        r"\bnahi\s*laayega\b", r"\binterested\s*no[iy]\b",
        r"\b(do\s*not|don'?t)\s*(send|want|need)\b", r"\bno\s*need\b", r"\bnot\s*needed\b", r"\bmat\s*bhej",
        r"\bvaddu(le|andi)?\b", r"\bpampinch?oddu\b", r"\bakkarledu\b",  # Telugu "don't want / don't send / not needed"
        # a bare "nahi" is deliberately NOT here: it means "not now" after "is now a good time?" and
        # must be read against VANI's previous turn (playbook rule 1) -- tier 2 does that
    ],
    "frustration": [
        # "nahi chahiye" / "zaroorat nahi" live under not_interested: they are the playbook's own
        # scenario-9 examples, and sellers in the recordings said them calmly
        r"\bbaar\s*baar\b", r"\bbar\s*bar\b",
        r"\bpareshan\b", r"\bband\s*(kar|karo|kijiye|kro)\b", r"\bmat\s*kar\w*\b", r"\bzabardasti\b", r"\bbas\s*kar\w*\b",
        r"\birritat", r"\bphone\s*(cut|rakh)", r"\bkitni\s*baar\b", r"\bdisturb\b", r"\bdimaag\s*(kharab|mat)",
        r"\bbakwas\b", r"\bfaltu\b", r"\bannoying\b", r"\bfed\s*up\b", r"\bkya\s*tamasha\b",
        r"\bmalli\s*malli\b", r"\bvisugu\b", r"\bkopam\b",  # Telugu: "again and again", "fed up", "angry"
        # v2, mined from DEV-split misses of IndiaMART's "Frustrated User" label: real frustration
        # is mostly rhetorical/argumentative, not explicit ("aap kyun call kare ja rahe ho baar-baar?")
        r"\bkyun?\s*(pareshan|dekh\s*rahe|call\s*kar|phone\s*kar|bol\s*rahe)", r"\bpeeche\s*pad", r"\bkhaamkha\b",
        r"\b(char|chaar|paanch|panch|das)\s*(se\s*\w+\s*)?(-?\s*\w+\s*)?baar\s*(phone|call)", r"\bphir\s*se\s*wahi\b",
        r"\bkya\s*kar\s*loge\b", r"\bjawab\s*do\b", r"\bsun(e|te)\s*nahi\b", r"\bmaine\s*(bola|kaha)\s*na\b",
        r"\bkisne\s*bola\b", r"\bkabhi\s*nahi\s*bola\b", r"\bmaine\s*kab\s*(bola|kaha)\b", r"\bkya\s*itni\s*jaldi\b",
        r"\bhata\s*dijiye\b", r"\bforce\s*na\b",
    ],
    "human_request": [
        r"\binsaan\s*se\s*baat", r"\breal\s*person\b", r"\bhuman\s*se\b", r"\bkisi\s*(aadmi|insaan|banda)\s*se\b",
        r"\bexecutive\s*se\s*baat\s*kara", r"\bmanager\s*se\s*baat", r"\btalk\s*to\s*(a\s*)?(human|person|someone)\b",
    ],
    "ai_bot_suspicion": [
        # bare "machine" fired on "how does it help my machine sell?" from an idli-MACHINE maker;
        # it now needs bot context ("machine se baat", "are you a machine")
        r"\bbot\b", r"\b(ai|a\.i\.)\b", r"\bmachine\s*(se|hai\s*kya|bol|ho\s*kya)\b", r"\b(are\s*you|you\s*are)\s*a\s*machine\b",
        r"\brobot\b", r"\bgenuine\s*person\b", r"\breal\s*insaan\b",
        r"\binsaan\s*(ho|hain|hai)\b", r"\brecorded\b", r"\bautomated\b", r"\bcomputer\s*(se|bol)",
    ],
    "confusion": [
        r"\b(kya\s*)?matlab\b", r"\bsamajh?\s*(nahi|nhi)\b", r"\bsamjha\s*(nahi|nhi)\b", r"\bsamajh\s*nahi\s*aaya\b",
        r"\b(phir|fir|dobara)\s*se\s*bol", r"\bdobara\s*bol", r"\bkya\s*bola\b", r"\bclear\s*nahi\b",
        r"\brepeat\s*(karo|kijiye|please)\b", r"\bwhat\s*do\s*you\s*mean\b", r"\bpardon\b", r"\bdidn'?t\s*(get|understand)\b",
        r"\bkis\s*baare\s*mein\b", r"\bkaun\s*sa\b.{0,15}\?", r"\bnot\s*clear\b",
        # missed in the demo: "Wait, what exactly is this callback for? How will this help my machines sell?"
        r"\bwhat\s*(exactly|is\s*(this|it)\s*(for|about))\b", r"\bhow\s*(will|does|would)\s*(this|it)\s*help\b",
        r"\bi\s*don'?t\s*(understand|follow|get\s*it)\b", r"\bkya\s*(keh|bol)\s*rahe\s*ho\b",
        r"\bard?h?am\s*(kaaledu|kaledu|kale)\b", r"\bmalli\s*cheppandi\b",  # Telugu: "didn't understand", "say again"
        # v2, mined from DEV-split misses: a bare "Kya?" / "Ji?" / "Haanji?" asks VANI to repeat
        r"^\s*(kya|ji|haan\s*ji|haanji|sorry|pardon)\s*\?\s*$", r"\bkis(ki|ke)\s*baat\b", r"\bkaun\s*se\s*product\b",
        r"\bkya\s*bol\s*rahe\b",
    ],
    "deferral": [
        r"\bjab\s*(hoga|time\s*hoga)\b", r"\btab\s*bata", r"\bbaad\s*(mein|me)\b", r"\bsaamne\s*se\s*bata",
        r"\badvance\s*mein\s*nahi\b", r"\babhi\s*nahi\b.{0,20}\b(baad|kal|later)\b", r"\bcall\s*(me\s*)?later\b",
        r"\bkal\s*(call|phone|baat)\s*kar", r"\bnext\s*week\b", r"\bsoch\s*ke\s*bata",
    ],
    "rush": [
        r"\bjaldi\b", r"\bbusy\s*(hoon|hu|hain|hai|hun)\b", r"\btime\s*nahi\s*hai\b", r"\bshort\s*mein\b",
        r"\bmeeting\s*mein\s*hoon\b", r"\bdrive\s*kar\s*raha\b", r"\bquick(ly)?\b", r"\bin\s*a\s*hurry\b",
        r"\b(seedha|sidha)\s*(bolo|boliye|point)", r"\bpoint\s*pe\s*aa", r"\bek\s*minute\s*mein\b", r"\bfast\b",
        r"\bkaam\s*kar\s*raha\s*hoon\b", r"\bgrahak\s*(hai|baithe)", r"\bcustomer\s*(hai|baitha)",
        r"\btvaraga\b", r"\bquick\s*ga\b", r"\btime\s*ledu\b", r"\bin\s*the\s*middle\s*of\b",  # Telugu / English cues
        # from the recording replay: "busy itna hai", "time nahi de payenge", "out of station"
        r"\bbusy\b", r"\btime\s*nahi\b", r"\bout\s*of\s*station\b",
        r"\btime\b.{0,20}\b(paas|pass|pas)\s*nahi\b",  # "utna time hamara paas nahi hai ji"
        r"ఇప్పుడు\s*call\s*(చేయకండి|చేయొద్దు|చెయ్యొద్దు|చేయవద్దు)",  # Telugu script "don't call NOW"
        r"\babhi\s*(call|phone)\s*mat\b", r"\bippudu\s*(call|phone)\s*(cheyoddu|cheyakandi|vaddu)\b", r"\bnot\s*now\b", r"\bbaahar\s*(hoon|hu|gaya)\b", r"\bsoch\s*ke\b.{0,15}\bbata",
    ],
    "price_query": [
        r"\bkitne\s*ka\b", r"\bprice\b", r"\brate\b", r"\bcharges?\b", r"\bkitna\s*(paisa|lagega|kharcha|cost)",
        r"\bcost\b", r"\bfees?\b", r"\bpackage\s*kitne", r"\bpaid\s*hai\s*kya\b", r"\bfree\s*hai\b",
        r"^\W*kitna\W*$", r"\bsubscription\b", r"\b(free\s*or\s*paid|paid\s*or\s*free|am\s*i\s*paying|is\s*it\s*paid)\b",  # bare "Kitna?" from the recordings
        r"\bpayment\b", r"\bentha\s*(avutundi|avuthundi|untundi|kharchu)\b", r"\bdabbulu\b",  # Telugu "how much / money"
    ],
    # Bare go-ahead words ("haan boliye", "bataiye", "achha") are acknowledgements,
    # not interest -- engine testing showed "Haan ji boliye, kaun?" being read as
    # interest. Only cues that show the seller wants MORE count.
    "interest": [
        r"(?<!not )(?<!un)\binterested\b", r"\b(ok|okay|theek\s*hai)\s*,?\s*bhej", r"\bkaise\s*(hoga|karenge|milega|kaam)\b",
        r"\bkab\s*(aayenge|aa\s*sakte|milenge)\b", r"\btell\s*me\s*more\b", r"\bsounds\s*good\b", r"\bkaun\s*si\s*enquir",
        r"\bkitni\s*enquir", r"\bdetail\s*(mein|me)\s*bata", r"\bthat\s*would\s*help\b", r"\bachha\s*idea\b",
        r"\b(haan|ha)\s*,?\s*(zaroor|bilkul)\b", r"\bfayda\s*(hoga|kya)\b", r"\bkya\s*benefit\b", r"\bhow\s*does\s*it\s*work\b",
    ],
    "identity_question": [
        r"\bkaun\s*(bol|hai|ho|baat)\b", r"\bkaun\s*\?", r"\bwho\s*(is\s*)?(this|calling|speaking|are\s*you)\b",
        r"\bmeeru\s*evaru\b", r"\bevaru\s*(matladutunnaru|maatladutunnaru)\b",
        r"\bkahan\s*se\s*(bol|call)", r"\bkis\s*company\s*se\b", r"\bnumber\s*kahan\s*se\s*mila\b",
        r"\bkis\s*liye\s*call\b", r"\bkyun\s*call\s*kiya\b", r"\bwhy\s*(are\s*you|did\s*you)\s*call",
    ],
    # ---- playbook scenarios 7, 8, 12, 13, 15 (scenarios.pdf); phrasings also seen in the 83 recordings ----
    "not_right_person": [
        r"\b(main|mai)\s*owner\s*nahi\b", r"\bowner\s*nahi\s*(hoon|hu|hun)\b", r"\b(sir|malik|boss|owner|seth|sahab|bhaiya)\s*(se|ko)\s*baat\s*(kijiye|karo|kar|karna)",
        r"\b(wrong|galat)\s*number\b", r"\bnot\s*the\s*(owner|right\s*person)\b", r"\bwo\s*(abhi\s*)?(nahi\s*hai|bahar\s*(hai|gaye))\b",
        r"\bmain\s*(staff|worker|employee|naukar)\s*(hoon|hu)\b", r"\bdusre\s*number\s*pe\b", r"\bunka\s*number\b",
    ],
    "already_with_executive": [
        r"\bexecutive\s*(pehle\s*se|already|aate|aaye|aata|aa\s*chuke)", r"\bhamare\s*executive\b", r"\b\w+\s*ji\s*pehle\s*se\s*aate\b",
        r"\b(already|pehle\s*se)\s*(baat|contact|touch)\s*(ho|mein|me)\b", r"\bexecutive\s*(ka|ki)\s*number\s*(hai|mere\s*paas)\b",
        r"\balready\s*(in\s*touch|working)\s*with\b",
    ],
    "wants_whatsapp": [
        r"whats\s*app\s*(pe|par|per|me|mein|on)?\s*(bhej|send|daal|details|kar)", r"\b(details|info|information)\s*(\w+\s*)?whats\s*app",
        r"\bsend\s*(it|details|me)?\s*(on|over)\s*whats\s*app\b", r"\bwhats\s*app\s*kar\s*(do|dijiye)\b",
        r"\bsend\b.{0,25}\b(on|over|via|to)\s*(my\s*)?whats\s*app\b",  # "just send everything on WhatsApp"
    ],
    # buy-lead / buyer-detail questions (IndiaMART, 10 Oct 2026: answer with the seller dashboard, no meeting).
    # "leads nahi aate" is a complaint, not a question about buy leads
    "buylead_query": [
        r"\b(zyada|jyada|more|aur|naye|new)\s*(buy\s*)?leads?\b(?!\s*(nahi|nhi)\b)",
        r"\bbuy\s*leads?\s*(kahan|kaise|kidhar|where|how)", r"\b(kahan|kaise|kidhar|where|how)\s*(\w+\s*){0,3}buy\s*leads?\b",
        r"\bbuyer\s*(ka|ke|ki)?\s*(number|details?|naam|contact|address)", r"\bkaun\s*(se|si|sa)\s*buyers?\b",
        r"\bkahan\s*(ke|se)\s*buyers?\b", r"\bbuyers?\s*(kaun|kahan)\s*(hai|hain|se)", r"\bkitni\s*quantity\b",
        r"\bmujhe\s*(ye|yeh|woh|wo)\s*kaise\s*milega\b", r"\bleads?\s*(kahan|kaise|kidhar)\s*(dekh|mil|milegi|milenge|aayenge)",
        r"\b(see|check|get|find)\s*(the\s*|my\s*|more\s*)?buy\s*leads\b", r"\bwhich\s*buyers\b", r"\bbuyer('s)?\s*(number|details|contact)\b",
    ],
    "gives_time": [
        r"\b\d{1,2}\s*(baje|bje|pm|am|o'?clock)\b", r"\b(ek|do|teen|chaar|char|paanch|panch|chhe|saat|aath|nau|das|gyarah|barah)\s*baje\b",
        r"\b(kal|parso|aaj|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|somvar|mangalvar|budhvar|guruvar|shukravar|shanivar|ravivar)\b"
        r".{0,20}\b(subah|shaam|sham|dopahar|morning|evening|afternoon|baje|\d)",
        r"\b(subah|shaam|sham|dopahar)\s*(ko|mein|me)?\s*\d", r"\bafter\s*\d", r"\b\d{1,2}\s*(ke\s*)?(baad|bad)\b",
        r"\brepu\b.{0,15}\b(udayam|sayantram|\d)", r"\bsaayantram\s*\d",
    ],
    "need_few_enquiries": [
        r"\b(enquir|inquir)\w*\s*(bahut\s*|bilkul\s*)?(kam|thodi|less)\b", r"\b(order|business|kaam|dhanda|sale)\s*(bahut\s*)?(kam|thanda|slow|manda|mandaa)\b",
        r"\bfew\s*(enquiries|inquiries|leads|orders)\b", r"\bnot\s*enough\s*(enquiries|inquiries|leads|business)\b",
        r"\bmarket\s*(down|slow|thanda|kharab)\b",
    ],
}

_COMPILED = {s: [re.compile(p, re.IGNORECASE) for p in ps] for s, ps in SIGNAL_PATTERNS.items()}

# pattern groups -> playbook signal names (scenarios.pdf): "deferral" and "rush" are both
# the playbook's "busy" ("abhi busy hoon", "baad mein"), etc.
ALIASES = {"hard_refusal": "do_not_call", "declined": "not_interested", "rush": "busy", "deferral": "busy"}

from playbook import SIGNAL_PRIORITY  # noqa: E402

PRIORITY = sorted(SIGNAL_PRIORITY, key=SIGNAL_PRIORITY.get)

# signals that switch the persona and/or goal
DELIVERY_SIGNALS = set(SIGNAL_PRIORITY) - {"context"}

# ---- language -------------------------------------------------------------
HINDI_FUNC = set("""si sa wali wala wale mujhe humein hum hai hain tha thi kya nahi nahin main mein aap ka ki ke ko se toh haan ji bhi kar karo raha
rahe rahi hoon ho abhi kal baat theek achha accha woh yeh kaun kyun kab kahan kitna kuch bata bataiye bol
boliye mera meri apna lekin aur jab tab phir wala chahiye dijiye""".split())
ENGLISH_FUNC = set("""the is are was were i you we they it my your our this that what which who why how when
where will would can could should have has had do does did not don't dont please thank thanks sorry already
and of to for with from about at on be been yes no okay right sure because but if so just any am i'm""".split())
TELUGU_CUES = set("""andi nenu meeru miru ledu ledhu cheppandi matladandi matladu kavali kaavali emiti enti
undi unnanu unnaru vaddu avunu sare chala ippudu tarvata telugu lo naaku naku mee""".split())

_TELUGU_SCRIPT = re.compile(r"[ఀ-౿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_OTHER_INDIC = re.compile(r"[஀-௿ಀ-೿ഀ-ൿঀ-৿઀-૿]")

EXPLICIT_LANG_REQUEST = [
    ("en-IN", re.compile(r"\b(english|angrezi|inglish)\s*(mein|me|main|mai|lo)\b|\b(speak|talk)\s*(in\s*)?english\b|\benglish\s*please\b|\bin\s*english\b", re.I)),
    ("te-IN", re.compile(r"\btelugu\s*(lo|mein|me|main|please)\b|\btelugulo\b|\b(speak|talk)\s*(in\s*)?telugu\b|\bin\s*telugu\b", re.I)),
    ("hi-IN", re.compile(r"\bhindi\s*(mein|me|main|mai|lo|please)\b|\b(speak|talk)\s*(in\s*)?hindi\b|\bin\s*hindi\b", re.I)),
    ("unsupported", re.compile(r"\b(tamil|kannada|malayalam|bengali|bangla|marathi|gujarati|odia|punjabi)\s*(mein|me|lo|please|la|il)?\b.{0,20}\b(baat|bolo|speak|talk|pesu|matlad)", re.I)),
]


@dataclass
class SignalHit:
    signal: str
    matched_phrase: str
    detector: str = "regex"
    target_language: Optional[str] = None


def english_share(text: str) -> Optional[float]:
    eng = hin = 0
    for tok in re.findall(r"[a-zA-Z']+", (text or "").lower()):
        if tok in ENGLISH_FUNC:
            eng += 1
        elif tok in HINDI_FUNC:
            hin += 1
    return eng / (eng + hin) if (eng + hin) >= 2 else None


SHORT_TURN = 4  # words; below this Saaras's language label is a guess (one English noun tips it)


def guess_language(text: str, stt_language: Optional[str] = None) -> Optional[str]:
    """Best guess of the language the seller just spoke, or None if too little signal.

    The words decide first; the STT label only breaks a tie. Trusting the label first flipped the Chennai call
    (3419775_20261009_223707) on every turn: "Vani catalog." and "Kaun si details?" were labelled en-IN by
    Saaras and VANI answered in English, then Hindi again on the next line."""
    if stt_language == "te-IN":
        return stt_language
    if _TELUGU_SCRIPT.search(text or ""):
        return "te-IN"
    toks = re.findall(r"[a-zA-Z']+", (text or "").lower())
    if sum(t in TELUGU_CUES for t in toks) >= 2:
        return "te-IN"
    if _OTHER_INDIC.search(text or "") or stt_language in {"ta-IN", "kn-IN", "ml-IN", "bn-IN", "mr-IN", "gu-IN", "od-IN", "pa-IN"}:
        return "unsupported"
    share = english_share(text)
    if share is not None:
        if share <= 0.3 or _DEVANAGARI.search(text or ""):
            return "hi-IN"
        if share >= 0.7 and len(toks) >= SHORT_TURN:
            return "en-IN"
        return None  # genuinely mixed: no switch either way
    if stt_language in {"hi-IN", "en-IN"}:
        return stt_language
    return None


def detect_language_switch(text: str, current_language: str, stt_language: Optional[str] = None,
                           previous_turn_language: Optional[str] = None) -> Optional[SignalHit]:
    """Explicit requests switch immediately. An implicit switch (seller simply
    starts speaking another language) needs either an unambiguous script/STT
    signal or two consecutive turns, so one English word in a Hinglish
    sentence never flips the call (hysteresis)."""
    for lang, pat in EXPLICIT_LANG_REQUEST:
        m = pat.search(text or "")
        if m:
            if lang == current_language:
                return None
            return SignalHit("language_switch", m.group(0), "regex:explicit_request", lang)

    spoken = guess_language(text, stt_language)
    if spoken is None or spoken == current_language:
        return None
    # a short line never switches on its own: it must be a real sentence the STT agrees with, or the second
    # turn in a row in that language ("Kaun si details?" is 3 words)
    words = len(re.findall(r"[^\s]+", text or ""))
    unambiguous = spoken in {"te-IN", "unsupported"} or (stt_language is not None and stt_language == spoken
                                                         and words >= SHORT_TURN)
    if unambiguous or previous_turn_language == spoken:
        return SignalHit("language_switch", f"seller spoke {spoken}", "stt_language" if stt_language else "lexical", spoken)
    return None


def detect_signals(text: str) -> List[SignalHit]:
    hits = {}
    for group, pats in _COMPILED.items():
        sig = ALIASES.get(group, group)
        if sig in hits:
            continue
        for p in pats:
            m = p.search(text or "")
            if m:
                hits[sig] = SignalHit(sig, m.group(0))
                break
    # a refusal or complaint outranks an "interest" word in the same turn: "I am not interested right
    # now" fired interest (from "interested") and switched VANI to ENGAGED in the demo
    if hits.keys() & {"not_interested", "do_not_call", "frustration", "complaint"}:
        hits.pop("interest", None)
    return sorted(hits.values(), key=lambda h: PRIORITY.index(h.signal))


# Frustration comes in three kinds, and only one of them means "end the call" (Chennai live session
# 3419775_20261010_125638: "Abhi main bol raha hoon baar baar call karte ho, kal phir se call karogi aap log" was
# counted as a second frustration and VANI hung up on a seller who was inviting her to talk NOW).
#   wants_out  asks to stop / hang up / leave them alone, or abuse -> a second strike ends the call
#   hostile    fed up, insulting the call ("pareshan kar diya", "faltu") -> calm down; a second strike ends it
#   venting    annoyed about repeated calls but still talking, or inviting VANI to get to the point -> never ends
#              the call: use THIS call (value line + one easy ask). E10: 18-43% of objecting sellers still secure
#              a callback; E4: a short back-off after frustration does not save more sellers than continuing.
_WANTS_OUT = re.compile(r"\bphone\s*(cut|rakh)\w*|\bband\s*(kar|karo|kijiye|kro)\b|\bbas\s*kar\w*|\b(chhod|chod)\s*(do|dijiye)\b|"
                        r"\bpeech[ae]\s*(chhod|pad)|\b(call|phone)\s*mat\b|\bmat\s*kar\w*\s*(call|phone)|\bdisturb\s*mat\b|"
                        r"\bhang\s*up\b|\bstop\s*(it|calling)\b|\bleave\s*me\b|\bget\s*lost\b|\brakh\s*(do|dijiye)\b|"
                        r"\bbakwas\b|\bdimaag\s*(kharab|mat)|\bkya\s*tamasha\b", re.I)
_HOSTILE = re.compile(r"\bpareshan\b|\birritat|\bannoying\b|\bfed\s*up\b|\bfaltu\b|\bzabardasti\b|\bkhaamkha\b|"
                      r"\bkya\s*kar\s*loge\b|\bvisugu\b|\bkopam\b", re.I)
CALL_FREQUENCY = re.compile(r"\bbaar\s*baar\b|\bbar\s*bar\b|\bkitni\s*baar\b|\bphir\s*(se\s*)?(call|phone)|\broz\s*(roz\s*)?(call|phone)|"
                            r"\bdaily\s*call|\bmalli\s*malli\b|\bagain\s*and\s*again\b|\bso\s*many\s*(calls|times)\b|"
                            r"\b(char|chaar|paanch|panch|das)\s*(\w+\s*){0,3}baar\s*(phone|call)|\bkitne\s*(call|phone)", re.I)
_ENGAGED = re.compile(r"\babhi\s*(main\s*|mai\s*)?(bol|baat\s*kar)\s*(raha|rahi|rha|rhi)|\bab\s*bolo\b|\bbolo\s*(kya|jaldi)|"
                      r"\bjaldi\s*(se\s*)?(batao|bataiye|bolo|boliye)|\bkya\s*(baat|kaam)\s*hai\b|\bbatao\s*kya\b|"
                      r"\bkal\s*phir\s*(se\s*)?(call|phone)|\bphir\s*(se\s*)?(call|phone)\s*karo?g|\bseedha\s*(batao|bolo)|"
                      r"\bpoint\s*pe\s*aao|\bjust\s*tell\s*me\b|\bget\s*to\s*the\s*point\b", re.I)


def frustration_kind(text: str) -> str:
    """wants_out | hostile | venting, for a line that carries frustration (see above)."""
    t = text or ""
    if _WANTS_OUT.search(t):
        return "wants_out"
    if _HOSTILE.search(t):
        return "hostile"
    if _ENGAGED.search(t) or CALL_FREQUENCY.search(t):
        return "venting"
    return "hostile"


HARD_NO = re.compile(r"\bbilkul\s*(bhi\s*)?(nahi|nhi)\s*(chahiye|chaiye)|\bkabhi\s*(bhi\s*)?(nahi|nhi)\s*chahiye|"
                     r"\bbilkul\s*interest\s*nahi|\babsolutely\s*not\b|\bnever\b|\bzaroorat\s*hi\s*nahi\b", re.I)


def top_signal(text: str) -> Optional[SignalHit]:
    hits = detect_signals(text)
    return hits[0] if hits else None


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    for t in ["Maine... mujhe nahi chahiye. baar baar please.", "Yeh AI bol raha hai ya genuine person?",
              "jab unko time hoga, toh aapko saamne se bataenge", "Ji ji, bataiye.", "Bhai jaldi bolo, customer baitha hai",
              "Can you please speak in English, I don't follow Hindi well", "Telugu lo matladandi please",
              "Kitne ka package hai?", "Aapke executive ne paise le liye, koi lead nahi aayi"]:
        print(f"{t[:55]!r:58} -> {[h.signal for h in detect_signals(t)]} | lang_switch={detect_language_switch(t, 'hi-IN')}")

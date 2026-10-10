"""The Seller Call Scenarios playbook (scenarios.pdf) as data: the single source
of truth read by the persona generator, the live engine, the prompt builder,
the recording analysis and the tests.

Two layers: PERSONA (how VANI speaks) and GOAL (what the call tries to
achieve). Both are set before the call and either can switch on any seller turn.
"""

# ---------------- pre-call: seller types (first match wins) ----------------
SELLER_TYPES = [
    # id, label, starting persona
    ("fatigued_repeat", "Fatigued repeat lead",
     {"voice": "calm", "empathy": 5, "assertiveness": 1, "max_words": 18, "ask_style": "soft",
      "opening_style": "apologise for calling again"}),
    ("english_professional", "English-preferring professional",
     {"voice": "neutral", "empathy": 3, "assertiveness": 3, "max_words": 24, "ask_style": "direct",
      "opening_style": "value first", "language": "en-IN"}),
    ("cautious_burned", "Cautious / burned seller",
     {"voice": "calm", "empathy": 5, "assertiveness": 1, "max_words": 22, "ask_style": "soft",
      "opening_style": "trust first; honest and transparent (virtual assistant only if asked)", "pace_bias": -0.05}),
    ("with_executive", "Already with an executive",
     {"voice": "warm", "empathy": 4, "assertiveness": 2, "max_words": 24, "ask_style": "soft",
      "opening_style": "relationship, no fresh pitch"}),
    ("busy_owner", "Busy business owner",
     {"voice": "crisp", "gender": "male", "empathy": 3, "assertiveness": 4, "max_words": 17, "ask_style": "direct",
      "opening_style": "value first", "pace_bias": 0.05}),
    ("warm_interested", "Warm, interested lead",
     {"voice": "warm", "empathy": 4, "assertiveness": 4, "max_words": 32, "ask_style": "direct",
      "opening_style": "move to next step quickly", "pace_bias": 0.03}),
    ("small_trader", "Small local trader",
     {"voice": "warmest", "empathy": 5, "assertiveness": 2, "max_words": 24, "ask_style": "soft",
      "opening_style": "benefit story in simple Hinglish", "pace_bias": -0.04}),
]
SELLER_TYPE_LABEL = {t[0]: t[1] for t in SELLER_TYPES}
HIGH_CONVERTING_BUCKETS = {"NUR", "PAM", "SCHD"}
CALLBACK_BUCKETS = {"OLP", "PANF"}

# ---------------- goals ----------------
GOALS = {
    "understand": "Learn how the business is doing, how IndiaMART is working for them, and what they need",
    "complaint_recovery": "Complaint captured in the seller's words, apology, routed to support; no pitch",
    "exec_handoff": "Executive's name and the seller's need passed on; no fresh pitch",
    "data_update": "Right contact person, number and role captured",
    "respectful_exit": "Reason and preferred contact frequency captured; polite end",
    "info_whatsapp": "Seller agrees to receive details on WhatsApp",
    "nurture": "Questions answered at the seller's pace; follow-up only if wanted",
    "meeting": "A slot agreed, in person or online as the seller prefers",
    "callback": "A time the seller chooses",
    "human_handoff": "A human executive calls at a chosen time",
}
FALLBACKS = {
    "complaint_recovery": ["callback", "respectful_exit"],
    "exec_handoff": ["callback", "data_update"],
    "data_update": ["callback", "respectful_exit"],
    "respectful_exit": ["info_whatsapp", "callback"],
    "info_whatsapp": ["callback", "meeting"],
    "nurture": ["info_whatsapp", "respectful_exit"],
    "meeting": ["callback", "info_whatsapp"],
    "callback": ["meeting", "info_whatsapp"],
    "human_handoff": [],
}
# goals a "softer" mid-call switch may not override
PROTECTED_GOALS = {"complaint_recovery", "exec_handoff", "data_update"}

# understanding question, tailored to goal and category (asked before any goal step)
UNDERSTANDING_Q = {
    "complaint_recovery": "पिछली बार क्या दिक्कत आई थी, ज़रा बताइए?",
    "exec_handoff": "आपके executive से अभी किस चीज़ में मदद चाहिए?",
    "data_update": "क्या आप ही business देखते हैं, या किसी और से बात करनी चाहिए?",
    "respectful_exit": "IndiaMART से आपको कितनी बार call आना ठीक लगेगा?",
    "info_whatsapp": "आपका {category} का काम अभी कैसा चल रहा है?",
    "nurture": "आपका {category} का काम अभी कैसा चल रहा है, IndiaMART से कुछ फ़ायदा हो रहा है?",
    "meeting": "आपका {category} का काम अभी कैसा चल रहा है?",
    "callback": "आपका {category} का काम अभी कैसा चल रहा है?",
}

# ---------------- live signals, in priority order (1 = highest) ----------------
# signal, priority, persona mode it switches to (None = no persona change), playbook action
SIGNALS = [
    ("do_not_call", 1, None, "Confirm it won't call again and end (DO_NOT_CALL)"),
    ("connectivity", 2, "CLEAR_AUDIO", "Ask once 'Kya aapko meri awaaz aa rahi hai?'; second time say it will call back and end"),
    ("frustration", 3, "CALM_EMPATHETIC", "Apologise once, stop all asks, offer: call later, WhatsApp, or end (repeated-call complaints: never another call). Second time, or abuse: close with ESCALATED_EXIT, unless the seller is asking something or still talking"),
    ("complaint", 4, "CALM_EMPATHETIC", "Apologise, route to support, ask when support may call; no pitch"),
    ("ai_bot_suspicion", 5, "TRANSPARENT", "Say it is IndiaMART's virtual assistant, then resume the pending question"),
    ("identity_question", 6, "TRANSPARENT", "Name, IndiaMART and the reason in one sentence (no virtual-assistant mention: that is only for a bot/AI question), then resume"),
    ("not_right_person", 7, None, "Apologise, ask for the right person and number once, close"),
    ("already_with_executive", 8, None, "Reassure and offer their account manager for any other doubt; a described need -> meeting (two slots); no -> close EXEC_HANDOFF"),
    ("not_interested", 9, None, "First refusal: ONE gentle two-option reason question. Refused again, 'zaroorat nahi', a reason, or a final-refusal phrase: close at once with the RESPECTFUL_EXIT line (nothing sent unasked); never ask how often to call, never re-pitch"),
    ("busy", 10, "BRIEF", "One line of value, then 'kis time call karun, ya WhatsApp par details bhej doon?'"),
    ("human_request", 11, None, "Agree, ask when an executive may call"),
    ("wants_whatsapp", 12, None, "Confirm and close (INFO_SENT)"),
    ("gives_time", 13, None, "Confirm the slot for whatever goal is active: a meeting only 9 AM-6 PM from tomorrow, chosen by the seller, then in person / online; callbacks and support calls any time"),
    ("language_switch", 14, "LANGUAGE", "Switch fully and repeat the pending point in the new language; voice stays the same"),
    ("need_few_enquiries", 15, None, "Empathise, explain how the executive helps with exactly that, offer a meeting"),
    ("buylead_query", 15.5, None, "Point to self-service: log in to the IndiaMART seller dashboard and open the BuyLeads section, on the website or the IndiaMART app; no meeting ask. Second time: offer the details on WhatsApp"),
    ("price_query", 16, None, "Never quote a price: charges depend on the plan and leads, the executive explains for their category; move to the goal step"),
    ("confusion", 17, "SIMPLE", "Restate the reason in simple words with the category as an example"),
    ("interest", 18, "ENGAGED", "Move to the goal step"),
    ("hangup_risk", 19, "COMPRESSED", "Skip the remaining questions and go straight to one easy ask"),
    ("context", 20, None, "Capture into seller_insights, mark answered questions, ask the next one"),
]
SIGNAL_PRIORITY = {s[0]: s[1] for s in SIGNALS}
SIGNAL_MODE = {s[0]: s[2] for s in SIGNALS}
SIGNAL_ACTION = {s[0]: s[3] for s in SIGNALS}
# acted on even at medium confidence: compliance and harm-avoidance beats hysteresis.
# frustration is NOT here: its second strike ends the call, and a medium-confidence LLM reading of a
# cooperative Telugu line ("chalo Telugu lo matladukundam, cheppandi") ended a demo call as ESCALATED_EXIT
ACT_ON_MEDIUM = {"do_not_call", "complaint", "human_request", "connectivity", "wants_whatsapp",
                 "gives_time", "language_switch"}

PERSONA_MODES = {
    "DEFAULT":         {"pace_delta": 0.0,   "max_words": None, "empathy_delta": 0, "assertiveness_delta": 0},
    "CLEAR_AUDIO":     {"pace_delta": -0.08, "max_words": 14,   "empathy_delta": 0, "assertiveness_delta": 0},
    "CALM_EMPATHETIC": {"pace_delta": -0.06, "max_words": 15,   "empathy_set": 5,   "assertiveness_set": 1},
    "TRANSPARENT":     {"pace_delta": 0.0,   "max_words": 30,   "empathy_delta": 1, "assertiveness_delta": 0},
    "BRIEF":           {"pace_delta": 0.05,  "max_words": 14,   "empathy_delta": 0, "assertiveness_delta": 0},
    "SIMPLE":          {"pace_delta": -0.1,  "max_words": 20,   "empathy_delta": 1, "assertiveness_delta": 0},
    "ENGAGED":         {"pace_delta": 0.03,  "max_words": 32,   "empathy_delta": 0, "assertiveness_delta": 1},
    "COMPRESSED":      {"pace_delta": 0.0,   "max_words": 14,   "empathy_delta": 0, "assertiveness_delta": -1},
    # annoyed about calls but still on the line: calm, but VANI keeps the conversation and gives the reason to stay
    "RESPECTFUL_VALUE": {"pace_delta": -0.03, "max_words": 30,  "empathy_set": 5,   "assertiveness_set": 2},
}
MODE_HOLD_TURNS = 2  # hold a new mode for at least 2 turns (unless a higher-priority signal arrives)

# ---------------- mid-call goal switches ----------------
# signal -> new goal, and the current goals it may NOT override
GOAL_SWITCHES = {
    "complaint": ("complaint_recovery", set()),
    "already_with_executive": ("exec_handoff", set()),
    "not_right_person": ("data_update", set()),
    "busy": ("callback", PROTECTED_GOALS),
    "frustration": ("callback", PROTECTED_GOALS),
    "wants_whatsapp": ("info_whatsapp", set()),
    "human_request": ("human_handoff", set()),
    "need_few_enquiries": ("meeting", PROTECTED_GOALS),
    "interest": ("meeting", PROTECTED_GOALS),
    "price_query": ("meeting", PROTECTED_GOALS),
    "refused_with_reason": ("respectful_exit", PROTECTED_GOALS),  # master 4.4: a reason after refusing -> close
}

# ---------------- endings ----------------
# outcome -> (seller_disposition, Hindi closing (female), Hindi closing (male), English closing)
ENDINGS = {
    # IndiaMART master prompt, section 8 (statements, said once, never followed by a question)
    "MEETING_FIXED": ("Interested", "आपकी meeting {slot} के लिए fix हो गई है, {format}। Confirmation WhatsApp पर आ जाएगा। धन्यवाद।", None,
                      "Your meeting is fixed for {slot}, {format}. The confirmation will come on WhatsApp. Thank you."),
    "CALLBACK_SCHEDULED": ("Open", "ठीक है, हम आपको {slot} पर call करेंगे। धन्यवाद।", None,
                           "Alright, we will call you {slot}. Thank you."),
    "INFO_SENT": ("Curious", "मैं details आपको WhatsApp पर भेज रही हूँ। धन्यवाद, आपका दिन शुभ हो।",
                  "मैं details आपको WhatsApp पर भेज रहा हूँ। धन्यवाद, आपका दिन शुभ हो।",
                  "I am sending you the details on WhatsApp. Thank you, have a good day."),
    "COMPLAINT_LOGGED": ("Dissatisfied", "आपकी बात मैंने note कर ली है, support team {slot} आपसे संपर्क करेगी। समय देने के लिए धन्यवाद।", None,
                         "I have noted your concern, and our support team will contact you {slot}. Thank you for your time."),
    "EXEC_HANDOFF": ("Engaged with exec", "ठीक है, धन्यवाद। आपका दिन शुभ हो।", None, "Alright, thank you. Have a good day."),
    "CONTACT_UPDATED": ("Not right person", "ठीक है, हम {person} से connect कर लेंगे। धन्यवाद।", None,
                        "Alright, we will connect with {person}. Thank you."),
    # WhatsApp only when the seller agrees (IndiaMART, 10 Oct 2026): the master's "WhatsApp par proposal bhej deti
    # hoon" would send to a seller who just said no, so the refusal closing is a plain thank-you
    "RESPECTFUL_EXIT": ("Not interested", "कोई बात नहीं। समय देने के लिए धन्यवाद, आपका दिन शुभ हो।", None,
                        "No problem. Thank you for your time, have a good day."),
    "DO_NOT_CALL": ("Do not call", "समझ गई, हम आपको दोबारा call नहीं करेंगे। धन्यवाद।", "समझ गया, हम आपको दोबारा call नहीं करेंगे। धन्यवाद।",
                    "Understood, we will not call you again. Thank you."),
    "ESCALATED_EXIT": ("Frustrated", "परेशानी के लिए माफ़ी चाहती हूँ। आपका दिन शुभ हो।", "परेशानी के लिए माफ़ी चाहता हूँ। आपका दिन शुभ हो।",
                       "Sorry for the trouble. Have a good day."),
    "CALL_BACK_LATER": ("Unknown", "आवाज़ साफ़ नहीं आ रही, मैं आपको थोड़ी देर में दोबारा call करती हूँ। धन्यवाद।",
                        "आवाज़ साफ़ नहीं आ रही, मैं आपको थोड़ी देर में दोबारा call करता हूँ। धन्यवाद।",
                        "I can't hear you clearly, I will call you back in a little while. Thank you."),
    "HUMAN_HANDOFF": ("Wants human", "हमारे executive आपको {slot} पर call करेंगे। धन्यवाद।", None,
                      "Our executive will call you {slot}. Thank you."),
}
# the support call was declined: no promise that support will call anyway (master intent 4)
COMPLAINT_DECLINED = {"hi-IN": "ठीक है, आपकी बात मैंने note कर ली है। समय देने के लिए धन्यवाद।",
                      "en-IN": "Alright, I have noted your concern. Thank you for your time.",
                      "te-IN": "సరేనండి, మీ విషయం నమోదు చేసుకున్నాను. మీ సమయానికి ధన్యవాదాలు."}
OUTCOMES = list(ENDINGS)

# Telugu closings written directly (runtime machine translation turned "we will not call you again"
# into "you need not call again" and "sorry for the trouble" into "sorry for the irritation I felt").
# Telugu first-person verbs here are gender-neutral.
ENDINGS_TE = {
    "MEETING_FIXED": "మీ meeting {slot} కి fix అయింది, {format}. Confirmation WhatsApp లో వస్తుంది. ధన్యవాదాలు.",
    "CALLBACK_SCHEDULED": "సరేనండి, మేము మీకు {slot} call చేస్తాము. ధన్యవాదాలు.",
    "INFO_SENT": "వివరాలు మీకు WhatsApp లో పంపిస్తున్నాను. ధన్యవాదాలు, మీ రోజు శుభంగా ఉండాలి.",
    "COMPLAINT_LOGGED": "మీ విషయం నమోదు చేసుకున్నాను, support team {slot} మిమ్మల్ని సంప్రదిస్తుంది. మీ సమయానికి ధన్యవాదాలు.",
    "EXEC_HANDOFF": "సరేనండి, ధన్యవాదాలు. మీ రోజు శుభంగా ఉండాలి.",
    "CONTACT_UPDATED": "సరేనండి, మేము {person} తో connect అవుతాము. ధన్యవాదాలు.",
    "RESPECTFUL_EXIT": "పర్వాలేదండి. మీ సమయానికి ధన్యవాదాలు, మీ రోజు శుభంగా ఉండాలి.",
    "DO_NOT_CALL": "అర్థమైంది, మేము మీకు మళ్ళీ call చేయము. ధన్యవాదాలు.",
    "ESCALATED_EXIT": "ఇబ్బందికి క్షమించండి. మీ రోజు శుభంగా ఉండాలి.",
    "CALL_BACK_LATER": "మీ మాట స్పష్టంగా వినిపించడం లేదు, కొద్దిసేపటి తర్వాత మళ్ళీ call చేస్తాను. ధన్యవాదాలు.",
    "HUMAN_HANDOFF": "మా executive మీకు {slot} call చేస్తారు. ధన్యవాదాలు.",
}

# which outcome fully / partly achieves which goal
GOAL_SUCCESS = {
    "complaint_recovery": {"COMPLAINT_LOGGED"},
    "exec_handoff": {"EXEC_HANDOFF"},
    "data_update": {"CONTACT_UPDATED"},
    "respectful_exit": {"RESPECTFUL_EXIT"},
    "info_whatsapp": {"INFO_SENT"},
    "nurture": {"INFO_SENT", "CALLBACK_SCHEDULED", "MEETING_FIXED"},
    "meeting": {"MEETING_FIXED"},
    "callback": {"CALLBACK_SCHEDULED"},
    "human_handoff": {"HUMAN_HANDOFF"},
}
NEUTRAL_OUTCOMES = {"CALL_BACK_LATER"}


def goal_achieved(primary_goal: str, outcome: str) -> str:
    if outcome in GOAL_SUCCESS.get(primary_goal, set()):
        return "yes"
    if outcome in {"MEETING_FIXED", "CALLBACK_SCHEDULED", "INFO_SENT", "EXEC_HANDOFF", "COMPLAINT_LOGGED",
                   "CONTACT_UPDATED", "HUMAN_HANDOFF"}:
        return "partly"
    if outcome in NEUTRAL_OUTCOMES:
        return "partly"
    return "no"


# ---------------- ask limits ----------------
def ask_limits(past_attempts: int) -> dict:
    heavy = past_attempts >= 7
    # master prompt section 7: 3 goal asks (2 for 7+ past calls), 2 refusals, 2 frustrations, 2 audio failures
    return {"understanding_question": 2, "goal_step": 2 if heavy else 3, "refusals": 2,
            "frustration": 2, "connectivity": 2, "off_topic": 2}


BOT_NAME = {"female": "Payal", "male": "Rohan"}

# What VANI says the WhatsApp details contain (IndiaMART master prompt, SEND_INFO / intent 12). It must match the
# approved WhatsApp template (integrations/whatsapp.py); no numbers are spoken.
WHATSAPP_DETAILS = ("how many buy leads your {category} competitors{in_city} have taken so far, the recent buy leads in "
                    "your category, and the buy leads you have missed")

# Facts VANI may use (IndiaMART's standard call pitch, master prompt section 1); no other numbers or names
INDIAMART_FACTS = ("about 15 lakh buyers and sellers connect on IndiaMART every day; IndiaMART has more than 60% of "
                   "the B2B market in India")

# Buy-lead and buyer-detail questions go to self-service, not a meeting (IndiaMART, 10 Oct 2026). VANI says
# "IndiaMART seller dashboard" only; the address below is for written material, not speech.
SELLER_DASHBOARD_URL = "seller.intermesh.com"
BUYLEAD_LINE = {
    "hi-IN": "आप अपने IndiaMART seller dashboard में login करके BuyLeads section में सभी buy leads देख सकते हैं — website पर, या IndiaMART app में भी।",
    "en-IN": "You can log in to your IndiaMART seller dashboard and open the BuyLeads section to see all buy leads — on the website, or in the IndiaMART app.",
    "te-IN": "మీ IndiaMART seller dashboard లో login చేసి BuyLeads section లో అన్ని buy leads చూడవచ్చు — website లో, లేదా IndiaMART app లో కూడా.",
}
BUYLEAD_LIGHT_CHECK = {"hi-IN": "क्या आप कुछ और जानना चाहेंगे?", "en-IN": "Is there anything else you would like to know?",
                       "te-IN": "ఇంకా ఏమైనా తెలుసుకోవాలనుకుంటున్నారా?"}
BUYLEAD_SEND_INFO = {"hi-IN": "ये सब details मैं आपको WhatsApp पर भेज देती हूँ, आप आराम से देख लीजिए। क्या इसी number पर भेज दूँ?",
                     "en-IN": "I can send all these details to you on WhatsApp so you can see them at leisure. Shall I send them to this number?",
                     "te-IN": "ఈ వివరాలన్నీ మీకు WhatsApp లో పంపిస్తాను, మీరు నెమ్మదిగా చూడవచ్చు. ఇదే number కి పంపనా?"}

# Opening reason per lead bucket. The buckets are not documented in the data
# dictionary; these meanings were learned by reading lead_call_summary text per
# bucket (269k calls). Meeting-fixed rate per bucket in brackets.
BUCKET_REASON = {
    # why we are calling, as a soft observation (master prompt 3.2: never "paid package kharidne ki koshish").
    # Meeting-fixed rate per bucket in the 269k calls in brackets.
    "PIM":   ("आप IndiaMART की paid services देख रहे थे", "you were looking at IndiaMART's paid services"),            # 10.5%
    "PAM":   ("आप IndiaMART की paid services देख रहे थे", "you were looking at IndiaMART's paid services"),            # 16.0%
    "PANF":  ("आप IndiaMART की paid services देख रहे थे", "you were looking at IndiaMART's paid services"),            # 10.5%
    "PNCHF": ("आपने IndiaMART से callback के लिए कहा था", "you had asked IndiaMART for a callback"),                    # 15.2%
    "PUA":   ("आप IndiaMART पर कुछ buy leads check कर रहे थे", "you were checking some buy leads on IndiaMART"),          # 12.8%
    "OLP":   ("आप IndiaMART पर कुछ buy leads check कर रहे थे", "you were checking some buy leads on IndiaMART"),          # 11.4%
    "OLPR":  ("आपने हाल ही में IndiaMART पर एक buy lead लिया था", "you recently took a buy lead on IndiaMART"),           # 11.4%
    "UA":    ("{city}{in_} आपकी {category} category में काफ़ी buyer enquiries आई हैं", "there have been many buyer enquiries in your {category} category{in_city}"),  # 10.1%
    "SCHD":  ("आपका IndiaMART demo book हुआ था", "you had booked an IndiaMART demo"),                                  # 14.3%
    "NUR":   ("आपने हाल ही में IndiaMART पर account बनाया है", "you recently created your IndiaMART account"),          # 31.2%
    "ENQR":  ("buyers आपको call कर रहे थे पर बात नहीं हो पाई", "buyers were calling you but could not reach you"),      # 5.3%
    "PNSR":  ("buyers आपको call कर रहे थे पर बात नहीं हो पाई", "buyers were calling you but could not reach you"),      # 6.0%
    "PNSM":  ("buyers आपको call कर रहे थे पर बात नहीं हो पाई", "buyers were calling you but could not reach you"),      # 7.4%
    "NVGT":  ("आपके profile पर buyer enquiries और calls आए हैं", "your profile has received buyer enquiries and calls"),  # 3.0%
    "PUT":   ("आपके business के लिए कुछ नए मौके हैं", "there are some new opportunities for your business"),            # 7.2%
}
# reasons already about buyer enquiries: the first reply adds no "buyers available" line (master 3.2)
ENQUIRY_BUCKETS = {"UA", "ENQR", "PNSR", "PNSM", "NVGT"}

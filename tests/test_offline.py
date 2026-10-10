"""Offline regression tests (no network). Each case is a playbook rule (scenarios.pdf)
or a defect actually found while building, so it cannot silently come back.

    python -m pytest tests -q
"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import hangup_model  # noqa: E402
import live_engine  # noqa: E402
from persona_generator import generate_persona, VOICES, VOICES_EN  # noqa: E402
from signal_detector import detect_signals, detect_language_switch  # noqa: E402
from utterance import dialogue_act, nothing_more  # noqa: E402
from voice_synth import format_numbers, sanitize, validate_speaker  # noqa: E402


def seller(**over):
    base = {"fk_glusr_usr_id": 1, "seller_state": "Delhi", "seller_city": "New Delhi", "business_type": "Proprietorship",
            "annual_turnover": "0 - 40 L", "top_category_1": "Clamps", "eng_cqs": 20.0, "eng_product_count": 10.0,
            "eng_enq_received_90d": 2.0, "bot_attempts": 1, "bot_answered": 1, "avg_answered_call_sec": 40.0,
            "calls_meeting_fixed": 0, "calls_not_interested": 0, "calls_call_later": 0, "past_objections": None,
            "past_dispositions_detailed": None, "past_questions_asked": None, "showed_frustration": 0,
            "asked_if_talking_to_bot": 0, "already_in_touch_with_executive": 0, "do_not_call_requested": 0}
    base.update(over)
    return base


def sigs(text):
    return {h.signal for h in detect_signals(text)}


# ---------------- signals: the playbook's own example words ----------------
@pytest.mark.parametrize("text,signal", [
    ("mujhe dobara call mat karna", "do_not_call"), ("number hata do", "do_not_call"),
    ("awaaz nahi aa rahi", "connectivity"), ("kitni baar call karoge", "frustration"), ("pareshan kar diya", "frustration"),
    ("leads hi nahi aate, paisa diya tha kuch nahi hua", "complaint"), ("aap robot ho kya?", "ai_bot_suspicion"),
    ("kaun bol raha hai?", "identity_question"), ("kis liye call kiya?", "identity_question"),
    ("main owner nahi hoon, sir se baat kijiye", "not_right_person"),
    ("hamare executive Rakesh ji pehle se aate hain", "already_with_executive"),
    ("nahi chahiye", "not_interested"), ("interest nahi hai", "not_interested"), ("abhi zaroorat nahi", "not_interested"),
    ("abhi busy hoon, jaldi bataiye", "busy"), ("baad mein", "busy"), ("manager se baat karao", "human_request"),
    ("WhatsApp pe details bhej do", "wants_whatsapp"), ("kal shaam 5 baje", "gives_time"), ("Tomorrow 4 pm", "gives_time"),
    ("enquiry bahut kam aati hai", "need_few_enquiries"), ("kitna charge lagega?", "price_query"),
    ("matlab? samjha nahi", "confusion"), ("kab aayenge? kaise hoga?", "interest"),
])
def test_playbook_example_words(text, signal):
    assert signal in sigs(text)


@pytest.mark.parametrize("text,signal", [  # real seller lines from the 83 recordings the old bot mishandled
    ("Nahi nahi thank you.", "not_interested"), ("Mujhe nahi thiye madam.", "not_interested"),
    ("Kitna?", "price_query"), ("Monthly ismein subscription kya hai?", "price_query"),
    ("Abhi dekhiye busy itna hai na counter mein abhi time nahi de payenge aapko.", "busy"),
    ("Theek hai na, hum soch ke aapko batate hain ma'am.", "busy"),
    ("Hello, haanji sir, ki aawaz aa rahi hai?", "connectivity"),
])
def test_recording_regressions(text, signal):
    assert signal in sigs(text)


@pytest.mark.parametrize("text,act", [
    # the Chennai demo line, and the requests it must stay distinct from
    ("What details on WhatsApp?", "question"), ("WhatsApp pe kya details milegi?", "question"),
    ("kya bhejoge WhatsApp pe?", "question"), ("emi details pampistaru?", "question"),
    ("WhatsApp pe details bhej do", "request"), ("Send it on WhatsApp", "request"),
    ("Can you send the details on WhatsApp?", "request"), ("Kya aap WhatsApp pe bhej sakte ho?", "request"),
    ("details pampandi", "request"), ("theek hai bhej do", "request"),
    ("Is there any cost?", "question"), ("kitna charge lagega", "question"), ("kaun bol raha hai", "question"),
    ("Why are you calling me again?", "question"), ("matlab?", "question"), ("How will this help me", "question"),
    ("It is going good.", "statement"), ("kal shaam 5 baje", "statement"), ("abhi busy hoon", "statement"),
    ("haan ji", "affirm"), ("nahi ji", "deny"), ("No, that's all, thank you", "deny"), ("Ok thanks", "closing"),
])
def test_dialogue_act(text, act):
    assert dialogue_act(text) == act


@pytest.mark.parametrize("text,done", [
    ("No, that's all. Thank you.", True), ("nahi ji, bas", True), ("No I am not interested.", True), ("okay", True),
    ("inkem ledu andi", True), ("bas itna hi, dhanyavaad", True),
    ("haan", False), ("nahi, ek sawaal hai", False), ("Yes one more thing", False), ("What about the price?", False),
    ("Can you also send the price list?", False),
])
def test_nothing_more(text, done):
    assert nothing_more(text) is done


def test_product_word_machine_is_not_bot_suspicion():
    assert "ai_bot_suspicion" not in sigs("How does it help my machine sell?")


def test_bare_acknowledgement_is_not_interest_and_bare_no_is_context_dependent():
    assert "interest" not in sigs("haan ji boliye")
    assert "not_interested" not in sigs("nahi")  # read against VANI's previous turn (tier 2)


def test_language_switch_explicit_and_hysteresis():
    assert detect_language_switch("Can you speak in English please?", "hi-IN").target_language == "en-IN"
    assert detect_language_switch("Telugu lo matladandi", "hi-IN").target_language == "te-IN"
    assert detect_language_switch("Okay what is the plan for this week then", "hi-IN") is None
    assert detect_language_switch("Okay what is the plan for this week then", "hi-IN", stt_language="en-IN").target_language == "en-IN"


# ---------------- persona generator: seller types and goals in playbook order ----------------
def test_do_not_call_is_never_dialled():
    p = generate_persona(seller(do_not_call_requested=1))
    assert p.blocked and p.voice == {}


@pytest.mark.parametrize("over,stype", [
    ({"bot_attempts": 4}, "fatigued_repeat"),
    ({"seller_state": "Tamil Nadu"}, "english_professional"),
    ({"past_objections": "Information / Trust / Privacy Concerns (1)"}, "cautious_burned"),
    ({"already_in_touch_with_executive": 1}, "with_executive"),
    ({"annual_turnover": "5 - 25 Cr"}, "busy_owner"),
    ({"avg_answered_call_sec": 15.0}, "busy_owner"),
    ({"calls_meeting_fixed": 1}, "warm_interested"),
    ({}, "small_trader"),
])
def test_seller_type(over, stype):
    assert generate_persona(seller(**over)).seller_type == stype


@pytest.mark.parametrize("over,goal", [
    ({"past_objections": "Call Handling / Executive Gaps (1)"}, "complaint_recovery"),
    ({"already_in_touch_with_executive": 1}, "exec_handoff"),
    ({"past_dispositions_detailed": "wrong_number (1)"}, "data_update"),
    ({"bot_attempts": 7}, "respectful_exit"),
    ({"bot_attempts": 5}, "info_whatsapp"),
    ({"calls_not_interested": 1}, "nurture"),
    ({"calls_meeting_fixed": 1}, "meeting"),
    ({"calls_call_later": 1}, "callback"),
    ({}, "meeting"),
])
def test_goal_order(over, goal):
    assert generate_persona(seller(**over)).goal.value == goal


def test_every_setting_has_reason_evidence_confidence():
    p = generate_persona(seller())
    for sec in (p.voice, p.language, p.tone):
        for name, f in sec.items():
            assert f.reason and f.evidence and f.confidence in {"high", "medium", "low"}, name


def test_missing_fields_lower_confidence():
    p = generate_persona(seller(seller_state=None, business_type=None, annual_turnover=None))
    assert {"seller_state", "business_type", "annual_turnover"} <= set(p.missing_fields)
    assert p.language["primary"].confidence == "low"


def test_bot_name_and_verbs_match_voice_gender():
    busy = generate_persona(seller(annual_turnover="5 - 25 Cr"))
    assert busy.voice["gender"].value == "male" and busy.voice["bot_name"].value == "Rohan"
    assert "बोल रहा हूँ" in busy.conversation_plan["opening"].value
    other = generate_persona(seller())
    assert other.voice["bot_name"].value == "Payal" and "बोल रही हूँ" in other.conversation_plan["opening"].value


def test_greeting_checks_the_business_and_fatigued_first_reply_apologises_first(make_call):
    plan = generate_persona(seller(bot_attempts=5)).to_dict()["conversation_plan"]
    op, first = plan["opening"]["value"], plan["first_reply"]
    assert op.startswith("नमस्ते, मैं IndiaMART से Payal") and op.endswith("से हो रही है?") and "माफ़ी" not in op
    assert first.startswith("दोबारा call करने के लिए माफ़ी") and first.endswith("?") and "meeting" not in first.lower()
    assert not re.findall(r"\d", first)                  # no invented numbers in the reason
    c = make_call([], bot_attempts=5)
    assert c.seller_turn(text="haan ji").reply == first   # said word for word, no LLM


def test_telugu_offered_and_pace_bounds():
    assert generate_persona(seller(seller_state="Telangana")).conversation_plan["telugu_offer"] is True
    for over in ({}, {"annual_turnover": "5 - 25 Cr"}, {"bot_attempts": 9}):
        assert 0.8 <= generate_persona(seller(**over)).voice["pace"].value <= 1.1


# ---------------- voice ----------------
def test_tts_text_rules_and_voices():
    assert format_numbers("12000 enquiries") == "12,000 enquiries"
    assert sanitize("**Hello** score 11/100") == "Hello score 11 out of 100"
    for v in list(VOICES.values()) + list(VOICES_EN.values()):
        validate_speaker(v, "bulbul:v4-flash")


def test_hangup_risk_is_a_probability():
    r = hangup_model.risk(hangup_model.turn_features(1, 0.5, 2.0, 3, 2, 30, 6, "haan"))
    assert 0.0 <= r <= 1.0


# ---------------- live engine with a scripted LLM ----------------
class FakeLLM:
    def __init__(self, replies):
        self.replies, self.last = list(replies), None
        self.chat = SimpleNamespace(completions=self._complete)
        self.text = SimpleNamespace(transliterate=lambda **k: SimpleNamespace(transliterated_text=k["input"]),
                                    translate=lambda **k: SimpleNamespace(translated_text=k["input"]))

    def _complete(self, **kw):
        self.last = self.replies.pop(0) if self.replies else self.last
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.last, ensure_ascii=False)))])


def turn(reply, signals=(), outcome="IN_PROGRESS", end=False, qtype="goal_step", lang="hi-IN", slot="", reason=False,
         answered=True):
    return {"seller_signals": [{"signal": s, "confidence": c} for s, c in
                               ([(x, "high") if isinstance(x, str) else x for x in signals] or [("none", "high")])],
            "seller_language": lang, "signal_reason": "test", "seller_insights": {}, "understanding_answered": answered,
            "refused_with_reason": reason, "slot": slot, "reply": reply, "question_type": qtype,
            "call_outcome": outcome, "end_call": end}


@pytest.fixture
def make_call(monkeypatch):
    def _make(replies, **over):
        fake = FakeLLM(replies)
        monkeypatch.setattr(live_engine, "client", lambda: fake)
        monkeypatch.setattr(hangup_model, "threshold", lambda: 2.0)  # keep the model out of scripted tests
        call = live_engine.LiveCall(generate_persona(seller(**over)).to_dict(), synthesize_audio=False)
        call.start()
        return call
    return _make


Q = "क्या आपके business में अभी कोई दिक्कत है?"


def test_do_not_call_ends_immediately_with_playbook_closing(make_call):
    c = make_call([])
    r = c.seller_turn(text="mujhe dobara call mat karna")
    assert r.call_outcome == "DO_NOT_CALL" and r.end_call and "दोबारा call नहीं करेंगे" in r.reply


def test_frustration_first_calms_then_second_ends(make_call):
    # master intent 3: CALM_EMPATHETIC, apologise once, offer an easy option; a complaint about repeated calls is
    # never answered with another call (live session 125638) -- WhatsApp is offered, sent only on a yes
    c = make_call([turn("जी, परेशानी के लिए माफ़ी चाहती हूँ। क्या मैं कल call करूँ?", ["frustration"])] * 3)
    r = c.seller_turn(text="kitni baar call karoge")
    assert r.delivery["mode"] == "CALM_EMPATHETIC" and r.delivery["goal"] == "info_whatsapp" and not r.end_call
    assert "कल call" not in r.reply and "WhatsApp" in r.reply and c.outcome == "IN_PROGRESS"
    r = c.seller_turn(text="pareshan kar diya aap logon ne")
    assert r.call_outcome == "ESCALATED_EXIT" and r.end_call


def test_first_frustration_cannot_be_closed_as_respectful_exit(make_call):
    bye = turn("कोई बात नहीं, समय देने के लिए धन्यवाद।", ["frustration"], outcome="RESPECTFUL_EXIT", end=True)
    c = make_call([bye, bye, bye])
    r = c.seller_turn(text="kitni baar call karoge")
    assert not r.end_call and "?" in r.reply


def test_complaint_switches_goal_and_blocks_pitch(make_call):
    pitch = turn("जी, माफ़ी चाहती हूँ। क्या कल एक meeting रख दूँ?", ["complaint"])
    c = make_call([pitch, pitch, pitch])
    r = c.seller_turn(text="leads hi nahi aate, paisa diya tha kuch nahi hua")
    assert r.delivery["goal"] == "complaint_recovery" and r.delivery["mode"] == "CALM_EMPATHETIC"
    assert "meeting" not in r.reply.lower()


def test_time_during_complaint_logs_the_complaint(make_call):
    c = make_call([turn("जी, माफ़ी चाहती हूँ। support team आपको किस समय call करे?", ["complaint"]),
                   turn("ठीक है।", ["gives_time"], outcome="CALLBACK_SCHEDULED", end=True, slot="kal shaam 5 baje")])
    c.seller_turn(text="leads hi nahi aate, paisa diya tha kuch nahi hua")
    r = c.seller_turn(text="kal shaam 5 baje")
    assert r.call_outcome == "COMPLAINT_LOGGED"


def test_price_quote_from_real_calls_is_removed(make_call):
    bad = turn("जी, monthly चार हज़ार plus GST लगता है। क्या meeting रख दूँ?", ["price_query"])
    c = make_call([bad, bad, bad])
    r = c.seller_turn(text="kitna charge lagega?")
    assert "हज़ार" not in r.reply and "GST" not in r.reply and "free" not in r.reply.lower()
    assert "Charges" in r.reply and r.reply.index("Charges") < r.reply.index("?")   # the answer first, then the ask


def test_internal_labels_and_human_claim_are_removed(make_call):
    bad = turn("मैं एक इंसान हूँ, goal complaint_recovery है। आपका काम कैसा चल रहा है?", qtype="understanding")
    c = make_call([bad, bad, bad])
    r = c.seller_turn(text="haan ji")
    assert "इंसान" not in r.reply and "complaint_recovery" not in r.reply


def test_understand_first(make_call):
    ask = turn("क्या मैं कल meeting रख दूँ?", qtype="goal_step", answered=False)
    c = make_call([ask, ask, ask])
    r = c.seller_turn(text="haan ji")
    assert "meeting" not in r.reply.lower() and "?" in r.reply


def test_mode_is_held_for_two_turns(make_call):
    c = make_call([turn("जी, एक line में बताती हूँ। किस time call करूँ?", ["busy"]),
                   turn("जी, बिल्कुल। कल किस time ठीक रहेगा?", ["interest"])])
    c.seller_turn(text="abhi busy hoon, jaldi bataiye")
    r = c.seller_turn(text="kab aayenge? kaise hoga?")
    assert r.delivery["mode"] == "BRIEF"


def test_calm_empathetic_is_not_replaced_by_engaged(make_call):
    c = make_call([turn("जी, माफ़ी चाहती हूँ। कब call करूँ?", ["frustration"]), turn("जी। कब call करूँ?", ["interest"]),
                   turn("जी। कल शाम ठीक रहेगा?", ["interest"]), turn("जी। कल शाम ठीक रहेगा या परसों?", ["interest"])])
    c.seller_turn(text="pareshan kar diya")
    for _ in range(3):
        r = c.seller_turn(text="kab aayenge? kaise hoga?")
    assert r.delivery["mode"] == "CALM_EMPATHETIC"


def test_language_switch_keeps_the_voice(make_call):
    c = make_call([turn("Sure ji. How is your business going?", ["language_switch"], lang="en-IN", qtype="understanding")])
    before = c.s["speaker"]
    r = c.seller_turn(text="Can you speak in English please?")
    assert r.delivery["language"] == "en-IN" and r.delivery["speaker"] == before


def test_medium_signal_needs_to_repeat(make_call):
    c = make_call([turn("जी। executive आपकी profile देखेंगे। क्या आप जानना चाहेंगे?", [("confusion", "medium")]),
                   turn("जी, buyers आपको ढूँढ रहे हैं। समझ आया?", [("confusion", "medium")], qtype="clarify")])
    c.seller_turn(text="haan ji")                        # the first reply is fixed (no LLM)
    assert c.seller_turn(text="hmm achha").delivery["mode"] == "DEFAULT"
    assert c.seller_turn(text="hmm phir se").delivery["mode"] == "SIMPLE"


def test_maam_is_not_a_time_so_no_false_meeting(make_call):
    c = make_call([turn("आपकी meeting पक्की।", outcome="MEETING_FIXED", end=True)] * 3)
    r = c.seller_turn(text="Theek hai, hum soch ke aapko batate hain ma'am")
    assert r.call_outcome != "MEETING_FIXED"


def test_busy_alone_is_not_a_callback(make_call):
    c = make_call([turn("ठीक है, हम call करेंगे।", ["busy"], outcome="CALLBACK_SCHEDULED", end=True)] * 3)
    r = c.seller_turn(text="na na utna time nahi hai ji")
    assert r.call_outcome != "CALLBACK_SCHEDULED"


def test_agreeing_to_a_proposed_time_fixes_the_meeting(make_call):
    # master 4.1: a slot inside 11 AM-5 PM from tomorrow, then "milkar ya online?", then the meeting is fixed
    fixed = turn("बहुत अच्छा।", outcome="MEETING_FIXED", end=True, slot="कल सुबह 11 बजे")
    c = make_call([turn("जी। क्या कल सुबह 11 बजे meeting रख दूँ?", ["need_few_enquiries"]), fixed, dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    r = c.seller_turn(text="haan theek hai")
    assert c.outcome == "IN_PROGRESS" and "11 बजे" in r.reply and "online" in r.reply   # format asked first
    r = c.seller_turn(text="online")
    assert r.call_outcome == "MEETING_FIXED" and "11 बजे" in r.reply and "online" in r.reply


def test_refusal_with_a_reason_closes_politely_without_whatsapp(make_call):
    # master 4.4 / intent 9: a reason after a no -> the RESPECTFUL_EXIT line; nothing is sent unasked (10 Oct)
    c = make_call([turn("जी, कोई बात नहीं। क्या मैं details WhatsApp पर भेज दूँ?", ["not_interested"], reason=True)])
    r = c.seller_turn(text="abhi zaroorat nahi hai, stock full hai")
    assert r.call_outcome == "RESPECTFUL_EXIT" and r.end_call and "WhatsApp" not in r.reply and "?" not in r.reply


def test_first_no_gets_the_two_option_question_and_its_answer_closes(make_call):
    pref = turn("जी, आगे कितनी बार call करना ठीक रहेगा?", ["not_interested"], qtype="contact")
    c = make_call([pref] * 3)
    r = c.seller_turn(text="nahi chahiye")
    assert not r.end_call and "पहले से काफ़ी काम" in r.reply and "कितनी बार" not in r.reply
    r = c.seller_turn(text="haan, pehle se kaafi kaam hai")
    assert r.call_outcome == "RESPECTFUL_EXIT" and r.end_call and "WhatsApp" not in r.reply
    c2 = make_call([pref] * 3)
    c2.seller_turn(text="nahi chahiye")
    r = c2.seller_turn(text="nahi chahiye, interest nahi hai")          # refused again
    assert r.call_outcome == "RESPECTFUL_EXIT" and r.end_call


def test_a_question_after_the_two_option_question_is_answered_not_closed(make_call):
    c = make_call([turn("Charges आपके plan के हिसाब से होते हैं। क्या आप जानना चाहेंगे?", ["price_query"])] * 3)
    c.seller_turn(text="nahi chahiye")
    r = c.seller_turn(text="waise iska charge kitna hai?")
    assert not r.end_call and c.outcome == "IN_PROGRESS"


def test_whatsapp_request_is_confirmed_and_closes(make_call):
    # master intent 12: the seller asked -> confirm and close (INFO_SENT); no "anything else?" round
    c = make_call([])
    r = c.seller_turn(text="WhatsApp pe details bhej do")
    assert r.call_outcome == "INFO_SENT" and r.end_call and "WhatsApp" in r.reply and "धन्यवाद" in r.reply
    assert "?" not in r.reply


def test_question_about_whatsapp_details_is_answered_not_closed(make_call):
    # Chennai demo: "What details on WhatsApp?" was read as wants_whatsapp and the call hung up as INFO_SENT
    wrong = turn("Our catalogue and how buyers in Chennai find you. Shall I send you the details on WhatsApp?",
                 ["wants_whatsapp"], outcome="INFO_SENT", end=True, lang="en-IN")
    c = make_call([wrong, dict(wrong), dict(wrong)], seller_state="Tamil Nadu")
    c.s["stage"], c.s["goal"], c.s["counts"]["goal_step"] = "goal_step", "info_whatsapp", 2  # ask limit reached
    c.history.append({"speaker": "vani", "text": "No problem. Shall I send you the details on WhatsApp?"})
    r = c.seller_turn(text="What details on WhatsApp?")
    assert not r.end_call and c.outcome == "IN_PROGRESS" and "wants_whatsapp" not in r.signals_tier1
    assert "catalogue" in r.reply and r.reply.endswith("?")
    r = c.seller_turn(text="Okay, send it on WhatsApp.")                # now they agree -> sent, and the call closes
    assert c.outcome == "INFO_SENT" and r.end_call and "WhatsApp" in r.reply and "good day" in r.reply


def test_meeting_is_fixed_only_after_slot_and_format_are_confirmed(make_call):
    fixed = turn("बहुत अच्छा।", outcome="MEETING_FIXED", end=True, slot="कल शाम 4 बजे")
    c = make_call([turn("जी। क्या कल शाम 4 बजे meeting रख दूँ?", ["need_few_enquiries"]), fixed, dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    r = c.seller_turn(text="haan theek hai")
    assert c.outcome == "IN_PROGRESS" and "4 बजे" in r.reply and "online" in r.reply
    r = c.seller_turn(text="milkar")
    assert r.call_outcome == "MEETING_FIXED" and r.end_call and "4 बजे" in r.reply and "मिलकर" in r.reply
    m = c.summary()["meeting"]
    assert m["format"] == "in_person" and m["at"].endswith("T16:00")


def test_seller_picks_the_second_option_and_that_slot_is_fixed(make_call):
    fixed = turn("ठीक है।", outcome="MEETING_FIXED", end=True)
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), fixed, dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    r = c.seller_turn(text="parso wala theek hai")
    assert c.outcome == "IN_PROGRESS" and "परसों शाम 4 बजे" in r.reply
    r = c.seller_turn(text="online")
    assert c.outcome == "MEETING_FIXED" and "परसों शाम 4 बजे" in r.reply and "online" in r.reply


def test_llm_cannot_fix_a_meeting_the_seller_did_not_confirm(make_call):
    fixed = turn("आपकी meeting कल 11 बजे fix हो गई है।", outcome="MEETING_FIXED", end=True, slot="कल सुबह 11 बजे")
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), fixed, dict(fixed),
                   dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    for line in ("executive kaun aayega?", "dekhte hain"):
        r = c.seller_turn(text=line)
        assert c.outcome == "IN_PROGRESS" and not r.end_call, line


def test_hard_endings_still_close_at_once(make_call):
    assert make_call([]).seller_turn(text="mujhe dobara call mat karna").end_call
    c = make_call([turn("जी, माफ़ी चाहती हूँ। क्या मैं कल call करूँ?", ["frustration"])])
    c.seller_turn(text="kitni baar call karoge")
    assert c.seller_turn(text="pareshan kar diya aap logon ne").end_call


def test_transparent_lasts_one_reply_and_discloses(make_call):
    c = make_call([turn("जी, आपके business में कैसा चल रहा है?", ["identity_question"], qtype="understanding"),
                   turn("जी, बढ़िया। क्या कल बात करें?")])
    r = c.seller_turn(text="kaun bol raha hai?")
    # who-is-calling gets name + IndiaMART; "virtual assistant" only for a bot question (master prompt section 1)
    assert r.delivery["mode"] == "TRANSPARENT" and "Payal" in r.reply and "virtual assistant" not in r.reply
    assert c.seller_turn(text="achha theek hai").delivery["mode"] == "DEFAULT"


def test_goal_ask_limit_moves_to_fallback(make_call):
    # three distinct goal asks (master limit 3) without agreement -> the next fallback goal (meeting -> callback)
    c = make_call([turn("जी, अच्छा है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ?", qtype="goal_step"),
                   turn("कोई बात नहीं। online video call पर बात करना आपके लिए ठीक रहेगा?", qtype="goal_step"),
                   turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", qtype="goal_step"),
                   turn("जी, समझ गई। आप किस बारे में और जानना चाहेंगे?", qtype="clarify")])
    for line in ["haan ji", "kaam theek chal raha hai", "dekhte hain", "pata nahi", "sochna padega"]:
        c.seller_turn(text=line)
    assert "callback" in c.goal_history


def test_not_interested_is_not_interest():
    assert sigs("No need. I am not interested right now, thank you.") == {"not_interested"}
    assert "not_interested" in sigs("No, do not send anything. Thank you.")


def test_declined_whatsapp_is_never_offered_again(make_call):
    again = turn("जी, executive आपकी profile देखेंगे। क्या मैं details WhatsApp पर भेज दूँ?")
    c = make_call([again] * 4)
    c.s["stage"] = "goal_step"
    c.history.append({"speaker": "vani", "text": "क्या मैं details WhatsApp पर भेज दूँ?"})
    c.seller_turn(text="nahi, WhatsApp nahi. meeting mein kya hoga?")
    assert "whatsapp" in c.declined_offers
    r = c.seller_turn(text="achha aur kya karenge woh?")
    assert "whatsapp" not in r.reply.lower() and "व्हाट्सएप" not in r.reply


def test_medium_frustration_cannot_end_the_call(make_call):
    c = make_call([turn("जी, माफ़ी चाहती हूँ। कब call करूँ?", ["frustration"]),
                   turn("జీ, చెప్పండి.", [("frustration", "medium")], outcome="ESCALATED_EXIT", end=True, lang="te-IN")])
    c.seller_turn(text="kitni baar call karoge")
    r = c.seller_turn(text="sare, Telugu lo matladukundam. cheppandi emi kavali?")
    assert r.call_outcome != "ESCALATED_EXIT"


@pytest.mark.parametrize("text", ["Ledu, ippudu meeting avasaram ledu. Malli call cheyoddu.",
                                  "vaddu, call cheyakandi. Thank you.", "వద్దు, call చేయకండి. Thank you.",
                                  "Just send everything on WhatsApp. No more calls."])
def test_telugu_do_not_call(text):
    assert "do_not_call" in sigs(text)


@pytest.mark.parametrize("text", ["Ippudu call cheyoddu thanks.", "abhi call mat karo, busy hoon",
                                  "ఇప్పుడు call చేయకండి", "Na na utna time hamara paas nahi hai ji."])
def test_not_now_is_busy_not_do_not_call(text):
    # "don't call NOW" was ended as DO_NOT_CALL in the demo; it means busy
    s = sigs(text)
    assert "do_not_call" not in s and "busy" in s


def test_repair_question_is_in_the_call_language(make_call):
    ask = turn("Shall I fix a meeting tomorrow?", qtype="goal_step", answered=False, lang="en-IN")
    c = make_call([ask, ask, ask], seller_state="Tamil Nadu")
    r = c.seller_turn(text="who is this?")
    assert not any("ऀ" <= ch <= "ॿ" for ch in r.reply)


def test_second_frustration_with_complaint_logs_the_complaint(make_call):
    c = make_call([turn("जी, माफ़ी चाहती हूँ। कब call करूँ?", ["frustration"])])
    c.seller_turn(text="baar baar phone kyun kar rahe ho")
    r = c.seller_turn(text="Paisa diya tha pehle, ek bhi lead nahi aayi, bahut pareshan ho gaya hoon")
    assert r.call_outcome == "COMPLAINT_LOGGED" and r.end_call and "support team" in r.reply


def test_whatsapp_declined_in_this_turn_is_not_offered(make_call):
    offer = turn("జీ, executive మీ profile చూస్తారు. WhatsApp లో details పంపనా?", lang="te-IN")
    c = make_call([offer] * 3, seller_state="Telangana")
    c.s["stage"], c.s["language"] = "goal_step", "te-IN"
    c.history.append({"speaker": "vani", "text": "WhatsApp లో details పంపనా?"})
    r = c.seller_turn(text="vaddu, WhatsApp kuda vaddu. executive emi chestaru?")
    assert "whatsapp" not in r.reply.lower()


def test_apology_is_said_once(make_call):
    again = turn("जी, बार-बार call करने के लिए माफ़ी चाहती हूँ। कल किस समय बात करें?")
    c = make_call([turn("जी, बार-बार call करने के लिए माफ़ी चाहती हूँ। क्या कल बात करें?", ["frustration"]), again, again, again])
    c.seller_turn(text="kitni baar call karoge")
    r = c.seller_turn(text="achha theek hai, bolo")
    assert "माफ़ी" not in r.reply


def test_fine_in_a_sentence_is_not_agreeing_to_the_meeting(make_call):
    # scenario 4: "kaam theek chal raha hai" after a 7 pm proposal closed the call as MEETING_FIXED
    c = make_call([turn("जी, समझ गई। enquiry कम आने की क्या वजह लगती है?", outcome="MEETING_FIXED", end=True),
                   turn("जी, समझ गई। enquiry कम आने की क्या वजह लगती है?")])
    c.s["stage"] = "goal_step"
    c.history.append({"speaker": "vani", "text": "क्या कल शाम 7 बजे की meeting सही रहेगी?"})
    c.seller_turn(text="kaam theek chal raha hai par enquiry bahut kam aati hai")
    assert c.outcome != "MEETING_FIXED"


def test_second_frustration_on_complaint_call_logs_the_complaint(make_call):
    c = make_call([])
    c.s["goal"], c.s["counts"]["frustration"] = "complaint_recovery", 1
    c.handle("frustration", "regex", "tum log disturb kar dete ho", "disturb")
    assert c.outcome == "COMPLAINT_LOGGED"


def test_answer_to_the_light_question_closes_a_respectful_exit_call(make_call):
    # master 4.2 (7+ calls): one light question, then close on the answer -- even if the LLM asks something else
    c = make_call([turn("आपको IndiaMART से कितनी बार call आना ठीक लगेगा?", qtype="contact")], bot_attempts=7)
    assert c.persona["goal"]["value"] == "respectful_exit"
    c.seller_turn(text="haan ji")
    r = c.seller_turn(text="nahi ji, kuch nahi")
    assert c.outcome == "RESPECTFUL_EXIT" and r.end_call and "कितनी बार" not in r.reply


def test_busy_seller_gets_a_short_turn(make_call):
    long = turn("ठीक है जी, मैं समझ गई। आपके Cotton Fabric business को बढ़ाने में मदद के लिए हमारे executive आपसे "
                "मिलकर पूरी जानकारी देंगे और आपकी profile भी बेहतर करेंगे। किस time call करूँ, या WhatsApp पर details भेज दूँ?")
    c = make_call([long, dict(long)])
    r = c.seller_turn(text="abhi busy hoon")
    assert c.s["mode"] == "BRIEF" and len(r.reply.split()) <= 1.5 * c.s["max_words"] and "?" in r.reply


def test_cost_question_is_answered_the_same_turn(make_call):
    # Chennai demo: "Is there any cost?" got a busy-style reply and the seller had to ask again
    skip = turn("जी, मैं समझ सकती हूँ। क्या कल 10 बजे बात करें?")
    c = make_call([skip, dict(skip)])
    r = c.seller_turn(text="Is there any cost for this visit? Am I paying anything?")
    assert "Charges" in r.reply and "free" not in r.reply.lower() and r.reply.index("Charges") < r.reply.index("?")


def test_time_given_in_goal_step_closes_the_slot(make_call):
    # Chennai demo: "Call back tomorrow at 10 AM. Thank you." got another question; the call never ended
    c = make_call([turn("जी, noted. क्या यही number सही है?", qtype="contact")])
    c.s["stage"], c.s["goal"] = "goal_step", "callback"
    c.seller_turn(text="Call back tomorrow at 10 AM. Thank you.")
    assert c.outcome == "CALLBACK_SCHEDULED"


def test_whatsapp_plus_no_more_calls_sends_and_records_dnc(make_call):
    # Chennai demo: "Just send everything on WhatsApp. No more calls." was read as declining WhatsApp
    c = make_call([], language="en-IN")
    c.seller_turn(text="Just send everything on WhatsApp. No more calls.")
    s = c.summary()
    assert s["final_outcome"] == "INFO_SENT" and s["do_not_call"] is True
    assert "whatsapp" not in c.declined_offers


def test_deflected_opening_moves_to_goal_ask_not_dead_end(make_call):
    # replay: the seller deflected the opening question; VANI's statement-only reply had no question
    dead = turn("जी, मैं समझ सकती हूँ।", qtype="none", answered=False)
    c = make_call([dead, dict(dead)])
    r = c.seller_turn(text="haan ji bataiye")
    assert "?" in r.reply and c.s["stage"] == "goal_step"


def test_declined_whatsapp_is_not_reselected_by_a_reason(make_call):
    # Telugu demo: meeting declined, WhatsApp offered and declined "with a reason" -> must not loop back
    c = make_call([turn("ठीक है जी, आप किस तरह संपर्क पसंद करेंगे?", qtype="contact", reason=True)])
    c.s["goal"], c.s["counts"]["refusals"] = "info_whatsapp", 1
    c.history.append({"speaker": "vani", "text": "क्या मैं details WhatsApp पर भेज दूँ?"})
    c.seller_turn(text="nahi chahiye, main khud dekh lunga")
    assert "whatsapp" in c.declined_offers
    assert c.s["goal"] == "respectful_exit"


def test_goodbye_is_in_the_language_asked_for_in_the_same_turn(make_call):
    c = make_call([])
    r = c.seller_turn(text="Telugu lo matladandi, malli call cheyakandi")
    assert r.call_outcome == "DO_NOT_CALL" and r.delivery["language"] == "te-IN"
    assert any("ఀ" <= ch <= "౿" for ch in r.reply)


def test_llm_failure_degrades_safely(make_call, monkeypatch):
    c = make_call([])
    monkeypatch.setattr(live_engine, "client", lambda: SimpleNamespace(chat=SimpleNamespace(
        completions=lambda **k: (_ for _ in ()).throw(RuntimeError("down")))))
    r = c.seller_turn(text="haan ji")
    assert r.reply and not r.end_call


def test_barge_in_keeps_only_what_was_heard(make_call):
    c = make_call([turn("जी, बिल्कुल। क्या मैं कल meeting रख दूँ?")])
    c.history[-1]["text"] = "नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। आपका काम अभी कैसा चल रहा है?"
    c.seller_turn(text="haan bolo jaldi", interrupted=True, heard_fraction=0.4)
    cut = c.history[-3]
    assert cut["interrupted"] and cut["text"].endswith("…") and "कैसा चल रहा है?" not in cut["text"]


def test_interrupted_opening_compresses(make_call):
    c = make_call([turn("जी, एक line में: buyers आपको ढूँढ रहे हैं। किस time बात करें?")])
    r = c.seller_turn(text="haan haan", interrupted=True, heard_fraction=0.3)
    assert "hangup_risk" in r.signals_tier1 and r.delivery["mode"] == "COMPRESSED"


# ---------------- contradictions and sarcasm (Chennai live session 3419775_20261009_231212) ----------------
def test_chennai_session_no_reask_and_sarcasm_backs_off(make_call):
    c = make_call([turn("जी, यह सुनकर खेद हुआ। आपका Clamps का काम अभी कैसा चल रहा है?", qtype="understanding", answered=False),
                   turn("जी, समझ सकती हूँ। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ?"),
                   turn("जी, यह जानकर अच्छा लगा। क्या online meeting fix कर लें?")] + [turn("जी, यह जानकर अच्छा लगा। क्या online meeting fix कर लें?")] * 3)
    r1 = c.seller_turn(text="Nahi achha nahi chal raha, bilkul achha nahi chal raha.")
    assert "कैसा चल रहा" not in r1.reply and c.s["stage"] == "goal_step"
    c.seller_turn(text="Bilkul kharab chal raha hai.")
    r3 = c.seller_turn(text="Are sab badhiya chal raha hai, itna badhiya business hai, mujhe inquiries bhi aa rahi hai, sab ho raha hai.")
    assert any(s["kind"] == "clarify" and s["signal"] == "sarcasm" for s in r3.switches)
    assert r3.delivery["mode"] == "CALM_EMPATHETIC" and "अच्छा लगा" not in r3.reply
    assert not live_engine._PITCH.search(r3.reply)


def test_genuine_flip_is_clarified_once_then_resolved(make_call):
    c = make_call([turn("जी, समझ गई। enquiries कितनी आती हैं?", qtype="clarify"),
                   turn("जी, बढ़िया। क्या मैं meeting रख दूँ?"),
                   turn("जी, executive इसमें मदद करेंगे। क्या कल meeting रख दूँ?"),
                   turn("जी। क्या कल 11 बजे ठीक रहेगा?")])
    c.seller_turn(text="kaam theek nahi chal raha")
    r = c.seller_turn(text="haan enquiry to aa rahi hai")
    assert "order नहीं बन रहे?" in r.reply and "meeting" not in r.reply
    entry = next(s for s in r.switches if s["kind"] == "clarify")
    assert entry["signal"] == "contradiction" and "turn 1" in entry["trigger"] and c.s["counts"]["goal_step"] == 0
    r = c.seller_turn(text="haan, order nahi ban rahe")
    assert any(s["signal"] == "clarify_resolved" and "no orders" in str(s["change_made"]) for s in r.switches)
    r = c.seller_turn(text="haan enquiry to aa rahi hai")
    assert sum(s.signal == "contradiction" for s in c.switch_log) == 1 and "order नहीं" not in r.reply
    assert [x["value"] for x in c.summary()["facts"]["business_status"]][:2] == ["bad", "mixed"]


def test_mixed_statement_is_not_a_contradiction():
    from facts import FactLedger, rule_facts
    led = FactLedger()
    led.add(rule_facts("kaam theek nahi chal raha", True), 1, "kaam theek nahi chal raha", "rules")
    facts = rule_facts("kaam theek hai par enquiry kam aati hai", True)
    assert facts["business_status"] == "mixed" and not led.contradictions(facts, 2, "kaam theek hai par enquiry kam aati hai")


def test_no_clarification_when_busy_or_complaining(make_call):
    c = make_call([turn("जी, समझ गई। किस time call करूँ?")] * 4)
    c.seller_turn(text="kaam theek nahi chal raha")
    r = c.seller_turn(text="abhi busy hoon, enquiry to aa rahi hai")
    assert c.s["mode"] == "BRIEF" and "order नहीं" not in r.reply and not c.clarified
    c2 = make_call([turn("जी, माफ़ी चाहती हूँ। support team आपको किस समय call करे?", ["complaint"])] * 4)
    c2.seller_turn(text="kaam theek nahi chal raha")
    r = c2.seller_turn(text="enquiry to aa rahi hai par paisa diya tha kuch nahi hua, leads hi nahi aate")
    assert "order नहीं" not in r.reply and not c2.clarified


def test_fact_rules():
    from facts import rule_facts, sarcasm_cues
    assert rule_facts("Nahi achha nahi chal raha", True) == {"business_status": "bad"}
    assert rule_facts("theek hai bhej do", True) == {}  # "theek hai" = okay, not a business report
    assert rule_facts("hamare executive Rakesh ji pehle se aate hain") == {"has_executive": "yes"}
    assert {"opener", "exaggeration"} <= set(sarcasm_cues("Are itna badhiya business hai"))


def test_filler_haan_on_a_contradiction_is_not_a_yes_to_the_offer(make_call):
    # suite run: "haan enquiry to aa rahi hai" after a WhatsApp offer closed INFO_SENT instead of clarifying
    sent = turn("मैं details आपको WhatsApp पर भेज रही हूँ।", outcome="INFO_SENT", end=True)
    c = make_call([turn("जी, समझ गई। क्या मैं WhatsApp पर details भेज दूँ?"), sent, dict(sent), dict(sent)])
    c.seller_turn(text="kaam theek nahi chal raha")
    r = c.seller_turn(text="haan enquiry to aa rahi hai")
    assert c.outcome == "IN_PROGRESS" and "order नहीं बन रहे?" in r.reply


def test_bad_business_report_is_neither_a_refusal_nor_a_yes(make_call):
    # suite run on the Chennai lines: the LLM called "Nahi achha nahi chal raha" not_interested, and
    # "Bilkul kharab chal raha hai" opened with "bilkul" and was taken as a yes to WhatsApp (INFO_SENT)
    sent = turn("मैं details आपको WhatsApp पर भेज रही हूँ।", ["not_interested"], outcome="INFO_SENT", end=True)
    c = make_call([turn("जी, समझ गई। क्या मैं WhatsApp पर details भेज दूँ?", ["not_interested"]), sent, dict(sent), dict(sent)])
    c.seller_turn(text="Nahi achha nahi chal raha, bilkul achha nahi chal raha.")
    c.seller_turn(text="Bilkul kharab chal raha hai.")
    assert c.outcome == "IN_PROGRESS" and c.s["counts"]["refusals"] == 0 and c.s["goal"] != "respectful_exit"
    assert live_engine._agrees("bilkul theek hai") and not live_engine._agrees("Bilkul kharab chal raha hai")


def test_sarcasm_counts_as_one_frustration_not_two(make_call, monkeypatch):
    # suite run: the LLM's frustration signal and the sarcasm path both counted the same line -> ESCALATED_EXIT
    sar = turn("जी, माफ़ी चाहती हूँ। क्या मैं WhatsApp पर details भेज दूँ?", ["frustration"])
    sar["sarcasm"] = "clear"
    pitch = turn("जी, समझ सकती हूँ। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ?")
    c = make_call([])

    class ByText(FakeLLM):  # the reply depends on the seller's line, not on how many retries ran before
        def _complete(self, **kw):
            self.last = sar if "badhiya" in kw["messages"][-1]["content"] else pitch
            return super()._complete(**kw)
    monkeypatch.setattr(live_engine, "client", lambda: ByText([]))
    c.seller_turn(text="Nahi achha nahi chal raha, bilkul achha nahi chal raha.")
    c.seller_turn(text="Bilkul kharab chal raha hai.")
    r = c.seller_turn(text="Are sab badhiya chal raha hai, itna badhiya business hai, sab ho raha hai.")
    assert not r.end_call and c.s["counts"]["frustration"] == 1 and r.delivery["mode"] == "CALM_EMPATHETIC"


def test_short_lines_do_not_flip_the_language():
    # Chennai session 3419775_20261009_223707: Saaras labelled "Vani catalog." and "Kaun si details?" en-IN and
    # the call flipped Hindi -> English -> Hindi on every turn
    from signal_detector import guess_language
    cur, prev = "en-IN", None
    for text, stt in [("Chaudah bada hai ji.", "hi-IN"), ("Vani catalog.", "en-IN"), ("Meeting nahi chahiye.", "hi-IN"),
                      ("Kaun si details?", "en-IN"), ("Nahi mujhe kuch nahi chahiye, aap mera peecha chhod do bas.", "hi-IN")]:
        hit = detect_language_switch(text, cur, stt, prev)
        cur = hit.target_language if hit else cur
        prev = guess_language(text, stt)
        if text != "Chaudah bada hai ji.":
            assert cur == "hi-IN", text
    assert guess_language("Kaun si details?", "en-IN") == "hi-IN"
    assert detect_language_switch("What details?", "hi-IN", "en-IN", None) is None          # short: wait a turn
    assert detect_language_switch("What details?", "hi-IN", "en-IN", "en-IN").target_language == "en-IN"


def test_llm_cannot_flip_language_on_a_hindi_line(make_call):
    c = make_call([turn("I can share how our executive helps. Shall I send the details on WhatsApp?", ["language_switch"],
                        lang="en-IN")] * 3)
    r = c.seller_turn(text="Kaun si details?")
    assert r.delivery["language"] == "hi-IN"


def test_failed_retries_still_repair_the_last_good_reply(make_call, monkeypatch):
    # scenario suite: the correction retries ran out of tokens mid-JSON and the first reply -- an unsupported
    # RESPECTFUL_EXIT -- was returned unrepaired, closing the call on a neutral line
    bye = turn("जी, समझ गई। समय देने के लिए धन्यवाद।", outcome="RESPECTFUL_EXIT", end=True)
    c = make_call([])
    c.seller_turn(text="haan ji")
    calls = []

    def broken(**kw):
        calls.append(1)
        content = json.dumps(bye, ensure_ascii=False) if len(calls) == 1 else '{"seller_act": "deny", "reply": "'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    monkeypatch.setattr(live_engine, "client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=broken), text=FakeLLM([]).text))
    r = c.seller_turn(text="achha, aur bataiye")
    assert not r.end_call and c.outcome == "IN_PROGRESS" and r.reply.strip().endswith("?")
    assert any(g["kind"] == "llm_error" for g in c.guard_corrections)


def test_right_persons_number_closes_the_contact_update(make_call):
    # suite run: the name and number were given and the LLM asked about the person's role instead of closing
    c = make_call([turn("जी, समझ गई। क्या आप सही व्यक्ति का नाम और number बता सकते हैं?", ["not_right_person"], qtype="contact"),
                   turn("ठीक है जी। क्या वो owner हैं?", qtype="contact")])
    c.seller_turn(text="main owner nahi hoon, sir se baat kijiye")
    r = c.seller_turn(text="unka naam Ramesh hai, number 9876543210")
    assert c.outcome == "CONTACT_UPDATED" and r.end_call and "connect" in r.reply
    assert r.reply.count("ठीक है") == 1 and "owner" not in r.reply


# ---------------- persuading frustrated-but-engaged sellers (live session 3419775_20261010_125638) ----------------
def test_session_125638_replayed_never_offers_another_call_and_never_cuts_a_talking_seller(make_call):
    callback = turn("मुझे सच में बहुत खेद है। क्या मैं आपको कल सुबह 10 बजे के आसपास call कर लूँ?", ["frustration"])
    c = make_call([callback] * 6)
    r1 = c.seller_turn(text="")
    assert "आवाज़" in r1.reply and not r1.end_call
    r2 = c.seller_turn(text="Yaar kyon baar baar phone karte ho?")
    assert r2.delivery["mode"] == "CALM_EMPATHETIC"                           # frustration outranks the audio check
    assert "10 बजे" not in r2.reply and "call कर लूँ" not in r2.reply and "WhatsApp" in r2.reply
    # second frustration, but the seller says he is talking: apologise and give him the floor (no cut, no question)
    r3 = c.seller_turn(text="Abhi main bol raha hoon baar baar call karte ho, kal phir se call karogi aap log.")
    assert not r3.end_call and c.outcome == "IN_PROGRESS" and "बताइए" in r3.reply and "?" not in r3.reply


def test_wants_out_twice_still_ends_the_call(make_call):
    c = make_call([turn("जी, माफ़ी चाहती हूँ। क्या मैं WhatsApp पर details भेज दूँ?", ["frustration"])] * 4)
    assert not c.seller_turn(text="phone rakho").end_call
    r = c.seller_turn(text="phone rakho yaar, band karo")
    assert r.end_call and r.call_outcome == "ESCALATED_EXIT"


def test_final_refusal_phrases_close_at_once_without_a_pitch(make_call):
    ask = turn("जी, समझ सकती हूँ। क्या 15 मिनट की meeting रख दूँ?", ["not_interested"])
    for line in ("abhi zaroorat nahi", "galti se dekh liya, phone rakhiye", "zaroorat hogi toh khud baat kar lunga"):
        c = make_call([ask, dict(ask)])
        r = c.seller_turn(text=line)
        assert r.call_outcome == "RESPECTFUL_EXIT" and r.end_call and "meeting" not in r.reply, line
        assert "WhatsApp" not in r.reply, line


# ---------------- IndiaMART master prompt additions (10 Oct 2026) ----------------
def test_buylead_question_gets_the_dashboard_not_a_meeting(make_call):
    c = make_call([turn("जी, हमारे executive दिखा देंगे। क्या कल meeting रख दूँ?")] * 3)
    r = c.seller_turn(text="aur buy leads kahan milenge?")
    assert "seller dashboard" in r.reply and "BuyLeads" in r.reply and "app" in r.reply
    assert "meeting" not in r.reply.lower() and "intermesh" not in r.reply   # the address is not spoken
    r = c.seller_turn(text="buyer ka number do")                              # asked again -> WhatsApp details
    assert "WhatsApp" in r.reply and c.s["goal"] == "info_whatsapp"


def test_llm_buylead_turn_never_pitches_a_meeting(make_call):
    c = make_call([turn("Buyers ki details executive dikha denge. Kya kal 11 baje meeting rakh doon?",
                        ["buylead_query"], lang="hi-IN")] * 3)
    c.s["stage"] = "goal_step"
    r = c.seller_turn(text="woh sab kaise dikhega mujhe?")   # no tier-1 match: only the LLM saw the buy-lead question
    assert "meeting" not in r.reply.lower() and "seller dashboard" in r.reply


def test_company_opening_starts_with_the_bot_name(make_call):
    p = generate_persona(seller(company_name="Shree Clamps Pvt Ltd")).to_dict()
    op = p["conversation_plan"]["opening"]["value"]
    assert op.startswith("नमस्ते, मैं IndiaMART से Payal") and "Shree Clamps Pvt Ltd" in op and op.endswith("?")
    assert "virtual assistant" not in op and p["conversation_plan"]["context_in_first_reply"]


def test_virtual_assistant_only_when_asked(make_call):
    va = turn("जी, मैं IndiaMART की virtual assistant हूँ। आपका काम कैसा चल रहा है?", qtype="understanding")
    c = make_call([va, dict(va), dict(va)])
    r = c.seller_turn(text="haan ji bataiye")
    assert "virtual assistant" not in r.reply
    c2 = make_call([turn("जी, मैं IndiaMART की virtual assistant Payal हूँ। आपका काम कैसा चल रहा है?",
                         ["ai_bot_suspicion"], qtype="understanding")])
    assert "virtual assistant" in c2.seller_turn(text="aap robot ho kya?").reply


def test_meeting_slots_follow_the_window():
    # IndiaMART, 10 Oct 2026: 9 AM to 6 PM, a calendar day from tomorrow, never today
    import datetime as dt
    import slots
    for text, ok in [("kal subah 8 baje", False), ("kal shaam 8 baje", False), ("aaj 3 baje", False),
                     ("kal subah 9 baje", True), ("kal subah 10 baje", True), ("kal shaam 6 baje", True),
                     ("kal shaam 7 baje", False), ("kal shaam 6:30 baje", False), ("parso dopahar 2 baje", True),
                     ("कल रात 8 बजे", False), ("Tomorrow 4 pm", True)]:
        assert slots.is_valid_meeting(slots.parse(text)) is ok, text
    assert slots.parse("bas 15 minute") is None
    sat = dt.date(2026, 10, 10)
    assert slots.when(slots.parse("kal subah 11 baje"), sat) == dt.datetime(2026, 10, 11, 11, 0)
    assert slots.when(slots.parse("Monday 11 am"), sat) == dt.datetime(2026, 10, 12, 11, 0)


def test_meeting_offer_outside_the_window_becomes_two_slots(make_call):
    late = turn("जी, समझ गई। क्या कल शाम 8 बजे meeting रख दूँ?", ["need_few_enquiries"])
    c = make_call([late, dict(late), dict(late)])
    r = c.seller_turn(text="enquiry bahut kam aati hai")
    assert "8 बजे" not in r.reply and "11 बजे" in r.reply and "4 बजे" in r.reply


def test_seller_time_outside_the_window_gets_the_nearest_slot(make_call):
    fixed = turn("ठीक है।", outcome="MEETING_FIXED", end=True, slot="kal shaam 8 baje")
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), fixed, dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    r = c.seller_turn(text="kal shaam 8 baje")
    assert c.outcome == "IN_PROGRESS" and "नौ से शाम छह" in r.reply and "6 बजे" in r.reply
    r = c.seller_turn(text="kal shaam 6 baje, online")                  # inside the window, format given -> fixed
    assert c.outcome == "MEETING_FIXED" and "6 बजे" in r.reply


def test_banned_phrases_are_removed(make_call):
    bad = turn("जी, मैं ध्यान से सुन रही हूँ। आसान शब्दों में: buyers आपको ढूँढ रहे हैं। क्या मैं details भेज दूँ?")
    c = make_call([bad, dict(bad), dict(bad)])
    r = c.seller_turn(text="haan ji")
    assert "ध्यान से सुन" not in r.reply and "आसान शब्दों" not in r.reply


def test_indiamart_is_spoken_so_bulbul_does_not_say_india_art():
    from voice_synth import speakable
    assert speakable("मैं IndiaMART से Payal बोल रही हूँ, BuyLeads देखिए", "hi-IN") == "मैं इंडियामार्ट से Payal बोल रही हूँ, बाय लीड्स देखिए"
    assert speakable("Payal from IndiaMART", "en-IN") == "Payal from India Mart"


def test_llm_label_alone_never_unlocks_virtual_assistant(make_call):
    # live session 19070168_20261010_151033: the LLM tagged "Enna maadhiri?" / "kaun bol raha hai?" as a bot question
    va = turn("जी, मैं IndiaMART की virtual assistant Payal हूँ। आपका काम कैसा चल रहा है?", ["ai_bot_suspicion"], qtype="understanding")
    c = make_call([va] * 6)
    for line in ("Enna maadhiri?", "kaun bol raha hai?"):
        assert "virtual" not in c.seller_turn(text=line).reply.lower(), line
    assert "virtual" in c.seller_turn(text="aap robot ho kya?").reply.lower()


def test_frustrated_seller_asking_something_real_is_not_cut(make_call):
    # IndiaMART, 10 Oct 2026: never cut the call while the seller is asking
    c = make_call([turn("जी, माफ़ी चाहती हूँ। Charges आपके plan के हिसाब से होते हैं। क्या मैं details WhatsApp पर भेज दूँ?",
                        ["frustration"])] * 3)
    c.seller_turn(text="kitni baar call karoge")
    r = c.seller_turn(text="pareshan ho gaya hoon, ye bataiye charge kitna lagta hai?")
    assert not r.end_call and c.outcome == "IN_PROGRESS"


def test_glad_is_never_said_to_bad_news(make_call):
    glad = turn("जी, यह जानकर अच्छा लगा। क्या कल सुबह 11 बजे या परसों शाम 4 बजे ठीक रहेगा?")
    c = make_call([glad] * 3)
    c.seller_turn(text="haan ji")
    r = c.seller_turn(text="kaam bilkul kharab chal raha hai")
    assert "अच्छा लगा" not in r.reply and "?" in r.reply


def test_choosing_an_option_goes_to_the_gate_even_if_the_llm_does_not_propose_it(make_call):
    nofix = turn("जी, बढ़िया। executive आपकी profile देखेंगे। और कुछ जानना चाहेंगे?")
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), nofix, dict(nofix)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    assert "परसों शाम 4 बजे" in c.seller_turn(text="dusra wala theek rahega").reply
    r = c.seller_turn(text="online kar lo")
    assert r.call_outcome == "MEETING_FIXED" and c.summary()["meeting"]["format"] == "online"


def test_executive_seller_gets_the_account_manager_offer_and_a_need_becomes_a_meeting(make_call):
    # master intent 8, word for word; a described doubt -> MEETING with two slots; "nothing more" -> EXEC_HANDOFF
    ask = turn("जी, बढ़िया। आप executive से क्या बात करना चाहेंगे?")
    c = make_call([ask] * 3)
    r = c.seller_turn(text="hamare executive Rakesh ji pehle se aate hain")
    assert "account manager" in r.reply and r.delivery["goal"] == "exec_handoff"
    r = c.seller_turn(text="unse bolna hamara catalog update karna hai")
    assert r.delivery["goal"] == "meeting" and "11 बजे" in r.reply and "4 बजे" in r.reply
    c2 = make_call([ask] * 3)
    c2.seller_turn(text="hamare executive Rakesh ji pehle se aate hain")
    r = c2.seller_turn(text="nahi ji, aur kuch nahi")
    assert c2.outcome == "EXEC_HANDOFF" and r.end_call


def test_no_time_to_meet_makes_it_online_not_a_callback(make_call):
    # master section 11 meeting example, the seller's lines
    online = turn("जी, कोई बात नहीं, online कर लेते हैं। कल सुबह 11 बजे online ठीक रहेगा?", ["busy"])
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["interest"]),
                   turn("बहुत अच्छा जी। मिलकर या online?"), online, dict(online)])
    c.seller_turn(text="haan ji")
    c.seller_turn(text="haan bataiye")
    c.seller_turn(text="haan theek hai")
    r = c.seller_turn(text="milne ka time nahi hai")
    assert r.delivery["goal"] == "meeting" and c.outcome == "IN_PROGRESS"
    r = c.seller_turn(text="haan")
    assert c.outcome == "MEETING_FIXED" and "online" in r.reply and c.summary()["meeting"]["format"] == "online"


def test_filler_haan_on_a_contradiction_is_not_a_yes_to_the_slots(make_call):
    # suite run: "haan enquiry to aa rahi hai" after the two-slot offer was taken as a yes to 11 AM
    slots_q = turn("जी, समझ गई। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?")
    c = make_call([slots_q] * 4)
    c.seller_turn(text="kaam theek nahi chal raha")
    r = c.seller_turn(text="haan enquiry to aa rahi hai")
    assert "order नहीं बन रहे?" in r.reply and "मिलकर या online" not in r.reply and not c.meeting_pending


def test_llm_never_decides_the_slot_for_the_seller(make_call):
    # suite run: "haan bataiye" -> "to kal subah 11 baje rakh leti hoon, milkar ya online?" (no slot was chosen)
    decided = turn("बहुत अच्छा जी। तो कल सुबह 11 बजे रख लेती हूँ, मिलकर या online?", ["interest"])
    c = make_call([decided] * 4)
    c.seller_turn(text="haan ji")
    r = c.seller_turn(text="haan bataiye")
    assert "रख लेती" not in r.reply and "11 बजे" in r.reply and "4 बजे" in r.reply and not c.meeting_pending


def test_bare_yes_to_meeting_or_whatsapp_is_not_a_whatsapp_yes(make_call):
    either = turn("ठीक है।", outcome="INFO_SENT", end=True)
    c = make_call([either] * 3)
    c.s["stage"] = "goal_step"
    c.history.append({"speaker": "vani", "text": "जी, online कर लेते हैं। कल सुबह 11 बजे online ठीक रहेगा, या WhatsApp पर details भेज दूँ?"})
    r = c.seller_turn(text="haan")
    assert c.outcome != "INFO_SENT"
    assert c.outcome == "MEETING_FIXED" and "online" in r.reply      # the first option, the format it named


def test_yes_to_a_callback_time_is_a_callback_not_a_meeting(make_call):
    cb = turn("ठीक है, हम आपको कल शाम 6 बजे call करेंगे।", outcome="CALLBACK_SCHEDULED", end=True, slot="कल शाम 6 बजे")
    c = make_call([cb] * 3)
    c.s["stage"], c.s["goal"] = "goal_step", "callback"
    c.history.append({"speaker": "vani", "text": "क्या मैं आपको कल शाम 6 बजे call करूँ?"})
    c.seller_turn(text="haan theek hai")
    assert c.outcome == "CALLBACK_SCHEDULED" and not c.meeting_pending


# ---------------- performance: same words, fewer round trips ----------------
def test_mechanical_problem_is_repaired_without_another_llm_call(make_call, monkeypatch):
    calls = []
    male = turn("जी, मैं समझ गई। क्या मैं details WhatsApp पर भेज दूँ?")
    c = make_call([male] * 3, annual_turnover="5 - 25 Cr")          # male voice (Rohan)
    fake = live_engine.client()
    orig = fake.chat.completions
    monkeypatch.setattr(fake.chat, "completions", lambda **k: (calls.append(1), orig(**k))[1])
    c.seller_turn(text="haan ji")                                     # fixed first reply, no LLM
    r = c.seller_turn(text="achha, aur bataiye")
    assert len(calls) == 1 and "समझ गया" in r.reply and "समझ गई" not in r.reply


def test_tts_sentences_in_parallel_joined_and_cached(monkeypatch, tmp_path):
    import base64
    import io
    import wave
    import voice_synth
    made = []

    def wav(n):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(22050)
            w.writeframes(b"\x01\x00" * n)
        return buf.getvalue()

    def convert(**k):
        made.append(k["text"])
        return SimpleNamespace(audios=[base64.b64encode(wav(1000)).decode()])
    monkeypatch.setattr(voice_synth, "client", lambda: SimpleNamespace(text_to_speech=SimpleNamespace(convert=convert)))
    monkeypatch.setattr(voice_synth, "CACHE_DIR", tmp_path)
    voice_synth._MEM.clear()
    text = "जी, बहुत अच्छा। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?"
    a = voice_synth.synthesize(text, "ishita_enhi_customer", "hi-IN", 0.93)
    assert len(made) == 2                                             # one request per sentence
    with wave.open(io.BytesIO(a)) as w:
        assert w.getnframes() == 2000 + int(voice_synth.SENTENCE_GAP_S * 22050)
    voice_synth._MEM.clear()
    assert voice_synth.synthesize(text, "ishita_enhi_customer", "hi-IN", 0.93) and len(made) == 2   # from disk
    voice_synth.synthesize("जी, बहुत अच्छा।", "ishita_enhi_customer", "hi-IN", 0.93)
    assert len(made) == 2                                             # a sentence said before is reused


def test_padded_json_cut_by_the_stop_sequence_is_recovered_as_written():
    # live bench: the model wrote the whole answer, then blank lines until max_tokens instead of the last fields
    cut = ('{\n  "seller_act": "statement",\n  "seller_signals": [],\n  "seller_language": "hi-IN",\n  "signal_reason": "x",\n'
           '  "seller_insights": {},\n  "understanding_answered": false,\n  "refused_with_reason": false,\n  "slot": "",\n'
           '  "reply": "जी, समझ गई। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?",\n  "question_type": "goal_step",\n'
           '  "call_outcome": "IN_PROGRESS",\n  "end_call": false,\n  "fact_update": ""\n  ')
    d = live_engine.parse_turn_json(cut)
    assert d["reply"].endswith("क्या ठीक रहेगा?") and d["sarcasm"] == "no" and d["clarify_fact"] == "" and d["end_call"] is False
    with pytest.raises(json.JSONDecodeError):
        live_engine.parse_turn_json('{\n  "seller_act": "statement",\n  "reply": "जी, समझ')   # cut inside the reply: retry
    assert "\n  \n  \n" not in json.dumps({"reply": "a\n\n\nb"}, indent=2)                   # never inside valid JSON


# ---------------- IndiaMART, 10 Oct 2026 (2): 9 AM-6 PM, fixed timings, silence, background voices ----------------
def test_seller_insisting_on_other_hours_is_told_timings_are_fixed_and_gets_whatsapp(make_call):
    fixed = turn("ठीक है।", outcome="MEETING_FIXED", end=True)
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), fixed, dict(fixed),
                   dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    r = c.seller_turn(text="kal raat 8 baje")
    assert c.outcome == "IN_PROGRESS" and "नौ से शाम छह" in r.reply                      # told once, nearest slot offered
    r = c.seller_turn(text="nahi, raat 8 baje hi ho payega")
    assert r.end_call and c.outcome == "INFO_SENT" and "fixed" in r.reply and "WhatsApp" in r.reply


def test_no_to_the_inside_slot_asking_for_other_hours_also_closes(make_call):
    fixed = turn("ठीक है।", outcome="MEETING_FIXED", end=True)
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), fixed, dict(fixed),
                   dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    c.seller_turn(text="subah 7 baje")
    r = c.seller_turn(text="nahi, main sirf subah jaldi free hota hoon")
    assert c.outcome == "INFO_SENT" and r.end_call


def test_agreeing_to_the_slot_inside_the_window_is_not_insisting(make_call):
    fixed = turn("ठीक है।", outcome="MEETING_FIXED", end=True)
    c = make_call([turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?", ["need_few_enquiries"]), fixed, dict(fixed),
                   dict(fixed)])
    c.seller_turn(text="enquiry bahut kam aati hai")
    c.seller_turn(text="kal raat 8 baje")
    r = c.seller_turn(text="achha theek hai, 6 baje kar lo")
    assert c.outcome == "IN_PROGRESS" and "6 बजे" in r.reply and "online" in r.reply      # then in person / online


def test_silence_asks_if_they_were_saying_something_then_the_first_reply_follows(make_call):
    c = make_call([])
    r = c.seller_turn(text="")
    assert r.reply == "माफ़ कीजिए, आपकी आवाज़ ठीक से नहीं आ रही। क्या आप कुछ कह रहे थे?" and not r.end_call
    r = c.seller_turn(text="haan ji")
    assert r.reply == c.persona["conversation_plan"]["first_reply"]


def test_background_noise_or_backchannel_over_vani_is_not_an_interruption(make_call):
    c = make_call([turn("जी, बिल्कुल। क्या कल meeting रख दूँ?")] * 2)
    c.seller_turn(text="haan ji")                                      # past the greeting
    before = [dict(h) for h in c.history]
    for heard in ("", "hmm", "haan ji", "achha theek hai"):
        r = c.seller_turn(text=heard, interrupted=True, heard_fraction=0.3)
        assert r.ignored and r.reply == "" and c.turn == 1 and c.history == before, heard
    r = c.seller_turn(text="ek minute, mera sawaal hai", interrupted=True, heard_fraction=0.3)   # real words: a turn
    assert not r.ignored and c.turn == 2


def test_slots_are_found_when_the_format_question_comes_last(make_call):
    # suite run: "kal 11 baje ya parso 4 baje, kya theek rahega? milkar ya online?" -> "haan theek hai" was not taken
    both = turn("जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा? मिलकर या online?", ["interest"])
    again = turn("बहुत अच्छा जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?")
    c = make_call([both, again, dict(again)])
    c.seller_turn(text="haan ji")
    c.seller_turn(text="haan bataiye")
    r = c.seller_turn(text="haan theek hai")
    assert c.meeting_pending and "कल सुबह 11 बजे" in r.reply and "online" in r.reply and "परसों" not in r.reply


def test_vani_never_says_ji(make_call):
    # IndiaMART, 10 Oct 2026: not in the greeting, fixed lines, closings, or the LLM's own words
    from text_normalize import drop_ji
    assert drop_ji("कोई बात नहीं जी। समय देने के लिए धन्यवाद।") == "कोई बात नहीं। समय देने के लिए धन्यवाद।"
    assert drop_ji("Okay. Ji, noted.") == "Okay. Noted." and drop_ji("Sure ji, your manager") == "Sure, your manager"
    assert drop_ji("जी हाँ, बिल्कुल।") == "हाँ, बिल्कुल।" and drop_ji("जीवन ज़रूरी है जी?") == "जीवन ज़रूरी है?"
    ji = re.compile(r"(?<![A-Za-z])ji(?![A-Za-z])|(?<![ऀ-ॣ०-ॿ])जी(?![ऀ-ॣ०-ॿ])", re.I)
    llm = turn("जी, बिल्कुल जी। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा जी?")
    for over in ({}, {"bot_attempts": 5}, {"seller_state": "Tamil Nadu"}, {"annual_turnover": "5 - 25 Cr"}):
        c = make_call([llm] * 6, **over)
        lines = [c.history[0]["text"]]
        for said in ("haan ji", "haan ji bataiye", "nahi chahiye", "nahi ji, interest nahi hai"):
            if c.ended:
                break
            lines.append(c.seller_turn(text=said).reply)
        assert not any(ji.search(x) for x in lines), (over, lines)

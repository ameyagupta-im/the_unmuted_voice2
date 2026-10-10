"""Phase 1 integrations and evaluation plumbing (offline: every integration in dry-run mode)."""
import io
import json
import sys
import wave
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import hangup_model  # noqa: E402
import live_engine  # noqa: E402
from integrations import base, crm, on_call_end, suppression, whatsapp  # noqa: E402
from persona_generator import generate_persona  # noqa: E402
from test_offline import FakeLLM, seller  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Logs and the suppression DB go to a temp dir; every live flag off."""
    monkeypatch.setattr(base, "LOG_DIR", tmp_path)
    monkeypatch.setattr(suppression, "LOG_DIR", tmp_path)
    monkeypatch.setattr(suppression, "DB", tmp_path / "suppression.db")
    monkeypatch.setattr(base, "load_env", lambda: None)
    for flag in ("VANI_WHATSAPP_LIVE", "VANI_CRM_LIVE", "VANI_DND_LIVE", "VANI_TELEPHONY_LIVE", "VANI_ENFORCE_CALL_HOURS"):
        monkeypatch.delenv(flag, raising=False)
    return tmp_path


def lines(path):
    return [json.loads(x) for x in open(path, encoding="utf-8")] if path.exists() else []


@pytest.fixture
def call(monkeypatch):
    def _make(**over):
        monkeypatch.setattr(live_engine, "client", lambda: FakeLLM([]))
        monkeypatch.setattr(hangup_model, "threshold", lambda: 2.0)
        c = live_engine.LiveCall(generate_persona(seller(**over)).to_dict(), synthesize_audio=False)
        c.start()
        return c
    return _make


# ---------------- CRM ----------------
def test_crm_maps_outcomes_to_existing_disposition_labels():
    assert set(crm.DISPOSITION_LABEL.values()) <= {"Meeting Fixed", "Not Interested", "General", "Call Later", "Busy"}
    assert set(crm.DISPOSITION_LABEL) >= set(live_engine.ENDINGS) | {"IN_PROGRESS"}


def test_on_call_end_info_sent_sends_whatsapp_and_writes_crm(call, isolated):
    c = call()
    c.seller_turn(text="WhatsApp pe details bhej do")                   # the seller asked -> INFO_SENT, closed
    done = on_call_end(c, "t1", phone="+91 98765 43210")
    assert done["whatsapp"]["mode"] == "dry_run" and done["whatsapp"]["to"].endswith("3210")
    assert "98765" not in json.dumps(lines(isolated / "whatsapp.jsonl"))  # numbers are masked in logs
    rec = lines(isolated / "crm.jsonl")[-1]
    assert rec["vani_outcome"] == "INFO_SENT" and rec["disposition_label"] == "General" and rec["completed"]


def test_nothing_is_sent_on_whatsapp_unless_the_seller_agreed(call, isolated):
    c = call()
    c.seller_turn(text="nahi chahiye")
    c.seller_turn(text="nahi chahiye, interest nahi hai")
    assert c.outcome == "RESPECTFUL_EXIT" and "whatsapp" not in on_call_end(c, "t2", phone="+91 98765 43210")


def test_confirmed_meeting_sends_a_clear_whatsapp_confirmation(call, isolated):
    from integrations import whatsapp
    m = whatsapp.meeting_text({"at": "2026-10-12T16:00", "format": "online"}, "hi-IN")
    assert m == {"date": "सोमवार, 12 अक्टूबर 2026", "time": "4:00 PM", "format": "Online (video call)"}
    assert whatsapp.meeting_text({"at": "2026-10-11T11:00", "format": "in_person"}, "en-IN")["date"] == "Sunday, 11 October 2026"


def test_do_not_call_goes_on_the_suppression_list_and_blocks_the_next_call(call):
    c = call()
    c.seller_turn(text="mujhe dobara call mat karna")
    on_call_end(c, "t2")
    assert suppression.is_suppressed(1)
    clearance = suppression.check(1)
    assert not clearance.allowed and "do-not-call" in clearance.reasons[0]


def test_abandoned_call_writes_crm_only(call, isolated):
    c = call()
    done = on_call_end(c, "t3")
    assert set(done) == {"crm"} and lines(isolated / "crm.jsonl")[-1]["completed"] is False


# ---------------- live flags never fall back silently ----------------
def test_live_flag_without_credentials_is_an_error(monkeypatch):
    monkeypatch.setenv("VANI_WHATSAPP_LIVE", "1")
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    with pytest.raises(RuntimeError, match="WHATSAPP_TOKEN"):
        whatsapp.send_details(1, "9876543210", "Clamps", "hi-IN")


def test_whatsapp_template_payload():
    p = whatsapp.build_payload("+91 98765-43210", "Clamps", "hi-IN", "vani_details")
    assert p["to"] == "919876543210" and p["template"]["language"]["code"] == "hi"


# ---------------- calling hours ----------------
NIGHT = datetime(2026, 10, 9, 22, 30, tzinfo=suppression.IST)
DAY = datetime(2026, 10, 9, 11, 0, tzinfo=suppression.IST)


def test_calling_hours_warn_in_demo_and_block_when_enforced(monkeypatch):
    assert suppression.check(7, now=DAY).allowed and not any("hours" in w for w in suppression.check(7, now=DAY).warnings)
    night = suppression.check(7, now=NIGHT)
    assert night.allowed and any("calling hours" in w for w in night.warnings)
    monkeypatch.setenv("VANI_ENFORCE_CALL_HOURS", "1")
    assert not suppression.check(7, now=NIGHT).allowed


def test_call_window_is_configurable(monkeypatch):
    monkeypatch.setenv("VANI_CALL_HOURS", "10:00-18:00")
    assert not suppression.in_window(datetime(2026, 10, 9, 9, 30, tzinfo=suppression.IST))
    assert suppression.in_window(datetime(2026, 10, 9, 17, 59, tzinfo=suppression.IST))


# ---------------- disclosure ----------------
def test_disclosure_flag_off_by_default_on_when_asked(monkeypatch):
    monkeypatch.delenv("VANI_DISCLOSE_RECORDING", raising=False)
    assert "record" not in generate_persona(seller()).conversation_plan["opening"].value
    # recording notice only: "virtual assistant" is said only when the seller asks (IndiaMART, 10 Oct 2026)
    hi = generate_persona(seller(), disclose_recording=True).conversation_plan["opening"].value
    assert "record" in hi and "virtual assistant" not in hi
    en = generate_persona(seller(seller_state="Tamil Nadu"), disclose_recording=True).conversation_plan["opening"].value
    assert "recorded" in en and "virtual assistant" not in en and en.strip().endswith("?")


# ---------------- evaluation plumbing ----------------
def test_split_is_by_call_and_stable():
    from build_eval_set import split_of_call
    ids = range(1000, 3000)
    assert all(split_of_call(i) == split_of_call(i) for i in ids)
    share = sum(split_of_call(i) == "dev" for i in ids) / len(ids)
    assert 0.65 < share < 0.75


def test_wer_and_phone_band():
    from compare_stt_modes import to_phone, wer
    assert wer("WhatsApp pe details bhej do", "whats app pe details bhej do") == 0
    assert wer("a b c d", "a x c") == 0.5
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(22050), w.writeframes(b"\x00\x01" * 22050)
    with wave.open(io.BytesIO(to_phone(buf.getvalue())), "rb") as w:
        assert w.getframerate() == 8000 and abs(w.getnframes() - 8000) <= 1

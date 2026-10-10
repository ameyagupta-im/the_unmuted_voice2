"""Sarvam deployment (Phase A): the agent instruction, per-seller variables, API bodies, campaign files.
Offline: every Sarvam request is a dry run."""
import csv
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_campaign  # noqa: E402
import sarvam_api  # noqa: E402
from integrations import base, suppression  # noqa: E402
from persona_generator import generate_persona  # noqa: E402
from sarvam_platform import (INPUT_VARIABLES, OUTPUT_VARIABLES, agent_bundle, agent_key, agent_variables_for,  # noqa: E402
                             build_instruction, missing_placeholders, voice_agents)
from test_offline import seller  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "LOG_DIR", tmp_path)
    monkeypatch.setattr(suppression, "LOG_DIR", tmp_path)
    monkeypatch.setattr(suppression, "DB", tmp_path / "suppression.db")
    monkeypatch.setattr(base, "load_env", lambda: None)
    monkeypatch.delenv("VANI_SARVAM_LIVE", raising=False)
    monkeypatch.delenv("SARVAM_WEBHOOK_URL", raising=False)
    return tmp_path


def test_instruction_is_spoken_text_with_known_variables_only():
    for gender in ("female", "male"):
        text = build_instruction(gender)
        assert not missing_placeholders(text)
        assert "Output JSON" not in text and "9. Output on this voice platform" in text  # spoken text, not JSON
        assert "End call tool" in text and "never end while the seller is still talking" in text
        assert "9 AM and 6 PM" in text and "between 11 AM and 5 PM" not in text and "{{company_name}}" in text
        assert "timings subah nau se shaam chhe baje tak fixed" in text and "Kya aap kuch keh rahe the?" in text
    assert "Rohan (male voice: bol raha hoon" in build_instruction("male") and "Payal (female voice: bol rahi hoon" in build_instruction("female")


def test_every_persona_maps_to_an_agent_with_all_variables():
    agents = voice_agents()
    for over in ({}, {"annual_turnover": "5 - 25 Cr"}, {"seller_state": "Tamil Nadu"}, {"bot_attempts": 4},
                 {"calls_meeting_fixed": 1}, {"already_in_touch_with_executive": 1}):
        p = generate_persona(seller(**over)).to_dict()
        call = agent_variables_for(p)
        assert call["agent_key"] in agents
        assert set(call["agent_variables"]) == set(INPUT_VARIABLES) and all(isinstance(v, str) for v in call["agent_variables"].values())
        assert call["app_overrides"]["initial_bot_message"] == p["conversation_plan"]["opening"]["value"]
        assert call["app_overrides"]["initial_language_name"] in ("Hindi", "English", "Telugu")


def test_bundle_outputs_cover_the_endings():
    b = agent_bundle("vani_female_warm", voice_agents()["vani_female_warm"])
    outcome = next(v for v in b["variables"]["output"] if v["name"] == "call_outcome")
    assert "INFO_SENT" in outcome["values"] and "NO_OUTCOME" in outcome["values"]
    assert set(OUTPUT_VARIABLES) >= {"call_outcome", "slot", "do_not_call"}


def test_outbound_body_follows_the_api_schema_and_masks_the_number(isolated):
    p = generate_persona(seller()).to_dict()
    call = agent_variables_for(p)
    body = sarvam_api.outbound_body({"app_id": "a1", "app_version": 2}, "+919876543210", call, {"seller_id": 1})
    assert body["app_config"]["connection_config"].keys() == {"connection_id", "agent_phone_number"}
    assert body["user_config"]["user_phone_number"] == "+919876543210"
    sarvam_api.create_outbound({"app_id": "a1", "app_version": 2}, "+919876543210", call, {"seller_id": 1})
    logged = (isolated / "sarvam_api.jsonl").read_text(encoding="utf-8")
    assert "dry_run" in logged and "9876543210" not in logged


def test_campaign_leaves_out_blocked_suppressed_and_numberless_sellers(tmp_path, monkeypatch):
    monkeypatch.setattr(build_campaign, "OUT", tmp_path / "campaigns")
    rows = [seller(fk_glusr_usr_id=1), seller(fk_glusr_usr_id=2, do_not_call_requested=1), seller(fk_glusr_usr_id=3),
            seller(fk_glusr_usr_id=4)]
    suppression.add(3, "asked on a call")
    got, left, out = build_campaign.build([1, 2, 3, 4], {1: "+910000000001", 2: "+910000000002", 3: "+910000000003"},
                                          "t", 1, sellers=pd.DataFrame(rows))
    assert sum(len(v) for v in got.values()) == 1
    reasons = dict(left)
    assert "blocked" in reasons[2] and "do-not-call" in reasons[3] and "no phone" in reasons[4]
    key = agent_key(generate_persona(rows[0]).to_dict())
    with open(out / f"{key}.csv", encoding="utf-8") as f:
        r = next(csv.DictReader(f))
    assert r["Phone Number"] == "+910000000001" and r["initial_bot_message"]
    body = json.loads((out / f"{key}.campaign.json").read_text(encoding="utf-8"))
    assert body["allowed_schedule"]["timezone"] == "Asia/Kolkata" and body["app_config"]["retry_config"]["max_retries"] == 2

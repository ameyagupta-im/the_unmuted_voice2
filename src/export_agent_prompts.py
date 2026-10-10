"""Exports the exact system prompt the live engine uses, per seller, as text files
ready to paste into a Sarvam Voice Agent (what is tested locally is what runs on
Sarvam). The engine also switches persona/goal mid-call; on the platform that
state lives in the prompt's per-turn instructions.

  python src/export_agent_prompts.py [seller_id ...]   -> sarvam_agent/<seller_id>_system_prompt.txt
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ROOT  # noqa: E402
from data_pipeline import load_seller_master  # noqa: E402
from persona_generator import generate_persona  # noqa: E402
from prompt_builder import build_system_prompt  # noqa: E402

DEFAULT_IDS = [3419775, 1243794, 56768582]


def initial_state(p):
    return {"language": p["language"]["primary"]["value"], "gender": p["voice"]["gender"]["value"],
            "speaker": p["voice"]["speaker"]["value"], "mode": "DEFAULT", "pace": p["voice"]["pace"]["value"],
            "max_words": p["tone"]["max_words"]["value"], "empathy": p["tone"]["empathy"]["value"],
            "assertiveness": p["tone"]["assertiveness"]["value"], "goal": p["goal"]["value"],
            "fallbacks": p["fallback_goals"], "stage": "understand", "counts": Counter(),
            "limits": p["conversation_plan"]["ask_limits"], "insights": {}, "telugu_offered_done": False}


def main(ids):
    out = ROOT / "sarvam_agent"
    out.mkdir(exist_ok=True)
    sellers = load_seller_master()
    for sid in ids:
        p = generate_persona(sellers.loc[sellers.fk_glusr_usr_id == sid].iloc[0].to_dict()).to_dict()
        if p["blocked"]:
            print(sid, "blocked (do-not-call), no agent prompt")
            continue
        text = build_system_prompt(p, initial_state(p))
        opening = p["conversation_plan"]["opening"]["value"]
        (out / f"{sid}_system_prompt.txt").write_text(text, encoding="utf-8")
        (out / f"{sid}_initial_message.txt").write_text(opening, encoding="utf-8")
        print(f"{sid}: {len(text):,} chars, voice {p['voice']['speaker']['value']}, pace {p['voice']['pace']['value']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main([int(x) for x in sys.argv[1:]] or DEFAULT_IDS)

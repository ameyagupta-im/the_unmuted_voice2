import json
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

picks = pd.read_csv("outputs/audio_demo/sample_picks.csv")
turns = pd.read_csv("data/ps07_call_turns.csv")

results = []
for _, r in picks.iterrows():
    attempt_id = int(r.attempt_id)
    out_path = f"outputs/audio_demo/stt_raw/{attempt_id}.mp3.json"
    with open(out_path, "r", encoding="utf-8") as f:
        stt_json = json.load(f)

    gt = turns[turns.attempt_id == attempt_id].sort_values("turn_no")
    gt_text = " | ".join(f"[{t.speaker}] {t.text}" for t in gt.itertuples())

    results.append(
        {
            "attempt_id": attempt_id,
            "disposition": r.disposition_label,
            "duration_sec": r.lead_call_duration,
            "sarvam_stt_language_code": stt_json.get("language_code"),
            "sarvam_stt_language_probability": stt_json.get("language_probability"),
            "sarvam_stt_transcript": stt_json.get("transcript"),
            "ground_truth_turns": gt_text,
        }
    )
    print(f"\n=== attempt {attempt_id} | {r.disposition_label} | {r.lead_call_duration}s ===")
    print("Detected language:", stt_json.get("language_code"), stt_json.get("language_probability"))
    print("STT transcript (Devanagari):")
    print(" ", stt_json.get("transcript"))
    print("Ground-truth turns (Romanized Hinglish):")
    print(" ", gt_text)

with open("outputs/audio_demo/stt_vs_groundtruth.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nSaved outputs/audio_demo/stt_vs_groundtruth.json")

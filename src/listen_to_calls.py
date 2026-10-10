"""Listen to a handful of real VANI bot-call recordings via Sarvam's batch
Speech-to-Text job (Saaras), and cross-check against the provided ground-truth
turn transcripts where available. Exploratory / evidence-gathering script,
not part of the production pipeline.
"""
import json
import os

import pandas as pd
from sarvamai import SarvamAI


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env_file()
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

picks = pd.read_csv("outputs/audio_demo/sample_picks.csv")
file_paths = [f"outputs/audio_demo/raw/{int(a)}.mp3" for a in picks.attempt_id]

job = client.speech_to_text_job.create_job(
    model="saaras:v3",
    mode="transcribe",
    language_code="unknown",
    with_timestamps=True,
)
print("job_id:", job.job_id)

job.upload_files(file_paths)
print("uploaded", len(file_paths), "files")

client.speech_to_text_job.start(job.job_id)
status = job.wait_until_complete(poll_interval=5, timeout=300)
print("final state:", status.job_state)

out_dir = "outputs/audio_demo/stt_raw"
os.makedirs(out_dir, exist_ok=True)
job.download_outputs(out_dir)
print("downloaded outputs to", out_dir)

mappings = job.get_output_mappings()
print(mappings)

turns = pd.read_csv("data/ps07_call_turns.csv")
results = []
for _, r in picks.iterrows():
    attempt_id = int(r.attempt_id)
    in_name = f"{attempt_id}.mp3"
    out_name = next((m["output_file"] for m in mappings if m["input_file"] == in_name), None)
    stt_text = None
    if out_name:
        out_path = os.path.join(out_dir, out_name)
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                stt_json = json.load(f)
            stt_text = stt_json.get("transcript")

    gt = turns[turns.attempt_id == attempt_id].sort_values("turn_no")
    gt_text = " | ".join(f"[{t.speaker}] {t.text}" for t in gt.itertuples())

    results.append(
        {
            "attempt_id": attempt_id,
            "disposition": r.disposition_label,
            "duration_sec": r.lead_call_duration,
            "sarvam_stt_transcript": stt_text,
            "ground_truth_turns": gt_text,
        }
    )
    print(f"\n--- attempt {attempt_id} ({r.disposition_label}, {r.lead_call_duration}s) ---")
    print("STT  :", (stt_text or "")[:400])
    print("Turns:", gt_text[:400])

with open("outputs/audio_demo/stt_vs_groundtruth.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nSaved outputs/audio_demo/stt_vs_groundtruth.json")

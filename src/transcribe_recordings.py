"""Transcribes the bot call recordings (data/bot_recordings_raw) with Sarvam's
batch Speech-to-Text job: saaras, translit mode (Roman text, same script as the
signal detector), speaker diarization (bot vs seller).

  python src/transcribe_recordings.py [--limit N]

Writes outputs/recordings/stt/<file>.json (raw) and
outputs/recordings/turns.csv (one row per diarized turn, bot/seller resolved).
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ROOT, OUTPUTS, client  # noqa: E402

INDEX = ROOT / "data" / "bot_recordings_raw" / "index.json"
OUT = OUTPUTS / "recordings"
BOT_CUES = re.compile(r"indiamart|india\s*mart|payal|vani|virtual\s*assistant|sales\s*executive|bol\s*rahi\s*hoon|"
                      r"meeting\s*fix|catalog|enquir|inquir", re.I)


def safe_name(row):
    return f"{row['folder'].split()[0].lower()}_{row['id']}.{row['ext']}"


def run_jobs(rows, batch_size=20):
    stt_dir = OUT / "stt"
    stt_dir.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if not (stt_dir / f"{safe_name(r)}.json").exists()]
    print(f"{len(todo)} to transcribe ({len(rows) - len(todo)} cached)")
    for i in range(0, len(todo), batch_size):
        chunk = todo[i:i + batch_size]
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for r in chunk:
                dst = os.path.join(tmp, safe_name(r))  # ASCII names, no spaces/parentheses
                shutil.copyfile(r["path"], dst)
                paths.append(dst)
            job = client().speech_to_text_job.create_job(
                model="saaras:v3", mode="translit", language_code="unknown",
                with_diarization=True, num_speakers=2, with_timestamps=True)
            job.upload_files(paths, timeout=300)
            client().speech_to_text_job.start(job.job_id)
            status = job.wait_until_complete(poll_interval=5, timeout=1800)
            print(f"  batch {i // batch_size + 1}: {status.job_state}")
            job.download_outputs(str(stt_dir))
            res = job.get_file_results()
            for f in res["failed"]:
                print("   failed:", f["file_name"], f["error_message"])


def resolve_turns(rows):
    out = []
    for r in rows:
        p = OUT / "stt" / f"{safe_name(r)}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        entries = (d.get("diarized_transcript") or {}).get("entries") or []
        if not entries:
            continue
        # bot = the speaker whose words carry IndiaMART/agent cues; tie -> who spoke first
        score = {}
        for e in entries:
            score.setdefault(e["speaker_id"], 0)
            score[e["speaker_id"]] += len(BOT_CUES.findall(e.get("transcript", "")))
        first = entries[0]["speaker_id"]
        bot = max(score, key=lambda k: (score[k], k == first))
        for n, e in enumerate(entries):
            out.append({"recording": safe_name(r), "folder": r["folder"], "seller_id": r["id"], "turn_no": n + 1,
                        "speaker": "bot" if e["speaker_id"] == bot else "seller",
                        "start_sec": e.get("start_time_seconds"), "end_sec": e.get("end_time_seconds"),
                        "text": e.get("transcript", "").strip(), "language": d.get("language_code")})
    df = pd.DataFrame(out)
    df.to_csv(OUT / "turns.csv", index=False, encoding="utf-8")
    return df


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    rows = json.loads(INDEX.read_text())
    if args.limit:
        rows = rows[:args.limit]
    run_jobs(rows)
    df = resolve_turns(rows)
    print(f"{df.recording.nunique() if len(df) else 0} recordings, {len(df)} turns -> {OUT / 'turns.csv'}")

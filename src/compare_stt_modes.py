"""Saaras `translit` vs `codemix` on phone-quality audio (roadmap Phase 1, item 4).

No local recording has a reference transcript (the 83 recordings are not in ps07_call_turns.csv, and the
5,000-call sample's audio sits behind IndiaMART URLs), so the reference set is built instead:
  - 180 real seller lines from the TEST calls of outputs/eval/signals.jsonl (what sellers actually say),
    plus 20 lines carrying the brand words STT gets wrong ("WhatsApp" was heard as "what is app")
  - each spoken by a Bulbul voice, then cut to 8 kHz (telephone band) before transcription
  - both modes transcribe the same audio; codemix's Devanagari is converted to Roman first, exactly as the
    engine would have to (that extra call is counted in its latency)
Scored: word error rate against the line as written, brand-word accuracy, latency. Caveat in the report:
synthetic speech is cleaner than a real phone line, so absolute WER is optimistic; the comparison is the point.

  python src/compare_stt_modes.py [--n 200]
"""
import argparse
import io
import json
import random
import re
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from config import OUTPUTS, STT_MODEL, client
from persona_generator import VOICES, VOICES_EN
from signal_detector import english_share
from text_normalize import is_devanagari, to_roman
from voice_synth import KEYTERMS, synthesize

OUT = OUTPUTS / "eval"
AUDIO = OUT / "stt_audio"
BRAND_LINES = [
    "WhatsApp pe details bhej do", "What details on WhatsApp?", "Send the catalogue on WhatsApp please",
    "IndiaMART se kaun bol raha hai?", "Mujhe BuyLead ke baare mein batao", "Aapka IndiaMART wala executive kab aayega?",
    "Catalogue update karna hai", "WhatsApp number yahi hai", "BuyLead kitne ka hai?", "IndiaMART pe enquiry kam aati hai",
    "Is this IndiaMART calling?", "Can you send it on WhatsApp?", "Mera catalogue dikha do WhatsApp pe",
    "BuyLead package chahiye", "IndiaMART ka paid package kya hai?", "WhatsApp kar dijiye details",
    "I already have an IndiaMART executive", "Catalogue mein product add karna hai", "Enquiry WhatsApp pe aati hai kya?",
    "BuyLead aur catalogue dono chahiye",
]
BRANDS = {"whatsapp": r"whats\s*app", "indiamart": r"india\s*mart", "buylead": r"buy\s*leads?", "catalogue": r"catalog(ue)?"}


def norm(text: str):
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    t = re.sub(r"\bwhats\s+app\b", "whatsapp", t)
    t = re.sub(r"\bindia\s+mart\b", "indiamart", t)
    t = re.sub(r"\bcatalog\b", "catalogue", t)
    return t.split()


def wer(ref: str, hyp: str) -> float:
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(1, len(r))


def to_phone(wav_bytes: bytes, rate: int = 8000) -> bytes:
    """22.05 kHz Bulbul audio -> 8 kHz mono 16-bit (telephone band), linear interpolation."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        src_rate, x = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n = int(len(x) * rate / src_rate)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(y.tobytes())
    return buf.getvalue()


def lines(n: int, seed=5):
    rows = [json.loads(x) for x in open(OUT / "signals.jsonl", encoding="utf-8")]
    pool = sorted({r["text"] for r in rows if r["split"] == "test" and 3 <= len(r["text"].split()) <= 20
                   and not is_devanagari(r["text"])})
    random.seed(seed)
    picked = random.sample(pool, min(len(pool), n - len(BRAND_LINES)))
    return [{"text": t, "brand": False} for t in picked] + [{"text": t, "brand": True} for t in BRAND_LINES]


def audio_for(i, line):
    path = AUDIO / f"{i:03d}.wav"
    if path.exists():
        return path.read_bytes()
    en = (english_share(line["text"]) or 0) >= 0.7
    voice = list(VOICES_EN.values())[i % len(VOICES_EN)] if en else list(VOICES.values())[i % len(VOICES)]
    wav = to_phone(synthesize(line["text"], speaker=voice, language_code="en-IN" if en else "hi-IN"))
    path.write_bytes(wav)
    return wav


def _retry(fn):
    for attempt in range(6):  # 429s under load: back off 2, 4, 8, 16, 32 s
        try:
            return fn()
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** (attempt + 1))


def stt(audio: bytes, mode: str):
    """Latency = the successful STT call (+ codemix's transliteration), never the back-off waits."""
    t = time.time()
    r = _retry(lambda: client().speech_to_text.transcribe(file=("turn.wav", audio, "audio/wav"), model=STT_MODEL,
                                                         mode=mode, language_code="unknown", keyterms=KEYTERMS))
    ms = (time.time() - t) * 1000
    text = r.transcript or ""
    if is_devanagari(text):  # the engine's regex layer needs Roman text: codemix pays this extra call
        t = time.time()
        text = to_roman(text)
        ms += (time.time() - t) * 1000
    return text, int(ms)


def run_one(i, line):
    try:
        audio = _retry(lambda: audio_for(i, line))
        out = dict(line, i=i)
        for mode in ("translit", "codemix"):
            hyp, ms = stt(audio, mode)
            out[mode] = {"hyp": hyp, "wer": round(wer(line["text"], hyp), 3), "ms": ms,
                         "brands_ok": [b for b, p in BRANDS.items() if re.search(p, line["text"], re.I)
                                       and re.search(p, hyp, re.I)],
                         "brands_ref": [b for b, p in BRANDS.items() if re.search(p, line["text"], re.I)]}
        return out
    except Exception as e:  # one line failing after all retries is skipped and counted, not fatal
        print(f"  skipped line {i}: {type(e).__name__}", flush=True)
        return None


def main(n=200):
    AUDIO.mkdir(parents=True, exist_ok=True)
    items = lines(n)
    with ThreadPoolExecutor(2) as ex:
        results = [r for r in ex.map(lambda a: run_one(*a), enumerate(items)) if r]
    print(f"  {len(results)}/{len(items)} lines scored", flush=True)
    summary = {}
    for mode in ("translit", "codemix"):
        w = [r[mode]["wer"] for r in results]
        ms = sorted(r[mode]["ms"] for r in results)
        ref = sum(len(r[mode]["brands_ref"]) for r in results)
        ok = sum(len(r[mode]["brands_ok"]) for r in results)
        summary[mode] = {"mean_wer": round(float(np.mean(w)), 3), "median_wer": round(float(np.median(w)), 3),
                         "brand_word_accuracy": round(ok / max(1, ref), 3), "brand_words": ref,
                         "p50_ms": ms[len(ms) // 2], "p95_ms": ms[int(len(ms) * 0.95) - 1]}
    t, c = summary["translit"], summary["codemix"]
    winner = "codemix" if (c["mean_wer"] < t["mean_wer"] - 0.02 and c["brand_word_accuracy"] >= t["brand_word_accuracy"]
                           and c["p95_ms"] <= t["p95_ms"] + 300) else "translit"
    report = {"n": len(results), "summary": summary, "winner": winner,
              "rule": "codemix wins only with mean WER at least 2 points lower, brand words no worse, p95 latency at "
                      "most 300 ms higher (the regex layer needs Roman text, so codemix pays a transliteration call)",
              "caveat": "synthetic Bulbul speech cut to 8 kHz: cleaner than a real phone line, so absolute WER is "
                        "optimistic; the comparison between modes is what this measures",
              "results": results}
    (OUT / "stt_mode_comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Saaras translit vs codemix (8 kHz phone-band audio)", "",
          f"{len(results)} real seller lines ({len(BRAND_LINES)} with brand words), spoken by Bulbul and cut to 8 kHz.", "",
          "| Mode | mean WER | median WER | brand words right | p50 ms | p95 ms |", "|---|---|---|---|---|---|"]
    for mode, s in summary.items():
        md.append(f"| {mode} | {s['mean_wer']:.3f} | {s['median_wer']:.3f} | {s['brand_word_accuracy']:.0%} of "
                  f"{s['brand_words']} | {s['p50_ms']} | {s['p95_ms']} |")
    md += ["", f"**Default: {winner}.** {report['rule']}.", "", f"Caveat: {report['caveat']}."]
    (OUT / "stt_mode_comparison.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    main(ap.parse_args().n)

"""Turn latency, stage by stage, on the live scenario-suite lines (real Sarvam calls: LLM, TTS, transliterate).

    python tests/latency_bench.py [--tts] [--scenarios 12] [--tag before]
    -> outputs/perf/latency_<tag>.json and a table on stdout

Counts every Sarvam call per turn and its time, so a retry, a transliteration or a slow TTS shows up by name.
"""
import argparse
import json
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from config import OUTPUTS  # noqa: E402

CALLS = []  # (kind, ms) for the current turn


def _wrap(obj, attr, kind):
    fn = getattr(obj, attr)

    def timed(*a, **k):
        t = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            CALLS.append((kind, (time.perf_counter() - t) * 1000))
    setattr(obj, attr, timed)


def instrument():
    c = config.client()
    _wrap(c.chat, "completions", "llm")
    _wrap(c.text_to_speech, "convert", "tts")
    _wrap(c.text, "transliterate", "transliterate")
    _wrap(c.text, "translate", "translate")


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else 0


def main(args):
    instrument()
    import live_engine
    import scenario_suite as S
    rows = []
    for name, sid, lines, _ in S.SCENARIOS[: args.scenarios]:
        call = live_engine.LiveCall(S.persona(sid), synthesize_audio=args.tts)
        CALLS.clear()
        call.start()
        for ln in lines:
            if call.ended:
                break
            CALLS.clear()
            t = time.perf_counter()
            g0 = len(call.guard_corrections)
            r = call.seller_turn(text=ln)
            retry_kinds = [g["kind"] for g in call.guard_corrections[g0:] if g.get("action") == "llm_retry"]
            repair_kinds = [g["kind"] for g in call.guard_corrections[g0:] if g.get("action") == "repaired"]
            retry_kinds += [f"llm_error:{g.get('error')}" for g in call.guard_corrections[g0:] if g["kind"] == "llm_error"]
            total = (time.perf_counter() - t) * 1000
            by = defaultdict(list)
            for k, ms in CALLS:
                by[k].append(ms)
            rows.append({"scenario": name, "seller": ln, "total_ms": round(total), "llm_calls": len(by["llm"]),
                         "llm_ms": [round(x) for x in by["llm"]], "tts_ms": [round(x) for x in by["tts"]],
                         "translit_calls": len(by["transliterate"]), "translit_ms": round(sum(by["transliterate"])),
                         "other_ms": round(total - sum(ms for _, ms in CALLS)), "retry_kinds": retry_kinds,
                         "repair_kinds": repair_kinds, "reply": r.reply})
            print(f"{total:7.0f} ms  llm x{len(by['llm'])} {[round(x) for x in by['llm']]}  tts {[round(x) for x in by['tts']]}  "
                  f"translit x{len(by['transliterate'])} {retry_kinds or ''} | {name}: {ln[:40]}", flush=True)
    tot = [r["total_ms"] for r in rows]
    llm1 = [r["llm_ms"][0] for r in rows if r["llm_ms"]]
    summary = {"turns": len(rows), "total_median": st.median(tot), "total_p90": pct(tot, 0.9), "total_max": max(tot),
               "llm_first_call_median": st.median(llm1) if llm1 else 0,
               "turns_with_llm_retry": sum(r["llm_calls"] > 1 for r in rows),
               "llm_calls_total": sum(r["llm_calls"] for r in rows),
               "turns_without_llm": sum(r["llm_calls"] == 0 for r in rows),
               "translit_calls_total": sum(r["translit_calls"] for r in rows),
               "other_ms_median": st.median(r["other_ms"] for r in rows),
               "retry_kinds": dict(sorted(__import__("collections").Counter(k for r in rows for k in r["retry_kinds"]).items())),
               "repair_kinds": dict(sorted(__import__("collections").Counter(k for r in rows for k in r["repair_kinds"]).items()))}
    print(json.dumps(summary, indent=1))
    out = OUTPUTS / "perf"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"latency_{args.tag}.json").write_text(json.dumps({"summary": summary, "turns": rows}, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts", action="store_true")
    ap.add_argument("--scenarios", type=int, default=100)
    ap.add_argument("--tag", default="run")
    main(ap.parse_args())

"""Learns from the 83 call recordings (transcribed by transcribe_recordings.py).

For each call, an LLM reads the diarized transcript against the playbook and
returns: who the agent is (bot or human executive), every playbook scenario
that occurred with the seller's exact words, how the agent handled it and
whether that handling followed the playbook, the outcome, and phrasings worth
reusing. Speaking rates and turn lengths are measured directly from timestamps.

Writes outputs/recordings/:
  call_analysis.jsonl   one record per call
  lessons.json          what the live agent uses (scenario examples, good
                        phrasings, measured speaking rates)
  recording_insights.md the human-readable report
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUTS, client, LLM_MODEL  # noqa: E402
from playbook import SIGNALS, OUTCOMES  # noqa: E402

OUT = OUTPUTS / "recordings"
SCENARIO_LIST = "\n".join(f"- {s[0]}: {s[3]}" for s in SIGNALS if s[0] not in ("hangup_risk", "context"))

SYSTEM = f"""You review a transcribed outbound call from IndiaMART to a seller (Hindi/Hinglish/English, Roman script).
Speaker labels come from automatic diarization and may occasionally be swapped; judge from content.
Playbook scenarios (seller signal: what the agent should do):
{SCENARIO_LIST}
Return JSON:
{{"agent_type": "bot" | "human_executive",
  "agent_type_reason": "one line",
  "agent_name": "name the agent used or null",
  "call_purpose": "one line",
  "scenarios": [{{"signal": "<one of the scenario names above>", "seller_quote": "exact seller words",
                  "agent_response": "what the agent said next (short quote)",
                  "handled_per_playbook": true | false, "why": "one line"}}],
  "agent_mistakes": ["short items, e.g. pitched after a complaint, ignored a language switch, repeated a question, quoted a price, claimed to be human"],
  "good_phrasings": [{{"situation": "<scenario name or 'opening' / 'understanding' / 'closing'>", "line": "exact agent line worth reusing"}}],
  "outcome": one of {OUTCOMES + ["UNCLEAR"]},
  "seller_need": "what the seller actually needed, one line or null"}}
Only list scenarios that really happened. Quotes must be copied from the transcript."""


def transcript_text(g: pd.DataFrame) -> str:
    return "\n".join(f"[{r.speaker}] {r.text}" for r in g.itertuples() if str(r.text).strip())


def analyse_call(g: pd.DataFrame) -> dict:
    for _ in range(3):
        try:
            r = client().chat.completions(
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": transcript_text(g)[:14000]}],
                model=LLM_MODEL, temperature=0.0, max_tokens=2500, response_format={"type": "json_object"})
            return json.loads(r.choices[0].message.content)
        except Exception as e:  # malformed JSON: retry
            err = e
    return {"error": str(err)}


def speaking_rates(turns: pd.DataFrame) -> dict:
    t = turns.copy()
    t["words"] = t.text.fillna("").str.split().str.len()
    t["dur"] = (t.end_sec - t.start_sec).clip(lower=0.2)
    t = t[t.words >= 3]
    rate = t.groupby("speaker").apply(lambda g: g.words.sum() / g.dur.sum(), include_groups=False)
    words = t.groupby("speaker").words.median()
    return {"words_per_sec": {k: round(float(v), 2) for k, v in rate.items()},
            "median_words_per_turn": {k: float(v) for k, v in words.items()}}


def main():
    turns = pd.read_csv(OUT / "turns.csv")
    done = {}
    path = OUT / "call_analysis.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            done[d["recording"]] = d
    with open(path, "a", encoding="utf-8") as f:
        for i, (rec, g) in enumerate(turns.groupby("recording", sort=False)):
            if rec in done:
                continue
            g = g.sort_values("turn_no")
            d = analyse_call(g)
            d.update({"recording": rec, "folder": g.folder.iloc[0], "seller_id": int(g.seller_id.iloc[0]),
                      "n_turns": len(g), "duration_sec": float(g.end_sec.max() or 0), **speaking_rates(g)})
            done[rec] = d
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            print(f"  {i + 1}: {rec} -> {d.get('agent_type')} / {d.get('outcome')} / "
                  f"{[s.get('signal') for s in d.get('scenarios', [])]}", flush=True)
    summarise(list(done.values()), turns)


def summarise(calls, turns):
    ok = [c for c in calls if "error" not in c]
    by_agent = Counter(c.get("agent_type") for c in ok)
    scen = defaultdict(list)
    handled = defaultdict(lambda: Counter())
    for c in ok:
        for s in c.get("scenarios", []) or []:
            sig = s.get("signal")
            if not sig:
                continue
            scen[sig].append({"seller_quote": s.get("seller_quote"), "agent_response": s.get("agent_response"),
                              "agent_type": c.get("agent_type"), "ok": s.get("handled_per_playbook"),
                              "why": s.get("why"), "recording": c["recording"]})
            handled[sig][(c.get("agent_type"), bool(s.get("handled_per_playbook")))] += 1
    mistakes = Counter(m.strip().lower() for c in ok for m in (c.get("agent_mistakes") or []))
    good = defaultdict(list)
    for c in ok:
        for p in c.get("good_phrasings", []) or []:
            if p.get("line"):
                good[p.get("situation", "other")].append({"line": p["line"], "agent_type": c.get("agent_type")})
    rates = defaultdict(list)
    for c in ok:
        for spk, v in (c.get("words_per_sec") or {}).items():
            rates[(c.get("agent_type"), spk)].append(v)
    rate_summary = {f"{a}/{s}": round(float(pd.Series(v).median()), 2) for (a, s), v in rates.items() if v}
    outcomes = Counter((c.get("agent_type"), c.get("outcome")) for c in ok)

    lessons = {
        "n_calls": len(ok), "agent_types": dict(by_agent),
        "speaking_rate_median_wps": rate_summary,
        "scenario_examples": {k: v[:12] for k, v in scen.items()},
        "scenario_handling": {k: {f"{a}:{'ok' if g else 'missed'}": n for (a, g), n in v.items()} for k, v in handled.items()},
        "good_phrasings": {k: v[:8] for k, v in good.items()},
        "common_mistakes": mistakes.most_common(25),
    }
    (OUT / "lessons.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# What the 83 call recordings teach", "",
             f"{len(ok)} calls analysed ({', '.join(f'{k}: {v}' for k, v in by_agent.items())}), "
             f"{len(turns):,} diarized turns. Transcribed with Sarvam Saaras (batch, diarized, translit).", "",
             "## Speaking rate (median words/sec)", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(rate_summary.items())]
    lines += ["", "## Scenarios that occurred, and whether the agent handled them per the playbook", "",
              "| Scenario | occurrences | bot ok / missed | human ok / missed | example seller words |", "|---|---|---|---|---|"]
    for sig, _, _, _ in SIGNALS:
        if sig not in scen:
            continue
        h = handled[sig]
        ex = (scen[sig][0]["seller_quote"] or "").replace("|", "/")[:70]
        lines.append(f"| {sig} | {len(scen[sig])} | {h[('bot', True)]} / {h[('bot', False)]} | "
                     f"{h[('human_executive', True)]} / {h[('human_executive', False)]} | {ex} |")
    lines += ["", "## Most common agent mistakes", ""] + [f"- {m} ({n})" for m, n in mistakes.most_common(15)]
    lines += ["", "## Outcomes", ""] + [f"- {a} / {o}: {n}" for (a, o), n in outcomes.most_common()]
    lines += ["", "## Phrasings worth reusing (by situation)", ""]
    for k, v in good.items():
        lines.append(f"**{k}**")
        lines += [f"- ({x['agent_type']}) {x['line']}" for x in v[:4]]
    (OUT / "recording_insights.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:60]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

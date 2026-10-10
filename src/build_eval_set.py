"""Held-out evaluation set from IndiaMART's own evaluator outputs (roadmap item 5).

Every later change (trained classifiers, streaming, routing) is judged on this set, so it is built once,
split BY CALL (an utterance-level split let near-identical lines from one call land in both halves), and
written to outputs/eval/:

  signals.jsonl        seller questions with the evaluator's category -> playbook signal labels
  incorrect_mf.jsonl   "meeting fixed" calls with the evaluator's verdict on whether the seller really agreed
  disposition.jsonl    detailed outcome per call (call_dropped, callback_requested, not_interested, ...)
  execdrop.jsonl       who ended the call and why
  act_labels.csv       500 seller turns (test calls) with VANI's previous line and the rule-based dialogue
                       act; the `human_act` column is left blank for a person to fill
  manifest.json        counts per file and split

Split: md5(attempt_id) % 10 < 7 -> dev (70%), else test (30%). Patterns and models are tuned on dev only.

  python src/build_eval_set.py
"""
import glob
import hashlib
import json
import random
import sys
from collections import Counter

import pandas as pd

from config import ROOT, OUTPUTS
from utterance import ACTS, dialogue_act

EVAL_DIR = OUTPUTS / "eval"
LABEL_TO_SIGNAL = {  # same mapping as eval_signals.py, plus the categories that map onto other playbook signals
    "AI Bot Confirmation": "ai_bot_suspicion", "Identity Confirmation": "identity_question",
    "Clarification": "confusion", "Frustrated User": "frustration", "Pricing Payment": "price_query",
    "Problem Complaint": "complaint",
}
ACT_SHEET_SIZE = 500


def split_of_call(attempt_id) -> str:
    return "dev" if int(hashlib.md5(str(attempt_id).encode("utf-8")).hexdigest(), 16) % 10 < 7 else "test"


def load_evaluators(agents) -> pd.DataFrame:
    ev = pd.concat([pd.read_csv(f, low_memory=False, usecols=["attempt_id", "fk_glusr_usr_id", "eval_agent", "agent_output"])
                    for f in sorted(glob.glob(str(ROOT / "data" / "ps07_evaluator_outputs_*.csv")))])
    return ev[ev.eval_agent.isin(agents)]


def _json(raw):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def signal_rows(ev):
    for r in ev[ev.eval_agent == "seller_questions"].itertuples():
        d = _json(r.agent_output) or {}
        for q in d.get("questions", []) or []:
            text = (q.get("que_dialogue") or "").strip()
            if not text:
                continue
            cats = q.get("category", []) or []
            yield {"attempt_id": r.attempt_id, "split": split_of_call(r.attempt_id), "text": text, "categories": cats,
                   "labels": sorted({LABEL_TO_SIGNAL[c] for c in cats if c in LABEL_TO_SIGNAL}),
                   "context": q.get("que_context", "")}


def incorrect_mf_rows(ev):
    for r in ev[ev.eval_agent == "incorrect_mf"].itertuples():
        d = _json(r.agent_output)
        if d is None or "incorrect_mf" not in d:
            continue
        yield {"attempt_id": r.attempt_id, "split": split_of_call(r.attempt_id), "incorrect_mf": bool(d["incorrect_mf"]),
               "seller_statements": d.get("seller_statements", []), "bot_statements": d.get("bot_statements", []),
               "seller_final_stance": d.get("seller_final_stance")}


def disposition_rows(ev):
    for r in ev[ev.eval_agent == "disposition"].itertuples():
        d = _json(r.agent_output)
        if d and d.get("disposition"):
            yield {"attempt_id": r.attempt_id, "split": split_of_call(r.attempt_id), "disposition": d["disposition"],
                   "sub_disposition": d.get("sub_disposition"), "next_action": d.get("next_action"),
                   "confidence": d.get("confidence")}


def execdrop_rows(ev):
    for r in ev[ev.eval_agent == "execdrop"].itertuples():
        d = _json(r.agent_output)
        if d and d.get("who_ended_call"):
            yield {"attempt_id": r.attempt_id, "split": split_of_call(r.attempt_id), "who_ended_call": d["who_ended_call"],
                   "seller_tried_after_closure": d.get("seller_tried_after_closure"), "explanation": d.get("explanation")}


def act_sheet(seed=11) -> pd.DataFrame:
    """500 seller turns from TEST calls, each with VANI's line before it, for hand-labelling dialogue acts."""
    turns = pd.read_csv(ROOT / "data" / "ps07_call_turns.csv", low_memory=False)
    turns = turns.sort_values(["attempt_id", "turn_no"])
    turns["prev_bot"] = turns.groupby("attempt_id").text.shift(1).where(turns.groupby("attempt_id").speaker.shift(1) == "bot")
    sellers = turns[(turns.speaker == "seller") & turns.text.notna() & turns.prev_bot.notna()]
    sellers = sellers[sellers.attempt_id.map(split_of_call) == "test"]
    sellers = sellers[sellers.text.str.split().str.len().between(1, 30)]
    # stratify by the rule-based act so rare acts (request, closing) are not swamped by statements
    sellers = sellers.assign(rule_act=sellers.text.map(dialogue_act))
    per = ACT_SHEET_SIZE // len(ACTS)
    parts = [g.sample(min(len(g), per), random_state=seed) for _, g in sellers.groupby("rule_act")]
    sheet = pd.concat(parts)
    if len(sheet) < ACT_SHEET_SIZE:
        rest = sellers.drop(sheet.index)
        sheet = pd.concat([sheet, rest.sample(min(len(rest), ACT_SHEET_SIZE - len(sheet)), random_state=seed)])
    sheet = sheet.sample(frac=1, random_state=seed)  # shuffle so the labeller does not see the rule's grouping
    return pd.DataFrame({"attempt_id": sheet.attempt_id, "turn_no": sheet.turn_no, "vani_before": sheet.prev_bot,
                         "seller_text": sheet.text, "rule_act": sheet.rule_act, "human_act": ""})


def _write_jsonl(name, rows):
    rows = list(rows)
    with open(EVAL_DIR / name, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return {"rows": len(rows), "by_split": dict(Counter(r["split"] for r in rows))}


def main():
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    ev = load_evaluators({"seller_questions", "incorrect_mf", "disposition", "execdrop"})
    manifest = {"split": "by call: md5(attempt_id) % 10 < 7 -> dev, else test",
                "signals.jsonl": _write_jsonl("signals.jsonl", signal_rows(ev)),
                "incorrect_mf.jsonl": _write_jsonl("incorrect_mf.jsonl", incorrect_mf_rows(ev)),
                "disposition.jsonl": _write_jsonl("disposition.jsonl", disposition_rows(ev)),
                "execdrop.jsonl": _write_jsonl("execdrop.jsonl", execdrop_rows(ev))}
    sheet_path = EVAL_DIR / "act_labels.csv"
    if sheet_path.exists() and pd.read_csv(sheet_path).human_act.notna().any():
        print("act_labels.csv already has human labels: left untouched")  # never overwrite a person's work
    else:
        sheet = act_sheet()
        sheet.to_csv(sheet_path, index=False, encoding="utf-8")
        manifest["act_labels.csv"] = {"rows": len(sheet), "by_rule_act": dict(Counter(sheet.rule_act)),
                                      "acts": list(ACTS), "fill": "human_act with one of the acts"}
    (EVAL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

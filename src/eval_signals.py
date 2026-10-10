"""Measures live-signal detection against an INDEPENDENT label source: the
category IndiaMART's own `seller_questions` evaluator assigned to each real
seller utterance (4,718 utterances, Apr-Sep 2026). This closes the gap
flagged in the earlier skeptical review: the detector had never been scored
on a labelled set it was not written from.

Label -> signal mapping:
  AI Bot Confirmation   -> ai_bot_suspicion
  Identity Confirmation -> identity_question
  Clarification         -> confusion
  Frustrated User       -> frustration
  Pricing Payment       -> price_query
  Problem Complaint     -> complaint

Caveats (reported with the numbers, not hidden):
  - labels are not exhaustive: an utterance labelled "Meeting Visit" can still
    contain unlabelled frustration, so precision here is a LOWER bound
  - utterances are scored without the preceding VANI turn; in the live engine
    tier 2 sees the whole conversation, so this understates tier 2
  - tier 2 (LLM) is scored on a stratified sample to keep API cost bounded
"""
import glob
import json
import random
import sys
from collections import Counter, defaultdict

import pandas as pd

from config import ROOT, OUTPUTS, client, LLM_MODEL
from prompt_builder import SIGNAL_DEFINITIONS
from signal_detector import detect_signals, top_signal

LABEL_TO_SIGNAL = {
    "AI Bot Confirmation": "ai_bot_suspicion",
    "Identity Confirmation": "identity_question",
    "Clarification": "confusion",
    "Frustrated User": "frustration",
    "Pricing Payment": "price_query",
    "Problem Complaint": "complaint",
}
SIGNALS = list(LABEL_TO_SIGNAL.values())

# v1 = the definitions the first evaluation ran with; v2 = the shared live definitions
TIER2_DEFS_V1 = """- frustration: annoyed, wants the caller to stop, pushes back sharply
- ai_bot_suspicion: asks whether this is a bot / AI / recorded / computer call
- identity_question: asks who is calling or from where
- confusion: did not understand, asks to repeat or clarify what was meant
- price_query: asks about price, charges, cost, paid or free
- complaint: complains about IndiaMART service, payment, an executive, or no leads
- deferral, rush, interest, declined, hard_refusal, language_switch, human_request, connectivity
Short replies like "haanji?" asking to repeat are confusion."""


def tier2_system(defs: str) -> str:
    return ("Classify one seller utterance from an outbound IndiaMART sales call (Hindi, English or Hinglish).\n"
            f"Return every signal that applies, or \"none\":\n{defs}\nOutput JSON {{\"signals\": [...]}}.")


def load_labelled():
    ev = pd.concat([pd.read_csv(f, low_memory=False)
                    for f in sorted(glob.glob(str(ROOT / "data" / "ps07_evaluator_outputs_*.csv")))])
    rows = []
    for raw in ev[ev.eval_agent == "seller_questions"].agent_output:
        try:
            d = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for q in d.get("questions", []) or []:
            text = (q.get("que_dialogue") or "").strip()
            if text:
                rows.append({"text": text, "labels": {LABEL_TO_SIGNAL[c] for c in q.get("category", []) or []
                                                      if c in LABEL_TO_SIGNAL}})
    return rows


def split_of(text: str) -> str:
    """Deterministic 60/40 dev/test split by content hash. Patterns are mined only
    from dev misses; all reported numbers are on test."""
    import hashlib
    return "dev" if int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % 10 < 6 else "test"


def tier1(text):
    return {h.signal for h in detect_signals(text)}


def tier1_only_report(tag: str):
    rows = load_labelled()
    for r in rows:
        r["pred"] = tier1(r["text"])
    test = [r for r in rows if split_of(r["text"]) == "test"]
    dev = [r for r in rows if split_of(r["text"]) == "dev"]
    res = {"tag": tag, "test": score(test, None, "t1"), "n_test": len(test), "n_dev": len(dev)}
    path = OUTPUTS / "evidence" / f"signal_eval_tier1_{tag}.json"
    path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res, dev


def tier2(text, defs=SIGNAL_DEFINITIONS):
    for _ in range(2):
        try:
            r = client().chat.completions(
                messages=[{"role": "system", "content": tier2_system(defs)}, {"role": "user", "content": text}],
                model=LLM_MODEL, temperature=0.0, max_tokens=120, response_format={"type": "json_object"})
            return {s for s in json.loads(r.choices[0].message.content).get("signals", []) if s != "none"}
        except Exception:
            continue
    return set()


def score(rows, predict, name):
    out = {}
    for sig in SIGNALS:
        tp = sum(1 for r in rows if sig in r["labels"] and sig in r["pred"])
        fn = sum(1 for r in rows if sig in r["labels"] and sig not in r["pred"])
        fp = sum(1 for r in rows if sig not in r["labels"] and sig in r["pred"])
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
        out[sig] = {"support": tp + fn, "precision_lower_bound": prec and round(prec, 3),
                    "recall": rec and round(rec, 3), "f1": f1 and round(f1, 3), "tp": tp, "fp": fp, "fn": fn}
    return out


def main(tier2_per_class=25, seed=7):
    rows = load_labelled()
    test = [r for r in rows if split_of(r["text"]) == "test"]
    for r in test:
        r["pred"] = tier1(r["text"])
    t1_test = score(test, None, "tier1")

    random.seed(seed)
    by_sig = defaultdict(list)
    for r in test:
        for s in r["labels"]:
            by_sig[s].append(r)
    sample, seen = [], set()
    for s in SIGNALS:
        for r in random.sample(by_sig[s], min(tier2_per_class, len(by_sig[s]))):
            if id(r) not in seen:
                sample.append(r)
                seen.add(id(r))
    negatives = [r for r in test if not r["labels"]]
    sample += random.sample(negatives, min(tier2_per_class * 2, len(negatives)))

    for i, r in enumerate(sample):
        r["t1"] = tier1(r["text"])
        r["t2v1"] = tier2(r["text"], TIER2_DEFS_V1)
        r["t2v2"] = tier2(r["text"], SIGNAL_DEFINITIONS)
        if i % 25 == 0:
            print(f"  tier-2 {i}/{len(sample)}", flush=True)

    def run(key_fn):
        for r in sample:
            r["pred"] = key_fn(r)
        return score(sample, None, "")

    s_t1 = run(lambda r: r["t1"])
    s_t2v1 = run(lambda r: r["t2v1"])
    s_t2v2 = run(lambda r: r["t2v2"])
    s_both = run(lambda r: r["t1"] | r["t2v2"])

    result = {
        "n_labelled_utterances": len(rows), "n_test": len(test),
        "split": "deterministic 60/40 dev/test by md5(text); regex v2 patterns and v2 definitions were revised "
                 "using dev-split errors only; every number here is on test",
        "tier1_regex_on_test": t1_test,
        "stratified_test_sample_size": len(sample),
        "sample_tier1": s_t1, "sample_tier2_v1_defs": s_t2v1, "sample_tier2_v2_defs": s_t2v2,
        "sample_combined_live_engine": s_both,
        "caveats": ["precision is a lower bound (labels are not exhaustive: e.g. 'aap kahan se bol rahe ho' is labelled "
                    "Location, not Identity)",
                    "IndiaMART's 'Clarification' label also covers logistics questions ('kal kis time?') which VANI's "
                    "confusion signal deliberately excludes, so confusion recall is understated",
                    "utterances scored without the preceding VANI turn; the live engine's tier 2 sees the full call",
                    "tier 2 scored on a stratified test sample, not every test utterance",
                    "8 example misses per class were viewed from the full set before the split was introduced "
                    "(minor test contamination)"],
    }
    (OUTPUTS / "evidence" / "signal_eval.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                           encoding="utf-8")

    def fmt(x):
        return "-" if x is None else f"{x:.2f}"
    lines = ["# Live-signal detection vs IndiaMART evaluator labels (held-out test split)", "",
             f"{len(rows):,} real seller utterances labelled by IndiaMART's `seller_questions` evaluator; "
             f"{len(test):,} in the held-out test split. Tier 2 scored on a stratified test sample of {len(sample)}.", "",
             "| Signal | test support | tier-1 regex P | tier-1 regex R | tier-2 v1 R | tier-2 v2 R | tier-2 v2 P | live (tier-1 ∪ tier-2 v2) P | live R |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in SIGNALS:
        a, c1, c2, d = t1_test[s], s_t2v1[s], s_t2v2[s], s_both[s]
        lines.append(f"| {s} | {a['support']} | {fmt(a['precision_lower_bound'])} | {fmt(a['recall'])} | "
                     f"{fmt(c1['recall'])} | {fmt(c2['recall'])} | {fmt(c2['precision_lower_bound'])} | "
                     f"{fmt(d['precision_lower_bound'])} | {fmt(d['recall'])} |")
    lines += ["", "Caveats:"] + [f"- {c}" for c in result["caveats"]]
    (OUTPUTS / "evidence" / "signal_eval.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def _pr(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return p and round(p, 3), r and round(r, 3)


def act_report(eval_dir):
    """Dialogue acts (utterance.py). Two views:
    - weak: every `seller_questions` utterance is something the seller ASKED (by IndiaMART's evaluator), so it
      should come out as question or request; the share that does is the act layer's recall on asks
    - human: per-act precision/recall on act_labels.csv once its human_act column is filled"""
    from utterance import ACTS, dialogue_act
    rows = [json.loads(x) for x in open(eval_dir / "signals.jsonl", encoding="utf-8")]
    test = [r for r in rows if r["split"] == "test"]
    acts = Counter(dialogue_act(r["text"]) for r in test)
    weak = {"n": len(test), "ask_recall": round((acts["question"] + acts["request"]) / max(1, len(test)), 3),
            "predicted": dict(acts)}
    human = None
    sheet = eval_dir / "act_labels.csv"
    if sheet.exists():
        df = pd.read_csv(sheet).dropna(subset=["human_act"])
        df = df[df.human_act.isin(ACTS)]
        if len(df):
            pred = df.seller_text.map(dialogue_act)
            human = {"n": len(df), "accuracy": round(float((pred == df.human_act).mean()), 3), "per_act": {}}
            for a in ACTS:
                tp = int(((pred == a) & (df.human_act == a)).sum())
                fp = int(((pred == a) & (df.human_act != a)).sum())
                fn = int(((pred != a) & (df.human_act == a)).sum())
                p, r = _pr(tp, fp, fn)
                human["per_act"][a] = {"support": tp + fn, "precision": p, "recall": r}
    return weak, human


def offline_report():
    """No API calls: tier-1 signals and dialogue acts on the BY-CALL test split from build_eval_set.py."""
    eval_dir = OUTPUTS / "eval"
    if not (eval_dir / "signals.jsonl").exists():
        raise SystemExit("run python src/build_eval_set.py first")
    rows = [json.loads(x) for x in open(eval_dir / "signals.jsonl", encoding="utf-8")]
    test = [dict(r, labels=set(r["labels"]), pred=tier1(r["text"])) for r in rows if r["split"] == "test"]
    sig = score(test, None, "tier1")
    weak, human = act_report(eval_dir)
    result = {"split": "by call (build_eval_set.py)", "n_test_utterances": len(test), "tier1_signals": sig,
              "acts_weak": weak, "acts_human": human}
    (eval_dir / "eval_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    fmt = lambda x: "-" if x is None else f"{x:.2f}"  # noqa: E731
    lines = ["# Offline evaluation (test split by call)", "",
             f"{len(test):,} labelled seller utterances from test calls.", "",
             "## Signals (tier-1 regex)", "", "| Signal | support | precision (lower bound) | recall |", "|---|---|---|---|"]
    lines += [f"| {s} | {v['support']} | {fmt(v['precision_lower_bound'])} | {fmt(v['recall'])} |" for s, v in sig.items()]
    lines += ["", "## Dialogue acts", "",
              f"Weak labels: of {weak['n']:,} utterances IndiaMART's evaluator marks as seller questions, "
              f"{weak['ask_recall']:.0%} are classified as question or request. Predicted: "
              + ", ".join(f"{k} {v}" for k, v in sorted(weak["predicted"].items(), key=lambda x: -x[1])) + "."]
    if human:
        lines += ["", f"Human labels ({human['n']} turns): accuracy {human['accuracy']:.0%}.", "",
                  "| Act | support | precision | recall |", "|---|---|---|---|"]
        lines += [f"| {a} | {v['support']} | {fmt(v['precision'])} | {fmt(v['recall'])} |" for a, v in human["per_act"].items()]
    else:
        lines += ["", "Human labels: not yet filled (outputs/eval/act_labels.csv, column human_act)."]
    (eval_dir / "eval_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    offline_report() if "--offline" in sys.argv else main()

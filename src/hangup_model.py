"""Hang-up risk model (playbook scenario 19).

Label: a seller turn is "at risk" if the call ends within the next 2 turns
without a meeting being fixed (the seller is about to drop off).
Features use only what the live engine knows at that moment about the seller's
turn and the call so far -- no future information:
  words, duration, words/sec, response delay after VANI stopped, turn index,
  short replies so far, length of VANI's previous turn, words vs the seller's
  own previous turn.
Trained on ps07_call_turns.csv (12,788 calls), split BY CALL 70/30.

  python src/hangup_model.py   -> outputs/models/hangup_model.json + report
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ROOT, OUTPUTS  # noqa: E402
from signal_detector import detect_signals  # noqa: E402

FEATURES = ["words", "dur", "wps", "delay", "turn_idx", "short_so_far", "prev_bot_words", "rel_prev",
            "ack_only", "is_question", "negative_cue"]
_ACK = {"haan", "han", "ha", "ji", "jee", "ok", "okay", "hmm", "hm", "achha", "accha", "acha", "theek", "thik", "hai",
        "haanji", "hello", "yes"}
_NEG = {"frustration", "not_interested", "do_not_call", "busy", "complaint"}  # playbook signal names
MODEL_PATH = OUTPUTS / "models" / "hangup_model.json"
DEFAULTS = {"dur": 1.6, "delay": 0.8}  # medians from training data; used when the live turn was typed


def turn_features(words, dur, delay, turn_idx, short_so_far, prev_bot_words, prev_seller_words, text=""):
    dur = dur if dur is not None else DEFAULTS["dur"]
    delay = delay if delay is not None else DEFAULTS["delay"]
    toks = [t.strip(".,?!").lower() for t in str(text).split()]
    return {"words": words, "dur": dur, "wps": words / max(dur, 0.2), "delay": delay, "turn_idx": turn_idx,
            "short_so_far": short_so_far, "prev_bot_words": prev_bot_words,
            "rel_prev": words / max(prev_seller_words, 1) if prev_seller_words else 1.0,
            "ack_only": float(bool(toks) and all(t in _ACK for t in toks)),
            "is_question": float("?" in str(text)),
            "negative_cue": float(any(h.signal in _NEG for h in detect_signals(str(text))))}


def build(turns: pd.DataFrame, seller_ended: set) -> pd.DataFrame:
    """Label: the turn is among the seller's last 2 turns in a call the SELLER ended
    (execdrop evaluator). A first version labelled any call ending within 2 turns
    without a meeting, which also counted polite closings: test AUC 0.56."""
    rows = []
    for aid, g in turns.groupby("attempt_id", sort=False):
        g = g.sort_values("turn_no").reset_index(drop=True)
        seller_idx = list(g.index[g.speaker == "seller"])
        last_two = set(seller_idx[-2:])
        short, prev_bot_end, prev_bot_words, prev_seller_words = 0, None, 0, None
        for i, r in g.iterrows():
            words = len(str(r.text).split())
            if r.speaker == "bot":
                prev_bot_end, prev_bot_words = r.end_sec, words
                continue
            delay = max(0.0, r.start_sec - prev_bot_end) if prev_bot_end is not None else None
            f = turn_features(words, max(r.end_sec - r.start_sec, 0.1), delay, i, short, prev_bot_words,
                              prev_seller_words, r.text)
            f["label"] = int(aid in seller_ended and i in last_two)
            f["attempt_id"] = aid
            f["text"] = str(r.text)
            rows.append(f)
            short += words <= 2
            prev_seller_words = words
    return pd.DataFrame(rows)


def train():
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    import glob

    turns = pd.read_csv(ROOT / "data" / "ps07_call_turns.csv")
    ev = pd.concat([pd.read_csv(f, low_memory=False)
                    for f in sorted(glob.glob(str(ROOT / "data" / "ps07_evaluator_outputs_*.csv")))])
    ex = ev[ev.eval_agent == "execdrop"]
    who = ex.agent_output.map(lambda s: json.loads(s).get("who_ended_call"))
    seller_ended = set(ex.attempt_id[who == "SELLER"])
    turns = turns[turns.attempt_id.isin(set(ex.attempt_id))]  # only calls whose ender is known
    df = build(turns, seller_ended)
    calls = df.attempt_id.unique()
    rng = np.random.default_rng(3)
    test_calls = set(rng.choice(calls, size=int(0.3 * len(calls)), replace=False))
    te = df.attempt_id.isin(test_calls)
    X = df[FEATURES].clip(upper=df[FEATURES].quantile(0.99), axis=1)
    mu, sd = X[~te].mean(), X[~te].std().replace(0, 1)
    Z = (X - mu) / sd
    clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(Z[~te], df.label[~te])
    p = clf.predict_proba(Z[te])[:, 1]
    auc = roc_auc_score(df.label[te], p)
    # keyword baseline: frustration / refusal / do-not-call words in the turn
    kw = df[te].text.map(lambda t: int(any(h.signal in _NEG for h in detect_signals(t))))
    auc_kw = roc_auc_score(df.label[te], kw)
    # threshold: flag about 6% of turns
    thr = float(np.quantile(p, 0.94))
    flagged = p >= thr
    precision = float(df.label[te][flagged].mean())
    base_rate = float(df.label[te].mean())
    model = {"features": FEATURES, "mean": mu.to_dict(), "std": sd.to_dict(), "clip": X[~te].quantile(0.99).to_dict(),
             "coef": dict(zip(FEATURES, clf.coef_[0].round(4).tolist())), "intercept": float(clf.intercept_[0]),
             "threshold": round(thr, 3),
             "eval": {"test_auc": round(auc, 3), "keyword_baseline_auc": round(auc_kw, 3),
                      "flag_rate": round(float(flagged.mean()), 3), "precision_at_threshold": round(precision, 3),
                      "base_rate": round(base_rate, 3), "n_train_turns": int((~te).sum()), "n_test_turns": int(te.sum()),
                      "split": "70/30 by call"}}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(json.dumps(model["eval"], indent=2))
    print("coefficients (standardised):", model["coef"])
    return model


_MODEL = None


def risk(features: dict) -> float:
    global _MODEL
    if _MODEL is None:
        _MODEL = json.loads(MODEL_PATH.read_text(encoding="utf-8")) if MODEL_PATH.exists() else {}
    if not _MODEL:
        return 0.0
    z = _MODEL["intercept"]
    for f in _MODEL["features"]:
        x = min(features[f], _MODEL["clip"][f])
        z += _MODEL["coef"][f] * (x - _MODEL["mean"][f]) / _MODEL["std"][f]
    return float(1 / (1 + np.exp(-z)))


def threshold() -> float:
    risk({f: 0 for f in FEATURES})
    return _MODEL.get("threshold", 1.0) if _MODEL else 1.0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    train()
